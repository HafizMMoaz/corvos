"""Schemas for Paddle-backed subscription checkout."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateSubscriptionCheckoutRequest(BaseModel):
    """Request body for starting a Paddle subscription checkout."""

    plan_id: int = Field(ge=1)


class CreateSubscriptionCheckoutResponse(BaseModel):
    """Response containing the Paddle-hosted checkout URL."""

    checkout_url: str


class PaddleWebhookResponse(BaseModel):
    """Generic acknowledgement for Paddle webhook delivery."""

    received: bool = True


class SubscriptionStatusResponse(BaseModel):
    """Current user's Paddle subscription status for the purchases-tab UI.

    Purpose-built and intentionally small -- does not expose raw Paddle ids
    (customer/subscription/transaction) the frontend has no use for.
    """

    has_subscription: bool = False
    status: str | None = None
    plan_key: str | None = None
    plan_name: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class PublicPlanRead(BaseModel):
    """A subscribable plan's public-facing fields only -- no paddle_price_id,
    no admin metadata."""

    id: int
    plan_key: str
    name: str
    description: str | None
    monthly_credit_micros: int
