# 接口契约：前端消费的后端接口

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

本契约定义前端**消费**的后端接口面（REST + SSE）。接口定义归属对应特性（001–005），本文件仅记录前端侧消费要求、鉴权、错误处理与依赖关系；前端实现统一收敛于 `api/http.ts`（axios REST）与 `api/sse.ts`（@microsoft/fetch-event-source 流式，解析零自研）。**前端禁止直接调用大模型/向量检索 API**（宪法原则三）。

## 0. 通用约定

- **鉴权**：除 `register`/`login` 外全部接口带 `Authorization: Bearer <token>`（token 经 `authTokenStore` 读取）；401 → 清登录态并跳登录页（FR-010）。
- **错误响应体**：`{ "code": string, "message": string }`，前端按 `code` 映射友好提示与重试语义。
- **依赖**：003=鉴权、001=问答流、004=会话/消息、002=知识库、005=反馈。接口契约细节以各归属特性的 contracts 为准，本文件如有冲突以前端消费需求为准并标注「需对齐」。

## 1. REST 接口

| 接口 | 方法 | 归属 | 前端用途 | 前端消费要点 |
|---|---|---|---|---|
| `/api/auth/register` | POST | 003 | 注册页 | 提交 {identifier, type, password}；409→已占用、400→格式/密码提示（FR-008/009） |
| `/api/auth/login` | POST | 003 | 登录页 | 返回 access_token + user；401→凭证错误提示；429→重试提示 |
| `/api/auth/me` | GET | 003 | 登录态初始化 | 返回 user + quota{limit,used,remaining}（FR-016 次数提示） |
| `/api/session` | POST | 004 | 新建会话 | 返回新建 session；进入空会话（FR-023） |
| `/api/session/list` | GET | 004 | 会话列表 | 返回会话数组（title/preview/updatedAt）；空→空态（FR-024） |
| `/api/session/{id}/messages` | GET | 004 | 历史加载 | 返回消息数组；含 reference_source/intent_label（FR-024/020） |
| `/api/knowledge/upload` | POST | 002 | 上传 | multipart；onUploadProgress 进度；返回文档进入「处理中」（FR-033/034） |
| `/api/knowledge/list` | GET | 002 | 知识库列表 | 返回文档数组（含状态/failMsg/大小/时间）+ 搜索过滤；轮询刷新用（FR-032/037） |
| `/api/knowledge/{id}` | DELETE | 002 | 删除文档 | 二次确认后调用；返回 204；级联清理向量（FR-035） |
| `/api/knowledge/{id}` | PUT/PATCH | 002 | 重命名/编辑元数据 | **需对齐**：初步方案清单未列改名端点，由 002 补充或本特性用列表重命名 → 跨特性协调项 |
| `/api/message/{id}/feedback` | POST | 005 | 提交反馈 | 提交 {type, text?}；乐观更新+失败回滚（FR-026/027/030） |

> 注：会话删除/重命名（FR-025）与反馈状态回读（FR-028）依赖 004/005 是否提供对应端点，未提供时 v1 前端降级（会话删除/重命名隐藏或本地标记，反馈状态以本会话内服务端返回为准）→ 列为跨特性协调项。

## 2. 流式问答接口（SSE）

**端点**：`POST /api/chat/stream`（001 契约；初步方案文档写的是 GET + query，**以前端消费为准统一为 POST + JSON 体**，携带 `Authorization` 头，问题正文不进 URL 以免长度/日志泄漏）

**请求体**：`{ "session_id": number, "question": string }`

**事件协议**（前端按此解析，见 [data-model.md](../data-model.md) §6）：

| 事件 | 载荷要点 | 前端行为 |
|---|---|---|
| `meta` | `sources[]`（docName + snippet） | 写入当前 AI 消息引用来源（FR-015） |
| `data` | 回答 token 文本 | 追加到当前 AI 消息 content，rAF 节流渲染（FR-013） |
| `finish` | message_id、可选 suggestions[] | 回填 messageId、落定追问建议、状态→completed（FR-013/021） |
| `error` | code（如 llm_timeout / llm_rate_limited）、message | 状态→error，友好提示 + 重试，保留已生成内容（FR-019） |

**前端侧错误处理**：
- HTTP 400 `question_too_long` → 长度提示（前端已前置拦截，作为兜底）
- HTTP 429 `quota_exceeded` → 次数用尽提示（FR-016）
- 401 → 登录过期，跳登录页
- 流中断/网络错误 → 本地 error 状态，可重试

**停止生成**：前端 `AbortController.abort()` 终止当前 fetch 流，已渲染内容保留（FR-014）。

## 3. 跨特性协调项（plan 阶段标记）

1. 问答端点统一为 `POST /api/chat/stream` + JSON 体（与 001 对齐；纠正初步方案文档的 GET+query 写法）。
2. 知识库文档**重命名/编辑**端点（`PUT/PATCH /api/knowledge/{id}`）由 002 补充确认。
3. 会话**重命名/删除**端点由 004 确认；未确认前前端按可选能力降级。
4. 反馈**状态回读**由 005 确认（列表/详情是否返回已有反馈），决定跨会话持久显示的实现方式（FR-028）。
5. 意图标签（FR-020）、追问建议（FR-021）依赖 006/001 可选能力，事件载荷由归属特性定义，前端按缺省容错（字段缺失即不展示）。
