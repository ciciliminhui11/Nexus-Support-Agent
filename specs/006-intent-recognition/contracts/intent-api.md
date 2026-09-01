# 接口契约：意图识别（三层漏斗）

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

本特性主体为**内部服务模块**，集成进 001 RAG 问答链路，不向普通用户暴露独立 HTTP 意图接口；另提供管理员联调接口用于验证与演示。

## 一、内部服务契约（001 集成点）

001 在「输入校验之后、Query 向量化之前」注入调用，契约如下。

### recognize(query) → IntentResult

```python
IntentResult(
    intent: IntentCategory,        # product_consult/after_sale/small_talk/complaint/unknown
    confidence: float,             # 0~1
    source_layer: SourceLayer,     # rule/small_model/fallback/unknown
    raw_query: str,
    normalized_query: str,
    matched_patterns: list[str],
    clarification_question: str | None
)
```

- **入参**：`query`（已通过 001 长度/配额校验的用户输入）、`session_id`（用于澄清反问上下文，可选）。
- **约定**：
  - 规则层命中（`source_layer=rule`）时不发起任何模型调用（FR-005）；
  - `intent=small_talk` / `complaint` 时 001 **必须**短路跳过知识库检索（FR-012 / SC-007）；
  - `intent=unknown` 时走 001 默认问答或兜底话术，不阻断主流程（FR-013）；
  - 识别全程异常（模型超时/限流/密钥缺失）→ 返回 `unknown` 降级，**不得**抛出使问答链路失败。

### route(intent) → HandlerKey

意图 → Handler 映射（详见 [data-model.md](../data-model.md) §4）：`product_consult/after_sale → rag_qa`、`small_talk → small_talk`、`complaint → complaint`、`unknown → default`。Handler 由 001/本模块通过依赖注入注册，router 不持有具体实现。

## 二、管理员联调接口

### POST /api/intent/debug

单条输入返回三层漏斗各层中间结果，用于联调、演示与词库/阈值调优验证。

- 鉴权：`Authorization: Bearer <jwt>`，角色为**管理员**（003 特性提供）；未鉴权 401，非管理员 403。
- 请求：

```json
{ "query": "我要投诉你们的服务质量" }
```

- 响应 `200`：

```json
{
  "query": "我要投诉你们的服务质量",
  "normalized_query": "我要投诉你们的服务质量",
  "rule_layer": { "hit": true, "matched_patterns": ["投诉"], "intent": "complaint" },
  "small_model_layer": null,
  "fallback_layer": null,
  "final": { "intent": "complaint", "confidence": 1.0, "source_layer": "rule" }
}
```

**说明**：未进入的层返回 `null`；规则层未命中时 `rule_layer.hit=false`，`small_model_layer`/`fallback_layer` 携带该层产出（含置信度与澄清问题）。不存在/权限不足响应：404/401/403，错误码见下。

## 三、状态码与错误码汇总

| HTTP | code | 说明 |
|---|---|---|
| 200 | — | 联调成功，返回三层结果 |
| 400 | `invalid_query` | query 为空或超长 |
| 401 | `unauthorized` | 未鉴权 |
| 403 | `forbidden` | 非管理员 |
| 429 | `model_rate_limited` | 模型限流（联调接口透出，内部集成时降级 unknown） |

## 四、配置契约（.env / system_config / 配置文件）

| 配置项 | 位置 | 默认值 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | .env | 用户填写 | 兜底层模型密钥（占位，不提交仓库；与 001 对话共用） |
| `LLM_BASE_URL` | .env | `https://api.deepseek.com` | 兜底层 OpenAI 兼容 base_url（与 001 对话共用） |
| `LLM_MODEL` | .env | `deepseek-v4-flash` | 兜底大模型名（与 001 对话共用） |
| `SMALL_MODEL_NAME` | .env | 用户填写 | 小模型层模型名（独立厂商/端点） |
| `SMALL_MODEL_API_KEY` | .env | 用户填写 | 小模型层密钥（不复用 DeepSeek 凭据） |
| `SMALL_MODEL_BASE_URL` | .env | 用户填写 | 小模型层 OpenAI 兼容 base_url |
| `intent_high_threshold` | system_config | 0.9 | 高阈值 |
| `intent_low_threshold` | system_config | 0.6 | 低阈值 |
| `intent_clarify_retry` | system_config | 1 | 澄清重试次数 |
| `intent_reverse_calibrate` | system_config | true | 反向校准规则通道开关 |
| `intent_model_self_check` | system_config | false | 模型自评通道开关 |
| 词库/句式模板/负样本文件 | 配置文件 | `intent_keywords.yaml` 等 | 路径经 system_config 指定 |

**结构示例**（词库/句式模板/负样本）见 [data-model.md](../data-model.md) §3；`.env.example` 提供全部密钥占位键名。
