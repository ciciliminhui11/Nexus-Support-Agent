# 快速验证指南：会话与消息

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 004 特性可用。实现细节见 `tasks.md` 与实施阶段。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- MySQL 8.0 已就绪；已存在两个账号（用户 A、用户 B）的 JWT（003 特性提供）

## 验证场景

### 场景 1：创建会话 → 问答 → 详情可见（验收场景 1、3）

```bash
# 1. 创建会话
curl -X POST http://localhost:8000/api/session -H "Authorization: Bearer <userA-jwt>"
# 预期 201，返回 session_id、title: "新会话"

# 2. 在该会话内发起问答（001 链路）
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <userA-jwt>" -H "Content-Type: application/json" \
  -d '{"session_id": <session_id>, "question": "本产品的退货政策是什么？"}'

# 3. 查看会话历史消息
curl http://localhost:8000/api/session/<session_id>/messages -H "Authorization: Bearer <userA-jwt>"
```

**预期**：
- 创建后立即能问答（SC-001）
- 问答结束后，消息详情立即可见提问 + AI 回答（SC-004），AI 回答含 `reference_source`（非兜底时）
- 首问后会话列表标题更新为首问摘要（如「本产品的退货政策是…」）

### 场景 2：会话列表（验收场景 2）

- 再创建两个会话并提问，然后：

```bash
curl http://localhost:8000/api/session/list -H "Authorization: Bearer <userA-jwt>"
```

**预期**：仅展示用户 A 的会话，按创建时间倒序（SC-002）；无会话时返回空列表。

### 场景 3：数据隔离（验收场景 3 / FR-004）

- 用**用户 B** 的 JWT 访问用户 A 的会话：

```bash
curl http://localhost:8000/api/session/<userA-session_id>/messages -H "Authorization: Bearer <userB-jwt>"
curl http://localhost:8000/api/session/<userA-session_id> -H "Authorization: Bearer <userB-jwt>"
```

**预期**：均返回 `404 session_not_found`（SC-005，跨用户访问 100% 拒绝）。

### 场景 4：边界情况

| 用例 | 操作 | 预期 |
|---|---|---|
| 未登录 | 不带 JWT 访问列表 | 401 `unauthorized` |
| 空会话 | 查看无消息会话 | 200，`items: []` |
| 大量消息 | 生成 50 条消息后 `page_size=20` 分页 | 每页 ≤20 条、有序、无重复无遗漏 |
| 引用来源为空 | 查看兜底回答消息 | `reference_source` 为 `[]` 正常展示 |

## 测试命令

```bash
cd backend
pytest tests/ -v
```

**预期**：全部通过。集成测试覆盖创建→问答→详情可见联动、跨用户隔离、分页有序、同秒并发消息顺序、空会话/空列表。

## 关键契约引用

- 创建/列表/详情/消息接口与错误码：[contracts/session-api.md](contracts/session-api.md)
- Session / Message 实体与查询契约：[data-model.md](data-model.md)
- 标题/分页/隔离策略依据：[research.md](research.md)
