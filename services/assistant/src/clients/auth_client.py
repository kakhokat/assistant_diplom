from __future__ import annotations

import httpx
from fastapi import HTTPException
from fastapi import status

from core.settings import settings


class AuthClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self._service_authorization: str | None = None

    async def me(self, authorization: str | None) -> dict:
        if not authorization or not authorization.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='missing bearer token',
                headers={'WWW-Authenticate': 'Bearer'},
            )

        resp = await self.client.get(
            f"{settings.AUTH_API_BASE_URL}/api/v1/auth/me",
            headers={'Authorization': authorization},
        )
        if resp.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='invalid bearer token',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        resp.raise_for_status()
        return resp.json()

    async def service_authorization(self, force_refresh: bool = False) -> str:
        if self._service_authorization and not force_refresh:
            return self._service_authorization

        resp = await self.client.post(
            f"{settings.AUTH_API_BASE_URL}/api/v1/auth/login",
            json={
                'login': settings.ASSISTANT_SERVICE_LOGIN,
                'password': settings.ASSISTANT_SERVICE_PASSWORD,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        token = body['access_token']
        self._service_authorization = f'Bearer {token}'
        return self._service_authorization
