"""
Admin LLM provider/model catalog routes: DB-backed CRUD for
`admin_llm_providers`/`admin_llm_models`, the replacement for hand-editing
`global_llm_config.yaml` (see `app.services.admin_llm_catalog_service`).

Endpoints:
- GET /admin/llm-providers - list providers (API key masked as `has_api_key`).
  Requires llm_providers:read.
- POST /admin/llm-providers - create a provider. Requires llm_providers:write.
- PUT /admin/llm-providers/{id} - update a provider (partial). Requires
  llm_providers:write.
- DELETE /admin/llm-providers/{id} - delete a provider (cascades to its
  models). Requires llm_providers:write.
- POST /admin/llm-providers/{id}/reveal - return a provider's decrypted API
  key. Requires llm_providers:write (there is no separate reveal permission
  for this catalog).
- POST /admin/llm-providers/{id}/discover-models - fetch the live list of
  models available from this provider's own API (or, for `static`-discovery
  providers, LiteLLM's bundled cost map -- no network call), by reusing the
  workspace BYOK flow's `model_connection_service.discover_models`. Never
  returns the provider's API key. Requires llm_providers:read.
- GET /admin/llm-models - list models, optional `provider_id` filter.
  Requires llm_providers:read.
- POST /admin/llm-models - create a model. Requires llm_providers:write.
- PUT /admin/llm-models/{id} - update a model (partial). Requires
  llm_providers:write.
- DELETE /admin/llm-models/{id} - delete a model. Requires llm_providers:write.
- POST /admin/llm-models/reload - force-reapply the DB catalog into
  `config.GLOBAL_LLM_CONFIGS` and return the applied count. Requires
  llm_providers:write.
- GET /admin/llm-quota - platform-wide free-tier token quota snapshot for
  the current period. Requires quotas:read.
- GET /admin/llm-quota/users/{user_id} - one user's free-tier token quota
  snapshot for the current period (nulls if they've never used free tier).
  Requires quotas:read.
- POST /admin/llm-quota/reset - manually reset the platform-wide free-tier
  quota (zero counters, bump to current period). Requires quotas:write.
- POST /admin/llm-quota/users/{user_id}/reset - manually reset one user's
  free-tier quota. Requires quotas:write.

Every create/update/delete/reveal call re-applies the live catalog
(`apply_admin_llm_configs`) after commit, and writes one `admin_audit_logs`
row via `record_admin_action` before commit, with `api_key`/
`api_key_encrypted` redacted from the audit payload. The reload endpoint is
audited too (it mutates live process state even though it writes no DB row).
The discover-models endpoint is a pure read (like `GET /admin/llm-providers`
and `GET /admin/llm-models`), so it is not audited either.
The free-model quota reset endpoints follow the same audit convention,
capturing `before` as well as `after` (a reset always zeroes the row, so
`after` alone would say nothing about what was wiped), though (per
`app.services.free_model_quota_service`'s self-committing reserve/
finalize/release/reset lifecycle) the reset mutation itself commits inside
the service call, with the audit row committed in a second, immediately
following commit rather than atomically with the reset.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    AdminLLMModel,
    AdminLLMProvider,
    Connection,
    FreeModelGlobalQuota,
    FreeModelUserQuota,
    PlatformPermission,
    get_async_session,
)
from app.schemas import (
    AdminFreeQuotaGlobalRead,
    AdminFreeQuotaUserRead,
    AdminLLMDiscoveredModelRead,
    AdminLLMModelCreate,
    AdminLLMModelRead,
    AdminLLMModelUpdate,
    AdminLLMProviderCreate,
    AdminLLMProviderRead,
    AdminLLMProviderRevealResponse,
    AdminLLMProviderUpdate,
    AdminLLMReloadResponse,
)
from app.services.admin_llm_catalog_service import apply_admin_llm_configs
from app.services.free_model_quota_service import (
    get_global_quota_snapshot,
    get_user_quota_snapshot,
    reset_global_quota,
    reset_user_quota,
)
from app.services.model_connection_service import ModelDiscoveryError, discover_models
from app.users import get_auth_context
from app.utils.oauth_security import TokenEncryption
from app.utils.platform_rbac import check_platform_permission, record_admin_action

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Read / audit-dict helpers
# ---------------------------------------------------------------------------


def _to_provider_read(provider: AdminLLMProvider) -> AdminLLMProviderRead:
    return AdminLLMProviderRead(
        id=provider.id,
        provider_key=provider.provider_key,
        display_name=provider.display_name,
        transport=provider.transport,
        litellm_prefix=provider.litellm_prefix,
        default_base_url=provider.default_base_url,
        base_url_required=provider.base_url_required,
        auth_style=provider.auth_style,
        has_api_key=bool(provider.api_key_encrypted),
        api_base_override=provider.api_base_override,
        is_enabled=provider.is_enabled,
        notes=provider.notes,
        created_by_id=provider.created_by_id,
        updated_by_id=provider.updated_by_id,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _provider_audit_dict(provider: AdminLLMProvider) -> dict[str, Any]:
    """Redacted snapshot of a provider for `admin_audit_logs.before`/`after`
    -- never includes `api_key`/`api_key_encrypted`, only whether a key is
    currently set."""
    return {
        "provider_key": provider.provider_key,
        "display_name": provider.display_name,
        "transport": provider.transport,
        "litellm_prefix": provider.litellm_prefix,
        "default_base_url": provider.default_base_url,
        "base_url_required": provider.base_url_required,
        "auth_style": provider.auth_style,
        "has_api_key": bool(provider.api_key_encrypted),
        "api_base_override": provider.api_base_override,
        "is_enabled": provider.is_enabled,
        "notes": provider.notes,
    }


def _to_model_read(model: AdminLLMModel) -> AdminLLMModelRead:
    return AdminLLMModelRead(
        id=model.id,
        provider_id=model.provider_id,
        name=model.name,
        model_name=model.model_name,
        billing_tier=model.billing_tier,
        anonymous_enabled=model.anonymous_enabled,
        seo_enabled=model.seo_enabled,
        seo_slug=model.seo_slug,
        seo_title=model.seo_title,
        seo_description=model.seo_description,
        quota_reserve_tokens=model.quota_reserve_tokens,
        supports_image_input=model.supports_image_input,
        supports_tools=model.supports_tools,
        max_input_tokens=model.max_input_tokens,
        api_base_override=model.api_base_override,
        api_version=model.api_version,
        rpm=model.rpm,
        tpm=model.tpm,
        litellm_params=model.litellm_params,
        system_instructions=model.system_instructions,
        use_default_system_instructions=model.use_default_system_instructions,
        citations_enabled=model.citations_enabled,
        is_planner=model.is_planner,
        router_pool_eligible=model.router_pool_eligible,
        is_enabled=model.is_enabled,
        created_by_id=model.created_by_id,
        updated_by_id=model.updated_by_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_audit_dict(model: AdminLLMModel) -> dict[str, Any]:
    """Snapshot of every mutable model field for `admin_audit_logs.before`/
    `after`. No secrets live on this table (unlike the provider audit dict),
    so every field is included -- nothing here needs redaction, and omitting
    fields would leave the audit trail unable to show what actually changed
    (e.g. pricing params or a model's system prompt)."""
    return {
        "provider_id": model.provider_id,
        "name": model.name,
        "model_name": model.model_name,
        "billing_tier": model.billing_tier,
        "anonymous_enabled": model.anonymous_enabled,
        "seo_enabled": model.seo_enabled,
        "seo_slug": model.seo_slug,
        "seo_title": model.seo_title,
        "seo_description": model.seo_description,
        "quota_reserve_tokens": model.quota_reserve_tokens,
        "supports_image_input": model.supports_image_input,
        "supports_tools": model.supports_tools,
        "max_input_tokens": model.max_input_tokens,
        "api_base_override": model.api_base_override,
        "api_version": model.api_version,
        "rpm": model.rpm,
        "tpm": model.tpm,
        "litellm_params": model.litellm_params,
        "system_instructions": model.system_instructions,
        "use_default_system_instructions": model.use_default_system_instructions,
        "citations_enabled": model.citations_enabled,
        "is_planner": model.is_planner,
        "router_pool_eligible": model.router_pool_eligible,
        "is_enabled": model.is_enabled,
    }


async def _get_provider_or_404(
    session: AsyncSession, provider_id: int
) -> AdminLLMProvider:
    result = await session.execute(
        select(AdminLLMProvider).filter(AdminLLMProvider.id == provider_id)
    )
    provider = result.scalars().first()
    if provider is None:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    return provider


async def _get_model_or_404(session: AsyncSession, model_id: int) -> AdminLLMModel:
    result = await session.execute(
        select(AdminLLMModel).filter(AdminLLMModel.id == model_id)
    )
    model = result.scalars().first()
    if model is None:
        raise HTTPException(status_code=404, detail="LLM model not found")
    return model


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@router.get("/llm-providers", response_model=list[AdminLLMProviderRead])
async def list_llm_providers(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all LLM providers (API key masked as `has_api_key`). Requires
    llm_providers:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_READ.value,
            "You don't have permission to view LLM providers",
        )
        result = await session.execute(
            select(AdminLLMProvider).order_by(AdminLLMProvider.provider_key)
        )
        return [_to_provider_read(p) for p in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list LLM providers: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list LLM providers: {e!s}"
        ) from e


@router.post("/llm-providers", response_model=AdminLLMProviderRead)
async def create_llm_provider(
    payload: AdminLLMProviderCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new LLM provider connection. Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM providers",
        )

        existing = await session.execute(
            select(AdminLLMProvider).filter(
                AdminLLMProvider.provider_key == payload.provider_key
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A provider with key '{payload.provider_key}' already exists",
            )

        provider = AdminLLMProvider(
            provider_key=payload.provider_key,
            display_name=payload.display_name,
            transport=payload.transport,
            litellm_prefix=payload.litellm_prefix,
            default_base_url=payload.default_base_url,
            base_url_required=payload.base_url_required,
            auth_style=payload.auth_style,
            api_base_override=payload.api_base_override,
            notes=payload.notes,
            created_by_id=auth.user.id,
            updated_by_id=auth.user.id,
        )
        if payload.api_key:
            provider.api_key_encrypted = TokenEncryption(
                config.SECRET_KEY
            ).encrypt_token(payload.api_key)

        session.add(provider)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_provider.create",
            target_type="admin_llm_provider",
            target_id=str(provider.id),
            after=_provider_audit_dict(provider),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(provider)

        # Providers alone don't appear in GLOBAL_LLM_CONFIGS, but re-apply for
        # consistency: a new provider's key can immediately back any existing
        # model rows that reference it.
        await apply_admin_llm_configs(session)

        return _to_provider_read(provider)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create LLM provider: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create LLM provider: {e!s}"
        ) from e


@router.put("/llm-providers/{provider_id}", response_model=AdminLLMProviderRead)
async def update_llm_provider(
    provider_id: int,
    payload: AdminLLMProviderUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an LLM provider (partial update). Same encrypt-on-write rule
    as create for `api_key`. Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM providers",
        )

        provider = await _get_provider_or_404(session, provider_id)
        before = _provider_audit_dict(provider)

        update_data = payload.model_dump(exclude_unset=True)
        update_data.pop("api_key", None)

        if (
            "provider_key" in update_data
            and update_data["provider_key"] != provider.provider_key
        ):
            existing = await session.execute(
                select(AdminLLMProvider).filter(
                    AdminLLMProvider.provider_key == update_data["provider_key"],
                    AdminLLMProvider.id != provider_id,
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"A provider with key '{update_data['provider_key']}' already exists",
                )

        for key, value in update_data.items():
            setattr(provider, key, value)

        if "api_key" in payload.model_fields_set:
            provider.api_key_encrypted = (
                TokenEncryption(config.SECRET_KEY).encrypt_token(payload.api_key)
                if payload.api_key
                else None
            )

        provider.updated_by_id = auth.user.id

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_provider.update",
            target_type="admin_llm_provider",
            target_id=str(provider_id),
            before=before,
            after=_provider_audit_dict(provider),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(provider)

        await apply_admin_llm_configs(session)

        return _to_provider_read(provider)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update LLM provider: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM provider: {e!s}"
        ) from e


@router.delete("/llm-providers/{provider_id}")
async def delete_llm_provider(
    provider_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete an LLM provider (cascades to its models via the FK). Requires
    llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM providers",
        )

        provider = await _get_provider_or_404(session, provider_id)
        before = _provider_audit_dict(provider)
        await session.delete(provider)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_provider.delete",
            target_type="admin_llm_provider",
            target_id=str(provider_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()

        await apply_admin_llm_configs(session)

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete LLM provider: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete LLM provider: {e!s}"
        ) from e


@router.post(
    "/llm-providers/{provider_id}/reveal", response_model=AdminLLMProviderRevealResponse
)
async def reveal_llm_provider_api_key(
    provider_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return a provider's decrypted plaintext API key. Gated behind
    llm_providers:write (the higher bar; this catalog has no separate reveal
    permission). Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to reveal LLM provider API keys",
        )

        provider = await _get_provider_or_404(session, provider_id)
        api_key = None
        if provider.api_key_encrypted:
            api_key = TokenEncryption(config.SECRET_KEY).decrypt_token(
                provider.api_key_encrypted
            )

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_provider.reveal",
            target_type="admin_llm_provider",
            target_id=str(provider_id),
            ip_address=_client_ip(request),
        )

        await session.commit()

        return AdminLLMProviderRevealResponse(id=provider_id, api_key=api_key)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reveal LLM provider API key: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to reveal LLM provider API key: {e!s}"
        ) from e


@router.post(
    "/llm-providers/{provider_id}/discover-models",
    response_model=list[AdminLLMDiscoveredModelRead],
)
async def discover_llm_provider_models(
    provider_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Fetch the live list of models available from this provider's own API.
    Reuses the workspace BYOK flow's `model_connection_service.discover_models`
    against an in-memory `Connection` built from this provider's stored
    fields (never added to the session or committed) -- mirrors
    `POST /model-connections/discover-preview`
    (`app.routes.model_connections_routes`) but sources the draft connection
    from an `AdminLLMProvider` row instead of a request body.

    Calls the provider's API using the already-stored key but never returns
    the key itself, so this is gated on the read permission, not write.
    Providers with no stored key, or a `discovery` kind of `"none"`/`"static"`,
    are not special-cased here: `discover_models` already handles them (an
    unauthenticated attempt, an empty list, and LiteLLM's bundled cost map,
    respectively -- none of those are errors). Requires llm_providers:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_READ.value,
            "You don't have permission to view LLM providers",
        )

        provider = await _get_provider_or_404(session, provider_id)

        decrypted_key = None
        if provider.api_key_encrypted:
            decrypted_key = TokenEncryption(config.SECRET_KEY).decrypt_token(
                provider.api_key_encrypted
            )

        draft = Connection(
            provider=provider.provider_key,
            base_url=provider.api_base_override or provider.default_base_url,
            api_key=decrypted_key or None,
            extra={},
        )

        try:
            discovered = await discover_models(draft)
        except ModelDiscoveryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return [
            AdminLLMDiscoveredModelRead(
                model_id=item["model_id"],
                display_name=item.get("display_name"),
                supports_chat=item.get("supports_chat"),
                supports_image_input=item.get("supports_image_input"),
                supports_tools=item.get("supports_tools"),
                supports_image_generation=item.get("supports_image_generation"),
                max_input_tokens=item.get("max_input_tokens"),
            )
            for item in discovered
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to discover models for provider {provider_id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to discover models: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@router.get("/llm-models", response_model=list[AdminLLMModelRead])
async def list_llm_models(
    provider_id: int | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List LLM models, optionally filtered to one provider. Requires
    llm_providers:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_READ.value,
            "You don't have permission to view LLM models",
        )
        stmt = select(AdminLLMModel)
        if provider_id is not None:
            stmt = stmt.filter(AdminLLMModel.provider_id == provider_id)
        stmt = stmt.order_by(AdminLLMModel.id)
        result = await session.execute(stmt)
        return [_to_model_read(m) for m in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list LLM models: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list LLM models: {e!s}"
        ) from e


@router.post("/llm-models", response_model=AdminLLMModelRead)
async def create_llm_model(
    payload: AdminLLMModelCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new LLM model under a provider. Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM models",
        )

        await _get_provider_or_404(session, payload.provider_id)

        existing = await session.execute(
            select(AdminLLMModel).filter(
                AdminLLMModel.provider_id == payload.provider_id,
                AdminLLMModel.model_name == payload.model_name,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"Model '{payload.model_name}' already exists for this provider",
            )

        if payload.seo_slug:
            slug_conflict = await session.execute(
                select(AdminLLMModel).filter(AdminLLMModel.seo_slug == payload.seo_slug)
            )
            if slug_conflict.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"SEO slug '{payload.seo_slug}' is already in use",
                )

        model = AdminLLMModel(
            **payload.model_dump(),
            created_by_id=auth.user.id,
            updated_by_id=auth.user.id,
        )
        session.add(model)
        await session.flush()

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_model.create",
            target_type="admin_llm_model",
            target_id=str(model.id),
            after=_model_audit_dict(model),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(model)

        await apply_admin_llm_configs(session)

        return _to_model_read(model)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create LLM model: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create LLM model: {e!s}"
        ) from e


@router.put("/llm-models/{model_id}", response_model=AdminLLMModelRead)
async def update_llm_model(
    model_id: int,
    payload: AdminLLMModelUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an LLM model (partial update). Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM models",
        )

        model = await _get_model_or_404(session, model_id)
        before = _model_audit_dict(model)

        update_data = payload.model_dump(exclude_unset=True)

        new_provider_id = update_data.get("provider_id", model.provider_id)
        new_model_name = update_data.get("model_name", model.model_name)
        if "provider_id" in update_data or "model_name" in update_data:
            if "provider_id" in update_data:
                await _get_provider_or_404(session, new_provider_id)
            dup = await session.execute(
                select(AdminLLMModel).filter(
                    AdminLLMModel.provider_id == new_provider_id,
                    AdminLLMModel.model_name == new_model_name,
                    AdminLLMModel.id != model_id,
                )
            )
            if dup.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"Model '{new_model_name}' already exists for this provider",
                )

        if update_data.get("seo_slug"):
            slug_conflict = await session.execute(
                select(AdminLLMModel).filter(
                    AdminLLMModel.seo_slug == update_data["seo_slug"],
                    AdminLLMModel.id != model_id,
                )
            )
            if slug_conflict.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"SEO slug '{update_data['seo_slug']}' is already in use",
                )

        for key, value in update_data.items():
            setattr(model, key, value)
        model.updated_by_id = auth.user.id

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_model.update",
            target_type="admin_llm_model",
            target_id=str(model_id),
            before=before,
            after=_model_audit_dict(model),
            ip_address=_client_ip(request),
        )

        await session.commit()
        await session.refresh(model)

        await apply_admin_llm_configs(session)

        return _to_model_read(model)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update LLM model: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM model: {e!s}"
        ) from e


@router.delete("/llm-models/{model_id}")
async def delete_llm_model(
    model_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete an LLM model. Requires llm_providers:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to manage LLM models",
        )

        model = await _get_model_or_404(session, model_id)
        before = _model_audit_dict(model)
        await session.delete(model)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_model.delete",
            target_type="admin_llm_model",
            target_id=str(model_id),
            before=before,
            ip_address=_client_ip(request),
        )

        await session.commit()

        await apply_admin_llm_configs(session)

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete LLM model: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete LLM model: {e!s}"
        ) from e


@router.post("/llm-models/reload", response_model=AdminLLMReloadResponse)
async def reload_llm_catalog(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Force-reapply the DB-backed catalog into `config.GLOBAL_LLM_CONFIGS`.
    A manual safety-net/ops action distinct from the automatic re-apply that
    already happens on every mutation above -- useful if the process's
    in-memory catalog ever drifts from the DB. Requires llm_providers:write.

    Audited like every other write-permissioned endpoint here: this mutates
    live process state (it can swap the whole model catalog under in-flight
    traffic), so it needs an audit trail even though it writes no DB row.
    There is no specific target -- it's a whole-catalog operation -- so
    `target_id` is left unset."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.LLM_PROVIDERS_WRITE.value,
            "You don't have permission to reload the LLM catalog",
        )
        applied = await apply_admin_llm_configs(session)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="admin_llm_catalog.reload",
            target_type="admin_llm_catalog",
            after={"applied_count": applied},
            ip_address=_client_ip(request),
        )
        await session.commit()

        return AdminLLMReloadResponse(applied_count=applied)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reload LLM catalog: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to reload LLM catalog: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Free-model quota
# ---------------------------------------------------------------------------


def _to_global_quota_read(row: FreeModelGlobalQuota) -> AdminFreeQuotaGlobalRead:
    return AdminFreeQuotaGlobalRead(
        period_start=row.period_start,
        tokens_reserved=row.tokens_reserved,
        tokens_used=row.tokens_used,
        cap_tokens=config.FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS,
        updated_at=row.updated_at,
    )


def _to_user_quota_read(
    user_id: UUID, row: FreeModelUserQuota | None
) -> AdminFreeQuotaUserRead:
    if row is None:
        return AdminFreeQuotaUserRead(
            user_id=user_id,
            period_start=None,
            tokens_reserved=None,
            tokens_used=None,
            cap_tokens=config.FREE_MODEL_USER_MONTHLY_CAP_TOKENS,
            updated_at=None,
        )
    return AdminFreeQuotaUserRead(
        user_id=user_id,
        period_start=row.period_start,
        tokens_reserved=row.tokens_reserved,
        tokens_used=row.tokens_used,
        cap_tokens=config.FREE_MODEL_USER_MONTHLY_CAP_TOKENS,
        updated_at=row.updated_at,
    )


def _global_quota_audit_dict(row: FreeModelGlobalQuota) -> dict[str, Any]:
    return {
        "period_start": str(row.period_start),
        "tokens_reserved": row.tokens_reserved,
        "tokens_used": row.tokens_used,
    }


def _user_quota_audit_dict(row: FreeModelUserQuota) -> dict[str, Any]:
    return {
        "period_start": str(row.period_start),
        "tokens_reserved": row.tokens_reserved,
        "tokens_used": row.tokens_used,
    }


@router.get("/llm-quota", response_model=AdminFreeQuotaGlobalRead)
async def get_llm_quota(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Platform-wide free-tier token quota snapshot for the current period,
    plus the configured cap. Requires quotas:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.QUOTAS_READ.value,
            "You don't have permission to view free-tier quota usage",
        )
        row = await get_global_quota_snapshot(session)
        return _to_global_quota_read(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get free-model global quota: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get free-model global quota: {e!s}"
        ) from e


@router.get("/llm-quota/users/{user_id}", response_model=AdminFreeQuotaUserRead)
async def get_llm_quota_for_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """One user's free-tier token quota snapshot for the current period,
    plus the configured cap. Usage fields are null if the user has never
    reserved free-tier quota yet. Requires quotas:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.QUOTAS_READ.value,
            "You don't have permission to view free-tier quota usage",
        )
        row = await get_user_quota_snapshot(session, user_id)
        return _to_user_quota_read(user_id, row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get free-model user quota: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get free-model user quota: {e!s}"
        ) from e


@router.post("/llm-quota/reset", response_model=AdminFreeQuotaGlobalRead)
async def reset_llm_quota(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Manually reset the platform-wide free-tier quota: zero its counters
    and bump `period_start` to the current period. Requires quotas:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.QUOTAS_WRITE.value,
            "You don't have permission to reset free-tier quota usage",
        )

        # Snapshot before the reset: `after` is uninformative by construction
        # (a reset always zeroes the row), so `before` is the only half of the
        # audit trail that can show what was actually wiped.
        before = _global_quota_audit_dict(await get_global_quota_snapshot(session))

        row = await reset_global_quota(session)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="free_model_global_quota.reset",
            target_type="free_model_global_quota",
            before=before,
            after=_global_quota_audit_dict(row),
            ip_address=_client_ip(request),
        )
        await session.commit()

        return _to_global_quota_read(row)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reset free-model global quota: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to reset free-model global quota: {e!s}"
        ) from e


@router.post("/llm-quota/users/{user_id}/reset", response_model=AdminFreeQuotaUserRead)
async def reset_llm_quota_for_user(
    user_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Manually reset one user's free-tier quota: zero its counters and
    bump `period_start` to the current period. Get-or-creates the row first
    so an admin can pre-emptively reset a user who's never used free tier
    yet. Requires quotas:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.QUOTAS_WRITE.value,
            "You don't have permission to reset free-tier quota usage",
        )

        # Snapshot before the reset, same reasoning as the global reset above.
        # `None` when the user had no row at all yet (`reset_user_quota`
        # get-or-creates one), which is itself the accurate "nothing was
        # wiped" record.
        existing = await get_user_quota_snapshot(session, user_id)
        before = _user_quota_audit_dict(existing) if existing is not None else None

        row = await reset_user_quota(session, user_id)

        await record_admin_action(
            session,
            actor_user_id=auth.user.id,
            action="free_model_user_quota.reset",
            target_type="free_model_user_quota",
            target_id=str(user_id),
            before=before,
            after=_user_quota_audit_dict(row),
            ip_address=_client_ip(request),
        )
        await session.commit()

        return _to_user_quota_read(user_id, row)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reset free-model user quota: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to reset free-model user quota: {e!s}"
        ) from e
