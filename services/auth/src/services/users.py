from typing import List
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from core.security import verify_password
from db.postgres import get_session
from domain.models.user import LoginHistoryRecord
from domain.models.user import UserProfile
from domain.models.user import UserUpdate
from infrastructure.postgres.role_repo import RoleRepo
from infrastructure.postgres.token_repo import TokenRepo
from infrastructure.postgres.user_repo import UserRepo


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepo(session)
        self.role_repo = RoleRepo(session)
        self.token_repo = TokenRepo(session)

    async def update_me(self, current: UserProfile, data: UserUpdate) -> UserProfile:
        user = await self.user_repo.get_by_id(current.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # смена логина
        if data.login and data.login != user.login:
            existing = await self.user_repo.get_by_login(data.login)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Login is already taken",
                )
            user = await self.user_repo.set_login(user.id, data.login)

        # смена пароля
        if data.new_password:
            if not data.old_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="old_password is required to change password",
                )
            if not verify_password(data.old_password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Old password is incorrect",
                )
            new_hash = hash_password(data.new_password)
            await self.user_repo.set_password(user.id, new_hash)

        roles = await self.role_repo.get_user_roles(user.id)
        return UserProfile(
            id=user.id,
            login=user.login,
            roles=roles,
            is_superuser=user.is_superuser,
        )

    async def get_login_history(
        self, user_id: UUID, limit: int, offset: int
    ) -> List[LoginHistoryRecord]:
        rows = await self.token_repo.list_login_history(
            user_id=user_id, limit=limit, offset=offset
        )
        return [
            LoginHistoryRecord(
                login_at=r.login_at,
                user_agent=r.user_agent,
                client_ip=r.client_ip,
                action=r.action,
            )
            for r in rows
        ]


def get_user_service(
    session: AsyncSession = Depends(get_session),
) -> UserService:
    return UserService(session=session)
