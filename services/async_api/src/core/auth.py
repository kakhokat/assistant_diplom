from __future__ import annotations

from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.settings import settings

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if creds is None or not creds.credentials:
        raise _unauthorized("missing bearer token")

    options: dict[str, Any] = {
        "require": ["sub", "exp"],
        "verify_aud": bool(settings.JWT_AUDIENCE),
        "verify_iss": bool(settings.JWT_ISSUER),
    }

    kwargs: dict[str, Any] = {
        "key": settings.JWT_SECRET,
        "algorithms": [settings.JWT_ALGORITHM],
        "options": options,
    }
    if settings.JWT_ISSUER:
        kwargs["issuer"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        kwargs["audience"] = settings.JWT_AUDIENCE

    try:
        payload = jwt.decode(creds.credentials, **kwargs)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("token expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("invalid token")

    sub = payload.get("sub")
    if isinstance(sub, str) and sub.strip():
        return sub
    raise _unauthorized("invalid token subject")


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
