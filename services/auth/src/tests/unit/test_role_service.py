# src/tests/unit/test_role_service.py

from uuid import UUID
from uuid import uuid4

import pytest

from fastapi import HTTPException

from domain.models.tokens import PermissionCheckRequest
from services.roles import RoleService


class DummyUser:
    def __init__(self, user_id: UUID):
        self.id = user_id


class DummyUserRepo:
    def __init__(self, user: DummyUser | None):
        self._user = user

    async def get_by_id(self, user_id: UUID):
        # для простоты игнорируем user_id, используем заранее заданного
        return self._user


class DummyRoleRepo:
    def __init__(self, roles: list[str]):
        self._roles = roles

    async def get_user_roles(self, user_id: UUID) -> list[str]:
        return self._roles


@pytest.mark.asyncio
async def test_check_permissions_allow_any_role():
    user_id = uuid4()
    service = RoleService(session=None)
    service.user_repo = DummyUserRepo(DummyUser(user_id))
    service.role_repo = DummyRoleRepo(["user", "subscribers"])

    req = PermissionCheckRequest(
        user_id=str(user_id),
        required_roles=["subscribers"],
        require_all=False,
    )

    resp = await service.check_permissions(req)

    assert resp.allowed is True
    assert "has required roles" in resp.reason


@pytest.mark.asyncio
async def test_check_permissions_require_all_not_met():
    user_id = uuid4()
    service = RoleService(session=None)
    service.user_repo = DummyUserRepo(DummyUser(user_id))
    service.role_repo = DummyRoleRepo(["user"])  # нет "subscribers"

    req = PermissionCheckRequest(
        user_id=str(user_id),
        required_roles=["user", "subscribers"],
        require_all=True,
    )

    resp = await service.check_permissions(req)

    assert resp.allowed is False
    assert "does not have required roles" in resp.reason


@pytest.mark.asyncio
async def test_check_permissions_user_not_found_raises_404():
    user_id = uuid4()
    service = RoleService(session=None)
    service.user_repo = DummyUserRepo(None)  # пользователя нет
    service.role_repo = DummyRoleRepo([])

    req = PermissionCheckRequest(
        user_id=str(user_id),
        required_roles=["user"],
        require_all=False,
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.check_permissions(req)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "User not found"
