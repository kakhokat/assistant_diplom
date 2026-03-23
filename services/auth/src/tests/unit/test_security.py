# src/tests/unit/test_security.py

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_access_token,
    is_refresh_token,
    verify_password,
)


def test_hash_and_verify_password_ok_and_fail():
    password = "StrongPass123!"
    hashed = hash_password(password)

    # хэш не равен исходному паролю
    assert hashed != password

    # верный пароль проходит проверку
    assert verify_password(password, hashed)

    # неверный пароль не проходит
    assert not verify_password("wrong-password", hashed)


def test_create_access_token_contains_expected_claims():
    subject = "user-id-123"
    roles = ["user", "admin"]

    token = create_access_token(
        subject=subject,
        roles=roles,
        is_superuser=True,
        token_version=5,
        expires_in=60,  # короткий TTL для теста
    )

    payload = decode_token(token)

    assert payload["sub"] == subject
    assert payload["type"] == "access"
    assert payload["roles"] == roles
    assert payload["is_superuser"] is True
    assert payload["token_version"] == 5

    # служебные поля
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload

    assert is_access_token(payload)
    assert not is_refresh_token(payload)


def test_create_refresh_token_has_refresh_type_and_no_roles():
    subject = "user-id-123"

    token = create_refresh_token(subject=subject, expires_in=60)
    payload = decode_token(token)

    assert payload["sub"] == subject
    assert payload["type"] == "refresh"
    assert "roles" not in payload
    assert "token_version" not in payload

    assert is_refresh_token(payload)
    assert not is_access_token(payload)
