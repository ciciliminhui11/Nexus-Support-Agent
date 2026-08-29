# 实施计划：用户反馈

**分支**：`005-user-feedback` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/005-user-feedback/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现用户对 AI 回答的反馈能力：对会话中的 AI 回答点赞/踩（二选一）+ 可选文字说明（≤200 字可配置）→ 反馈持久化（关联消息、提交者、时间）→ 重复提交覆盖更新（最后为准）→ 仅 AI 回答可反馈（用户消息/不存在消息拒绝）→ 数据隔离（他人会话消息拒绝）→ 反馈独立存储供后续质量统计。

技术方案遵循宪法：反馈仅登录用户可提交（003 鉴权），数据仅服务端读写，数据隔离为合规硬性边界。Feedback 实体独立于会话/消息存储（消息删除后反馈保留，供统计）。管理后台统计为加分项不在本特性范围，本特性保证数据基础完整（SC-005）。

## 技术上下文

**语言/版本**：Python 3.11（FastAPI + uvicorn）

**主要依赖**：fastapi、sqlalchemy、pymysql、pydantic-settings、pytest

**存储**：MySQL 8.0（Feedback 表）

**测试**：pytest（unit + integration；覆盖提交/更新覆盖/校验/隔离/长度边界）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端 REST API）

**性能目标**：反馈提交 2 秒内完成（SC-001）

**约束**：仅登录用户；仅 AI 回答可反馈；必须选赞/踩之一；文字 ≤200 字（可配置）；重复提交覆盖更新；越权拒绝；反馈独立存储、消息删除后保留

**规模/范围**：管理后台反馈统计为加分项，不在本特性范围；不支持匿名反馈；一条消息同一提交者一条反馈记录

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 安全与合规：数据查询必须鉴权授权 | FR-001/FR-008 仅登录用户可提交；FR-009 越权反馈拒绝（归属校验）；反馈数据仅供鉴权查询 | ✅ 通过 |
| 原则三：AI 能力仅在服务端执行 | 反馈数据仅服务端读写，前端经 REST 交互 | ✅ 通过 |
| 开发流程质量门槛 | 关键链路集成测试（提交→覆盖→查询；隔离与校验边界） | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/005-user-feedback/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

后端结构沿用 001 规划，本特性新增反馈模块。

```text
backend/
├── app/
│   ├── api/
│   │   └── feedback.py        # POST /api/message/{id}/feedback、GET /api/message/{id}/feedback
│   ├── db/
│   │   └── models.py          # 追加 Feedback 模型
│   ├── schemas/
│   │   └── feedback.py        # 提交/查询 Pydantic 结构
│   ├── services/
│   │   ├── feedback/
│   │   │   ├── __init__.py
│   │   │   ├── submit.py      # 提交业务：消息归属+角色校验、upsert、长度/类型校验
│   │   │   └── query.py       # 按消息查询反馈（数据基础，供统计）
│   │   └── ...
│   └── ...
└── tests/
    ├── unit/
    │   ├── test_feedback_validation.py  # 类型/长度/角色/不存在校验
    │   └── test_feedback_upsert.py      # 覆盖更新
    └── integration/
        └── test_feedback_flow.py        # 提交→覆盖→隔离→查询
```

**结构决策**：沿用后端模块化结构。反馈提交业务（校验 + upsert）收敛在 `services/feedback/submit.py`；消息归属/角色校验复用 004 的会话归属逻辑（先定位消息 → 断言会话归属 → 断言 role='ai'），保证数据隔离与「仅 AI 可反馈」无遗漏。反馈独立表存储，与消息删除解耦。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
