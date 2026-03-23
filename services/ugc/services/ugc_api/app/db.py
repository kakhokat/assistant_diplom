from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .settings import settings

mongo_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global mongo_client
    if mongo_client is None:
        mongo_client = AsyncIOMotorClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=3000,
        )
    return mongo_client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


async def close_client() -> None:
    global mongo_client
    if mongo_client is not None:
        mongo_client.close()
        mongo_client = None
