from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt
import jwt

from core.settings import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # если хэш битый/не bcrypt-формата
        return False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(
    subject: str,
    *,
    token_type: str,
    expires_in: int,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = _now_utc()
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "jti": str(uuid4()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_access_token(
    *,
    subject: str,
    roles: list[str],
    is_superuser: bool,
    token_version: int,
    expires_in: Optional[int] = None,
) -> str:
    # Canonical claims used across services
    is_admin = bool(is_superuser or ("admin" in roles))
    role = "admin" if is_admin else "user"

    # Minimal scope set for the cleaned assistant-ready platform
    scopes: list[str] = ["catalog:read", "ugc:read", "ugc:write"]
    if is_admin:
        scopes += ["admin:platform"]

    return _create_token(
        subject,
        token_type="access",
        expires_in=expires_in or settings.ACCESS_TOKEN_EXPIRES_IN,
        extra_claims={
            "roles": roles,
            "is_superuser": is_superuser,
            "token_version": token_version,
            "role": role,
            # OAuth2-style scope claim (space-separated)
            "scope": " ".join(scopes),
        },
    )


def create_refresh_token(
    *,
    subject: str,
    expires_in: Optional[int] = None,
) -> str:
    return _create_token(
        subject,
        token_type="refresh",
        expires_in=expires_in or settings.REFRESH_TOKEN_EXPIRES_IN,
    )


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


def is_refresh_token(payload: Dict[str, Any]) -> bool:
    return payload.get("type") == "refresh"


def is_access_token(payload: Dict[str, Any]) -> bool:
    return payload.get("type") == "access"
