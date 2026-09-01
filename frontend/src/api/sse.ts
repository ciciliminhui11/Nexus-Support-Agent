/**
 * 问答流式封装：基于 @microsoft/fetch-event-source 消费 `POST /api/chat/stream`。
 * 分发 data / meta / finish / error 事件，AbortController.signal 支持停止生成。
 * 解析零自研（库内建 SSE 解析）。
 */
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { API_BASE } from "@/api/http";
import { getToken } from "@/api/authTokenStore";
import type { ChatRequest, Postcheck, Source } from "@/types";

export interface ChatStreamHandlers {
  onMeta: (sources: Source[]) => void;
  onData: (delta: string) => void;
  onFinish: (messageId: number, postcheck: Postcheck) => void;
  /** SSE error 事件（后端友好错误，如 llm_timeout / llm_rate_limited） */
  onErrorEvent: (code: string, message: string) => void;
  /** HTTP 层失败（400/401/429 或网络异常） */
  onHttpError?: (code: string, message: string) => void;
}

/** 终止标志：抛出的 error 需带 retriable=false 阻止库内自动重试 */
class FatalSseError extends Error {
  retriable = false;
}

export async function streamChat(
  request: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  await fetchEventSource(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
    signal,
    openWhenHidden: true,

    async onopen(response) {
      if (!response.ok) {
        let code = "http_error";
        let message = `请求失败（HTTP ${response.status}）`;
        try {
          const body = (await response.json()) as { code?: string; message?: string };
          if (body.code) code = body.code;
          if (body.message) message = body.message;
        } catch {
          /* 非 JSON body，使用默认文案 */
        }
        handlers.onHttpError?.(code, message);
        throw new FatalSseError(message);
      }
    },

    onmessage(event) {
      if (!event.data) return;
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        switch (event.event) {
          case "meta":
            handlers.onMeta((data.sources as Source[]) ?? []);
            break;
          case "data":
            if (typeof data.delta === "string") handlers.onData(data.delta);
            break;
          case "finish":
            handlers.onFinish(data.message_id as number, data.postcheck as Postcheck);
            break;
          case "error":
            handlers.onErrorEvent(
              (data.code as string) ?? "llm_error",
              (data.message as string) ?? "AI 服务暂时不可用",
            );
            break;
          default:
            break;
        }
      } catch {
        /* 单条事件解析失败忽略，不中断流 */
      }
    },

    onerror(error) {
      // 网络中断 / 连接失败 → 通知调用方并终止（不自动重试）
      handlers.onHttpError?.("network_error", "网络连接中断，请稍后重试");
      throw error instanceof FatalSseError ? error : new FatalSseError("network_error");
    },
  });
}
