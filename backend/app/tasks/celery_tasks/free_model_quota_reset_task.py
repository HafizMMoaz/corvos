"""Monthly reset of free-tier token quota counters (global + per-user)."""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.services.free_model_quota_service import reset_all_free_quotas_for_new_period
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="reset_free_model_quotas")
def reset_free_model_quotas_task():
    """Zero the counters of every *stale* free-model quota row (global plus
    per-user) and roll its `period_start` forward to the current month.

    Rows already at the current period are skipped, not re-zeroed: an
    ordinary `free_quota_reserve` call can race ahead of this scheduled
    sweep and lazily roll a row over itself (e.g. a free-tier call at 00:01
    on the 1st, before the sweep runs), and re-zeroing it would wipe that
    already-legitimate current-period usage.

    Defensive counterpart to that lazy per-call rollover in
    `app.services.free_model_quota_service` -- keeps quota rows tidy even
    for users who don't make a free-tier call right at the monthly
    boundary."""
    return run_async_celery_task(_reset_free_model_quotas)


async def _reset_free_model_quotas() -> None:
    async with get_celery_session_maker()() as db_session:
        reset_count = await reset_all_free_quotas_for_new_period(db_session)
        logger.info(
            "Free-model quota monthly reset completed. users_reset=%s",
            reset_count,
        )
