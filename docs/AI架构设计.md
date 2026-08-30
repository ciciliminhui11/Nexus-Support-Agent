# AI 架构设计

> `docs/` 为项目总体文档；各模块规格见 [`../specs/`](../specs/)。

## RAG 检索链路（模块 001）

混合检索（向量 + BM25 双路召回 → RRF 融合 → Reranker 精排）架构图：

```mermaid
flowchart TD
    Q[用户提问] --> VALID{输入校验<br/>长度≤500 字 + 每日配额}
    VALID -- 超长/超配额 --> ERR[400/429 契约错误码]
    VALID -- 通过 --> HIST[读取最近 N 轮历史]
    HIST --> EMB[Query 向量化<br/>embedding.py]

    EMB --> VPATH[向量路<br/>Chroma 余弦检索 candidate_k]
    VPATH --> VFILT{阈值过滤<br/>distance ≤ 1 - rag_similarity_threshold}
    VFILT -- 通过 --> VRANK[向量命中<br/>distance]

    EMB --> BPATH[BM25 路<br/>jieba 分词<br/>bm25.py]
    BPATH --> GATE{显著词闸门<br/>与问题共享 ≥1 显著词}
    GATE -- 通过 --> BSCORE[自研 Okapi BM25 打分<br/>rag_bm25_top_k]
    GATE -- 不通过 --> BVANISH[该片段排除]
    BSCORE --> BRANK[BM25 命中<br/>bm25_score]

    VRANK & BRANK --> RRF[RRF 融合<br/>Σ 1/(k+rank), k=60]
    RRF --> CAND[粗筛候选池<br/>rag_candidate_k=20]

    CAND --> RERANK{Reranker 精排<br/>可选}
    RERANK -- 已装模型 --> CROSS[CrossEncoder<br/>bge-reranker-v2-m3<br/>对「问题-片段」对打分]
    RERANK -- 未装/加载失败/推理异常 --> FALLBACK[回落 RRF 融合序]
    CROSS --> TOPK[取 rag_top_k=6]
    FALLBACK --> TOPK

    TOPK -- 两路皆空 --> EMPTY[兜底话术<br/>不调用 LLM]
    TOPK -- 有命中 --> PROMPT[Prompt 组装<br/>System Prompt + 编号来源片段 + 历史 + 问题]
    PROMPT --> LLM[LLM 流式调用<br/>Ollama Qwen2]
    LLM --> SSE[SSE 事件流<br/>data / meta / finish / error]
    SSE --> PERSIST[消息持久化 + 来源后校验]
```

## 关键设计决策

### 1. 检索策略：双路召回 + RRF 融合（FR-004）

- **为什么双路**：纯向量检索对口语化表述与关键词精确匹配（品牌、型号、货号）召回不足；BM25 关键词路径补齐。两路覆盖「语义相关 + 字面重叠」两种召回信号。
- **为什么 RRF**：向量余弦分与 BM25 分量纲不同、无法直接相加；RRF 只用**排名**融合（`Σ 1/(k+rank)`），免去分数归一化，两路都命中的片段自然排前。
- **显著词闸门**：候选片段须与问题共享 ≥1 显著词（CJK 二元及以上 / ASCII 词 len≥2）才进入 BM25 打分，防止功能字（的/天/么）假阳性破坏空检索兜底语义。
- **自研 Okapi BM25**：jieba 仅分词，打分自研（k1=1.5、b=0.75），满足宪法「核心链路自研可读」。

### 2. 重排序：Reranker 精排（FR-014，可插拔降级）

- Cross-Encoder 对「问题-片段」对打分，把语义相似但业务无关的片段（如「退款时效」vs「配送时效」）压后，提高送入 LLM 上下文的质量，降低注意力稀释与幻觉。
- **可插拔 + 全链路降级**：模型未安装（`find_spec` 检测）→ Noop 保序；加载失败 → `warmup()` 吞异常置 Noop；推理异常 → `retriever` 回落 RRF 融合序。任何一环失败都不影响主链路可用性。
- 精排只对粗筛候选池（20 条）打分，不扫描全库，控制首字延迟。

### 3. 上下文截断（FR-011）

预算 = `context_max_tokens × 1.5 字符/token`。超限时**先按消息边界丢最早历史**，仍超再**从末尾减知识片段**（保持编号连续），严禁先丢知识（答案依据）。

### 4. 幻觉抑制（FR-005/FR-006/FR-013）

- 空检索不调用 LLM，输出固定兜底话术，禁止编造。
- System Prompt 强约束「仅依据编号材料回答、无材料输出兜底话术」。
- 输出后来源校验（postcheck）：启发式检出超出知识片段范围的断言，标记「待人工核实」而非静默放行。

### 5. 异常处理（FR-010）

LLM 超时 / 限流 / 服务不可用统一转 SSE `error` 事件（`llm_timeout`/`llm_rate_limited`/`llm_error`）友好返回；错误分支同样持久化 AI 消息，不发空响应、不静默结束。

### 6. 服务端唯一执行（原则三）

检索与 LLM 调用全部后端完成，前端仅通过 REST/SSE 交互，模型 API Key 只存服务端环境变量。
