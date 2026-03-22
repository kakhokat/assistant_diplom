from __future__ import annotations

from datetime import datetime
from datetime import timezone

from pydantic import BaseModel
from pydantic import Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ok(BaseModel):
    ok: bool = True


class Meta(BaseModel):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
