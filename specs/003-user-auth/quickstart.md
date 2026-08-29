# 快速验证指南：用户鉴权

**日期**：2026-08-29 | **特性**：[spec.md](spec.md)

本文档是可运行的端到端验证指南，证明 003 特性可用。实现细节见 `tasks.md` 与实施阶段。

## 前置条件

- 后端已启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- MySQL 8.0 已就绪；`JWT_SECRET` 等环境变量已按 `.env.example` 配置

## 验证场景

### 场景 1：注册 → 登录 → 访问受保护功能（验收场景 1、2）

```bash
# 1. 注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"account_identifier":"13800138000","account_type":"phone","password":"secret123"}'
# 预期 201，返回 user_id

# 2. 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account_identifier":"13800138000","account_type":"phone","password":"secret123"}'
# 预期 200，返回 access_token

# 3. 访问受保护接口
curl http://localhost:8000/api/auth/me -H "Authorization: Bearer <access_token>"
# 预期 200，返回账号信息 + 配额
```

**注册 → 立即登录**：注册成功后凭据立即可登录（SC-002）。

### 场景 2：校验与防枚举（验收场景 3、4 / 边界情况）

| 用例 | 操作 | 预期 |
|---|---|---|
| 手机号格式非法 | `"13800"` | 400 `invalid_identifier`，不建账号 |
| 邮箱格式非法 | `"abc@"` | 400 `invalid_identifier` |
| 标识重复注册 | 再次注册同手机号 | 409 `identifier_taken` |
| 密码过短 | `"123"` | 400 `password_too_short` |
| 密码错误登录 | 正确标识 + 错密码 | 401 `invalid_credentials`（不泄露账号是否存在） |
| 连续失败 | 连续 ≥5 次错密码 | 429 `too_many_attempts`，含 `retry_after` |
| 无效/过期令牌 | 乱造 token 或改过期时间 | 401 `unauthorized` |

### 场景 3：配额联动（用户故事 3）

- 完成一次问答（001 链路），再 `GET /api/auth/me`：
- **预期**：`quota.used` 与已提问次数一致，`remaining = 100 - used`（SC-007）
- 跨日（或修改配置时区/日期后）：`used` 重置为 0（自然日切换）

### 场景 4：管理员角色

- 用 `ADMIN_ACCOUNT` 配置的账号登录：
- **预期**：`GET /api/auth/me` 中 `role: "admin"`；该账号可访问 002 知识库管理接口；普通用户访问 002 接口返回 403。

## 测试命令

```bash
cd backend
pytest tests/ -v
```

**预期**：全部通过。集成测试覆盖注册→登录→受保护访问、配额联动（问答后 used 递增）、并发登录互不干扰、失败防护。

## 关键契约引用

- 注册/登录/me 接口、鉴权依赖与错误码：[contracts/auth-api.md](contracts/auth-api.md)
- User / UserQuotaDaily 实体与 JWT 载荷：[data-model.md](data-model.md)
- 算法与安全参数依据：[research.md](research.md)
