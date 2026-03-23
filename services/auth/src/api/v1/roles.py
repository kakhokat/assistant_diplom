from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from core.internal_auth import require_internal_api_key
from domain.models.role import RoleAssignment, RoleCreate, RoleRead, RoleUpdate
from domain.models.tokens import PermissionCheckRequest, PermissionCheckResponse
from domain.models.user import UserProfile
from services.auth import AuthService, get_auth_service
from services.roles import RoleService, get_role_service

from .auth import get_current_user

router = APIRouter()

# optional bearer для случая "либо internal-key, либо jwt"
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_optional)],
    auth: AuthService = Depends(get_auth_service),
) -> UserProfile | None:
    if not token:
        return None
    return await auth.get_current_user(token)


async def get_current_admin(
    current: UserProfile = Depends(get_current_user),
) -> UserProfile:
    if not current.is_superuser and "admin" not in current.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current


async def require_admin_or_internal(
    request: Request,
    current: UserProfile | None = Depends(get_current_user_optional),
) -> None:
    # 1) internal-key путь (без JWT)
    if request.headers.get("x-internal-api-key"):
        require_internal_api_key(request)
        return

    # 2) иначе — нужен admin JWT
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    if not current.is_superuser and "admin" not in current.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )


@router.get("/roles", response_model=list[RoleRead], tags=["roles"])
async def list_roles(
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    return await service.list_roles()


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    tags=["roles"],
)
async def create_role(
    payload: RoleCreate,
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    return await service.create_role(payload)


@router.patch("/roles/{role_id}", response_model=RoleRead, tags=["roles"])
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    return await service.update_role(role_id, payload)


@router.delete(
    "/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["roles"]
)
async def delete_role(
    role_id: UUID,
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    await service.delete_role(role_id)
    return


@router.post("/roles/assign", status_code=status.HTTP_204_NO_CONTENT, tags=["roles"])
async def assign_role(
    payload: RoleAssignment,
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    await service.assign_role(payload)
    return


@router.post("/roles/revoke", status_code=status.HTTP_204_NO_CONTENT, tags=["roles"])
async def revoke_role(
    payload: RoleAssignment,
    _admin: UserProfile = Depends(get_current_admin),
    service: RoleService = Depends(get_role_service),
):
    await service.revoke_role(payload)
    return


@router.post(
    "/permissions/check",
    response_model=PermissionCheckResponse,
    tags=["permissions"],
)
async def check_permissions(
    payload: PermissionCheckRequest,
    _guard: None = Depends(require_admin_or_internal),
    service: RoleService = Depends(get_role_service),
):
    return await service.check_permissions(payload)
