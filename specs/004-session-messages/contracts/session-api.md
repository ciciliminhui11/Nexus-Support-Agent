# 接口契约：会话与消息

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

## 通用约定

- 所有端点要求 `Authorization: Bearer <jwt>`（003 鉴权依赖）。
- 未鉴权 / 令牌无效 / 过期 → `401 { "code": "unauthorized", "message": "请重新登录" }`。

## 端点

### POST /api/session

创建会话。

- 请求体：`{}`（v1 无必填参数，标题系统默认生成）。
- 成功 `201`：

```json
{ "session_id": 1001, "title": "新会话", "create_time": "2026-08-29T10:00:00" }
```

### GET /api/session/list

当前用户的会话列表（按创建时间倒序，分页）。

- 查询参数：`page`（默认 1）、`page_size`（默认 20）。
- 成功 `200`：

```json
{
  "total": 3,
  "items": [
    { "session_id": 1003, "title": "本产品的退货政策是…", "create_time": "2026-08-29T10:05:00" },
    { "session_id": 1002, "title": "新会话", "create_time": "2026-08-29T09:50:00" }
  ]
}
```

- 无会话时 `items: []`、`total: 0`（前端据此引导创建）。

### GET /api/session/{session_id}

会话详情（含归属校验）。

```json
{ "session_id": 1001, "title": "新会话", "create_time": "2026-08-29T10:00:00", "message_count": 4 }
```

- 归属校验失败 → `404 { "code": "session_not_found", "message": "会话不存在" }`（不泄露他人会话存在性）。

### GET /api/session/{session_id}/messages

会话历史消息（按时间正序，分页）。

- 查询参数：`page`（默认 1）、`page_size`（默认 20，上限 100）。
- 成功 `200`：

```json
{
  "total": 4,
  "items": [
    { "message_id": 1, "role": "user", "content": "本产品的退货政策是什么？", "reference_source": null, "intent_label": null, "create_time": "2026-08-29T10:00:01" },
    { "message_id": 2, "role": "ai", "content": "根据知识库，本产品支持 7 天无理由退货。", "reference_source": [ { "doc_name": "FAQ.md", "snippet": "退货时限为 7 天……" } ], "intent_label": null, "create_time": "2026-08-29T10:00:05" }
  ]
}
```

- 空会话 → `items: []`、`total: 0`（HTTP 200，正常展示）。
- 会话归属校验失败 → `404 session_not_found`。

## 状态码与错误码汇总

| HTTP | code | 说明 |
|---|---|---|
| 200 | - | 正常（含空列表/空会话） |
| 201 | - | 会话创建成功 |
| 401 | `unauthorized` | 未鉴权 / 令牌无效 / 过期 |
| 404 | `session_not_found` | 会话不存在或非本人会话 |

## 配置契约（system_config / .env）

| 配置项 | key | 默认值 | 说明 |
|---|---|---|---|
| 列表分页大小 | `session_page_size` | 20 | FR-002 |
| 消息分页大小 | `message_page_size` | 20 | FR-009 |
| 消息分页上限 | `message_page_size_max` | 100 | FR-009 |
| 默认标题 | `default_session_title` | `新会话` | FR-006 |
| 摘要标题长度 | `session_title_summary_len` | 20 | FR-006 首问截断字符数 |
| 多轮上下文轮数 | `context_turns` | 6 | FR-008（与 001 共用） |
