# 任务清单：链路埋点可观测性

**功能分支**：`008-observability` | **规格**：[spec.md](spec.md) | **研究**：[research.md](research.md)

本清单把「链路埋点可观测性」拆解为可独立实施、可独立验证的增量任务，采用 TDD（先写测试、红 → 实现 → 绿）。任务按 Phase 依赖排序，覆盖：spec → 数据层与采集核心 → 查询 API → 文档入库埋点 → 问答链路埋点 → 生命周期与回归验证。

---

## Phase 1 准备阶段（Setup）

> 特性文档与基础数据/配置层，为后续所有阶段提供骨架。

- [x] T001 [P] 创建 `specs/008-observability/` 三件套：`spec.md`（FR/SC/用户故事）、`research.md`（决策记录）、`tasks.md`（本清单）。
- [x] T002 [P] 新增 `TraceEvent` 模型：`backend/app/db/models.py` 追加 `TraceEvent` 类（`_PK` 主键、trace_id/trace_type/stage/seq/status/start_at/duration_ms/detail(JSON)/doc_id/session_id/user_id/message_id/error/create_time，索引 ix_trace_trace_id / ix_trace_type_time / ix_trace_session）；`backend/数据库初始化脚本/init.sql` 追加 MySQL DDL（注释风格与现有表一致）。
- [x] T003 [P] 新增 trace 配置：`backend/app/config.py` Settings 追加 `trace_enabled`(True) / `trace_flush_enabled`(True) / `trace_flush_interval_seconds`(10) / `trace_buffer_size`(200) / `trace_console_log`(True) / `trace_retention_days`(7)；`backend/.env.example` 追加同名注释项。

**检查点**：表可建（测试 `create_all()` 含 trace_event）、配置可读（settings 含 trace_*）。

---

## Phase 2 采集核心（tracing 模块，TDD）

> 纯基础设施，不接业务。每个模块先写单测再实现。

- [x] T004 [P] 创建 `backend/app/services/tracing/__init__.py`（re-export）与 `events.py`：`TraceEvent` 数据字段常量、`STAGE_*`/`STATUS_*`/`TRACE_TYPE_*` 常量、`_bounded(val, cap)` 体积护栏。
- [x] T005 [P] 创建 `collector.py`：线程安全 `Collector`（`add/pending/drain/reset/flush(db=None)`）+ 全局单例 `collector`；`flush` 批量 insert（db 为空自开 `SessionLocal()`），失败只 log 不重试。单测 `tests/unit/test_trace_collector.py`。
- [x] T006 [P] 创建 `tracer.py`：`Tracer`（`span(stage)` 同步 contextmanager 计时、异常标 error 上抛；`finish(status, error, **meta)` 幂等，拼 meta 行(seq=0) + 推入 collector + 按 `trace_console_log` 打印；`trace_enabled=false` 全程短路）。单测 `tests/unit/test_trace_tracer.py`。
- [x] T007 [P] 创建 `console.py`：`render_trace_block()` 生成可读链路块（含 trace_id/类型/各 stage 顺序/耗时/状态/关键 detail）。单测 `tests/unit/test_trace_console.py`。
- [x] T008 [P] 创建 `flusher.py`：`async trace_flush_task(stop)` 周期/达缓冲阈值 flush、关停兜底 flush、`purge_old()` 按 `trace_retention_days` 清理（≤0 跳过）。单测 `tests/unit/test_trace_flusher.py`（monkeypatch interval 极小跑一轮 + 关停 flush）。

**检查点**：采集/落库/打印可单测通过；未接入任何业务代码。

---

## Phase 3 查询 API 与测试隔离

- [x] T009 [P] 创建 `backend/app/schemas/trace.py`（list/detail 响应模型）与 `backend/app/api/trace.py`（管理员 `require_admin`：`GET /api/trace/list` 按 trace_id 聚合+过滤分页；`GET /api/trace/detail?trace_id=` 按 seq 返回，不存在 404）；`backend/app/main.py` 注册 `app.include_router(trace.router)`。集成测试 `tests/integration/test_trace_api.py`（403 / list 过滤 / detail 还原 / 404）。
- [x] T010 [P] `backend/tests/conftest.py` 隔离改造：顶层 env setdefault `TRACE_FLUSH_ENABLED=false`、`TRACE_CONSOLE_LOG=false`、`TRACE_RETENTION_DAYS=0`；autouse fixture `_reset_trace_collector`（`collector.reset()`）；fixture `trace_flush(db)`（`collector.flush(db)`）。

**检查点**：查询 API 权限与功能通过；测试环境后台写被隔离。

---

## Phase 4 业务接线（文档入库 + 意图 + 问答）

> 复用既有数据结构，不改变既有公共签名。

- [x] T011 [P] `backend/app/services/rag/retriever.py` 加可选 `stats: dict | None = None`：填充 ready_docs / vector_before_threshold / vector_after_threshold / bm25_available / bm25_hits / candidate_pool / reranker(状态) / empty。单测 `tests/unit/test_trace_retriever_stats.py`（含不传 stats 行为不变）。
- [x] T012 [P] `backend/app/intent/service.py` 新增公共 `recognize_with_trace(db, query) -> (IntentResult, IntentTrace)`（复用 `_recognize_with_trace` + 永不抛异常兜底），`recognize()` 不动。单测 `tests/unit/test_intent_recognize_with_trace.py`。
- [x] T013 [P] `backend/app/services/knowledge/pipeline.py` `process_document` 埋点：创建 `Tracer("ingest", doc_id=...)`，span 覆盖 doc_load / doc_parse{chars} / doc_split{chunks, semantic_split} / doc_embed_ingest{batches, dim, vectors} / doc_status{status}，失败路径 finish(error) 含回滚与取消。集成测试 `tests/integration/test_trace_ingest.py`。
- [x] T014 [P] `backend/app/api/chat.py` `chat_stream` 埋点：创建 `Tracer("chat", session_id, user_id, question)`；前置段 preflight/intent（用 `recognize_with_trace`）/retrieve（传 stats + sources）；生成器内 persist_user / short_circuit / empty_retrieval / prompt / llm_stream（first_token_ms）/ postcheck / finish；`finally` 兜底未 finish 补 error。集成测试 `tests/integration/test_trace_chat.py`。

**检查点**：上传文档与问答触发后，控制台链路块 + 落库 span 完整可断言。

---

## Phase 5 生命周期与回归验证

- [x] T015 [P] `backend/app/main.py` lifespan 接入：`trace_flush_enabled` 时启动 `asyncio.create_task(trace_flush_task(stop))`，关闭时 set/cancel + await（同僵尸清扫器模式）。
- [x] T016 [P] 全量回归：`cd backend && pytest tests/ -v` 全部通过；补 Spec→Code 映射表；宪法三轮闭环验证（映射 → 全量测试 → 人工安全/性能/可维护性审查）。

**检查点**：全量测试绿；交付文档（映射表）齐备。
