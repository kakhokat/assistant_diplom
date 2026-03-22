from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class UserBase(BaseModel):
    login: str


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserRead(BaseModel):
    id: UUID
    login: str

    model_config = ConfigDict(from_attributes=True)


class UserProfile(BaseModel):
    id: UUID
    login: str
    roles: list[str] = []
    is_superuser: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    login: str | None = None
    old_password: str | None = None
    new_password: str | None = None


class LoginRequest(BaseModel):
    login: str
    password: str


class LoginHistoryRecord(BaseModel):
    login_at: datetime
    user_agent: str | None = None
    client_ip: str | None = None
    action: str
