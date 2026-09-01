# 快速验证指南：知识库管理

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 002 特性可用。实现细节见 `tasks.md` 与实施阶段。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- MySQL 8.0 已就绪；Chroma 向量库已就绪；bge-m3 Embedding 可用（SiliconFlow 云端，`.env` 填 `EMBEDDING_API_KEY`）
- 具备管理员角色的 JWT（登录/注册由 003 特性提供）
- 准备测试文件：`docs/faq.md`（合法）、`docs/bad.exe`（非法格式）、`docs/empty.txt`（空文件）、`docs/huge.txt`（超 20MB）

## 验证场景

### 场景 1：上传文档 → 后台异步入库 → 就绪（验收场景 1）

```bash
curl -X POST http://localhost:8000/api/knowledge/upload \
  -H "Authorization: Bearer <admin-jwt>" \
  -F "file=@docs/faq.md"
```

**预期**：
- 2 秒内返回 `202`，响应含 `doc_id`、`status: "处理中"`
- 轮询 `GET /api/knowledge/{doc_id}`：数秒至 2 分钟内状态变为「就绪」
- 与 001 联动：对就绪文档内容提问，检索可命中（SC-005）

### 场景 2：知识库列表与状态展示（验收场景 2）

```bash
curl -X POST ... -F "file=@docs/faq.md"     # 正常
curl -X POST ... -F "file=@docs/bad.exe"    # 预期 400
curl -X POST ... -F "file=@docs/empty.txt"  # 预期 400
curl -X GET  http://localhost:8000/api/knowledge/list
```

**预期**：列表展示每份已上传文档的名称、上传时间、状态；非法/空文件不进入列表；若构造一份解析失败文档，其详情展示可读 `fail_msg`。

### 场景 3：删除文档 → 级联清理 → 不再命中（验收场景 3）

```bash
curl -X DELETE http://localhost:8000/api/knowledge/{doc_id} -H "Authorization: Bearer <admin-jwt>"
```

**预期**：
- 返回 204；列表不再出现该文档
- 与 001 联动：删除后对原文档内容提问，检索 100% 不再命中（SC-006）
- 检查 Chroma：无该 `doc_id` 的孤儿切片

## 边界用例

| 用例 | 操作 | 预期 |
|---|---|---|
| 非法格式 | 上传 `.exe`/`.zip` | HTTP 400，`unsupported_format` |
| 空文件 | 上传 0 字节或全空白 | HTTP 400，`empty_file` |
| 超限文件 | 上传 >20MB | HTTP 413，`file_too_large` |
| 部分切片失败 | mock 向量化注入异常 | 文档「失败」+ 可读原因 + 无残留切片 |
| 处理中删除 | 上传后立即 DELETE | 级联清理完成，无孤儿切片 |
| 未授权 | 用普通用户 JWT 上传 | HTTP 403 |

## 测试命令

```bash
cd backend
pytest tests/ -v
```

**预期**：全部通过。集成测试覆盖上传→就绪链路、失败回滚、删除级联（含检索不再命中断言）、并发删除与解析。

## 关键契约引用

- 上传/列表/删除接口与错误码：[contracts/knowledge-api.md](contracts/knowledge-api.md)
- 文档/切片/任务实体与状态机：[data-model.md](data-model.md)
- 参数取值依据：[research.md](research.md)
