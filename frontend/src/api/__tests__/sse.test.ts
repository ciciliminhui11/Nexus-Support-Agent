/**
 * streamChat SSE 封装单测：mock @microsoft/fetch-event-source，
 * 通过驱动库回调（onopen/onmessage）验证事件分发与 HTTP 失败路径。
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: vi.fn(),
}));

import { fetchEventSource } from "@microsoft/fetch-event-source";
import { streamChat } from "@/api/sse";

const mockedFetch = vi.mocked(fetchEventSource);

type Config = {
  onopen: (res: Response) => Promise<void>;
  onmessage: (ev: { event: string; data: string }) => void;
  onerror: (err: unknown) => void;
  headers: Record<string, string>;
};

/** 取最后一次 fetchEventSource 调用时库拿到的配置 */
function lastConfig(): Config {
  const calls = mockedFetch.mock.calls;
  return calls[calls.length - 1][1] as Config;
}

function sseMessage(event: string, data: unknown) {
  return { event, data: JSON.stringify(data), id: "", retry: 0 };
}

describe("streamChat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetch.mockReset();
  });

  it("正常流：meta → data×n → finish 依序分发", async () => {
    const onMeta = vi.fn();
    const onData = vi.fn();
    const onFinish = vi.fn();

    mockedFetch.mockImplementation(async () => {
      const cfg = lastConfig();
      cfg.onmessage(sseMessage("meta", { sources: [{ doc_name: "a.md", snippet: "片段" }] }));
      cfg.onmessage(sseMessage("data", { delta: "你" }));
      cfg.onmessage(sseMessage("data", { delta: "好" }));
      cfg.onmessage(sseMessage("finish", { message_id: 42, postcheck: { status: "ok" } }));
    });

    await streamChat(
      { session_id: 1, question: "hi" },
      { onMeta, onData, onFinish, onErrorEvent: vi.fn() },
    );

    expect(onMeta).toHaveBeenCalledWith([{ doc_name: "a.md", snippet: "片段" }]);
    expect(onData.mock.calls.map((c) => c[0]).join("")).toBe("你好");
    expect(onFinish).toHaveBeenCalledWith(42, { status: "ok" });
  });

  it("error 事件：code + message 透传给 onErrorEvent", async () => {
    const onErrorEvent = vi.fn();

    mockedFetch.mockImplementation(async () => {
      const cfg = lastConfig();
      cfg.onmessage(sseMessage("meta", { sources: [] }));
      cfg.onmessage(sseMessage("error", { code: "llm_timeout", message: "回答生成超时，请稍后重试" }));
    });

    await streamChat(
      { session_id: 1, question: "超时" },
      { onMeta: vi.fn(), onData: vi.fn(), onFinish: vi.fn(), onErrorEvent },
    );
    expect(onErrorEvent).toHaveBeenCalledWith("llm_timeout", "回答生成超时，请稍后重试");
  });

  it("非 2xx 响应：onHttpError 收到错误码并抛错（阻止自动重试）", async () => {
    const onHttpError = vi.fn();

    mockedFetch.mockImplementation(async () => {
      const cfg = lastConfig();
      await cfg.onopen({
        ok: false,
        status: 401,
        json: async () => ({ code: "unauthorized", message: "未登录" }),
      } as Response);
      throw new Error("should not reach");
    });

    await expect(
      streamChat(
        { session_id: 1, question: "x" },
        { onMeta: vi.fn(), onData: vi.fn(), onFinish: vi.fn(), onErrorEvent: vi.fn(), onHttpError },
      ),
    ).rejects.toThrow();
    expect(onHttpError).toHaveBeenCalledWith("unauthorized", "未登录");
  });

  it("请求携带 Bearer 令牌（会话有效时）", () => {
    sessionStorage.setItem("nexus_auth_token", "jwt-token");
    try {
      mockedFetch.mockImplementation(async () => {});
      void streamChat(
        { session_id: 1, question: "hi" },
        { onMeta: vi.fn(), onData: vi.fn(), onFinish: vi.fn(), onErrorEvent: vi.fn() },
      );
      expect(lastConfig().headers.Authorization).toBe("Bearer jwt-token");
    } finally {
      sessionStorage.removeItem("nexus_auth_token");
    }
  });
});
