# 任务清单：知识库管理

> 依据 [spec.md](spec.md)、[plan.md](plan.md)、[data-model.md](data-model.md)、[contracts/knowledge-api.md](contracts/knowledge-api.md)、[research.md](research.md) 生成。
> 外部依赖说明：本特性复用 001 的 `backend/app/main.py`、`backend/app/db/session.py`（SQLAlchemy engine/Base）、`backend/app/vector_store/chroma.py`（Chroma 封装基础），以及 003 的 `backend/app/api/deps.py`（`get_current_user`）与 `backend/app/core/roles.py`（管理员角色校验）。上述文件为跨特性共享，本清单仅涉及 002 追加/扩展的部分。

---

## Phase 1 准备阶段（Setup）

- [ ] T001 [P] 创建后端目录骨架与空包：`backend/app/__init__.py`、`backend/app/api/__init__.py`、`backend/app/core/__init__.py`、`backend/app/db/__init__.py`、`backend/app/services/__init__.py`、`backend/app/services/knowledge/__init__.py`、`backend/app/vector_store/__init__.py`、`backend/tests/__init__.py`、`backend/tests/unit/__init__.py`、`backend/tests/integration/__init__.py`
- [ ] T002 [P] 创建 `backend/requirements.txt`，声明依赖：fastapi、uvicorn、sqlalchemy、pymysql、chromadb、sentence-transformers（bge-m3）、python-multipart、pydantic-settings、python-dotenv、pytest、httpx
- [ ] T003 [P] 创建 `backend/.env.example`，列出配置项模板：`max_upload_size_mb=20`、`chunk_size=500`、`chunk_overlap=80`、`parse_timeout_seconds=600`、`embedding_batch_size=16`，以及 MySQL 连接、Chroma 持久化目录、bge-m3 模型路径、JWT 密钥占位（密钥不落真实值，见宪法）
- [ ] T004 [P] 创建 `backend/tests/conftest.py` 测试夹具：SQLite 内存测试数据库（`db/session.py` 可切换）、临时目录 Chroma、FastAPI TestClient，供单元/集成测试复用

---

## Phase 2 基础阶段（Foundational）

- [ ] T005 [P] 在 `backend/app/db/models.py` 追加 SQLAlchemy 模型 `KnowledgeDoc`（id BIGINT PK、doc_name VARCHAR(255)、file_path VARCHAR(500)、status ENUM('处理中','就绪','失败') 默认'处理中'、fail_msg VARCHAR(1000) 可空、upload_time DATETIME）与 `ParseTask`（id PK、doc_id FK→knowledge_doc.id、status ENUM('处理中','成功','失败','已取消')、create_time、finish_time 可空、fail_msg 可空），并按 data-model.md 建立 `(status)`、`(upload_time)`、`(status)` 索引（复用 001 的 `db/session.py` Base）
- [ ] T006 [P] 在 `backend/app/core/config.py` 定义 pydantic-settings 配置类，读取 `max_upload_size_mb`、`chunk_size`、`chunk_overlap`、`parse_timeout_seconds`、`embedding_batch_size`（默认值见 contracts/knowledge-api.md 配置契约）
- [ ] T007 [P] 在 `backend/app/core/async_tasks.py` 实现后台任务提交薄接口（封装 FastAPI `BackgroundTasks`，暴露 `submit_background_task(func, *args)`），抽象层保证后续切换 Celery 仅改此模块
- [ ] T008 [P] 在 `backend/app/vector_store/chroma.py` 实现/扩展 Chroma collection 封装：`get_or_create_collection`、`add_chunks(doc_id, chunks)`（写入时附带 `metadata.doc_id`、`metadata.chunk_index`、`metadata.snippet`）、`delete_by_doc_id(doc_id)`（按 `doc_id` 确定性批量删除）、以及供 001 检索复用的 `query`（与 001 共享，新增 delete 能力满足 FR-005/FR-008）

**检查点**：基础就绪，可开始并行实施用户故事。

---

## 阶段 3：用户故事 1 - 上传文档并异步完成入库（优先级：P1）

**目标**：管理员上传 txt/md 文档后接口立即返回 202，系统后台完成「文本抽取 → 切分 → 向量化 → 写入 Chroma」，文档状态机由「处理中」收敛到「就绪」，可被问答链路检索命中。

**独立测试**：上传一份合法 txt 文档，可独立验证：接口即时返回、文档状态由「处理中」变为「就绪」、就绪后问答链路可命中该文档内容。

- [ ] T009 [P] [US1] 在 `backend/app/services/knowledge/validator.py` 实现上传校验：扩展名白名单（`.txt`/`.md`）、MIME 兜底、文件大小 ≤ `max_upload_size_mb`、去空白后非空；分别抛出/返回结构化错误码 `unsupported_format`、`empty_file`、`file_too_large`（对应 FR-001/FR-007/FR-010）
- [ ] T010 [P] [US1] 在 `backend/app/services/knowledge/file_store.py` 实现原始文件落盘：将上传文件保存到本地磁盘目录并返回存储路径（`file_path`）；封装为可切换对象存储的接口抽象（生产环境替换点）
- [ ] T011 [P] [US1] 在 `backend/app/services/knowledge/parser.py` 实现文本抽取：txt（utf-8）与 markdown（去 markdown 结构标记）抽取为纯文本；编码无法识别等异常抛出带可读信息的异常（供 fail_msg 使用）
- [ ] T012 [P] [US1] 在 `backend/app/services/knowledge/splitter.py` 实现文本切分：markdown 按 `##`/`###` 标题层级切分（一个章节一个 chunk，缺失时固定长度兜底）；txt 先递归粗切再按 embedding 相似度检测语义断点二次切分；兜底参数 `chunk_size=500`、`chunk_overlap=80`（自研可读，遵循宪法原则一）
- [ ] T013 [US1] 在 `backend/app/services/knowledge/ingester.py` 实现向量化与写入：bge-m3 单例复用，按 `embedding_batch_size`（默认 16）分批向量化后写入 Chroma；向量库内部 ID 确定性生成 `f"{doc_id}-{chunk_index}"`；每个 chunk 写入增强元数据（`doc_id`、`chunk_index`、`snippet`、`source_file`、`section`、`heading_path`、`category`、`version_date`、`source_priority`）；向量化前将父标题/章节标题拼接到文本开头（标题注入），表格内容转自然语言后再切分
- [ ] T014 [US1] 在 `backend/app/services/knowledge/pipeline.py` 编排流水线：解析 → 切分 → 向量化 → 入库；任一环节失败即标记文档 `失败` 并写入可读 `fail_msg`，同时按 `doc_id` 回滚该文档已写入的向量切片；全部成功则置文档 `就绪`（FR-004/FR-011）
- [ ] T015 [US1] 在 `backend/app/api/knowledge.py` 实现 `POST /api/knowledge/upload`（校验 → 存原始文件 → 写 KnowledgeDoc「处理中」+ ParseTask → 通过 `core/async_tasks.py` 提交后台任务 → 返回 202 与 `doc_id`/`doc_name`/`status`/`upload_time`）与 `GET /api/knowledge/{doc_id}`（详情含 `fail_msg`，不存在返回 404 `doc_not_found`）；包含 Pydantic 响应模型与错误码映射（`unsupported_format`/`empty_file`/`file_too_large`/`doc_not_found`），并挂 003 的管理员鉴权依赖（`api/deps.py` + `core/roles.py`）
- [ ] T016 [US1] 在 `backend/app/main.py` 注册 knowledge 路由（`app.include_router`），使 `/api/knowledge/*` 端点对外可用（共享文件，与 001 路由注册协调）
- [ ] T017 [P] [US1] 在 `backend/tests/unit/test_validator.py` 编写单元测试：非法格式（`.exe`/`.zip`）、空文件/全空白、超限（>20MB）分别被拒绝并返回正确错误码
- [ ] T018 [P] [US1] 在 `backend/tests/unit/test_parser_splitter.py` 编写单元测试：txt/md 文本抽取正确、markdown 按标题切分、缺失标题与超长章节走固定长度兜底、chunk_size/chunk_overlap 参数生效
- [ ] T019 [P] [US1] 在 `backend/tests/unit/test_state_machine.py` 编写单元测试：状态机 `处理中 → 就绪` 与 `处理中 → 失败` 单向收敛、失败时 fail_msg 非空且回滚已写切片
- [ ] T020 [US1] 在 `backend/tests/integration/test_ingest_flow.py` 编写集成测试：真实 Chroma（临时目录）+ SQLite 覆盖「上传 → 处理中 → 就绪」关键链路（含就绪后检索命中），并注入解析异常验证失败回滚、无残留半成品

**检查点**：用户故事 1 此刻可独立运行与验证（上传 → 就绪 → 检索命中）。

---

## 阶段 4：用户故事 2 - 查看知识库列表与处理状态（优先级：P2）

**目标**：管理员查看知识库列表，看到每份文档的名称、上传时间与处理状态；失败文档展示可读失败原因，便于重传或排查。

**独立测试**：上传多份文档（含一份故意失败的文件），可独立验证：列表正确展示每份文档的名称、上传时间与状态；失败文档展示可读原因。

- [ ] T021 [US2] 在 `backend/app/api/knowledge.py` 实现 `GET /api/knowledge/list`：分页参数 `page`（默认 1）、`page_size`（默认 20），按 `upload_time` 排序，返回 `total` 与 `items`（每项含 `doc_id`/`doc_name`/`status`/`upload_time`/`fail_msg`，失败项 fail_msg 非空）；挂管理员鉴权依赖（`api/deps.py` + `core/roles.py`）

**检查点**：用户故事 2 此刻可独立运行与验证（列表正确反映名称/时间/状态，失败文档展示可读原因）。

---

## 阶段 5：用户故事 3 - 删除文档并级联清理（优先级：P3）

**目标**：管理员删除一份文档，系统同步清理原始文件、文档元数据与全部向量切片，删除后该文档内容不再被检索命中。

**独立测试**：删除一份已就绪文档，可独立验证：知识库列表中该文档消失、删除后问答链路检索不再命中其内容。

- [ ] T022 [P] [US3] 在 `backend/app/services/knowledge/cleaner.py` 实现事务性级联删除：按 `doc_id` 删除 Chroma 切片（`delete_by_doc_id`）→ 删除 MySQL 元数据 → 删除本地原始文件；对「处理中」文档标记取消（ParseTask 置「已取消」）；任一步骤失败回滚（FR-008 宪法原则五硬性约束）
- [ ] T023 [US3] 在 `backend/app/api/knowledge.py` 实现 `DELETE /api/knowledge/{doc_id}`：调用 `cleaner.py` 级联清理，成功返回 204、不存在返回 404；对「处理中」文档触发取消标记；挂管理员鉴权依赖
- [ ] T024 [P] [US3] 在 `backend/app/services/knowledge/pipeline.py` 增加取消检测：后台任务完成回调处检查 ParseTask 是否「已取消」，若已取消则不重写文档状态、不重写入库，直接完成清理，避免删除与解析并发产生孤儿切片
- [ ] T025 [US3] 在 `backend/tests/integration/test_delete_cascade.py` 编写集成测试：删除已就绪文档后检索命中率降为 0、Chroma 无该 `doc_id` 孤儿切片；并发场景（处理中文档删除）级联清理一致、不残留孤儿切片

**检查点**：用户故事 3 此刻可独立运行与验证（删除后列表消失、检索不再命中、无孤儿切片）。

---

## 阶段 6：打磨与横切关注点（Polish & Cross-Cutting Concerns）

- [ ] T026 [P] 在 `backend/app/core/async_tasks.py` 实现超时守卫：周期性扫描 `status='处理中'` 且超过 `parse_timeout_seconds`（默认 600s）的 ParseTask，将其与关联文档置为「失败」并记录「处理超时」原因，保证异常中断（进程崩溃）也能收敛、不长期停留「处理中」（SC-004）
- [ ] T027 [P] 完善 `backend/.env.example`：核对并补充所有配置项（`max_upload_size_mb`/`chunk_size`/`chunk_overlap`/`parse_timeout_seconds`/`embedding_batch_size`）的中文注释说明；核对 `specs/002-knowledge-base/quickstart.md` 中场景 1/2/3 与边界用例的 curl 命令可执行
- [ ] T028 端到端验收：按 `specs/002-knowledge-base/quickstart.md` 运行全部验证场景与边界用例（非法格式/空文件/超限/部分切片失败/处理中删除/未授权），核对 SC-001~SC-007（上传 2 秒返回、100KB 文档 2 分钟内就绪、状态无卡死、删除后命中率 0）

---

## 依赖关系与执行顺序

- Phase 1（T001-T004）与 Phase 2（T005-T008）必须先于所有用户故事；Phase 2 的模型/配置/后台任务/Chroma 封装是全部故事的共同前置。
- 用户故事 1（T009-T020）内部依赖链：`validator/file_store/parser/splitter`（可并行）→ `ingester` → `pipeline` → `api/knowledge.py`（upload/detail）→ `main.py` 注册 → 测试。T013 依赖 T012 的切分输出契约；T014 依赖 T011/T012/T013；T015 依赖 T009/T010/T014；T020 依赖 T014/T015。
- 用户故事 2（T021）仅依赖 Phase 2 与 T015 已实现的 detail 端点/`fail_msg` 字段，可独立于 US1 其余部分实施（但需 US1 的 upload 端点以产生可观察数据）。
- 用户故事 3（T022-T025）依赖 Phase 2 的 Chroma `delete_by_doc_id` 与 US1 的 `pipeline.py`；`cleaner` 与 `pipeline` 取消检测（T022/T024）可并行。
- 打磨阶段（T026-T028）须在所有故事后执行。

## 并行机会

- Setup（T001-T004）与 Foundational（T005-T008）各任务触及不同文件，可整体并行。
- US1 中 T009/T010/T011/T012 四个纯函数模块相互独立，可并行开发。
- 测试任务 T017/T018/T019 与被测模块完成后可并行编写。
- US2（T021）与 US3（T022/T024）在 US1 落地后可与 US1 的收尾测试并行推进。
- US3 的 `cleaner.py`（T022）与 `pipeline.py` 取消检测（T024）分属不同文件，可并行。

## 实施策略

- **MVP 优先**：先交付 Phase 1 + Phase 2 + 用户故事 1（T001-T020），即「上传 → 异步解析/切分/向量化 → 就绪 → 可检索」的核心闭环，即 MVP 范围。
- **增量交付**：MVP 后按 P2 → P3 顺序追加列表（US2）与删除级联（US3），每个故事独立可测、独立上线，不阻塞前序已交付能力。
- **并行团队策略**：MVP 落地后，可将 US2 列表端点、US3 删除级联、US1 剩余集成测试三条线并行分配给不同人员；跨特性共享文件（`main.py`、`db/models.py`、`vector_store/chroma.py`、`api/deps.py`）的改动需与 001/003 协调合并，避免冲突。
