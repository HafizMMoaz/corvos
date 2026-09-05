"""
Admin plans, feature-flags, and entitlements routes: DB-backed CRUD for
`plans`/`feature_flags`/`plan_feature_values`/`plan_model_entitlements`, plus
the per-user actions (plan assignment, entitlements lookup, feature
overrides) that read/write against a specific user's billing state (see
`app.services.entitlement_service`).

Endpoints:
- GET /admin/plans - list all plans. Requires plans:read.
- POST /admin/plans - create a plan. Requires plans:write.
- PUT /admin/plans/{plan_id} - update a plan (partial). Requires
  plans:write.
- DELETE /admin/plans/{plan_id} - hard delete a plan. `User.plan_id` is
  `ON DELETE SET NULL`, so this un-assigns any members rather than erroring;
  there is no "block delete if in use" guard (use `is_active=False` to
  retire a plan without orphaning members' entitlements-by-omission).
  Requires plans:write.
- POST /admin/plans/{plan_id}/model-entitlements - add one allowed
  `config_id` to a plan. Requires plans:write.
- DELETE /admin/plans/{plan_id}/model-entitlements/{config_id} - remove one
  allowed `config_id` from a plan. Requires plans:write.
- GET /admin/plans/{plan_id}/model-entitlements - list a plan's allowed
  `config_id`s. An empty list is a valid, meaningful response (unrestricted),
  not a 404. Requires plans:read.
- PUT /admin/plans/{plan_id}/feature-values/{feature_flag_id} - upsert a
  plan's value for one feature flag. Requires plans:write.
- DELETE /admin/plans/{plan_id}/feature-values/{feature_flag_id} - remove a
  plan's configured value for one feature flag, reverting it to the
  disabled default. Requires plans:write.
- GET /admin/plans/{plan_id}/feature-values - list a plan's configured
  feature flag values (only rows that exist). Requires plans:read.
- GET /admin/feature-flags - list all feature flag definitions. Requires
  feature_flags:read.
- POST /admin/feature-flags - create a feature flag. Requires
  feature_flags:write.
- PUT /admin/feature-flags/{flag_id} - update a feature flag (partial).
  Requires feature_flags:write.
- DELETE /admin/feature-flags/{flag_id} - delete a feature flag (cascades to
  `plan_feature_values`/`user_feature_overrides` referencing it via the DB
  FK). Requires feature_flags:write.
- PUT /admin/users/{user_id}/plan - assign (or, with `plan_id: null`,
  un-assign) a user's plan. Never touches `credit_micros_balance` -- that is
  exclusively the Paddle-fulfillment track's concern. Requires
  billing:write.
- GET /admin/users/{user_id}/entitlements - a user's fully resolved
  entitlement state (`entitlement_service.get_effective_entitlements`).
  Requires billing:read.
- PUT /admin/users/{user_id}/feature-overrides/{feature_flag_id} - upsert a
  forced feature-flag value for one user. `created_by_id` is set only on
  first creation of the row, never overwritten by a later update. Requires
  billing:write.
- DELETE /admin/users/{user_id}/feature-overrides/{feature_flag_id} - remove
  a user's override, reverting to the plan default. Requires billing:write.
- GET /admin/users/{user_id}/feature-overrides - list a user's overrides,
  including expired-but-not-deleted ones (their `expires_at` stays visible).
  Requires billing:read.
- GET /admin/subscriptions - list every Paddle subscription joined with its
  user's email and plan's name, most recently updated first. Read-only:
  subscription state always flows in from Paddle webhooks, so there is no
  admin write action here. Requires billing:read.
- GET /admin/users - paginated user list for the admin Users page, with an
  optional `search` (email/display_name substring, case-insensitive) and
  `plan_id` filter. Requires users:read.

Every mutating route writes one `admin_audit_logs` row via
`record_admin_action` before `commit()`, same ordering as every existing
admin route. Read-only routes (list/get, the entitlements lookup) are never
audited, matching existing precedent. `plan_feature_values`'s two mutating
routes (upsert and delete-to-default) share a single `plan_feature_value.set`
audit action -- deleting a value is itself just "setting" it back to its
disabled default, so no separate delete verb is needed (unlike
`plan_model_entitlements`, whose add/remove are genuinely different
operations on an allowlist). Deleting a plan feature value or a user feature
override is idempotent and still audited even when there was nothing to
remove, mirroring `admin_setting.delete`'s revert-to-default precedent
(`app.services.settings_vault_service.delete_setting`).
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    FeatureFlag,
    PaddleSubscription,
    Plan,
    PlanFeatureValue,
    PlanModelEntitlement,
    PlatformPermission,
    User,
    UserFeatureOverride,
    get_async_session,
)
from app.schemas import (
    AdminSubscriptionRead,
    AdminUserListItemRead,
    AdminUserListResponse,
    FeatureFlagCreate,
    FeatureFlagRead,
    FeatureFlagUpdate,
    PlanCreate,
    PlanFeatureValueRead,
    PlanFeatureValueSet,
    PlanModelEntitlementCreate,
    PlanModelEntitlementRead,
    PlanRead,
    PlanUpdate,
    UserEntitlementsRead,
    UserFeatureOverrideRead,
    UserFeatureOverrideSet,
    UserPlanAssignmentUpdate,
    UserPlanRead,
)
from app.services.entitlement_service import get_effective_entitlements
from app.users import get_auth_context
from app.utils.platform_rbac import check_platform_permission, record_admin_action

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Read / audit-dict helpers
# ---------------------------------------------------------------------------


def _to_plan_read(plan: Plan) -> PlanRead:
    return PlanRead(
        id=plan.id,
        plan_key=plan.plan_key,
        name=plan.name,
        description=plan.description,
        monthly_credit_micros=plan.monthly_credit_micros,
        paddle_price_id=plan.paddle_price_id,
        is_active=plan.is_active,
        updated_by_id=plan.updated_by_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _plan_audit_dict(plan: Plan) -> dict[str, Any]:
    return {
        "plan_key": plan.plan_key,
        "name": plan.name,
        "description": plan.description,
        "monthly_credit_micros": plan.monthly_credit_micros,
        "paddle_price_id": plan.paddle_price_id,
        "is_active": plan.is_active,
    }


def _to_feature_flag_read(flag: FeatureFlag) -> FeatureFlagRead:
    return FeatureFlagRead(
        id=flag.id,
        flag_key=flag.flag_key,
        name=flag.name,
        description=flag.description,
        updated_by_id=flag.updated_by_id,
        created_at=flag.created_at,
        updated_at=flag.updated_at,
    )


def _feature_flag_audit_dict(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "flag_key": flag.flag_key,
        "name": flag.name,
        "description": flag.description,
    }


def _to_plan_feature_value_read(row: PlanFeatureValue) -> PlanFeatureValueRead:
    return PlanFeatureValueRead(
        feature_flag_id=row.feature_flag_id,
        enabled=row.enabled,
        updated_at=row.updated_at,
    )


def _plan_feature_value_audit_dict(
    plan_id: int, feature_flag_id: int, enabled: bool
) -> dict[str, Any]:
    return {"plan_id": plan_id, "feature_flag_id": feature_flag_id, "enabled": enabled}


def _to_user_feature_override_read(
    row: UserFeatureOverride,
) -> UserFeatureOverrideRead:
    return UserFeatureOverrideRead(
        id=row.id,
        user_id=row.user_id,
        feature_flag_id=row.feature_flag_id,
        enabled=row.enabled,
        expires_at=row.expires_at,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _user_feature_override_audit_dict(row: UserFeatureOverride) -> dict[str, Any]:
    return {
        "user_id": str(row.user_id),
        "feature_flag_id": row.feature_flag_id,
        "enabled": row.enabled,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_by_id": str(row.created_by_id) if row.created_by_id else None,
    }


async def _get_plan_or_404(session: AsyncSession, plan_id: int) -> Plan:
    result = await session.execute(select(Plan).filter(Plan.id == plan_id))
    plan = result.scalars().first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


async def _get_feature_flag_or_404(
    session: AsyncSession, feature_flag_id: int
) -> FeatureFlag:
    result = await session.execute(
        select(FeatureFlag).filter(FeatureFlag.id == feature_flag_id)
    )
    flag = result.scalars().first()
    if flag is None:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    return flag


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> User:
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all plans. Requires plans:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_READ.value,
            "You don't have permission to view plans",
        )
        result = await session.execute(select(Plan).order_by(Plan.plan_key))
        return [_to_plan_read(p) for p in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list plans: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list plans: {e!s}"
        ) from e


@router.post("/plans", response_model=PlanRead)
async def create_plan(
    payload: PlanCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new plan. `paddle_price_id` cannot be set here -- set it via
    a later update once the matching Paddle price exists. Requires
    plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        existing = await session.execute(
            select(Plan).filter(Plan.plan_key == payload.plan_key)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A plan with key '{payload.plan_key}' already exists",
            )

        plan = Plan(
            plan_key=payload.plan_key,
            name=payload.name,
            description=payload.description,
            monthly_credit_micros=payload.monthly_credit_micros,
            is_active=payload.is_active,
            updated_by_id=auth.user.id,
        )
        session.add(plan)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan.create",
            target_type="plan",
            target_id=str(plan.id),
            after=_plan_audit_dict(plan),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(plan)

        return _to_plan_read(plan)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create plan: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create plan: {e!s}"
        ) from e


@router.put("/plans/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a plan (partial update). Requires plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        plan = await _get_plan_or_404(session, plan_id)
        before = _plan_audit_dict(plan)

        update_data = payload.model_dump(exclude_unset=True)

        if "plan_key" in update_data and update_data["plan_key"] != plan.plan_key:
            existing = await session.execute(
                select(Plan).filter(
                    Plan.plan_key == update_data["plan_key"], Plan.id != plan_id
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"A plan with key '{update_data['plan_key']}' already exists",
                )

        if update_data.get("paddle_price_id"):
            conflict = await session.execute(
                select(Plan).filter(
                    Plan.paddle_price_id == update_data["paddle_price_id"],
                    Plan.id != plan_id,
                )
            )
            if conflict.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Paddle price '{update_data['paddle_price_id']}' is "
                        "already assigned to another plan"
                    ),
                )

        for key, value in update_data.items():
            setattr(plan, key, value)
        plan.updated_by_id = auth.user.id

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan.update",
            target_type="plan",
            target_id=str(plan_id),
            before=before,
            after=_plan_audit_dict(plan),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(plan)

        return _to_plan_read(plan)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update plan: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update plan: {e!s}"
        ) from e


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Hard delete a plan. `User.plan_id` is `ON DELETE SET NULL`, so any
    members are un-assigned rather than blocking the delete. Requires
    plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        plan = await _get_plan_or_404(session, plan_id)
        before = _plan_audit_dict(plan)
        await session.delete(plan)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan.delete",
            target_type="plan",
            target_id=str(plan_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete plan: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete plan: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Plan model entitlements
# ---------------------------------------------------------------------------


@router.post(
    "/plans/{plan_id}/model-entitlements", response_model=PlanModelEntitlementRead
)
async def add_plan_model_entitlement(
    plan_id: int,
    payload: PlanModelEntitlementCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Add one allowed `config_id` to a plan. Requires plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        await _get_plan_or_404(session, plan_id)

        existing = await session.execute(
            select(PlanModelEntitlement).filter(
                PlanModelEntitlement.plan_id == plan_id,
                PlanModelEntitlement.config_id == payload.config_id,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=(f"Model {payload.config_id} is already entitled for this plan"),
            )

        entitlement = PlanModelEntitlement(plan_id=plan_id, config_id=payload.config_id)
        session.add(entitlement)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan_model_entitlement.add",
            target_type="plan_model_entitlement",
            target_id=str(entitlement.id),
            after={"plan_id": plan_id, "config_id": payload.config_id},
            ip_address=_client_ip(request),
        )

        await session.commit()

        return PlanModelEntitlementRead(plan_id=plan_id, config_id=payload.config_id)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to add plan model entitlement: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to add plan model entitlement: {e!s}"
        ) from e


@router.delete("/plans/{plan_id}/model-entitlements/{config_id}")
async def remove_plan_model_entitlement(
    plan_id: int,
    config_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove one allowed `config_id` from a plan. 404 if the pair doesn't
    exist. Requires plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        await _get_plan_or_404(session, plan_id)

        result = await session.execute(
            select(PlanModelEntitlement).filter(
                PlanModelEntitlement.plan_id == plan_id,
                PlanModelEntitlement.config_id == config_id,
            )
        )
        entitlement = result.scalars().first()
        if entitlement is None:
            raise HTTPException(
                status_code=404, detail="Model entitlement not found for this plan"
            )

        await session.delete(entitlement)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan_model_entitlement.remove",
            target_type="plan_model_entitlement",
            target_id=str(entitlement.id),
            before={"plan_id": plan_id, "config_id": config_id},
            ip_address=_client_ip(request),
        )

        await session.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to remove plan model entitlement: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to remove plan model entitlement: {e!s}"
        ) from e


@router.get("/plans/{plan_id}/model-entitlements", response_model=list[int])
async def list_plan_model_entitlements(
    plan_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List a plan's allowed `config_id`s. An empty list means unrestricted
    (per the ruled default), not "not found". Requires plans:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_READ.value,
            "You don't have permission to view plans",
        )

        await _get_plan_or_404(session, plan_id)

        result = await session.execute(
            select(PlanModelEntitlement.config_id)
            .filter(PlanModelEntitlement.plan_id == plan_id)
            .order_by(PlanModelEntitlement.config_id)
        )
        return list(result.scalars().all())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list plan model entitlements: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list plan model entitlements: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Plan feature values
# ---------------------------------------------------------------------------


@router.put(
    "/plans/{plan_id}/feature-values/{feature_flag_id}",
    response_model=PlanFeatureValueRead,
)
async def set_plan_feature_value(
    plan_id: int,
    feature_flag_id: int,
    payload: PlanFeatureValueSet,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Upsert a plan's value for one feature flag. Requires plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        await _get_plan_or_404(session, plan_id)
        await _get_feature_flag_or_404(session, feature_flag_id)

        result = await session.execute(
            select(PlanFeatureValue).filter(
                PlanFeatureValue.plan_id == plan_id,
                PlanFeatureValue.feature_flag_id == feature_flag_id,
            )
        )
        row = result.scalars().first()
        before = (
            _plan_feature_value_audit_dict(plan_id, feature_flag_id, row.enabled)
            if row is not None
            else None
        )

        if row is None:
            row = PlanFeatureValue(
                plan_id=plan_id,
                feature_flag_id=feature_flag_id,
                enabled=payload.enabled,
            )
            session.add(row)
        else:
            row.enabled = payload.enabled
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan_feature_value.set",
            target_type="plan_feature_value",
            target_id=str(row.id),
            before=before,
            after=_plan_feature_value_audit_dict(plan_id, feature_flag_id, row.enabled),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(row)

        return _to_plan_feature_value_read(row)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to set plan feature value: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to set plan feature value: {e!s}"
        ) from e


@router.delete("/plans/{plan_id}/feature-values/{feature_flag_id}")
async def delete_plan_feature_value(
    plan_id: int,
    feature_flag_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove a plan's configured value for one feature flag, reverting it
    to the disabled default. Idempotent -- still audited even if there was
    no row to remove. Requires plans:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_WRITE.value,
            "You don't have permission to manage plans",
        )

        await _get_plan_or_404(session, plan_id)
        await _get_feature_flag_or_404(session, feature_flag_id)

        result = await session.execute(
            select(PlanFeatureValue).filter(
                PlanFeatureValue.plan_id == plan_id,
                PlanFeatureValue.feature_flag_id == feature_flag_id,
            )
        )
        row = result.scalars().first()
        before = (
            _plan_feature_value_audit_dict(plan_id, feature_flag_id, row.enabled)
            if row is not None
            else None
        )
        target_id = str(row.id) if row is not None else None
        if row is not None:
            await session.delete(row)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="plan_feature_value.set",
            target_type="plan_feature_value",
            target_id=target_id,
            before=before,
            after=_plan_feature_value_audit_dict(plan_id, feature_flag_id, False),
            ip_address=_client_ip(request),
        )

        await session.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete plan feature value: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete plan feature value: {e!s}"
        ) from e


@router.get(
    "/plans/{plan_id}/feature-values", response_model=list[PlanFeatureValueRead]
)
async def list_plan_feature_values(
    plan_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List a plan's configured feature flag values. Only rows that exist
    are returned -- a `feature_flag_id` absent here is off by default for
    this plan. Requires plans:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.PLANS_READ.value,
            "You don't have permission to view plans",
        )

        await _get_plan_or_404(session, plan_id)

        result = await session.execute(
            select(PlanFeatureValue)
            .filter(PlanFeatureValue.plan_id == plan_id)
            .order_by(PlanFeatureValue.feature_flag_id)
        )
        return [_to_plan_feature_value_read(row) for row in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list plan feature values: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list plan feature values: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


@router.get("/feature-flags", response_model=list[FeatureFlagRead])
async def list_feature_flags(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all feature flag definitions. Requires feature_flags:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.FEATURE_FLAGS_READ.value,
            "You don't have permission to view feature flags",
        )
        result = await session.execute(
            select(FeatureFlag).order_by(FeatureFlag.flag_key)
        )
        return [_to_feature_flag_read(f) for f in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list feature flags: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list feature flags: {e!s}"
        ) from e


@router.post("/feature-flags", response_model=FeatureFlagRead)
async def create_feature_flag(
    payload: FeatureFlagCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new feature flag definition. Requires feature_flags:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.FEATURE_FLAGS_WRITE.value,
            "You don't have permission to manage feature flags",
        )

        existing = await session.execute(
            select(FeatureFlag).filter(FeatureFlag.flag_key == payload.flag_key)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A feature flag with key '{payload.flag_key}' already exists",
            )

        flag = FeatureFlag(
            flag_key=payload.flag_key,
            name=payload.name,
            description=payload.description,
            updated_by_id=auth.user.id,
        )
        session.add(flag)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="feature_flag.create",
            target_type="feature_flag",
            target_id=str(flag.id),
            after=_feature_flag_audit_dict(flag),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(flag)

        return _to_feature_flag_read(flag)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create feature flag: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create feature flag: {e!s}"
        ) from e


@router.put("/feature-flags/{flag_id}", response_model=FeatureFlagRead)
async def update_feature_flag(
    flag_id: int,
    payload: FeatureFlagUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a feature flag (partial update). Requires
    feature_flags:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.FEATURE_FLAGS_WRITE.value,
            "You don't have permission to manage feature flags",
        )

        flag = await _get_feature_flag_or_404(session, flag_id)
        before = _feature_flag_audit_dict(flag)

        update_data = payload.model_dump(exclude_unset=True)

        if "flag_key" in update_data and update_data["flag_key"] != flag.flag_key:
            existing = await session.execute(
                select(FeatureFlag).filter(
                    FeatureFlag.flag_key == update_data["flag_key"],
                    FeatureFlag.id != flag_id,
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"A feature flag with key '{update_data['flag_key']}' "
                        "already exists"
                    ),
                )

        for key, value in update_data.items():
            setattr(flag, key, value)
        flag.updated_by_id = auth.user.id

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="feature_flag.update",
            target_type="feature_flag",
            target_id=str(flag_id),
            before=before,
            after=_feature_flag_audit_dict(flag),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(flag)

        return _to_feature_flag_read(flag)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update feature flag: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update feature flag: {e!s}"
        ) from e


@router.delete("/feature-flags/{flag_id}")
async def delete_feature_flag(
    flag_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a feature flag (cascades to `plan_feature_values`/
    `user_feature_overrides` referencing it via the DB FK). Requires
    feature_flags:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.FEATURE_FLAGS_WRITE.value,
            "You don't have permission to manage feature flags",
        )

        flag = await _get_feature_flag_or_404(session, flag_id)
        before = _feature_flag_audit_dict(flag)
        await session.delete(flag)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="feature_flag.delete",
            target_type="feature_flag",
            target_id=str(flag_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete feature flag: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete feature flag: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Per-user billing actions
# ---------------------------------------------------------------------------


@router.put("/users/{user_id}/plan", response_model=UserPlanRead)
async def set_user_plan(
    user_id: UUID,
    payload: UserPlanAssignmentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Assign (or, with `plan_id: null`, un-assign) a user's plan. Only sets
    `user.plan_id` -- never touches `credit_micros_balance`, which is
    exclusively the Paddle-fulfillment track's concern. Requires
    billing:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_WRITE.value,
            "You don't have permission to manage user billing",
        )

        user = await _get_user_or_404(session, user_id)
        if payload.plan_id is not None:
            await _get_plan_or_404(session, payload.plan_id)

        before_plan_id = user.plan_id
        user.plan_id = payload.plan_id

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="user_plan_assignment.set",
            target_type="user_plan_assignment",
            target_id=str(user_id),
            before={"plan_id": before_plan_id},
            after={"plan_id": payload.plan_id},
            ip_address=_client_ip(request),
        )

        await session.commit()

        return UserPlanRead(user_id=user_id, plan_id=payload.plan_id)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to set user plan: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to set user plan: {e!s}"
        ) from e


@router.get("/users/{user_id}/entitlements", response_model=UserEntitlementsRead)
async def get_user_entitlements(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """A user's fully resolved entitlement state. Requires billing:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_READ.value,
            "You don't have permission to view user billing",
        )

        user = await _get_user_or_404(session, user_id)
        result = await get_effective_entitlements(session, user)

        return UserEntitlementsRead(
            user_id=user_id,
            plan=_to_plan_read(result.plan) if result.plan is not None else None,
            feature_flags=result.feature_flags,
            unrestricted_models=result.unrestricted_models,
            allowed_config_ids=sorted(result.allowed_config_ids),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user entitlements: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get user entitlements: {e!s}"
        ) from e


@router.put(
    "/users/{user_id}/feature-overrides/{feature_flag_id}",
    response_model=UserFeatureOverrideRead,
)
async def set_user_feature_override(
    user_id: UUID,
    feature_flag_id: int,
    payload: UserFeatureOverrideSet,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Upsert a forced feature-flag value for one user, overriding their
    plan's value in either direction. `created_by_id` is set only on first
    creation of the row -- a later update by a different admin does not
    overwrite who originally granted it. Requires billing:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_WRITE.value,
            "You don't have permission to manage user billing",
        )

        await _get_user_or_404(session, user_id)
        await _get_feature_flag_or_404(session, feature_flag_id)

        result = await session.execute(
            select(UserFeatureOverride).filter(
                UserFeatureOverride.user_id == user_id,
                UserFeatureOverride.feature_flag_id == feature_flag_id,
            )
        )
        row = result.scalars().first()
        before = _user_feature_override_audit_dict(row) if row is not None else None

        if row is None:
            row = UserFeatureOverride(
                user_id=user_id,
                feature_flag_id=feature_flag_id,
                enabled=payload.enabled,
                expires_at=payload.expires_at,
                created_by_id=auth.user.id,
            )
            session.add(row)
        else:
            row.enabled = payload.enabled
            row.expires_at = payload.expires_at
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="user_feature_override.set",
            target_type="user_feature_override",
            target_id=str(row.id),
            before=before,
            after=_user_feature_override_audit_dict(row),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(row)

        return _to_user_feature_override_read(row)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to set user feature override: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to set user feature override: {e!s}"
        ) from e


@router.delete("/users/{user_id}/feature-overrides/{feature_flag_id}")
async def delete_user_feature_override(
    user_id: UUID,
    feature_flag_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove a user's feature override, reverting to the plan default.
    Idempotent -- still audited even if there was no override to remove.
    Requires billing:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_WRITE.value,
            "You don't have permission to manage user billing",
        )

        await _get_user_or_404(session, user_id)
        await _get_feature_flag_or_404(session, feature_flag_id)

        result = await session.execute(
            select(UserFeatureOverride).filter(
                UserFeatureOverride.user_id == user_id,
                UserFeatureOverride.feature_flag_id == feature_flag_id,
            )
        )
        row = result.scalars().first()
        before = _user_feature_override_audit_dict(row) if row is not None else None
        target_id = str(row.id) if row is not None else None
        if row is not None:
            await session.delete(row)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="user_feature_override.delete",
            target_type="user_feature_override",
            target_id=target_id,
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete user feature override: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete user feature override: {e!s}"
        ) from e


@router.get(
    "/users/{user_id}/feature-overrides", response_model=list[UserFeatureOverrideRead]
)
async def list_user_feature_overrides(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List a user's feature overrides, including expired-but-not-deleted
    ones (their `expires_at` stays visible for history). Requires
    billing:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_READ.value,
            "You don't have permission to view user billing",
        )

        await _get_user_or_404(session, user_id)

        result = await session.execute(
            select(UserFeatureOverride)
            .filter(UserFeatureOverride.user_id == user_id)
            .order_by(UserFeatureOverride.feature_flag_id)
        )
        return [_to_user_feature_override_read(row) for row in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list user feature overrides: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list user feature overrides: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Admin subscriptions / users listings
# ---------------------------------------------------------------------------


@router.get("/subscriptions", response_model=list[AdminSubscriptionRead])
async def list_subscriptions(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List every Paddle subscription joined with its user's email and plan's
    name, most recently updated first. Read-only -- subscription state always
    flows in from Paddle webhooks, so there is no admin write action here.
    Requires billing:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.BILLING_READ.value,
            "You don't have permission to view subscriptions",
        )

        result = await session.execute(
            select(PaddleSubscription, User.email, Plan.name)
            .join(User, PaddleSubscription.user_id == User.id)
            .outerjoin(Plan, PaddleSubscription.plan_id == Plan.id)
            .order_by(PaddleSubscription.updated_at.desc())
        )
        return [
            AdminSubscriptionRead(
                id=sub.id,
                user_id=sub.user_id,
                user_email=email,
                plan_id=sub.plan_id,
                plan_name=plan_name,
                paddle_subscription_id=sub.paddle_subscription_id,
                paddle_customer_id=sub.paddle_customer_id,
                status=sub.status,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
                created_at=sub.created_at,
                updated_at=sub.updated_at,
            )
            for sub, email, plan_name in result.all()
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list subscriptions: {e!s}"
        ) from e


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=200),
    plan_id: int | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Paginated user list for the admin Users page. `search` matches a
    case-insensitive substring of email or display_name; `plan_id` filters to
    one plan. Ordered by email for stable pagination (user has no created_at
    column). Requires users:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.USERS_READ.value,
            "You don't have permission to view users",
        )

        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(User.email.ilike(pattern), User.display_name.ilike(pattern))
            )
        if plan_id is not None:
            filters.append(User.plan_id == plan_id)

        count_stmt = select(func.count()).select_from(User)
        list_stmt = (
            select(User, Plan.name)
            .outerjoin(Plan, User.plan_id == Plan.id)
            .order_by(User.email)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)

        total = (await session.execute(count_stmt)).scalar_one()
        rows = (
            await session.execute(list_stmt.limit(limit).offset(offset))
        ).all()

        return AdminUserListResponse(
            users=[
                AdminUserListItemRead(
                    id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    is_active=user.is_active,
                    is_superuser=user.is_superuser,
                    plan_id=user.plan_id,
                    plan_name=plan_name,
                    credit_micros_balance=user.credit_micros_balance,
                    last_login=user.last_login,
                )
                for user, plan_name in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list users: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list users: {e!s}"
        ) from e
