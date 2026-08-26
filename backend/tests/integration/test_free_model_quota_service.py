"""Integration tests for the free-tier model quota track (Phase C Track 2 of
the super admin dashboard): `app.services.free_model_quota_service` and the
`/admin/llm-quota*` routes appended to `app.routes.admin.admin_llm_routes`.

Mirrors the fixture style of `tests/integration/test_admin_llm_catalog.py`
(Phase C Track 1): route handlers are called directly (session + AuthContext
passed in), no ASGI test client.

Most tests use the `db_session` fixture (real Postgres, but every commit is
actually a SAVEPOINT release inside one connection's outer transaction --
see `tests/integration/conftest.py` -- so the whole test's writes roll back
automatically). The concurrent-lock tests are the deliberate exception: they
need two genuinely independent Postgres connections so a `SELECT ... FOR
UPDATE` taken by one can actually block the other, which a single
savepoint-nested connection cannot demonstrate. Those tests open their own
sessions off the shared `async_engine` fixture, commit for real, and clean
up explicitly in a `finally` block.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    AdminAuditLog,
    FreeModelGlobalQuota,
    FreeModelUserQuota,
    PlatformRole,
    PlatformRoleAssignment,
    User,
)
from app.routes.admin import admin_llm_routes as routes
from app.services.free_model_quota_service import (
    FreeQuotaResult,
    free_quota_finalize,
    free_quota_release,
    free_quota_reserve,
    get_global_quota_snapshot,
    get_user_quota_snapshot,
    reset_all_free_quotas_for_new_period,
    reset_global_quota,
    reset_user_quota,
)

pytestmark = pytest.mark.integration

_GLOBAL_ROW_ID = 1


def _current_period_start() -> date:
    now = datetime.now(UTC)
    return date(now.year, now.month, 1)


def _last_period_start() -> date:
    first_of_this_month = _current_period_start()
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    return date(last_day_prev_month.year, last_day_prev_month.month, 1)


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


async def _audit_rows(
    session: AsyncSession, *, action: str, target_id: str | None = None
) -> list[AdminAuditLog]:
    stmt = select(AdminAuditLog).filter(AdminAuditLog.action == action)
    if target_id is not None:
        stmt = stmt.filter(AdminAuditLog.target_id == target_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# free_quota_reserve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reserve_allowed_within_both_caps(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000)

    result = await free_quota_reserve(db_session, db_user.id, 500)

    assert result == FreeQuotaResult(allowed=True, reason=None)

    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.tokens_reserved == 500

    user_row = await get_user_quota_snapshot(db_session, db_user.id)
    assert user_row.tokens_reserved == 500


@pytest.mark.asyncio
async def test_reserve_blocks_global_cap_for_every_user(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Once the global cap is hit, a *different* user's reserve is also
    denied -- the cap is platform-wide, not per-user."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 100)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000_000)

    # Captured up front: `free_quota_reserve`'s internal `session.rollback()`
    # on denial expires every ORM object the session is tracking, so
    # touching `user.id` after a denied call would try to lazily reload the
    # (now-expired) object outside of an awaited context.
    user_a_id = (await _make_user(db_session)).id
    user_b_id = (await _make_user(db_session)).id

    first = await free_quota_reserve(db_session, user_a_id, 100)
    assert first.allowed is True

    second = await free_quota_reserve(db_session, user_b_id, 1)
    assert second.allowed is False
    assert second.reason == "global_cap_exhausted"

    # A denial rolls back the whole transaction, including the
    # get-or-create insert for user_b's row -- so no row was ever actually
    # committed for them. No partial state leaks out of a denied reserve.
    user_b_row = await get_user_quota_snapshot(db_session, user_b_id)
    assert user_b_row is None


@pytest.mark.asyncio
async def test_reserve_blocks_user_cap_independently_of_other_users(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A user hitting their own per-user cap does not block a different
    user who is still under both caps."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 1_000_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 100)

    user_a_id = (await _make_user(db_session)).id
    user_b_id = (await _make_user(db_session)).id

    first = await free_quota_reserve(db_session, user_a_id, 100)
    assert first.allowed is True

    blocked = await free_quota_reserve(db_session, user_a_id, 1)
    assert blocked.allowed is False
    assert blocked.reason == "user_cap_exhausted"

    still_allowed = await free_quota_reserve(db_session, user_b_id, 100)
    assert still_allowed.allowed is True


# ---------------------------------------------------------------------------
# free_quota_finalize / free_quota_release
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_moves_tokens_from_reserved_to_used(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)

    await free_quota_reserve(db_session, db_user.id, 500)
    await free_quota_finalize(
        db_session, db_user.id, actual_tokens=300, reserved_tokens=500
    )

    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.tokens_reserved == 0
    assert global_row.tokens_used == 300

    user_row = await get_user_quota_snapshot(db_session, db_user.id)
    assert user_row.tokens_reserved == 0
    assert user_row.tokens_used == 300


@pytest.mark.asyncio
async def test_finalize_clamps_reserved_release_at_zero(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    """Releasing more than is currently reserved must clamp at 0, not go
    negative (mirrors `credit_finalize`'s clamp)."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)

    await free_quota_reserve(db_session, db_user.id, 200)
    await free_quota_finalize(
        db_session, db_user.id, actual_tokens=50, reserved_tokens=999_999
    )

    user_row = await get_user_quota_snapshot(db_session, db_user.id)
    assert user_row.tokens_reserved == 0
    assert user_row.tokens_used == 50


@pytest.mark.asyncio
async def test_release_returns_reservation_to_pool(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)

    await free_quota_reserve(db_session, db_user.id, 500)
    await free_quota_release(db_session, db_user.id, 500)

    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.tokens_reserved == 0
    assert global_row.tokens_used == 0

    user_row = await get_user_quota_snapshot(db_session, db_user.id)
    assert user_row.tokens_reserved == 0
    assert user_row.tokens_used == 0


# ---------------------------------------------------------------------------
# Period rollover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reserve_rolls_over_stale_global_period_before_checking_cap(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 1_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000_000)

    # Seed a stale global row already sitting at its (old-period) cap -- if
    # rollover didn't happen first, this reserve would be wrongly denied.
    db_session.add(
        FreeModelGlobalQuota(
            id=_GLOBAL_ROW_ID,
            period_start=_last_period_start(),
            tokens_reserved=0,
            tokens_used=1_000,
        )
    )
    await db_session.flush()

    result = await free_quota_reserve(db_session, db_user.id, 100)

    assert result.allowed is True
    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.period_start == _current_period_start()
    assert global_row.tokens_used == 0
    assert global_row.tokens_reserved == 100


@pytest.mark.asyncio
async def test_reserve_rolls_over_stale_user_period_before_checking_cap(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 1_000_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000)

    db_session.add(
        FreeModelUserQuota(
            user_id=db_user.id,
            period_start=_last_period_start(),
            tokens_reserved=0,
            tokens_used=1_000,
        )
    )
    await db_session.flush()

    result = await free_quota_reserve(db_session, db_user.id, 100)

    assert result.allowed is True
    user_row = await get_user_quota_snapshot(db_session, db_user.id)
    assert user_row.period_start == _current_period_start()
    assert user_row.tokens_used == 0
    assert user_row.tokens_reserved == 100


# ---------------------------------------------------------------------------
# get_global_quota_snapshot / get_user_quota_snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_global_quota_snapshot_creates_row_when_missing(
    db_session: AsyncSession,
):
    row = await get_global_quota_snapshot(db_session)
    assert row.id == _GLOBAL_ROW_ID
    assert row.tokens_reserved == 0
    assert row.tokens_used == 0
    assert row.period_start == _current_period_start()


@pytest.mark.asyncio
async def test_get_user_quota_snapshot_returns_none_when_never_used(
    db_session: AsyncSession, db_user: User
):
    assert await get_user_quota_snapshot(db_session, db_user.id) is None


# ---------------------------------------------------------------------------
# reset_global_quota / reset_user_quota / reset_all_free_quotas_for_new_period
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_global_quota_zeroes_and_bumps_period(
    db_session: AsyncSession, db_user: User, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)
    await free_quota_reserve(db_session, db_user.id, 500)

    row = await reset_global_quota(db_session)

    assert row.tokens_reserved == 0
    assert row.tokens_used == 0
    assert row.period_start == _current_period_start()


@pytest.mark.asyncio
async def test_reset_user_quota_get_or_creates_row(
    db_session: AsyncSession, db_user: User
):
    """An admin can reset a user who has never used free tier yet."""
    assert await get_user_quota_snapshot(db_session, db_user.id) is None

    row = await reset_user_quota(db_session, db_user.id)

    assert row.user_id == db_user.id
    assert row.tokens_reserved == 0
    assert row.tokens_used == 0
    assert row.period_start == _current_period_start()


@pytest.mark.asyncio
async def test_reset_all_free_quotas_resets_every_stale_row_and_returns_count(
    db_session: AsyncSession,
):
    """Seeds rows with a stale (last-month) `period_start` directly --
    `free_quota_reserve` always writes the *current* period, so it can't be
    used to set up the "genuinely stale" rows this sweep exists to clean
    up (see the staleness-filter test below for why that distinction
    matters)."""
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    user_c = await _make_user(db_session)

    stale_period = _last_period_start()
    for u in (user_a, user_b, user_c):
        db_session.add(
            FreeModelUserQuota(
                user_id=u.id,
                period_start=stale_period,
                tokens_reserved=10,
                tokens_used=40,
            )
        )
    await db_session.flush()

    count = await reset_all_free_quotas_for_new_period(db_session)
    assert count == 3

    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.tokens_reserved == 0
    assert global_row.tokens_used == 0
    assert global_row.period_start == _current_period_start()

    for u in (user_a, user_b, user_c):
        row = await get_user_quota_snapshot(db_session, u.id)
        assert row.tokens_reserved == 0
        assert row.tokens_used == 0
        assert row.period_start == _current_period_start()


@pytest.mark.asyncio
async def test_reset_all_free_quotas_does_not_touch_rows_already_in_current_period(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Regression test for the Important finding in review: a row that
    already rolled over to the current period (e.g. via a live
    `free_quota_reserve` call that raced ahead of this scheduled sweep)
    must not be wiped by the sweep -- only genuinely stale rows should be
    reset. Covers both the per-user row and the shared global row, since
    the same race applies to both."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)

    current_user = await _make_user(db_session)
    await free_quota_reserve(db_session, current_user.id, 500)

    stale_user = await _make_user(db_session)
    db_session.add(
        FreeModelUserQuota(
            user_id=stale_user.id,
            period_start=_last_period_start(),
            tokens_reserved=10,
            tokens_used=40,
        )
    )
    await db_session.flush()

    count = await reset_all_free_quotas_for_new_period(db_session)

    # Only the stale row was reset and counted -- the already-current user
    # row, and the already-current global row it bumped, are untouched.
    assert count == 1

    current_row = await get_user_quota_snapshot(db_session, current_user.id)
    assert current_row.tokens_reserved == 500

    stale_row = await get_user_quota_snapshot(db_session, stale_user.id)
    assert stale_row.tokens_reserved == 0
    assert stale_row.tokens_used == 0
    assert stale_row.period_start == _current_period_start()

    global_row = await get_global_quota_snapshot(db_session)
    assert global_row.tokens_reserved == 500


# ---------------------------------------------------------------------------
# Admin routes: GET
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_llm_quota_requires_quotas_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.get_llm_quota(session=db_session, auth=_auth(user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_llm_quota_returns_snapshot_and_cap(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 42_000)
    admin = await _make_admin(db_session, permissions=["quotas:read"])

    result = await routes.get_llm_quota(session=db_session, auth=_auth(admin))

    assert result.cap_tokens == 42_000
    assert result.tokens_reserved == 0
    assert result.tokens_used == 0


@pytest.mark.asyncio
async def test_get_llm_quota_for_user_requires_quotas_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.get_llm_quota_for_user(
            user.id, session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_llm_quota_for_user_returns_nulls_when_never_used(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 7_000)
    admin = await _make_admin(db_session, permissions=["quotas:read"])
    target = await _make_user(db_session)

    result = await routes.get_llm_quota_for_user(
        target.id, session=db_session, auth=_auth(admin)
    )

    assert result.user_id == target.id
    assert result.cap_tokens == 7_000
    assert result.period_start is None
    assert result.tokens_reserved is None
    assert result.tokens_used is None
    assert result.updated_at is None


@pytest.mark.asyncio
async def test_get_llm_quota_for_user_returns_usage_when_present(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 1_000_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000_000)
    admin = await _make_admin(db_session, permissions=["quotas:read"])
    target = await _make_user(db_session)
    await free_quota_reserve(db_session, target.id, 250)

    result = await routes.get_llm_quota_for_user(
        target.id, session=db_session, auth=_auth(admin)
    )

    assert result.tokens_reserved == 250


# ---------------------------------------------------------------------------
# Admin routes: POST reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_llm_quota_requires_quotas_write(db_session: AsyncSession):
    user = await _make_admin(db_session, permissions=["quotas:read"])
    with pytest.raises(HTTPException) as exc:
        await routes.reset_llm_quota(
            request=_fake_request(), session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reset_llm_quota_resets_and_writes_audit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)
    admin = await _make_admin(db_session, permissions=["quotas:write"])
    other_user = await _make_user(db_session)
    await free_quota_reserve(db_session, other_user.id, 500)

    result = await routes.reset_llm_quota(
        request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    assert result.tokens_reserved == 0
    assert result.tokens_used == 0

    audit = await _audit_rows(db_session, action="free_model_global_quota.reset")
    assert len(audit) == 1
    assert audit[0].target_type == "free_model_global_quota"
    # `after` is uninformative by construction (a reset always zeroes the
    # row), so `before` is the only half that records what was wiped.
    assert audit[0].before["tokens_reserved"] == 500
    assert audit[0].after["tokens_reserved"] == 0


@pytest.mark.asyncio
async def test_reset_llm_quota_for_user_requires_quotas_write(db_session: AsyncSession):
    user = await _make_admin(db_session, permissions=["quotas:read"])
    target = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.reset_llm_quota_for_user(
            target.id, request=_fake_request(), session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reset_llm_quota_for_user_resets_and_writes_audit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 10_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 10_000)
    admin = await _make_admin(db_session, permissions=["quotas:write"])
    target = await _make_user(db_session)
    await free_quota_reserve(db_session, target.id, 500)

    result = await routes.reset_llm_quota_for_user(
        target.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    assert result.user_id == target.id
    assert result.tokens_reserved == 0
    assert result.tokens_used == 0

    audit = await _audit_rows(
        db_session, action="free_model_user_quota.reset", target_id=str(target.id)
    )
    assert len(audit) == 1
    assert audit[0].target_type == "free_model_user_quota"
    assert audit[0].before["tokens_reserved"] == 500
    assert audit[0].after["tokens_reserved"] == 0


@pytest.mark.asyncio
async def test_reset_llm_quota_for_user_with_no_existing_row_records_null_before(
    db_session: AsyncSession,
):
    """`reset_user_quota` get-or-creates, so an admin can reset a user who
    has never used free tier. `before` is null in that case, which is the
    accurate record that nothing was actually wiped."""
    admin = await _make_admin(db_session, permissions=["quotas:write"])
    target = await _make_user(db_session)

    await routes.reset_llm_quota_for_user(
        target.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    audit = await _audit_rows(
        db_session, action="free_model_user_quota.reset", target_id=str(target.id)
    )
    assert len(audit) == 1
    assert audit[0].before is None


# ---------------------------------------------------------------------------
# Concurrency: prove the row lock actually serializes reservations.
#
# These bypass `db_session`'s savepoint-nested connection deliberately --
# two savepoints on the *same* underlying connection cannot demonstrate a
# real `SELECT ... FOR UPDATE` block, since a single asyncpg connection only
# ever has one statement in flight at a time. Real independent connections
# are required, so real commits happen here; each test cleans up explicitly.
# ---------------------------------------------------------------------------


async def _make_committed_user(session_maker: async_sessionmaker) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_maker() as session:
        session.add(
            User(
                id=user_id,
                email=f"{user_id}@corvos.test",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
        await session.commit()
    return user_id


async def _delete_committed_users(
    session_maker: async_sessionmaker, user_ids: list[uuid.UUID]
) -> None:
    async with session_maker() as session:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest_asyncio.fixture
async def real_session_maker(async_engine) -> async_sessionmaker:
    """Independent, fully-committing sessions against the real test DB
    (distinct from `db_session`'s savepoint-nested connection) -- needed so
    two concurrent coroutines get genuinely separate Postgres connections
    and their row locks can actually contend."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_concurrent_reserve_against_global_row_does_not_over_admit(
    real_session_maker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
):
    """Two different users racing to reserve against the shared global cap:
    only one can fit, and the lock must force them to serialize rather than
    both reading the pre-update state and over-admitting."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 100)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 1_000_000)

    user_a = await _make_committed_user(real_session_maker)
    user_b = await _make_committed_user(real_session_maker)

    try:
        async with real_session_maker() as session:
            await reset_global_quota(session)

        async def _reserve(user_id: uuid.UUID) -> FreeQuotaResult:
            async with real_session_maker() as session:
                return await free_quota_reserve(session, user_id, 60)

        result_a, result_b = await asyncio.gather(_reserve(user_a), _reserve(user_b))

        outcomes = [result_a.allowed, result_b.allowed]
        assert outcomes.count(True) == 1
        assert outcomes.count(False) == 1
        denied = result_a if not result_a.allowed else result_b
        assert denied.reason == "global_cap_exhausted"

        async with real_session_maker() as session:
            global_row = await get_global_quota_snapshot(session)
            # Exactly one 60-token reservation landed -- if the lock hadn't
            # serialized the two calls, both could have read
            # tokens_reserved=0 concurrently and both succeeded, leaving 120
            # (over the 100 cap) reserved.
            assert global_row.tokens_reserved == 60
    finally:
        async with real_session_maker() as session:
            await reset_global_quota(session)
        await _delete_committed_users(real_session_maker, [user_a, user_b])


@pytest.mark.asyncio
async def test_concurrent_reserve_against_same_user_row_does_not_over_admit(
    real_session_maker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
):
    """Two concurrent reserve calls for the *same* user racing against their
    own per-user cap must not both succeed."""
    monkeypatch.setattr(config, "FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS", 1_000_000)
    monkeypatch.setattr(config, "FREE_MODEL_USER_MONTHLY_CAP_TOKENS", 100)

    user_id = await _make_committed_user(real_session_maker)

    try:
        async with real_session_maker() as session:
            await reset_global_quota(session)

        async def _reserve() -> FreeQuotaResult:
            async with real_session_maker() as session:
                return await free_quota_reserve(session, user_id, 60)

        result_1, result_2 = await asyncio.gather(_reserve(), _reserve())

        outcomes = [result_1.allowed, result_2.allowed]
        assert outcomes.count(True) == 1
        assert outcomes.count(False) == 1
        denied = result_1 if not result_1.allowed else result_2
        assert denied.reason == "user_cap_exhausted"

        async with real_session_maker() as session:
            user_row = await get_user_quota_snapshot(session, user_id)
            assert user_row.tokens_reserved == 60
    finally:
        async with real_session_maker() as session:
            await reset_global_quota(session)
        await _delete_committed_users(real_session_maker, [user_id])


# ---------------------------------------------------------------------------
# BYOK must not be charged against the platform's free-tier caps.
#
# Exercised through the real chat model loader rather than a hand-built
# AgentConfig, because the defect lives in the gap between what
# `llm_bundle.py` stamps on the BYOK path (`billing_tier="free"`, which has
# only ever meant "skip the premium credit wallet") and what
# `needs_free_quota` reads.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_byok_model_from_the_chat_loader_does_not_need_free_quota(
    db_session: AsyncSession,
):
    from app.db import Connection, ConnectionScope, Model, ModelSource, Workspace
    from app.tasks.chat.streaming.flows.shared.free_quota import needs_free_quota
    from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle

    user = await _make_user(db_session)
    workspace = Workspace(name=f"WS {uuid.uuid4().hex[:8]}", user_id=user.id)
    db_session.add(workspace)
    await db_session.flush()

    connection = Connection(
        provider="openai",
        api_key="sk-users-own-key",
        extra={},
        scope=ConnectionScope.SEARCH_SPACE,
        enabled=True,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    db_session.add(connection)
    await db_session.flush()

    model = Model(
        connection_id=connection.id,
        model_id="gpt-byok",
        display_name="My Own GPT",
        source=ModelSource.MANUAL,
        supports_chat=True,
        enabled=True,
    )
    db_session.add(model)
    await db_session.flush()

    _llm, agent_config, error = await load_llm_bundle(
        db_session, config_id=model.id, workspace_id=workspace.id
    )

    assert error is None
    assert agent_config is not None
    # The exact shape the finding describes: BYOK is stamped free/non-premium.
    assert agent_config.config_id == model.id > 0
    assert agent_config.billing_tier == "free"
    assert agent_config.is_premium is False
    # ...and must still not be charged against the shared free-tier caps.
    assert needs_free_quota(agent_config, str(user.id)) is False
