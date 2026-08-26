"""Entitlement resolution: what a user's plan and per-user overrides grant
them, for feature flags and model access.

This is the read-only resolution primitive behind the super admin billing
dashboard's plan/feature-flag CRUD (`app.routes.admin.admin_billing_routes`).
It is NOT wired into any live chat, tool-access, or model-resolution call
site in this phase -- that wiring is explicitly out of scope for Phase E,
Track 1 (a controller ruling, not an oversight); a later phase consumes
`user_has_feature`/`user_model_allowed` from application call sites.

Two deliberately opposite ruled defaults:

- `PlanFeatureValue`: absence of a row for `(plan_id, feature_flag_id)` means
  that flag is disabled for the plan. An allowlist of *enabled* flags.
- `PlanModelEntitlement`: absence of *any* row for a plan means every model
  is allowed (unrestricted). Restriction only starts once an admin actively
  adds rows. This direction is required so that every existing user (who
  gets `plan_id = NULL` after migration 180) sees zero behavior change, and
  so a freshly created plan with no entitlements configured yet doesn't
  silently lock its members out of every model.

No row locking anywhere here -- this is pure read/precedence resolution, not
a concurrent-mutation-race path like the free-model quota service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    FeatureFlag,
    Plan,
    PlanFeatureValue,
    PlanModelEntitlement,
    User,
    UserFeatureOverride,
)


@dataclass
class EffectiveEntitlements:
    """A user's fully resolved entitlement state at the moment of the call."""

    plan: Plan | None
    feature_flags: dict[str, bool] = field(default_factory=dict)
    unrestricted_models: bool = True
    allowed_config_ids: frozenset[int] = field(default_factory=frozenset)


async def get_effective_entitlements(
    session: AsyncSession, user: User
) -> EffectiveEntitlements:
    """Resolve `user`'s plan, effective feature flag values, and model
    restriction state.

    Resolution order per feature flag: plan default (from `PlanFeatureValue`,
    or the disabled default if no row exists), then any unexpired
    `UserFeatureOverride` overwrites it in either direction.
    """
    # Fetch by id rather than trusting `user.plan`/`user.plan_id` off a
    # possibly-detached instance -- avoids lazy-load-on-detached surprises in
    # an async context.
    plan_id_result = await session.execute(
        select(User.plan_id).where(User.id == user.id)
    )
    plan_id = plan_id_result.scalar_one_or_none()

    plan: Plan | None = None
    if plan_id is not None:
        plan_result = await session.execute(select(Plan).where(Plan.id == plan_id))
        plan = plan_result.scalars().first()

    all_flags_result = await session.execute(select(FeatureFlag))
    all_flags = all_flags_result.scalars().all()

    plan_values: dict[int, bool] = {}
    if plan_id is not None:
        plan_values_result = await session.execute(
            select(PlanFeatureValue).where(PlanFeatureValue.plan_id == plan_id)
        )
        plan_values = {
            row.feature_flag_id: row.enabled
            for row in plan_values_result.scalars().all()
        }

    feature_flags: dict[str, bool] = {
        flag.flag_key: plan_values.get(flag.id, False) for flag in all_flags
    }
    flag_key_by_id = {flag.id: flag.flag_key for flag in all_flags}

    now = datetime.now(UTC)
    overrides_result = await session.execute(
        select(UserFeatureOverride).where(
            UserFeatureOverride.user_id == user.id,
            or_(
                UserFeatureOverride.expires_at.is_(None),
                UserFeatureOverride.expires_at > now,
            ),
        )
    )
    for override in overrides_result.scalars().all():
        flag_key = flag_key_by_id.get(override.feature_flag_id)
        if flag_key is not None:
            feature_flags[flag_key] = override.enabled

    if plan_id is None:
        unrestricted_models = True
        allowed_config_ids: frozenset[int] = frozenset()
    else:
        entitlements_result = await session.execute(
            select(PlanModelEntitlement.config_id).where(
                PlanModelEntitlement.plan_id == plan_id
            )
        )
        config_ids = list(entitlements_result.scalars().all())
        if config_ids:
            unrestricted_models = False
            allowed_config_ids = frozenset(config_ids)
        else:
            unrestricted_models = True
            allowed_config_ids = frozenset()

    return EffectiveEntitlements(
        plan=plan,
        feature_flags=feature_flags,
        unrestricted_models=unrestricted_models,
        allowed_config_ids=allowed_config_ids,
    )


async def user_has_feature(session: AsyncSession, user: User, flag_key: str) -> bool:
    """Whether `user` has `flag_key` effectively enabled. An unknown
    `flag_key` (typo, or a flag deleted after being referenced) defaults
    closed, not open."""
    result = await get_effective_entitlements(session, user)
    return result.feature_flags.get(flag_key, False)


async def user_model_allowed(session: AsyncSession, user: User, config_id: int) -> bool:
    """Whether `user` is allowed to use the model identified by `config_id`
    (the synthetic cross-source model id, see `PlanModelEntitlement`)."""
    result = await get_effective_entitlements(session, user)
    if result.unrestricted_models:
        return True
    return config_id in result.allowed_config_ids
