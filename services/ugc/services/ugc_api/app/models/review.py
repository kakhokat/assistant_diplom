from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .common import Meta


class ReviewKey(BaseModel):
    film_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)


class ReviewCreate(ReviewKey):
    text: str = Field(..., min_length=1, max_length=10_000)
    user_film_rating: int = Field(..., ge=0, le=10)


class ReviewUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    user_film_rating: int = Field(..., ge=0, le=10)


class ReviewOut(ReviewCreate, Meta):
    review_id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    updated_at: datetime
