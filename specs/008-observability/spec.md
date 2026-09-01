# 功能规格说明：链路埋点可观测性

**功能分支**：`008-observability`

**创建日期**：2026-09-01

**状态**：草稿

**输入**：开发者描述："给上传文档（解析、切片、embedding、召回）与 AI 回答流程（意图识别走哪层、召回了哪个文档、结果如何）等重要过程埋点，异步上报。开发者触发后能直接看到哪里有问题。"

## 识别链路概述

本特性为「文档入库流水线」与「问答链路」添加**过程埋点（trace）**：

1. **采集**：每个重要阶段记录一条 span（阶段名、开始时间、耗时、状态 ok/error/skipped、关键结果负载 detail），写入内存缓冲（微秒级、不阻塞任何业务链路）。
2. **异步上报**：后台定时任务把缓冲批量写入 MySQL `trace_event` 表（进程关停时兜底 flush 剩余）；落库失败只记日志不阻塞、不重试。
3. **可观测出口**：后端控制台（stdout）在每次链路结束时打印**可读的完整链路流转块**（阶段顺序、耗时、状态、关键指标）；管理员可经 `/api/trace/list`、`/api/trace/detail` 查询历史 trace 定位问题。

埋点覆盖：
- **ingest 链路**：文档加载 → 解析 → 切片 → 嵌入+入库 → 终态（就绪/失败/已取消），含回滚与并发删除取消路径。
- **chat 链路**：前置校验 → 意图识别（三层漏斗来源层）→ 混合召回（向量/BM25/RRF/Reranker 状态 + 命中文档与分数）→ Prompt 组装 → LLM 流式（首 token 时延、字符数、错误码）→ 输出后校验 → 终态，含意图短路与空检索兜底分支。

## 用户场景与测试 *(必填)*

### 用户故事 1 - 文档入库链路可观测（优先级：P1）

开发者上传文档后，能在一个地方（控制台链路块 + trace 表 + 查询 API）看到：每个阶段耗时、切片数、embedding 批次与维度、最终状态，以及在失败/回滚/取消时看到出错的阶段与原因，从而定位"文档为什么没进库 / 为什么失败"。

**优先级理由**：文档入库是知识库正确性的根基，失败与慢点最常见，且流水线阶段边界清晰、最容易先落地，故为 P1。

**独立测试**：上传一个正常文档与一个坏文件，可独立验证 ingest 链路的完整 span 序列与失败路径的 error span。

**验收场景**：

1. **假如** 开发者上传一个正常文本文件，**当** 处理完成，**那么** 控制台打印完整 ingest 链路块，`trace_event` 表出现 ≥4 条 ok span（doc_parse/doc_split/doc_embed_ingest/doc_status），detail 含字符数/切片数/batches/dim。
2. **假如** 上传一个解析失败的坏文件，**当** 处理，**那么** 出错阶段产生 error span，`doc_status` span 记录状态=失败，trace 整体状态=error，detail 含失败原因。
3. **假如** 处理中的文档被并发删除，**当** 取消，**那么** trace 记录已取消终态与回滚路径，不残留"处理中"误导。

---

### 用户故事 2 - 问答链路可观测（优先级：P1）

开发者（或管理员）让前端用户正常提问后，能直接看到：意图识别走了哪一层（规则/小模型/大模型兜底/未识别）与置信度、召回了哪些文档及其分数（向量/BM25 命中数、候选池规模、Reranker 是否启用）、LLM 首 token 时延与总耗时、是否触发超时/限流/连接错误，从而定位"为什么回答不对 / 为什么慢 / 为什么报错"。

**优先级理由**：问答是核心用户体验链路，意图分层与召回质量是最常见的"哪里有问题"来源，且意图模块已有分层溯源数据结构可直接复用，故为 P1。

**独立测试**：一次正常流式问答、一次意图短路问答、一次 LLM 异常问答，可独立验证 chat 链路的完整 span 序列与各分支。

**验收场景**：

1. **假如** 用户正常提问且命中知识库，**当** 问答流式完成，**那么** 控制台打印 chat 链路块，trace 出现 ≥6 条 span（preflight/intent/retrieve/prompt/llm_stream/postcheck/finish），intent 记录来源层与置信度，retrieve 记录命中文档+分数，llm_stream 记录首 token 时延。
2. **假如** 用户提问命中意图短路（闲聊/投诉/澄清），**当** 处理，**那么** trace 记录 short_circuit span，不出现 retrieve/llm_stream 阶段。
3. **假如** 知识库为空或检索无命中，**当** 处理，**那么** trace 记录 empty_retrieval 分支，不调用 LLM。
4. **假如** LLM 超时/限流/连接异常，**当** 处理，**那么** llm_stream span 记录对应 error_code，trace 整体状态=error。

---

### 用户故事 3 - 历史回溯与问题定位（优先级：P2）

开发者可经后端查询 API（仅管理员）按 trace 类型/文档/会话/时间/状态过滤历史 trace，查看单条 trace 的完整阶段序列与负载，定位历史问题；可用 `trace_enabled=false` 完全关闭采集（零开销）。

**优先级理由**：历史回溯在排障与回归验证中有用，但依赖前面两条链路的采集先落地，故为 P2。

**独立测试**：用管理员账号调 list/detail，用普通账号验证 403，可独立验证权限与过滤。

**验收场景**：

1. **假如** 管理员调用 `GET /api/trace/list`，**当** 带过滤条件，**那么** 返回聚合的 trace 列表（trace_id/类型/时间/span 数/是否含错误），不含 question/detail（轻量）。
2. **假如** 管理员调用 `GET /api/trace/detail?trace_id=`，**当** 提供已存在的 trace_id，**那么** 按 seq 返回该 trace 全部 span（含 detail 全文）；trace_id 不存在时返回 404。
3. **假如** 普通用户调用上述接口，**当** 请求，**那么** 返回 403。
4. **假如** 设置 `trace_enabled=false`，**当** 触发任意操作，**那么** 不采集、不打印、不落库任何 trace（零开销）。

---

## 功能需求（FR）

- **FR-001** 文档处理链路 MUST 全阶段埋点：doc_load / doc_parse / doc_split / doc_embed_ingest / doc_status，覆盖失败、回滚、并发删除取消路径。
- **FR-002** 问答链路 MUST 全阶段埋点：preflight / intent / retrieve / prompt / llm_stream / postcheck / finish，覆盖意图短路与空检索兜底分支。
- **FR-003** 埋点 MUST 先入内存缓冲、由后台任务批量异步落库，不阻塞请求；进程关停 MUST flush 剩余。
- **FR-004** 后端控制台 MUST 按 `trace_console_log` 开关打印可读完整链路块。
- **FR-005** 管理员 MUST 可经 `/api/trace/list`、`/api/trace/detail` 查询历史 trace。
- **FR-006** 意图 span MUST 记录分层来源（rule / small_model / fallback / unknown）、置信度、命中的匹配模式与澄清话术。
- **FR-007** 召回 span MUST 记录就绪文档数、向量/BM25 命中数、候选池规模、Reranker 状态（enabled/noop/failed）与命中文档+分数。
- **FR-008** LLM span MUST 记录 backend、首 token 时延、输出字符数、错误码（llm_timeout / llm_rate_limited / llm_error）。
- **FR-009** 查询接口 MUST 仅管理员可访问；detail 数据 MUST 脱敏（不存密钥、question 截断）。
- **FR-010** `trace_enabled=false` 时 MUST 零采集、零打印、零落库（Tracer 全程短路）。
- **FR-011**（P2）`trace_retention_days` 超期数据由后台任务定期清理（≤0 表示不清理）。

## 关键实体

- `TraceEvent`（表 `trace_event`）：一次链路的每个 span 平铺一行，`trace_id` 关联同一次链路；字段见 data-model 约定（trace_id / trace_type / stage / seq / status / start_at / duration_ms / detail(JSON) / doc_id / session_id / user_id / message_id / error / create_time）。
- `Tracer`：每操作一个实例，收集 spans 并负责控制台输出；`trace_enabled=false` 时短路。
- `Collector`：进程级线程安全缓冲，`flush(db)` 批量落库。

## 成功标准（SC）

- **SC-001** 单次上传文档，控制台 + `trace_event` 出现完整 ingest 链路（≥4 条 ok span）；失败路径含 error span 与终态。
- **SC-002** 单次流式问答，控制台 + `trace_event` 出现完整 chat 链路（≥6 条 span），`first_token_ms` 正确。
- **SC-003** 关键阶段（parse/split/embed/intent/retrieve/llm）100% 在 trace 可见；LLM 三类异常正确映射 error_code。
- **SC-004** flush 不阻塞 SSE：首 token 前链路零新增 DB 写（trace 只做内存 append）。
- **SC-005** 按 trace_id 可完整还原链路；list/detail 权限校验（普通用户 403）。
- **SC-006** 全量 pytest 通过 + Spec→Code 映射表完整（宪法三轮闭环验证）。

## 假设

- 单进程 uvicorn 部署假设成立（与 002 后台任务一致）；多 worker 时内存缓冲被切碎，需换共享队列（记录于 research，不在本期）。
- 观测开关（trace_enabled 等）重启级生效，不走 system_config 热调。
