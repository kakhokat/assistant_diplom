from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.postgres.models import SocialAccount


class SocialRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_provider_user_id(
        self, provider: str, provider_user_id: str
    ) -> Optional[SocialAccount]:
        stmt = select(SocialAccount).where(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == provider_user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id,
        provider: str,
        provider_user_id: str,
        email: str | None,
    ) -> SocialAccount:
        row = SocialAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
