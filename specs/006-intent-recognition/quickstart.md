# 快速验证指南：意图识别（三层漏斗）

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 006 特性可用。实现细节见 `tasks.md` 与实施阶段。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 已配置 `.env`：将 `.env.example` 复制为 `.env` 并填写 `DEEPSEEK_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（小模型名默认 `DeepSeek-R1-0528-Qwen3-8B`）；**未填密钥时验证降级路径**
- 内置默认词库/句式模板/负样本库已加载（`intent_keywords.yaml` 等）
- 具备管理员角色的 JWT（注册/登录由 003 特性提供）

## 验证场景

### 场景 1：规则层零成本拦截（验收场景 1/2/3）

```bash
curl -X POST http://localhost:8000/api/intent/debug \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query":"我要投诉你们的服务质量"}'
```

**预期**：
- `rule_layer.hit=true`、`matched_patterns=["投诉"]`、`final.intent="complaint"`、`final.source_layer="rule"`
- `small_model_layer` 与 `fallback_layer` 均为 `null` —— **未调用任何模型**（SC-001，识别附加延迟 < 10ms）
- 请求日志显示无模型 API 调用、无 token 消耗

### 场景 2：小模型高置信度识别（验收场景：小模型故事 2-1）

```bash
curl -X POST http://localhost:8000/api/intent/debug \
  -H "Authorization: Bearer <admin-jwt>" \
  -d '{"query":"这产品能不能七天无理由退货"}'
```

**预期**（需已配置密钥，或走集成测试的 mock 路径）：
- `rule_layer.hit=false`
- `small_model_layer` 返回 `intent="after_sale"`、`confidence ≥ 0.9`
- `final.source_layer="small_model"`、`final.intent="after_sale"`（SC-002）

### 场景 3：中段置信度触发澄清（验收场景：小模型故事 2-2）

输入歧义表达（如"能退吗"），mock 返回 `confidence` 落在 [0.6, 0.9)：
- `small_model_layer.clarification_question` 非空（如"请问你是想了解退货政策，还是办理退货？"）
- 澄清后重判仍不达标则流转下一层

### 场景 4：低置信度流转大模型兜底（验收场景：大模型故事 3-1）

输入新说法/模糊表达，小模型置信度 < 0.6（或反向校准拒绝）：
- `fallback_layer` 返回 JSON 结构化 `intent` + `confidence`（FR-009/FR-010）
- `final.source_layer="fallback"`

### 场景 5：模型不可用降级（验收场景：大模型故事 3-2 / FR-013）

**不填写密钥**（或 mock 超时/429）调用 debug 接口：
- 返回 `final.intent="unknown"`、`final.source_layer="unknown"`
- 与 001 联动：正常提问仍可走默认问答/兜底话术，**不阻断用户提问主流程**

### 场景 6：路由行为（验收场景：SC-007 / FR-012）

集成测试断言（`test_intent_route.py`）：
- `small_talk` / `complaint` 意图 → 001 不进入向量检索，返回模板/转人工话术
- `product_consult` / `after_sale` → 进入 001 RAG 检索
- 识别后消息记录 `intent_label` 写入对应意图值（FR-011）

## 边界用例

| 用例 | 操作 | 预期 |
|---|---|---|
| 空/纯标点输入 | `{"query":"？？？"}` | 归入 unknown 降级，不报错 |
| 多关键词冲突 | "我要投诉但想咨询价格" | 最长匹配/意图裁决，返回明确一类 |
| 词边界 | "投诉咨询中心是什么" | 不误判为投诉（词边界校验 + 负样本拦截） |
| 密钥缺失 | 未填 `.env` 密钥 | unknown 降级，主链路不受影响 |
| 非管理员调用 | 普通用户 JWT 调 debug | HTTP 403 |

## 测试命令

```bash
cd backend
pytest tests/unit/intent tests/integration/intent -v
```

**预期**：全部通过。单元覆盖关键词匹配（ahocorasick-ng 最长匹配/词边界）、归一化、句式模板（pyparsing）、双阈值、反向校准；集成覆盖三层漏斗全链路（mock 模型 API）、闲聊/投诉不检索路由、密钥缺失降级。

## 关键契约引用

- 内部服务契约 `recognize()` / `route()`、联调接口与配置契约：[contracts/intent-api.md](contracts/intent-api.md)
- 意图枚举、配置结构、路由映射与流水线流转：[data-model.md](data-model.md)
- 各技术决策依据（ahocorasick-ng / pyparsing 选型、置信度获取、双阈值取值等）：[research.md](research.md)
