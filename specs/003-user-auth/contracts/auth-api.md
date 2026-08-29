# 接口契约：用户鉴权

**日期**：2026-08-29 | **特性**：[spec.md](../spec.md)

## 端点

### POST /api/auth/register

注册账号（手机号或邮箱二选一 + 密码）。

```json
{ "account_identifier": "13800138000", "account_type": "phone", "password": "secret123" }
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| account_identifier | string | 是 | 手机号（默认 `^1[3-9]\d{9}$`）或邮箱 |
| account_type | enum(`phone`,`email`) | 是 | 标识类型 |
| password | string | 是 | ≥8 位（`min_password_length`），非空白 |

- 成功 `201`：
```json
{ "user_id": 42, "account_identifier": "13800138000", "account_type": "phone", "role": "user", "created_at": "2026-08-29T10:00:00" }
```
- 失败：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 标识格式非法 | 400 | `{ "code": "invalid_identifier", "message": "手机号或邮箱格式不正确" }` |
| 标识已占用 | 409 | `{ "code": "identifier_taken", "message": "该手机号/邮箱已被注册" }` |
| 密码过短 | 400 | `{ "code": "password_too_short", "message": "密码长度不能少于 8 位" }` |

### POST /api/auth/login

登录并签发 JWT。

```json
{ "account_identifier": "13800138000", "account_type": "phone", "password": "secret123" }
```

- 成功 `200`：
```json
{ "access_token": "<jwt>", "token_type": "bearer", "expires_in": 86400, "user": { "user_id": 42, "role": "user" } }
```
- 失败（统一提示，防枚举）：

| 场景 | HTTP | 响应体 |
|---|---|---|
| 账号不存在 / 密码错误 | 401 | `{ "code": "invalid_credentials", "message": "手机号/邮箱或密码错误" }` |
| 连续失败触发延迟 | 429 | `{ "code": "too_many_attempts", "message": "尝试过于频繁，请 N 秒后再试", "retry_after": N }` |

### GET /api/auth/me

查看当前账号信息与当日配额（需 `Authorization: Bearer <jwt>`）。

```json
{
  "user_id": 42,
  "account_identifier": "13800138000",
  "account_type": "phone",
  "role": "user",
  "created_at": "2026-08-29T10:00:00",
  "quota": { "limit": 100, "used": 12, "remaining": 88 }
}
```

- 未携带/无效/过期令牌 → `401 { "code": "unauthorized", "message": "请重新登录" }`。

## 鉴权依赖契约（全站复用）

所有受保护接口统一走 `api/deps.py` 的 `get_current_user` 依赖：

- 请求头缺 `Authorization` 或非 Bearer → 401 `unauthorized`
- 令牌签名无效 / 已过期 → 401 `unauthorized`（引导重新登录）
- 校验通过 → 依赖注入当前 User 对象，路由可直接取用

管理员专属接口（如 002 知识库管理）追加 `require_admin` 依赖：
- 角色非 `admin` → 403 `{ "code": "forbidden", "message": "无权操作" }`

## 配置契约（system_config / .env）

| 配置项 | key | 默认值 | 说明 |
|---|---|---|---|
| JWT 密钥 | `JWT_SECRET` | （必填，≥32 字节） | 仅服务端环境变量，禁止入库/提交 |
| JWT 有效期 | `jwt_expire_hours` | 24 | 小时 |
| 密码最小长度 | `min_password_length` | 8 | FR-009 |
| 手机号正则 | `phone_regex` | `^1[3-9]\d{9}$` | 可配置 |
| 失败触发阈值 | `login_fail_threshold` | 5 | FR-010 |
| 递增延迟封顶 | `login_lock_max_seconds` | 300 | FR-010 |
| 每日配额上限 | `daily_quota_limit` | 100 | FR-008（与 001 共用） |
| 管理员账号 | `ADMIN_ACCOUNT` | （预置） | 启动时置 admin 角色 |
