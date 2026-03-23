from __future__ import annotations

from typing import Optional

import redis.exceptions as redis_exc
from redis.asyncio import Redis


class TokenBlacklist:
    """Чёрный список access-токенов по jti.

    Важно для деградации:
    - если Redis недоступен, сервис авторизации НЕ должен падать,
      поэтому проверки/записи делаем best-effort.
    """

    def __init__(self, client: Optional[Redis]):
        self.client = client

    @staticmethod
    def _key(jti: str) -> str:
        return f"blacklist:{jti}"

    async def is_blacklisted(self, jti: str) -> bool:
        if not self.client:
            return False
        try:
            exists = await self.client.exists(self._key(jti))
            return bool(exists)
        except redis_exc.RedisError:
            # fail-open: не блокируем пользователей, если Redis упал
            return False

    async def blacklist(self, jti: str, expires_in: int) -> None:
        if not self.client or expires_in <= 0:
            return
        try:
            await self.client.setex(self._key(jti), expires_in, b"1")
        except redis_exc.RedisError:
            # fail-open
            return
