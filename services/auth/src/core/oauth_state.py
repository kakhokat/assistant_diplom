from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from core.settings import settings


def create_oauth_state(next_url: str | None = None, expires_in: int = 600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "type": "oauth_state",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": str(uuid4()),
    }
    if next_url:
        payload["next"] = next_url

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_oauth_state(state: str) -> dict:
    payload = jwt.decode(
        state,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "oauth_state":
        raise ValueError("Invalid state token type")
    return payload
