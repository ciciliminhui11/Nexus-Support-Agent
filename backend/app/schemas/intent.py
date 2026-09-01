"""006 意图识别接口结构（联调/调试用）。"""
from __future__ import annotations

from pydantic import BaseModel


class IntentDebugRequest(BaseModel):
    query: str
