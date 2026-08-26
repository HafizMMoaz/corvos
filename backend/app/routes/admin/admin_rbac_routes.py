"""
Platform admin RBAC routes: roles, role assignments, permissions catalog,
and the admin audit log.

Endpoints:
- /admin/me - current admin's identity and effective permissions
- /admin/permissions - list all available platform permissions
- /admin/roles - CRUD for platform-wide admin roles
- /admin/role-assignments - grant/revoke admin roles to/from users
- /admin/audit-log - paginated history of every admin dashboard mutation
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    AdminAuditLog,
    PlatformPermission,
    PlatformRole,
    PlatformRoleAssignment,
    User,
    get_async_session,
)
from app.schemas import (
    AdminAuditLogListResponse,
    AdminAuditLogRead,
    AdminMeResponse,
    PlatformPermissionInfo,
    PlatformPermissionsListResponse,
    PlatformRoleAssignmentCreate,
    PlatformRoleAssignmentRead,
    PlatformRoleCreate,
    PlatformRoleRead,
    PlatformRoleUpdate,
)
from app.users import get_auth_context
from app.utils.platform_rbac import (
    check_platform_permission,
    get_platform_permissions,
    record_admin_action,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PLATFORM_PERMISSION_DESCRIPTIONS = {
    "settings:read": "View server settings and configuration values",
    "settings:write": "Change server settings and configuration values",
    "settings:reveal": "Reveal the plaintext value of a secret setting",
    "llm_providers:read": "View LLM provider and model catalog",
    "llm_providers:write": "Add, edit, or remove LLM providers and models",
    "quotas:read": "View free-model quota usage",
    "quotas:write": "Change or reset free-model quota caps",
    "connectors:read": "View connector OAuth app credentials",
    "connectors:write": "Change connector OAuth app credentials",
    "billing:read": "View billing/payment data",
    "billing:write": "Change billing/payment configuration",
    "plans:read": "View subscription plans",
    "plans:write": "Create, edit, or remove subscription plans",
    "feature_flags:read": "View feature flags and entitlements",
    "feature_flags:write": "Change feature flags and entitlements",
    "users:read": "View user accounts",
    "users:write": "Edit user accounts (status, credits, plan)",
    "admin_roles:read": "View platform admin roles and assignments",
    "admin_roles:write": "Create, edit, or assign platform admin roles",
    "audit_log:read": "View the admin dashboard audit log",
    "*": "Full access to every admin dashboard capability",
}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ============ Admin Identity ============


@router.get("/me", response_model=AdminMeResponse)
async def get_admin_me(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Return the current principal's platform admin permissions and roles.
    Returns 403 if the principal has no platform role assignments at all --
    this is the endpoint the admin dashboard shell calls to decide whether
    to render or redirect away.
    """
    permissions = await get_platform_permissions(session, auth.user.id)
    if not permissions:
        raise HTTPException(
            status_code=403, detail="You don't have access to the admin dashboard"
        )

    result = await session.execute(
        select(PlatformRoleAssignment)
        .options(selectinload(PlatformRoleAssignment.role))
        .filter(PlatformRoleAssignment.user_id == auth.user.id)
    )
    role_names = [
        a.role.name for a in result.scalars().all() if a.role is not None
    ]

    return AdminMeResponse(
        user_id=auth.user.id,
        email=auth.user.email,
        permissions=permissions,
        roles=role_names,
    )


@router.get("/permissions", response_model=PlatformPermissionsListResponse)
async def list_platform_permissions(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all available platform permissions that can be assigned to admin roles."""
    await check_platform_permission(
        session,
        auth,
        PlatformPermission.ADMIN_ROLES_READ.value,
        "You don't have permission to view admin permissions",
    )

    permissions = [
        PlatformPermissionInfo(
            value=perm.value,
            name=perm.name,
            description=PLATFORM_PERMISSION_DESCRIPTIONS.get(
                perm.value, f"Permission for {perm.value}"
            ),
        )
        for perm in PlatformPermission
    ]
    return PlatformPermissionsListResponse(permissions=permissions)


# ============ Platform Role Endpoints ============


@router.post("/roles", response_model=PlatformRoleRead)
async def create_platform_role(
    role_data: PlatformRoleCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new platform admin role. Requires admin_roles:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_WRITE.value,
            "You don't have permission to create admin roles",
        )

        result = await session.execute(
            select(PlatformRole).filter(PlatformRole.name == role_data.name)
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A platform role named '{role_data.name}' already exists",
            )

        valid_permissions = {p.value for p in PlatformPermission}
        for perm in role_data.permissions:
            if perm not in valid_permissions:
                raise HTTPException(
                    status_code=400, detail=f"Invalid permission: {perm}"
                )

        db_role = PlatformRole(**role_data.model_dump(), is_system_role=False)
        session.add(db_role)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="platform_role.create",
            target_type="platform_role",
            target_id=str(db_role.id),
            after=role_data.model_dump(),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create platform role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create platform role: {e!s}"
        ) from e


@router.get("/roles", response_model=list[PlatformRoleRead])
async def list_platform_roles(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all platform admin roles. Requires admin_roles:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_READ.value,
            "You don't have permission to view admin roles",
        )
        result = await session.execute(select(PlatformRole))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch platform roles: {e!s}"
        ) from e


@router.patch("/roles/{role_id}", response_model=PlatformRoleRead)
async def update_platform_role(
    role_id: int,
    role_data: PlatformRoleUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a platform admin role. Requires admin_roles:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_WRITE.value,
            "You don't have permission to update admin roles",
        )

        result = await session.execute(
            select(PlatformRole).filter(PlatformRole.id == role_id)
        )
        db_role = result.scalars().first()
        if not db_role:
            raise HTTPException(status_code=404, detail="Platform role not found")

        update_data = role_data.model_dump(exclude_unset=True)
        if "permissions" in update_data:
            valid_permissions = {p.value for p in PlatformPermission}
            for perm in update_data["permissions"]:
                if perm not in valid_permissions:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid permission: {perm}"
                    )

        before = {
            "name": db_role.name,
            "description": db_role.description,
            "permissions": db_role.permissions,
        }
        for key, value in update_data.items():
            setattr(db_role, key, value)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="platform_role.update",
            target_type="platform_role",
            target_id=str(role_id),
            before=before,
            after=update_data,
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update platform role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update platform role: {e!s}"
        ) from e


@router.delete("/roles/{role_id}")
async def delete_platform_role(
    role_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a custom platform admin role. System roles cannot be deleted."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_WRITE.value,
            "You don't have permission to delete admin roles",
        )

        result = await session.execute(
            select(PlatformRole).filter(PlatformRole.id == role_id)
        )
        db_role = result.scalars().first()
        if not db_role:
            raise HTTPException(status_code=404, detail="Platform role not found")
        if db_role.is_system_role:
            raise HTTPException(
                status_code=400, detail="Built-in system roles cannot be deleted"
            )

        before = {"name": db_role.name, "permissions": db_role.permissions}
        await session.delete(db_role)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="platform_role.delete",
            target_type="platform_role",
            target_id=str(role_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete platform role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete platform role: {e!s}"
        ) from e


# ============ Platform Role Assignment Endpoints ============


@router.get("/role-assignments", response_model=list[PlatformRoleAssignmentRead])
async def list_platform_role_assignments(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all platform admin role assignments. Requires admin_roles:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_READ.value,
            "You don't have permission to view admin role assignments",
        )
        result = await session.execute(
            select(PlatformRoleAssignment).options(
                selectinload(PlatformRoleAssignment.role)
            )
        )
        assignments = result.scalars().all()
        return [
            PlatformRoleAssignmentRead(
                id=a.id,
                user_id=a.user_id,
                role_id=a.role_id,
                role_name=a.role.name if a.role else "",
                assigned_by_id=a.assigned_by_id,
                created_at=a.created_at,
            )
            for a in assignments
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch platform role assignments: {e!s}",
        ) from e


@router.post("/role-assignments", response_model=PlatformRoleAssignmentRead)
async def create_platform_role_assignment(
    assignment_data: PlatformRoleAssignmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Grant a user a platform admin role. Requires admin_roles:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_WRITE.value,
            "You don't have permission to assign admin roles",
        )

        user_result = await session.execute(
            select(User).filter(User.id == assignment_data.user_id)
        )
        if not user_result.scalars().first():
            raise HTTPException(status_code=404, detail="User not found")

        role_result = await session.execute(
            select(PlatformRole).filter(PlatformRole.id == assignment_data.role_id)
        )
        role = role_result.scalars().first()
        if not role:
            raise HTTPException(status_code=404, detail="Platform role not found")

        existing = await session.execute(
            select(PlatformRoleAssignment).filter(
                PlatformRoleAssignment.user_id == assignment_data.user_id,
                PlatformRoleAssignment.role_id == assignment_data.role_id,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409, detail="User already has this admin role"
            )

        db_assignment = PlatformRoleAssignment(
            user_id=assignment_data.user_id,
            role_id=assignment_data.role_id,
            assigned_by_id=auth.user.id,
        )
        session.add(db_assignment)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="platform_role_assignment.create",
            target_type="platform_role_assignment",
            target_id=str(db_assignment.id),
            after={
                "user_id": str(assignment_data.user_id),
                "role_id": assignment_data.role_id,
                "role_name": role.name,
            },
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(db_assignment)
        return PlatformRoleAssignmentRead(
            id=db_assignment.id,
            user_id=db_assignment.user_id,
            role_id=db_assignment.role_id,
            role_name=role.name,
            assigned_by_id=db_assignment.assigned_by_id,
            created_at=db_assignment.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to create platform role assignment: {e!s}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create platform role assignment: {e!s}",
        ) from e


@router.delete("/role-assignments/{assignment_id}")
async def delete_platform_role_assignment(
    assignment_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Revoke a platform admin role from a user. Requires admin_roles:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.ADMIN_ROLES_WRITE.value,
            "You don't have permission to revoke admin roles",
        )

        result = await session.execute(
            select(PlatformRoleAssignment)
            .options(selectinload(PlatformRoleAssignment.role))
            .filter(PlatformRoleAssignment.id == assignment_id)
        )
        db_assignment = result.scalars().first()
        if not db_assignment:
            raise HTTPException(
                status_code=404, detail="Admin role assignment not found"
            )

        before = {
            "user_id": str(db_assignment.user_id),
            "role_id": db_assignment.role_id,
            "role_name": db_assignment.role.name if db_assignment.role else None,
        }
        await session.delete(db_assignment)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="platform_role_assignment.delete",
            target_type="platform_role_assignment",
            target_id=str(assignment_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to delete platform role assignment: {e!s}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete platform role assignment: {e!s}",
        ) from e


# ============ Audit Log Endpoint ============


@router.get("/audit-log", response_model=AdminAuditLogListResponse)
async def list_admin_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List admin dashboard audit log entries, newest first. Requires audit_log:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.AUDIT_LOG_READ.value,
            "You don't have permission to view the audit log",
        )

        stmt = select(AdminAuditLog)
        count_stmt = select(func.count()).select_from(AdminAuditLog)
        if action:
            stmt = stmt.filter(AdminAuditLog.action == action)
            count_stmt = count_stmt.filter(AdminAuditLog.action == action)
        if target_type:
            stmt = stmt.filter(AdminAuditLog.target_type == target_type)
            count_stmt = count_stmt.filter(AdminAuditLog.target_type == target_type)

        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(AdminAuditLog.created_at.desc()).limit(limit).offset(
            offset
        )
        result = await session.execute(stmt)
        entries = result.scalars().all()

        return AdminAuditLogListResponse(
            entries=[AdminAuditLogRead.model_validate(e) for e in entries],
            total=total,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch audit log: {e!s}"
        ) from e
