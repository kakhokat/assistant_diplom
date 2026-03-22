from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleRead(RoleBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class RoleAssignment(BaseModel):
    user_id: UUID
    role_name: str
