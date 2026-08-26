"""Integration tests for the super admin plans/feature-flags/entitlements
routes (Phase E, Track 1 of the super admin dashboard):
`app.routes.admin.admin_billing_routes`.

Route handlers are called directly (session + AuthContext passed in), the
same pattern used by `tests/integration/test_admin_connector_credentials.py`
(Phase D) and `tests/integration/test_admin_llm_catalog.py` (Phase C), rather
than spinning up an ASGI test client. This file has no shared fixture module
to import the `_auth`/`_fake_request`/`_make_user`/`_make_admin` helpers
from, so they're duplicated here, same as those files do.

`app.services.entitlement_service`'s own resolution logic is covered by
`tests/unit/services/test_entitlement_service.py` against a fake session;
this file only exercises the CRUD routes built on top of it (permission
gating, 409/404 handling, audit logging, and the couple of behavioral
guarantees that only make sense against a real DB -- plan deletion
un-assigning members via `ON DELETE SET NULL`, and a plan assignment never
touching `credit_micros_balance`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.context import AuthContext
from app.db import (
    AdminAuditLog,
    FeatureFlag,
    Plan,
    PlatformRole,
    PlatformRoleAssignment,
    User,
)
from app.routes.admin import admin_billing_routes as routes
from app.schemas import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    PlanCreate,
    PlanFeatureValueSet,
    PlanModelEntitlementCreate,
    PlanUpdate,
    UserFeatureOverrideSet,
    UserPlanAssignmentUpdate,
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


async def _make_admin(
    session: AsyncSession, *, permissions: list[str], name: str | None = None
) -> User:
    """Create a user granted exactly `permissions` via a fresh platform role."""
    user = await _make_user(session)
    role = PlatformRole(
        name=name or f"role_{uuid.uuid4().hex[:8]}",
        permissions=permissions,
        is_system_role=False,
    )
    session.add(role)
    await session.flush()
    session.add(PlatformRoleAssignment(user_id=user.id, role_id=role.id))
    await session.flush()
    return user


async def _make_plan(session: AsyncSession, *, plan_key: str | None = None) -> Plan:
    plan = Plan(
        plan_key=plan_key or f"plan_{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_credit_micros=0,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def _make_flag(
    session: AsyncSession, *, flag_key: str | None = None
) -> FeatureFlag:
    flag = FeatureFlag(
        flag_key=flag_key or f"flag_{uuid.uuid4().hex[:8]}", name="Test Flag"
    )
    session.add(flag)
    await session.flush()
    return flag


async def _audit_rows(
    session: AsyncSession, *, action: str, target_id: str | None = None
) -> list[AdminAuditLog]:
    stmt = select(AdminAuditLog).filter(AdminAuditLog.action == action)
    if target_id is not None:
        stmt = stmt.filter(AdminAuditLog.target_id == target_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_crud_round_trip_and_409_on_duplicate_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["plans:read", "plans:write"])

    created = await routes.create_plan(
        PlanCreate(
            plan_key="pro",
            name="Pro",
            description="Pro tier",
            monthly_credit_micros=5_000_000,
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.plan_key == "pro"
    assert created.monthly_credit_micros == 5_000_000
    assert created.paddle_price_id is None
    assert created.is_active is True
    assert created.updated_by_id == admin.id

    listed = await routes.list_plans(session=db_session, auth=_auth(admin))
    assert any(p.id == created.id for p in listed)

    with pytest.raises(HTTPException) as exc:
        await routes.create_plan(
            PlanCreate(plan_key="pro", name="Pro Duplicate"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 409

    updated = await routes.update_plan(
        created.id,
        PlanUpdate(name="Pro Renamed", paddle_price_id="pri_123"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.name == "Pro Renamed"
    assert updated.paddle_price_id == "pri_123"
    # Untouched fields survive the partial update.
    assert updated.description == "Pro tier"
    assert updated.monthly_credit_micros == 5_000_000

    deleted = await routes.delete_plan(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert deleted == {"success": True}

    with pytest.raises(HTTPException) as exc:
        await routes.update_plan(
            created.id,
            PlanUpdate(name="ghost"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_plan_delete_unassigns_members_without_erroring(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["plans:write", "billing:write"])
    plan = await _make_plan(db_session)
    member = await _make_user(db_session)

    await routes.set_user_plan(
        member.id,
        UserPlanAssignmentUpdate(plan_id=plan.id),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    await db_session.refresh(member)
    assert member.plan_id == plan.id

    result = await routes.delete_plan(
        plan.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert result == {"success": True}

    await db_session.refresh(member)
    assert member.plan_id is None


# ---------------------------------------------------------------------------
# Feature flag CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feature_flag_crud_round_trip_and_409_on_duplicate_key(
    db_session: AsyncSession,
):
    admin = await _make_admin(
        db_session, permissions=["feature_flags:read", "feature_flags:write"]
    )

    created = await routes.create_feature_flag(
        FeatureFlagCreate(flag_key="advanced_search", name="Advanced Search"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.flag_key == "advanced_search"

    with pytest.raises(HTTPException) as exc:
        await routes.create_feature_flag(
            FeatureFlagCreate(flag_key="advanced_search", name="Dup"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 409

    updated = await routes.update_feature_flag(
        created.id,
        FeatureFlagUpdate(description="now with a description"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.description == "now with a description"
    assert updated.flag_key == "advanced_search"

    listed = await routes.list_feature_flags(session=db_session, auth=_auth(admin))
    assert any(f.id == created.id for f in listed)

    deleted = await routes.delete_feature_flag(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert deleted == {"success": True}

    with pytest.raises(HTTPException) as exc:
        await routes.update_feature_flag(
            created.id,
            FeatureFlagUpdate(name="ghost"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Plan model entitlements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_model_entitlement_add_remove_list(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["plans:read", "plans:write"])
    plan = await _make_plan(db_session)

    empty = await routes.list_plan_model_entitlements(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert empty == []

    added = await routes.add_plan_model_entitlement(
        plan.id,
        PlanModelEntitlementCreate(config_id=100),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert added.plan_id == plan.id
    assert added.config_id == 100

    with pytest.raises(HTTPException) as exc:
        await routes.add_plan_model_entitlement(
            plan.id,
            PlanModelEntitlementCreate(config_id=100),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 409

    await routes.add_plan_model_entitlement(
        plan.id,
        PlanModelEntitlementCreate(config_id=200),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    listed = await routes.list_plan_model_entitlements(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert listed == [100, 200]

    removed = await routes.remove_plan_model_entitlement(
        plan.id, 100, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert removed == {"success": True}

    with pytest.raises(HTTPException) as exc:
        await routes.remove_plan_model_entitlement(
            plan.id, 999, request=_fake_request(), session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 404

    final = await routes.list_plan_model_entitlements(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert final == [200]


# ---------------------------------------------------------------------------
# Plan feature values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_feature_value_upsert_delete_list(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["plans:read", "plans:write"])
    plan = await _make_plan(db_session)
    flag = await _make_flag(db_session)

    empty = await routes.list_plan_feature_values(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert empty == []

    set_true = await routes.set_plan_feature_value(
        plan.id,
        flag.id,
        PlanFeatureValueSet(enabled=True),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert set_true.feature_flag_id == flag.id
    assert set_true.enabled is True

    set_false = await routes.set_plan_feature_value(
        plan.id,
        flag.id,
        PlanFeatureValueSet(enabled=False),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert set_false.enabled is False

    listed = await routes.list_plan_feature_values(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert len(listed) == 1
    assert listed[0].feature_flag_id == flag.id
    assert listed[0].enabled is False

    deleted = await routes.delete_plan_feature_value(
        plan.id, flag.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert deleted == {"success": True}

    after_delete = await routes.list_plan_feature_values(
        plan.id, session=db_session, auth=_auth(admin)
    )
    assert after_delete == []

    # Deleting again with no row present is idempotent, not a 404.
    deleted_again = await routes.delete_plan_feature_value(
        plan.id, flag.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert deleted_again == {"success": True}


# ---------------------------------------------------------------------------
# Permission gating: each of the 3 permission pairs is independent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plans_write_only_role_cannot_touch_feature_flags_or_billing(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["plans:write"])
    other_user = await _make_user(db_session)

    # Granted: plans:write.
    created = await routes.create_plan(
        PlanCreate(plan_key="grantcheck", name="Grant Check"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.plan_key == "grantcheck"

    # Not granted: feature_flags:write.
    with pytest.raises(HTTPException) as exc:
        await routes.create_feature_flag(
            FeatureFlagCreate(flag_key="nope", name="Nope"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403

    # Not granted: feature_flags:read.
    with pytest.raises(HTTPException) as exc:
        await routes.list_feature_flags(session=db_session, auth=_auth(admin))
    assert exc.value.status_code == 403

    # Not granted: billing:write.
    with pytest.raises(HTTPException) as exc:
        await routes.set_user_plan(
            other_user.id,
            UserPlanAssignmentUpdate(plan_id=None),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_feature_flags_write_only_role_cannot_touch_plans_or_billing(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["feature_flags:write"])
    other_user = await _make_user(db_session)

    created = await routes.create_feature_flag(
        FeatureFlagCreate(flag_key="grantcheck2", name="Grant Check 2"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.flag_key == "grantcheck2"

    with pytest.raises(HTTPException) as exc:
        await routes.create_plan(
            PlanCreate(plan_key="nope2", name="Nope"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await routes.set_user_plan(
            other_user.id,
            UserPlanAssignmentUpdate(plan_id=None),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_billing_write_only_role_cannot_touch_plans_or_feature_flags(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["billing:write"])
    target_user = await _make_user(db_session)

    # Granted: billing:write (unassigning requires no plan lookup).
    result = await routes.set_user_plan(
        target_user.id,
        UserPlanAssignmentUpdate(plan_id=None),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert result.plan_id is None

    with pytest.raises(HTTPException) as exc:
        await routes.create_plan(
            PlanCreate(plan_key="nope3", name="Nope"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await routes.create_feature_flag(
            FeatureFlagCreate(flag_key="nope3", name="Nope"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# User plan assignment never touches credit_micros_balance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_user_plan_does_not_change_credit_balance(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["billing:write"])
    plan = await _make_plan(db_session)
    member = await _make_user(db_session)
    member.credit_micros_balance = 4_242_000
    await db_session.flush()
    balance_before = member.credit_micros_balance

    result = await routes.set_user_plan(
        member.id,
        UserPlanAssignmentUpdate(plan_id=plan.id),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert result.plan_id == plan.id

    await db_session.refresh(member)
    assert member.credit_micros_balance == balance_before
    assert member.credit_micros_balance == 4_242_000


@pytest.mark.asyncio
async def test_set_user_plan_rejects_unknown_user_and_unknown_plan(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["billing:write"])
    real_user = await _make_user(db_session)

    with pytest.raises(HTTPException) as exc:
        await routes.set_user_plan(
            uuid.uuid4(),
            UserPlanAssignmentUpdate(plan_id=None),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await routes.set_user_plan(
            real_user.id,
            UserPlanAssignmentUpdate(plan_id=999_999),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# User feature overrides
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_feature_override_created_by_id_preserved_across_update_by_different_admin(
    db_session: AsyncSession,
):
    admin1 = await _make_admin(db_session, permissions=["billing:write"])
    admin2 = await _make_admin(db_session, permissions=["billing:write"])
    target_user = await _make_user(db_session)
    flag = await _make_flag(db_session)

    first = await routes.set_user_feature_override(
        target_user.id,
        flag.id,
        UserFeatureOverrideSet(enabled=True, expires_at=None),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin1),
    )
    assert first.created_by_id == admin1.id
    assert first.enabled is True

    second = await routes.set_user_feature_override(
        target_user.id,
        flag.id,
        UserFeatureOverrideSet(enabled=False, expires_at=None),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin2),
    )
    # The forced value changed, but who originally granted it did not.
    assert second.enabled is False
    assert second.created_by_id == admin1.id
    assert second.created_by_id != admin2.id


@pytest.mark.asyncio
async def test_user_feature_override_delete_is_idempotent_and_list_shows_expired_rows(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["billing:write", "billing:read"])
    target_user = await _make_user(db_session)
    flag = await _make_flag(db_session)

    await routes.set_user_feature_override(
        target_user.id,
        flag.id,
        UserFeatureOverrideSet(
            enabled=True, expires_at=datetime.now(UTC) - timedelta(days=1)
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    # Expired-but-not-deleted rows still show up in the list view.
    listed = await routes.list_user_feature_overrides(
        target_user.id, session=db_session, auth=_auth(admin)
    )
    assert len(listed) == 1
    assert listed[0].expires_at is not None

    deleted = await routes.delete_user_feature_override(
        target_user.id,
        flag.id,
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert deleted == {"success": True}

    listed_after = await routes.list_user_feature_overrides(
        target_user.id, session=db_session, auth=_auth(admin)
    )
    assert listed_after == []

    # Deleting again with nothing present is idempotent, not a 404.
    deleted_again = await routes.delete_user_feature_override(
        target_user.id,
        flag.id,
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert deleted_again == {"success": True}


# ---------------------------------------------------------------------------
# Entitlements lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_entitlements_returns_resolved_state(db_session: AsyncSession):
    admin = await _make_admin(
        db_session, permissions=["billing:read", "billing:write", "plans:write"]
    )
    plan = await _make_plan(db_session)
    flag = await _make_flag(db_session)
    member = await _make_user(db_session)

    await routes.add_plan_model_entitlement(
        plan.id,
        PlanModelEntitlementCreate(config_id=7),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    await routes.set_plan_feature_value(
        plan.id,
        flag.id,
        PlanFeatureValueSet(enabled=True),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    await routes.set_user_plan(
        member.id,
        UserPlanAssignmentUpdate(plan_id=plan.id),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    entitlements = await routes.get_user_entitlements(
        member.id, session=db_session, auth=_auth(admin)
    )

    assert entitlements.plan is not None
    assert entitlements.plan.id == plan.id
    assert entitlements.feature_flags[flag.flag_key] is True
    assert entitlements.unrestricted_models is False
    assert entitlements.allowed_config_ids == [7]


@pytest.mark.asyncio
async def test_get_user_entitlements_rejects_unknown_user(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["billing:read"])
    with pytest.raises(HTTPException) as exc:
        await routes.get_user_entitlements(
            uuid.uuid4(), session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Audit log: exact <resource>.<verb> action strings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mutating_routes_write_audit_rows_with_exact_action_strings(
    db_session: AsyncSession,
):
    admin = await _make_admin(
        db_session,
        permissions=[
            "plans:read",
            "plans:write",
            "feature_flags:read",
            "feature_flags:write",
            "billing:read",
            "billing:write",
        ],
    )

    plan = await routes.create_plan(
        PlanCreate(plan_key="audit_plan", name="Audit Plan"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert (
        len(await _audit_rows(db_session, action="plan.create", target_id=str(plan.id)))
        == 1
    )

    await routes.update_plan(
        plan.id,
        PlanUpdate(name="Audit Plan Renamed"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert (
        len(await _audit_rows(db_session, action="plan.update", target_id=str(plan.id)))
        == 1
    )

    flag = await routes.create_feature_flag(
        FeatureFlagCreate(flag_key="audit_flag", name="Audit Flag"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert (
        len(
            await _audit_rows(
                db_session, action="feature_flag.create", target_id=str(flag.id)
            )
        )
        == 1
    )

    await routes.update_feature_flag(
        flag.id,
        FeatureFlagUpdate(name="Audit Flag Renamed"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert (
        len(
            await _audit_rows(
                db_session, action="feature_flag.update", target_id=str(flag.id)
            )
        )
        == 1
    )

    entitlement = await routes.add_plan_model_entitlement(
        plan.id,
        PlanModelEntitlementCreate(config_id=42),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    add_rows = await _audit_rows(db_session, action="plan_model_entitlement.add")
    assert any(r.after == {"plan_id": plan.id, "config_id": 42} for r in add_rows)

    await routes.remove_plan_model_entitlement(
        plan.id,
        entitlement.config_id,
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    remove_rows = await _audit_rows(db_session, action="plan_model_entitlement.remove")
    assert any(r.before == {"plan_id": plan.id, "config_id": 42} for r in remove_rows)

    fv_row = await routes.set_plan_feature_value(
        plan.id,
        flag.id,
        PlanFeatureValueSet(enabled=True),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    set_rows = await _audit_rows(db_session, action="plan_feature_value.set")
    assert any(
        r.after == {"plan_id": plan.id, "feature_flag_id": flag.id, "enabled": True}
        for r in set_rows
    )
    assert fv_row.enabled is True

    await routes.delete_plan_feature_value(
        plan.id, flag.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    set_rows_after_delete = await _audit_rows(
        db_session, action="plan_feature_value.set"
    )
    assert any(
        r.after == {"plan_id": plan.id, "feature_flag_id": flag.id, "enabled": False}
        for r in set_rows_after_delete
    )

    target_user = await _make_user(db_session)
    await routes.set_user_plan(
        target_user.id,
        UserPlanAssignmentUpdate(plan_id=plan.id),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assignment_rows = await _audit_rows(
        db_session, action="user_plan_assignment.set", target_id=str(target_user.id)
    )
    assert len(assignment_rows) == 1
    assert assignment_rows[0].after == {"plan_id": plan.id}

    override = await routes.set_user_feature_override(
        target_user.id,
        flag.id,
        UserFeatureOverrideSet(enabled=True, expires_at=None),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert (
        len(
            await _audit_rows(
                db_session,
                action="user_feature_override.set",
                target_id=str(override.id),
            )
        )
        == 1
    )

    await routes.delete_user_feature_override(
        target_user.id,
        flag.id,
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    delete_rows = await _audit_rows(
        db_session, action="user_feature_override.delete", target_id=str(override.id)
    )
    assert len(delete_rows) == 1

    await routes.delete_feature_flag(
        flag.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert (
        len(
            await _audit_rows(
                db_session, action="feature_flag.delete", target_id=str(flag.id)
            )
        )
        == 1
    )

    await routes.delete_plan(
        plan.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert (
        len(await _audit_rows(db_session, action="plan.delete", target_id=str(plan.id)))
        == 1
    )
