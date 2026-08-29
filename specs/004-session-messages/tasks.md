# 任务清单：会话与消息

**分支**：`004-session-messages` | **日期**：2026-08-29 | **输入**：[plan.md](plan.md)、[spec.md](spec.md)、[data-model.md](data-model.md)、[contracts/session-api.md](contracts/session-api.md)、[research.md](research.md)

本清单为「会话与消息」模块生成实施任务。任务按用户故事（US1→US3）组织，每个故事可独立实现与独立测试。任务 ID 全程连续递增；`[P]` 表示可并行（不同文件、无未完成依赖）；`[US1]`/`[US2]`/`[US3]` 为用户故事标签。

> 上游依赖：`backend/app/api/deps.py` 的 `get_current_user` 鉴权依赖由 **003-user-auth** 提供；`Session`/`Message` 模型基础定义与 `backend/app/db/session.py`、`backend/app/config.py`、`backend/app/main.py` 骨架由 **001-rag-qa** 规划。若这些文件尚未落地，本清单的 Setup/Foundational 任务负责补齐或核对。

---

## Phase 1 准备阶段（Setup）

项目初始化与基础结构。此阶段任务不加用户故事标签。

- [ ] T001 [P] 建立会话模块包骨架：创建空包文件 `backend/app/services/session/__init__.py`；核对 `backend/app/__init__.py`、`backend/app/api/__init__.py`、`backend/app/schemas/__init__.py`、`backend/app/services/__init__.py`、`backend/app/db/__init__.py` 已存在（若由 001/003 已建立则跳过，仅确认目录结构对齐 plan.md「源码（仓库根目录）」）。
- [ ] T002 [P] 在 `backend/app/config.py` 中新增会话模块配置项并给出默认值（依据 contracts/session-api.md「配置契约」）：`session_page_size=20`、`message_page_size=20`、`message_page_size_max=100`、`default_session_title="新会话"`、`session_title_summary_len=20`、`context_turns=6`（pydantic-settings 字段，读取 `.env`）。
- [ ] T003 [P] 建立测试基础设施：创建 `backend/tests/__init__.py` 与 `backend/tests/conftest.py`，提供隔离测试数据库夹具（SQLAlchemy 临时库 + 建表 + 覆盖 `get_current_user` 依赖返回固定测试用户），供后续 unit/integration 测试复用（见 plan.md「测试」pytest）。

---

## Phase 2 基础阶段（Foundational）

阻塞所有用户故事的前置任务。此阶段任务不加用户故事标签。

- [ ] T004 [P] 在 `backend/app/db/models.py` 中定义 `Session` 与 `Message` SQLAlchemy 模型（与 001 共用同一张表；若 001 已定义则逐字段核对一致，见 data-model.md）—— `Session`：id(BIGINT PK 自增)、user_id(BIGINT FK→user.id)、title(VARCHAR(100))、create_time(DATETIME 默认当前时间)；`Message`：id(BIGINT PK)、session_id(BIGINT FK→session.id)、role(ENUM('user','ai'))、content(TEXT)、reference_source(JSON 可空)、intent_label(VARCHAR(50) 可空)、create_time(DATETIME)。同时添加索引 `(user_id, create_time DESC)` 与 `(session_id, create_time, id)`。
- [ ] T005 [P] 在 `backend/app/schemas/session.py` 中定义 Pydantic 响应结构（依据 contracts/session-api.md 各端点返回体）：`SessionCreateResponse`（session_id/title/create_time）、`SessionListItem`（session_id/title/create_time）、`SessionListResponse`（total/items）、`SessionDetailResponse`（session_id/title/create_time/message_count）、`MessageItem`（message_id/role/content/reference_source/intent_label/create_time）、`MessageListResponse`（total/items）。
- [ ] T006 在 `backend/app/services/session/session_crud.py` 中实现归属校验函数 `get_owned_session(db, session_id, user_id)`：按 id 查询 `Session`，当 `session is None` 或 `session.user_id != user_id` 时返回 None，否则返回该会话对象。此函数供详情/消息端点统一复用，保证数据隔离无遗漏（见 research.md §2「数据隔离实现」）。

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 创建会话并开始问答（优先级：P1）

**目标**：登录用户能创建会话（默认标题「新会话」、归属当前用户），创建后即可在该会话内发起问答；供问答链路复用的多轮历史读取能力就绪。

**独立测试**：登录后创建会话，可独立验证：会话创建成功、归属当前用户、可在其中发起问答。

- [ ] T007 [US1] 在 `backend/app/services/session/session_crud.py` 中实现 `create_session(db, user_id)`：创建一条 `Session`（`user_id`=当前用户、`title`=配置 `default_session_title`「新会话」、`create_time` 默认当前时间），返回会话对象（对应 FR-001/FR-006，data-model.md「标题规则」）。
- [ ] T008 [US1] 在 `backend/app/services/session/session_crud.py` 中实现 `update_title_from_first_message(db, session_id, content)`：当会话 `title` 仍为默认值「新会话」且收到首条用户消息时，将标题更新为「content 前 `session_title_summary_len` 字符 + `…`」（截断不拆分代理字符；见 research.md §1「默认标题策略」，供 001 写入首条消息后调用）。
- [ ] T009 [US1] 在 `backend/app/api/session.py` 中实现 `POST /api/session` 端点：定义 `router = APIRouter()`，依赖 `get_current_user`（`backend/app/api/deps.py`）鉴权，调用 `create_session`，返回 201 `{session_id, title, create_time}`；未登录走 401（contracts/session-api.md）。并将该 router 注册到 `backend/app/main.py`。
- [ ] T010 [US1] 在 `backend/app/services/history.py` 中实现 `get_recent_messages(db, session_id, turns)`：读取会话最近 N 轮历史消息——先 `ORDER BY create_time DESC, id DESC LIMIT 2*turns`（一轮含 user+ai 两条，故取 2*N 条）再倒序还原为正序返回，`turns` 取配置 `context_turns`（对应 FR-008，供 001 组装多轮上下文，见 data-model.md「最近 N 轮」查询契约）。
- [ ] T011 [US1] 在 `backend/tests/unit/test_session_crud.py` 编写单元测试：`create_session` 创建成功且 `user_id` 归属正确、默认标题为「新会话」；`update_title_from_first_message` 在标题仍为默认值时正确生成「前 20 字符 + …」摘要、非默认值时不覆盖（见 research.md §6 测试策略）。
- [ ] T012 [US1] 在 `backend/tests/integration/test_session_flow.py` 编写集成测试：创建会话 → 模拟 001 问答链路直接向 `Message` 表写入提问+回答（user 一条、ai 一条带 `reference_source`）→ 按 `session_id` 读回消息可见（验证 SC-001 创建后可问答、SC-004 持久化生效）。

**检查点**：用户故事 1 此刻可独立运行与验证——登录创建会话返回 201 默认标题，多轮历史读取能力就绪，问答产生的消息可持久化读回。

---

## 阶段 4：用户故事 2 - 查看自己的会话列表（优先级：P2）

**目标**：登录用户查看属于自己的会话列表，按创建时间倒序、分页，可进入任一会话。

**独立测试**：登录后查看会话列表，可独立验证：列表仅展示当前用户的会话，按时间倒序。

- [ ] T013 [US2] 在 `backend/app/services/session/session_crud.py` 中实现 `list_sessions(db, user_id, page, page_size)`：按 `WHERE user_id=:uid ORDER BY create_time DESC` 分页查询（`page_size` 默认取配置 `session_page_size`），返回 `(total, items)`（对应 FR-002/FR-009，data-model.md「会话列表」查询契约）。
- [ ] T014 [US2] 在 `backend/app/api/session.py` 中实现 `GET /api/session/list` 端点：依赖 `get_current_user`，解析查询参数 `page`（默认 1）、`page_size`（默认 20），调用 `list_sessions`，返回 200 `{total, items}`；无会话时返回 `items: []`、`total: 0`（contracts/session-api.md）。
- [ ] T015 [US2] 在 `backend/tests/unit/test_session_crud.py` 补充列表单元测试：`list_sessions` 仅返回当前用户自己的会话、按创建时间倒序、分页正确（含空列表返回 total=0）（见 research.md §6）。

**检查点**：用户故事 2 此刻可独立运行与验证——列表仅展示本人会话、按时间倒序、分页正确、空列表返回空数组。

---

## 阶段 5：用户故事 3 - 查看会话历史消息（优先级：P2）

**目标**：用户进入某会话，按时间顺序查看完整历史问答消息（含角色/内容/引用来源/意图标签），越权访问被拒绝。

**独立测试**：进入有问答记录的会话，可独立验证：历史消息按时间完整有序展示。

- [ ] T016 [US3] 在 `backend/app/services/session/message_query.py` 中实现 `list_messages(db, session_id, page, page_size)`：按 `WHERE session_id=:sid ORDER BY create_time ASC, id ASC` 分页查询（`page_size` 默认取配置 `message_page_size`、上限 `message_page_size_max`），返回 `(total, items)`（对应 FR-003/FR-009，data-model.md「历史消息」查询契约）。
- [ ] T017 [US3] 在 `backend/app/services/session/session_crud.py` 中实现 `get_session_detail(db, session_id, user_id)`：先调用 `get_owned_session` 做归属校验（非本人返回 None），再统计该会话 `message_count`，返回会话详情（对应 FR-004，data-model.md「会话详情归属」查询契约）。
- [ ] T018 [US3] 在 `backend/app/api/session.py` 中实现 `GET /api/session/{session_id}` 端点：依赖 `get_current_user`，调用 `get_session_detail`；本人返回 200 `{session_id, title, create_time, message_count}`，非本人/不存在返回 404 `{code: "session_not_found"}`（不泄露他人会话存在性，见 contracts/session-api.md）。
- [ ] T019 [US3] 在 `backend/app/api/message.py` 中实现 `GET /api/session/{session_id}/messages` 端点：定义 `router = APIRouter()`，依赖 `get_current_user`，先调用 `get_owned_session` 归属校验（非本人 404），再调用 `list_messages`，返回 200 `{total, items}`；空会话返回 `items: []`、`total: 0`（contracts/session-api.md）。并将该 router 注册到 `backend/app/main.py`。
- [ ] T020 [US3] 在 `backend/tests/unit/test_ownership.py` 编写单元测试：`get_owned_session` 对非本人会话返回 None、对本人会话返回会话对象、对不存在会话返回 None（数据隔离核心逻辑，见 research.md §6）。
- [ ] T021 [US3] 在 `backend/tests/integration/test_message_pagination.py` 编写集成测试：历史消息按时间正序返回、分页正确（`page_size` 上限 100 生效）、同秒并发写入的消息按 `(create_time, id)` 稳定排序不重复不遗漏、空会话返回空列表（见 research.md §3 分页策略、§6 测试策略）。

**检查点**：用户故事 3 此刻可独立运行与验证——历史消息按时间有序返回、越权访问返回 404。

---

## 阶段 6：打磨与横切关注点（Polish & Cross-Cutting Concerns）

收尾、跨故事一致性与端到端验证。此阶段任务不加用户故事标签。

- [ ] T022 在 `backend/tests/integration/test_session_flow.py` 补充跨用户隔离集成测试：使用用户 B 的凭据访问用户 A 的会话详情（`GET /api/session/{id}`）与消息（`GET /api/session/{id}/messages`），均返回 404 `session_not_found`（对应 SC-005 跨用户访问 100% 拒绝，见 quickstart.md 场景 3）。
- [ ] T023 在 `backend/app/config.py` 对应的 `.env.example` 中补充会话模块配置项模板与中文注释（`SESSION_PAGE_SIZE`、`MESSAGE_PAGE_SIZE`、`MESSAGE_PAGE_SIZE_MAX`、`DEFAULT_SESSION_TITLE`、`SESSION_TITLE_SUMMARY_LEN`、`CONTEXT_TURNS`），不提交真实密钥。
- [ ] T024 运行全量测试：`cd backend && pytest tests/ -v`，确保 unit + integration 全部通过（覆盖创建/列表/详情、数据隔离越权拒绝、分页、与 001 消息写入联动，见 quickstart.md「测试命令」）。
- [ ] T025 端到端手工验证 quickstart.md 全部 4 个场景（场景 1 创建→问答→详情可见、场景 2 会话列表、场景 3 数据隔离、场景 4 边界情况），确认 SC-001~SC-006 可度量结果达标。

---

## 依赖关系与执行顺序

- **顺序依赖**：Phase 1 → Phase 2 → 各用户故事 → Phase 6。用户故事按优先级顺序实施（P1 先于 P2）。
- **Foundational 阻塞点**：T004（模型）、T005（schema）、T006（归属校验）是所有故事的共同前置；未完成前不得开始任何故事阶段。
- **故事内部依赖**：每个故事内先实现服务层（CRUD/查询），再实现端点，最后补测试。例如 US1 中 T007/T008（服务）→ T009（端点）→ T011/T012（测试）。
- **跨故事依赖**：
  - US3 的 `GET /api/session/{id}`（T018）与 `get_owned_session`（T006）、`get_session_detail`（T017）强依赖；消息分页（T016）依赖 T004 的 `Message` 模型。
  - US2 的列表（T013）依赖 T004 的 `Session` 模型与 `(user_id, create_time DESC)` 索引。
  - US1 的历史读取（T010）依赖 T004 的 `Message` 模型。
- **上游特性依赖**：所有受保护端点依赖 003 的 `get_current_user`（`backend/app/api/deps.py`）；消息「写入」由 001 问答链路完成，004 仅提供存储与读取（见 research.md §4「与 001-RAG 的读写联动」）。
- **配置依赖**：T002 的配置项在 T007/T010/T013/T016 中被读取，需先行完成。

## 并行机会

- **Setup 阶段**：T001（包骨架）、T002（配置）、T003（测试夹具）互不依赖，可并行。
- **Foundational 阶段**：T004（模型）与 T005（schema）可并行；T006 依赖 T004，须在其后。
- **跨用户故事并行**：US1、US2、US3 在 Phase 2 检查点后就绪后可并行实施（不同文件、不同端点），建议由不同开发者/团队并行推进；三个故事共享的 `session_crud.py`（T007/T008/T013/T017）需协调改动顺序，避免冲突。
- **测试与实现并行**：每个故事的服务层/端点完成后，其单元测试与集成测试可与下一个故事的服务层实现并行推进。

## 实施策略

- **MVP 优先**：MVP = 用户故事 1（创建会话并开始问答，6 个任务）。先交付「创建会话 + 默认标题 + 历史读取 + 持久化联动」，即可让 001 问答链路在会话上下文中跑通，是 RAG 闭环的最小可用单元。
- **增量交付**：MVP 之后依次交付 US2（会话列表）与 US3（历史消息详情），每完成一个故事即形成可独立验证的增量；最后以 Phase 6 完成数据隔离集成验证、配置模板与端到端验收。
- **并行团队策略**：若多人协作，可让一名开发者负责 Setup+Foundational（T001~T006），随后 US1、US2、US3 分别交由不同开发者并行；跨用户隔离与端到端验证（Phase 6）由集成负责人收敛，确保 SC-005/SC-006 合规达标。
