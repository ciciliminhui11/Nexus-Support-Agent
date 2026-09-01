"""006 联调接口 /api/intent/debug 集成测试：权限、参数校验、trace 结构。"""
from __future__ import annotations

from app.intent.schema import IntentCategory, SourceLayer


def _post(client, headers, query):
    return client.post(
        "/api/intent/debug", json={"query": query}, headers=headers
    )


def test_requires_admin(client, auth_headers):
    headers, _ = auth_headers(role="user")
    resp = _post(client, headers, "我要投诉你们的服务质量")
    assert resp.status_code == 403


def test_admin_empty_query_400(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = _post(client, headers, "   ")
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_query"


def test_admin_overlong_query_400(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = _post(client, headers, "长" * 501)
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_query"


def test_admin_rule_hit_returns_trace(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = _post(client, headers, "我要投诉你们的服务质量")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "我要投诉你们的服务质量"
    assert body["normalized_query"]
    assert body["rule_layer"]["intent"] == "complaint"
    assert body["small_model_layer"] is None
    assert body["fallback_layer"] is None
    assert body["error"] is None
    assert body["final"]["intent"] == IntentCategory.complaint.value
    assert body["final"]["source_layer"] == SourceLayer.rule.value
    assert body["final"]["confidence"] == 1.0


def test_admin_negative_sample_suppressed(client, auth_headers):
    """负样本抑制后规则层不命中；测试环境空密钥 → no_api_key 降级。"""
    headers, _ = auth_headers(role="admin")
    resp = _post(client, headers, "投诉咨询中心电话多少")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule_layer"] is None
    assert body["error"] == "no_api_key"
    assert body["final"]["intent"] == IntentCategory.unknown.value


def test_admin_mocked_model_path(client, auth_headers, monkeypatch):
    """mock 小模型高置信度 → small_model 层输出，trace 逐层可见。"""
    monkeypatch.setattr(
        "app.config.settings.deepseek_api_key", "test-key"
    )
    monkeypatch.setattr(
        "app.intent.service.classify_small",
        lambda q: (IntentCategory.product_consult, 0.95),
    )
    monkeypatch.setattr(
        "app.intent.service.classify_fallback", lambda q: None
    )
    headers, _ = auth_headers(role="admin")
    resp = _post(client, headers, "能退吗")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule_layer"] is None
    assert body["small_model_layer"]["intent"] == "product_consult"
    assert body["small_model_layer"]["confidence"] == 0.95
    assert body["final"]["intent"] == "product_consult"
    assert body["final"]["source_layer"] == "small_model"
