from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class Permission(BaseModel):
    """Schema for a single permission"""

    name: str
    displayName: str = Field(validation_alias="display_name")
    description: Optional[str] = None
    category: str

    model_config = ConfigDict(populate_by_name=True)


class PermissionGroupBase(BaseModel):
    """Base schema for permission groups"""

    name: str
    displayName: str = Field(validation_alias="display_name")
    description: Optional[str] = None
    color: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class PermissionGroupCreate(PermissionGroupBase):
    """Schema for creating a new permission group"""

    permissionNames: List[str] = Field(default=[], validation_alias="permission_names")


class PermissionGroupUpdate(BaseModel):
    """Schema for updating an existing permission group"""

    displayName: Optional[str] = Field(default=None, validation_alias="display_name")
    description: Optional[str] = None
    color: Optional[str] = None
    permissionNames: Optional[List[str]] = Field(default=None, validation_alias="permission_names")

    model_config = ConfigDict(populate_by_name=True)


class PermissionGroup(PermissionGroupBase):
    """Schema for permission group response with full details"""

    id: int
    isSystem: bool = Field(validation_alias="is_system")
    priority: int
    permissions: List[str] = []
    createdAt: datetime = Field(validation_alias="created_at")
    updatedAt: datetime = Field(validation_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PermissionGroupSimple(BaseModel):
    """Simplified permission group schema for embedding in user responses"""

    id: int
    name: str
    displayName: str = Field(validation_alias="display_name")
    color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
