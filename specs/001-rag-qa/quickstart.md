# 快速验证指南：RAG 智能问答链路

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 001 特性可用。实现细节见 `tasks.md` 与实施阶段，不在本文档内。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- MySQL 8.0 已就绪，`system_config` 表载入默认配置（见[配置契约](contracts/chat-stream.md)）
- Chroma 向量库已就绪；Embedding 模型（bge-m3，Ollama 提供）可用，LLM 已配置 DeepSeek V4 Flash（`.env` 填 `DEEPSEEK_API_KEY`，`LLM_BACKEND=deepseek`）
- 知识库存在至少一条**就绪**文档（上传/解析由 002 特性提供，可用预置测试数据 `docs/faq.md`）
- 存在有效会话（创建会话由 004 特性提供；可用 SQL 预置一条会话记录）
- **（可选）Reranker 精排模型**（sentence-transformers + `bge-reranker-v2-m3`，按 重难点总结 第五部分镜像安装教程 安装）。未安装时自动回退 RRF 融合排序，不影响主链路，仅 `meta` 引用顺序为融合序。

## 验证场景

### 场景 1：正常提问 → 流式回答 + 引用来源（验收场景 1、2）

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1001, "question": "本产品的退货政策是什么？"}'
```

**预期**：
- 首事件为 `meta`，携带 `sources`（文档名 + 片段摘要）
- 多个 `data` 事件逐块输出回答文本
- 末尾 `finish` 事件，`message_id` 非空
- 回答内容严格落在检索片段范围内
- 数据库 message 表新增 user 与 ai 两条记录，ai 记录 reference_source 非空

### 场景 2：多轮上下文保持（验收场景 1、2）

```bash
# 先问第一轮，再问第二轮
curl -N -X POST ... -d '{"session_id": 1001, "question": "你们支持在线客服吗？"}'
curl -N -X POST ... -d '{"session_id": 1001, "question": "那它收费吗？"}'
```

**预期**：第二轮回答能理解「它」指代在线客服；请求日志/测试断言确认携带最近 N 轮历史。

### 场景 3：边界与异常（验收场景 3）

| 用例 | 操作 | 预期 |
|---|---|---|
| 长度超限 | `question` 填 501 字 | HTTP 400，`question_too_long`，不建立流 |
| 配额耗尽 | 连续提问至当日上限+1 | HTTP 429，`quota_exceeded`，不建立流 |
| 检索为空 | 提问无关主题（或清空知识库） | 流内仅一个 `data` 事件含固定兜底话术，随后 `finish`，**不调用 LLM** |
| LLM 超时 | mock Ollama 延迟超过 `llm_timeout_seconds` | 流内 `error` 事件 `llm_timeout`，随后连接关闭 |
| LLM 限流 | mock Ollama 返回 429 | 流内 `error` 事件 `llm_rate_limited`，友好文案 |

### 场景 4：上下文超长截断（验收场景 2）

- 将 `context_turns` 调大并填充长历史，或放大知识片段，使历史+知识总长超过 `context_max_tokens`
- 提问后验证：回答仍基于知识片段给出（未丢失关键知识），最早历史被丢弃，无报错

### 场景 5：混合检索 + 精排（验收场景 4、5）

```bash
# 关键词精确匹配：问句与知识片段无语义重叠但共享关键词（口语化/型号/货号）
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <jwt>" -H "Content-Type: application/json" \
  -d '{"session_id": 1001, "question": "退货政策如何办理"}'
```

**预期（BM25 关键词召回）**：即使向量路被阈值滤掉，`meta` 仍有来源（jieba 显著词闸门命中），回答基于知识片段。

```bash
# 重排验证：知识库同时存在「退货政策」与「配送时效」文档，问「退货政策与配送时效」
```

**预期（Reranker 精排，已装模型时）**：`meta` 来源按精排相关性排序，业务无关片段被压后；未装模型时回落融合序，链路正常（可在日志看到一次降级 warning）。

## 测试命令

```bash
cd backend
pytest tests/ -v
```

**预期**：全部通过。其中集成测试覆盖正常流式、空检索兜底、超时/429、上下文超长、并发配额一致性与持久化；混合检索相关单元测试覆盖 jieba 分词/显著词闸门、RRF 融合、Reranker 降级；集成测试新增 BM25 关键词命中（`test_hybrid_bm25_only_keyword_hit`）与 FakeReranker 重排 meta 顺序（`test_fake_reranker_reorders_meta_sources`）。注意：测试环境未装 sentence-transformers，Reranker 走 Noop 降级路径（由注入假精排器的用例单独验证精排行为）。

## 关键契约引用

- SSE 事件协议与错误码：[contracts/chat-stream.md](contracts/chat-stream.md)
- 消息持久化结构：[data-model.md](data-model.md)
- 参数取值依据：[research.md](research.md)
