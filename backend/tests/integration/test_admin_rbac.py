"""Integration tests for the platform-wide admin RBAC system (Phase A of the
super admin dashboard): `app.utils.platform_rbac` and
`app.routes.admin.admin_rbac_routes`.

Route handlers are called directly (session + AuthContext passed in), the
same pattern used by `tests/integration/test_obsidian_plugin_routes.py`,
rather than spinning up an ASGI test client.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.context import AuthContext
from app.db import (
    AdminAuditLog,
    PlatformPermission,
    PlatformRole,
    PlatformRoleAssignment,
    User,
)
from app.routes.admin.admin_rbac_routes import (
    create_platform_role,
    create_platform_role_assignment,
    delete_platform_role,
    delete_platform_role_assignment,
    get_admin_me,
    list_admin_audit_log,
    list_platform_role_assignments,
    list_platform_roles,
)
from app.schemas import (
    PlatformRoleAssignmentCreate,
    PlatformRoleCreate,
)
from app.utils.platform_rbac import (
    check_platform_permission,
    get_platform_permissions,
    is_platform_admin,
    record_admin_action,
)

pytestmark = pytest.mark.integration


def _auth(user: User) -> AuthContext:
    return AuthContext.session(user)


def _fake_request() -> Request:
    return Request(scope={"type": "http", "client": ("127.0.0.1", 0), "headers": []})


async def _make_user(session: AsyncSession, *, email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"{uuid.uuid4()}@corvos.test",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_role(
    session: AsyncSession,
    *,
    name: str,
    permissions: list[str],
    is_system_role: bool = False,
) -> PlatformRole:
    role = PlatformRole(
        name=name, permissions=permissions, is_system_role=is_system_role
    )
    session.add(role)
    await session.flush()
    return role


async def _assign(
    session: AsyncSession, user: User, role: PlatformRole
) -> PlatformRoleAssignment:
    assignment = PlatformRoleAssignment(user_id=user.id, role_id=role.id)
    session.add(assignment)
    await session.flush()
    return assignment


# ---------------------------------------------------------------------------
# app.utils.platform_rbac
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_no_assignment_has_no_permissions(db_session: AsyncSession):
    user = await _make_user(db_session)

    permissions = await get_platform_permissions(db_session, user.id)

    assert permissions == []
    assert await is_platform_admin(db_session, user.id) is False


@pytest.mark.asyncio
async def test_wildcard_role_grants_every_permission(db_session: AsyncSession):
    user = await _make_user(db_session)
    role = await _make_role(
        db_session,
        name="super_admin_test",
        permissions=[PlatformPermission.FULL_ACCESS.value],
    )
    await _assign(db_session, user, role)

    # Should not raise for an arbitrary permission not explicitly listed.
    permissions = await check_platform_permission(
        db_session, _auth(user), PlatformPermission.BILLING_WRITE.value
    )

    assert PlatformPermission.FULL_ACCESS.value in permissions
    assert await is_platform_admin(db_session, user.id) is True


@pytest.mark.asyncio
async def test_scoped_role_denies_unlisted_permission(db_session: AsyncSession):
    user = await _make_user(db_session)
    role = await _make_role(
        db_session, name="support_admin_test", permissions=["users:read"]
    )
    await _assign(db_session, user, role)

    with pytest.raises(HTTPException) as exc:
        await check_platform_permission(
            db_session, _auth(user), PlatformPermission.BILLING_WRITE.value
        )
    assert exc.value.status_code == 403

    # But the granted permission passes.
    await check_platform_permission(db_session, _auth(user), "users:read")


@pytest.mark.asyncio
async def test_record_admin_action_writes_audit_row(db_session: AsyncSession):
    actor = await _make_user(db_session)

    entry = await record_admin_action(
        db_session,
        actor_user_id=actor.id,
        action="test.action",
        target_type="test_target",
        target_id="123",
        before={"a": 1},
        after={"a": 2},
    )

    assert entry.id is not None
    assert entry.action == "test.action"
    assert entry.before == {"a": 1}
    assert entry.after == {"a": 2}


# ---------------------------------------------------------------------------
# app.routes.admin.admin_rbac_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_admin_me_returns_403_for_non_admin(db_session: AsyncSession):
    user = await _make_user(db_session)

    with pytest.raises(HTTPException) as exc:
        await get_admin_me(session=db_session, auth=_auth(user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_admin_me_returns_permissions_and_roles(db_session: AsyncSession):
    user = await _make_user(db_session)
    role = await _make_role(
        db_session, name="billing_admin_test", permissions=["billing:read"]
    )
    await _assign(db_session, user, role)

    result = await get_admin_me(session=db_session, auth=_auth(user))

    assert result.user_id == user.id
    assert "billing:read" in result.permissions
    assert "billing_admin_test" in result.roles


@pytest.mark.asyncio
async def test_create_role_requires_admin_roles_write(db_session: AsyncSession):
    user = await _make_user(db_session)
    role = await _make_role(
        db_session, name="read_only_admin_test", permissions=["users:read"]
    )
    await _assign(db_session, user, role)

    with pytest.raises(HTTPException) as exc:
        await create_platform_role(
            PlatformRoleCreate(name="new_role", permissions=["users:read"]),
            request=_fake_request(),
            session=db_session,
            auth=_auth(user),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_role_and_it_appears_in_list(db_session: AsyncSession):
    admin = await _make_user(db_session)
    admin_role = await _make_role(
        db_session, name="super_admin_test_2", permissions=["*"]
    )
    await _assign(db_session, admin, admin_role)

    created = await create_platform_role(
        PlatformRoleCreate(
            name="content_moderator", permissions=["users:read", "users:write"]
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.name == "content_moderator"
    assert created.is_system_role is False

    roles = await list_platform_roles(session=db_session, auth=_auth(admin))
    assert any(r.name == "content_moderator" for r in roles)

    # The creation itself is audited.
    log = await list_admin_audit_log(
        limit=50,
        offset=0,
        action="platform_role.create",
        target_type="platform_role",
        session=db_session,
        auth=_auth(admin),
    )
    assert log.total >= 1
    assert any(e.target_id == str(created.id) for e in log.entries)


@pytest.mark.asyncio
async def test_create_role_rejects_invalid_permission(db_session: AsyncSession):
    admin = await _make_user(db_session)
    admin_role = await _make_role(
        db_session, name="super_admin_test_3", permissions=["*"]
    )
    await _assign(db_session, admin, admin_role)

    with pytest.raises(HTTPException) as exc:
        await create_platform_role(
            PlatformRoleCreate(name="bad_role", permissions=["not:a:real:permission"]),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_system_role_is_forbidden(db_session: AsyncSession):
    admin = await _make_user(db_session)
    admin_role = await _make_role(
        db_session, name="super_admin_test_4", permissions=["*"]
    )
    await _assign(db_session, admin, admin_role)

    system_role = await _make_role(
        db_session, name="system_role_test", permissions=["users:read"], is_system_role=True
    )

    with pytest.raises(HTTPException) as exc:
        await delete_platform_role(
            system_role.id, request=_fake_request(), session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_role_assignment_grant_and_revoke_round_trip(db_session: AsyncSession):
    admin = await _make_user(db_session)
    admin_role = await _make_role(
        db_session, name="super_admin_test_5", permissions=["*"]
    )
    await _assign(db_session, admin, admin_role)

    target_user = await _make_user(db_session)
    target_role = await _make_role(
        db_session, name="support_admin_test_2", permissions=["users:read"]
    )

    assignment = await create_platform_role_assignment(
        PlatformRoleAssignmentCreate(user_id=target_user.id, role_id=target_role.id),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert assignment.role_name == "support_admin_test_2"
    assert await is_platform_admin(db_session, target_user.id) is True

    assignments = await list_platform_role_assignments(
        session=db_session, auth=_auth(admin)
    )
    assert any(a.id == assignment.id for a in assignments)

    result = await delete_platform_role_assignment(
        assignment.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert result == {"success": True}
    assert await is_platform_admin(db_session, target_user.id) is False


@pytest.mark.asyncio
async def test_duplicate_role_assignment_conflicts(db_session: AsyncSession):
    admin = await _make_user(db_session)
    admin_role = await _make_role(
        db_session, name="super_admin_test_6", permissions=["*"]
    )
    await _assign(db_session, admin, admin_role)

    target_user = await _make_user(db_session)
    target_role = await _make_role(
        db_session, name="support_admin_test_3", permissions=["users:read"]
    )
    await _assign(db_session, target_user, target_role)

    with pytest.raises(HTTPException) as exc:
        await create_platform_role_assignment(
            PlatformRoleAssignmentCreate(
                user_id=target_user.id, role_id=target_role.id
            ),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 409
