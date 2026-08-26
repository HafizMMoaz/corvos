"""Unit tests for `app.services.entitlement_service`'s pure resolution logic:
`get_effective_entitlements`, `user_has_feature`, `user_model_allowed`.

No real database is touched. `_FakeSession` stands in for `AsyncSession`,
dispatching each `select(...)` statement to canned in-memory data by
inspecting the statement's target entity (`stmt.column_descriptions[0]
["entity"]`) -- the same technique-neutral boundary a real Postgres session
would sit behind, so what's under test here is the actual precedence
resolution in `entitlement_service.py`, not a re-implementation of it. Every
row is a real `app.db` ORM instance built directly in memory (never added to
a session), so attribute access matches production exactly.

Route/DB-integration coverage (plan CRUD, model-entitlement/feature-value
upsert routes, permission gating, audit rows) lives in
`tests/integration/routes/test_admin_billing_routes.py` instead, mirroring
the unit/integration split already established by Phase C's LLM catalog
tests (see that module's docstring).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.db import (
    FeatureFlag,
    Plan,
    PlanFeatureValue,
    PlanModelEntitlement,
    User,
    UserFeatureOverride,
)
from app.services.entitlement_service import (
    get_effective_entitlements,
    user_has_feature,
    user_model_allowed,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fake AsyncSession
# ---------------------------------------------------------------------------


class _FakeScalars:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return _FakeScalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


@dataclass
class _FakeSession:
    """Stands in for `AsyncSession` across the fixed, known query shapes
    `get_effective_entitlements` issues. Dispatches on the queried entity
    rather than interpreting the WHERE clause -- the data returned per
    scenario is set up directly by each test, mirroring what a real
    Postgres session would hand back for that user/plan."""

    plan_id: int | None
    plan: Plan | None = None
    feature_flags: list[FeatureFlag] = field(default_factory=list)
    plan_feature_values: list[PlanFeatureValue] = field(default_factory=list)
    user_overrides: list[UserFeatureOverride] = field(default_factory=list)
    plan_model_config_ids: list[int] = field(default_factory=list)

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is User:
            return _FakeResult([self.plan_id])
        if entity is Plan:
            return _FakeResult([self.plan] if self.plan is not None else [])
        if entity is FeatureFlag:
            return _FakeResult(self.feature_flags)
        if entity is PlanFeatureValue:
            return _FakeResult(self.plan_feature_values)
        if entity is UserFeatureOverride:
            now = datetime.now(UTC)
            unexpired = [
                o
                for o in self.user_overrides
                if o.expires_at is None or o.expires_at > now
            ]
            return _FakeResult(unexpired)
        if entity is PlanModelEntitlement:
            return _FakeResult(self.plan_model_config_ids)
        raise AssertionError(f"Unexpected query entity: {entity}")


def _user(plan_id: int | None = None) -> User:
    return User(id=uuid.uuid4(), plan_id=plan_id)


def _flag(id: int, flag_key: str) -> FeatureFlag:
    return FeatureFlag(id=id, flag_key=flag_key, name=flag_key)


# ---------------------------------------------------------------------------
# get_effective_entitlements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_plan_is_unrestricted_and_all_flags_default_false():
    user = _user(plan_id=None)
    session = _FakeSession(
        plan_id=None,
        feature_flags=[_flag(1, "advanced_search"), _flag(2, "beta_ui")],
    )

    result = await get_effective_entitlements(session, user)

    assert result.plan is None
    assert result.unrestricted_models is True
    assert result.allowed_config_ids == frozenset()
    assert result.feature_flags == {"advanced_search": False, "beta_ui": False}


@pytest.mark.asyncio
async def test_plan_with_entitlement_rows_restricts_to_exactly_those_config_ids():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[],
        plan_model_config_ids=[10, 20, 30],
    )

    result = await get_effective_entitlements(session, user)

    assert result.plan is plan
    assert result.unrestricted_models is False
    assert result.allowed_config_ids == frozenset({10, 20, 30})


@pytest.mark.asyncio
async def test_plan_with_zero_entitlement_rows_is_unrestricted():
    """Ruling 1: a plan with zero plan_model_entitlements rows allows every
    model -- an allowlist that only starts restricting once rows exist."""
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="team", name="Team")
    session = _FakeSession(plan_id=1, plan=plan, plan_model_config_ids=[])

    result = await get_effective_entitlements(session, user)

    assert result.unrestricted_models is True
    assert result.allowed_config_ids == frozenset()


@pytest.mark.asyncio
async def test_plan_feature_value_true_with_no_override_is_effective_true():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    flag = _flag(1, "advanced_search")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[flag],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=1, enabled=True)
        ],
    )

    result = await get_effective_entitlements(session, user)

    assert result.feature_flags == {"advanced_search": True}


@pytest.mark.asyncio
async def test_user_override_false_wins_over_plan_feature_value_true():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    flag = _flag(1, "advanced_search")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[flag],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=1, enabled=True)
        ],
        user_overrides=[
            UserFeatureOverride(user_id=user.id, feature_flag_id=1, enabled=False)
        ],
    )

    result = await get_effective_entitlements(session, user)

    assert result.feature_flags == {"advanced_search": False}


@pytest.mark.asyncio
async def test_user_override_true_wins_over_plan_feature_value_false():
    """Override wins in the other direction too -- force-on over a plan
    default of disabled (the ordinary no-row-yet case)."""
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="free", name="Free")
    flag = _flag(1, "beta_ui")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[flag],
        plan_feature_values=[],  # no row -> plan default is disabled
        user_overrides=[
            UserFeatureOverride(user_id=user.id, feature_flag_id=1, enabled=True)
        ],
    )

    result = await get_effective_entitlements(session, user)

    assert result.feature_flags == {"beta_ui": True}


@pytest.mark.asyncio
async def test_expired_override_falls_through_to_plan_default():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    flag = _flag(1, "advanced_search")
    expired_override = UserFeatureOverride(
        user_id=user.id,
        feature_flag_id=1,
        enabled=True,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[flag],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=1, enabled=False)
        ],
        user_overrides=[expired_override],
    )

    result = await get_effective_entitlements(session, user)

    # Falls through to the plan default (disabled), not the expired override.
    assert result.feature_flags == {"advanced_search": False}
    # The row itself is untouched -- entitlement_service never deletes
    # anything, it only stops honoring an expired row at resolution time.
    assert session.user_overrides == [expired_override]
    assert expired_override.enabled is True


@pytest.mark.asyncio
async def test_unexpired_override_with_future_expiry_still_applies():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    flag = _flag(1, "advanced_search")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[flag],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=1, enabled=False)
        ],
        user_overrides=[
            UserFeatureOverride(
                user_id=user.id,
                feature_flag_id=1,
                enabled=True,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        ],
    )

    result = await get_effective_entitlements(session, user)

    assert result.feature_flags == {"advanced_search": True}


@pytest.mark.asyncio
async def test_every_known_flag_key_present_even_without_a_plan_value_row():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[_flag(1, "a"), _flag(2, "b"), _flag(3, "c")],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=2, enabled=True)
        ],
    )

    result = await get_effective_entitlements(session, user)

    assert result.feature_flags == {"a": False, "b": True, "c": False}


# ---------------------------------------------------------------------------
# user_has_feature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_has_feature_returns_resolved_value():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    session = _FakeSession(
        plan_id=1,
        plan=plan,
        feature_flags=[_flag(1, "advanced_search")],
        plan_feature_values=[
            PlanFeatureValue(plan_id=1, feature_flag_id=1, enabled=True)
        ],
    )

    assert await user_has_feature(session, user, "advanced_search") is True


@pytest.mark.asyncio
async def test_user_has_feature_unknown_flag_key_defaults_closed():
    """An unknown flag_key (typo, or a flag deleted after being referenced)
    defaults closed, not open."""
    user = _user(plan_id=None)
    session = _FakeSession(plan_id=None, feature_flags=[_flag(1, "advanced_search")])

    assert await user_has_feature(session, user, "does_not_exist") is False


# ---------------------------------------------------------------------------
# user_model_allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_model_allowed_true_when_unrestricted():
    user = _user(plan_id=None)
    session = _FakeSession(plan_id=None)

    assert await user_model_allowed(session, user, 12345) is True


@pytest.mark.asyncio
async def test_user_model_allowed_checks_membership_when_restricted():
    user = _user(plan_id=1)
    plan = Plan(id=1, plan_key="pro", name="Pro")
    session = _FakeSession(plan_id=1, plan=plan, plan_model_config_ids=[10, 20])

    assert await user_model_allowed(session, user, 10) is True
    assert await user_model_allowed(session, user, 99) is False
