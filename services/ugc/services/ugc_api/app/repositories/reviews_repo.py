from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Optional
from typing import cast
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..constants import CREATED_AT
from ..constants import FILM_ID
from ..constants import REVIEW_ID
from ..constants import TEXT
from ..constants import UPDATED_AT
from ..constants import USER_FILM_RATING
from ..constants import USER_ID
from ..settings import settings


class ReviewsRepo:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[settings.col_reviews]

    async def ensure_indexes(self) -> None:
        await self.col.create_index(
            [(REVIEW_ID, 1)],
            unique=True,
            name="ux_review_id",
        )
        await self.col.create_index(
            [(FILM_ID, 1), (CREATED_AT, -1)],
            name="ix_film_created_at",
        )

    async def create(
        self, film_id: str, user_id: str, text: str, rating: int
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        doc: dict[str, Any] = {
            REVIEW_ID: str(uuid4()),
            FILM_ID: film_id,
            USER_ID: user_id,
            TEXT: text,
            USER_FILM_RATING: rating,
            CREATED_AT: now,
            UPDATED_AT: now,
        }
        await self.col.insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def get(self, review_id: str) -> Optional[dict[str, Any]]:
        doc = await self.col.find_one({REVIEW_ID: review_id}, projection={"_id": 0})
        if not doc:
            return None
        return cast(dict[str, Any], doc)

    async def update(
        self, review_id: str, text: str, rating: int
    ) -> Optional[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {REVIEW_ID: review_id},
            {"$set": {TEXT: text, USER_FILM_RATING: rating, UPDATED_AT: now}},
        )
        return await self.get(review_id)

    async def delete(self, review_id: str) -> bool:
        res = await self.col.delete_one({REVIEW_ID: review_id})
        return bool(res.deleted_count)

    async def list_by_film(
        self, film_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        cursor = (
            self.col.find({FILM_ID: film_id}, projection={"_id": 0})
            .sort(CREATED_AT, -1)
            .skip(offset)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [cast(dict[str, Any], d) for d in docs]
