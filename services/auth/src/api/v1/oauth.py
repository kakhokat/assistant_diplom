from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import RedirectResponse

from domain.models.tokens import TokenPair
from services.auth import AuthService, get_auth_service
from services.oauth_yandex import YandexOAuthService

router = APIRouter()


def _get_client_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    return user_agent, client_ip


class OAuthProvider(Protocol):
    def build_login_redirect(self, next_url: str | None = None) -> str: ...

    async def handle_callback(
        self,
        *,
        code: str,
        state: str | None,
        user_agent: str | None,
        client_ip: str | None,
    ) -> TokenPair: ...


# Реестр провайдеров (добавление нового провайдера = добавить сюда)
OAUTH_PROVIDERS: dict[str, type[OAuthProvider]] = {
    "yandex": YandexOAuthService,
}


def get_oauth_provider_service(
    provider: str = Path(..., min_length=1),
    auth: AuthService = Depends(get_auth_service),
) -> OAuthProvider:
    cls = OAUTH_PROVIDERS.get(provider)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth provider is not supported",
        )
    return cls(auth=auth)


@router.get("/oauth/{provider}/login", include_in_schema=True)
async def oauth_login(
    request: Request,
    provider: str,
    next: str | None = None,
    service: OAuthProvider = Depends(get_oauth_provider_service),
):
    url = service.build_login_redirect(next_url=next)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/oauth/{provider}/callback",
    response_model=TokenPair,
    include_in_schema=True,
)
async def oauth_callback(
    request: Request,
    provider: str,
    code: str,
    state: str | None = None,
    service: OAuthProvider = Depends(get_oauth_provider_service),
):
    ua, ip = _get_client_meta(request)
    return await service.handle_callback(
        code=code, state=state, user_agent=ua, client_ip=ip
    )
