# 接口契约：用户反馈

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

## 通用约定

- 所有端点要求 `Authorization: Bearer <jwt>`（003 鉴权依赖）。
- 未鉴权 / 令牌无效 / 过期 → `401 { "code": "unauthorized", "message": "请重新登录" }`。

## 端点

### POST /api/message/{message_id}/feedback

提交 / 覆盖更新对某条 AI 消息的反馈。

```json
{ "feedback_type": "dislike", "feedback_text": "回答没有解释退货的运费承担方。" }
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| feedback_type | enum(`like`,`dislike`) | 是 | 点赞 / 踩，二选一 |
| feedback_text | string | 否 | ≤200 字（`feedback_max_length`，可配置），空白视同未填写 |

- 成功 `200`（新建 `201`；覆盖更新 `200`，行为一致）：

```json
{ "message_id": 2, "feedback_type": "dislike", "feedback_text": "回答没有解释退货的运费承担方。", "updated_at": "2026-08-29T10:01:00" }
```

- 失败：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 消息不存在 | 404 | `{ "code": "message_not_found", "message": "消息不存在" }` |
| 消息非 AI 回答（用户消息） | 400 | `{ "code": "not_ai_message", "message": "只能对 AI 回答提交反馈" }` |
| 越权（他人会话消息） | 404 | `{ "code": "message_not_found", "message": "消息不存在" }` |
| 未选类型 / 类型非法 | 400 | `{ "code": "invalid_feedback_type", "message": "必须选择点赞或踩" }` |
| 文字超限 | 400 | `{ "code": "feedback_too_long", "message": "文字反馈不能超过 200 字" }` |

**覆盖语义**：同一 `(message_id, user_id)` 重复提交 → 更新类型/文字，以最后一次为准（FR-006）。

### GET /api/message/{message_id}/feedback

查询某条消息的反馈状态（当前用户视角 + 全量列表供前端展示/统计数据基础）。

```json
{
  "message_id": 2,
  "mine": { "feedback_type": "dislike", "feedback_text": "回答没有解释退货的运费承担方。", "updated_at": "2026-08-29T10:01:00" },
  "all": [
    { "user_id": 42, "feedback_type": "dislike", "feedback_text": "回答没有解释退货的运费承担方。", "updated_at": "2026-08-29T10:01:00" }
  ]
}
```

- `mine` 为当前用户对该消息的反馈（无则 `null`）；`all` 为该消息全部反馈。
- 消息不存在 / 越权 → `404 message_not_found`。

## 状态码与错误码汇总

| HTTP | code | 说明 |
|---|---|---|
| 200 / 201 | - | 提交成功（新建/覆盖） |
| 400 | `not_ai_message` / `invalid_feedback_type` / `feedback_too_long` | 校验失败 |
| 401 | `unauthorized` | 未鉴权 / 令牌无效 / 过期 |
| 404 | `message_not_found` | 消息不存在或非本人会话消息 |

## 配置契约（system_config / .env）

| 配置项 | key | 默认值 | 说明 |
|---|---|---|---|
| 文字反馈长度上限 | `feedback_max_length` | 200 | FR-007，字符数 |
