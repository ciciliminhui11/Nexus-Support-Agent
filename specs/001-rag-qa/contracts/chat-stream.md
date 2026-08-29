# 接口契约：RAG 流式问答

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

## 端点

### POST /api/chat/stream

SSE 流式问答端点。调用方携带 JWT（鉴权细节见 003 特性契约），请求体：

```json
{
  "session_id": 1001,
  "question": "本产品的退货政策是什么？"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| session_id | integer | 是 | 会话 ID（须属于当前用户） |
| question | string | 是 | 1~500 字；501 字及以上返回 400 |

**请求头**：`Authorization: Bearer <jwt>`
**响应头**：`Content-Type: text/event-stream`，`Cache-Control: no-cache`，`Connection: keep-alive`

### 前置校验（非流式错误，HTTP 状态码直接返回）

| 场景 | HTTP | 响应体 |
|---|---|---|
| 未鉴权 / JWT 无效 | 401 | `{ "code": "unauthorized", "message": "请先登录" }` |
| 问题超 500 字 | 400 | `{ "code": "question_too_long", "message": "问题长度不能超过 500 字" }` |
| 问题为空 | 400 | `{ "code": "question_empty", "message": "问题不能为空" }` |
| session_id 不属于当前用户 | 403 | `{ "code": "session_forbidden", "message": "无权访问该会话" }` |
| 当日配额已用尽 | 429 | `{ "code": "quota_exceeded", "message": "今日提问次数已用尽，请明天再试" }` |

### SSE 事件协议

每次问答建立一次 SSE 连接，服务端推送事件序列：

| 事件名 | 时机 | data 载荷 | 说明 |
|---|---|---|---|
| `meta` | 回答开始前（有命中时） | `{ "sources": [ {"doc_name": "...", "snippet": "..."} ] }` | 引用来源（去重，按召回顺序） |
| `data` | 生成过程中 | `{ "delta": "文本增量" }` | 每个 token/片段推送一次 |
| `finish` | 流末尾 | `{ "message_id": 123, "postcheck": { "status": "ok"\|"review" } }` | 结束标记；postcheck 为来源后校验结果 |
| `error` | 异常时 | `{ "code": "llm_timeout"\|"llm_rate_limited"\|"llm_error", "message": "友好错误文案" }` | 中断流并结束 |

**线上格式**（每事件两行）：
```
event: meta
data: {"sources":[{"doc_name":"FAQ.md","snippet":"退货时限为 7 天……"}]}

event: data
data: {"delta":"根据知识库，本产品"}

event: data
data: {"delta":"支持 7 天无理由退货。"}

event: finish
data: {"message_id":123,"postcheck":{"status":"ok"}}
```

**空检索兜底**：检索无有效片段时不建立 LLM 连接，直接推送一个 `data` 事件携带固定兜底话术，随后 `finish`：
```
event: data
data: {"delta":"抱歉，知识库中没有找到相关信息，请换个方式提问或者联系人工客服。"}

event: finish
data: {"message_id":124,"postcheck":{"status":"ok"}}
```
（兜底话术的 message 同样持久化，reference_source 为空数组。）

**事件序列约束**：
- `meta` 至多一次，且必须在首个 `data` 之前。
- `finish` 与 `error` 互斥，仅推送其一，且为最后一个事件。
- `error` 出现后不得再推送任何 `data`。
- 中途断流 / LLM 返回空内容按失败处理，推送 `error`（`llm_error`）。

### 持久化行为

流结束后（含兜底）服务端写入两条 Message（role=user / role=ai），AI 消息携带 `reference_source`；若中途 `error`，AI 消息内容为错误文案并标注失败。该行为与数据模型契约见 [data-model.md](../data-model.md)。

## 配置契约（system_config / .env）

| 配置项 | key | 默认值 | 说明 |
|---|---|---|---|
| 每日配额上限 | `daily_quota_limit` | 100 | FR-002 |
| 上下文轮数 N | `context_turns` | 6 | FR-003 |
| 检索 top-k | `rag_top_k` | 6 | FR-004 |
| 相似度阈值 | `rag_similarity_threshold` | 0.55 | FR-004 |
| 上下文 token 上限 | `context_max_tokens` | 6000 | FR-011 截断阈值 |
| LLM 超时（秒） | `llm_timeout_seconds` | 60 | FR-010 |
| LLM 首 token 等待（秒） | `llm_first_token_timeout` | 30 | SC-001/SC-005 |
