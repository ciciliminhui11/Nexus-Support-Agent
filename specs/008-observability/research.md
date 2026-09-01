# 研究记录：链路埋点可观测性

**日期**：2026-09-01 | **特性**：[spec.md](spec.md)

本文件记录设计阶段对技术选型与集成方案的研究结论，统一为「决策 / 理由 / 备选方案」。

## 1. 存储形态：MySQL `trace_event` 平铺多行 + trace_id 关联

- **决策**：新增 `trace_event` 表，一次链路的每个 span 平铺为一行，用 `trace_id` 关联；`status` 用 `String` 而非 `Enum`（追加式观测表未来加状态值不引发 MySQL ENUM 迁移）。
- **理由**：平铺多行利于 SQL 过滤/分页/聚合（按 trace_id GROUP BY 出概览、按 seq 还原单条链路）；复用现有 MySQL + SQLAlchemy 基础设施，重启保留、可查历史；与项目「会话/消息分表」的数据风格一致。观测表是追加式、只增不改，用 String 状态值比 Enum 更抗演进。
- **备选方案**：单行 JSON 树（detail 聚合一个 trace，不利于 SQL 过滤与聚合）；纯日志文件（不可结构化查询）；时序库 / OTel（引入重依赖与部署复杂度，对调试性埋点过度设计）。

## 2. flush 机制：asyncio task + `asyncio.to_thread`（不用 threading 守护线程）

- **决策**：后台落库用 `asyncio.create_task(trace_flush_task(stop))`（生命周期与 `_runtime_zombie_sweeper_task` 同构），DB 写经 `asyncio.to_thread` 丢到 anyio 线程池；缓冲达到 `trace_buffer_size` 或间隔到 `trace_flush_interval_seconds` 触发；关停时在 task 内兜底 flush 剩余。
- **理由**：生命周期显式可控（随 lifespan 启停、可 cancel）；关停兜底 flush 可被 await、干净收尾；`to_thread` 复用既有线程池不新增常驻线程；循环内 `await` 保证同一时刻至多一个 flush 在跑，天然串行。SQLite 内存测试库（StaticPool 单连接）的并发问题只在测试环境存在，用 `trace_flush_enabled=false` 彻底关掉后台写规避，生产 MySQL 连接池本身安全。
- **备选方案**：threading 守护线程（解释器退出失控、无法干净收尾、与 StaticPool 单连接并发风险）；每次埋点直接同步写 DB（阻塞业务链路，违背 FR-003）；Celery/Redis 队列（重依赖，项目已明确免 Celery/Redis）。

## 3. 测试隔离：env 开关 + autouse reset + 显式 flush

- **决策**：conftest 顶层 `TRACE_FLUSH_ENABLED=false`、`TRACE_CONSOLE_LOG=false`、`TRACE_RETENTION_DAYS=0`；autouse fixture `_reset_trace_collector` 每用例清空缓冲；提供 `trace_flush(db)` fixture 把缓冲显式落库到当前测试库。
- **理由**：后台 flusher 永不触碰测试库（规避 StaticPool 并发与被 drop 表写入）；autouse reset 防止用例间缓冲泄漏；显式 flush 让集成测试可控地断言落库结果，且 `flush(db)` 传入测试会话保证同一线程串行、结果立即可见。
- **备选方案**：测试不关后台写（StaticPool 单连接跨会话事务交叠、易 flaky）；断言直接读缓冲不落库（测不到落库环节）。

## 4. 意图溯源：暴露公共 `recognize_with_trace`（复用既有 IntentTrace）

- **决策**：`intent/service.py` 新增公共函数 `recognize_with_trace(db, query) -> (IntentResult, IntentTrace)`，内部复用既有的 `_recognize_with_trace` 与外层永不抛异常兜底；`recognize()` 原签名不动。
- **理由**：意图模块已有完整的 `IntentTrace` 分层溯源（normalized/rule/small_model/fallback/error），只是内部实现；chat 链路需要「意图走哪层」+ 分层详情，复用零新增推理成本、一次调用拿到全部信息。`recognize()` 是既有单测依赖的公共入口，保留不变避免破坏。
- **备选方案**：仅用 `recognize()` 的 `IntentResult.source_layer`（拿不到分层原始结果与降级原因）；在 chat 里改调 `debug_recognize` 的 dict（返回结构非类型化、与链路埋点耦合）。

## 5. 召回统计：retriever 加可选 `stats: dict | None = None` 参数

- **决策**：`retriever.retrieve(...)` 新增可选 `stats` 参数字典，调用方传入空 dict 则函数原地填充各阶段计数（就绪文档数 / 向量阈值过滤前后命中数 / BM25 可用与命中数 / 候选池规模 / Reranker 状态）；不传则行为完全不变。
- **理由**：编排层只能从返回值推断最终 top_k 的来源归属（有 `distance`=向量命中、仅 `bm25_score`=BM25 独有），**推不出**「向量 8 条全被阈值滤掉只剩 BM25 5 条」这类诊断关键信息；可选 dict 成本约 10 行、无签名破坏、与 tracing 模块解耦（retriever 只填 dict，不 import 埋点代码）。
- **备选方案**：仅在编排层用返回结果推断（拿不到过滤前计数与候选池/Reranker 状态，诊断盲区）；把 stats 并入返回值（破坏既有返回结构契约）。

## 6. detail 体积护栏与脱敏

- **决策**：统一护栏——detail 内列表/字符串截断到上限（question ≤200 字符、matched_patterns ≤10、sources ≤top_k），单行 detail 目标 <4KB；不存明文密钥与完整用户敏感内容；查询 API 仅管理员。
- **理由**：观测表只增不删（有保留期清理），detail 失控会拖垮表膨胀与查询；埋点数据含用户问题与召回内容，属敏感信息，须最小化与权限收敛（FR-009）。
- **备选方案**：全量存 question/文档全文（表膨胀 + 敏感信息风险）；仅存计数不存明细（丢掉"召回了哪个文档"这一核心诉求）。

## 7. 配置分级：trace 开关只走 Settings/env，不走 system_config 热调

- **决策**：`trace_enabled / trace_flush_* / trace_console_log / trace_retention_days` 全部定义在 `Settings`（env 驱动），写入 `.env.example`；不注册进 `system_config` 表热调。
- **理由**：埋点采集发生在高频热路径，若每 span 查一次 DB 当开关，观测本身拖慢业务（违背 FR-003）；观测开关应是重启级生效的运维决策，与业务参数（rag_top_k 等）性质不同。
- **备选方案**：注册进 system_config 热调（热路径查库代价高、语义不当）。

## 8. 单进程假设与未来多 worker

- **决策**：本期按 uvicorn 单进程假设实现（进程级内存缓冲 + 进程内 asyncio task），与 002 后台任务一致。
- **理由**：项目当前部署为单进程 dev 场景，不存在跨进程缓冲共享问题；内存缓冲+to_thread 在单进程内串行安全。
- **备选方案**：多 worker 时进程内缓冲被切碎、trace_id 无法跨进程关联，需换共享存储（MySQL 队列/Redis 队列）——记入 future work，不在本期范围。
