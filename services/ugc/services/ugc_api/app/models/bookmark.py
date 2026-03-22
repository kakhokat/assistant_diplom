from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from .common import Meta


class BookmarkKey(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    film_id: str = Field(..., min_length=1, max_length=128)


class BookmarkCreate(BookmarkKey):
    """Payload for creating/upserting bookmark."""

    model_config = ConfigDict(title="BookmarkCreate")


class BookmarkOut(BookmarkKey, Meta):
    created_at: datetime
    updated_at: datetime
