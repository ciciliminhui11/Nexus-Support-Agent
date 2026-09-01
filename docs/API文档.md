# API 文档

> 版本：0.1.0（对应后端 `backend/app/main.py`）
> 更新时间：2026-09-01
>
> 交互式接口文档（Swagger UI）：`http://localhost:8000/docs`
> 健康检查：`GET http://localhost:8000/healthz` → `{ "status": "ok" }`

本文档覆盖后端全部 HTTP 接口，重点包含**登录、上传文档、RAG 流式问答（SSE）、会话历史查询、反馈提交**五个核心流程的请求/响应示例，以及流式问答的 **SSE 数据格式说明**。

各模块的详细接口契约见 [`specs/`](../specs/) 下对应目录的 `contracts/*.md`。

---

## 1. 通用约定

### 1.1 基础信息

| 项 | 值 |
|---|---|
| Base URL | 开发默认 `http://localhost:8000`（生产按部署环境，见[运行指南](../运行指南.md)） |
| 内容类型 | 请求 `application/json`；文件上传 `multipart/form-data`；流式问答 `text/event-stream` |
| 时间格式 | ISO 8601，如 `2026-08-29T10:00:00`（MySQL 秒级精度） |
| 角色 | `user`（普通用户）、`admin`（管理员，启动时预置，见 `main.py::seed_admin`） |

### 1.2 鉴权

除 `POST /api/auth/register`、`POST /api/auth/login`、`GET /healthz` 外，**所有接口均需登录**：

```
Authorization: Bearer <access_token>
```

- 令牌为 JWT（HS256），有效期默认 24 小时（`jwt_expire_hours`）。
- 缺令牌 / 令牌无效 / 已过期 → `401 { "code": "unauthorized", "message": "请重新登录" }`。
- 普通用户访问管理员专属接口 → `403 { "code": "forbidden", "message": "无权操作" }`。

### 1.3 通用错误响应格式

所有非流式错误统一返回：

```json
{ "code": "错误码", "message": "面向用户的友好文案" }
```

错误码语义与 HTTP 状态码见 [第 9 章 错误码汇总](#9-错误码汇总)。

### 1.4 分页约定

列表接口统一支持 `page`（默认 1，`>=1`）与 `page_size`（默认见各接口，`1~100`）。响应统一为：

```json
{ "total": 42, "items": [ ... ] }
```

---

## 2. 接口总览

### 2.1 核心业务接口

| 方法 | 路径 | 鉴权 | 说明 | 章节 |
|---|---|---|---|---|
| POST | `/api/auth/login` | 否 | 登录，签发 JWT | [3.1](#31-登录-post-apiauthlogin) |
| POST | `/api/auth/register` | 否 | 注册账号（手机号 / 邮箱） | [3.2](#32-注册-post-apiauthregister) |
| GET | `/api/auth/me` | 用户 | 当前账号信息与当日配额 | [3.3](#33-当前账号信息-get-apiauthme) |
| POST | `/api/knowledge/upload` | 管理员 | 上传文档，触发后台入库 | [4.1](#41-上传文档-post-apiknowledgeupload) |
| GET | `/api/knowledge/list` | 管理员 | 文档列表（分页） | [4.2](#42-文档列表-get-apiknowledgelist) |
| GET | `/api/knowledge/{doc_id}` | 管理员 | 单文档详情（含失败原因） | [4.3](#43-文档详情-get-apiknowledgedoc_id) |
| DELETE | `/api/knowledge/{doc_id}` | 管理员 | 删除文档（级联清理） | [4.4](#44-删除文档-delete-apiknowledgedoc_id) |
| POST | `/api/chat/stream` | 用户 | RAG 流式问答（SSE） | [5](#5-rag-问答sse-流式) |
| POST | `/api/session` | 用户 | 创建会话 | [6.1](#61-创建会话-post-apisession) |
| GET | `/api/session/list` | 用户 | 会话列表（分页） | [6.2](#62-会话列表-get-apisessionlist) |
| GET | `/api/session/{session_id}` | 用户 | 会话详情（含消息数） | [6.3](#63-会话详情-get-apisessionsession_id) |
| GET | `/api/session/{session_id}/messages` | 用户 | **会话历史查询**（分页） | [6.4](#64-会话历史查询-get-apisessionsession_idmessages) |
| POST | `/api/message/{message_id}/feedback` | 用户 | **反馈提交**（点赞 / 点踩） | [7.1](#71-提交反馈-post-apimessagemessage_idfeedback) |
| GET | `/api/message/{message_id}/feedback` | 用户 | 查询单条消息的反馈 | [7.2](#72-查询反馈-get-apimessagemessage_idfeedback) |

### 2.2 管理端 / 调试接口

| 方法 | 路径 | 鉴权 | 说明 | 章节 |
|---|---|---|---|---|
| GET | `/api/message/admin/feedback/list` | 管理员 | 反馈全量列表（含消息摘要） | [7.3](#73-管理端反馈列表-get-apimessageadminfeedbacklist) |
| GET | `/api/admin/users` | 管理员 | 用户列表（含额度信息） | [8.1](#81-额度管理-apiadmin) |
| PUT | `/api/admin/users/{user_id}/quota` | 管理员 | 设置单用户每日限额 | [8.1](#81-额度管理-apiadmin) |
| GET | `/api/admin/quota/global` | 管理员 | 查看全局每日限额 | [8.1](#81-额度管理-apiadmin) |
| PUT | `/api/admin/quota/global` | 管理员 | 设置全局每日限额 | [8.1](#81-额度管理-apiadmin) |
| POST | `/api/intent/debug` | 管理员 | 意图识别联调（三层漏斗原始结果） | [8.2](#82-意图识别调试-post-apiintentdebug) |
| GET | `/api/trace/list` | 管理员 | 链路埋点概览列表 | [8.3](#83-链路埋点查询-apitrace) |
| GET | `/api/trace/detail` | 管理员 | 单条链路埋点明细 | [8.3](#83-链路埋点查询-apitrace) |
| GET | `/healthz` | 否 | 健康检查 | — |

---

## 3. 鉴权接口

### 3.1 登录 `POST /api/auth/login`

**请求头**：无（无需鉴权）

**请求体**（`application/json`）：

```json
{
  "account_identifier": "13800138000",
  "account_type": "phone",
  "password": "secret123"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| account_identifier | string | 是 | 手机号（默认 `^1[3-9]\d{9}$`）或邮箱 |
| account_type | enum(`phone`, `email`) | 是 | 标识类型 |
| password | string | 是 | 任意非空字符串（登录不做长度校验） |

**响应 200**：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": { "user_id": 42, "role": "user" }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| access_token | string | JWT，后续请求放入 `Authorization: Bearer <token>` |
| expires_in | int | 有效期秒数（`jwt_expire_hours × 3600`，默认 24h） |
| user | object | 仅含 user_id 与 role |

**错误响应**（统一文案，防账号枚举）：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 账号不存在 / 密码错误 | 401 | `{ "code": "invalid_credentials", "message": "手机号/邮箱或密码错误" }` |
| 连续失败触发防暴破延迟 | 429 | `{ "code": "too_many_attempts", "message": "尝试过于频繁，请 N 秒后再试", "retry_after": N }` |

**curl 示例**：

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"account_identifier":"13800138000","account_type":"phone","password":"secret123"}'
```

### 3.2 注册 `POST /api/auth/register`

**请求体**（字段同登录）：

```json
{
  "account_identifier": "13800138000",
  "account_type": "phone",
  "password": "secret123"
}
```

| 字段 | 约束 |
|---|---|
| account_identifier | 手机号（`^1[3-9]\d{9}$`）或邮箱格式 |
| account_type | enum(`phone`, `email`) |
| password | ≥ 8 位（`min_password_length`），非全空白，UTF-8 ≤ 72 字节 |

**响应 201**：

```json
{
  "user_id": 42,
  "account_identifier": "13800138000",
  "account_type": "phone",
  "role": "user",
  "created_at": "2026-08-29T10:00:00"
}
```

**错误响应**：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 标识格式非法 / 账号类型不支持 | 400 | `{ "code": "invalid_identifier", "message": "手机号或邮箱格式不正确" }` |
| 密码为空 / 过短 | 400 | `{ "code": "password_too_short", "message": "密码长度不能少于 8 位" }` |
| 密码超 72 字节 | 400 | `{ "code": "password_too_long", "message": "密码长度不能超过 72 字节" }` |
| 标识已占用 | 409 | `{ "code": "identifier_taken", "message": "该手机号/邮箱已被注册" }` |

### 3.3 当前账号信息 `GET /api/auth/me`

**请求头**：`Authorization: Bearer <jwt>`

**响应 200**：

```json
{
  "user_id": 42,
  "account_identifier": "13800138000",
  "account_type": "phone",
  "role": "user",
  "created_at": "2026-08-29T10:00:00",
  "quota": { "limit": 100, "used": 12, "remaining": 88 }
}
```

`quota` 为当日提问配额：`limit` 实际生效限额（个人额度优先，未设置时回落全局默认），`used` 当日已用次数，`remaining` 剩余次数。

---

## 4. 知识库接口（管理员专属）

> 全部接口要求 `Authorization: Bearer <jwt>` 且角色为 `admin`。

### 4.1 上传文档 `POST /api/knowledge/upload`

**请求头**：`Authorization: Bearer <admin_jwt>`

**请求体**：`multipart/form-data`，表单字段 `file`（文件流）。

**响应 202 Accepted**（立即返回，不等待后台解析入库）：

```json
{
  "doc_id": 5,
  "doc_name": "FAQ.md",
  "status": "处理中",
  "upload_time": "2026-08-29T10:00:00"
}
```

上传后服务端异步执行「解析 → 切分 → 向量化 → 写入 Chroma」。文档 `status` 流转：`处理中` → `就绪` / `失败`。

**错误响应**：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 格式不支持（仅 txt / markdown） | 400 | `{ "code": "unsupported_format", "message": "仅支持 txt 与 markdown 格式" }` |
| 空文件 / 全空白 | 400 | `{ "code": "empty_file", "message": "文件内容为空" }` |
| 超过大小上限（默认 20MB） | 413 | `{ "code": "file_too_large", "message": "文件大小超过 20MB 上限" }` |
| 未鉴权 | 401 | `{ "code": "unauthorized", "message": "请重新登录" }` |
| 非管理员 | 403 | `{ "code": "forbidden", "message": "无权操作" }` |

**curl 示例**：

```bash
curl -X POST http://localhost:8000/api/knowledge/upload \
  -H 'Authorization: Bearer <admin_jwt>' \
  -F 'file=@./FAQ.md'
```

### 4.2 文档列表 `GET /api/knowledge/list`

**查询参数**：`page`（默认 1）、`page_size`（默认 20，上限 100）。

**响应 200**：

```json
{
  "total": 42,
  "items": [
    { "doc_id": 5, "doc_name": "FAQ.md", "status": "就绪", "upload_time": "2026-08-29T10:00:00", "fail_msg": null }
  ]
}
```

### 4.3 文档详情 `GET /api/knowledge/{doc_id}`

**响应 200**：

```json
{
  "doc_id": 5,
  "doc_name": "FAQ.md",
  "status": "失败",
  "fail_msg": "文本抽取失败：文件编码无法识别（expected utf-8）",
  "upload_time": "2026-08-29T10:00:00"
}
```

文档不存在 → `404 { "code": "doc_not_found", "message": "文档不存在" }`。

### 4.4 删除文档 `DELETE /api/knowledge/{doc_id}`

事务性级联清理：原始文件 + MySQL 元数据 + 全部向量切片。

- 成功 → **204 No Content**（无响应体）。
- 文档不存在 → 404 `doc_not_found`。
- 对「处理中」文档：标记取消，后台任务收敛后完成清理。

---

## 5. RAG 问答（SSE 流式）

### 5.1 `POST /api/chat/stream`

**请求头**：`Authorization: Bearer <jwt>`

**请求体**（`application/json`）：

```json
{
  "session_id": 1001,
  "question": "本产品的退货政策是什么？"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| session_id | int | 是 | `>=1`，须属于当前用户 |
| question | string | 是 | 1~500 字；空 / 501 字及以上直接返回 400 |

**响应头**：

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**前置校验错误**（非流式，HTTP 状态码直接返回，不建立 SSE 连接）：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 未鉴权 / JWT 无效 | 401 | `{ "code": "unauthorized", "message": "请重新登录" }` |
| 问题为空 | 400 | `{ "code": "question_empty", "message": "问题不能为空" }` |
| 问题超 500 字 | 400 | `{ "code": "question_too_long", "message": "问题长度不能超过 500 字" }` |
| session_id 不属于当前用户 | 403 | `{ "code": "session_forbidden", "message": "无权访问该会话" }` |
| 当日配额已用尽 | 429 | `{ "code": "quota_exceeded", "message": "今日提问次数已用尽，请明天再试" }` |

### 5.2 SSE 数据格式说明

#### 线上格式

每次问答建立一次 SSE 连接，服务端按事件推送，**每个事件两行 + 空行**：

```
event: <事件名>
data: <JSON 载荷>

```

即 `event: <type>\ndata: <json>\n\n`（`data` 载荷为 `ensure_ascii=False` 的 UTF-8 JSON）。

#### 事件类型

| 事件名 | 时机 | data 载荷 | 说明 |
|---|---|---|---|
| `meta` | 回答开始前（检索有命中时） | `{ "sources": [ { "doc_name": "...", "snippet": "..." } ] }` | 引用来源，按召回顺序去重后下发，至多一次，必在首个 `data` 之前 |
| `data` | 生成过程中 | `{ "delta": "文本增量" }` | 每个片段 / token 推送一次，客户端拼接 `delta` 得到完整回答 |
| `finish` | 流末尾 | `{ "message_id": 123, "postcheck": { "status": "ok"\|"review" } }` | 结束标记；`message_id` 为已持久化的 AI 消息 ID，`postcheck` 为来源后校验结果 |
| `error` | 异常时 | `{ "code": "llm_timeout"\|"llm_rate_limited"\|"llm_error", "message": "友好错误文案" }` | 中断流并结束 |

**事件序列约束**：

- `meta` 至多一次，且必须在首个 `data` 之前（无命中 / 意图短路时不发送）。
- `finish` 与 `error` 互斥，仅推送其一，且为**最后一个事件**。
- `error` 出现后不得再推送任何 `data`。
- 中途断流 / LLM 返回空内容按失败处理，推送 `error`（`llm_error`）。

#### 完整流示例（检索命中，正常回答）

服务端逐条推送（客户端逐条读取）：

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

#### 意图短路示例（闲聊 / 投诉 / 澄清）

006 意图识别命中 `small_talk` / `complaint` / `clarify` 时**不检索、不调用 LLM**，无 `meta` 事件，直接推 `data` + `finish`：

```
event: data
data: {"delta":"您好，很高兴为您服务！如果您有任何产品、售后方面的问题，随时都可以问我哦～"}

event: finish
data: {"message_id":124,"postcheck":{"status":"ok"}}
```

#### 空检索兜底示例（知识库无命中）

检索无有效片段时不建立 LLM 连接，直接推送固定兜底话术 + `finish`（无 `meta`）：

```
event: data
data: {"delta":"抱歉，知识库中没有找到相关信息，请换个方式提问或者联系人工客服。"}

event: finish
data: {"message_id":125,"postcheck":{"status":"ok"}}
```

#### 异常示例（LLM 层失败）

生成中途 LLM 超时 / 限流 / 服务错误时，推送 `error` 并结束流（不再有 `finish`）：

```
event: error
data: {"code":"llm_timeout","message":"回答生成超时，请稍后重试"}
```

`code` 取值：`llm_timeout` / `llm_rate_limited` / `llm_error`。

### 5.3 前端消费要点

SSE 基于 HTTP，**不能用 `EventSource` 携带 `Authorization` 请求头**，建议用 `fetch` + `ReadableStream` 手动解析，或使用支持自定义请求头的 SSE 库：

1. 发送 `POST /api/chat/stream`，携带 Bearer 令牌与 JSON 请求体。
2. 读取响应流，按空行拆分为事件块，解析每块的 `event:` 与 `data:` 行。
3. 按事件类型处理：`data` → 追加 `delta`；`finish` → 结束并取 `message_id`；`error` → 展示 `message` 并终止。
4. 拼接所有 `delta` 即完整回答；首屏可在首个 `data` 到达前先用 `meta` 的 `sources` 渲染「引用来源」。

---

## 6. 会话与消息历史

### 6.1 创建会话 `POST /api/session`

无请求体。**响应 201**：

```json
{
  "session_id": 1001,
  "title": "新会话",
  "create_time": "2026-08-29T10:00:00"
}
```

标题默认为「新会话」，该会话首条消息发出后自动基于消息内容生成标题。

### 6.2 会话列表 `GET /api/session/list`

**查询参数**：`page`（默认 1）、`page_size`（默认 20）。

**响应 200**：

```json
{
  "total": 3,
  "items": [
    { "session_id": 1001, "title": "退货政策咨询", "create_time": "2026-08-29T10:00:00" }
  ]
}
```

按创建时间倒序。

### 6.3 会话详情 `GET /api/session/{session_id}`

**响应 200**：

```json
{
  "session_id": 1001,
  "title": "退货政策咨询",
  "create_time": "2026-08-29T10:00:00",
  "message_count": 14
}
```

会话不存在 / 不属于当前用户 → `404 { "code": "session_not_found", "message": "会话不存在" }`。

### 6.4 会话历史查询 `GET /api/session/{session_id}/messages`

**查询参数**：`page`（默认 1）、`page_size`（默认 20，上限 100）。

**响应 200**：

```json
{
  "total": 14,
  "items": [
    {
      "message_id": 120,
      "role": "user",
      "content": "本产品的退货政策是什么？",
      "reference_source": null,
      "intent_label": "产品咨询",
      "create_time": "2026-08-29T10:05:00"
    },
    {
      "message_id": 123,
      "role": "ai",
      "content": "根据知识库，本产品支持 7 天无理由退货。",
      "reference_source": [
        { "doc_name": "FAQ.md", "snippet": "退货时限为 7 天……" }
      ],
      "intent_label": null,
      "create_time": "2026-08-29T10:05:03"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| message_id | int | 消息 ID |
| role | enum(`user`, `ai`) | 消息角色 |
| content | string | 消息内容 |
| reference_source | array\|null | AI 消息的引用来源（`{doc_name, snippet}` 列表）；用户消息为 `null` |
| intent_label | string\|null | 用户消息的 006 意图识别标签（`产品咨询` / `售后` / `闲聊` / `投诉` / `未识别`）；AI 消息为 `null` |
| create_time | datetime | 创建时间 |

按时间正序（旧 → 新）。会话不存在 / 不属于当前用户 → 404 `session_not_found`。

---

## 7. 用户反馈

### 7.1 提交反馈 `POST /api/message/{message_id}/feedback`

对某条 **AI 消息** 提交或覆盖点赞 / 点踩反馈（以最后一次提交为准，upsert 语义）。

**请求体**：

```json
{
  "feedback_type": "like",
  "feedback_text": "回答很清晰"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| feedback_type | enum(`like`, `dislike`) | 是 | 点赞 / 点踩 |
| feedback_text | string | 否 | ≤ 200 字（`feedback_max_length`，可配置）；纯空白视同未填写（置 `null`） |

**响应**（新建 `201`，覆盖更新 `200`）：

```json
{
  "message_id": 123,
  "feedback_type": "like",
  "feedback_text": "回答很清晰",
  "updated_at": "2026-08-29T10:06:00"
}
```

**错误响应**：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 消息不存在 / 不属于当前用户会话 | 404 | `{ "code": "message_not_found", "message": "消息不存在" }` |
| 目标不是 AI 消息 | 400 | `{ "code": "not_ai_message", "message": "只能对 AI 回答提交反馈" }` |
| 类型缺失 / 非法 | 400 | `{ "code": "invalid_feedback_type", "message": "必须选择点赞或踩" }` |
| 文字超长 | 400 | `{ "code": "feedback_too_long", "message": "文字反馈不能超过 200 字" }` |

### 7.2 查询反馈 `GET /api/message/{message_id}/feedback`

查询某条消息的反馈：`mine` 为当前用户自己的反馈（无则 `null`），`all` 为全量反馈（统计用途）。

**响应 200**：

```json
{
  "message_id": 123,
  "mine": {
    "feedback_type": "like",
    "feedback_text": "回答很清晰",
    "updated_at": "2026-08-29T10:06:00"
  },
  "all": [
    {
      "user_id": 42,
      "feedback_type": "like",
      "feedback_text": "回答很清晰",
      "updated_at": "2026-08-29T10:06:00"
    }
  ]
}
```

消息不存在 / 越权 → 404 `message_not_found`。

### 7.3 管理端反馈列表 `GET /api/message/admin/feedback/list`

**鉴权**：管理员。

**查询参数**：`page`（默认 1）、`page_size`（默认 20，上限 100）、`feedback_type`（可选过滤 `like` / `dislike`）。

**响应 200**：

```json
{
  "total": 5,
  "items": [
    {
      "feedback_id": 7,
      "message_id": 123,
      "user_id": 42,
      "feedback_type": "dislike",
      "feedback_text": "回答与问题无关",
      "message_content": "根据知识库，本产品支持 7 天无理由退货。",
      "updated_at": "2026-08-29T10:06:00"
    }
  ]
}
```

`message_content` 为对应 AI 消息内容的前 100 字摘要。按更新时间倒序。

---

## 8. 管理端与调试接口

### 8.1 额度管理 `/api/admin`

全部要求管理员权限。

**`GET /api/admin/users`**（`page` / `page_size`）— 用户列表含额度：

```json
{
  "total": 42,
  "items": [
    {
      "user_id": 42,
      "account_identifier": "13800138000",
      "account_type": "phone",
      "role": "user",
      "daily_quota": null,
      "used_today": 12,
      "effective_limit": 100
    }
  ]
}
```

**`PUT /api/admin/users/{user_id}/quota`** — 设置单用户每日限额：

```json
{ "daily_quota": 200 }
```

`daily_quota` 传 `null` 恢复为全局默认。用户不存在 → 404 `user_not_found`。

**`GET /api/admin/quota/global`** → `{ "daily_quota_limit": 100 }`

**`PUT /api/admin/quota/global`** — 设置全局每日限额（需为正整数，否则 400 `invalid_quota`）：

```json
{ "daily_quota": 150 }
```

### 8.2 意图识别调试 `POST /api/intent/debug`

**鉴权**：管理员。透出 006 三层漏斗（规则层 → 小模型层 → 大模型兜底层）各层原始结果与降级原因，供联调校准。

**请求体**：

```json
{ "query": "能退换吗" }
```

`query` 1~500 字，空 / 超长 → 400 `invalid_query`。响应为各层识别明细（结构随 006 实现，详见 [`specs/006-intent-recognition/`](../specs/006-intent-recognition/)）。

### 8.3 链路埋点查询 `/api/trace`

**鉴权**：管理员。查询 008 链路埋点，用于历史回溯定位问题。

**`GET /api/trace/list`** — 按 `trace_id` 聚合的概览列表。可选查询参数：`trace_type`（`ingest` / `chat`）、`doc_id`、`session_id`、`status`（`ok` / `error`）、`time_from`、`time_to`、`page`、`page_size`。

**`GET /api/trace/detail?trace_id=xxx`** — 按 `seq` 还原单条 trace 的全部 span。`trace_id` 不存在 → 404 `trace_not_found`。

---

## 9. 错误码汇总

| HTTP | code | 常见场景 |
|---|---|---|
| 400 | `invalid_identifier` | 注册：标识格式非法 / 账号类型不支持 |
| 400 | `password_too_short` / `password_too_long` | 注册：密码长度不合法 |
| 400 | `question_empty` / `question_too_long` | 问答：问题为空 / 超 500 字 |
| 400 | `invalid_query` | 意图调试：query 为空 / 超 500 字 |
| 400 | `unsupported_format` / `empty_file` | 上传：格式不支持 / 空文件 |
| 400 | `not_ai_message` | 反馈：目标不是 AI 消息 |
| 400 | `invalid_feedback_type` / `feedback_too_long` | 反馈：类型非法 / 文字超长 |
| 400 | `invalid_quota` | 管理端：额度设置不合法 |
| 401 | `unauthorized` | 未鉴权 / 令牌无效或过期 |
| 401 | `invalid_credentials` | 登录失败（账号或密码错误） |
| 403 | `forbidden` | 非管理员访问管理接口 |
| 403 | `session_forbidden` | 访问他人会话 |
| 404 | `doc_not_found` / `session_not_found` / `message_not_found` / `user_not_found` / `trace_not_found` | 资源不存在（反馈场景对「存在但越权」也统一返回 404） |
| 409 | `identifier_taken` | 注册：标识已占用 |
| 413 | `file_too_large` | 上传：超过大小上限 |
| 429 | `quota_exceeded` | 当日提问配额用尽 |
| 429 | `too_many_attempts` | 登录防暴破延迟（含 `retry_after`） |
| 502 | `llm_error` | LLM 层失败（流式接口内由 SSE `error` 事件承载，非流式场景为 HTTP） |

---

## 10. 附录：完整调用链路 curl 示例

```bash
# 1. 登录（普通用户），取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"account_identifier":"13800138000","account_type":"phone","password":"secret123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. 创建会话
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/session \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

# 3. 流式问答（SSE）：实时输出事件流
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":$SESSION_ID,\"question\":\"本产品的退货政策是什么？\"}"

# 4. 查询会话历史
curl -s "http://localhost:8000/api/session/$SESSION_ID/messages?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# 5. 对最新一条 AI 消息提交点赞反馈（message_id 取自上一步响应）
curl -s -X POST http://localhost:8000/api/message/123/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"feedback_type":"like","feedback_text":"回答很清晰"}'
```
