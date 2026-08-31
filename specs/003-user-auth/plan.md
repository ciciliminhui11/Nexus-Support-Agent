# 实施计划：用户鉴权

**分支**：`003-user-auth` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/003-user-auth/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现用户鉴权基础：注册（手机号/邮箱二选一 + 密码，格式与唯一性校验，密码加盐哈希存储）→ 登录（统一失败提示防枚举，连续失败递增延迟防护）→ JWT 签发（默认 24h 有效期）→ 受保护资源鉴权依赖（校验令牌有效性与过期，全站复用）→ 账号信息与每日配额查询（联动 001 配额计数）。

技术方案遵循宪法安全与合规要求：密码以不可逆加盐哈希（bcrypt）存储、JWT 鉴权、密钥仅存服务端环境变量（`.env.example` 提供模板）、角色体系（普通用户/管理员）预置配置供 002 等受控功能使用。本特性提供的鉴权依赖是 001/002/004/005 全部受保护接口的统一入口。

## 技术上下文

**语言/版本**：Python 3.14（FastAPI + uvicorn）

**主要依赖**：fastapi、sqlalchemy、pymysql、passlib[bcrypt]（密码哈希）、pyjwt（JWT 签发/校验）、pydantic-settings、python-dotenv、pytest

**存储**：MySQL 8.0（User 表、UserQuotaDaily 计数表）

**测试**：pytest（unit + integration；覆盖注册校验、登录防枚举、JWT 校验、配额联动、并发登录）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端 REST API）

**性能目标**：注册 30 秒内完成（SC-001，无人工审核）；鉴权校验附加延迟 <50ms（令牌本地验签，无外部依赖）

**约束**：账号标识二选一（手机号/邮箱）；手机号默认中国大陆 11 位可配置；密码最小 8 位可配置；JWT 有效期默认 24h；登录失败返回统一提示；连续失败递增延迟防护；令牌无效/过期拒绝访问；密码不可逆哈希存储；角色仅普通用户/管理员两档

**规模/范围**：v1 无令牌吊销服务（登出由客户端丢弃）；无验证码强制；无并发会话限制；生产密钥签发与轮换策略留文档说明

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 安全与合规：JWT 鉴权、受保护接口校验 | FR-004/FR-005 JWT 签发与校验；`core/security.py` 提供全局鉴权依赖；无效/过期令牌拒绝访问 | ✅ 通过 |
| 安全与合规：密码哈希存储 | FR-003 bcrypt 加盐哈希，禁止明文落库 | ✅ 通过 |
| 安全与合规：密钥仅存服务端 | JWT 密钥、密码算法参数仅存环境变量；`.env.example` 提供模板，真实密钥不提交仓库 | ✅ 通过 |
| 原则五：每日配额硬性约束 | FR-008 UserQuotaDaily 按自然日计数，联动 001 FR-002（默认 100 次/天），跨日自动重置 | ✅ 通过 |
| 原则二：禁止编造（间接） | 鉴权是防未授权访问的安全基础，与问答链路的可信边界一致 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/003-user-auth/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

后端结构沿用 001 规划，本特性新增鉴权模块。

```text
backend/
├── app/
│   ├── api/
│   │   ├── auth.py            # POST /api/auth/register、POST /api/auth/login、GET /api/auth/me
│   │   └── deps.py            # get_current_user 鉴权依赖（全站复用，供 001/002/004/005 使用）
│   ├── core/
│   │   ├── security.py        # 密码哈希/校验（bcrypt）、JWT 签发/解码、令牌过期校验
│   │   ├── login_guard.py     # 连续登录失败递增延迟防护（账号+IP 维度）
│   │   └── roles.py           # 角色常量与权限校验依赖（admin 专属接口用）
│   ├── db/
│   │   └── models.py          # 追加 User 模型
│   ├── schemas/
│   │   └── auth.py            # 注册/登录/账号信息/配额 Pydantic 结构
│   ├── services/
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── registration.py  # 注册业务：格式校验 + 唯一性 + 哈希入库
│   │   │   ├── login.py         # 登录业务：统一失败提示 + 失败防护
│   │   │   └── quota.py         # 每日配额查询（已用/剩余），联动 001 计数
│   └── ...
└── tests/
    ├── unit/
    │   ├── test_password_hash.py  # 哈希不可逆/加盐
    │   ├── test_jwt.py            # 签发/过期/无效签名
    │   ├── test_validation.py     # 手机号/邮箱/密码规则
    │   └── test_login_guard.py    # 递增延迟
    └── integration/
        ├── test_register_login.py
        └── test_quota_linking.py  # 配额与问答联动
```

**结构决策**：沿用后端模块化结构。鉴权核心收敛到 `core/security.py`（哈希 + JWT），全局鉴权依赖在 `api/deps.py`（所有受保护路由统一引用），登录防暴力破解独立 `core/login_guard.py`。配额逻辑 `services/auth/quota.py` 与 001 的 `validation.py` 共享同一 UserQuotaDaily 计数表（001 负责递增，003 负责查询展示）。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
