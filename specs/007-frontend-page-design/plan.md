# 实施计划：前端页面设计

**分支**：`007-frontend-page-design` | **日期**：2026-08-29（v2：React 选型） | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/007-frontend-page-design/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性交付 AI 智能客服系统的完整前端页面（企业专业浅色风），覆盖用户端（注册/登录、会话列表与历史、智能问答主界面、回答反馈）与管理端（知识库管理：上传 .txt/.md/.pdf、解析状态流转、文档增删改查、列表搜索）。

技术方案（用户指定 **React + TypeScript**，前端流式/渲染/状态一律**不自研**，仅 RAG 链路在后端保留自研）：Vite + React 18 + TS 5，**Ant Design 5**（ConfigProvider token 定制企业专业浅色风，表单/上传/表格/弹窗开箱即用），**TanStack Query**（服务端数据缓存/轮询/失效）+ **Zustand**（登录态等全局客户端状态），React Router v7 守卫 + axios 401 拦截。核心**流式问答体验**用 **@microsoft/fetch-event-source** 消费 `POST /api/chat/stream`（兼容 `data/meta/finish/error` 协议，AbortController 实现停止，解析零自研），AI 回答用 **Streamdown** 流式渲染（内置净化 + Shiki/KaTeX/Mermaid）。前端**不调用**任何大模型/向量检索（宪法：AI 能力仅在服务端）。登录态 v1 按 003 契约存 sessionStorage（收敛于 `authTokenStore` 抽象），生产硬化升级 httpOnly Cookie + 刷新令牌。测试：Vitest + React Testing Library + Playwright E2E（本地 mock SSE）覆盖全部验收场景。

## 技术上下文

**语言/版本**：TypeScript 5 + React 18（函数组件 + hooks）

**主要依赖**：react、react-dom、react-router-dom（v7）、antd（v5）、@tanstack/react-query、zustand、@microsoft/fetch-event-source、streamdown（+ @streamdown/code、@streamdown/math、@streamdown/mermaid）、axios；构建 Vite；测试 vitest + @testing-library/react + @playwright/test

**存储**：无服务端存储；前端本地态 = Zustand（内存）+ TanStack Query 缓存（内存）+ `sessionStorage`（JWT，仅经 `authTokenStore` 抽象读写）；AI 回答经 Streamdown 净化渲染，原始 HTML 不留存

**测试**：Vitest（AntD 校验规则、useChatStream 状态、fetch-event-source 事件分发 mock、反馈乐观回滚、上传校验、路由守卫）+ Playwright E2E（本地 mock SSE 服务，覆盖注册→登录→问答流式→来源→停止→反馈→上传→状态流转→删除→401 过期跳转）

**目标平台**：现代桌面浏览器（Chrome/Edge/Firefox/Safari），窄屏 ≥1024px 无横向滚动；管理端以桌面为主

**项目类型**：web 前端应用（SPA，前后端分离中的前端项目）

**性能目标**：发起提问后首段流式输出 ≤1 秒可见（SC-002）；历史会话切换响应 ≤1 秒（SC-005）；流式渲染由库级节流承担不卡顿

**约束**：前端禁止直接调用大模型 API 与向量检索（宪法原则三）；前端流式解析/渲染不自研（fetch-event-source/Streamdown）；SSE 仅消费 `data`/`meta`/`finish`/`error` 事件协议；问题 ≤500 字与每日次数由前端校验+后端兜底；正文 ≥14px、对比度 ≥4.5:1（WCAG AA）；AI 内容渲染必须净化（Streamdown 内置保持开启）；密钥不落前端

**规模/范围**：4 组页面（注册/登录、问答主界面、会话列表、知识库管理）+ AntD 主题令牌体系；本特性不含会话查询/反馈统计/数据看板等分析页（已声明留待后续特性）；依赖 001–005 已规划的后端接口

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 原则一：RAG 核心链路可读可控 | 前端不承载任何 RAG 逻辑；流式解析（fetch-event-source）与渲染（Streamdown）为成熟库，属「用库不造轮」而非黑盒封装，链路仍可解释；RAG 自研保留在后端 001 特性 | ✅ 通过 |
| 原则二：禁止编造与幻觉抑制 | 前端不生成内容；忠实消费 SSE `meta` 引用来源并渲染，空检索兜底话术由服务端下发、前端原样展示，禁止前端拼装虚假引用 | ✅ 通过 |
| 原则三：AI 能力仅在服务端执行 | 前端**只**通过 REST + SSE 与后端交互，无任何大模型/向量检索调用，密钥不落前端（research §1/§2） | ✅ 通过 |
| 原则四：流式输出与耗时任务异步化 | 前端完整消费 `data`/`meta`/`finish`/`error` 事件并流式渲染（FR-013）；停止生成经 AbortController；文档上传后轮询状态流转（FR-034，异步在服务端） | ✅ 通过 |
| 原则五：硬性业务约束 | 前端实现 500 字校验提示、每日次数用尽提示（FR-016）；兜底话术展示（FR-015）；登录态管理与 401 引导重新登录 | ✅ 通过 |
| 安全与合规 | JWT 经 `authTokenStore` 抽象读写（v1 sessionStorage，生产升级 HttpOnly Cookie）；AI 内容经 Streamdown 强制净化；管理端路由守卫拒绝未授权；密码仅表单传输不落前端 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

**Phase 1 设计后复检（通过）**：research.md 确认流式解析/渲染全部为成熟库（fetch-event-source / Streamdown），前端零自研轮子、零模型调用（原则一/三）；Streamdown 内置净化保持开启、`authTokenStore` 收敛 token 读写、admin 路由守卫（安全与合规）；fetch-event-source 的 `onmessage` 分发 + AbortController 停止 + `finish`/`error` 语义覆盖停止、错误、来源展示（原则四）。未引入新违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/007-frontend-page-design/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

项目为前后端分离的 Web 应用，本特性仅涉及前端；采用 Option 2 的前端结构。

```text
frontend/
├── index.html
├── vite.config.ts        # Vite + React 插件 + 路径别名 + Playwright 相关配置
├── package.json
├── src/
│   ├── main.tsx          # 应用装配：React QueryProvider、Zustand、AntD ConfigProvider（主题 token）、Router
│   ├── App.tsx           # 根组件（路由出口 + AntD 全局 message/modal 宿主）
│   ├── router/
│   │   └── index.tsx     # 路由表 + 守卫组件 RequireAuth/AdminOnly/redirect/401
│   ├── types/
│   │   └── index.ts      # 前端领域类型：User/Session/Message/KnownledgeDoc/Feedback/SseEvent
│   ├── stores/
│   │   ├── auth.ts       # Zustand：登录态、当前用户、配额（token 不落 store，经 authTokenStore）
│   │   └── session.ts    # Zustand：当前会话、输入草稿等轻量 UI 态
│   ├── api/
│   │   ├── http.ts       # axios 实例（Bearer 注入、401 拦截、错误码→友好提示映射）
│   │   ├── authTokenStore.ts # JWT 读写抽象（v1 sessionStorage，可切换 httpOnly cookie 方案）
│   │   ├── queries.ts    # TanStack Query hooks：me/sessions/messages/knowledge/quota（含轮询与失效）
│   │   └── sse.ts        # 基于 @microsoft/fetch-event-source 的问答流封装：onmessage 分发 data/meta/finish/error，signal 中止
│   ├── hooks/
│   │   ├── useChatStream.ts # 编排：发送→fetch-event-source→消息状态跟踪→停止；与 Zustand 轻量同步
│   │   └── useAutoScroll.ts # 近底部自动滚动
│   ├── utils/
│   │   └── validation.ts    # 纯函数校验（手机号/邮箱/密码/长度/上传类型与大小），供 AntD Form rules 复用
│   ├── components/
│   │   ├── chat/            # MessageBubble（Streamdown 渲染）/ SourceList / FeedbackControls / StreamCursor
│   │   ├── session/         # SessionList / SessionItem / NewSessionButton
│   │   ├── knowledge/       # DocTable（AntD Table）/ DocUpload（AntD Upload）/ DocStatusTag / DocActions
│   │   └── common/          # 基于 AntD 的页面级包装（AntD 组件直接用，必要时薄封装统一空态/确认弹窗）
│   ├── pages/
│   │   ├── login/           # LoginPage.tsx / RegisterPage.tsx（AntD Form）
│   │   ├── chat/            # ChatPage.tsx（会话列表 + 消息区 + 输入区）
│   │   ├── admin/           # AdminLayout.tsx + KnowledgePage.tsx
│   │   └── NotFound.tsx
│   └── styles/
│       ├── theme.ts         # AntD ConfigProvider theme.token 单一来源（主色/语义色/字号/圆角/间距）
│       └── global.css       # 全局样式：表格防爆、对比度、焦点样式、Streamdown 样式域隔离
└── tests/
    ├── unit/                # Vitest：validation / useChatStream / sseEvents / feedbackMutation / uploadRules / guards
    ├── e2e/                 # Playwright：auth / chat-stream / feedback / knowledge
    └── mocks/
        └── sse-server.ts    # 本地 mock SSE 服务（预置 data/meta/finish/error 事件）
```

**结构决策**：采用前端单项目结构（`frontend/`），按「页面（pages）— 组件（components）— 状态（stores + TanStack Query）— 服务（api/hooks）— 工具（utils）— 样式（theme.ts）」分层。**关键单点均为成熟库或薄封装**：SSE 消费封装在 `api/sse.ts`（fetch-event-source，不自研解析）、渲染在 `components/chat/MessageBubble`（Streamdown）、JWT 读写收敛于 `authTokenStore.ts` 抽象、主题令牌收敛于 `styles/theme.ts`（AntD token 单源，支撑 SC-009 一致性抽检）。前端自研面仅剩页面组装、消息状态跟踪与校验规则，不重复造轮子。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
