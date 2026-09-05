"""
Pydantic schemas for the super admin plans/feature-flags/entitlements
endpoints (`app.routes.admin.admin_billing_routes`), mirroring the style of
`app.schemas.admin_llm_schemas`.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ============ Plan Schemas ============


class PlanRead(BaseModel):
    """One plan's current state."""

    id: int
    plan_key: str
    name: str
    description: str | None
    monthly_credit_micros: int
    paddle_price_id: str | None
    is_active: bool
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PlanCreate(BaseModel):
    """Request body for `POST /admin/plans`. `paddle_price_id` is not
    settable here -- it is populated by a later `PUT` once the matching
    Paddle price exists (Track 2/frontend concern)."""

    plan_key: str
    name: str
    description: str | None = None
    monthly_credit_micros: int = 0
    is_active: bool = True


class PlanUpdate(BaseModel):
    """Request body for `PUT /admin/plans/{plan_id}` (partial update). Only
    fields present in the request are changed."""

    plan_key: str | None = None
    name: str | None = None
    description: str | None = None
    monthly_credit_micros: int | None = None
    paddle_price_id: str | None = None
    is_active: bool | None = None


# ============ Feature Flag Schemas ============


class FeatureFlagRead(BaseModel):
    """One feature flag definition's current state."""

    id: int
    flag_key: str
    name: str
    description: str | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class FeatureFlagCreate(BaseModel):
    """Request body for `POST /admin/feature-flags`."""

    flag_key: str
    name: str
    description: str | None = None


class FeatureFlagUpdate(BaseModel):
    """Request body for `PUT /admin/feature-flags/{flag_id}` (partial
    update). Only fields present in the request are changed."""

    flag_key: str | None = None
    name: str | None = None
    description: str | None = None


# ============ Plan Model Entitlement Schemas ============


class PlanModelEntitlementCreate(BaseModel):
    """Request body for `POST /admin/plans/{plan_id}/model-entitlements`."""

    config_id: int


class PlanModelEntitlementRead(BaseModel):
    """Response for `POST /admin/plans/{plan_id}/model-entitlements`."""

    plan_id: int
    config_id: int


# ============ Plan Feature Value Schemas ============


class PlanFeatureValueSet(BaseModel):
    """Request body for
    `PUT /admin/plans/{plan_id}/feature-values/{feature_flag_id}`."""

    enabled: bool


class PlanFeatureValueRead(BaseModel):
    """One plan's configured value for one feature flag. Only rows that
    exist are returned -- a `feature_flag_id` absent from the list response
    is off by default for that plan."""

    feature_flag_id: int
    enabled: bool
    updated_at: datetime


# ============ User Plan Assignment Schemas ============


class UserPlanAssignmentUpdate(BaseModel):
    """Request body for `PUT /admin/users/{user_id}/plan`. `plan_id = None`
    un-assigns the user from any plan."""

    plan_id: int | None


class UserPlanRead(BaseModel):
    """Response for `PUT /admin/users/{user_id}/plan`."""

    user_id: UUID
    plan_id: int | None


# ============ User Entitlements Lookup Schema ============


class UserEntitlementsRead(BaseModel):
    """Response for `GET /admin/users/{user_id}/entitlements`: a user's fully
    resolved entitlement state (`app.services.entitlement_service`)."""

    user_id: UUID
    plan: PlanRead | None
    feature_flags: dict[str, bool]
    unrestricted_models: bool
    allowed_config_ids: list[int]


# ============ User Feature Override Schemas ============


class UserFeatureOverrideSet(BaseModel):
    """Request body for
    `PUT /admin/users/{user_id}/feature-overrides/{feature_flag_id}`."""

    enabled: bool
    expires_at: datetime | None = None


class UserFeatureOverrideRead(BaseModel):
    """One user's forced value for one feature flag. Expired-but-not-deleted
    rows are still returned by the list endpoint (with `expires_at` visible)
    so an admin can see the full override history; only
    `app.services.entitlement_service` stops honoring an expired row."""

    id: int
    user_id: UUID
    feature_flag_id: int
    enabled: bool
    expires_at: datetime | None
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


# ============ Admin Subscriptions List Schema ============


class AdminSubscriptionRead(BaseModel):
    """One row of the admin subscriptions list: a `PaddleSubscription`
    (upserted from Paddle webhooks, see `app.services.paddle_service`)
    joined with its user's email and plan's name. Read-only -- subscription
    state always flows in from Paddle; the admin UI only displays it."""

    id: int
    user_id: UUID
    user_email: str
    plan_id: int | None
    plan_name: str | None
    paddle_subscription_id: str
    paddle_customer_id: str
    status: str
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime


# ============ Admin Users List Schemas ============


class AdminUserListItemRead(BaseModel):
    """One row of the admin users list. `user` has no created_at column, so
    `last_login` (nullable) is the only recency signal available."""

    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    is_superuser: bool
    plan_id: int | None
    plan_name: str | None
    credit_micros_balance: int
    last_login: datetime | None


class AdminUserListResponse(BaseModel):
    """Response for `GET /admin/users` (paginated)."""

    users: list[AdminUserListItemRead]
    total: int
    limit: int
    offset: int
