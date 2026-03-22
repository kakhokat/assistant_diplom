from datetime import datetime
from typing import Protocol
from uuid import UUID


class TokenRepository(Protocol):
    async def add_refresh_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        client_ip: str | None,
    ): ...

    async def get_by_hash(self, token_hash: str): ...

    async def revoke(self, token) -> None: ...

    async def revoke_all_for_user(
        self, user_id: UUID, except_token_hash: str | None = None
    ) -> None: ...

    async def add_login_event(
        self,
        user_id: UUID,
        action: str,
        user_agent: str | None,
        client_ip: str | None,
    ) -> None: ...

    async def list_login_history(self, user_id: UUID, limit: int, offset: int): ...
