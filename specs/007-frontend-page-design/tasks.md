# 任务清单：前端页面设计

> 本清单基于 `plan.md`（React + TypeScript 技术栈与 `frontend/src/...` 项目结构）、`spec.md`（5 个用户故事）、`data-model.md`（视图模型）、`contracts/`（设计系统/页面/接口契约）生成。任务按「准备 → 基础 → 用户故事（P1→P2）→ 打磨」顺序组织，每个任务含精确文件路径，可独立执行。

---

## Phase 1：准备阶段（Setup）

项目初始化与基础结构：Vite + React + TS 脚手架，AntD 5、TanStack Query、Zustand、React Router、axios、fetch-event-source、Streamdown 依赖登记，Vitest/Playwright 与本地 mock SSE 基础配置。

- [ ] T001 [P] 创建 `frontend/` 项目脚手架：`frontend/package.json`、`frontend/index.html`、`frontend/tsconfig.json`、`frontend/tsconfig.node.json`、`frontend/.env.development`（含 `VITE_API_BASE`）、`frontend/.gitignore`，采用 Vite + React 18 + TypeScript 5，并在 `package.json` 注册 `dev`/`build`/`preview` 脚本
- [ ] T002 [P] 在 `frontend/package.json` 登记运行时依赖：`react`、`react-dom`、`react-router-dom`、`antd`、`@tanstack/react-query`、`zustand`、`@microsoft/fetch-event-source`、`streamdown`、`@streamdown/code`、`@streamdown/math`、`@streamdown/mermaid`、`axios`
- [ ] T003 [P] 在 `frontend/package.json` 登记开发依赖：`vite`、`@vitejs/plugin-react`、`typescript`、`@types/react`、`@types/react-dom`、`vitest`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`、`jsdom`、`@playwright/test`
- [ ] T004 [P] 编写 `frontend/vite.config.ts`：接入 `@vitejs/plugin-react`，配置路径别名 `@` → `frontend/src`，设置 `server.port=5173` 与 `/api` 代理到 `VITE_API_BASE`
- [ ] T005 [P] 编写 `frontend/vitest.config.ts` 与 `frontend/src/test/setup.ts`：`environment` 为 `jsdom`，在 setup 中挂载 `@testing-library/jest-dom`
- [ ] T006 [P] 编写 `frontend/playwright.config.ts`：`baseURL` 为 `http://localhost:5173`，`webServer` 同时启动 `npm run dev` 与 mock SSE 服务
- [ ] T007 [P] 编写 `frontend/tests/mocks/sse-server.ts`：本地 mock SSE 服务，预置 `meta → data → finish` 正常流、`error`（超时/限流）、空检索兜底三种事件序列；在 `frontend/package.json` 注册 `mock:sse`、`test:unit`、`test:e2e` 脚本
- [ ] T008 [P] 创建 `frontend/src/main.tsx` 与 `frontend/src/App.tsx` 最小占位（挂载 React 根节点），保证脚手架先行跑通，后续 Foundational 阶段填充 `QueryClientProvider`/`ConfigProvider`/`Router`

---

## Phase 2：基础阶段（Foundational）

阻塞所有用户故事的前置任务：主题体系、全局样式、路由守卫、认证基础、HTTP/SSE 封装、领域类型定义等。任务不加用户故事标签。

- [ ] T009 [P] 创建 `frontend/src/types/index.ts`：定义领域类型 `User`、`Session`、`Message`（含 `StreamState` 联合类型 `'connecting' | 'streaming' | 'completed' | 'aborted' | 'error'`）、`Source`、`Feedback`、`KnowledgeDoc`、`Quota`、`SseEvent`，对应 `data-model.md` 实体与 SSE 事件契约
- [ ] T010 [P] 创建 `frontend/src/styles/theme.ts`：按 `contracts/design-system.md` 定义 AntD `ConfigProvider.theme.token` 单一来源（`colorPrimary` 品牌蓝 `#2F6BFF`、语义色 `colorSuccess/colorWarning/colorError`、`colorBgLayout`/`colorBgContainer`/`colorText`/`colorTextSecondary`、`borderRadius` 8、`fontSize` 14、间距体系、`boxShadow`）
- [ ] T011 [P] 创建 `frontend/src/styles/global.css`：全局样式（正文 ≥14px、WCAG AA 对比度、清晰 focus 焦点环、表格防爆 `display:block; overflow-x:auto; white-space:nowrap`、Streamdown 样式域隔离）
- [ ] T012 [P] 创建 `frontend/src/utils/validation.ts`：纯函数校验（手机号/邮箱格式、密码长度与强度、两次密码一致、单条问题 ≤500 字、上传类型 `.txt/.md/.pdf` 白名单与大小上限），供 AntD Form `rules` 复用
- [ ] T013 [P] 创建 `frontend/src/api/authTokenStore.ts`：JWT 读写抽象（v1 存 `sessionStorage`，暴露 `getToken`/`setToken`/`clearToken`，注释生产升级 httpOnly Cookie + 刷新令牌路径）
- [ ] T014 创建 `frontend/src/api/http.ts`：axios 实例（`baseURL=VITE_API_BASE`、请求拦截注入 `Authorization: Bearer`、响应拦截统一 401 → 清登录态并跳 `/login`、按 `{code, message}` 错误码映射友好提示）
- [ ] T015 创建 `frontend/src/stores/auth.ts`：Zustand 登录态（`user`/`status: 'unauthenticated' | 'loading' | 'authenticated'`/`quota`），action：`login`/`register`/`logout`/`fetchMe`/`apply401`（调用 `api/http.ts`，token 不落 store）
- [ ] T016 [P] 创建 `frontend/src/stores/session.ts`：Zustand 轻量 UI 态（当前会话 id、输入草稿、`activeSessionId`）
- [ ] T017 创建 `frontend/src/api/queries.ts`：TanStack Query hooks（`useMe` 登录态初始化、`useSessions`、`useMessages`、`useKnowledgeDocs`、`useQuota`），含 `queryKey` 与失效约定
- [ ] T018 创建 `frontend/src/api/sse.ts`：基于 `@microsoft/fetch-event-source` 的问答流封装，`onmessage` 分发 `data`/`meta`/`finish`/`error` 事件，`AbortController.signal` 中止（不自研解析），请求体 `{session_id, question}`
- [ ] T019 创建 `frontend/src/router/index.tsx` 与 `frontend/src/pages/NotFound.tsx`：路由表 + 守卫组件 `RequireAuth`（未登录 → `/login?redirect=…`）与 `AdminOnly`（非 admin 拒绝），404 兜底；先注册 `/login`、`/register`、`*` 路由，`/chat` 与 `/admin/knowledge` 由对应故事接入
- [ ] T020 完善 `frontend/src/main.tsx` 与 `frontend/src/App.tsx`：装配 React `QueryClientProvider`、Zustand、AntD `ConfigProvider`（`theme.ts` token）、Router，`App.tsx` 使用 AntD `App` 组件承载全局 `message`/`modal` 宿主

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 用户注册与登录（优先级：P1）

**目标**：交付注册/登录页，支持手机号或邮箱 + 密码（注册含确认密码），实时表单校验、错误内联提示、登录态跳转与未登录拦截重定向。

**独立测试**：打开登录/注册页，可独立验证：注册成功、登录成功进入主界面、登录失败提示、表单校验、未登录拦截重定向。

- [ ] T021 [P] [US1] 创建 `frontend/src/pages/login/LoginPage.tsx`：AntD Form 登录表单（手机号/邮箱 + 密码 + 登录按钮 + 「去注册」入口），`rules` 实时校验（必填/格式）、错误内联展示，登录中按钮 `loading` 态，登录失败友好提示（不暴露敏感细节），登录成功进入 `/chat`，支持 `redirect` 参数返回原目标页，调用 `stores/auth.ts` 的 `login`
- [ ] T022 [P] [US1] 创建 `frontend/src/pages/login/RegisterPage.tsx`：AntD Form 注册表单（手机号/邮箱 + 密码 + 确认密码 + 注册按钮 + 「去登录」入口），`rules` 校验（必填/格式/密码长度与强度/两次一致）、错误内联，注册中 `loading`，注册成功反馈，调用 `stores/auth.ts` 的 `register`
- [ ] T023 [US1] 在 `frontend/src/router/index.tsx` 接入 `/login`、`/register` 路由，并实现「已登录访问 `/login` 或 `/register` 时跳转 `/chat`」逻辑

**检查点**：注册/登录流程可独立运行与验证（US1 全部验收场景）。

---

## 阶段 4：用户故事 2 - 智能问答主界面（流式回答 + 引用来源）（优先级：P1）

**目标**：交付问答主界面（消息区 + 输入区），AI 回答经 Streamdown 流式渲染，附带引用来源或兜底标识，支持停止生成、输入长度与每日次数约束、错误重试。

**独立测试**：登录后进入问答主界面，可独立验证：提问与流式回答、引用来源展示、兜底话术展示、生成中停止、输入校验、错误提示。

- [ ] T024 [US2] 创建 `frontend/src/hooks/useChatStream.ts`：编排「发送 → 调用 `api/sse.ts` → 消息状态跟踪（`connecting/streaming/completed/aborted/error`）→ 停止（`AbortController`）」，与 `stores/session.ts` 轻量同步，处理 `meta`（写 sources）/`data`（追加 content）/`finish`（回填 messageId、落定 suggestions）/`error`（保留已生成内容 + 可重试）
- [ ] T025 [P] [US2] 创建 `frontend/src/hooks/useAutoScroll.ts`：近底部自动滚动，用户主动上滚时暂停
- [ ] T026 [P] [US2] 创建 `frontend/src/components/chat/StreamCursor.tsx`：生成中流式光标指示
- [ ] T027 [P] [US2] 创建 `frontend/src/components/chat/SourceList.tsx`：引用来源展示（文档名 + 片段摘要，可点击展开详情，FR-015）
- [ ] T028 [US2] 创建 `frontend/src/components/chat/MessageBubble.tsx`：用户消息（主色浅底/右侧）与 AI 消息（卡片/左侧）视觉区分；AI 消息用 `<Streamdown>` 流式渲染（内置净化保持开启）、内嵌 `StreamCursor`、引用来源折叠区、反馈控件位、`streaming` 态展示停止按钮
- [ ] T029 [US2] 创建 `frontend/src/pages/chat/ChatPage.tsx`：整体布局（消息区 + 底部输入区），输入区含 500 字实时计数、发送/停止按钮、次数剩余提示；新会话欢迎语 + 示例问题引导；错误友好提示 + 重试；意图标签/追问建议按字段存在性容错展示；左侧会话列表面板先留占位（US3 接入）
- [ ] T030 [US2] 在 `frontend/src/router/index.tsx` 接入 `/chat` 路由（`RequireAuth` 守卫），使登录后进入主界面

**检查点**：流式问答主界面可独立运行与验证（US2 全部验收场景）。

---

## 阶段 5：用户故事 3 - 会话列表与历史会话（优先级：P1）

**目标**：交付会话列表面板，支持查看全部会话、一键新建、点击切换加载历史消息，当前会话高亮，空态引导。

**独立测试**：登录后打开会话列表，可独立验证：列表展示、新建会话、切换会话加载历史消息、当前会话高亮。

- [ ] T031 [P] [US3] 创建 `frontend/src/components/session/SessionItem.tsx`：单个会话项（标题/最后消息预览/更新时间，当前会话高亮），点击切换
- [ ] T032 [P] [US3] 创建 `frontend/src/components/session/NewSessionButton.tsx`：新建会话按钮，调用 `POST /api/session` 创建并进入空会话（FR-023）
- [ ] T033 [US3] 创建 `frontend/src/components/session/SessionList.tsx`：会话列表（按时间排序、当前会话高亮、空态引导），组合 `SessionItem` 与 `NewSessionButton`，使用 `useSessions`
- [ ] T034 [US3] 将 `SessionList` 接入 `frontend/src/pages/chat/ChatPage.tsx` 左侧面板（替换 US2 占位），窄屏（1024–1279px）折叠为 AntD `Drawer`（FR-005）
- [ ] T035 [US3] 实现历史加载与切换：`useMessages` 加载选中会话全部历史消息并在消息区完整展示，切换响应 ≤1 秒，新消息追加到会话末尾并同步列表预览，列表为空展示空态引导
- [ ] T036 [US3] 会话重命名与删除（加分项 FR-025，删除需二次确认，删除后返回列表或相邻会话；端点未确认时前端降级隐藏，见 `contracts/frontend-api.md` 协调项）

**检查点**：会话列表与历史会话可独立运行与验证（US3 全部验收场景）。

---

## 阶段 6：用户故事 4 - 对 AI 回答进行反馈（优先级：P2）

**目标**：交付 AI 回答的赞/踩反馈入口，踩时可附可选文字，反馈状态在会话内持久可见，仅出现在 AI 回答上。

**独立测试**：在问答主界面针对某条 AI 回答，可独立验证：赞/踩提交、状态切换、可选文字、反馈状态持久显示。

- [ ] T037 [P] [US4] 创建 `frontend/src/components/chat/FeedbackControls.tsx`：赞/踩按钮 + 踩时展开可选文字输入框 + 提交态（`isPending` 防重复），已选状态切换
- [ ] T038 [P] [US4] 在 `frontend/src/api/queries.ts` 新增 `useFeedbackMutation`：`useMutation` 乐观更新（`POST /api/message/{id}/feedback`，体 `{type, text?}`），失败回滚并 `message` 轻提示，提交成功后状态以服务端返回为准
- [ ] T039 [US4] 将 `FeedbackControls` 接入 `frontend/src/components/chat/MessageBubble.tsx` 的 AI 消息分支，确保用户消息/错误消息不提供反馈入口（FR-029）

**检查点**：反馈功能可独立运行与验证（US4 全部验收场景）。

---

## 阶段 7：用户故事 5 - 知识库管理（管理端）（优先级：P2）

**目标**：交付管理端知识库管理页，支持 .txt/.md/.pdf 文档上传、状态流转展示、列表搜索与增删改查，未授权访问被拦截。

**独立测试**：登录管理端进入知识库管理页，可独立验证：上传校验、状态流转展示、列表展示、搜索、编辑、删除。

- [ ] T040 [P] [US5] 创建 `frontend/src/pages/admin/AdminLayout.tsx`：管理端布局（侧边导航 + 内容区），当前项高亮，被 `AdminOnly` 守卫包裹（FR-031）
- [ ] T041 [P] [US5] 创建 `frontend/src/components/knowledge/DocStatusTag.tsx`：文档状态标签（处理中=加载态/就绪=成功色/失败=错误色 + `failMsg` 展示）
- [ ] T042 [P] [US5] 创建 `frontend/src/components/knowledge/DocTable.tsx`：AntD `Table` 文档列表（名称/类型/大小/状态/上传时间）+ 搜索 + 分页 + 空态（FR-032/037）
- [ ] T043 [P] [US5] 创建 `frontend/src/components/knowledge/DocUpload.tsx`：AntD `Upload` 多文件选择 + `beforeUpload` 类型/大小前置校验 + `onProgress` 进度 + `customRequest` 对接 `/api/knowledge/upload`，上传中临时项（FR-033）
- [ ] T044 [P] [US5] 创建 `frontend/src/components/knowledge/DocActions.tsx`：重命名/删除（二次确认 + 级联清理向量提示）/失败重传/查看详情（FR-034/035/036）
- [ ] T045 [US5] 创建 `frontend/src/pages/admin/KnowledgePage.tsx`：组装 `DocTable` + `DocUpload` + `DocStatusTag` + `DocActions`，接入 `useKnowledgeDocs` 轮询（仅存在非终态「处理中」项时开启 `refetchInterval`），删除后列表即时更新
- [ ] T046 [US5] 在 `frontend/src/router/index.tsx` 接入 `/admin/knowledge` 路由（`RequireAuth` + `AdminOnly` 守卫），未授权拒绝并引导登录

**检查点**：知识库管理页可独立运行与验证（US5 全部验收场景）。

---

## 阶段 8：打磨与横切关注点（Polish & Cross-Cutting Concerns）

- [ ] T047 全站一致性抽检（SC-009）：核对 `colorPrimary` 单源、圆角/间距与 token 一致、组件状态集齐全、空/错/加载态无缺失、无内联硬编码样式（随机抽查 5 页）
- [ ] T048 响应式与无障碍（FR-005/006、SC-008/010）：验证问答页 ≥1024px 无横向滚动、窄屏 `Drawer` 折叠、管理端 ≥1280px 适配、键盘可达、焦点可见、正文对比度 WCAG AA
- [ ] T049 错误与边界状态兜底（SC-004）：全站空/错/加载态检查、弱网/超时/限流（429）恢复提示、快速重复点击的防重复提交与状态防抖
- [ ] T050 性能与构建优化：AntD 按需加载、构建产物优化，核对首段流式输出 ≤1 秒（SC-002）与历史切换 ≤1 秒（SC-005）
- [ ] T051 跨特性协调项收口（`contracts/frontend-api.md` §3）：确认改名端点、会话删除/重命名、反馈状态回读、意图/追问建议字段缺失容错的前端降级行为
- [ ] T052 运行 `npm run test:unit` 与 `npm run test:e2e`（mock SSE）确保全部通过，并按 `quickstart.md` 5 个场景完成手工验收（注册登录/流式问答/历史会话/反馈/知识库管理）

---

## 依赖关系与执行顺序

1. **Phase 1（Setup）** 先行：脚手架与依赖就绪后，Phase 2 方可开始。
2. **Phase 2（Foundational）** 阻塞所有用户故事：`types` → `theme`/`global.css`/`validation`/`authTokenStore` → `http`/`auth store`/`queries`/`sse` → `router`/`main+App`。其中 `http` 依赖 `authTokenStore` 与 `types`，`auth store` 依赖 `http`，`queries` 依赖 `http`，`router` 依赖 `auth store` 与 `queries`。
3. **用户故事阶段**：US1（P1）→ US2（P1）→ US3（P1）→ US4（P2）→ US5（P2）按优先级顺序实施；P1 三故事彼此可独立完成与独立验收。US4 依赖 US2 的 `MessageBubble`，US3 依赖 US2 的 `ChatPage` 布局占位，故建议 US2 先于 US3/US4 完成。
4. **打磨阶段**：所有故事完成后进行一致性、无障碍、性能、跨特性协调项与全量验收。

## 并行机会

- **Setup 阶段**：T001–T008 各自为独立文件，可全部并行。
- **Foundational 阶段**：T009（types）、T010（theme）、T011（global.css）、T012（validation）、T013（authTokenStore）、T016（session store）互不依赖，可并行；其余按依赖顺序推进。
- **US1**：T021 与 T022（两个页面）可并行。
- **US2**：T025（useAutoScroll）、T026（StreamCursor）、T027（SourceList）可并行，随后 T028（MessageBubble）与 T029（ChatPage）。
- **US3**：T031（SessionItem）与 T032（NewSessionButton）可并行，随后 T033（SessionList）。
- **US4**：T037（FeedbackControls）与 T038（useFeedbackMutation）可并行。
- **US5**：T040–T044（布局与各组件）均为独立文件，可全部并行，随后 T045（KnowledgePage）组装。

## 实施策略

- **MVP 优先**：先交付 P1 三故事（US1 注册登录 → US2 智能问答 → US3 会话列表），形成「注册登录 → 提问 → 流式回答 → 历史会话」的完整可用闭环；其中 US1 为最小可演示单位。
- **增量交付**：每个用户故事完成后即为一颗可独立演示、独立验证的增量，P2（US4 反馈、US5 知识库管理）作为增强在 P1 闭环后依次叠加。
- **并行团队策略**：Foundational 就绪后，US1/US2/US3 可由不同成员并行开发（US2 先完成 ChatPage 布局供 US3 接入）；US4/US5 在 P1 稳定后并行推进，最后统一进入打磨阶段完成一致性与全量验收。
