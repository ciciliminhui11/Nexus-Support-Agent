# 研究记录：前端页面设计

**日期**：2026-08-29（v2：选型改为 React 系，前端不自研） | **特性**：[spec.md](spec.md)

本文件记录 Phase 0 对技术上下文 unknowns / 依赖 / 集成的研究结论，统一为「决策 / 理由 / 备选方案」。

**总原则（用户明确要求）**：前端流式输出、Markdown 渲染、状态管理等一律**不自研**，全部选用成熟库/组件；仅 RAG 核心链路（后端 001 特性）保留适量自研。本特性（前端）唯一保留的最小自研面是**页面与交互的组装层**（路由、布局、消息状态跟踪、校验规则），不重复造轮子。

## 0. 技术栈总览（v2 定稿）

| 域 | 选定方案 | 职责 |
|---|---|---|
| 框架 | **React 18 + TypeScript 5**（用户指定） | 应用主体 |
| 构建 | Vite | 构建/开发服务器 |
| 路由 | **React Router v7** | 路由表 + 守卫（RequireAuth/AdminOnly/redirect/401） |
| UI 组件库 | **Ant Design 5**（`ConfigProvider` theme token 定制） | 表单/上传/表格/弹窗/分页/消息提示，管理端数据组件开箱即用 |
| 服务端状态 | **TanStack Query** | 会话/消息/知识库/配额等 API 数据缓存、重试、轮询、失效 |
| 全局客户端状态 | **Zustand** | 登录态、当前会话、UI 轻量态 |
| 流式问答（SSE） | **@microsoft/fetch-event-source** | fetch + SSE 解析 + 事件分发，兼容 `data/meta/finish/error` 协议 |
| AI 回答渲染 | **Streamdown**（react-markdown 兼容 drop-in，流式优化） | 流式 Markdown 渲染 + 内置安全净化 + Shiki 高亮/KaTeX/Mermaid/复制 |
| HTTP | axios | REST 请求、上传进度、拦截器（Bearer 注入/401/错误码映射） |
| 表单 | AntD Form（内置校验规则） | 注册/登录表单校验（不自研） |
| 上传 | AntD Upload（内置进度/类型校验/customRequest） | 知识库上传（不自研） |
| 表格 | AntD Table（内置排序/分页/加载/空态） | 知识库列表（不自研） |
| 测试 | Vitest + React Testing Library + Playwright（本地 mock SSE） | 单元/组件/E2E |

## 1. 流式问答消费：@microsoft/fetch-event-source（不自研 SSE 解析）

- **决策**：采用 **`@microsoft/fetch-event-source`** 消费 `POST /api/chat/stream`（携带 `Authorization: Bearer` 头与 JSON 请求体），用其 `onopen`/`onmessage`/`onerror`/`onclose` 回调分发 `data`/`meta`/`finish`/`error` 事件；用 `signal: AbortController` 实现「停止生成」。
- **理由**：原生 `EventSource` 只支持 GET、无自定义头、无请求体，鉴权只能走 URL（token 泄漏进日志/历史），本系统问答需 POST + Bearer + JSON 体，故排除；`@microsoft/fetch-event-source` 直接提供 fetch + SSE 解析 + 事件分发，**解析逻辑零自研**，与现有 `data/meta/finish/error` 协议零冲突（按 `event:` 字段分发）。token 经 `authTokenStore` 注入 `Headers`。停止/超时用 `AbortController`（FR-014）。
- **已知注意点**：该库 2021 年后未更新，社区有 fork（`fetch-event-source-hperrin`、`@fixers/fetch-event-source` 等）；无内置指数退避——本项目不需要静默自动重连（错误经 `error` 事件 + 重试按钮处理，401 死循环风险由「不自动重连」规避），故用核心库即可，实施时锁定版本并核对 fork 差异。若后续需要更活跃维护，可平滑替换为等价库（接口形态一致）。
- **备选方案**：Vercel AI SDK `useChat`（React 流式标准，自带消息状态机/停止/乐观 UI，但**强绑定 AI SDK 流协议**，需把 001 后端 SSE 改为其格式或自写适配 transport，跨特性改动成本高；已评估并放弃）；`eventsource-parser`（Vercel ~600B 极简分帧解析器，但 fetch 编排与事件分发仍需自写 glue）；原生手写解析（用户明确要求不自研，排除）。

## 2. 登录态存储：v1 按 003 契约存 sessionStorage + 安全加固；生产升级 httpOnly Cookie 刷新令牌

- **决策**：v1 遵循 003 鉴权契约（登录返回 `access_token`，全站 `Authorization: Bearer` 头），token 存 **`sessionStorage`**（刷新会话内不丢、关闭标签页即清除），认证读写收敛到独立 `authTokenStore` 抽象（Zustand auth store 仅存内存态，不持 token）；AI 渲染内容强制净化（Streamdown 内置 + 渲染前兜底校验，见 §3）、配置严格 CSP，降低 XSS 窃取面。文档化**生产升级路径**：改为「短时 access token 仅存内存 + 长时 refresh token 落 `HttpOnly + Secure + SameSite` Cookie + 静默刷新端点」。
- **理由**：2026 年安全共识（OWASP / IETF OAuth BCP / Auth0）为短时 access token 存内存、refresh token 落 HttpOnly Cookie——但该模式要求后端在登录/刷新响应写 Cookie 并提供刷新端点，属于 003 鉴权契约变更，不在本前端特性单方面可决定范围。本项目为本地沙箱、考试交付场景，v1 复用既有契约快速闭环，把存储收敛到单一抽象 + 前端净化加固，将 cookie 方案列为跨特性生产硬化项。localStorage 与 sessionStorage 对 XSS 同样可读，但 sessionStorage 关闭标签即清、窃取窗口更短，故选它。
- **备选方案**：localStorage（暴露窗口更长，无必要）；直接改 003 契约上 httpOnly cookie（更安全，需后端协同 + CSRF 处理，留作生产升级）；内存 only（刷新即丢登录态，违反 FR-010「刷新不丢失」）。

## 3. AI 回答渲染：Streamdown（流式优化 + 内置净化，不自研渲染管线）

- **决策**：AI 回答用 **Streamdown**（react-markdown 的 drop-in 替代，`<Streamdown>{content}</Streamdown>`）流式渲染；配 `@streamdown/code`（Shiki 高亮）、`@streamdown/math`（KaTeX）、`@streamdown/mermaid`（图表）；**渲染前强制安全净化**——Streamdown 内置 HTML 净化，实施时验证并保持开启（对 AI 内容视为不可信，防 prompt injection 注入脚本）；流式模式下其 `Streamdown` 对半成品 Markdown 做部分内容渲染（未闭合围栏按纯文本处理，流结束定型），并支持 `static` 静态模式供历史/详情复用。
- **理由**：用户要求前端渲染不自研；Streamdown 专为 AI 流式设计（react-markdown 无缝迁移、内置净化、Shiki/KaTeX/Mermaid/复制按钮），glue 最少，且是 2026 流式 Markdown 领域的主流选择之一。选择它的同时**保留不可省略的安全约束**：净化开启 + 默认转义原始 HTML。
- **已知注意点**：Streamdown 样式依赖 Tailwind CSS（需将 Tailwind 扫描范围加入其 dist 文件）；在 AntD 项目中引入 Tailwind 会增加一套 CSS 工具链——实施时按需最小化引入（或对 Streamdown 组件包裹隔离样式域），作为实现的已知成本，已在 plan 标注。
- **备选方案**：react-markdown + remark-gfm + rehype-sanitize（生态最成熟但非流式优先，每 chunk 重渲染需自行节流，glue 多）；markstream-react（流式优先、渐进式 Mermaid/KaTeX、长文虚拟化，但 API 非 react-markdown 兼容、包大且较新）；手写 markdown-it + DOMPurify 管线（用户明确要求不自研，排除）。

## 4. UI 组件库：Ant Design 5 + ConfigProvider theme token（企业专业浅色风）

- **决策**：采用 **Ant Design 5**，企业专业浅色风通过 `ConfigProvider` 的 `theme.token` 定制（主色、语义色、圆角、字号、间距、阴影收敛为单一 theme 源）；管理端数据组件（Table/Form/Upload/Modal/Pagination/Messages）全部用 AntD 内置能力，不自研。
- **理由**：管理端知识库页是数据密集型场景（表格/表单/上传/分页/空态），AntD 这些组件开箱即用、中文生态最佳、与初步方案 React 备选一致；`ConfigProvider` token 体系可支撑 SC-009「抽查 5 页样式一致」。用户指定前端不自研，AntD 能最大程度把通用组件交给库。
- **已知注意点**：AntD bundle 较大（需按需加载 + 构建优化）；a11y 弱于 Radix/shadcn——FR-006/SC-010 的键盘可达与对比度要求靠 token 与全局 CSS 兜底落实。
- **备选方案**：shadcn/ui + Tailwind（现代默认、CSS 变量主题契合令牌、bundle 最小，但无内置表格/上传，需组合 @tanstack/react-table 等，组装量大）；MUI（企业最稳但 Material 观感需大量覆写成浅色专业风）；Mantine（介于二者之间，也在候选，最后按「与初步方案 React 备选一致 + 管理端组件最全」选 AntD）。

## 5. 状态管理：TanStack Query（服务端状态）+ Zustand（全局客户端状态）

- **决策**：**严格分离服务端与客户端状态**（2026 最佳实践）：会话/消息/知识库/配额等 API 数据走 **TanStack Query**（`queryKey` 缓存、`refetchInterval` 轮询、失败重试、`invalidateQueries` 失效、`useMutation` 乐观更新）；登录态/当前会话/UI 轻量态走 **Zustand**（模块级单例、selector 订阅、无 Provider）。流式问答的消息流状态（connecting/streaming/completed/aborted/error）由 `useChatStream` hook 持有（其底层是 fetch-event-source 回调 + Zustand 轻量同步），仅跟踪状态不重造解析。
- **理由**：上传后「处理中→就绪/失败」需要轮询/失效刷新，TanStack Query 的 `refetchInterval`/`invalidateQueries` 天然覆盖（§7）；反馈乐观更新用 `useMutation` 四步生命周期（快照→乐观→往返→回滚）开箱即用（§8）；Zustand 无 Provider、selector 订阅避免无关重渲染，适合登录态等全局同步态。
- **备选方案**：Redux Toolkit + RTK Query（学习成本/样板高、bundle 大，中小项目偏重，已评估放弃）；仅 Zustand + axios（服务端缓存/轮询/重试需手写，违背「非必要不自研」）。

## 6. 路由与鉴权：React Router v7 + 守卫组件 + axios 401 拦截

- **决策**：**React Router v7** 定义路由表；用守卫组件 `<RequireAuth>`/`<AdminOnly>` 包裹受保护路由（未登录 → `/login?redirect=…`；角色非 admin → 拒绝），路由级组件组合而非框架层配置；axios 拦截器统一处理 401（清登录态 → 跳登录页，FR-010/011）。登录态初始化用 TanStack Query 的 `useQuery('me')`。
- **理由**：React Router 是 React 生态事实标准路由；守卫组件化组合最贴合 React 心智模型，与 FR-011 未登录重定向、FR-031 管理端授权验收一一对应。
- **备选方案**：TanStack Router（更类型安全但生态较新，学习成本高）；路由守卫写在每次请求里（分散、不可测，排除）。

## 7. 知识库上传与状态刷新：AntD Upload + TanStack Query 轮询/失效

- **决策**：上传用 **AntD Upload**（内置多文件选择、`beforeUpload` 类型/大小前置校验、`onProgress` 进度、`customRequest` 对接后端）；上传成功后 TanStack Query 使知识库列表查询失效并刷新；**仅当列表存在非终态（处理中）文档时开启 `refetchInterval` 轻量轮询**，终态后停止（FR-033/034）。
- **理由**：AntD Upload 内置校验/进度/拖拽，符合「不自研」；上传与状态流转是服务端异步，TanStack Query 失效+轮询是最简单可靠的终态感知手段，且轮询按需启停成本可控。
- **备选方案**：手写文件输入 + axios 进度（重复造轮子）；长轮询/WebSocket 推送（后端需额外支持，超前端范围，留作优化）。

## 8. 反馈：TanStack Query useMutation 乐观更新 + 服务端为准

- **决策**：赞/踩提交用 **`useMutation` 乐观更新**（立即切换 UI + AntD message 轻提示，失败回滚并提示）；同一条回答的反馈状态以服务端返回为准（FR-028 跨会话持久），重进会话按服务端数据恢复；提交按钮 `isPending` 态防重复（FR-030）。反馈控件仅挂在 AI 消息上（FR-029）。
- **理由**：反馈体验要即时（FR-026），乐观更新在弱网下给出即时反馈、失败回滚保证最终一致；useMutation 提供 isPending/onSuccess/onError 等钩子，无需自研提交状态机。
- **备选方案**：同步等待后端再更新（弱网体验差）；纯本地状态（刷新即丢，违反 FR-028）。

## 9. 响应式与无障碍：桌面主设计 + 窄屏折叠 + WCAG AA（AntD token 兜底）

- **决策**：桌面端（≥1280px）完整布局；问答页在窄屏（1024–1279px）将会话列表折叠为可开合抽屉/图标入口（AntD Drawer），保证 ≥1024px 无横向滚动（FR-005/SC-008）；正文 ≥14px、文本背景对比度 ≥4.5:1 经 `ConfigProvider` token 与全局 CSS 落实（FR-004/006），全部关键操作支持键盘且焦点可见。
- **理由**：FR-005/006/SC-008/SC-010 为硬性可测指标，AntD token（`fontSize`、`colorText`/`colorBgContainer`）与全局样式层是落实点；AntD 组件本身具备基础键盘可达，配合 token 对比度约束补足 FR-006。
- **备选方案**：移动端完整重排（超范围）；不做窄屏适配（违反 FR-005）。

## 10. 测试策略：Vitest + React Testing Library + Playwright（mock SSE）

- **决策**：**Vitest + React Testing Library** 做组件/store/hook 单元测试（AntD Form 校验规则、`useChatStream` 状态跟踪、fetch-event-source 事件分发 mock、反馈乐观回滚、上传校验、路由守卫）；**Playwright** 做 E2E，覆盖 spec 验收场景：注册→登录→提问→流式渲染→引用来源→停止→反馈→上传→状态流转→删除→401 过期跳转；SSE 用本地 mock 服务（预置 data/meta/finish/error 事件）保证确定可复现。设计一致性以 AntD token 单源 + E2E 视觉抽查（SC-009）双保险。
- **理由**：宪法「测试优先」「关键链路集成测试必须」；页面特性以用户体验为验收，E2E 是唯一能验证「流式打字机、来源展示、状态反馈」端到端体验的手段；mock SSE 避免依赖真实 LLM/后端，测试稳定可复现。
- **备选方案**：仅组件单测（覆盖不到跨页流程与流式体验）；仅真后端联调（依赖 001–005 全就绪，不可独立）；视觉回归快照（首版可不做，列入后续）。

## 参考来源（外部事实核查）

- 流式对话选型：[Vercel AI SDK useChat 与流式模式综述](https://dev.to/thegdsks/streaming-llm-responses-in-typescript-sse-readablestream-and-the-react-19-usechat-hook-36la)、[Streaming LLM Frontend Patterns](https://gigagpu.com/ai-streaming-llm-frontend-patterns/)、[@microsoft/fetch-event-source](https://app.unpkg.com/@microsoft/fetch-event-source@2.0.1/files/README.md)、[Vercel AI SDK v5 迁移](https://www.pkgpulse.com/guides/vercel-ai-sdk-5-migration-2026)
- Markdown 渲染选型：[markstream-react vs react-markdown vs Streamdown 对比](https://markstream.simonhe.me/compare/)、[Streamdown（react-markdown 迁移）](https://markstream.simonhe.me/guide/react-markdown-migration)、[markstream-react React 文档](https://markstream.simonhe.me/frameworks/react)
- UI 组件库选型：[shadcn/ui vs MUI vs Ant Design 2026](https://adminlte.io/blog/shadcn-ui-vs-mui-vs-ant-design/)、[Top React Component Libraries 2026](https://www.pkgpulse.com/guides/top-react-component-libraries)、[React UI Frameworks Compared（MUI/Radix/shadcn）](https://spell.sh/blog/react-ui-frameworks-compared)
- 状态管理选型：[React State Management 2026（server/client 分离）](https://www.pkgpulse.com/guides/state-of-react-state-management-2026)、[2026 决策树而非宗教](https://www.aiwisdom.dev/articles/frontend-react/state-management)、[TanStack Query + Zustand 迁移实践](https://dou.ua/forums/topic/61489/)
- JWT 存储：[SPA Token 存储安全](https://safeguard.sh/resources/blog/single-page-application-token-storage-security)、[Stop Storing JWTs in LocalStorage（2026）](https://dev.to/aleksei_aleinikov/stop-storing-jwts-in-localstorage-cookie-auth-for-spas-in-2026-2enk)
