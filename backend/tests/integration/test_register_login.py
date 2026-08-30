"""注册/登录/鉴权 API 集成测试（覆盖契约核心验收场景）。"""
from __future__ import annotations


def test_register_success(client):
    r = client.post(
        "/api/auth/register",
        json={
            "account_identifier": "13900139000",
            "account_type": "phone",
            "password": "secret123",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] > 0
    assert body["role"] == "user"
    assert body["account_identifier"] == "13900139000"


def test_register_duplicate_identifier_conflict(client):
    payload = {"account_identifier": "13900139000", "account_type": "phone", "password": "secret123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["code"] == "identifier_taken"


def test_register_invalid_identifier(client):
    r = client.post(
        "/api/auth/register",
        json={"account_identifier": "123", "account_type": "phone", "password": "secret123"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_identifier"


def test_register_short_password(client):
    r = client.post(
        "/api/auth/register",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "123"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "password_too_short"


def test_login_success_and_token(client, db):
    client.post(
        "/api/auth/register",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "secret123"},
    )
    r = client.post(
        "/api/auth/login",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "secret123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 24 * 3600
    assert body["access_token"]
    assert body["user"]["role"] == "user"


def test_login_wrong_password_uniform_message(client):
    client.post(
        "/api/auth/register",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "secret123"},
    )
    r = client.post(
        "/api/auth/login",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "wrongpass"},
    )
    assert r.status_code == 401
    body = r.json()
    # 统一提示，不泄露账号是否存在
    assert body["code"] == "invalid_credentials"


def test_login_nonexistent_account_same_message(client):
    r = client.post(
        "/api/auth/login",
        json={"account_identifier": "19999999999", "account_type": "phone", "password": "wrongpass"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_me_returns_quota(client, auth_headers):
    headers, user = auth_headers()
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == user.id
    assert body["quota"] == {"limit": 100, "used": 0, "remaining": 100}


def test_me_without_token_unauthorized(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_me_with_invalid_token_unauthorized(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_admin_role_protected(client, auth_headers):
    """管理端专属校验：普通用户访问管理员资源被拒。"""
    headers, user = auth_headers(role="user")
    # 管理员资源校验依赖 require_admin——此处用假资源验证 403 语义由 deps 提供
    # 直接调用依赖函数更轻量，这里通过后续模块的真实端点覆盖；本测试验证 deps 行为
    from app.api.deps import require_admin
    from app.core.exceptions import ForbiddenError

    try:
        require_admin(user)
        assert False
    except ForbiddenError:
        pass


def test_login_guard_lockout(client):
    """连续失败触发 429 锁定。"""
    client.post(
        "/api/auth/register",
        json={"account_identifier": "13900139000", "account_type": "phone", "password": "secret123"},
    )
    payload = {"account_identifier": "13900139000", "account_type": "phone", "password": "wrongpass"}
    for _ in range(5):
        r = client.post("/api/auth/login", json=payload)
        assert r.status_code == 401
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 429
    assert r.json()["code"] == "too_many_attempts"
    assert "retry_after" in r.json()
