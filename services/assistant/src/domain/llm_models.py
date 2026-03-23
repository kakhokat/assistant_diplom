from __future__ import annotations

from pydantic import BaseModel, Field


class LlmParseResult(BaseModel):
    intent: str = Field(min_length=2, max_length=64)
    confidence: float = Field(ge=0.0, le=1.0)
    film_title: str | None = Field(default=None, max_length=256)
    person_name: str | None = Field(default=None, max_length=256)
    search_queries: list[str] = Field(default_factory=list, max_length=5)
    requires_auth: bool | None = None
    reason: str | None = Field(default=None, max_length=500)
