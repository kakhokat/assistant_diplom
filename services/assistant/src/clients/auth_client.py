from __future__ import annotations

import base64
import binascii
import json
import time
from typing import Any

import httpx
from fastapi import HTTPException, status

from core.settings import settings


class AuthClient:
    SERVICE_TOKEN_REFRESH_SKEW_SECONDS = 30

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self._service_authorization: str | None = None
        self._service_token_expires_at: float | None = None

    async def me(self, authorization: str | None) -> dict:
        if not authorization or not authorization.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        resp = await self.client.get(
            f"{settings.AUTH_API_BASE_URL}/api/v1/auth/me",
            headers={"Authorization": authorization},
        )
        if resp.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        resp.raise_for_status()
        return resp.json()

    async def service_authorization(self, force_refresh: bool = False) -> str:
        if self._service_authorization and not force_refresh and self._token_is_fresh():
            return self._service_authorization

        resp = await self.client.post(
            f"{settings.AUTH_API_BASE_URL}/api/v1/auth/login",
            json={
                "login": settings.ASSISTANT_SERVICE_LOGIN,
                "password": settings.ASSISTANT_SERVICE_PASSWORD,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        token = body["access_token"]
        self._service_authorization = f"Bearer {token}"
        self._service_token_expires_at = self._resolve_service_token_expires_at(
            token, body
        )
        return self._service_authorization

    def _token_is_fresh(self) -> bool:
        if self._service_token_expires_at is None:
            return True
        return (
            time.time() + self.SERVICE_TOKEN_REFRESH_SKEW_SECONDS
            < self._service_token_expires_at
        )

    @staticmethod
    def _resolve_service_token_expires_at(
        token: str, response_body: dict[str, Any]
    ) -> float | None:
        exp = AuthClient._extract_exp_from_jwt(token)
        if exp is not None:
            return exp

        expires_in = response_body.get("expires_in")
        if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool):
            return time.time() + float(expires_in)
        return None

    @staticmethod
    def _extract_exp_from_jwt(token: str) -> float | None:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        payload_segment = parts[1]
        padding = "=" * (-len(payload_segment) % 4)
        try:
            payload_raw = base64.urlsafe_b64decode(payload_segment + padding)
            payload = json.loads(payload_raw.decode("utf-8"))
        except (
            ValueError,
            TypeError,
            UnicodeDecodeError,
            binascii.Error,
            json.JSONDecodeError,
        ):
            return None

        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and not isinstance(exp, bool):
            return float(exp)
        return None
