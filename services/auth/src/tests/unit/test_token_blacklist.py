# src/tests/unit/test_token_blacklist.py

import pytest

from infrastructure.redis.cache import TokenBlacklist


class DummyRedis:
    def __init__(self):
        self.store = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def setex(self, key: str, ttl: int, value: bytes) -> None:
        # ttl тут можно не учитывать, достаточно факта сохранения
        self.store[key] = (value, ttl)


@pytest.mark.asyncio
async def test_blacklist_with_dummy_redis():
    client = DummyRedis()
    blacklist = TokenBlacklist(client)

    jti = "test-jti"

    # сначала токена в чёрном списке нет
    assert not await blacklist.is_blacklisted(jti)

    # кладём токен в blacklist
    await blacklist.blacklist(jti, expires_in=10)

    # теперь он есть
    assert await blacklist.is_blacklisted(jti)


@pytest.mark.asyncio
async def test_blacklist_with_none_client_is_noop():
    blacklist = TokenBlacklist(client=None)

    jti = "another-jti"

    # вызов не должен падать, но и ничего не делает
    await blacklist.blacklist(jti, expires_in=10)

    # при отсутствии клиента — всегда False
    assert not await blacklist.is_blacklisted(jti)
