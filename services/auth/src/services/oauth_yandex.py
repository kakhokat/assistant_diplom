from __future__ import annotations

from urllib.parse import urlencode

import httpx

from fastapi import HTTPException
from fastapi import status

from core.oauth_state import create_oauth_state
from core.oauth_state import decode_oauth_state
from core.settings import settings
from services.auth import AuthService


class YandexOAuthService:
    AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
    TOKEN_URL = "https://oauth.yandex.ru/token"
    USERINFO_URL = "https://login.yandex.ru/info"

    def __init__(self, auth: AuthService):
        self.auth = auth

    def _ensure_config(self) -> None:
        if (
            not settings.YANDEX_OAUTH_CLIENT_ID
            or not settings.YANDEX_OAUTH_CLIENT_SECRET
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Yandex OAuth is not configured",
            )

    def build_login_redirect(self, next_url: str | None = None) -> str:
        self._ensure_config()
        state = create_oauth_state(next_url=next_url)

        params = {
            "response_type": "code",
            "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
            "redirect_uri": settings.YANDEX_OAUTH_REDIRECT_URI,
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def handle_callback(
        self,
        *,
        code: str,
        state: str | None,
        user_agent: str | None,
        client_ip: str | None,
    ):
        self._ensure_config()
        if state:
            try:
                decode_oauth_state(state)
            except Exception:  # noqa: BLE001
                raise HTTPException(status_code=400, detail="Invalid state")

        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
                    "client_secret": settings.YANDEX_OAUTH_CLIENT_SECRET,
                    "redirect_uri": settings.YANDEX_OAUTH_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code >= 400:
                raise HTTPException(
                    status_code=401, detail="OAuth token exchange failed"
                )

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=401, detail="No access_token from provider"
                )

            user_resp = await client.get(
                self.USERINFO_URL,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access_token}"},
            )
            if user_resp.status_code >= 400:
                raise HTTPException(status_code=401, detail="OAuth userinfo failed")

            user_data = user_resp.json()
            provider_user_id = str(user_data.get("id"))
            email = user_data.get("default_email")

            if not provider_user_id or provider_user_id == "None":
                raise HTTPException(status_code=401, detail="No user id from provider")

        return await self.auth.login_via_social(
            provider="yandex",
            provider_user_id=provider_user_id,
            email=email,
            user_agent=user_agent,
            client_ip=client_ip,
        )
