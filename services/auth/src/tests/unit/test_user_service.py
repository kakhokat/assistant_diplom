# src/tests/unit/test_user_service.py

from uuid import uuid4

import pytest
from fastapi import HTTPException

from core.security import hash_password
from domain.models.user import UserProfile, UserUpdate
from services.users import UserService


class DummyUser:
    def __init__(self, user_id, login: str, password_hash: str):
        self.id = user_id
        self.login = login
        self.password_hash = password_hash
        self.is_superuser = False


class DummyUserRepo:
    def __init__(self, user: DummyUser):
        self._user = user

    async def get_by_id(self, user_id):
        return self._user

    async def get_by_login(self, login: str):
        # в этом тесте нам не нужен поиск по логину
        return None

    async def set_login(self, user_id, new_login: str):
        self._user.login = new_login
        return self._user

    async def set_password(self, user_id, password_hash: str):
        self._user.password_hash = password_hash


class DummyRoleRepo:
    async def get_user_roles(self, user_id):
        return []


class DummyTokenRepo:
    async def list_login_history(self, user_id, limit, offset):
        return []


@pytest.mark.asyncio
async def test_update_me_change_password_requires_old_password():
    user_id = uuid4()
    user = DummyUser(
        user_id=user_id,
        login="user",
        password_hash=hash_password("old-pass"),
    )

    service = UserService(session=None)
    service.user_repo = DummyUserRepo(user)
    service.role_repo = DummyRoleRepo()
    service.token_repo = DummyTokenRepo()

    current_profile = UserProfile(
        id=user_id,
        login="user",
        roles=[],
        is_superuser=False,
    )

    # пытаемся сменить пароль без old_password
    update = UserUpdate(
        new_password="new-pass",
        old_password=None,
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.update_me(current_profile, update)

    assert excinfo.value.status_code == 400
    assert "old_password is required" in excinfo.value.detail
