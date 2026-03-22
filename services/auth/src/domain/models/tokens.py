from uuid import UUID

from pydantic import BaseModel


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PermissionCheckRequest(BaseModel):
    user_id: UUID
    required_roles: list[str]
    require_all: bool = False


class PermissionCheckResponse(BaseModel):
    allowed: bool
    reason: str
