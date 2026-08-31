from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class RoleRead(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionRead(BaseModel):
    id: int
    entity: str
    action: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserRoleCreate(BaseModel):
    user_id: int
    role_id: int


class UserRoleRead(BaseModel):
    id: int
    user_id: int
    role_id: int
    granted_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserWithRolesRead(BaseModel):
    id: int
    email: str
    full_name: str
    is_superuser: bool
    roles: list[RoleRead] = []