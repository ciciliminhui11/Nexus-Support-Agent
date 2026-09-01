/**
 * 流式问答编排（T024）：
 * 发送 → 调用 api/sse.ts → 状态跟踪（connecting/streaming/completed/aborted/error）
 * → 停止（AbortController）→ meta 写 sources / data 追加 content / finish 回填
 * messageId / error 保留已生成内容。
 *
 * 该 hook 只管「正在生成的一条 AI 消息」，通过 onUpdate 把增量补丁交给调用方
 * （ChatPage 以 key 定位并合并进消息列表）。
 */
import { useCallback, useRef, useState } from "react";
import { streamChat } from "@/api/sse";
import type { Postcheck, Source, StreamState } from "@/types";

export type ChatDraftState = StreamState | "idle";

export interface AiDraft {
  content: string;
  sources: Source[];
  state: ChatDraftState;
  messageId: number | null;
  postcheck: Postcheck | null;
}

export interface SendHandlers {
  /** 把补丁合并到当前 AI 消息（调用方以消息 key 定位） */
  onUpdate: (patch: Partial<AiDraft>) => void;
  /** SSE error 事件 / HTTP 失败（code + 友好文案） */
  onErrorEvent?: (code: string, message: string) => void;
  /** finish 事件：拿到真实 messageId */
  onDone?: (messageId: number) => void;
}

export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);
  const [state, setState] = useState<ChatDraftState>("idle");

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const send = useCallback(
    async (sessionId: number, question: string, handlers: SendHandlers) => {
      // 前一条未结束先中断（防御性）
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      const reset: Partial<AiDraft> = {
        content: "",
        sources: [],
        state: "connecting",
        messageId: null,
        postcheck: null,
      };
      setState("connecting");
      handlers.onUpdate(reset);

      let content = "";
      let settled = false;
      const patch = (p: Partial<AiDraft>) => handlers.onUpdate(p);

      try {
        await streamChat(
          { session_id: sessionId, question },
          {
            onMeta: (sources) => patch({ sources, state: "streaming" }),
            onData: (delta) => {
              content += delta;
              patch({ content, state: "streaming" });
            },
            onFinish: (messageId, postcheck) => {
              settled = true;
              patch({ messageId, postcheck, state: "completed" });
              setState("completed");
              handlers.onDone?.(messageId);
            },
            onErrorEvent: (code, message) => {
              settled = true;
              patch({ state: "error" });
              setState("error");
              handlers.onErrorEvent?.(code, message);
            },
            onHttpError: (code, message) => {
              settled = true;
              patch({ state: "error" });
              setState("error");
              handlers.onErrorEvent?.(code, message);
            },
          },
          ctrl.signal,
        );
        // 连接正常关闭但未收到 finish → 视为中断
        if (!settled) {
          patch({ state: "error" });
          setState("error");
          handlers.onErrorEvent?.("llm_error", "回答中断，请稍后重试");
        }
      } catch {
        // streamChat 内部已消化错误；此处捕获兜底
        if (ctrl.signal.aborted) {
          patch({ state: "aborted" });
          setState("aborted");
        } else if (!settled) {
          patch({ state: "error" });
          setState("error");
          handlers.onErrorEvent?.("llm_error", "回答中断，请稍后重试");
        }
      }
    },
    [],
  );

  const streaming = state === "connecting" || state === "streaming";

  return { send, stop, streaming, state };
}
