from datetime import datetime
from datetime import timezone
from typing import List
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.postgres.models import LoginHistory
from infrastructure.postgres.models import RefreshToken


class TokenRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_refresh_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        client_ip: str | None,
    ) -> RefreshToken:
        # 👇 НОРМАЛИЗАЦИЯ: делаем naive-UTC, чтобы совпадало с колонкой DateTime без tz
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)

        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self.session.commit()

    async def revoke_all_for_user(
        self, user_id: UUID, except_token_hash: str | None = None
    ) -> None:
        stmt = select(RefreshToken).where(RefreshToken.user_id == user_id)
        res = await self.session.execute(stmt)
        tokens: List[RefreshToken] = list(res.scalars().all())
        for t in tokens:
            if except_token_hash and t.token_hash == except_token_hash:
                continue
            t.revoked = True
        await self.session.commit()

    async def revoke_for_user_session(
        self,
        user_id: UUID,
        user_agent: str | None,
        client_ip: str | None,
    ) -> None:
        """Отзывает refresh-токены текущей сессии.

        Ищет refresh-токены по (user_agent, client_ip). Если мета неизвестна — отзывает все.
        """
        conditions = [
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        ]
        if user_agent is not None:
            conditions.append(RefreshToken.user_agent == user_agent)
        if client_ip is not None:
            conditions.append(RefreshToken.client_ip == client_ip)

        stmt = update(RefreshToken).where(*conditions).values(revoked=True)
        await self.session.execute(stmt)
        await self.session.commit()

    async def add_login_event(
        self,
        user_id: UUID,
        action: str,
        user_agent: str | None,
        client_ip: str | None,
    ) -> None:
        event = LoginHistory(
            user_id=user_id,
            action=action,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        self.session.add(event)
        await self.session.commit()

    async def list_login_history(self, user_id: UUID, limit: int, offset: int):
        stmt = (
            select(LoginHistory)
            .where(LoginHistory.user_id == user_id)
            .order_by(LoginHistory.login_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
