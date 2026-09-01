# 后端（Backend）

> AI 智能客服系统后端。已实现 001 RAG 智能问答、002 知识库、003 注册登录鉴权、004 会话与消息、005 用户反馈、006 意图识别、008 链路埋点。

## 技术栈

- **Web**：Python 3.14 + FastAPI（异步原生，对 SSE 流式输出友好）+ uvicorn
- **数据库**：SQLAlchemy + pymysql（MySQL 8.0）
- **向量库**：Chroma（本地文件模式，`./chroma_data`）
- **检索（001）**：向量召回 + jieba 中文分词 BM25 + RRF 融合 + 可选 bge-reranker-v2-m3 精排
- **对话 LLM**：httpx 直连 OpenAI 兼容协议，DeepSeek 官方 API（001 对话 + 006 意图兜底共用一份配置）
- **Embedding**：SiliconFlow 云端 bge-m3（OpenAI 兼容 `/embeddings`，默认）；亦支持本地 sentence-transformers / Ollama 后端
- **鉴权（003）**：pyjwt（JWT）+ bcrypt（密码哈希，直接调用、不依赖 passlib）
- **意图识别（006）**：规则层（pyahocorasick 多模式匹配 + pyparsing 句式模板 + pyyaml 词库）+ 可选小模型层 + 大模型兜底，高/低双阈值 + 负样本反向校准
- **后台任务（002）**：FastAPI `BackgroundTasks` 进程内执行，**无需 Redis / Celery**

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `app/main.py` | FastAPI 应用装配：CORS、全局异常、路由注册、启动初始化（自动建表 / 预置管理员 / Reranker 预热 / 僵尸任务清扫） |
| `app/config.py` | 统一配置（pydantic-settings 加载 `.env`；运行时热调参数由 `system_config` 表覆盖） |
| `app/api/` | 路由层：`auth` / `session` / `knowledge` / `chat` / `feedback`（`/api/message`）/ `intent` / `trace` / `admin` |
| `app/core/` | 鉴权守卫、安全（JWT / 密码哈希）、登录防爆破、角色、日志、业务异常 |
| `app/db/` | SQLAlchemy 模型与会话（`models.py` / `session.py`） |
| `app/schemas/` | Pydantic 请求/响应模型 |
| `app/services/` | 业务层：鉴权、知识库（解析/切分/向量化/入库）、RAG（检索/精排/LLM/SSE）、意图、会话、反馈、配置、链路埋点 |
| `app/intent/` | 006 意图识别：规则引擎 / 小模型 / 大模型兜底 / 归一化 / 路由 |
| `app/vector_store/` | Chroma 向量库封装（`chroma.py`） |
| `config/` | 意图规则层 YAML 词库（关键词 / 句式模板 / 负样本） |
| `storage/uploaded/` | 知识库原始上传文件存储（运行时数据，不进仓库） |
| `chroma_data/` | Chroma 本地向量数据（运行时数据，不进仓库） |
| `数据库初始化脚本/init.sql` | 建表语句 + `system_config` 预置默认配置 |
| `requirements.txt` | Python 依赖清单 |
| `.env` / `.env.example` | 环境变量（API Key 等，`.env` 被 gitignore） |
| `tests/` | pytest 单元 / 集成测试 |

## 启动说明

### 1. 安装依赖（首次）

```bash
cd backend
.venv/Scripts/pip install -r requirements.txt        # Windows（Linux/macOS 用 python -m pip）
```

> 建议先创建并激活虚拟环境（Python 3.14）。`requirements.txt` 中 `sentence-transformers` / `torch` 按注释为可选（仅 Reranker 精排 / 本地 Embedding 需要）。

### 2. 配置环境变量

```bash
copy .env.example .env       # Windows；Linux/macOS 用 cp .env.example .env
```

按 `.env.example` 顶部说明填写真实值（必填项见下方「API Key / 模型配置方式」）。

### 3. 初始化数据库

- MySQL 8.0 中执行 `数据库初始化脚本/init.sql` 建库建表（业务表 + `system_config` 预置配置）。
- 业务表也可由应用启动时自动建表（`create_all`）；`system_config` 默认配置仍需 SQL 预置。
- 管理员账号不写死在 SQL：启动时按 `.env` 的 `ADMIN_ACCOUNT` / `ADMIN_PASSWORD` 自动预置 admin 角色。

### 4. 启动服务

```bash
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000   # 生产/局域网
# 开发热重载：
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

- 健康检查：<http://localhost:8000/healthz>
- API 文档（Swagger UI）：<http://localhost:8000/docs>

### 5. 后台任务说明

002 知识库上传后的「解析 → 切分 → 向量化 → 入库」由 FastAPI `BackgroundTasks` **进程内**执行，启动时自动运行僵尸任务清扫协程，**无需单独启动 Redis / Celery worker**。

## API Key / 模型配置方式

所有密钥仅通过环境变量（`.env`）配置，禁止硬编码或提交仓库（`.env` 已 gitignore）。复制 `.env.example` 为 `.env` 后填写：

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | ✅ | MySQL 连接串：`mysql+pymysql://<user>:<pass>@<host>:<port>/<db>?charset=utf8mb4` |
| `JWT_SECRET` | ✅ | JWT 签名密钥，生产 ≥32 字节随机串（默认值仅开发用） |
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek 官方 API 密钥（001 对话 + 006 意图兜底共用） |
| `EMBEDDING_API_KEY` | ✅ | SiliconFlow API 密钥（Embedding，默认 `EMBEDDING_BACKEND=openai_compat`） |
| `ADMIN_ACCOUNT` / `ADMIN_PASSWORD` | — | 预置管理员账号/密码，生产必须修改 |
| `LLM_MODEL` / `LLM_BASE_URL` | — | 对话 LLM 统一配置（默认 `deepseek-v4-flash` / `https://api.deepseek.com`） |

- **LLM**：`LLM_BACKEND=deepseek`（默认，OpenAI 兼容 API）调用 DeepSeek 官方；如需本地可改 `ollama` + `OLLAMA_BASE_URL` / `OLLAMA_CHAT_MODEL`。
- **Embedding**：默认走 SiliconFlow 云端 bge-m3（`EMBEDDING_BACKEND=openai_compat`，`EMBEDDING_API_MODEL=BAAI/bge-m3`）；可改 `local`（本地 sentence-transformers）或 `ollama`（本机 Ollama 提供 bge-m3）。
- **Reranker 精排（可选）**：混合检索主链路（向量 + BM25 + RRF）开箱即用，无需精排模型。如需精排，安装 `sentence-transformers` + `torch`，`.env` 置 `RAG_RERANKER_ENABLED=true`、`RAG_RERANKER_MODEL=BAAI/bge-reranker-v2-m3`；未安装时自动降级为 NoopReranker，不影响主链路。
- **意图识别**：`INTENT_ENABLED=true` 开启；小模型层可用独立 `SMALL_MODEL_*` 指向第三方端点，三项均空时直接流转大模型兜底。
- **链路埋点（008）**：`TRACE_ENABLED` / `TRACE_FLUSH_ENABLED` 总开关，后台批量落库，`/api/trace` 查询。
- 各配置项完整说明见 `.env.example` 注释与 `app/config.py`。

## 测试

```bash
.venv/Scripts/python -m pytest tests/unit       # 单元测试（200 用例，无需外部依赖）
.venv/Scripts/python -m pytest tests/integration   # 集成测试（86 用例，需真实 MySQL，可选 DeepSeek/Embedding）
```

- 集成测试按 `pytest.ini` 走真实 MySQL；涉及 LLM / Embedding 的用例在后端配置好 `.env` 后跑全链路。
- 测试配置见 `tests/conftest.py`（独立测试库 / 环境变量覆盖）。

## 常用接口

| 模块 | 前缀 | 说明 |
| --- | --- | --- |
| 鉴权 | `/api/auth` | 注册 / 登录 / 登出 |
| 会话 | `/api/session` | 会话列表 / 创建 / 重命名 / 删除（级联清消息） |
| 消息 | `/api/session/*/messages` | 历史消息分页 |
| 知识库 | `/api/knowledge` | 文档上传 / 列表 / 状态 / 删除 |
| 问答 | `/api/chat/stream` | SSE 流式问答（`data/meta/finish/error` 协议） |
| 反馈 | `/api/message` | 消息点赞/点踩反馈 |
| 意图 | `/api/intent` | 意图识别调试 |
| 埋点 | `/api/trace` | 链路埋点查询 |
| 管理 | `/api/admin` | 管理端接口 |
