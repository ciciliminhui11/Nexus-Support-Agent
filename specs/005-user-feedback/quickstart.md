# 快速验证指南：用户反馈

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

本文档是可运行的端到端验证指南，证明 005 特性可用。实现细节见 `tasks.md` 与实施阶段。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- MySQL 8.0 已就绪；已存在用户 A、用户 B 的 JWT（003 特性提供）
- 已存在一条 AI 消息（经 001 问答产生，记录其 `message_id`），以及一条用户消息作对照

## 验证场景

### 场景 1：点赞 / 踩 + 文字反馈（验收场景 1、2）

```bash
# 对 AI 消息点「踩」并附文字
curl -X POST http://localhost:8000/api/message/<ai_message_id>/feedback \
  -H "Authorization: Bearer <userA-jwt>" -H "Content-Type: application/json" \
  -d '{"feedback_type":"dislike","feedback_text":"没有解释运费承担方。"}'
# 预期 201/200，反馈成功记录

# 查询该消息反馈
curl http://localhost:8000/api/message/<ai_message_id>/feedback -H "Authorization: Bearer <userA-jwt>"
# 预期 mine 与 all 均含该反馈
```

**预期**：反馈 2 秒内提交成功（SC-001）；持久化且可按消息与提交者追溯（SC-002）。

### 场景 2：覆盖更新（验收场景 3 / FR-006）

```bash
# 同一用户再提交「赞」覆盖
curl -X POST http://localhost:8000/api/message/<ai_message_id>/feedback \
  -H "Authorization: Bearer <userA-jwt>" -H "Content-Type: application/json" \
  -d '{"feedback_type":"like"}'
curl http://localhost:8000/api/message/<ai_message_id>/feedback -H "Authorization: Bearer <userA-jwt>"
```

**预期**：反馈变为 `like`，以最后一次为准（SC-004）；`all` 列表仅一条该用户记录。

### 场景 3：校验与隔离（验收场景 1 场景 3 / FR-003、FR-008、FR-009）

| 用例 | 操作 | 预期 |
|---|---|---|
| 对用户消息反馈 | 对 role=user 的消息 POST | 400 `not_ai_message` |
| 消息不存在 | 对不存在 id POST | 404 `message_not_found` |
| 未选类型 | `{}` 或 `{"feedback_text":"..."}` | 400 `invalid_feedback_type` |
| 文字超限 | `feedback_text` 填 201 字 | 400 `feedback_too_long`（恰好 200 字应通过） |
| 越权反馈 | 用户 B 对用户 A 会话中的消息 POST | 404 `message_not_found` |
| 未登录 | 不带 JWT POST | 401 `unauthorized` |

## 测试命令

```bash
cd backend
pytest tests/ -v
```

**预期**：全部通过。集成测试覆盖提交→覆盖更新→隔离拒绝→按消息查询，及角色/类型/长度校验边界。

## 关键契约引用

- 提交/查询接口与错误码：[contracts/feedback-api.md](contracts/feedback-api.md)
- Feedback 实体与 upsert 语义：[data-model.md](data-model.md)
- 校验与存储策略依据：[research.md](research.md)
