import json
from typing import Optional

import redis.exceptions as redis_exc
from redis.asyncio import Redis

from domain.ports.cache import Cache


class RedisCache(Cache):
    def __init__(self, client: Redis):
        self.client = client

    async def get(self, key: str) -> Optional[bytes]:
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except redis_exc.RedisError:
            return None

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        if not self.client:
            return
        try:
            await self.client.set(key, value, ttl)
        except redis_exc.RedisError:
            pass


def dumps(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def loads(raw: bytes):
    return json.loads(raw.decode("utf-8"))
