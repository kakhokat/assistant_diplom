from typing import List
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres import get_session
from domain.models.role import RoleAssignment
from domain.models.role import RoleCreate
from domain.models.role import RoleRead
from domain.models.role import RoleUpdate
from domain.models.tokens import PermissionCheckRequest
from domain.models.tokens import PermissionCheckResponse
from infrastructure.postgres.role_repo import RoleRepo
from infrastructure.postgres.user_repo import UserRepo


class RoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.role_repo = RoleRepo(session)
        self.user_repo = UserRepo(session)

    async def list_roles(self) -> List[RoleRead]:
        roles = await self.role_repo.list_roles()
        return [
            RoleRead(id=r.id, name=r.name, description=r.description) for r in roles
        ]

    async def create_role(self, data: RoleCreate) -> RoleRead:
        try:
            role = await self.role_repo.create_role(data)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role with this name already exists",
            )
        return RoleRead(id=role.id, name=role.name, description=role.description)

    async def update_role(self, role_id: UUID, data: RoleUpdate) -> RoleRead:
        role = await self.role_repo.get_role_by_id(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        role = await self.role_repo.update_role(role_id, data)
        return RoleRead(id=role.id, name=role.name, description=role.description)

    async def delete_role(self, role_id: UUID) -> None:
        role = await self.role_repo.get_role_by_id(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        await self.role_repo.delete_role(role_id)

    async def assign_role(self, data: RoleAssignment) -> None:
        user = await self.user_repo.get_by_id(data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        try:
            await self.role_repo.assign_role(data.user_id, data.role_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    async def revoke_role(self, data: RoleAssignment) -> None:
        user = await self.user_repo.get_by_id(data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await self.role_repo.revoke_role(data.user_id, data.role_name)

    async def check_permissions(
        self, req: PermissionCheckRequest
    ) -> PermissionCheckResponse:
        user = await self.user_repo.get_by_id(req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        roles = await self.role_repo.get_user_roles(user.id)
        found = set(roles)
        required = set(req.required_roles)
        if req.require_all:
            allowed = required.issubset(found)
        else:
            allowed = bool(found & required)
        reason = (
            "User has required roles"
            if allowed
            else "User does not have required roles"
        )
        return PermissionCheckResponse(allowed=allowed, reason=reason)


def get_role_service(
    session: AsyncSession = Depends(get_session),
) -> RoleService:
    return RoleService(session=session)
