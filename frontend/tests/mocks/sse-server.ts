/**
 * 本地 mock SSE 服务：模拟后端 `POST /api/chat/stream` 的三种事件序列。
 *
 * 用于单元测试（Vitest 可对其发请求）与 Playwright E2E（playwright.config.ts
 * 的 webServer 同时拉起 dev server 与本服务）。
 *
 * 三种序列（按问题关键词分流，便于测试构造）：
 *  - 默认              → meta → data×n → finish（正常流）
 *  - 含「超时/timeout」  → meta → error(llm_timeout)
 *  - 含「限流/429」      → meta → error(llm_rate_limited)
 *  - 含「无关/随便」      → data(兜底话术) → finish（空检索兜底，不调用 LLM）
 */
import http from "node:http";

const PORT = Number(process.env.MOCK_SSE_PORT || 8899);

const FALLBACK_TEXT =
  "抱歉，知识库中没有找到相关信息，请换个方式提问或者联系人工客服。";

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (req.method === "POST" && req.url === "/api/chat/stream") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      let question = "";
      try {
        question = (JSON.parse(body || "{}").question || "") as string;
      } catch {
        /* ignore parse errors */
      }

      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      });

      const sources = [
        { doc_name: "退货政策.md", snippet: "支持 7 天无理由退换货……" },
        { doc_name: "配送时效.md", snippet: "华东地区次日达……" },
      ];

      if (/超时|timeout/i.test(question)) {
        res.write(sse("meta", { sources }));
        res.write(sse("error", { code: "llm_timeout", message: "回答生成超时，请稍后重试" }));
        res.end();
        return;
      }

      if (/限流|429/.test(question)) {
        res.write(sse("meta", { sources }));
        res.write(sse("error", { code: "llm_rate_limited", message: "服务繁忙，请稍后再试" }));
        res.end();
        return;
      }

      if (/无关|随便/.test(question)) {
        // 空检索兜底：不发 meta，直接 data 兜底话术 + finish
        res.write(sse("data", { delta: FALLBACK_TEXT }));
        res.write(sse("finish", { message_id: 10001, postcheck: { status: "ok" } }));
        res.end();
        return;
      }

      // 默认正常流：meta → data×n → finish（带一点延迟模拟流式）
      res.write(sse("meta", { sources }));
      const chunks = question.length > 20 ? question.slice(0, 20) : "好的，这是根据知识库整理的回答。";
      for (const ch of chunks) {
        res.write(sse("data", { delta: ch }));
      }
      res.write(sse("finish", { message_id: 10002, postcheck: { status: "ok" } }));
      res.end();
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ code: "not_found" }));
});

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[mock:sse] listening on http://localhost:${PORT}`);
});
