"""鉴权接口 Pydantic 结构（与 specs/003/contracts/auth-api.md 一致）。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountRequest(BaseModel):
    account_identifier: str = Field(min_length=1, max_length=100)
    account_type: Literal["phone", "email"]
    password: str = Field(min_length=1)


class RegisterRequest(AccountRequest):
    pass


class LoginRequest(AccountRequest):
    pass


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    account_identifier: str
    account_type: str
    role: str
    created_at: datetime


class QuotaInfo(BaseModel):
    limit: int
    used: int
    remaining: int


class MeResponse(BaseModel):
    user_id: int
    account_identifier: str
    account_type: str
    role: str
    created_at: datetime
    quota: QuotaInfo


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RegisterResponse(BaseModel):
    user_id: int
    account_identifier: str
    account_type: str
    role: str
    created_at: datetime
