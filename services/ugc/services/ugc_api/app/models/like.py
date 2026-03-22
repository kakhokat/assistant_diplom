from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from .common import Meta


class LikeKey(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    film_id: str = Field(..., min_length=1, max_length=128)


class LikeCreate(LikeKey):
    value: int = Field(..., ge=0, le=10)


class LikeUpdate(BaseModel):
    value: int = Field(..., ge=0, le=10)


class LikeOut(LikeKey, Meta):
    value: int
    created_at: datetime
    updated_at: datetime


class LikeAggregatesOut(BaseModel):
    film_id: str = Field(..., min_length=1, max_length=128)
    count: int = Field(..., ge=0)
    avg: float
    like_cnt: int = Field(..., ge=0)
    dislike_cnt: int = Field(..., ge=0)
