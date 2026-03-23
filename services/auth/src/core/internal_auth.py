from __future__ import annotations

from fastapi import HTTPException, Request, status

from core.settings import settings


def require_internal_api_key(request: Request) -> None:
    expected = settings.INTERNAL_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_KEY is not configured",
        )
    got = request.headers.get("x-internal-api-key")
    if got != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
