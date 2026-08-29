# 任务清单：用户鉴权

**特性分支**：`003-user-auth` | **输入**：[spec.md](spec.md)、[plan.md](plan.md)、[data-model.md](data-model.md)、[contracts/auth-api.md](contracts/auth-api.md)、[research.md](research.md)、[quickstart.md](quickstart.md)

> 说明：任务按用户故事组织，Setup/Foundational 阶段不加故事标签；用户故事阶段任务带 [USx] 标签。所有任务可独立实现、独立验证。

---

## 阶段 1：准备阶段（Setup）

项目初始化与基础结构（不含用户故事逻辑）。

- [ ] T001 [P] 创建 `backend/requirements.txt`，声明依赖：fastapi、uvicorn[standard]、sqlalchemy、pymysql、passlib[bcrypt]、pyjwt、pydantic-settings、python-dotenv、pytest、httpx（FastAPI TestClient 依赖），版本对齐 plan.md「技术上下文」。
- [ ] T002 [P] 创建 `backend/.env.example`，按 contracts/auth-api.md「配置契约」列出环境变量模板：`JWT_SECRET`（≥32 字节占位符）、`jwt_expire_hours=24`、`min_password_length=8`、`phone_regex=^1[3-9]\d{9}$`、`login_fail_threshold=5`、`login_lock_max_seconds=300`、`daily_quota_limit=100`、`ADMIN_ACCOUNT`（占位）、MySQL 连接串占位；真实密钥不提交仓库。
- [ ] T003 [P] 创建 `backend/app/__init__.py` 与 `backend/app/main.py`：初始化 FastAPI 应用实例（标题「Nexus-Support-Agent」），预留 `lifespan` 钩子占位与 `/health` 健康检查；暴露 `app` 对象供 `uvicorn app.main:app` 入口使用。
- [ ] T004 [P] 创建 `backend/app/core/__init__.py` 与 `backend/app/core/config.py`：用 pydantic-settings 定义 `Settings` 类，读取 contracts/auth-api.md「配置契约」全部配置项（JWT_SECRET、jwt_expire_hours、min_password_length、phone_regex、login_fail_threshold、login_lock_max_seconds、daily_quota_limit、ADMIN_ACCOUNT、数据库连接），并提供单例 `get_settings()` 供各模块复用。
- [ ] T005 创建 `backend/app/db/__init__.py`、`backend/app/db/base.py`（SQLAlchemy `DeclarativeBase` 基类）与 `backend/app/db/session.py`（`engine` + `SessionLocal` + `get_db` 依赖生成器，连接串取自 `Settings`）。
- [ ] T006 [P] 创建 `backend/pytest.ini`（配置测试根路径与 `testpaths=tests`）与 `backend/tests/__init__.py`、`backend/tests/conftest.py`：提供测试数据库 fixture（本地可用 SQLite 内存库，连接配置从环境变量读取）与应用测试客户端 fixture（FastAPI `TestClient`/httpx），供后续集成测试复用。

---

## 阶段 2：基础阶段（Foundational）

阻塞所有用户故事的前置能力（模型、安全原语、鉴权依赖、校验结构）。

- [ ] T007 [P] 在 `backend/app/db/models.py` 中定义 `User` 模型：字段按 data-model.md §1（`id` BIGINT PK AUTO_INCREMENT、`account_identifier` VARCHAR(100) NOT NULL UNIQUE、`account_type` ENUM('phone','email')、`password_hash` VARCHAR(255)、`role` ENUM('user','admin') DEFAULT 'user'、`created_at` DATETIME DEFAULT CURRENT_TIMESTAMP），并声明 `UNIQUE(account_identifier)` 约束（FR-002）。
- [ ] T008 [P] 在 `backend/app/db/models.py` 中定义 `UserQuotaDaily` 模型：字段按 data-model.md §2（`id` BIGINT PK、`user_id` BIGINT FK→user.id、`stat_date` DATE、`count` INT DEFAULT 0），并声明 `UNIQUE(user_id, stat_date)` 约束；计数递增由 001 负责，本特性仅查询。
- [ ] T009 在 `backend/app/core/security.py` 中实现密码哈希函数 `hash_password` / `verify_password`：使用 passlib bcrypt（rounds=12、每用户随机盐），符合 research §1 与 FR-003（不可逆加盐哈希，禁止明文）。
- [ ] T010 在 `backend/app/core/security.py` 中实现 JWT 签发与解码：`create_access_token(sub, role, account_type)`（HS256，载荷含 sub/role/account_type/iat/exp，`exp` 由 `jwt_expire_hours` 计算）与 `decode_token`（验签 + 校验 `exp` 过期，非法/过期抛出），符合 research §2 与 FR-004/FR-005。
- [ ] T011 [P] 创建 `backend/app/core/login_guard.py`：实现连续登录失败防护，按「账号标识 + 来源 IP」维度记录 `fail_count` 与 `locked_until`，失败满 `login_fail_threshold`（默认 5）后触发递增延迟 `min(2^fail_count, login_lock_max_seconds)` 秒，登录成功清零，符合 research §3 与 FR-010。
- [ ] T012 [P] 创建 `backend/app/schemas/__init__.py` 与 `backend/app/schemas/auth.py`：定义 Pydantic 结构 `RegisterRequest`、`LoginRequest`、`RegisterResponse`、`LoginResponse`、`UserInfo`、`QuotaInfo`、`MeResponse`，字段与 contracts/auth-api.md 各端点请求/响应体一致。
- [ ] T013 [P] 创建 `backend/app/services/__init__.py` 与 `backend/app/services/auth/__init__.py` 空模块，建立服务包结构。
- [ ] T014 创建 `backend/app/api/__init__.py` 与 `backend/app/api/deps.py`：实现 `get_current_user` 依赖——从 `Authorization` 头取 Bearer 令牌，缺失/非 Bearer → 401 `unauthorized`；调用 `security.decode_token` 校验签名与过期；按 `sub` 查询 `User` 存在性；通过后注入当前 User 对象，符合 contracts/auth-api.md「鉴权依赖契约」。
- [ ] T015 创建 `backend/app/core/roles.py`：定义角色常量（`USER='user'`、`ADMIN='admin'`）与 `require_admin` 依赖（复用 `get_current_user`，当前用户 role 非 admin → 403 `forbidden`），符合 research §7 与 contracts/auth-api.md 管理员鉴权契约。

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 注册账号（优先级：P1）

**目标**：交付注册能力——新用户以手机号或邮箱（二选一）+ 密码注册账号，注册成功后凭据可用于登录。

**独立测试**：提交合法且唯一的手机号/邮箱 + 密码完成注册，可独立验证：注册成功、凭据可登录、重复注册被拒绝。

- [ ] T016 [US1] 创建 `backend/app/services/auth/registration.py`：实现注册业务 `register(...)`——按 `account_type` 用配置中的 `phone_regex`/邮箱正则校验 `account_identifier` 格式（FR-001/FR-002），校验密码长度 ≥ `min_password_length` 且非空白（FR-009），预查标识唯一性，调用 `security.hash_password` 生成哈希后写入 `User` 记录，返回新用户信息。
- [ ] T017 [US1] 在 `backend/app/api/auth.py` 中实现 `POST /api/auth/register`：接收 `RegisterRequest`，调用 registration 服务；成功返回 201（`RegisterResponse`）；标识格式非法 → 400 `invalid_identifier`、标识已占用 → 409 `identifier_taken`、密码过短 → 400 `password_too_short`，错误码/消息严格按 contracts/auth-api.md。
- [ ] T018 [US1] 在 `backend/app/main.py` 中创建并注册 auth 路由：`auth_router = APIRouter(prefix="/api/auth", tags=["auth"])` 并 `app.include_router(auth_router)`，使 register 端点可访问。

**检查点**：注册端点可独立运行，可用 curl 验证注册成功、重复注册 409、非法格式/短密码被拒。

---

## 阶段 4：用户故事 2 - 登录并访问受保护功能（优先级：P1）

**目标**：交付登录与令牌签发能力——凭注册凭据登录签发 JWT，受保护接口凭有效令牌放行、无效/过期令牌拒绝。

**独立测试**：使用已注册凭据登录，可独立验证：登录成功签发令牌、持令牌可访问受保护功能、错误凭据被拒绝。

- [ ] T019 [US2] 创建 `backend/app/services/auth/login.py`：实现登录业务 `login(...)`——先经 `login_guard` 判断是否处于递增延迟中（触发则返回 `too_many_attempts`）；查询 `User`，账号不存在与密码错误统一返回 `invalid_credentials`（FR-006/防枚举）；校验通过后调用 `security.create_access_token` 签发 JWT 并清零 `login_guard` 失败计数，返回令牌与用户摘要。
- [ ] T020 [US2] 在 `backend/app/api/auth.py` 中实现 `POST /api/auth/login`：接收 `LoginRequest`，调用 login 服务；成功 200（`LoginResponse`）；账号不存在/密码错误 → 401 `invalid_credentials`、连续失败触发延迟 → 429 `too_many_attempts`（含 `retry_after`），错误码/消息按 contracts/auth-api.md。
- [ ] T021 [US2] 在 `backend/app/api/auth.py` 中实现受保护端点 `GET /api/auth/me`（依赖 `get_current_user`），先返回当前用户基本信息（user_id、account_identifier、account_type、role、created_at），用于验证 FR-005：持有效令牌放行、令牌缺失/无效/过期 → 401 `unauthorized`（配额字段在用户故事 3 补充）。

**检查点**：登录端点可独立运行，可用 curl 验证登录成功签发令牌、错误凭据 401 统一提示、持令牌访问 `me` 放行、无效/过期令牌 401。

---

## 阶段 5：用户故事 3 - 查看账号信息与每日提问配额（优先级：P3）

**目标**：交付账号信息与每日提问配额查询能力——已登录用户查看自己的账号信息及当日已用/剩余提问次数。

**独立测试**：登录后查看账号信息与配额，可独立验证：信息正确展示、配额计数与问答行为一致。

- [ ] T022 [US3] 创建 `backend/app/services/auth/quota.py`：实现每日配额查询 `get_quota(user_id)`——查询 `UserQuotaDaily` 当日（配置时区自然日）记录，`used = count`、`limit = daily_quota_limit`、`remaining = max(0, limit - count)`，无记录时 `count=0`，符合 FR-008 与 data-model.md §2 查询契约。
- [ ] T023 [US3] 在 `backend/app/api/auth.py` 中扩展 `GET /api/auth/me`：在账号信息基础上追加 `quota` 字段（limit/used/remaining），调用 quota 服务，响应结构与 contracts/auth-api.md `GET /api/auth/me` 一致。

**检查点**：`me` 端点可独立运行，登录后可查看账号信息与配额；配合 001 问答链路可验证 `used` 与提问次数一致、跨日重置。

---

## 阶段 6：打磨与横切关注点

跨故事的测试与运维收尾（不加故事标签）。

- [ ] T024 [P] 创建 `backend/tests/unit/test_password_hash.py`：验证密码哈希不可逆、加盐（同密码两次哈希结果不同）、`verify_password` 正确性（research §8）。
- [ ] T025 [P] 创建 `backend/tests/unit/test_jwt.py`：验证 JWT 签发载荷（sub/role/account_type/exp）、过期令牌拒绝、无效签名拒绝（FR-005）。
- [ ] T026 [P] 创建 `backend/tests/unit/test_validation.py`：验证手机号/邮箱格式校验、密码长度与空/空白校验规则（FR-002/FR-009）。
- [ ] T027 [P] 创建 `backend/tests/unit/test_login_guard.py`：验证连续失败递增延迟触发、`locked_until` 计算、登录成功清零（FR-010）。
- [ ] T028 [P] 创建 `backend/tests/integration/test_register_login.py`：覆盖注册→登录→受保护访问全链路、登录失败防枚举（统一提示）、并发登录互不干扰（quickstart 场景 1/2）。
- [ ] T029 [P] 创建 `backend/tests/integration/test_quota_linking.py`：构造提问使 `UserQuotaDaily.count` 递增后查询 `me`，验证 `used`/`remaining` 一致及跨日重置（quickstart 场景 3、SC-007）。
- [ ] T030 在 `backend/app/main.py` 的 `lifespan` 中实现启动逻辑：`from app.db import models` 后调用 `Base.metadata.create_all` 自动建表，并按 `ADMIN_ACCOUNT` 配置预置管理员账号为 `role='admin'`（research §7）。
- [ ] T031 按 quickstart.md 运行端到端验证（注册→登录→me、校验与防枚举、配额联动、管理员角色场景），并执行 `cd backend && pytest tests/ -v` 确认全部通过，核对 SC-001~SC-007 成功标准。

---

## 依赖关系与执行顺序

- **Setup（T001–T006）**：先完成，是后续一切的前置。T001/T002/T003/T004/T006 相互独立可并行；T005 依赖 T004（连接串取自 Settings）。
- **Foundational（T007–T015）**：T007/T008/T011/T012/T013 相互独立可并行；T009→T010 同文件顺序执行；T014 依赖 T009/T010 + T007/T008 + T005；T015 依赖 T014。
- **用户故事**：US1（T016–T018）、US2（T019–T021）、US3（T022–T023）均依赖 Foundational 完成。US1 与 US2 同为 P1，逻辑相互独立（登录仅依赖 User 模型与 security，不依赖注册服务），可并行；US3 的 `me` 配额扩展依赖 US2 建立的 `me` 端点骨架。
- **Polish（T024–T031）**：依赖全部故事完成；T024–T029 相互独立可并行；T030/T031 最后执行。

## 并行机会

- Setup 内：T001、T002、T003、T004、T006 可并行。
- Foundational 内：T007、T008、T011、T012、T013 可与 T009/T010 并行推进（不同文件、无交叉依赖）。
- 故事间：US1 与 US2 可由两个开发者并行实施（同为 P1、互不阻塞）。
- Polish 内：T024–T029 六个测试文件相互独立，可并行编写。

## 实施策略

- **MVP 优先**：先交付用户故事 1（注册）作为最小可用产品，注册是账号体系与所有业务的前提（P1）。
- **增量交付**：MVP（US1）→ 登录与受保护访问（US2）→ 账号信息与配额（US3），每阶段均可独立运行与验证，形成「注册→登录→me」的完整可用闭环。
- **并行团队策略**：Foundational 完成后，一名开发者推进 US1，另一名并行推进 US2；US2 完成后由同一人延伸 US3；测试与运维收尾（T024–T031）在功能就绪后由测试/后端并行补齐。
