# 实施计划：会话与消息

**分支**：`004-session-messages` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/004-session-messages/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现会话与消息的读写能力：创建会话（默认标题，归属当前用户，立即可问答）→ 查看自己的会话列表（按创建时间倒序、分页）→ 查看会话历史消息（按时间顺序、分页，含角色/内容/引用来源/意图标签）→ 数据隔离（用户仅可访问自己的会话，越权拒绝）。同时为 001-RAG 提供消息持久化与最近 N 轮历史读取的存储层。

技术方案遵循宪法：会话与消息归属用户，数据隔离为合规硬性边界；服务端唯一数据源（前端不直接访问）；JWT 鉴权由 003 提供，本特性经 `api/deps.py` 复用。Session / Message 实体定义与 001 数据模型保持一致，本特性负责其 CRUD 与查询。

## 技术上下文

**语言/版本**：Python 3.14（FastAPI + uvicorn）

**主要依赖**：fastapi、sqlalchemy、pymysql、pydantic-settings、pytest

**存储**：MySQL 8.0（Session、Message 表）

**测试**：pytest（unit + integration；覆盖创建/列表/详情、数据隔离越权拒绝、分页、与 001 消息写入联动）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端 REST API）

**性能目标**：会话创建 2 秒内完成（SC-001）；会话列表与消息详情查询（带索引分页）响应 <200ms

**约束**：会话归属登录用户；列表仅展示自己的会话、按时间倒序；历史消息按时间顺序返回；越权访问拒绝；消息量大分页承载；v1 不含删除/重命名会话（假设约定，后续增强）

**规模/范围**：单会话消息量不设上限（分页承载）；默认标题「新会话」或首条消息截断摘要；标题编辑为后续增强

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 安全与合规：数据查询必须鉴权授权 | FR-004 数据隔离：会话列表/详情均经 `get_current_user` 鉴权，并按 owner 过滤/校验；跨用户访问 100% 拒绝（SC-005） | ✅ 通过 |
| 原则三：AI 能力仅在服务端执行 | 会话与消息数据仅由服务端读写，前端经 REST 交互 | ✅ 通过 |
| 开发流程质量门槛 | 关键链路集成测试（问答→持久化→详情可见）；引用来源为空的兜底消息展示兼容 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/004-session-messages/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

后端结构沿用 001 规划，本特性新增会话管理模块。

```text
backend/
├── app/
│   ├── api/
│   │   ├── session.py        # POST /api/session、GET /api/session/list、GET /api/session/{id}
│   │   └── message.py        # GET /api/session/{id}/messages（历史消息分页）
│   ├── db/
│   │   └── models.py         # Session / Message 模型（与 001 共用定义）
│   ├── schemas/
│   │   └── session.py        # 创建/列表/详情 Pydantic 结构
│   ├── services/
│   │   ├── session/
│   │   │   ├── __init__.py
│   │   │   ├── session_crud.py   # 创建（默认标题）/ 列表（owner+倒序）/ 归属校验
│   │   │   └── message_query.py  # 历史消息按时间分页查询
│   │   └── history.py        # 读取最近 N 轮历史（供 001 复用，见 001 plan）
│   └── ...
└── tests/
    ├── unit/
    │   ├── test_session_crud.py      # 创建/列表/标题默认值
    │   └── test_ownership.py         # 数据隔离校验
    └── integration/
        ├── test_session_flow.py      # 创建→问答→详情可见 联动
        └── test_message_pagination.py
```

**结构决策**：沿用后端模块化结构。会话归属校验收敛在 `services/session/session_crud.py`（列表带 owner 过滤、详情带归属断言），所有会话端点复用同一校验路径，保证数据隔离无遗漏。`services/history.py` 的最近 N 轮读取逻辑与 001 的 history 模块为同一能力（004 提供存储层查询，001 调用组装上下文），命名对齐避免重复实现。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
