# 前端（Frontend）

> AI 智能客服系统前端。技术选型：**React 18 + TypeScript + Vite + Ant Design 5**（按 specs/007-frontend-page-design 规格与 plan.md v2，用户确认 React 选型）。已实现：注册/登录、智能问答主界面（流式 + 引用来源）、会话列表与历史会话、用户反馈（点赞/点踩）、管理端（知识库管理 / 反馈查看 / 配额查看）。

## 技术栈

- **框架**：React 18（函数组件 + Hooks）+ TypeScript 5
- **构建**：Vite（`dev` / `build` / `preview`）
- **UI**：Ant Design 5（ConfigProvider token 定制企业专业浅色风）
- **状态**：TanStack Query（服务端数据）+ Zustand（登录态等全局客户端状态）
- **路由**：React Router（RequireAuth / AdminOnly 守卫）
- **通信**：axios（REST）+ `@microsoft/fetch-event-source`（流式问答 SSE，兼容 `data/meta/finish/error` 协议）
- **渲染**：Streamdown 流式 Markdown 渲染（内置净化）
- **测试**：Vitest + React Testing Library（单元）、Playwright（E2E 直连真实后端）

> 前端不调用任何大模型/向量检索，LLM 与检索全部由后端完成（模型 API Key 仅存服务端环境变量）。

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `src/api/` | HTTP（axios 实例 + 401 拦截）/ SSE 封装 / TanStack Query hooks / JWT 存储抽象 |
| `src/stores/` | Zustand 登录态与会话 UI 态 |
| `src/components/` | 聊天（消息气泡/来源/光标）/ 会话列表等组件 |
| `src/pages/` | 登录/注册/问答主界面 + 管理端（`admin/`：知识库管理、反馈、配额，`AdminOnly` 守卫） |
| `src/hooks/` | 流式问答编排 / 自动滚动 |
| `src/styles/` | AntD 主题 token 单源 + 全局样式 |
| `src/types/` | 领域类型与 SSE 事件类型 |
| `src/router/` | 路由表 + 守卫（RequireAuth / AdminOnly / GuestOnly） |
| `tests/mocks/` | 本地 mock SSE 服务（测试用） |

## 启动说明

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 代理到后端
```

环境变量：复制 `.env.development` 中 `VITE_API_BASE` 指向后端地址（默认 `http://localhost:8000`）。

## 测试

```bash
npm run test:unit   # Vitest 单元测试（39 用例：校验/SSE 封装/流式编排/组件）
npm run test:e2e    # Playwright E2E（直连真实后端，见下）
```

### E2E（直连真实后端）

E2E 走**全链路真实后端**（MySQL + DeepSeek），请先按根目录《运行指南》起好后端，再执行：

```bash
cd backend && uvicorn app.main:app --reload --port 8000   # 另开终端
cd frontend && npm run test:e2e
```

- Playwright 仅自动拉起 Vite dev server（5173）；后端须自行启动且监听 8000。
- 知识库为空时后端走兜底话术（不调用 LLM），用例断言「必有回复」而非具体文案，空/非空知识库均可跑。
- 每次运行注册独立测试账号（`e2e_<timestamp>@example.com`），互不干扰。

### 本地无后端调试问答流（可选）

```bash
npm run mock:sse   # 起本地 mock SSE 服务 :8899
```

配合把 `.env.development` 的 `VITE_API_BASE` 改为 `http://localhost:8899`，即可在无后端环境下调试前端流式渲染（仅覆盖 `/api/chat/stream`，登录/会话等接口不在此范围）。该服务不参与 E2E。

## 注意事项

- LLM 与向量检索全部由后端完成，前端禁止直接调用大模型 API。
- 登录态 v1 存 `sessionStorage`（收敛于 `src/api/authTokenStore.ts` 抽象），生产可升级 httpOnly Cookie + 刷新令牌。
