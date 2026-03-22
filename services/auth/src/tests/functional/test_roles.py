import asyncio

from http import HTTPStatus
from uuid import UUID
from uuid import uuid4

from fastapi.testclient import TestClient

from db.postgres import AsyncSessionLocal
from infrastructure.postgres.user_repo import UserRepo


def _random_login() -> str:
    return f"user_{uuid4().hex[:8]}"


async def _set_superuser(login: str) -> None:
    """
    Помечаем пользователя как суперпользователя напрямую в БД,
    чтобы иметь возможность тестировать админские ручки.
    """
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        user = await repo.get_by_login(login)
        if not user:
            raise RuntimeError("User not found in DB")
        user.is_superuser = True
        await session.commit()


def _make_admin_headers(client: TestClient):
    """
    Создаёт пользователя, делает его суперюзером и возвращает headers с его access-токеном.
    """
    login = _random_login()
    password = "StrongPass123"

    r = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r.status_code == HTTPStatus.CREATED

    asyncio.run(_set_superuser(login))

    r_login = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r_login.status_code == HTTPStatus.OK
    tokens = r_login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return headers


def test_roles_crud_and_assign(client: TestClient):
    admin_headers = _make_admin_headers(client)

    # создаём роль subscribers
    r_create = client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={"name": "subscribers", "description": "Can watch new films"},
    )
    assert r_create.status_code == HTTPStatus.CREATED
    role = r_create.json()
    assert role["name"] == "subscribers"
    role_id = role["id"]
    UUID(role_id)

    # список ролей
    r_list = client.get("/api/v1/roles", headers=admin_headers)
    assert r_list.status_code == HTTPStatus.OK
    names = [r["name"] for r in r_list.json()]
    assert "subscribers" in names

    # создаём обычного пользователя и назначаем ему роль
    user_login = _random_login()
    password = "StrongPass123"
    r_user = client.post(
        "/api/v1/auth/signup",
        json={"login": user_login, "password": password},
    )
    assert r_user.status_code == HTTPStatus.CREATED
    user = r_user.json()
    user_id = user["id"]

    # assign
    r_assign = client.post(
        "/api/v1/roles/assign",
        headers=admin_headers,
        json={"user_id": user_id, "role_name": "subscribers"},
    )
    assert r_assign.status_code == HTTPStatus.NO_CONTENT

    # check permissions -> allowed
    r_check = client.post(
        "/api/v1/permissions/check",
        headers=admin_headers,
        json={
            "user_id": user_id,
            "required_roles": ["subscribers"],
            "require_all": True,
        },
    )
    assert r_check.status_code == HTTPStatus.OK
    payload = r_check.json()
    assert payload["allowed"] is True

    # revoke
    r_revoke = client.post(
        "/api/v1/roles/revoke",
        headers=admin_headers,
        json={"user_id": user_id, "role_name": "subscribers"},
    )
    assert r_revoke.status_code == HTTPStatus.NO_CONTENT

    # check permissions снова -> not allowed
    r_check2 = client.post(
        "/api/v1/permissions/check",
        headers=admin_headers,
        json={
            "user_id": user_id,
            "required_roles": ["subscribers"],
            "require_all": True,
        },
    )
    assert r_check2.status_code == HTTPStatus.OK
    payload2 = r_check2.json()
    assert payload2["allowed"] is False


def test_roles_forbidden_for_non_admin(client: TestClient):
    # обычный пользователь
    login = _random_login()
    password = "StrongPass123"
    r_signup = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r_signup.status_code == HTTPStatus.CREATED

    r_login = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r_login.status_code == HTTPStatus.OK

    tokens = r_login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # список ролей для обычного пользователя -> 403
    r_list = client.get("/api/v1/roles", headers=headers)
    assert r_list.status_code == HTTPStatus.FORBIDDEN
