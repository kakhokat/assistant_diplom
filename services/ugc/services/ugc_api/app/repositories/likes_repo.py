from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..constants import (
    AVG,
    COUNT,
    CREATED_AT,
    DISLIKE_CNT,
    FILM_ID,
    LIKE_CNT,
    OP_AVG,
    OP_COND,
    OP_EQ,
    OP_GROUP,
    OP_MATCH,
    OP_SUM,
    UPDATED_AT,
    USER_ID,
    VALUE,
)
from ..settings import settings


class LikesRepo:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[settings.col_likes]

    async def ensure_indexes(self) -> None:
        await self.col.create_index(
            [(USER_ID, 1), (FILM_ID, 1)],
            unique=True,
            name="ux_user_film",
        )
        await self.col.create_index(
            [(FILM_ID, 1), (CREATED_AT, -1)],
            name="ix_film_created_at",
        )

    async def upsert(self, user_id: str, film_id: str, value: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {USER_ID: user_id, FILM_ID: film_id},
            {
                "$set": {VALUE: value, UPDATED_AT: now},
                "$setOnInsert": {CREATED_AT: now},
            },
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
            .skip(offset)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [cast(dict[str, Any], d) for d in docs]

    async def aggregates_for_film(self, film_id: str) -> dict[str, Any]:
        pipeline: list[dict[str, Any]] = [
            {OP_MATCH: {FILM_ID: film_id}},
            {
                OP_GROUP: {
                    "_id": f"${FILM_ID}",
                    COUNT: {OP_SUM: 1},
                    AVG: {OP_AVG: f"${VALUE}"},
                    LIKE_CNT: {OP_SUM: {OP_COND: [{OP_EQ: [f"${VALUE}", 10]}, 1, 0]}},
                    DISLIKE_CNT: {OP_SUM: {OP_COND: [{OP_EQ: [f"${VALUE}", 0]}, 1, 0]}},
                }
            },
        ]

        docs = await self.col.aggregate(pipeline).to_list(length=1)
        if not docs:
            return {
                FILM_ID: film_id,
                COUNT: 0,
                AVG: float(0),
                LIKE_CNT: 0,
                DISLIKE_CNT: 0,
            }

        r = cast(dict[str, Any], docs[0])
        zero_f = float(0)
        return {
            FILM_ID: film_id,
            COUNT: int(r.get(COUNT, 0) or 0),
            AVG: float(r.get(AVG, zero_f) or zero_f),
            LIKE_CNT: int(r.get(LIKE_CNT, 0) or 0),
            DISLIKE_CNT: int(r.get(DISLIKE_CNT, 0) or 0),
        }
