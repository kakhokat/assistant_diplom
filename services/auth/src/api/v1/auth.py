from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from domain.models.tokens import TokenPair
from domain.models.user import LoginRequest, UserCreate, UserProfile, UserRead
from services.auth import AuthService, get_auth_service

router = APIRouter()

# Используется Swagger'ом для Authorize
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def _get_client_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    return user_agent, client_ip


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    return await service.register_user(payload)


# Обычный JSON-логин (используется тестами и руками)
@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ua, ip = _get_client_meta(request)
    return await service.login(payload, user_agent=ua, client_ip=ip)


# OAuth2 password flow для Authorize в Swagger (form-data: username/password)
@router.post("/token", response_model=TokenPair)
async def login_oauth2(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ua, ip = _get_client_meta(request)
    creds = LoginRequest(login=form_data.username, password=form_data.password)
    return await service.login(creds, user_agent=ua, client_ip=ip)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: dict,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required",
        )
    ua, ip = _get_client_meta(request)
    return await service.refresh_tokens(
        refresh_token=refresh_token,
        user_agent=ua,
        client_ip=ip,
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    service: AuthService = Depends(get_auth_service),
) -> UserProfile:
    return await service.get_current_user(token)


@router.get("/me", response_model=UserProfile)
async def me(current: UserProfile = Depends(get_current_user)):
    return current


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    service: AuthService = Depends(get_auth_service),
    current: UserProfile = Depends(get_current_user),
):
    ua, ip = _get_client_meta(request)
    await service.logout(token, current, user_agent=ua, client_ip=ip)
    return


@router.post("/logout-others", status_code=status.HTTP_204_NO_CONTENT)
async def logout_others(
    current: UserProfile = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    await service.logout_others(current)
    return
