"""
Pydantic schemas for the super admin dashboard's platform-wide RBAC endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ============ Platform Role Schemas ============


class PlatformRoleBase(BaseModel):
    """Base schema for platform-wide admin roles."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


class PlatformRoleCreate(PlatformRoleBase):
    """Schema for creating a new platform role."""

    pass


class PlatformRoleUpdate(BaseModel):
    """Schema for updating a platform role (partial update)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    permissions: list[str] | None = None


class PlatformRoleRead(PlatformRoleBase):
    """Schema for reading a platform role."""

    id: int
    is_system_role: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Platform Role Assignment Schemas ============


class PlatformRoleAssignmentCreate(BaseModel):
    """Schema for granting a user a platform role."""

    user_id: UUID
    role_id: int


class PlatformRoleAssignmentRead(BaseModel):
    """Schema for reading a platform role assignment."""

    id: int
    user_id: UUID
    role_id: int
    role_name: str
    assigned_by_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Admin Session / Me Schemas ============


class AdminMeResponse(BaseModel):
    """Schema for the current admin's identity and effective permissions."""

    user_id: UUID
    email: str
    permissions: list[str]
    roles: list[str]


# ============ Audit Log Schemas ============


class AdminAuditLogRead(BaseModel):
    """Schema for reading an admin audit log entry."""

    id: int
    actor_user_id: UUID | None
    action: str
    target_type: str
    target_id: str | None
    before: dict | None
    after: dict | None
    extra_metadata: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminAuditLogListResponse(BaseModel):
    """Paginated response for admin audit log entries."""

    entries: list[AdminAuditLogRead]
    total: int


# ============ Platform Permission Schemas ============


class PlatformPermissionInfo(BaseModel):
    """Schema for platform permission information."""

    value: str
    name: str
    description: str


class PlatformPermissionsListResponse(BaseModel):
    """Response schema for listing all available platform permissions."""

    permissions: list[PlatformPermissionInfo]
