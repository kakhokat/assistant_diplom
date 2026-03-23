from __future__ import annotations

import os
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ENV_JWT_SECRET = "JWT_SECRET"
ENV_JWT_ALGORITHM = "JWT_ALGORITHM"
ENV_JWT_ISSUER = "JWT_ISSUER"
ENV_JWT_AUDIENCE = "JWT_AUDIENCE"

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is empty")
    return value.strip()


def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    detail: str | None = None

    if creds is None or not creds.credentials:
        detail = "missing bearer token"
    else:
        token = creds.credentials
        alg = _get_required_env(ENV_JWT_ALGORITHM)

        issuer_raw = os.environ.get(ENV_JWT_ISSUER)
        audience_raw = os.environ.get(ENV_JWT_AUDIENCE)
        issuer = issuer_raw.strip() if issuer_raw and issuer_raw.strip() else None
        audience = (
            audience_raw.strip() if audience_raw and audience_raw.strip() else None
        )

        options: dict[str, Any] = {
            "require": ["sub", "exp"],
            "verify_aud": bool(audience),
            "verify_iss": bool(issuer),
        }

        kwargs: dict[str, Any] = {
            "key": _get_required_env(ENV_JWT_SECRET),
            "algorithms": [alg],
            "options": options,
        }
        if issuer:
            kwargs["issuer"] = issuer
        if audience:
            kwargs["audience"] = audience

        try:
            payload = jwt.decode(token, **kwargs)
        except jwt.ExpiredSignatureError:
            detail = "token expired"
        except jwt.InvalidTokenError:
            detail = "invalid token"
        else:
            sub = payload.get("sub")
            if isinstance(sub, str) and sub.strip():
                return sub
            detail = "invalid token subject"

    raise _unauthorized(detail or "invalid token")


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
