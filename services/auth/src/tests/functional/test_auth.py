from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _random_login() -> str:
    return f"user_{uuid4().hex[:8]}"


def test_signup_and_login_flow(client: TestClient):
    login = _random_login()
    password = "StrongPass123"

    # регистрация
    r = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r.status_code == HTTPStatus.CREATED
    data = r.json()
    assert data["login"] == login
    UUID(data["id"])

    # повторная регистрация тем же логином -> 409
    r2 = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r2.status_code == HTTPStatus.CONFLICT

    # логин
    r3 = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r3.status_code == HTTPStatus.OK
    tokens = r3.json()
    assert "access_token" in tokens and "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    access = tokens["access_token"]

    # auth/me с валидным токеном
    r4 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r4.status_code == HTTPStatus.OK
    profile = r4.json()
    assert profile["login"] == login
    assert "roles" in profile
    assert "is_superuser" in profile


def test_me_requires_auth(client: TestClient):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_and_logout_others(client: TestClient):
    login = _random_login()
    password = "StrongPass123"

    # регистрация и два логина (две сессии)
    r_signup = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r_signup.status_code == HTTPStatus.CREATED

    r1 = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r1.status_code == HTTPStatus.OK
    tokens1 = r1.json()

    r2 = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r2.status_code == HTTPStatus.OK
    tokens2 = r2.json()

    # refresh по второму refresh-токену
    r_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens2["refresh_token"]},
    )
    assert r_refresh.status_code == HTTPStatus.OK
    new_pair = r_refresh.json()
    assert new_pair["access_token"] != tokens2["access_token"]

    # logout-others через первый access-токен
    r_logout_others = client.post(
        "/api/v1/auth/logout-others",
        headers={"Authorization": f"Bearer {tokens1['access_token']}"},
    )
    assert r_logout_others.status_code == HTTPStatus.NO_CONTENT

    # старый access-токен (от второй сессии) больше не работает
    r_me_old = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens2['access_token']}"},
    )
    assert r_me_old.status_code == HTTPStatus.UNAUTHORIZED

    # новый логин работает
    r3 = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r3.status_code == HTTPStatus.OK
    tokens3 = r3.json()

    r_me_new = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens3['access_token']}"},
    )
    assert r_me_new.status_code == HTTPStatus.OK


def test_update_me_and_login_history(client: TestClient):
    login = _random_login()
    password = "StrongPass123"

    r = client.post(
        "/api/v1/auth/signup",
        json={"login": login, "password": password},
    )
    assert r.status_code == HTTPStatus.CREATED

    r_login = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert r_login.status_code == HTTPStatus.OK
    tokens = r_login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # смена логина
    new_login = _random_login()
    r_update = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"login": new_login},
    )
    assert r_update.status_code == HTTPStatus.OK
    profile = r_update.json()
    assert profile["login"] == new_login

    # история входов должна содержать хотя бы один login
    r_hist = client.get(
        "/api/v1/users/me/login-history",
        headers=headers,
    )
    assert r_hist.status_code == HTTPStatus.OK
    history = r_hist.json()
    assert isinstance(history, list)
    assert any(item["action"] == "login" for item in history)
