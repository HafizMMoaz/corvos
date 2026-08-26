"""
Atomic free-tier token quota service (global + per-user monthly caps).

Mirrors `app.services.token_quota_service.TokenQuotaService`'s Postgres
row-lock reserve/finalize/release lifecycle (`credit_reserve`/
`credit_finalize`/`credit_release`), applied to `free_model_global_quota`
(singleton, id=1) and `free_model_user_quota` (one row per user) instead of
the `User` row's micro-USD credit columns -- token-counted instead of
dollar-counted, with two caps enforced in the same transaction instead of
one.

Storage: both tables were created by migration 177
(`177_add_admin_llm_catalog_and_quota`); this module is their first
consumer. Neither table has a request_id/idempotency-key column -- this is a
deliberate scope decision already baked into the schema.

Period handling: a "period" is a calendar month, represented by
`period_start` (first day of the month, UTC). Every reserve/finalize/release
call locks the row it needs and, before using it, lazily rolls it to the
current period if `period_start` is stale (zeroing both counters). This
keeps enforcement correct even if the monthly Celery reset task
(`app.tasks.celery_tasks.free_model_quota_reset_task`) hasn't run yet.

Lock ordering: every one of reserve/finalize/release locks the global row
before the user row, inside one transaction per call. This is consistent
across every code path so two concurrent requests can never deadlock, and it
means every free-tier reservation across the whole platform serializes
through the one global row -- the intended effect of "global shared cap
enforced strictly," not a bug to optimize away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import FreeModelGlobalQuota, FreeModelUserQuota

_GLOBAL_QUOTA_ROW_ID = 1


@dataclass
class FreeQuotaResult:
    allowed: bool
    reason: str | None = None  # "global_cap_exhausted" | "user_cap_exhausted" | None


def _current_period_start() -> date:
    """First day of the current UTC month."""
    now = datetime.now(UTC)
    return date(now.year, now.month, 1)


async def _get_or_create_global_locked(session: AsyncSession) -> FreeModelGlobalQuota:
    """Get-or-create the singleton global row and lock it with
    ``SELECT ... FOR UPDATE``, rolling it to the current period if stale.

    Uses ``INSERT ... ON CONFLICT DO NOTHING`` first so two concurrent
    first-ever callers can't race to create the row.
    """
    period = _current_period_start()
    await session.execute(
        pg_insert(FreeModelGlobalQuota)
        .values(
            id=_GLOBAL_QUOTA_ROW_ID,
            period_start=period,
            tokens_reserved=0,
            tokens_used=0,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    row = (
        await session.execute(
            select(FreeModelGlobalQuota)
            .where(FreeModelGlobalQuota.id == _GLOBAL_QUOTA_ROW_ID)
            .with_for_update(of=FreeModelGlobalQuota)
        )
    ).scalar_one()

    if row.period_start < period:
        row.tokens_reserved = 0
        row.tokens_used = 0
        row.period_start = period

    return row


async def _get_or_create_user_locked(
    session: AsyncSession, user_id: UUID
) -> FreeModelUserQuota:
    """Get-or-create the per-user row and lock it with
    ``SELECT ... FOR UPDATE``, rolling it to the current period if stale.
    Same get-or-create race protection as the global row.
    """
    period = _current_period_start()
    await session.execute(
        pg_insert(FreeModelUserQuota)
        .values(
            user_id=user_id,
            period_start=period,
            tokens_reserved=0,
            tokens_used=0,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    row = (
        await session.execute(
            select(FreeModelUserQuota)
            .where(FreeModelUserQuota.user_id == user_id)
            .with_for_update(of=FreeModelUserQuota)
        )
    ).scalar_one()

    if row.period_start < period:
        row.tokens_reserved = 0
        row.tokens_used = 0
        row.period_start = period

    return row


async def free_quota_reserve(
    session: AsyncSession, user_id: UUID, reserve_tokens: int
) -> FreeQuotaResult:
    """Reserve ``reserve_tokens`` against both the global and per-user
    monthly caps in one transaction.

    Locks the global row, then the user row (get-or-create, roll period if
    stale, in that order). Blocks on whichever cap would be exceeded first
    -- the global cap is checked before the user cap, matching the lock
    order. Denial rolls back (releasing both locks) without reserving
    anything; approval increments both rows' ``tokens_reserved`` and
    commits.
    """
    global_row = await _get_or_create_global_locked(session)
    user_row = await _get_or_create_user_locked(session, user_id)

    if (
        global_row.tokens_used + global_row.tokens_reserved + reserve_tokens
        > config.FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS
    ):
        await session.rollback()
        return FreeQuotaResult(allowed=False, reason="global_cap_exhausted")

    if (
        user_row.tokens_used + user_row.tokens_reserved + reserve_tokens
        > config.FREE_MODEL_USER_MONTHLY_CAP_TOKENS
    ):
        await session.rollback()
        return FreeQuotaResult(allowed=False, reason="user_cap_exhausted")

    global_row.tokens_reserved += reserve_tokens
    user_row.tokens_reserved += reserve_tokens
    await session.commit()

    return FreeQuotaResult(allowed=True)


async def free_quota_finalize(
    session: AsyncSession, user_id: UUID, actual_tokens: int, reserved_tokens: int
) -> None:
    """Settle a reservation: release ``reserved_tokens`` (clamped at 0, same
    as ``credit_finalize``) from both rows' ``tokens_reserved`` and add
    ``actual_tokens`` to both rows' ``tokens_used``.

    Does not raise on a stale/rolled period -- if the period rolled over
    between reserve and finalize (a stream that straddles a month
    boundary), this finalizes against whatever the row now holds (freshly
    zeroed by the get-or-create-locked helper above). This is an accepted
    rare-edge-case simplification, not a gap to solve here (the existing
    `credit_finalize` has no period concept at all to compare against).
    """
    global_row = await _get_or_create_global_locked(session)
    user_row = await _get_or_create_user_locked(session, user_id)

    global_row.tokens_reserved = max(0, global_row.tokens_reserved - reserved_tokens)
    global_row.tokens_used += actual_tokens

    user_row.tokens_reserved = max(0, user_row.tokens_reserved - reserved_tokens)
    user_row.tokens_used += actual_tokens

    await session.commit()


async def free_quota_release(
    session: AsyncSession, user_id: UUID, reserved_tokens: int
) -> None:
    """Release ``reserved_tokens`` (clamped at 0) from both rows'
    ``tokens_reserved`` on a cancellation path. Never raises internally --
    same as `credit_release`, the caller (`release_free_quota`) wraps this
    in try/except.
    """
    global_row = await _get_or_create_global_locked(session)
    user_row = await _get_or_create_user_locked(session, user_id)

    global_row.tokens_reserved = max(0, global_row.tokens_reserved - reserved_tokens)
    user_row.tokens_reserved = max(0, user_row.tokens_reserved - reserved_tokens)

    await session.commit()


async def get_global_quota_snapshot(session: AsyncSession) -> FreeModelGlobalQuota:
    """Get-or-create the global row (id=1) for display. Read-only -- no
    ``FOR UPDATE`` lock, since a view doesn't need to serialize against
    concurrent reservations.
    """
    await session.execute(
        pg_insert(FreeModelGlobalQuota)
        .values(
            id=_GLOBAL_QUOTA_ROW_ID,
            period_start=_current_period_start(),
            tokens_reserved=0,
            tokens_used=0,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.commit()

    return (
        await session.execute(
            select(FreeModelGlobalQuota).where(
                FreeModelGlobalQuota.id == _GLOBAL_QUOTA_ROW_ID
            )
        )
    ).scalar_one()


async def get_user_quota_snapshot(
    session: AsyncSession, user_id: UUID
) -> FreeModelUserQuota | None:
    """Return the user's row, or None if they've never reserved free-tier
    quota yet. Does not create one just for a view.
    """
    return (
        await session.execute(
            select(FreeModelUserQuota).where(FreeModelUserQuota.user_id == user_id)
        )
    ).scalar_one_or_none()


async def reset_global_quota(session: AsyncSession) -> FreeModelGlobalQuota:
    """Admin manual reset: zero the global row's counters and bump
    `period_start` to the current period. Caller (the route handler) owns
    the audit log entry -- this function only does the DB mutation,
    mirroring how `admin_llm_catalog_service.apply_admin_llm_configs` stays
    audit-agnostic and lets its callers own that.
    """
    row = await _get_or_create_global_locked(session)
    row.tokens_reserved = 0
    row.tokens_used = 0
    row.period_start = _current_period_start()
    await session.commit()
    return row


async def reset_user_quota(session: AsyncSession, user_id: UUID) -> FreeModelUserQuota:
    """Admin manual reset for one user's row. Get-or-create first -- an
    admin may want to pre-emptively reset a user who's never used free tier
    yet, unusual but harmless.
    """
    row = await _get_or_create_user_locked(session, user_id)
    row.tokens_reserved = 0
    row.tokens_used = 0
    row.period_start = _current_period_start()
    await session.commit()
    return row


async def reset_all_free_quotas_for_new_period(session: AsyncSession) -> int:
    """Bulk reset for the monthly Celery sweep: reset the global row and
    every stale `free_model_user_quota` row to the current period.

    Uses bulk ``UPDATE`` statements instead of ``SELECT ... FOR UPDATE`` +
    a Python-side loop. Postgres holds row locks until the transaction
    ends either way, so the win is not that the bulk form releases locks
    earlier -- it is that the whole sweep is one short server-side
    statement per table rather than a round-trip-per-row Python loop, so
    the window during which those locks are held is a fraction as long.
    Every free-tier reserve serializes through the global row's lock, so
    that window is exactly what free-tier chat platform-wide waits on.

    Both bulk updates are filtered to ``period_start < period`` (only
    genuinely stale rows) rather than touching every row unconditionally.
    This matters for correctness, not just performance: a row can already
    have been lazily rolled over to the current period by an ordinary
    ``free_quota_reserve`` call that raced ahead of this scheduled sweep
    (e.g. a user's free-tier call at 00:01 on the 1st, before the sweep
    runs at 00:05) -- an unconditional reset would wipe out that
    already-legitimate current-period usage.

    Returns the count of user rows actually reset (stale rows only; a row
    already at the current period is left untouched and not counted). The
    global row is always ensured/reset too if stale, but is not counted in
    the return value.
    """
    period = _current_period_start()

    # Ensure the singleton global row exists at all (cheap upsert, no lock
    # needed -- nothing else can contend with a fresh single-row INSERT ...
    # ON CONFLICT DO NOTHING), then bulk-reset it only if it's stale.
    await session.execute(
        pg_insert(FreeModelGlobalQuota)
        .values(
            id=_GLOBAL_QUOTA_ROW_ID,
            period_start=period,
            tokens_reserved=0,
            tokens_used=0,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(
        update(FreeModelGlobalQuota)
        .where(
            FreeModelGlobalQuota.id == _GLOBAL_QUOTA_ROW_ID,
            FreeModelGlobalQuota.period_start < period,
        )
        .values(tokens_reserved=0, tokens_used=0, period_start=period)
    )

    result = await session.execute(
        update(FreeModelUserQuota)
        .where(FreeModelUserQuota.period_start < period)
        .values(tokens_reserved=0, tokens_used=0, period_start=period)
    )

    await session.commit()
    return result.rowcount
