from typing import List
from typing import Optional
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.role import RoleCreate
from domain.models.role import RoleUpdate
from infrastructure.postgres.models import Role
from infrastructure.postgres.models import User
from infrastructure.postgres.models import UserRole


class RoleRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_roles(self) -> List[Role]:
        stmt = select(Role).order_by(Role.name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_role(self, data: RoleCreate) -> Role:
        role = Role(name=data.name, description=data.description)
        self.session.add(role)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(role)
        return role

    async def get_role_by_id(self, role_id: UUID) -> Optional[Role]:
        stmt = select(Role).where(Role.id == role_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_role(self, role_id: UUID, data: RoleUpdate) -> Role:
        values = {}
        if data.name is not None:
            values["name"] = data.name
        if data.description is not None:
            values["description"] = data.description
        stmt = update(Role).where(Role.id == role_id).values(**values).returning(Role)
        res = await self.session.execute(stmt)
        role = res.scalar_one()
        await self.session.commit()
        return role

    async def delete_role(self, role_id: UUID) -> None:
        stmt = delete(Role).where(Role.id == role_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def assign_role(self, user_id: UUID, role_name: str) -> None:
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        role = await self.get_role_by_name(role_name)
        if not role:
            raise ValueError("Role not found")

        # проверим, нет ли уже такой роли
        stmt = select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return

        ur = UserRole(user_id=user_id, role_id=role.id)
        self.session.add(ur)
        await self.session.commit()

    async def revoke_role(self, user_id: UUID, role_name: str) -> None:
        role = await self.get_role_by_name(role_name)
        if not role:
            return
        stmt = delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_user_roles(self, user_id: UUID) -> list[str]:
        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
