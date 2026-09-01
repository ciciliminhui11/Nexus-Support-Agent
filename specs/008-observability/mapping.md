# Spec→Code 映射表：链路埋点可观测性

**功能分支**：`008-observability` | **规格**：[spec.md](spec.md) | **任务**：[tasks.md](tasks.md)

第一轮闭环验证（宪法 §闭环验证）：逐条核对 Spec 要求 → 代码位置 → 是否实现。
全部 FR 与关键实体均有实现；验收场景由对应集成测试覆盖。

## 功能需求（FR）映射

| Spec 要求 | 代码位置 | 是否实现 |
| --- | --- | --- |
| FR-001 文档处理全阶段埋点（doc_load/parse/split/embed_ingest/doc_status + 失败/回滚/取消） | [pipeline.py](../backend/app/services/knowledge/pipeline.py) `process_document`；阶段常量 [events.py](../backend/app/services/tracing/events.py) | ✅ |
| FR-002 问答链路全阶段埋点（preflight/intent/retrieve/prompt/llm_stream/postcheck/finish + 短路/空检索） | [chat.py](../backend/app/api/chat.py) `chat_stream` | ✅ |
| FR-003 内存缓冲 + 后台批量异步落库 + 关停 flush | [collector.py](../backend/app/services/tracing/collector.py) `Collector.flush`；[flusher.py](../backend/app/services/tracing/flusher.py) `trace_flush_task`；[main.py](../backend/app/main.py) `lifespan` | ✅ |
| FR-004 控制台打印可读完整链路块（`trace_console_log`） | [tracer.py](../backend/app/services/tracing/tracer.py) `Tracer.finish`；[console.py](../backend/app/services/tracing/console.py) `render_trace_block` | ✅ |
| FR-005 管理员查询 `/api/trace/list`、`/api/trace/detail` | [trace.py](../backend/app/api/trace.py)；注册 [main.py](../backend/app/main.py)；模型 [schemas/trace.py](../backend/app/schemas/trace.py) | ✅ |
| FR-006 意图 span 记录分层来源/置信度/命中模式/澄清话术 | [chat.py](../backend/app/api/chat.py) `STAGE_INTENT` span；公共入口 [service.py](../backend/app/intent/service.py) `recognize_with_trace` | ✅ |
| FR-007 召回 span 记录就绪数/向量与BM25命中数/候选池/Reranker状态/命中文档+分数 | [retriever.py](../backend/app/services/rag/retriever.py) 可选 `stats`；[chat.py](../backend/app/api/chat.py) `STAGE_RETRIEVE` span | ✅ |
| FR-008 LLM span 记录 backend/首token时延/字符数/错误码 | [chat.py](../backend/app/api/chat.py) `STAGE_LLM_STREAM` span；[tracer.py](../backend/app/services/tracing/tracer.py) `mark_span_error` | ✅ |
| FR-009 查询接口仅管理员；detail 脱敏（不存密钥、question 截断） | [trace.py](../backend/app/api/trace.py) `require_admin`；[events.py](../backend/app/services/tracing/events.py) 截断护栏；[tracer.py](../backend/app/services/tracing/tracer.py) `truncate_text` | ✅ |
| FR-010 `trace_enabled=false` 零采集/零打印/零落库 | [tracer.py](../backend/app/services/tracing/tracer.py) `_enabled` 短路；[config.py](../backend/app/config.py) `trace_enabled` | ✅ |
| FR-011（P2）`trace_retention_days` 超期清理 | [flusher.py](../backend/app/services/tracing/flusher.py) `purge_old`；[main.py](../backend/app/main.py) `lifespan`（随启动调用） | ✅ |

## 关键实体映射

| 实体 | 代码位置 | 说明 |
| --- | --- | --- |
| `TraceEvent` 模型 | [models.py](../backend/app/db/models.py) `TraceEvent` | `_PK`/索引 ix_trace_trace_id/ix_trace_type_time/ix_trace_session |
| `trace_event` MySQL DDL | [init.sql](../backend/数据库初始化脚本/init.sql) | 注释风格与既有表一致 |
| `Tracer` | [tracer.py](../backend/app/services/tracing/tracer.py) | 每操作实例，span 收集 + 控制台输出 + 短路 |
| `Collector` | [collector.py](../backend/app/services/tracing/collector.py) | 线程安全缓冲，flush(db) 批量落库 |

## 配置映射

| 配置项 | 位置 | 默认 |
| --- | --- | --- |
| `trace_enabled` / `trace_flush_*` / `trace_console_log` / `trace_retention_days` | [config.py](../backend/app/config.py) `Settings`；[.env.example](../backend/.env.example) | true / 10s / 200 / true / 7 |

## 验收场景 ↔ 测试

| 验收场景（spec.md 用户故事） | 覆盖测试 |
| --- | --- |
| 正常上传 → ≥4 条 ok span，detail 含 chars/chunks/batches/dim | [test_trace_ingest.py](../backend/tests/integration/test_trace_ingest.py) `test_normal_upload_produces_ok_ingest_trace` |
| 解析失败 → error span + doc_status 失败 + trace error | 同文件 `test_parse_failure_records_error_trace` |
| 并发删除取消 → 已取消终态 + 回滚路径 | 同文件 `test_concurrent_delete_records_cancelled` |
| 正常问答 → ≥6 条 span，intent 记录来源层/置信度，retrieve 命中文档，llm_stream 首 token | [test_trace_chat.py](../backend/tests/integration/test_trace_chat.py) `test_normal_chat_trace` |
| 意图短路 → short_circuit span，无 retrieve/llm_stream | 同文件 `test_short_circuit_trace` |
| 空检索兜底 → empty_retrieval 分支，不调 LLM | 同文件 `test_empty_retrieval_trace` |
| LLM 超时 → llm_stream 记 error_code，trace error | 同文件 `test_llm_error_trace` |
| 管理员 list 聚合/过滤、detail 还原、普通用户 403、404 | [test_trace_api.py](../backend/tests/integration/test_trace_api.py) |
| `trace_enabled=false` 零采集 | [test_trace_tracer.py](../backend/tests/unit/test_trace_tracer.py) `test_disabled_trace_zero_collection` |

## 结果

- 第二轮闭环验证：`cd backend && pytest tests/` → **293 passed**（全量，含 trace 采集/API/埋点/回归）。
- 第三轮人工审查（安全/性能/UX/可维护性）已完成，结论见下。

## 第三轮人工审查记录

| 维度 | 审查结论 |
| --- | --- |
| 安全 | 查询接口 `require_admin` 管理员专属（普通用户 403 有测试覆盖）；question/error/matched_patterns/sources 均有截断护栏，不存密钥；detail 仅含文档名/片段/计数/意图层，无敏感信息；SQL 全走 ORM 绑定参数，无注入面 |
| 性能 | `trace_enabled=false` 全程短路零开销（span 空操作、finish 直接返回，有单测）；后台 flush 周期/阈值双触发，purge 按 600s 节流；list 聚合走 `ix_trace_type_time`/`ix_trace_session`。**已知可接受项**：`doc_id` 过滤无独立索引（P2 管理工具规模下可容忍，如数据量大可后续补 `ix_trace_doc`） |
| UX | 控制台链路块按阶段/耗时/状态/关键指标渲染，sources 预览前 6 条 `doc_name(score)`；API 返回分页聚合概览 + 按 seq 还原的完整 span 详情 |
| 可维护性 | 阶段/状态常量集中在 `events.py`，Tracer/Collector/flusher 职责单一；`mark_span_error` 用于业务内捕获异常的 span 标错（如 LLM 流式错误、空响应）。**提示**：包级 `collector` 实例重导出会遮蔽同名子模块，测试侧已用 `importlib.import_module` 规避，改代码时注意 |
| 本次修正 | ① 控制台 `_format_sources` 兼容 `doc_name`/`doc` 两种来源键（原只认 `doc`，chat 来源预览会显示 `?()`）；② 空响应路径将 `llm_stream` span 标 error 并记 `error_code=llm_error`（原漏标，违反 FR-008 的 LLM span 错误码要求）。两处修正后全量仍 **293 passed** |

第三轮人工审查通过，008 特性闭环完成。
