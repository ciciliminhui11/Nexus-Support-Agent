# Nexus-Support-Agent · AI 智能客服系统

基于 **RAG（检索增强生成）** 的 AI 客服系统：用户提问 → 意图识别 → 混合检索知识库 → LLM 流式回答，支持来源引用、幻觉校验、会话管理、用户反馈与知识库后台任务。

## 功能特性

- **RAG 问答**：混合检索（向量 + BM25 双路召回 → RRF 融合 → Reranker 精排），流式 SSE 输出
- **意图识别**：三层漏斗（规则 → 小模型 → 大模型兜底），闲聊/投诉/澄清短路免检索
- **防幻觉**：空检索短路不调用 LLM + System Prompt 约束 + 输出后来源校验（postcheck）
- **知识库管理**：Markdown/PDF 文档上传解析、切片入库、状态管理（后台任务，无需 Redis/Celery）
- **用户体系**：注册/登录（JWT）、会话多轮、消息持久化、用户反馈
- **运维**：`system_config` 运行时热调参数、全链路埋点 trace 可查

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.14 + FastAPI（异步，SSE 流式） |
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 |
| 对话 LLM | DeepSeek 官方 API（`deepseek-v4-flash`，OpenAI 兼容） |
| Embedding | SiliconFlow 云端 `BAAI/bge-m3`（1024 维） |
| 向量库 | Chroma（本地文件模式，cosine） |
| 业务库 | MySQL 8.0（SQLAlchemy + pymysql） |
| 精排 | `bge-reranker-v2-m3`（可选，缺省自动降级 Noop） |

> 前端不调用任何模型/检索，LLM 与检索全部由后端完成，API Key 只存服务端环境变量。

## 项目结构

```
├── backend/      # FastAPI 后端（app / tests / 数据库初始化脚本）
├── frontend/     # React 前端（src / e2e / tests）
├── docs/         # AI架构设计 / API文档 / 数据库设计 / 业务流程
├── specs/        # 各模块规格（spec / plan / tasks / research）
├── 运行指南.md    # 如何跑起来（前后端 + 模型/API 配置）
└── 项目说明.md    # 项目总览：技术选型 / RAG 架构 / 工程问题 / AI 工具体会
```

## 快速开始

前置依赖：Python 3.14、MySQL 8.0、Node.js ≥ 18。

```bash
# 后端
cd backend
.venv/Scripts/pip install -r requirements.txt
copy .env.example .env          # 填 MySQL / DeepSeek / SiliconFlow 密钥
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

- 健康检查：<http://localhost:8000/healthz>；API 文档：<http://localhost:8000/docs>
- **必须配置**：`DATABASE_URL`、`JWT_SECRET`、`DEEPSEEK_API_KEY`、`EMBEDDING_API_KEY`（详见 [运行指南.md](运行指南.md) 模型/API 配置章节）

## 测试

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit        # 200 单测（无需外部依赖）
cd backend && .venv/Scripts/python -m pytest tests/integration # 86 集成测试（需真实 MySQL）
cd frontend && npm run test:unit                               # 39 前端单测
cd frontend && npm run test:e2e                                # Playwright E2E
```

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [运行指南.md](运行指南.md) | 如何运行：前置依赖 / 前后端启动 / API Key 配置 / 常见问题 |
| [项目说明.md](项目说明.md) | 项目总览：技术选型原因、RAG 架构图、AI 工程问题处理、AI 编程工具心得 |
| [docs/AI架构设计.md](docs/AI架构设计.md) | 001 RAG 检索链路详细设计与关键决策 |
| [docs/API文档.md](docs/API文档.md) | 各模块接口契约 |
| [specs/](specs/) | 各模块规格（001 RAG 问答 … 008 埋点） |
