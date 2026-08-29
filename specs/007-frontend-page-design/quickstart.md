# 快速验证指南：前端页面设计

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 007 前端页面可用。实现细节见 `tasks.md` 与实施阶段，不在本文档内。

## 前置条件

- 后端已启动（`uvicorn app.main:app --host 0.0.0.0 --port 8000`），且 001–005 接口可用；或使用本地 mock SSE 服务独立验证流式体验
- Node.js ≥ 20，包管理器 npm/pnpm
- `.env.development` 配置后端地址（`VITE_API_BASE`），密钥不落前端

## 启动与安装

```bash
cd frontend
npm install
npm run dev            # 默认 http://localhost:5173
```

E2E 依赖的本地 mock SSE 服务：

```bash
npm run mock:sse       # 启动预置 data/meta/finish/error 事件流的 mock 服务
```

## 验证场景

### 场景 1：注册 → 登录 → 进入主界面（验收场景 US1）

1. 打开 `/register`，填写手机号/密码/确认密码，提交 → 注册成功反馈
2. 切到 `/login` 输入错误密码 → 展示明确错误提示，无敏感细节
3. 输入正确凭证登录 → 进入 `/chat` 主界面；刷新页面登录态保持
4. 直接访问 `/chat`（未登录新会话）→ 被重定向到 `/login?redirect=/chat`

**预期**：表单校验内联展示、登录态刷新不丢、未登录重定向均生效（FR-008~011）。

### 场景 2：流式问答 + 引用来源 + 停止 + 兜底（验收场景 US2）

1. 在输入区发送合法问题（mock SSE 返回 `meta` → 若干 `data` → `finish`）
2. 观察：首段输出 ≤1 秒出现；AI 回答逐段打字机渲染；回答下方展示引用来源（文档名 + 片段摘要），可展开
3. 输入 501 字 → 禁止发送并提示长度超限
4. 发送后立即点「停止」→ 停止输出且已生成内容保留
5. 使用 mock 返回 `error`（超时）→ 展示友好错误提示并可重试，已发送问题保留
6. mock 返回空检索兜底 → 展示固定兜底话术 + 「未检索到知识库内容」标识

**预期**：流式渲染、来源/兜底展示、停止、错误重试、长度拦截全部符合（FR-013~019）。

### 场景 3：多轮与历史会话（验收场景 US3）

1. 新建会话 → 进入空会话，展示欢迎语 + 示例问题
2. 连续提问两轮 → 同会话内消息连续展示
3. 回会话列表，点击历史会话 → 加载全部历史并可继续提问
4. 列表为空时 → 展示空态引导

**预期**：切换响应 ≤1 秒、历史完整、空态可见（FR-018/022~024，SC-005）。

### 场景 4：反馈（验收场景 US4）

1. 对某条 AI 回答点「赞」→ 按钮切换已选 + 轻提示
2. 对另一条点「踩」→ 展开文字框，填写或不填提交
3. 刷新页面 → 已提交反馈状态仍显示（后端返回为准）
4. 尝试对用户消息操作 → 无反馈入口

**预期**：乐观反馈、可选文字、状态持久、仅 AI 消息可反馈（FR-026~030）。

### 场景 5：知识库管理（验收场景 US5，需 admin 账号）

1. 用 admin 登录进入管理端 → 未授权访问被拦截
2. 上传 `.txt`/`.md`/`.pdf` → 上传进度可见，进入「处理中」
3. 选择 `.exe` → 拒绝并提示类型不支持
4. 轮询后状态流转为「就绪」；模拟失败 → 「失败」+ 原因展示
5. 搜索过滤、重命名、删除（二次确认）→ 列表即时更新；删除提示级联清理向量
6. 搜索无结果 → 空态

**预期**：上传校验、状态流转、增删改查、空态全部符合（FR-031~037，SC-006）。

## 测试命令

```bash
cd frontend
npm run test:unit     # Vitest + RTL：validation / sseEvents / useChatStream / feedbackMutation / uploadRules / guards
npm run test:e2e      # Playwright：auth / chat-stream / feedback / knowledge（mock SSE）
```

**预期**：全部通过。E2E 覆盖注册→登录→流式→来源→停止→反馈→上传→状态流转→删除→401 过期跳转。

## 关键契约引用

- 设计令牌与组件状态：[contracts/design-system.md](contracts/design-system.md)
- 页面结构与验收映射：[contracts/pages.md](contracts/pages.md)
- 前端消费的后端接口（REST + SSE）：[contracts/frontend-api.md](contracts/frontend-api.md)
- 前端状态模型与 SSE 事件：[data-model.md](data-model.md)
- 关键技术决策依据：[research.md](research.md)
