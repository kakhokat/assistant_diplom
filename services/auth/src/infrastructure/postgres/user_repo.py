from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.user import UserCreate
from infrastructure.postgres.models import User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_login(self, login: str) -> Optional[User]:
        stmt = select(User).where(User.login == login)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_user(
        self,
        data: UserCreate,
        *,
        password_hash: str,
        is_superuser: bool = False,
    ) -> User:
        user = User(
            login=data.login,
            password_hash=password_hash,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user

    async def set_login(self, user_id: UUID, new_login: str) -> User:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(login=new_login)
            .returning(User)
        )
        res = await self.session.execute(stmt)
        user = res.scalar_one()
        await self.session.commit()
        return user

    async def set_password(self, user_id: UUID, password_hash: str) -> None:
        stmt = (
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def increment_token_version(self, user_id: UUID) -> int:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        user.token_version += 1
        await self.session.commit()
        await self.session.refresh(user)
        return user.token_version
