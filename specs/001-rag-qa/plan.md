# 实施计划：RAG 智能问答链路

**分支**：`001-rag-qa` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/001-rag-qa/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现 RAG 智能问答的核心闭环：输入校验（≤500 字 + 每日 100 次配额）→ 读取会话最近 N 轮历史 → Query 向量化 → 向量检索（相似度阈值过滤 + top-k 召回）→ 无命中走固定兜底话术（禁止编造）→ Prompt 组装（System Prompt + 带编号来源的知识片段 + 历史 + 问题）→ LLM 流式调用 → SSE 以 `data`/`meta`/`finish`/`error` 事件流式返回（token + 引用来源 + 结束 + 错误）→ 会话消息持久化 → 输出后来源校验。

技术方案遵循宪法与初步方案：Python 3.11 + FastAPI，SQLAlchemy + MySQL 8.0 存元数据，Chroma 存向量，bge-m3 本地 Embedding，Ollama Qwen2 提供 LLM。RAG 核心链路（切分/向量化/检索/Prompt 组装/SSE 封装）全部自研可读，不引入黑盒 LangChain 链。LLM 超时 / 429 限流以 SSE `error` 事件友好返回。

## 技术上下文

**语言/版本**：Python 3.11（FastAPI + uvicorn）

**主要依赖**：fastapi、uvicorn、sqlalchemy、pymysql、chromadb、sentence-transformers（bge-m3）、httpx（调用 Ollama 兼容接口）、pydantic-settings、python-dotenv、pytest

**存储**：MySQL 8.0（会话/消息/每日配额等业务元数据）+ Chroma 本地文件向量库（切片向量，metadata 关联 doc_id）

**测试**：pytest（unit + integration，集成测试覆盖完整 RAG 链路、SSE 事件协议、异常场景）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端 API + SSE 流）

**性能目标**：提交到首个回答 token 的首字延迟 ≤3 秒（SC-001）；回答流式逐块输出（SC-002）

**约束**：单条提问 ≤500 字；每日配额默认 100 次/用户/天（可配置）；SSE 流式输出禁止整段返回；上下文超长执行截断策略；LLM 超时/限流以错误事件返回（≤5 秒内收到明确错误）；所有 API 密钥走环境变量，禁止硬编码

**规模/范围**：单机沙箱可运行（MySQL + Chroma + Ollama 本地模型）；生产组件切换留迁移方案；意图识别、追问建议、重排序等加分项不在本特性范围

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 原则一：RAG 核心链路可读可控 | 切分、Embedding、检索、Prompt 组装、SSE 封装全部自研模块化，不引入黑盒 LangChain 链；每层可解释可调优 | ✅ 通过 |
| 原则二：禁止编造与幻觉抑制 | FR-005 空检索固定兜底话术；FR-006 System Prompt 强约束；FR-008 `meta` 事件携带引用来源（文档名+片段摘要）；FR-013 输出后来源校验，检出超范围标记提示 | ✅ 通过 |
| 原则三：AI 能力仅在服务端执行 | 检索与 LLM 调用全部后端完成，前端仅通过 REST/SSE 交互 | ✅ 通过 |
| 原则四：流式输出与耗时任务异步化 | FR-007 SSE 逐块返回；FR-009 统一事件协议 `data`/`meta`/`finish`/`error`（文档解析异步属 002 特性） | ✅ 通过 |
| 原则五：硬性业务约束 | FR-001 500 字上限；FR-002 每日配额；FR-003 携带最近 N 轮历史；FR-011 超长截断（优先丢最早历史、保留压缩知识）；.env.example 提供密钥模板 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/001-rag-qa/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

项目为前后端分离的 Web 应用，本特性仅涉及后端；采用 Option 2 的后端结构。

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用装配、路由注册、SSE 端点
│   ├── config.py            # .env 配置加载（pydantic-settings）
│   ├── api/
│   │   ├── __init__.py
│   │   └── chat.py          # POST /api/chat/stream 流式问答端点
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py    # 统一业务异常（长度超限/配额耗尽/检索为空）
│   │   └── logging.py       # 日志模块
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py       # SQLAlchemy engine / session 管理
│   │   └── models.py        # Session / Message / UserQuotaDaily 模型（本特性涉及）
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── chat.py          # 请求/SSE 事件 Pydantic 结构
│   ├── services/
│   │   ├── __init__.py
│   │   ├── validation.py    # 长度校验、每日配额校验与计数
│   │   ├── history.py       # 读取最近 N 轮历史 + 上下文截断
│   │   └── rag/
│   │       ├── __init__.py
│   │       ├── embedding.py # bge-m3 向量化封装（Query）
│   │       ├── retriever.py # Chroma 检索：阈值过滤 + top-k 召回
│   │       ├── prompt.py    # System Prompt + 知识片段编号 + 历史组装 + 截断
│   │       ├── llm.py       # Ollama 流式调用、超时/429 异常捕获
│   │       ├── sse.py       # data/meta/finish/error 事件封装
│   │       └── postcheck.py # 输出后来源校验（幻觉检出标记）
│   └── vector_store/
│       ├── __init__.py
│       └── chroma.py        # Chroma client / collection 封装（按 doc_id 关联）
└── tests/
    ├── __init__.py
    ├── conftest.py          # 测试数据库 / Chroma 隔离夹具
    ├── unit/
    │   ├── __init__.py
    │   ├── test_validation.py
    │   ├── test_history_truncation.py
    │   ├── test_prompt.py
    │   └── test_sse_events.py
    └── integration/
        ├── __init__.py
        └── test_rag_chat_flow.py   # 完整链路：问答→流→引用→持久化→兜底→异常
```

**结构决策**：采用后端单项目结构（`backend/app` 模块化），RAG 链路按职责拆分为 `services/rag/` 子模块（embedding / retriever / prompt / llm / sse / postcheck），满足宪法「核心链路自研可读、每层可解释」要求，便于单层调优与独立测试。向量库访问统一收敛到 `vector_store/`，隔离 Chroma 细节、便于后续切换生产向量库。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
