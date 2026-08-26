"""
Platform-wide admin RBAC utility functions.

Mirrors `app.utils.rbac`'s workspace-scoped permission checking, but for the
super admin dashboard: permissions here are not scoped to a workspace, they
are granted (or not) to a user across the whole platform via
`PlatformRoleAssignment`.
"""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    AdminAuditLog,
    PlatformPermission,
    PlatformRoleAssignment,
    has_permission,
)


async def get_platform_permissions(
    session: AsyncSession,
    user_id: UUID,
) -> list[str]:
    """
    Get the union of permissions granted to a user across all of their
    platform role assignments.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        List of permission strings (deduplicated)
    """
    result = await session.execute(
        select(PlatformRoleAssignment)
        .options(selectinload(PlatformRoleAssignment.role))
        .filter(PlatformRoleAssignment.user_id == user_id)
    )
    assignments = result.scalars().all()

    permissions: set[str] = set()
    for assignment in assignments:
        if assignment.role:
            permissions.update(assignment.role.permissions or [])

    return list(permissions)


async def is_platform_admin(session: AsyncSession, user_id: UUID) -> bool:
    """Whether a user has any platform role assignment at all."""
    permissions = await get_platform_permissions(session, user_id)
    return len(permissions) > 0


async def check_platform_permission(
    session: AsyncSession,
    auth: AuthContext,
    required_permission: str,
    error_message: str = "You don't have permission to perform this action",
) -> list[str]:
    """
    Check if the authenticated principal has a specific platform-wide
    admin permission. Raises HTTPException if permission is denied.

    Args:
        session: Database session
        auth: Resolved auth context for the request
        required_permission: PlatformPermission value to check
        error_message: Custom error message for permission denied

    Returns:
        The user's platform permissions if granted

    Raises:
        HTTPException: If the user lacks the permission (403)
    """
    permissions = await get_platform_permissions(session, auth.user.id)

    if not has_permission(permissions, required_permission):
        raise HTTPException(status_code=403, detail=error_message)

    return permissions


async def record_admin_action(
    session: AsyncSession,
    actor_user_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AdminAuditLog:
    """
    Write one audit row for an admin dashboard mutation. Callers are
    responsible for redacting secret values from `before`/`after` before
    passing them in -- this helper does not mask anything.

    Does not commit; the caller's existing transaction commits it alongside
    the actual mutation so the audit row and the change land atomically.
    """
    entry = AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        extra_metadata=extra_metadata,
        ip_address=ip_address,
    )
    session.add(entry)
    await session.flush()
    return entry


__all__ = [
    "PlatformPermission",
    "check_platform_permission",
    "get_platform_permissions",
    "is_platform_admin",
    "record_admin_action",
]
