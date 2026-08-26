"""Paddle billing service: subscription checkout, webhook fulfillment, and
Paddle REST API access for the `/paddle` routes and the reconciliation task.

Mirrors `stripe_routes.py`'s idempotent webhook-fulfillment shape closely
(`SELECT ... FOR UPDATE`, status-guarded early return, commit) -- see that
module's `_get_or_create_stripe_customer` and
`_fulfill_completed_credit_purchase` for the precedent this module's
`get_or_create_paddle_customer` and `fulfill_completed_transaction` copy.

Paddle Billing REST API facts (developer.paddle.com, verified live against
the API reference and webhook payload examples while building this module):
- Base URL: sandbox-api.paddle.com (sandbox) / api.paddle.com (production),
  selected by `config.PADDLE_ENVIRONMENT`.
- Auth: `Authorization: Bearer <PADDLE_API_KEY>` on every call. No
  vendor/seller id header is required by any endpoint this module calls.
- A transaction/subscription's line items carry a *nested* `price` object
  (`item["price"]["id"]`) in every API response and webhook payload this
  module reads -- confirmed against the Get Transaction / Get Subscription
  API reference and the `transaction.completed` / `subscription.created`
  webhook examples. The *request* body for creating a transaction uses the
  opposite shape (flat `items[].price_id`); that is a deliberate asymmetry
  in Paddle's own API between what you send and what you get back, not an
  inconsistency in this module.
- `POST /transactions`'s response `data.checkout.url` already has
  `?_ptxn=<transaction id>` appended by Paddle -- nothing to add here.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    CreditPurchaseStatus,
    PaddleCustomer,
    PaddleSubscription,
    PaddleTransaction,
    Plan,
    User,
)

logger = logging.getLogger(__name__)

# Paddle's own SDKs reportedly default to a 5-second webhook timestamp
# tolerance; that is unusually tight for real network/queueing latency and
# risks spuriously rejecting legitimate webhooks (including Paddle's own
# retries). 300s (5 minutes) is still tight enough to block replay attacks
# while being generous enough for normal delivery latency -- do not tighten
# this to "match the docs".
_SIGNATURE_TOLERANCE_SECONDS = 300


def _paddle_base_url() -> str:
    if config.PADDLE_ENVIRONMENT == "production":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def _get_required_api_key() -> str:
    if not config.PADDLE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PADDLE_API_KEY is not configured.",
        )
    return config.PADDLE_API_KEY


async def _paddle_request(method: str, path: str, *, json: dict | None = None) -> dict:
    """Call the Paddle REST API and return the decoded JSON body."""
    api_key = _get_required_api_key()
    url = f"{_paddle_base_url()}{path}"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, headers=headers, json=json)
        response.raise_for_status()
        return response.json()


async def get_transaction(transaction_id: str) -> dict:
    """Fetch the full transaction object from Paddle (`GET /transactions/{id}`).

    Used both as a fallback when a webhook payload's `items` array is
    trimmed/absent and by the reconciliation task to re-check a stale
    pending transaction against Paddle's source of truth.
    """
    return await _paddle_request("GET", f"/transactions/{transaction_id}")


async def get_or_create_paddle_customer(session: AsyncSession, user: User) -> str:
    """Return the user's Paddle Customer id, creating + persisting one if needed.

    Copies `stripe_routes._get_or_create_stripe_customer`'s
    `SELECT ... FOR UPDATE`-guarded race-protection shape: lock, re-check,
    and only create a new Paddle customer if one still doesn't exist after
    the lock is acquired.
    """
    existing = (
        await session.execute(
            select(PaddleCustomer)
            .where(PaddleCustomer.user_id == user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing.paddle_customer_id

    response = await _paddle_request("POST", "/customers", json={"email": user.email})
    customer_id = str(response["data"]["id"])

    # Re-check under lock to avoid two concurrent checkouts creating
    # duplicate Paddle customers for the same user.
    locked = (
        await session.execute(
            select(PaddleCustomer)
            .where(PaddleCustomer.user_id == user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked is not None:
        # Another request won the race; reuse theirs.
        return locked.paddle_customer_id

    session.add(PaddleCustomer(user_id=user.id, paddle_customer_id=customer_id))
    await session.commit()
    return customer_id


async def create_subscription_checkout(
    session: AsyncSession, user: User, plan: Plan
) -> str:
    """Start a Paddle subscription checkout for `plan`, returning the checkout URL."""
    if not plan.paddle_price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This plan is not configured for Paddle checkout.",
        )

    customer_id = await get_or_create_paddle_customer(session, user)

    response = await _paddle_request(
        "POST",
        "/transactions",
        json={
            "items": [{"price_id": plan.paddle_price_id, "quantity": 1}],
            "customer_id": customer_id,
            "collection_mode": "automatic",
        },
    )
    checkout_url = response.get("data", {}).get("checkout", {}).get("url")
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Paddle checkout transaction did not return a URL.",
        )
    return checkout_url


def verify_paddle_signature(
    raw_body: bytes, signature_header: str, secret: str
) -> bool:
    """Verify a `Paddle-Signature` header against `raw_body`.

    Header shape: `ts=<unix_timestamp>;h1=<hex_hmac>`. The signed digest is
    HMAC-SHA256 of `f"{ts}:{raw_body}"` keyed by the webhook secret, compared
    in constant time (`hmac.compare_digest`, never `==`). Rejects a stale
    timestamp beyond `_SIGNATURE_TOLERANCE_SECONDS` to block replay attacks.
    """
    if not signature_header:
        return False

    parts: dict[str, str] = {}
    for chunk in signature_header.split(";"):
        if "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        parts[key.strip()] = value.strip()

    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False

    try:
        ts_int = int(ts)
    except ValueError:
        return False

    if abs(time.time() - ts_int) > _SIGNATURE_TOLERANCE_SECONDS:
        return False

    signed_payload = f"{ts}:{raw_body.decode()}".encode()
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, h1)


def _resolve_price_id_from_items(items: list[dict[str, Any]] | None) -> str | None:
    """Extract a line item's price id from a Paddle webhook `items` array.

    Each item carries a *nested* `price` object (`item["price"]["id"]`), not
    a flat `price_id` -- confirmed against Paddle's Get Transaction / Get
    Subscription API reference and webhook payload examples. Returns the
    first item with a resolvable price id (this track only ever creates
    single-item transactions/subscriptions, but loops defensively in case
    Paddle or a future change sends more than one).
    """
    if not items:
        return None
    for item in items:
        price = item.get("price") or {}
        price_id = price.get("id")
        if price_id:
            return str(price_id)
    return None


async def _resolve_plan_by_price_id(
    session: AsyncSession, price_id: str | None
) -> Plan | None:
    if not price_id:
        return None
    return (
        await session.execute(select(Plan).where(Plan.paddle_price_id == price_id))
    ).scalar_one_or_none()


async def _resolve_user_id_from_customer(
    session: AsyncSession, paddle_customer_id: str | None
) -> uuid.UUID | None:
    """Map a Paddle customer id back to our user id via `paddle_customers`.

    That row was created by `get_or_create_paddle_customer` when this app
    initiated the checkout, so every customer id a webhook reports should
    already have a matching row.
    """
    if not paddle_customer_id:
        return None
    customer = (
        await session.execute(
            select(PaddleCustomer).where(
                PaddleCustomer.paddle_customer_id == paddle_customer_id
            )
        )
    ).scalar_one_or_none()
    return customer.user_id if customer else None


async def fulfill_completed_transaction(session: AsyncSession, data: dict) -> None:
    """Grant subscription credit after a confirmed Paddle transaction payment.

    Idempotent and structured like `stripe_routes._fulfill_completed_credit_purchase`:
    lock the `paddle_transactions` row by `paddle_transaction_id`; if it is
    already COMPLETED, return immediately (webhook-retry / reconciliation
    idempotency guard) before doing any further work, including the
    Paddle API fallback call below -- a duplicate delivery must not re-hit
    the network. Otherwise create a PENDING row from `data` if absent,
    resolve the plan from the transaction's price id, lock and credit the
    user row, then commit.

    If the `items` array is trimmed/absent and the `get_transaction`
    fallback call itself fails (timeout, connection error, 5xx), the row is
    left/created PENDING and this function returns without granting credit
    -- a transient failure to *determine* the price id must never be
    treated the same as a resolved price id that genuinely doesn't map to
    any plan (which does complete with 0 credit, see below). Leaving the
    row PENDING lets the reconciliation task retry it later instead of
    silently writing the charge off forever.
    """
    transaction_id = str(data["id"])

    if data.get("subscription_id") is None:
        # Out of scope for this track: Paddle handles subscription checkout
        # only here, so a non-subscription transaction.completed event (if
        # one ever arrives) is skipped, not fulfilled.
        logger.info(
            "Skipping Paddle fulfillment for transaction %s: not a "
            "subscription transaction (subscription_id is null).",
            transaction_id,
        )
        return

    purchase = (
        await session.execute(
            select(PaddleTransaction)
            .where(PaddleTransaction.paddle_transaction_id == transaction_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is not None and purchase.status == CreditPurchaseStatus.COMPLETED:
        return

    # Distinguish "we resolved a price id and it doesn't map to any plan"
    # (a real data problem -- fine to complete with 0 credit, per below)
    # from "we couldn't even determine the price id because the fallback
    # lookup itself failed" (a transient infra hiccup -- must stay
    # recoverable, not get silently written off as 0 credit).
    price_resolution_failed = False
    price_id = _resolve_price_id_from_items(data.get("items"))
    if price_id is None:
        try:
            full_transaction = await get_transaction(transaction_id)
            price_id = _resolve_price_id_from_items(
                full_transaction.get("data", {}).get("items")
            )
        except httpx.HTTPError:
            logger.warning(
                "Paddle transaction %s: failed to fetch full transaction to "
                "resolve its price id; leaving PENDING for the "
                "reconciliation task to retry instead of granting 0 credit",
                transaction_id,
                exc_info=True,
            )
            price_resolution_failed = True

    plan = await _resolve_plan_by_price_id(session, price_id)

    customer_id = data.get("customer_id")
    subscription_id = data.get("subscription_id")
    amount_total_raw = data.get("details", {}).get("totals", {}).get("grand_total")
    amount_total = int(amount_total_raw) if amount_total_raw is not None else None
    currency = data.get("currency_code")

    if purchase is None:
        user_id = await _resolve_user_id_from_customer(session, customer_id)
        if user_id is None:
            logger.error(
                "Skipping Paddle fulfillment for transaction %s: no user "
                "found for Paddle customer %s",
                transaction_id,
                customer_id,
            )
            return

        purchase = PaddleTransaction(
            user_id=user_id,
            paddle_transaction_id=transaction_id,
            paddle_subscription_id=subscription_id,
            plan_id=plan.id if plan else None,
            status=CreditPurchaseStatus.PENDING,
            amount_total=amount_total,
            currency=currency,
        )
        session.add(purchase)
        await session.flush()

    if price_resolution_failed:
        # Commit only to persist the PENDING row created just above (if
        # this was the first delivery) and release the row lock -- the
        # transaction stays PENDING, unchanged from COMPLETED, so the
        # reconciliation task's `WHERE status == PENDING` filter will
        # revisit it and retry price resolution once Paddle's API is
        # reachable again.
        await session.commit()
        return

    user = (
        (
            await session.execute(
                select(User).where(User.id == purchase.user_id).with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if user is None:
        logger.error(
            "Skipping Paddle fulfillment for transaction %s: user %s not found",
            transaction_id,
            purchase.user_id,
        )
        return

    if plan is None:
        logger.warning(
            "Paddle transaction %s: price id %s does not match any known "
            "plan; storing plan_id=NULL and granting no credit",
            transaction_id,
            price_id,
        )
    credit_micros_granted = plan.monthly_credit_micros if plan is not None else 0

    purchase.status = CreditPurchaseStatus.COMPLETED
    purchase.completed_at = datetime.now(UTC)
    purchase.plan_id = plan.id if plan else purchase.plan_id
    purchase.credit_micros_granted = credit_micros_granted
    purchase.amount_total = (
        amount_total if amount_total is not None else purchase.amount_total
    )
    purchase.currency = currency or purchase.currency
    user.credit_micros_balance = user.credit_micros_balance + credit_micros_granted

    await session.commit()


def _parse_paddle_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse Paddle timestamp %r", value)
        return None


async def upsert_subscription_from_webhook(session: AsyncSession, data: dict) -> None:
    """Create or update a `paddle_subscriptions` row from a subscription webhook.

    Handles `subscription.created`, `.updated`, and `.canceled` with the
    same upsert logic (create if absent, else update by
    `paddle_subscription_id`) -- Paddle describes `.updated` as a catch-all
    for every subscription state change, and `.canceled`'s `data.status` is
    already `"canceled"` in the payload, so no event-specific branching is
    needed here. Resolves `plan_id` from the subscription's own `items`
    independently of `fulfill_completed_transaction` so the two handlers
    never depend on each other's arrival order.
    """
    subscription_id = str(data["id"])
    price_id = _resolve_price_id_from_items(data.get("items"))
    plan = await _resolve_plan_by_price_id(session, price_id)
    if price_id is not None and plan is None:
        logger.warning(
            "Paddle subscription %s: price id %s does not match any known plan",
            subscription_id,
            price_id,
        )

    customer_id = data.get("customer_id")
    billing_period = data.get("current_billing_period") or {}
    period_end = _parse_paddle_timestamp(billing_period.get("ends_at"))
    scheduled_change = data.get("scheduled_change") or {}
    cancel_at_period_end = scheduled_change.get("action") == "cancel"

    subscription = (
        await session.execute(
            select(PaddleSubscription)
            .where(PaddleSubscription.paddle_subscription_id == subscription_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if subscription is None:
        user_id = await _resolve_user_id_from_customer(session, customer_id)
        if user_id is None:
            logger.error(
                "Skipping Paddle subscription upsert for %s: no user found "
                "for Paddle customer %s",
                subscription_id,
                customer_id,
            )
            return
        subscription = PaddleSubscription(
            user_id=user_id,
            paddle_subscription_id=subscription_id,
            paddle_customer_id=customer_id or "",
        )
        session.add(subscription)

    if plan is not None:
        subscription.plan_id = plan.id
    subscription.status = data.get("status") or subscription.status
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = cancel_at_period_end
    if customer_id:
        subscription.paddle_customer_id = customer_id

    await session.commit()
