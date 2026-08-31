# 实施计划：知识库管理

**分支**：`002-knowledge-base` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/002-knowledge-base/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现知识库文档的全生命周期管理：上传（校验格式/大小/空文件，立即返回成功）→ 后台异步执行「文本抽取 → 切分 → 向量化 → 写入 Chroma」→ 文档状态机（`处理中 / 就绪 / 失败`）驱动收敛 → 知识库列表（名称/上传时间/状态/失败原因）→ 事务性级联删除（原始文件 + MySQL 元数据 + 向量切片）。

技术方案遵循宪法与初步方案：FastAPI + SQLAlchemy（MySQL 8.0）存元数据，Chroma 存切片向量（metadata.doc_id 与 MySQL 关联），bge-m3 向量化，FastAPI `BackgroundTasks` 进程内后台异步执行（任务定义于 `services/knowledge/pipeline.py`，进程内执行、免 Redis/Celery）；后台提交经 `core/async_tasks.py::run_in_background` 薄接口，未来需扩展时切换到 Celery + Redis 仅改该接口实现。配套「僵尸任务清扫」双层防卡死（启动清扫 + 运行期 `asyncio.create_task` 周期循环，无需 celery-beat）。切分与向量化自研可读（宪法原则一），删除级联依 `doc_id`（宪法原则五硬性约束）。

## 技术上下文

**语言/版本**：Python 3.14（FastAPI + uvicorn）

**主要依赖**：fastapi、sqlalchemy、pymysql、chromadb、sentence-transformers（bge-m3）、python-multipart（文件上传）、pathlib、pytest

**外部依赖（可选/废弃）**：celery、redis —— 当前改用 FastAPI `BackgroundTasks` 进程内执行，不再必需；保留作为未来扩展回 Celery + Redis 的备选（见 research §1），`core/async_tasks.py` 薄接口为此预留。

**存储**：MySQL 8.0（KnowledgeDoc / ParseTask 元数据）+ Chroma 本地文件向量库（ContentChunk）+ 本地磁盘文件存储（原始文档，生产可换对象存储）

**测试**：pytest（unit + integration；集成测试覆盖「解析→向量化入库」关键链路、状态机收敛、删除级联、失败回滚）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端 REST API + 后台任务）

**性能目标**：上传接口 2 秒内返回成功（SC-001）；100KB 以内文档 2 分钟内转「就绪」（SC-002）

**约束**：txt/md 必选格式、pdf 可选；单文件上限可配置默认 20MB；空文件拒绝；上传后立即返回不阻塞；状态机必须收敛「就绪/失败」；任一环节失败整份失败并回滚切片；删除必须级联清理；仅认证且有权限（管理员）用户可管理

**规模/范围**：单机沙箱（MySQL + Chroma + Redis + 本地磁盘）；生产对象存储留迁移方案；pdf 解析、内容去重、多知识库不在 v1 范围

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 原则一：RAG 核心链路可读可控 | 文本切分与向量化（Embedding）自研模块化（`services/knowledge/splitter.py`、`ingester.py`），不引入黑盒链；Chroma 写入由 `vector_store/` 封装 | ✅ 通过 |
| 原则四：流式输出与耗时任务异步化 | FR-002 上传立即返回，解析/切分/向量化由 FastAPI `BackgroundTasks` 进程内后台异步执行；HTTP 先返回，DB 状态机记录；配套僵尸任务清扫防卡死（见 §1） | ✅ 通过 |
| 原则五：硬性业务约束 | FR-008 删除文档 MUST 同步删除对应向量切片（依 `doc_id` 级联），删除后立即不再命中；密钥走 `.env.example` | ✅ 通过 |
| 安全与合规 | 管理操作仅认证且有权限用户（FR-009）；向量库内部 ID 与 MySQL 文档 ID 建立可追溯索引对（metadata.doc_id） | ✅ 通过 |
| 开发流程质量门槛 | 「文档解析→向量化入库」关键链路集成测试（必须）；失败回滚不残留半成品 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/002-knowledge-base/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

后端结构沿用 001 规划，本特性新增知识库管理模块。

```text
backend/
├── app/
│   ├── api/
│   │   └── knowledge.py        # POST /api/knowledge/upload、GET /api/knowledge/list、
│   │                           # GET /api/knowledge/{id}、DELETE /api/knowledge/{id}
│   ├── core/
│   │   ├── config.py           # 文件大小上限等配置（.env）
│   │   └── async_tasks.py      # 后台任务提交薄接口（run_in_background → BackgroundTasks.add_task；未来可切 Celery .delay()）
│   ├── db/
│   │   └── models.py           # 追加 KnowledgeDoc、ParseTask 模型
│   ├── services/
│   │   └── knowledge/
│   │       ├── __init__.py
│   │       ├── validator.py    # 格式/大小/空文件校验
│   │       ├── file_store.py   # 原始文件本地磁盘读写（生产可换对象存储）
│   │       ├── parser.py       # txt/md 文本抽取
│   │       ├── splitter.py     # 文本切分（chunk_size/overlap 可配置，自研）
│   │       ├── ingester.py     # 向量化 + 写入 Chroma（含 metadata.doc_id / snippet）
│   │       ├── pipeline.py     # 解析→切分→向量化→入库编排；任一环节失败回滚
│   │       └── cleaner.py      # 删除级联：原始文件 + 元数据 + 向量切片
│   └── vector_store/
│       └── chroma.py           # Chroma collection 封装（按 metadata.doc_id 删除/查询）
└── tests/
    ├── unit/
    │   ├── test_validator.py   # 格式/空文件/超限拒绝
    │   ├── test_parser_splitter.py
    │   └── test_state_machine.py
    └── integration/
        ├── test_ingest_flow.py # 上传→处理中→就绪 关键链路
        └── test_delete_cascade.py  # 删除→检索不再命中，无孤儿切片
```

**结构决策**：沿用 001 的后端模块化结构，知识库逻辑收敛到 `services/knowledge/`，处理流水线独立成 `pipeline.py`（明确回滚边界），删除级联独立成 `cleaner.py`（事务边界清晰）。Chroma 访问继续走 `vector_store/chroma.py` 统一封装，与 001 检索共用。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
