"""
Pydantic schemas for the super admin LLM provider/model catalog endpoints
(`app.routes.admin.admin_llm_routes`), mirroring the style of
`app.schemas.admin_settings_schemas`.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

# ============ LLM Provider Schemas ============


class AdminLLMProviderRead(BaseModel):
    """One provider connection's current state. `has_api_key` reports
    whether a key is stored without ever returning ciphertext or plaintext
    -- use `POST /admin/llm-providers/{id}/reveal` for the real value."""

    id: int
    provider_key: str
    display_name: str
    transport: str
    litellm_prefix: str | None
    default_base_url: str | None
    base_url_required: bool
    auth_style: str
    has_api_key: bool
    api_base_override: str | None
    is_enabled: bool
    notes: str | None
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AdminLLMProviderCreate(BaseModel):
    """Request body for `POST /admin/llm-providers`. `api_key`, if given, is
    plaintext here and encrypted before storage -- never stored or logged as
    given."""

    provider_key: str
    display_name: str
    transport: str
    litellm_prefix: str | None = None
    default_base_url: str | None = None
    base_url_required: bool = False
    auth_style: str
    api_key: str | None = None
    api_base_override: str | None = None
    notes: str | None = None


class AdminLLMProviderUpdate(BaseModel):
    """Request body for `PUT /admin/llm-providers/{id}` (partial update).
    Only fields present in the request are changed. Same encrypt-on-write
    rule as create for `api_key`."""

    provider_key: str | None = None
    display_name: str | None = None
    transport: str | None = None
    litellm_prefix: str | None = None
    default_base_url: str | None = None
    base_url_required: bool | None = None
    auth_style: str | None = None
    api_key: str | None = None
    api_base_override: str | None = None
    is_enabled: bool | None = None
    notes: str | None = None


class AdminLLMProviderRevealResponse(BaseModel):
    """Response for `POST /admin/llm-providers/{id}/reveal`: the one place a
    provider's plaintext API key is ever returned over the wire."""

    id: int
    api_key: str | None


# ============ LLM Model Schemas ============


class AdminLLMModelRead(BaseModel):
    """One admin-managed model's current state."""

    id: int
    provider_id: int
    name: str
    model_name: str
    billing_tier: str
    anonymous_enabled: bool
    seo_enabled: bool
    seo_slug: str | None
    seo_title: str | None
    seo_description: str | None
    quota_reserve_tokens: int | None
    supports_image_input: bool
    supports_tools: bool
    max_input_tokens: int | None
    api_base_override: str | None
    api_version: str | None
    rpm: int | None
    tpm: int | None
    litellm_params: dict[str, Any] | None
    system_instructions: str | None
    use_default_system_instructions: bool
    citations_enabled: bool
    is_planner: bool
    router_pool_eligible: bool
    is_enabled: bool
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AdminLLMModelCreate(BaseModel):
    """Request body for `POST /admin/llm-models`.

    `billing_tier` is a strict enum, not a bare string:
    `AgentConfig.from_yaml_config` derives `is_premium` from an exact
    `== "premium"` comparison, so a typo or different casing (e.g.
    `"Premium"`) would silently create a free-tier model that also gets
    charged against the shared free-tier caps. Matches the constraint the
    frontend already enforces (`web/app/admin/llm-quotas/components/
    model-form-schema.ts`).
    """

    provider_id: int
    name: str
    model_name: str
    billing_tier: Literal["free", "premium"] = "premium"
    anonymous_enabled: bool = False
    seo_enabled: bool = False
    seo_slug: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    quota_reserve_tokens: int | None = None
    supports_image_input: bool = False
    supports_tools: bool = False
    max_input_tokens: int | None = None
    api_base_override: str | None = None
    api_version: str | None = None
    rpm: int | None = None
    tpm: int | None = None
    litellm_params: dict[str, Any] | None = None
    system_instructions: str | None = None
    use_default_system_instructions: bool = True
    citations_enabled: bool = True
    is_planner: bool = False
    router_pool_eligible: bool = True
    is_enabled: bool = True


class AdminLLMModelUpdate(BaseModel):
    """Request body for `PUT /admin/llm-models/{id}` (partial update). Only
    fields present in the request are changed. Same strict `billing_tier`
    enum as create, for the same reason."""

    provider_id: int | None = None
    name: str | None = None
    model_name: str | None = None
    billing_tier: Literal["free", "premium"] | None = None
    anonymous_enabled: bool | None = None
    seo_enabled: bool | None = None
    seo_slug: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    quota_reserve_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    max_input_tokens: int | None = None
    api_base_override: str | None = None
    api_version: str | None = None
    rpm: int | None = None
    tpm: int | None = None
    litellm_params: dict[str, Any] | None = None
    system_instructions: str | None = None
    use_default_system_instructions: bool | None = None
    citations_enabled: bool | None = None
    is_planner: bool | None = None
    router_pool_eligible: bool | None = None
    is_enabled: bool | None = None


# ============ Model Discovery Schema ============


class AdminLLMDiscoveredModelRead(BaseModel):
    """One model discovered live from a provider's own API (or, for
    `static`-discovery providers, LiteLLM's bundled cost map), returned by
    `POST /admin/llm-providers/{id}/discover-models`. Trimmed from the
    workspace BYOK flow's `ModelPreviewRead` (`app.schemas.model_connections`):
    no `source`/`enabled`/`metadata` -- those are workspace-connection-specific
    concepts that don't apply to this admin-catalog use case."""

    model_id: str
    display_name: str | None
    supports_chat: bool | None
    supports_image_input: bool | None
    supports_tools: bool | None
    supports_image_generation: bool | None
    max_input_tokens: int | None


# ============ Reload Schema ============


class AdminLLMReloadResponse(BaseModel):
    """Response for `POST /admin/llm-models/reload`."""

    applied_count: int


# ============ Free-Model Quota Schemas ============


class AdminFreeQuotaGlobalRead(BaseModel):
    """Response for `GET /admin/llm-quota` and
    `POST /admin/llm-quota/reset`: the platform-wide free-tier token quota
    for the current period, plus the configured cap it's enforced against."""

    period_start: date
    tokens_reserved: int
    tokens_used: int
    cap_tokens: int
    updated_at: datetime


class AdminFreeQuotaUserRead(BaseModel):
    """Response for `GET /admin/llm-quota/users/{user_id}` and
    `POST /admin/llm-quota/users/{user_id}/reset`: one user's free-tier
    token quota for the current period, plus the configured cap. All usage
    fields are null when the user has never reserved free-tier quota yet."""

    user_id: UUID
    period_start: date | None
    tokens_reserved: int | None
    tokens_used: int | None
    cap_tokens: int
    updated_at: datetime | None
