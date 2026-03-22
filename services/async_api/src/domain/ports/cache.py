from typing import Optional, Protocol


class Cache(Protocol):
    async def get(self, key: str) -> Optional[bytes]: ...

    async def set(self, key: str, value: bytes, ttl: int) -> None: ...
