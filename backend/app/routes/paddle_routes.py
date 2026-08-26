"""Paddle routes for subscription checkout.

Paddle handles subscription checkout only in this track -- crediting
`user.credit_micros_balance` by a plan's `monthly_credit_micros` on
successful payment and recording the subscription state. This is a
separate, additive payment path alongside the existing Stripe one-off
credit-pack purchases (`stripe_routes.py`), which stays untouched and fully
functional. Structure mirrors `stripe_routes.py` closely: a user-facing
checkout-creation route, a signature-verified webhook route (no auth), and a
small read-only status route for the purchases-tab UI.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import PaddleSubscription, Plan, get_async_session
from app.schemas.paddle import (
    CreateSubscriptionCheckoutRequest,
    CreateSubscriptionCheckoutResponse,
    PaddleWebhookResponse,
    PublicPlanRead,
    SubscriptionStatusResponse,
)
from app.services import paddle_service
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paddle", tags=["paddle"])

_SUBSCRIPTION_EVENT_TYPES = {
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
}


@router.get("/plans", response_model=list[PublicPlanRead])
async def list_available_plans(
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> list[Plan]:
    """Active plans available for subscription (public fields only). Any
    logged-in user can call this -- it's how the purchases-tab UI discovers
    what plan ids exist to pass to `create-subscription-checkout`, unlike
    `GET /admin/plans` which is platform-admin-only and returns every plan
    plus admin-only fields."""
    plans = (
        (
            await db_session.execute(
                select(Plan)
                .where(Plan.is_active.is_(True))
                .order_by(Plan.monthly_credit_micros)
            )
        )
        .scalars()
        .all()
    )
    return plans


@router.post(
    "/create-subscription-checkout",
    response_model=CreateSubscriptionCheckoutResponse,
)
async def create_subscription_checkout(
    body: CreateSubscriptionCheckoutRequest,
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateSubscriptionCheckoutResponse:
    """Create a Paddle checkout transaction for subscribing to a plan."""
    user = auth.user
    plan = (
        await db_session.execute(select(Plan).where(Plan.id == body.plan_id))
    ).scalar_one_or_none()
    if plan is None or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found.",
        )

    checkout_url = await paddle_service.create_subscription_checkout(
        db_session, user, plan
    )
    return CreateSubscriptionCheckoutResponse(checkout_url=checkout_url)


@router.post("/webhook", response_model=PaddleWebhookResponse)
async def paddle_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
) -> PaddleWebhookResponse:
    """Handle Paddle webhooks: fulfil completed transactions and keep
    subscription state in sync."""
    if not config.PADDLE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paddle webhook handling is not configured.",
        )

    # Signature verification must run against the exact raw bytes Paddle
    # signed -- read the body before any JSON parsing (Paddle's own docs
    # warn that any reformatting of the body before hashing breaks
    # verification).
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature")

    if not signature or not paddle_service.verify_paddle_signature(
        raw_body, signature, config.PADDLE_WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle webhook signature.",
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle webhook payload.",
        ) from exc

    event_type = payload.get("event_type")
    data = payload.get("data") or {}

    try:
        if event_type == "transaction.completed":
            await paddle_service.fulfill_completed_transaction(db_session, data)
        elif event_type in _SUBSCRIPTION_EVENT_TYPES:
            await paddle_service.upsert_subscription_from_webhook(db_session, data)
        # Every other event type (customer.created, transaction.created,
        # adjustment.*, ...) is a deliberate no-op -- Paddle sends far more
        # event types than this track handles.
    except Exception:
        logger.exception(
            "Paddle webhook handler failed for event_id=%s type=%s - Paddle will retry",
            payload.get("event_id", "?"),
            event_type,
        )
        raise

    return PaddleWebhookResponse()


@router.get("/subscription-status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> SubscriptionStatusResponse:
    """Return the current user's Paddle subscription state for the purchases tab."""
    user = auth.user
    subscription = (
        await db_session.execute(
            select(PaddleSubscription)
            .where(PaddleSubscription.user_id == user.id)
            .order_by(PaddleSubscription.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if subscription is None:
        return SubscriptionStatusResponse(has_subscription=False)

    plan = None
    if subscription.plan_id is not None:
        plan = (
            await db_session.execute(
                select(Plan).where(Plan.id == subscription.plan_id)
            )
        ).scalar_one_or_none()

    return SubscriptionStatusResponse(
        has_subscription=True,
        status=subscription.status,
        plan_key=plan.plan_key if plan else None,
        plan_name=plan.name if plan else None,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )
