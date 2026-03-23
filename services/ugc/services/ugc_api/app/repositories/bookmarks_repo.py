from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..constants import CREATED_AT, FILM_ID, UPDATED_AT, USER_ID
from ..settings import settings


class BookmarksRepo:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[settings.col_bookmarks]

    async def ensure_indexes(self) -> None:
        await self.col.create_index(
            [(USER_ID, 1), (FILM_ID, 1)],
            unique=True,
            name="ux_user_film",
        )
        await self.col.create_index(
            [(USER_ID, 1), (CREATED_AT, -1)],
            name="ix_user_created_at",
        )

    async def create(self, user_id: str, film_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {USER_ID: user_id, FILM_ID: film_id},
            {"$set": {UPDATED_AT: now}, "$setOnInsert": {CREATED_AT: now}},
            upsert=True,
        )
        doc = await self.get(user_id, film_id)
        return cast(dict[str, Any], doc)

    async def get(self, user_id: str, film_id: str) -> Optional[dict[str, Any]]:
        doc = await self.col.find_one(
            {USER_ID: user_id, FILM_ID: film_id},
            projection={"_id": 0},
        )
        if not doc:
            return None
        return cast(dict[str, Any], doc)

    async def delete(self, user_id: str, film_id: str) -> bool:
        res = await self.col.delete_one({USER_ID: user_id, FILM_ID: film_id})
        return bool(res.deleted_count)

    async def list_by_user(
        self, user_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        cursor = (
            self.col.find({USER_ID: user_id}, projection={"_id": 0})
            .sort(CREATED_AT, -1)
            .skip(offset)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [cast(dict[str, Any], d) for d in docs]
