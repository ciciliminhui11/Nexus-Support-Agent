# 任务清单：RAG 智能问答链路

**分支**：`001-rag-qa` | **输入**：来自 `/specs/001-rag-qa/` 的 plan.md、spec.md、data-model.md、research.md、contracts/、quickstart.md

本清单将「RAG 智能问答链路」拆解为依赖有序的实施任务，按用户故事优先级（P1 → P2 → P3）组织，每个用户故事可独立实现与独立验证。任务路径来自 plan.md 的 `backend/app` 项目结构。

---

## Phase 1：准备阶段（Setup）

> 项目初始化与基础结构，不依赖任何用户故事。

- [ ] T001 创建后端目录骨架及所有包初始化文件：`backend/app/__init__.py`、`backend/app/api/__init__.py`、`backend/app/core/__init__.py`、`backend/app/db/__init__.py`、`backend/app/schemas/__init__.py`、`backend/app/services/__init__.py`、`backend/app/services/rag/__init__.py`、`backend/app/vector_store/__init__.py`、`backend/tests/__init__.py`、`backend/tests/unit/__init__.py`、`backend/tests/integration/__init__.py`（空文件即可）
- [ ] T002 [P] 创建 `backend/requirements.txt`，列出依赖：fastapi、uvicorn、sqlalchemy、pymysql、chromadb、sentence-transformers、httpx、pydantic-settings、python-dotenv、pytest（版本留空或标注最新稳定）
- [ ] T003 [P] 创建 `backend/.env.example` 环境变量模板，列出所有密钥与配置项占位符（数据库连接串、Chroma 持久化目录、bge-m3 模型路径、Ollama base_url、Qwen2 模型名，及 config.py 中的全部可配置项）
- [ ] T004 [P] 创建 `backend/app/config.py`，用 pydantic-settings 定义 `Settings` 类加载 `.env`，包含配置项及默认值：数据库 URL、Chroma 持久化目录、embedding 模型（bge-m3）、Ollama base_url 与模型名（Qwen2）、`daily_quota_limit=100`、`context_turns=6`、`rag_top_k=6`、`rag_similarity_threshold=0.55`、`context_max_tokens=6000`、`llm_timeout_seconds=60`、`llm_first_token_timeout=30`（取值见 contracts/chat-stream.md 配置契约）
- [ ] T005 [P] 创建 `backend/app/core/exceptions.py`，定义统一业务异常（均带 `code`/`message` 字段）：`QuestionTooLong`、`QuestionEmpty`、`QuotaExceeded`、`SessionForbidden`、`RetrievalEmpty`、`LLMTimeout`、`LLMRateLimited`、`LLMError`，供后续校验、检索、LLM 调用与 API 层复用
- [ ] T006 [P] 创建 `backend/app/core/logging.py`，配置标准 logging（控制台 + 结构化日志，记录请求链路与异常），供全链路各模块调用

---

## Phase 2：基础阶段（Foundational）

> 阻塞所有用户故事的前置任务：数据库模型与会话管理、测试基础设施。完成后方可并行实施各用户故事。

- [ ] T007 创建 `backend/app/db/models.py`，定义 SQLAlchemy ORM 模型（依据 data-model.md）：`Session`（id/user_id/title/create_time，索引 `(user_id, create_time)`）、`Message`（id/session_id/role ENUM('user','ai')/content/reference_source JSON/intent_label/create_time，索引 `(session_id, create_time)`）、`UserQuotaDaily`（id/user_id/stat_date/count，唯一约束 `UNIQUE(user_id, stat_date)`）；`reference_source` 用 JSON 列存储 `[{doc_name, snippet}]` 数组
- [ ] T008 创建 `backend/app/db/session.py`，定义 SQLAlchemy `engine`、`SessionLocal`（sessionmaker）与 FastAPI 依赖注入 `get_db`（yield 会话并保证关闭），数据库连接串从 config.py 读取
- [ ] T009 创建 `backend/tests/conftest.py`，提供测试隔离夹具：内存 SQLite（模拟 MySQL）会话夹具、临时目录 Chroma 夹具、`system_config` 默认配置夹具（pytest 基础设施，供后续测试复用）

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 用户提问并获得带来源的流式回答（优先级：P1）

**目标**：打通 RAG 核心闭环 —— 校验输入 → Query 向量化 → 向量检索 → Prompt 组装 → LLM 流式调用 → SSE 逐块返回 token 与引用来源 → 消息持久化 → 输出后来源校验。

**独立测试**：知识库有一条已就绪文档，用户发起提问，可独立验证：收到流式 token、回答尾部出现 `meta` 引用来源事件、会话已保存问答记录。

- [ ] T010 [P] [US1] 创建 `backend/app/schemas/chat.py`，定义 Pydantic 模型：请求 `ChatRequest`（`session_id: int`、`question: str`，question 必填且非空）；SSE 事件载荷 `ReferenceSource`（doc_name/snippet）、`MetaEvent`（sources 数组）、`DataEvent`（delta）、`FinishEvent`（message_id、postcheck）、`ErrorEvent`（code、message），对齐 contracts/chat-stream.md 事件协议
- [ ] T011 [P] [US1] 创建 `backend/app/vector_store/chroma.py`，封装 Chroma client 与 collection（`cosine` 距离、本地持久化目录），提供 `get_or_create_collection`、`query(embedding, top_k)`（返回带 `metadata.doc_id`、`metadata.snippet`、`page_content` 的结果），隔离 Chroma 细节便于后续切换向量库
- [ ] T012 [P] [US1] 创建 `backend/app/services/rag/embedding.py`，封装 bge-m3 向量化（sentence-transformers，1024 维），提供进程级单例复用（模块加载一次模型）、`embed_query(text)` 与 `embed_documents(texts)`，保证入库与检索向量分布一致
- [ ] T013 [US1] 创建 `backend/app/services/rag/retriever.py`，实现混合检索链路（FR-004/FR-014）：调用 embedding.py 向量化 Query → 向量路 Chroma 检索按 `rag_similarity_threshold` 阈值过滤 → BM25 路（jieba 分词 + 显著词闸门 + Okapi BM25）按 `rag_bm25_top_k` 召回 → RRF 融合（`rag_rrf_k`）成粗筛候选池 `rag_candidate_k` → Reranker 精排取 `rag_top_k`（加载/推理失败回退融合序）→ 无有效片段返回空列表（走兜底）。知识冲突检测与过滤（research §5）为后续增强，不在本次范围
- [ ] T013b [US1] 创建 `backend/app/services/rag/bm25.py`：jieba 分词（缺失降级为 ASCII-only，`JIEBA_AVAILABLE`）、显著词过滤（len≥2）、`passes_gate` 闸门（与问题共享 ≥1 显著词）、自研 Okapi BM25（k1=1.5、b=0.75）`BM25Index.build/rank`
- [ ] T013c [US1] 创建 `backend/app/services/rag/reranker.py`：`Reranker` 协议、`CrossEncoderReranker`（sentence-transformers 懒加载）、`NoopReranker` 降级、`get_reranker()`（进程缓存，`rag_reranker_enabled`/`find_spec` 决议）、`warmup()`/`reset_reranker()`；配置新增 `rag_candidate_k`/`rag_bm25_top_k`/`rag_rrf_k`/`rag_reranker_enabled`/`rag_reranker_model`
- [ ] T014 [P] [US1] 创建 `backend/app/services/rag/prompt.py`，实现 Prompt 组装（FR-006）：拼接 System Prompt（强约束「仅依据编号材料回答、无材料输出兜底话术、禁止编造」）+ 带编号与来源元信息的检索知识片段（`【1】来源：xxx｜章节：yyy` 格式）+ 历史对话（当前接受历史参数，单轮为空）+ 用户问题；返回组装后的 messages 结构
- [ ] T015 [P] [US1] 创建 `backend/app/services/rag/llm.py`，实现 Ollama 流式调用（httpx 异步调用 openai 兼容 `/api/chat`，`timeout` 取 `llm_timeout_seconds`、首 token 等待 `llm_first_token_timeout`），以 async generator 逐块产出 token；捕获 `httpx.TimeoutException` 与 HTTP 429，抛出自定义 `LLMTimeout`/`LLMRateLimited`/`LLMError` 异常（FR-010 的底层捕获，SSE 映射见 US3）
- [ ] T016 [P] [US1] 创建 `backend/app/services/rag/sse.py`，实现 SSE 事件封装（FR-009）：提供 `format_sse(event, data)` 输出 `event: <type>\ndata: <json>` 两行格式，以及 `emit_meta`/`emit_data`/`emit_finish`/`emit_error` 辅助函数；保证 `meta` 至多一次且在首个 `data` 前、`finish`/`error` 互斥且为最后事件（见 contracts/chat-stream.md 事件序列约束）
- [ ] T017 [P] [US1] 创建 `backend/app/services/rag/postcheck.py`，实现输出后来源校验（FR-013）：对 LLM 完整输出做启发式幻觉检出（输出中超出知识片段重叠范围的实体/长断言标记为「待人工核实」），返回 `{status: "ok"|"review"}`，供 `finish` 事件的 `postcheck` 字段使用，不阻断回答
- [ ] T018 [P] [US1] 创建 `backend/app/services/validation.py`，实现输入长度校验（FR-001）：question 为空抛 `QuestionEmpty`、超过 500 字抛 `QuestionTooLong`（边界 500 通过、501 拒绝）；每日配额校验见 US3
- [ ] T019 [US1] 创建 `backend/app/api/chat.py`，实现 `POST /api/chat/stream` 端点，编排完整链路：读取请求 → validation 长度/空校验 → （历史暂为空，US2 接入）→ retriever 检索 → 命中则 prompt 组装 → llm 流式 → sse 逐块推送 `data`、前置推送 `meta` 引用来源、末尾 `finish`（含 message_id + postcheck）→ 持久化 user/ai 两条 Message（FR-012，ai 记录 reference_source）；设置响应头 `Content-Type: text/event-stream`、`Cache-Control: no-cache`、`Connection: keep-alive`
- [ ] T020 [US1] 创建 `backend/app/main.py`，装配 FastAPI 应用：注册 `/api/chat/stream` 路由、挂载 `get_db` 依赖、应用启动事件中预热 embedding/reranker 模型与 Chroma collection（进程级加载，避免请求内冷启动，支撑 SC-001 ≤3 秒首字延迟）

**检查点**：用户故事 1 此刻可独立运行与验证 —— 在已预置就绪文档与有效会话的前提下，提交 500 字内问题，可收到流式 token、`meta` 引用来源事件、`finish` 结束事件，且问答记录已持久化（对应 quickstart 场景 1）。

---

## 阶段 4：用户故事 2 - 多轮对话上下文保持（优先级：P2）

**目标**：同一会话内连续追问时，自动携带最近 N 轮历史，使回答能引用前文；上下文超长时执行可预期的截断策略（丢最早历史、保留并压缩知识片段）。

**独立测试**：在同一会话连续提出两条相关问题，验证第二条回答能理解第一条语境，且请求携带最近 N 轮历史。

- [ ] T021 [US2] 创建 `backend/app/services/history.py`，实现历史读取（FR-003）：按 `session_id` 从 Message 表读取最近 N 轮（`context_turns`）对话并按时间升序返回；实现上下文截断（FR-011 前半）：按消息边界优先丢弃最早历史消息，保证历史不超预算（配合 prompt.py 的知识压缩策略）
- [ ] T022 [US2] 修改 `backend/app/services/rag/prompt.py`，落地 Token 预算分配与截断（FR-011、research §6）：按 `SystemPrompt(~500) + 知识片段(~1500) + 历史(~800) + 用户问题` 预算组装，超限降级顺序为「优先压缩对话历史 → 减少 RAG chunk 数量 → 压缩画像」，严禁丢弃关键业务知识片段；历史按消息边界丢弃、知识片段按需压缩而非整体丢弃
- [ ] T023 [US2] 修改 `backend/app/api/chat.py`，在编排中接入 history：检索前调用 history.py 读取最近 N 轮历史，传入 prompt.py 组装（替换 US1 的空历史占位），保证多轮追问携带上下文

**检查点**：用户故事 2 此刻可独立运行与验证 —— 同一会话连续追问，第二轮回答能基于前文语境（如理解指代），且请求/日志确认携带最近 N 轮历史；超长场景按策略截断而不丢失关键知识（对应 quickstart 场景 2、4）。

---

## 阶段 5：用户故事 3 - 边界与异常情况下的弹性处理（优先级：P3）

**目标**：当输入超长、配额耗尽、检索为空、LLM 超时或限流时，系统给出明确且友好的处理，不报错崩溃、不编造内容、不静默结束。

**独立测试**：分别构造 501 字问题、当日第 101 次提问、检索无命中、模拟 LLM 超时/429，逐一验证系统行为符合约定。

- [ ] T024 [US3] 修改 `backend/app/services/validation.py`，实现每日配额校验与原子计数（FR-002）：按 `(user_id, stat_date)` 唯一键对 `UserQuotaDaily` 在事务内做 `UPDATE ... SET count = count + 1 WHERE count < :limit` 原子递增；校验与递增在同一事务，防止并发重复计数；达到 `daily_quota_limit` 时抛 `QuotaExceeded`（返回 HTTP 429，code=`quota_exceeded`）
- [ ] T025 [US3] 修改 `backend/app/api/chat.py`，实现空检索兜底（FR-005）：retriever 返回空列表/无有效片段时，不建立 LLM 连接、不调用生成，直接推送一个 `data` 事件携带固定兜底话术「抱歉，知识库中没有找到相关信息，请换个方式提问或者联系人工客服。」随后推送 `finish`；该兜底 message 同样持久化且 reference_source 为空数组（对应 contracts/chat-stream.md 空检索兜底协议）
- [ ] T026 [US3] 修改 `backend/app/api/chat.py`，实现 LLM 异常 → SSE `error` 事件（FR-010）：捕获 LLMTimeout/LLMRateLimited/LLMError，以 `error` 事件推送友好错误（code=`llm_timeout`/`llm_rate_limited`/`llm_error`），随后关闭连接；LLM 返回空内容或中途断流按失败处理推送 `error`（llm_error），不发空响应、不静默结束

**检查点**：用户故事 3 此刻可独立运行与验证 —— 分别构造 501 字问题（HTTP 400 `question_too_long`）、超配额提问（HTTP 429 `quota_exceeded`）、无关主题提问（兜底话术且不调用 LLM）、模拟 LLM 超时/429（`error` 事件友好提示），系统行为均符合约定（对应 quickstart 场景 3）。

---

## 阶段 6：打磨与横切关注点（Polish & Cross-Cutting Concerns）

> 关键链路集成测试（宪法要求「必须」）与单元测试补齐、端到端验证。

- [ ] T027 创建 `backend/tests/integration/test_rag_chat_flow.py`，编写关键链路集成测试（research §12、宪法「关键链路集成测试（必须）」）：用真实 Chroma（临时目录）+ 内存 SQLite + mock Ollama 服务，覆盖正常流式（token/meta/finish）、引用来源、消息持久化、空检索兜底、LLM 超时/429、上下文超长截断、并发配额一致性、Reranker 降级回退，另加混合检索两用例：`test_hybrid_bm25_only_keyword_hit`（向量被阈值滤掉、BM25 闸门命中 → 有来源且调 LLM）、`test_fake_reranker_reorders_meta_sources`（注入含「配送」最高分的假精排器 → meta sources[0] 为配送文档）
- [ ] T028 [P] 创建 `backend/tests/unit/` 下单元测试：`test_validation.py`（长度边界 500/501、配额计数）、`test_history_truncation.py`（历史按消息边界丢弃）、`test_prompt.py`（编号知识组装与 token 预算截断）、`test_sse_events.py`（data/meta/finish/error 事件序列约束）；混合检索新增 `test_bm25.py`（分词/显著词闸门/打分排序/空语料/jieba 降级）、`test_reranker.py`（Noop 保序/disabled 与 find_spec 决议/懒加载不导入/注入假模块测 rerank/warmup 失败置 Noop/reset 隔离）、`test_rrf.py`（融合排序/单路保序/空/分数量级）、`test_retriever_hybrid.py`（向量路命中/BM25 独有命中/阈值过滤空/空语料空/RRF 并集共享靠前/FakeReranker 重排/精排异常回落）
- [ ] T029 运行全量测试并修复：在 `backend/` 下执行 `pytest tests/ -v`，确保全部通过；按 quickstart.md 场景 1~4 做端到端手工验证（正常流式、多轮上下文、边界异常、上下文超长）

---

## 依赖关系与执行顺序

- **严格顺序**：T001（目录骨架）→ T007（models）→ T008（session）→ T009（conftest）构成线性基础；随后用户故事按优先级 US1 → US2 → US3 推进。
- **US1 内部依赖**：T010/T011/T012（schemas / Chroma / embedding）先行，T013（retriever）依赖 T011+T012，T019（api/chat.py 编排）依赖前面全部模块，T020（main.py）依赖 T019。
- **跨故事依赖**：US2（history/prompt 截断）依赖 US1 的 prompt.py 与 api/chat.py 编排；US3（配额/兜底/异常）依赖 US1 的 validation.py、retriever.py、llm.py 与 api/chat.py 编排。
- **外部特性依赖（本特性不实现，仅消费契约）**：鉴权（JWT，003 特性）、知识库文档解析与向量化入库（002 特性，提供就绪文档与 ContentChunk 向量）、会话 CRUD（004 特性，提供 Session 记录）；本特性假定这些已就绪或通过预置数据/夹具提供。

## 并行机会

- **Phase 1（Setup）**：T002~T006 均为独立文件，可完全并行。
- **US1**：T010（schemas）、T011（Chroma）、T012（embedding）、T014（prompt）、T015（llm）、T016（sse）、T017（postcheck）、T018（validation）互不依赖，可并行开发；T013、T019、T020 依次串行收口。
- **跨故事并行团队**：基础阶段完成后，US1 由核心团队推进；US2（history/截断）与 US3（配额/兜底/异常）可分别由不同成员在 US1 的 prompt.py/validation.py/retriever.py/llm.py/api/chat.py 稳定后并行开发（仅需各自依赖的 US1 接口已定稿）。
- **Polish**：T027（集成测试）与 T028（单元测试）可并行编写。

## 实施策略

- **MVP 优先**：先交付用户故事 1（核心 RAG 闭环），即可让用户在单轮场景得到带来源的流式可信回答，构成最小可用产品；随后增量叠加 US2（多轮上下文）、US3（边界弹性）。
- **增量交付**：每个用户故事完成后均为一个可独立运行、可独立验证的增量（对应 quickstart 场景 1 → 2/4 → 3），可随时对外演示或灰度。
- **并行团队策略**：核心链路（US1）作为主线先行；一旦 US1 的模块接口（schemas、retriever、prompt、llm、sse、validation、api 编排）稳定，即可并行启动 US2、US3 的增量开发，缩短总周期。
- **质量门禁**：每个故事完成后须通过该故事的「独立测试」与对应 quickstart 场景；Phase 6 完成关键链路集成测试与全量单测后，方可视为本特性交付完成。
