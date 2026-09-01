# 实施计划：意图识别（三层漏斗）

**分支**：`006-intent-recognition` | **日期**：2026-08-29 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/006-intent-recognition/spec.md` 的功能规格

**说明**：本文件由 `/speckit-plan` 命令填充，其定义描述了执行工作流。

## 摘要

本特性实现用户问题意图识别模块：一条**三层漏斗链路**（前置校验规则层 → 小模型识别层 → 大模型兜底层），将用户输入识别为**产品咨询 / 售后 / 闲聊 / 投诉**四类意图之一，结果写入 `message.intent_label` 并按意图路由分发。

技术要点：前置校验层**零模型推理**——文本归一化 + AC 自动机关键词匹配（`ahocorasick-ng` 库，最长匹配 + 词边界薄封装）+ 句式模板解析（`pyparsing` 库），命中即终止、不消耗算力；小模型层用 DeepSeek-R1-0528-Qwen3-8B 分类，配合**正向校准（标注数据约束）+ 反向校准（负样本校验）**与**高/低双阈值**（≥0.9 直接输出 / [0.6,0.9) 反问澄清 / <0.6 流转大模型）；大模型层 Few-shot + 强制 JSON 结构化输出兜底。模型密钥经 `.env` 环境变量占位，用户后续填写。

集成方式：在 001 RAG 问答链路「输入校验后、向量化前」插入 `recognize()`，闲聊/投诉不进入知识库检索，产品咨询/售后走 RAG。规则层匹配用成熟算法库（ahocorasick-ng / pyparsing）薄封装，核心编排与归一化自研，符合宪法原则一（见宪法核验）。

## 技术上下文

**语言/版本**：Python 3.14（FastAPI + uvicorn）

**主要依赖**：fastapi、httpx（模型 API 调用）、**pyahocorasick 2.3.1**（关键词多模式串匹配，最长匹配；ahocorasick-ng 无 3.14/Windows 发行版，改用同 API 上游包 pyahocorasick 2.3.1）、**pyparsing**（句式模板解析）、pyyaml（词库/句式模板/负样本配置）、pydantic-settings + python-dotenv（配置/密钥）；测试 pytest

**存储**：无新增业务表。复用 001/004 的 `message.intent_label` 字段；配置分三层——`.env`（密钥类）、`system_config` 表（阈值等运行时参数）、YAML/JSON 配置文件（词库/句式模板/负样本库）

**测试**：pytest（unit + integration；覆盖关键词匹配（pyahocorasick）、句式模板（pyparsing）、归一化、双阈值、反向校准、三层编排、闲聊不检索路由、密钥未配置降级）

**目标平台**：Linux 服务器（后端服务，本地沙箱可运行）

**项目类型**：web-service（后端模块，作为内部服务集成进 001 RAG 链路）

**性能目标**：规则层命中识别附加延迟 < 10ms（零模型成本，SC-001）；规则层 + 小模型命中路径附加延迟 ≤ 50ms（SC-006）；大模型兜底 3 秒内返回可解析结果（SC-006）

**约束**：四类意图（产品咨询/售后/闲聊/投诉 + 未识别兜底）；规则层命中不调用模型；小模型默认 `DeepSeek-R1-0528-Qwen3-8B`（开源蒸馏权重，经自建/第三方 OpenAI 兼容端点访问，客户端薄且可配置）、大模型可配置；结构化输出仅 `json_object`、schema 客户端自验；密钥仅存 `.env` 且提供 `.env.example` 占位；闲聊/投诉路由不进入知识库检索（SC-007）

**规模/范围**：v1 内置默认词库/句式模板/负样本库与阈值基线（0.9/0.6），后续用真实流量扩充校准；模型自评反向校准通道默认关闭（可选开关）；无独立 HTTP 意图接口对普通用户开放（内部服务 + 管理员调试接口）

## 宪法核验

*门禁：Phase 0 研究前必须通过，Phase 1 设计后再核验。*

| 宪法原则 | 本特性落点 | 状态 |
|---|---|---|
| 原则一：RAG 核心链路必须可读可控 | 意图识别辅助匹配组件选用成熟算法库（ahocorasick-ng / pyparsing）——两者原理清晰（goto/failure/output 三表；声明式文法）、团队可解释，非「未理解内部逻辑的黑盒高阶链」；原则一明示的切分/Embedding/检索/Prompt 组装核心链路仍自研；模型客户端用 httpx 直连 OpenAI 兼容协议，无厂商锁定 | ✅ 通过（决策理由见 research §1/§2） |
| 原则二：禁止编造与幻觉抑制 | 闲聊/投诉不检索知识库、用模板/转人工话术；识别失败降级「未识别」不硬猜；反向校准抑制小模型乱打标签 | ✅ 通过 |
| 原则三：AI 能力仅在服务端执行 | 小/大模型调用全部后端执行，前端仅通过问答链路间接获得意图标签 | ✅ 通过 |
| 原则五：硬性业务约束 | 模型密钥仅存 `.env`、`.env.example` 提供占位、真实密钥不提交仓库（FR-014）；识别附加延迟不拖慢主链路（SC-006） | ✅ 通过 |
| 原则四：流式输出与异步化 | 意图识别是问答链路前置步骤，识别完成后再进入流式问答；识别本身为轻量同步调用，不违反异步化要求 | ✅ 通过 |

无门禁违规，无需 Complexity Tracking。

## 项目结构

### 文档（本特性）

```text
specs/006-intent-recognition/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（/speckit-plan 输出）
├── data-model.md        # Phase 1 输出（/speckit-plan 输出）
├── quickstart.md        # Phase 1 输出（/speckit-plan 输出）
├── contracts/           # Phase 1 输出（/speckit-plan 输出）
└── tasks.md             # Phase 2 输出（/speckit-tasks 输出 - 不由 /speckit-plan 创建）
```

### 源码（仓库根目录）

后端结构沿用 001 规划，本特性新增 `intent` 模块。

```text
backend/
├── app/
│   ├── api/
│   │   ├── intent_debug.py      # POST /api/intent/debug 管理员联调接口（返回三层各层结果）
│   │   └── deps.py              # 复用 003 鉴权依赖（admin 角色校验）
│   ├── core/
│   │   └── config.py            # 追加 intent 配置节：阈值/模型名/词库与模板文件路径
│   ├── intent/                  # ★ 本特性核心模块
│   │   ├── __init__.py
│   │   ├── schema.py            # IntentCategory 枚举 / IntentResult / HandlerKey
│   │   ├── service.py           # 三层漏斗编排 recognize()：normalize→rules→small_model→fallback→route
│   │   ├── normalize.py         # 文本归一化（全角→半角/去符号/繁简常用字/形近字纠错）
│   │   ├── rules/
│   │   │   ├── __init__.py
│   │   │   ├── keyword_store.py # 词库加载（词→意图映射，YAML/JSON）
│   │   │   ├── ac_automaton.py  # AC 自动机关键词匹配（ahocorasick-ng 封装：最长匹配 + 词边界薄校验）
│   │   │   └── template_patterns.py # 句式模板解析（pyparsing 声明式文法 + 命名结果）
│   │   ├── small_model/
│   │   │   ├── __init__.py
│   │   │   ├── client.py        # DeepSeek 小模型薄客户端（OpenAI 兼容，json_object 输出 + 客户端 schema 校验 + 超时/429退避 + usage 落库）
│   │   │   ├── calibrate.py     # 正向校准（标注基线）与反向校准（负样本校验，可选模型自评）
│   │   │   └── threshold.py     # 高/低双阈值判定、临界带二次采样一致性、澄清决策
│   │   ├── fallback/
│   │   │   ├── __init__.py
│   │   │   ├── client.py        # 大模型客户端 + Few-shot prompt 组装 + JSON 强制解析/降级 + usage 落库
│   │   │   └── few_shot.py      # Few-shot 样例常量（每类意图至少 1 例 + 歧义例）
│   │   └── router.py            # 意图→handler 路由映射（依赖注入，001 提供 rag handler）
│   └── ...
└── tests/
    ├── unit/
    │   └── intent/
    │       ├── test_ac_automaton.py       # ahocorasick-ng 关键词匹配（最长匹配/词边界）
    │       ├── test_normalize.py          # 全角/繁简/形近/符号
    │       ├── test_template_patterns.py  # pyparsing 句式模板命中与意图标签
    │       ├── test_threshold.py          # 高/中/低阈值三条判定路径
    │       └── test_calibrate.py          # 反向校准负样本拦截
    └── integration/
        └── intent/
            ├── test_intent_pipeline.py # 三层漏斗全链路（mock 模型 API，四条路径）
            └── test_intent_route.py    # 闲聊不检索/投诉转人工/未识别降级路由断言
```

**结构决策**：意图识别作为独立后端模块 `app/intent/`，与 RAG 主链路（001）通过 `router.py` 的依赖注入解耦——001 在「输入校验后、向量化前」注入调用 `recognize()`，按返回结果决定是否检索与标注。规则层三件套（normalize/ac_automaton/template_patterns）与模型层（small_model/fallback）分目录，符合「零模型 vs 有模型」的层级边界，便于按层测试与替换；规则层内部把库封装收敛在 `ac_automaton.py` / `template_patterns.py` 两个薄适配模块内，若后续要换库或改自研，只改这两处。配置分三层（`.env`/`system_config`/配置文件）满足 FR-014 与运营可调需求。

## 复杂度跟踪

> 仅当宪法核验存在需正当化的违规时填写

无违规，不适用。
