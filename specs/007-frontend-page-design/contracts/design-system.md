# 设计系统契约：企业专业浅色风

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

本契约定义全站视觉与组件规范的**单一来源**（实现于 `frontend/src/styles/theme.ts` 的 Ant Design `ConfigProvider.theme.token` + 全局 `global.css`），保证 FR-001~006 可测、SC-009 一致性抽检可验证。所有页面与组件必须遵守，禁止样式漂移。

## 1. 主题令牌（AntD ConfigProvider theme.token）

| 令牌 | 取值（默认） | 用途 |
|---|---|---|
| `colorPrimary` | 单一品牌主色（专业蓝系，如 `#2F6BFF`） | 主操作按钮、激活态、链接、重点强调（FR-001 单一主色） |
| `colorSuccess` / `colorWarning` / `colorError` | 绿 / 橙 / 红语义色 | 状态反馈（处理中/就绪/失败、成功/警告/错误提示） |
| `colorBgLayout` | 浅灰（如 `#F5F7FA`） | 页面背景 |
| `colorBgContainer` / `colorText` / `colorTextSecondary` | 白 / 近黑 / 灰 | 卡片背景与正文/辅助信息层级 |
| `borderRadius` | 8 | 卡片、弹窗统一圆角 |
| `fontSize` | 14 | 正文基准字号（≥14px，FR-004） |
| `fontSizeHeading*` | 18+ / 16 / 14 | 标题/正文/辅助三级层级 |
| `token` 间距体系 | 4 基数，统一 4 的倍数 | 布局间距 |
| `boxShadow` | 统一轻投影 | 卡片浮起层级 |

**约束**：主色全局唯一（除语义色外不得引入第二强调色）；正文与背景对比度 ≥4.5:1，大字号与辅助色 ≥3:1（FR-006/WCAG AA）——通过 `colorText`/`colorTextSecondary`/`colorBgContainer` 的取值保证，并用全局样式兜底。

## 2. 组件状态集（AntD 组件统一）

| 状态 | 视觉要求 |
|---|---|
| 默认 / 悬停 / 聚焦 | 三态明确可辨；聚焦态有清晰 focus 环（键盘可达 FR-006） |
| 禁用 | 降低对比（AntD 默认禁用态），仍可读 |
| 加载 | `loading` 态 + Spin 指示，主操作禁重复触发 |
| 成功 / 错误 | 语义色 + 可理解文案，错误内联展示在对应控件旁 |
| 空态 | 每页/每列表提供 `Empty` 组件 + 引导文案（FR-003） |

**关键组件（AntD 内置，不自研）**：
- **Button**：primary / default / text 三档，交互热区 ≥44px（图标按钮）
- **Form + Input**：`rules` 实时校验错误内联（FR-008），支持长度计数（`maxLength` + 计数）
- **Modal**：确认类操作二次确认载体（删除等 FR-025/035）
- **Empty**：空会话/空列表/空搜索统一空态
- **Table / Pagination**：知识库列表分页（FR-032）
- **Upload**：上传文件选择/进度/类型校验（FR-033）
- **message / notification**：全局成功/错误/警告轻提示（FR-026 反馈提示、FR-019 错误提示）

## 3. 流式渲染相关组件契约

- **MessageBubble**：用户消息（主色浅底/右侧）与 AI 消息（卡片/左侧）清晰区分（FR-012）；AI 消息内含 **Streamdown**（流式 Markdown 渲染 + 内置净化，见 [research.md](../research.md) §3）、流式光标、来源折叠区、反馈控件、停止按钮（仅 streaming 态）。
- **表格防爆**：AI 回答内嵌表格 `display:block; overflow-x:auto; white-space:nowrap`，不撑破气泡/容器（FR-004 长内容处理）——由 `global.css` 兜底。
- **长代码块**：Streamdown 代码块内置复制按钮 + 横向滚动；语言归一化由 `@streamdown/code`（Shiki）承担。

## 4. 响应式契约

| 断点 | 行为 |
|---|---|
| ≥1280px | 完整布局（问答页：会话列表 + 消息区 + 输入区；管理端：侧边导航 + 内容区） |
| 1024–1279px | 问答页会话列表折叠为可开合 Drawer 抽屉（AntD）；≥1024px 无横向滚动（FR-005/SC-008） |

## 5. 一致性抽检（SC-009）

随机抽查 5 个页面，核对：主色唯一（`colorPrimary` 单源）、圆角/间距与 token 一致、组件状态集齐全、空/错/加载态无缺失、无内联硬编码样式（样式一律走 token/className）。违规即视为不通过。
