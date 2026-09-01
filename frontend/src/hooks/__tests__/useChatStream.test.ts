/**
 * useChatStream 编排单测：mock @/api/sse，验证
 * 正常流补丁合并、error 事件、AbortController 停止。
 */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/sse", () => ({
  streamChat: vi.fn(),
}));

import { streamChat } from "@/api/sse";
import { useChatStream, type AiDraft } from "@/hooks/useChatStream";

const mockedStream = vi.mocked(streamChat);

describe("useChatStream", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedStream.mockReset();
  });

  it("正常流：data 追加 content、finish 回填 messageId 并置 completed", async () => {
    mockedStream.mockImplementation(async (_req, handlers) => {
      handlers.onMeta([{ doc_name: "a.md", snippet: "s" }]);
      handlers.onData("你");
      handlers.onData("好");
      handlers.onFinish(7, { status: "ok" });
    });

    const { result } = renderHook(() => useChatStream());
    const patches: Partial<AiDraft>[] = [];
    await act(async () => {
      await result.current.send(1, "hi", { onUpdate: (p) => patches.push(p) });
    });

    // data 增量逐条追加：最后一个 content 补丁即为完整内容
    const lastContent = [...patches]
      .reverse()
      .find((p) => typeof p.content === "string")?.content;
    expect(lastContent).toBe("你好");
    // finish 补丁回填 messageId / postcheck / completed
    expect(patches.at(-1)).toMatchObject({
      state: "completed",
      messageId: 7,
      postcheck: { status: "ok" },
    });
    expect(result.current.streaming).toBe(false);
    expect(result.current.state).toBe("completed");
  });

  it("error 事件：补丁置 error、回调收到友好文案", async () => {
    mockedStream.mockImplementation(async (_req, handlers) => {
      handlers.onErrorEvent("llm_rate_limited", "服务繁忙，请稍后再试");
    });

    const { result } = renderHook(() => useChatStream());
    const onErrorEvent = vi.fn();
    const patches: Partial<AiDraft>[] = [];
    await act(async () => {
      await result.current.send(1, "限流", { onUpdate: (p) => patches.push(p), onErrorEvent });
    });

    expect(onErrorEvent).toHaveBeenCalledWith("llm_rate_limited", "服务繁忙，请稍后再试");
    expect(patches.at(-1)?.state).toBe("error");
    expect(result.current.state).toBe("error");
  });

  it("停止生成：AbortController 中断 → aborted", async () => {
    mockedStream.mockImplementation(async (_req, _handlers, signal) => {
      await new Promise((_resolve, reject) => {
        signal!.addEventListener("abort", () =>
          reject(new DOMException("The user aborted a request.", "AbortError")),
        );
      });
    });

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      const p = result.current.send(1, "q", { onUpdate: () => {} });
      result.current.stop();
      await p;
    });
    expect(result.current.state).toBe("aborted");
    expect(result.current.streaming).toBe(false);
  });

  it("连接正常关闭但未收到 finish：按中断处理", async () => {
    mockedStream.mockImplementation(async () => {
      /* 不派发任何事件即返回 */
    });

    const { result } = renderHook(() => useChatStream());
    const onErrorEvent = vi.fn();
    await act(async () => {
      await result.current.send(1, "q", { onUpdate: () => {}, onErrorEvent });
    });
    expect(result.current.state).toBe("error");
    expect(onErrorEvent).toHaveBeenCalled();
  });
});
