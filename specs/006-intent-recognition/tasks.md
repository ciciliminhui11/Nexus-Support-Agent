# 任务清单：意图识别（三层漏斗）

**功能分支**：`006-intent-recognition` | **规格**：[spec.md](spec.md) | **计划**：[plan.md](plan.md)

本清单把「意图识别（三层漏斗）」拆解为可独立实施、可独立验证的增量任务。识别链路为**三层漏斗**（前置校验规则层 → 小模型识别层 → 大模型兜底层），最终产出四类意图（产品咨询 / 售后 / 闲聊 / 投诉 + 未识别兜底），写入 `message.intent_label` 并按意图路由。

任务按用户故事组织（P1 → P2 → P3），共享基础设施与阻塞前置放在前两个阶段。每个任务的描述包含精确文件路径（源自 [plan.md](plan.md) 的项目结构），LLM 无需额外上下文即可实施。

---

## Phase 1 准备阶段（Setup）

> 项目初始化与基础结构，为后续所有阶段提供骨架。此阶段任务不携带用户故事标签。

- [ ] T001 [P] 创建后端目录骨架与意图识别模块的包结构：新建 `backend/app/intent/__init__.py`、`backend/app/intent/rules/__init__.py`、`backend/app/intent/small_model/__init__.py`、`backend/app/intent/fallback/__init__.py`，每个 `__init__.py` 仅保留包标识（可含模块 docstring），不写业务逻辑。
- [ ] T002 [P] 创建 `backend/requirements.txt`，写入本特性依赖清单：`fastapi`、`httpx`（模型 API 调用）、`ahocorasick-ng`（关键词多模式串匹配）、`pyparsing`（句式模板解析）、`pyyaml`（词库/模板/负样本配置解析）、`pydantic-settings`、`python-dotenv`（配置与密钥）、`pytest`（测试）。保留版本号以仓库锁定为准。
- [ ] T003 [P] 创建 `backend/.env.example` 占位模板，包含密钥/模型变量键名（值留空占位）：小模型层 `SMALL_MODEL_NAME=`、`SMALL_MODEL_API_KEY=`、`SMALL_MODEL_BASE_URL=`（独立厂商/端点，不复用 DeepSeek 凭据），兜底层 `DEEPSEEK_LARGE_MODEL=`（复用 `DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL`）。真实密钥由用户后续填写、不提交仓库（FR-014）。
- [ ] T004 [P] 创建 `backend/pyproject.toml`（或 `backend/pytest.ini`），配置 pytest：`testpaths = ["tests"]`，声明单元测试目录 `tests/unit/intent` 与集成测试目录 `tests/integration/intent`，并开启所需的 asyncio/HTTP 测试插件（如需 `pytest-asyncio` 则在此一并声明）。

## Phase 2 基础阶段（Foundational）

> 阻塞所有用户故事的前置任务：类型/枚举、配置加载、路由映射、默认配置数据、测试夹具。此阶段任务不携带用户故事标签。

- [ ] T005 [P] 在 `backend/app/config.py` 追加 intent 配置节：定义 `Settings`（pydantic-settings），从 `.env` 读取小模型层 `SMALL_MODEL_NAME`、`SMALL_MODEL_API_KEY`、`SMALL_MODEL_BASE_URL`（独立凭据，不复用 DeepSeek），兜底层 `DEEPSEEK_LARGE_MODEL`（空则回退 `DEEPSEEK_CHAT_MODEL`）；从 `system_config` 表/配置读取阈值与参数：`intent_high_threshold`（默认 0.9）、`intent_low_threshold`（默认 0.6）、`intent_clarify_retry`（默认 1）、`intent_reverse_calibrate`（默认 true）、`intent_model_self_check`（默认 false），以及词库/句式模板/负样本文件路径（指向 `backend/config/intent_keywords.yaml`、`intent_patterns.yaml`、`intent_negative_samples.yaml`）。
- [ ] T006 [P] 创建 `backend/app/intent/schema.py`，定义：`IntentCategory` 枚举（`product_consult` / `after_sale` / `small_talk` / `complaint` / `unknown`）、`SourceLayer` 枚举（`rule` / `small_model` / `fallback` / `unknown`）、`HandlerKey` 枚举（`rag_qa` / `small_talk` / `complaint` / `default`），以及 `IntentResult` 数据类（字段：`intent: IntentCategory`、`confidence: float`、`source_layer: SourceLayer`、`raw_query: str`、`normalized_query: str`、`matched_patterns: list[str]`、`clarification_question: str | None`）。字段语义与类型对齐 data-model.md §2。
- [ ] T007 [P] 创建 `backend/app/intent/router.py`，实现 `route(intent: IntentCategory) -> HandlerKey` 映射：`product_consult`/`after_sale` → `rag_qa`、`small_talk` → `small_talk`、`complaint` → `complaint`、`unknown` → `default`（对齐 data-model.md §4）。Handler 具体实现经依赖注入注册（001 提供 `rag_qa` handler），router 不持有具体实现。
- [ ] T008 [P] 创建默认配置文件 `backend/config/intent_keywords.yaml`（词 → 意图，含产品咨询/售后/闲聊/投诉四类示例词，如「投诉」→complaint）、`backend/config/intent_patterns.yaml`（句式模板 → 意图，如「帮我查询…」→product_consult、「取消订单…」→after_sale）、`backend/config/intent_negative_samples.yaml`（意图 → 反特征，如 complaint 的「投诉咨询中心」）。默认内容参照 data-model.md §3 示例，作为 v1 内置基线供联调校准。
- [ ] T009 [P] 创建测试基础设施：新建 `backend/tests/unit/intent/__init__.py`、`backend/tests/integration/intent/__init__.py` 与 `backend/tests/conftest.py`，在 `conftest.py` 中提供可注入的 **mock 小/大模型 API 客户端夹具**（fixture 可模拟模型返回指定 JSON、模拟超时与 429 限流），供后续集成测试复用，避免依赖真实 API。

**检查点**：基础就绪，可开始并行实施用户故事。此时 `schema.py` 提供类型契约、`config.py` 提供配置入口、`router.py` 提供路由映射、默认配置数据与 mock 模型夹具就位。

---

## 阶段 3：用户故事 1 - 高频/固定问法零成本拦截（优先级：P1）

**目标**：用户在输入含明确关键词或固定句式（如「我要投诉」「帮我查询退款政策」「怎么退换货」）时，前置校验层（规则层）直接识别出意图，**不调用任何模型**，毫秒级完成并标记意图标签。

**独立测试**：配置一套关键词库与句式模板后，输入命中规则的固定问法，可独立验证：不调用任何模型即输出意图、消息带意图标签、并按路由分发到对应处理。验收场景覆盖：①「我要投诉你们的服务质量」→ 命中「投诉」意图、不调模型、`intent_label=投诉`；② 固定句式「帮我查询…」「取消订单…」→ 句式模板命中直接输出；③ 多个关键词同现（「投诉」+「咨询」）→ 采用最长匹配策略取更长命中结果。

- [ ] T010 [P] [US1] 创建 `backend/app/intent/normalize.py`，实现文本归一化流水线：全角→半角、去除空白与特殊符号、繁简转换（v1 用内置常用字映射表，不引入 opencc）、常见形近字纠错（配置化纠错表，如「退还/退货」归一）。函数签名 `normalize(text: str) -> str`，返回归一化文本仅供规则层匹配；原始输入在调用方保留（FR-001）。
- [ ] T011 [P] [US1] 创建 `backend/app/intent/rules/keyword_store.py`，实现词库加载：读取 `backend/config/intent_keywords.yaml`（YAML/JSON），构建「词 → 意图」映射（如 `{"投诉": complaint, "退款": after_sale, ...}`），提供 `load_keywords(path) -> dict[str, IntentCategory]` 或等价的词表访问接口。
- [ ] T012 [P] [US1] 创建 `backend/app/intent/rules/ac_automaton.py`，封装 `ahocorasick-ng` 实现关键词匹配：`build(automaton, keywords)` 构建自动机；匹配使用**最长匹配**语义（多条命中取更长者，FR-002）；在库命中位置（start/end）基础上做**词边界薄校验**——命中串前后各取一字符校验是否为词边界字符，只匹配完整语义片段、不匹配任意子串（FR-003）。输出命中词与对应意图。
- [ ] T013 [P] [US1] 创建 `backend/app/intent/rules/template_patterns.py`，用 `pyparsing` 定义句式模板文法：读取 `backend/config/intent_patterns.yaml`，把每条模板（如「帮我查询(?P<subject>…）」「取消订单(?P<order_id>…)」）加载时编译为 pyparsing 解析器，支持命名捕获（named results）；提供 `match_patterns(normalized_text) -> 命中模板的意图标签`，覆盖强固定句式（FR-004）。
- [ ] T014 [US1] 创建 `backend/app/intent/service.py`，实现 `recognize()` 的**规则层编排**：入参 `query`（已通过 001 长度/配额校验）→ 调用 `normalize()` 归一化 → 依次执行 AC 自动机关键词匹配与句式模板匹配 → 命中且无意图冲突时**直接返回** `IntentResult(intent, confidence=1.0, source_layer=rule, matched_patterns=[...])` 并终止，**不调用任何模型**（FR-005）；规则层未命中时返回哨兵（如 `source_layer=unknown` 或 None），为后续小模型层预留流转点。

**检查点**：用户故事 1 此刻可独立运行与验证——向 `recognize()` 输入命中规则的固定问法，可直接得到规则层意图结果、零模型调用；未命中输入正确流转（暂返回未识别哨兵）。

---

## 阶段 4：用户故事 2 - 常规口语表达由小模型识别 + 双阈值判定（优先级：P2）

**目标**：用户用口语化、非固定句式表达（如「这玩意儿能不能七天无理由」「你们家售后怎么弄的」）时，规则层未命中，交由小模型（DeepSeek-R1-0528-Qwen3-8B）分类；通过正向校准 + 反向校准抑制误判，置信度经高/低双阈值判定（≥高阈值直接出、中段反问澄清、<低阈值流转大模型）。

**独立测试**：配置好小模型 API 后，输入非固定句式问题，可独立验证高/中/低置信度三条路径的判定行为，以及反向校准拦截行为。验收场景覆盖：① 置信度 ≥ 高阈值 → 直接输出、不进入大模型层；② 置信度落在【低阈值, 高阈值）→ 反问澄清后重判、重判仍不达标按配置重试小模型一次；③ 置信度 < 低阈值 → 放弃小模型结果、流转大模型兜底；④ 反向校准命中负样本 → 拒绝该预测、视同拿不准流转下一层。

- [ ] T015 [P] [US2] 创建 `backend/app/intent/small_model/client.py`，实现小模型薄客户端：用 `httpx` 直连 OpenAI 兼容 `POST /chat/completions`（Bearer 鉴权），请求携带 `response_format={"type":"json_object"}`；返回 JSON 在客户端自行校验 schema（字段存在/类型/`intent` 枚举值合法）；显式设置超时（默认 30~60s）并对 429 做指数退避重试；每次调用后记录 `usage`（prompt/completion/total/reasoning tokens）连同 model、时间戳、所属漏斗层 `small_model` 写入日志/统计（research §6.1）。
- [ ] T016 [P] [US2] 创建 `backend/app/intent/small_model/threshold.py`，实现高/低双阈值判定：`≥ high_threshold`（默认 0.9）→ 直接输出意图；`[low_threshold, high_threshold)`（默认 [0.6, 0.9)）→ 触发澄清反问（生成「请问你是想要 X 还是 Y？」追问文本）并按配置重试；`< low_threshold` → 放弃小模型结果、标记流转大模型。可选增强：临界带二次采样投票（低温采样 N=3~5 次，投票一致率作为二次置信度复核，端点不支持时退化为自报置信度）。参数从 `IntentSettings` 读取（FR-008）。
- [ ] T017 [P] [US2] 创建 `backend/app/intent/small_model/calibrate.py`，实现正向校准与反向校准：**正向校准**——基于标注数据的分类约束（标注基线对输出做约束）；**反向校准**——读取 `backend/config/intent_negative_samples.yaml` 负样本库，对模型输出意图 A 后，在归一化输入上做 A 的反特征匹配（词/正则），命中即拒绝该预测（特征规则通道，默认开启）；可选**模型自评通道**（向小模型二次提问「该输入是否真正属于意图 A 的特征？」，返回「否」即拒绝，受 `intent_model_self_check` 开关控制，默认关闭）。函数返回「是否采信」判定（FR-007）。
- [ ] T018 [US2] 在 `backend/app/intent/service.py` 中增加**小模型层编排**：规则层未命中时 → 调用 `small_model/client.py` 分类 → 调用 `calibrate.py` 正向校准 + 反向校准（拒绝则视同拿不准）→ 调用 `threshold.py` 双阈值判定 → 命中高阈值返回 `IntentResult(source_layer=small_model)`；中段返回 `clarification_question`（澄清后重判，仍不达标按配置重试）；低阈值或反向校准拒绝则流转大模型兜底层（为 US3 预留流转点）。

**检查点**：用户故事 2 此刻可独立运行与验证——mock 小模型 API 下，高/中/低置信度三条路径与反向校准拦截行为均可复现。

---

## 阶段 5：用户故事 3 - 歧义/新说法由大模型兜底（优先级：P3）

**目标**：小模型完全拿不准的歧义、新说法、复杂混合表达，由大模型通过 Few-shot 样例 + JSON 结构化输出兜底识别，保证识别结果 100% 可被下游解析；模型不可用时优雅降级，不阻断主流程。

**独立测试**：配置好大模型 API 后，输入模糊歧义问题，可独立验证返回 JSON 结构化意图结果；模型不可用时验证降级行为。验收场景覆盖：① 小模型低置信度放弃/反向校准拒绝 → 大模型依据 Few-shot 样例与意图清单输出 JSON 结构化结果（意图 + 置信度），禁止自由文本闲聊；② 大模型返回无法解析/为空/调用失败（超时/限流）→ 返回降级结果（`unknown` + 默认路由），不阻断主流程；③ 四类意图之外的混合/离题表达 → 归入最相近意图或按配置兜底策略标记。

- [ ] T019 [P] [US3] 创建 `backend/app/intent/fallback/few_shot.py`，定义 Few-shot 样例常量：覆盖每类意图（产品咨询/售后/闲聊/投诉）至少 1 例 + 1 例歧义归「未识别」的样例（用户输入 → 输出意图），供兜底 prompt 组装引用（FR-009）。
- [ ] T020 [US3] 创建 `backend/app/intent/fallback/client.py`，实现大模型客户端与兜底逻辑：复用 OpenAI 兼容 `httpx` 调用（可复用 small_model/client.py 的通用 HTTP 封装），组装兜底 prompt（系统指令「你是意图识别器，只输出 JSON」→ 可用意图清单（四类 + 未识别）→ Few-shot 样例 → 用户 query）；强制 `response_format={"type":"json_object"}` 结构化输出；返回 JSON 在客户端解析并校验 schema（FR-010）；解析失败/空/超时/429 统一降级返回 `unknown`；每次调用记录 `usage` 与漏斗层 `fallback`（research §6.1）。
- [ ] T021 [US3] 在 `backend/app/intent/service.py` 中增加**大模型兜底层编排**：小模型放弃（低置信度或反向校准拒绝）时 → 调用 `fallback/client.py` 兜底识别 → 解析成功返回 `IntentResult(source_layer=fallback)`；解析失败/超时/429/密钥未配置 → 返回降级 `IntentResult(intent=unknown, source_layer=unknown, confidence=0.0)`，**不抛出使问答链路失败的异常**（FR-013）。

**检查点**：用户故事 3 此刻可独立运行与验证——mock 大模型 API 下，JSON 结构化兜底与「模型不可用 → unknown 降级」两条路径均可复现，且不影响主流程。

---

## 阶段 6：打磨与横切关注点（Polish & Cross-Cutting Concerns）

> 跨所有用户故事的集成、标注、路由、调试接口与降级收尾。此阶段任务不携带用户故事标签。

- [ ] T022 [P] 创建 `backend/app/api/intent_debug.py`，实现管理员联调接口 `POST /api/intent/debug`：鉴权要求管理员角色（复用 `deps.py` 的 admin 依赖），请求 `{"query": "..."}`，返回三层漏斗各层中间结果——`query`、`normalized_query`、`rule_layer`（`hit`/`matched_patterns`/`intent`）、`small_model_layer`（未进入为 null）、`fallback_layer`（未进入为 null）、`final`（`intent`/`confidence`/`source_layer`）；错误码：400 `invalid_query`（query 空/超长）、401 `unauthorized`、403 `forbidden`、429 `model_rate_limited`（对齐 contracts/intent-api.md 二/三节）。
- [ ] T023 [P] 在 `backend/app/api/deps.py` 提供/复用 003 特性提供的管理员（admin 角色）鉴权依赖：从 `Authorization: Bearer <jwt>` 解析 JWT 并校验 admin 角色，供 `intent_debug.py` 使用（若 003 尚未落地，则先定义返回 401/403 的占位 admin 依赖）。
- [ ] T024 实现 001 集成点：在 001 RAG 问答链路「输入校验之后、Query 向量化之前」通过**依赖注入**插入 `recognize()` 调用（不修改 001 主链路代码）；根据识别结果决定是否进入检索——`small_talk` / `complaint` 意图**短路跳过知识库检索**返回模板/转人工话术，`product_consult` / `after_sale` 进入 RAG 检索，`unknown` 走 001 默认问答或兜底话术（FR-012 / SC-007）。
- [ ] T025 实现意图标签落库：将最终识别结果（意图 + 来源层）写入会话消息的 `message.intent_label` 字段（复用 001/004 已设计的消息表字段），供会话详情与后台统计使用；`intent_label` 只持久化意图枚举值（FR-011）。
- [ ] T026 完善边界与异常兜底：空输入/纯标点/纯表情输入 → 归入 `unknown` 降级且不报错；模型超时/限流（429）/密钥未配置 → 降级 `unknown` + 默认路由，**确保识别流程异常不影响用户提问主流程**（FR-013）；校验词边界负样本边界用例（如「投诉咨询中心」不误判为投诉）。
- [ ] T027 端到端联调与校准：按 [quickstart.md](quickstart.md) 场景 1~6 逐条验证（规则层零成本拦截、小模型高置信度、中段澄清、低置信度流转、模型不可用降级、路由行为与 `intent_label` 落库），并校准默认词库/句式模板/阈值基线；运行 `cd backend && pytest tests/unit/intent tests/integration/intent -v` 确认全部通过。

---

## 依赖关系与执行顺序

- **Phase 1（Setup）→ Phase 2（Foundational）**：先完成骨架、依赖与配置（T001–T004），再落地类型/配置/路由/默认数据/测试夹具（T005–T009）。Foundational 是三个用户故事的共同前置。
- **三个用户故事按优先级串行**：US1（规则层，P1）→ US2（小模型层，P2）→ US3（大模型兜底层，P3）。三者共享同一个 `backend/app/intent/service.py` 编排入口，后续故事在 `service.py` 中追加对应层编排，依赖前序层的流转点（US1 未命中 → US2；US2 放弃 → US3）。
- **Polish 阶段**依赖三个用户故事全部完成：`intent_debug.py`（T022）需三层结果齐全；001 集成（T024）与 `intent_label` 落库（T025）依赖 `service.py` 完整链路；端到端验证（T027）依赖全部前置任务。

## 并行机会

- **Phase 1 内**：T001/T002/T003/T004 互不依赖，可并行。
- **Phase 2 内**：T005（配置）/T006（schema）/T007（router）/T008（默认配置数据）/T009（测试夹具）为不同文件、无硬依赖，可并行；其中 `router.py` 引用 `schema.py` 的 `HandlerKey` 枚举（软依赖，接口明确后可并行）。
- **每个用户故事内部**：规则层四件套（normalize / keyword_store / ac_automaton / template_patterns，T010–T013）与模型层三件套（client / threshold / calibrate，T015–T017）为不同文件，可并行；各故事的 `service.py` 编排（T014/T018/T021）依赖本故事内组件完成，需最后实施。
- **跨团队**：Foundational 就绪后，US1 / US2 / US3 的组件层可由不同开发者并行推进（接口契约已由 `schema.py` 固定），但 `service.py` 编排按故事顺序合并。

## 实施策略

- **MVP 优先（先交付用户故事 1）**：US1 是三层漏斗经济性根基——规则层零模型、零成本、最低延迟，可独立验证「高频问法不调用模型」这一核心价值。先交付 US1 即可获得「规则层拦截」的可用闭环。
- **增量交付**：每完成一个用户故事即形成一个可运行、可独立验证的增量（规则层 → +小模型 → +大模型兜底），最后用 Polish 阶段打通 001 集成、标注落库与管理端联调。
- **并行团队策略**：Foundational 完成后，若有多名开发者，可按「规则层组件 / 小模型层组件 / 大模型层组件」切分并行；`service.py` 编排与 001 集成点（T024）作为收口任务，由了解全链路的开发者统一合并，保证三层漏斗流转与「闲聊/投诉不检索」的路由正确性。

---

**任务统计**：共 27 个任务。用户故事 1（P1）：5 个；用户故事 2（P2）：4 个；用户故事 3（P3）：3 个；Setup 4 个；Foundational 5 个；Polish 6 个。**MVP 范围 = 用户故事 1（高频/固定问法零成本拦截）**。
