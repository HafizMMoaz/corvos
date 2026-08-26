"""Reconcile pending Paddle transactions that might miss webhook fulfillment."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import config
from app.db import CreditPurchaseStatus, PaddleTransaction
from app.services import paddle_service
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

# Paddle transaction `status` values (per the Get Transaction API reference):
# draft, ready, billed, paid, completed, canceled, past_due. `completed`/
# `paid` mean the payment went through; `canceled` is the terminal failure
# state (Paddle has no separate "expired" value for transactions, unlike a
# Stripe checkout session).
_COMPLETED_TRANSACTION_STATUSES = {"completed", "paid"}
_FAILED_TRANSACTION_STATUSES = {"canceled"}


@celery_app.task(name="reconcile_pending_paddle_transactions")
def reconcile_pending_paddle_transactions_task():
    """Recover paid Paddle transactions left pending due to missed webhook handling."""
    return run_async_celery_task(_reconcile_pending_paddle_transactions)


async def _reconcile_pending_paddle_transactions() -> None:
    """Reconcile stale pending Paddle transactions against Paddle's source of truth.

    Paddle retries webhook delivery automatically, but best practice is to
    add an application-level reconciliation path in case all retries fail or
    the endpoint is unavailable for an extended window.
    """
    if not config.PADDLE_API_KEY:
        logger.warning(
            "Paddle reconciliation skipped because PADDLE_API_KEY is not configured."
        )
        return

    lookback_minutes = max(config.PADDLE_RECONCILIATION_LOOKBACK_MINUTES, 0)
    batch_size = max(config.PADDLE_RECONCILIATION_BATCH_SIZE, 1)
    cutoff = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

    async with get_celery_session_maker()() as db_session:
        pending_transactions = (
            (
                await db_session.execute(
                    select(PaddleTransaction)
                    .where(
                        PaddleTransaction.status == CreditPurchaseStatus.PENDING,
                        PaddleTransaction.created_at <= cutoff,
                    )
                    .order_by(PaddleTransaction.created_at.asc())
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )

        if not pending_transactions:
            logger.debug(
                "Paddle reconciliation found no pending transactions older than "
                "%s minutes.",
                lookback_minutes,
            )
            return

        logger.info(
            "Paddle reconciliation checking %s pending transactions "
            "(cutoff=%s, batch=%s).",
            len(pending_transactions),
            lookback_minutes,
            batch_size,
        )

        fulfilled_count = 0
        failed_count = 0

        for transaction in pending_transactions:
            transaction_id = transaction.paddle_transaction_id

            try:
                full_transaction = await paddle_service.get_transaction(transaction_id)
            except httpx.HTTPError:
                logger.exception(
                    "Paddle reconciliation failed to retrieve transaction %s",
                    transaction_id,
                )
                await db_session.rollback()
                continue

            paddle_status = full_transaction.get("data", {}).get("status")

            try:
                if paddle_status in _COMPLETED_TRANSACTION_STATUSES:
                    await paddle_service.fulfill_completed_transaction(
                        db_session, full_transaction["data"]
                    )
                    fulfilled_count += 1
                elif paddle_status in _FAILED_TRANSACTION_STATUSES:
                    transaction.status = CreditPurchaseStatus.FAILED
                    await db_session.commit()
                    failed_count += 1
            except Exception:
                logger.exception(
                    "Paddle reconciliation failed while processing transaction %s",
                    transaction_id,
                )
                await db_session.rollback()

        logger.info(
            "Paddle reconciliation completed. fulfilled=%s failed=%s checked=%s",
            fulfilled_count,
            failed_count,
            len(pending_transactions),
        )
