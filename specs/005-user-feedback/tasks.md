# 任务清单：用户反馈

**分支**：`005-user-feedback` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md) | **计划**：[plan.md](plan.md)

**输入**：来自 `/specs/005-user-feedback/` 的 plan.md、spec.md、data-model.md、contracts/feedback-api.md、research.md、quickstart.md。

**功能概述**：用户对会话中的 AI 回答点赞/踩（二选一）+ 可选文字说明（≤200 字可配置）→ 反馈持久化（关联消息、提交者、时间）→ 重复提交覆盖更新（最后为准）→ 仅 AI 回答可反馈 → 数据隔离（他人会话消息拒绝）→ 反馈独立存储供后续质量统计。管理后台统计为加分项，不在本特性范围。

---

## Phase 1：准备阶段（Setup）

项目初始化与基础结构（不加用户故事标签）。

- [ ] T001 [P] 创建反馈服务包：新建目录 `backend/app/services/feedback/` 并写入空的 `backend/app/services/feedback/__init__.py`；若 `backend/app/services/__init__.py` 尚不存在则一并创建，使 `feedback` 成为可导入的 Python 包。
- [ ] T002 [P] 新增文字反馈长度配置：在配置模块 `backend/app/core/config.py`（pydantic-settings 的 Settings，若既有 settings 模块路径不同则沿用既有模块）中新增配置项 `feedback_max_length`，默认值 `200`；同时在 `backend/.env.example` 中追加 `feedback_max_length=200` 模板条目（对应 FR-007「可配置」）。

---

## Phase 2：基础阶段（Foundational）

阻塞所有用户故事的前置任务（不加用户故事标签）。

- [ ] T003 在 `backend/app/db/models.py` 中追加 Feedback ORM 模型（SQLAlchemy），字段：`id`（BIGINT，PK，AUTO_INCREMENT）、`message_id`（BIGINT，NOT NULL，FK→message.id，**不启用 ON DELETE CASCADE**）、`user_id`（BIGINT，NOT NULL，FK→user.id）、`feedback_type`（ENUM('like','dislike')，NOT NULL）、`feedback_text`（VARCHAR(500)，NULL）、`create_time`（DATETIME，NOT NULL，默认 CURRENT_TIMESTAMP）、`update_time`（DATETIME，NOT NULL，DEFAULT CURRENT_TIMESTAMP ON UPDATE）；并添加唯一约束 `UNIQUE(message_id, user_id)`。
- [ ] T004 [P] 在 `backend/app/schemas/feedback.py` 中定义 Pydantic 结构：`FeedbackSubmitRequest`（`feedback_type: Literal['like','dislike']` 必填、`feedback_text: str | None = None` 可选）、`FeedbackSubmitResponse`（message_id、feedback_type、feedback_text、updated_at）、`FeedbackItem`（user_id、feedback_type、feedback_text、updated_at）、`FeedbackQueryResponse`（message_id、mine: FeedbackItem | None、all: list[FeedbackItem]）。
- [ ] T005 [P] 搭建测试基础设施：若 `backend/tests/conftest.py` 尚不存在则创建，提供共享夹具——测试数据库 session、FastAPI TestClient、已鉴权用户夹具（模拟 `app/api/deps.py` 的 `get_current_user` 注入当前用户），供后续反馈单测/集成测试复用。

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 对 AI 回答点赞或踩（优先级：P1）

**目标**：用户在会话中看到一条 AI 回答后，可对其点赞或踩，反馈立即记录、与消息正确关联、数据可查询。

**独立测试**：对一条 AI 回答提交点赞（或踩），可独立验证：反馈成功记录、与消息正确关联、数据可查询。

**验收场景**：

1. 假如 用户已登录且会话中有一条 AI 回答，当 用户对其点赞，那么 反馈成功记录，类型为「点赞」并关联该消息。
2. 假如 用户对同一 AI 回答选择踩，当 用户提交踩，那么 反馈成功记录，类型为「踩」。
3. 假如 用户对一条用户消息（非 AI 回答）提交反馈，当 发起请求，那么 被拒绝并提示只能对 AI 回答反馈。

**实施任务**：

- [ ] T006 [US1] 在 `backend/app/services/feedback/submit.py` 中实现提交核心：按 message_id 查询消息（不存在抛 404 `message_not_found`）；断言消息 `role == 'ai'`（否则抛 400 `not_ai_message`）；通过后以 `feedback_type`（及可选 `feedback_text`）插入一条 Feedback 记录。
- [ ] T007 [P] [US1] 在 `backend/app/services/feedback/query.py` 中实现按消息查询：给定 message_id，返回当前用户对该消息的反馈（`mine`，无则 None）与该消息全部反馈（`all`）列表，供前端展示与统计基础（FR-005）。
- [ ] T008 [US1] 在 `backend/app/api/feedback.py` 中实现两个端点：`POST /api/message/{message_id}/feedback` 与 `GET /api/message/{message_id}/feedback`，均通过 `backend/app/api/deps.py` 的 `get_current_user` 鉴权依赖注入当前用户，分别调用 submit/query 服务，按契约返回 200/201 成功或 400/404/401 错误码。
- [ ] T009 [US1] 在 `backend/app/main.py` 中注册 feedback 路由（将 `backend/app/api/feedback.py` 的 router `include_router` 进应用）。

**检查点**：此时 US1 可独立运行与验证——对 AI 消息 POST 点赞/踩成功入库，GET 可查询到该反馈；对用户消息 POST 返回 400。

---

## 阶段 4：用户故事 2 - 附加文字反馈说明（优先级：P2）

**目标**：用户在对回答点赞/踩的同时，可选填写一段文字说明具体问题或满意之处，与类型一并持久化。

**独立测试**：提交点赞/踩时附带文字反馈，可独立验证：文字反馈与类型一并持久化、可查询。

**验收场景**：

1. 假如 用户对一条 AI 回答选择踩，当 同时填写文字说明并提交，那么 文字反馈与「踩」一并持久化关联到该消息。
2. 假如 用户提交的反馈既未选择赞也未选择踩，当 发起请求，那么 被拒绝并提示必须至少选择一种类型。
3. 假如 用户填写的文字反馈超过长度限制（默认 200 字），当 提交，那么 被拒绝并提示长度超限。

**实施任务**：

- [ ] T010 [US2] 在 `backend/app/services/feedback/submit.py` 中增加文字反馈校验与持久化：`feedback_text` 长度 ≤ `feedback_max_length`（从配置读取，默认 200），恰好 200 字通过、超过抛 400 `feedback_too_long`；纯空白文字视同未填写（置为 None），并将文字随类型一并写入（FR-007）。
- [ ] T011 [US2] 在 `backend/app/api/feedback.py` 中补齐校验错误码映射：`feedback_type` 缺失或非法时返回 400 `{"code": "invalid_feedback_type", "message": "必须选择点赞或踩"}`；文字超限返回 400 `{"code": "feedback_too_long", "message": "文字反馈不能超过 200 字"}`，确保与契约一致（FR-008）。

**检查点**：此时 US2 可独立运行与验证——POST 带文字反馈成功持久化且可查询；未选类型返回 400 `invalid_feedback_type`；文字超 200 字返回 400 `feedback_too_long`，恰好 200 字通过。

---

## 阶段 5：用户故事 3 - 修改或撤销自己的反馈（优先级：P3）

**目标**：用户对自己的反馈操作失误后，可再次提交以覆盖更新（如由「踩」改为「赞」，或撤销文字）；并保证他人会话消息不可反馈。

**独立测试**：先提交「踩」，再改为「赞」，可独立验证：该消息的反馈以最后一次提交为准。

**验收场景**：

1. 假如 用户已对某 AI 回答提交「踩」，当 再次对该回答提交「赞」，那么 反馈更新为「赞」，以最后一次为准。
2. 假如 用户对他人会话中的消息提交反馈，当 发起请求，那么 被拒绝访问（数据隔离）。

**实施任务**：

- [ ] T012 [US3] 在 `backend/app/services/feedback/submit.py` 中实现 upsert 覆盖更新：命中 `UNIQUE(message_id, user_id)` 时更新 `feedback_type` / `feedback_text` / `update_time`（以最后一次为准），未命中则插入新记录（FR-006）。
- [ ] T013 [US3] 在 `backend/app/services/feedback/submit.py` 中增加归属校验（数据隔离）：定位消息后查询其所属会话，断言 `session.user_id == current_user.id`，不满足返回 404 `message_not_found`（不泄露存在性）；将该校验插入到「存在性 → 归属 → 角色」链路中（FR-009，复用 004 的会话归属逻辑）。

**检查点**：此时 US3 可独立运行与验证——同一消息重复提交后 GET 查询返回最后一次的反馈；他人会话中的消息提交反馈返回 404。

---

## 阶段 6：打磨与横切关注点（Polish & Cross-Cutting Concerns）

不加用户故事标签。覆盖宪法「开发流程质量门槛」要求的关键链路集成测试与校验边界测试。

- [ ] T014 [P] 创建 `backend/tests/unit/test_feedback_validation.py`，覆盖：类型必填/非法枚举、文字长度边界（199/200/201）、对用户消息（role=user）拒绝、对不存在消息拒绝。
- [ ] T015 [P] 创建 `backend/tests/unit/test_feedback_upsert.py`，覆盖：同一 `(message_id, user_id)` 重复提交覆盖更新、以最后一次为准。
- [ ] T016 [P] 创建 `backend/tests/integration/test_feedback_flow.py`，覆盖端到端链路：提交 → 覆盖更新 → 越权隔离拒绝 → 按消息查询。
- [ ] T017 按 `specs/005-user-feedback/quickstart.md` 运行验证：`cd backend && pytest tests/ -v` 全部通过；执行 quickstart 中的 curl 场景（点赞/踩+文字、覆盖更新、校验与隔离），确认 SC-001~SC-006 满足。

---

## 依赖关系与执行顺序

- **Phase 1 → Phase 2**：Setup（T001、T002）先于 Foundational；Foundational 的 T003（模型）、T004（结构）、T005（测试夹具）阻塞所有用户故事。
- **用户故事**：US1 → US2 → US3 按优先级顺序依赖（同文件 `submit.py` 的增量增强），但查询/端点等独立文件可并行。
- **T006/T007（submit/query 服务）→ T008（api 端点）→ T009（路由注册）**：严格顺序。
- **T010（US2 长度校验）→ T012/T013（US3 upsert/归属）**：均修改 `submit.py`，须顺序实施。
- **Polish（T014~T016）**：依赖全部故事完成；T017 依赖 T014~T016。

## 并行机会

- Setup：T001 与 T002 可并行（不同文件）。
- Foundational：T003、T004、T005 可并行（不同文件）。
- US1：T006 与 T007 可并行（不同文件）；T008 待二者完成后实施。
- Polish：T014、T015、T016 可并行（不同测试文件）。
- 用户故事阶段在 Foundational 完成后，若多人协作，US1 完成后 US2 与 US3 的文档/测试准备可提前并行（但 `submit.py` 的改动需串行）。

## 实施策略

- **MVP 优先**：先交付 US1（对 AI 回答点赞/踩 + 查询），它是反馈能力的核心与 P1，即可形成可运行、可验证的最小闭环；随后增量叠加 US2（文字反馈）、US3（覆盖更新 + 数据隔离）。
- **增量交付**：每个用户故事阶段末尾都有「检查点」，保证每个故事可独立运行与验证；反馈存储、校验、查询能力随故事逐层完善，无需一次性全量实现。
- **并行团队策略**：单开发者按 T001→T017 顺序推进；多人协作时，Foundational 完成后可将 US1 的 submit/query 拆分并行，US1 联调通过后 US2/US3 串行在 `submit.py` 上推进，同时另一人可提前编写 Polish 阶段的测试文件（T014~T016）。
- **测试策略**：宪法质量门槛要求关键链路集成测试（提交→覆盖→查询，隔离与校验边界）；单元测试覆盖类型/长度/角色/不存在校验边界。测试文件集中在 Polish 阶段统一补齐（对应 plan.md 的 `tests/unit/*`、`tests/integration/*`）。
