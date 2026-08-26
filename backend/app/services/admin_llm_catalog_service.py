"""
Admin LLM provider/model catalog service: maps DB-backed
`AdminLLMProvider`/`AdminLLMModel` rows into the same YAML-shaped dicts
`app.config.load_global_llm_configs()` produces from
`global_llm_config.yaml`, and hot-swaps them into the live
`config.GLOBAL_LLM_CONFIGS` list.

Storage: one `AdminLLMProvider` row per configured provider connection, one
`AdminLLMModel` row per model exposed under that provider (migration
`177_add_admin_llm_catalog_and_quota`). This is the DB-backed replacement for
hand-editing the gitignored `global_llm_config.yaml` -- changes made through
the super admin dashboard take effect immediately via the same hot-swap
mechanism, no restart required.

Hot-swap mechanism: `config = Config()` (`app.config.config`) is a real
singleton *instance*. `apply_admin_llm_configs` reassigns
`config.GLOBAL_LLM_CONFIGS` to a freshly built list (never mutates the
existing list in place) -- list reassignment is atomic under the GIL, so
concurrent readers of `config.GLOBAL_LLM_CONFIGS` see either the old full
list or the new full list, never a partially-built one. This is the same
technique `app.services.openrouter_integration_service.refresh` already uses
to hot-swap in OpenRouter's dynamically-discovered models: entries carrying
a marker key (`_admin_db_sourced` here, `_OPENROUTER_DYNAMIC_MARKER` there)
are filtered out and replaced, every other entry (static YAML configs,
OpenRouter dynamic configs) is left untouched. The swap is followed by the
same post-swap steps that precedent performs (derived-catalog reprojection,
pricing re-registration, router rebuild), see `apply_admin_llm_configs`.

Synthetic config id: each admin-managed model is assigned
`-(100000 + model.id)` as its `GLOBAL_LLM_CONFIGS` entry id. This stays well
clear of the YAML static range (-1..-999) and OpenRouter's dynamic range
(around -10000..), so none of the three sources can collide.

API keys are encrypted at rest on `AdminLLMProvider.api_key_encrypted` via
the same `TokenEncryption` class already used for OAuth tokens and Phase B's
settings vault; a fresh `TokenEncryption` instance is constructed on every
decrypt (never cached).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import config, refresh_global_model_catalog
from app.db import AdminLLMModel, AdminLLMProvider
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

# Marker key on every config dict this service produces, so a later re-apply
# can find and replace only its own previously-injected entries (see
# `apply_admin_llm_configs`) without touching static YAML or OpenRouter
# dynamic entries.
ADMIN_DB_SOURCED_MARKER = "_admin_db_sourced"

# Offset applied to `AdminLLMModel.id` to derive the synthetic negative id
# used in `config.GLOBAL_LLM_CONFIGS`. Chosen to stay well clear of the YAML
# static range (-1..-999) and OpenRouter's dynamic range (around -10000..,
# see `id_offset` in `app.services.openrouter_integration_service`).
SYNTHETIC_ID_OFFSET = 100000


def _decrypt_api_key(provider: AdminLLMProvider) -> str:
    """Decrypt `provider.api_key_encrypted`, or "" if no key is set."""
    if not provider.api_key_encrypted:
        return ""
    return TokenEncryption(config.SECRET_KEY).decrypt_token(provider.api_key_encrypted)


def model_to_config_dict(
    model: AdminLLMModel, provider: AdminLLMProvider
) -> dict[str, Any]:
    """Map one enabled `AdminLLMModel` + its `AdminLLMProvider` into the
    YAML-shaped dict `config.GLOBAL_LLM_CONFIGS` expects. Pure mapping (no
    DB access beyond decrypting the already-loaded provider's API key) so
    it's independently testable against in-memory ORM instances."""
    return {
        "id": -(SYNTHETIC_ID_OFFSET + model.id),
        "name": model.name,
        "billing_tier": model.billing_tier,
        "anonymous_enabled": model.anonymous_enabled,
        "seo_enabled": model.seo_enabled,
        "seo_slug": model.seo_slug,
        "seo_title": model.seo_title,
        "seo_description": model.seo_description,
        "quota_reserve_tokens": model.quota_reserve_tokens,
        "provider": provider.provider_key,
        # Mirrors `model_resolver.py`'s `spec.litellm_prefix or str(provider)`:
        # `create_chat_litellm_from_config` (llm_config.py) uses
        # `custom_provider` verbatim as the litellm prefix when set, and only
        # falls back to building `f"{provider}/{model_name}"` from the raw
        # `provider` field when it's None. Needed for any provider whose
        # `litellm_prefix` differs from its `provider_key` (the
        # openai_compatible/openai_compatible_raw/lm_studio/ollama_chat
        # transports, and any custom provider_key an admin enters for a
        # provider outside the static registry) -- without it, the litellm
        # call would be built with the wrong prefix and fail at call time.
        "custom_provider": provider.litellm_prefix or None,
        "model_name": model.model_name,
        "supports_image_input": model.supports_image_input,
        "supports_tools": model.supports_tools,
        "max_input_tokens": model.max_input_tokens,
        "api_key": _decrypt_api_key(provider),
        "api_base": (
            model.api_base_override
            or provider.api_base_override
            or provider.default_base_url
        ),
        "api_version": model.api_version,
        "rpm": model.rpm,
        "tpm": model.tpm,
        "litellm_params": model.litellm_params or {},
        "system_instructions": model.system_instructions,
        "use_default_system_instructions": model.use_default_system_instructions,
        "citations_enabled": model.citations_enabled,
        "is_planner": model.is_planner,
        "router_pool_eligible": model.router_pool_eligible,
        ADMIN_DB_SOURCED_MARKER: True,
    }


async def apply_admin_llm_configs(session: AsyncSession) -> int:
    """Load every enabled `AdminLLMModel` (whose `AdminLLMProvider` is also
    enabled), map each to a YAML-shaped dict, and hot-swap them into
    `config.GLOBAL_LLM_CONFIGS`, replacing only previously-injected
    admin-sourced entries. Call once at FastAPI lifespan startup (after DB
    connectivity is confirmed) and again after every catalog mutation.

    Follows the swap with the same three post-swap steps
    `openrouter_integration_service.refresh` performs, because
    `GLOBAL_LLM_CONFIGS` alone is not what most consumers actually read:

    1. `refresh_global_model_catalog()` rebuilds
       `config.GLOBAL_MODELS`/`config.GLOBAL_CONNECTIONS`, the *derived*
       projection every authenticated-user consumer resolves against (the
       chat model loader in
       `app.tasks.chat.streaming.flows.shared.llm_bundle`, the
       `GET /global-model-connections` model picker, Auto-mode pin
       candidates). Without this an admin-created model exists in
       `GLOBAL_LLM_CONFIGS` but is invisible and unusable everywhere else
       until the next process restart. Deliberately NOT wrapped in
       try/except: it is a pure in-memory reprojection of the list we just
       assigned (no I/O, nothing to fail on), and swallowing a failure here
       would silently leave the catalog half-applied.
    2. LiteLLM pricing re-registration, so a newly created premium model
       has a cost entry immediately instead of billing 0 until restart.
    3. LLM router rebuild + chat router cache clear, so a model disabled or
       deleted through the dashboard actually stops being reachable through
       the Auto-mode/router-pool flows. Skipped while the router is still
       uninitialized (the boot case) so it does not pre-empt startup's own
       correctly-ordered `initialize_llm_router()`; see the inline comment.

    Steps 2 and 3 are each independently wrapped in try/except-and-log:
    they are best-effort side effects, and a failure in either must not
    fail the catalog apply itself (which the CRUD routes call after an
    already-committed mutation).

    Returns the count of model configs applied.
    """
    result = await session.execute(
        select(AdminLLMModel)
        .options(selectinload(AdminLLMModel.provider))
        .join(AdminLLMProvider, AdminLLMModel.provider_id == AdminLLMProvider.id)
        .filter(AdminLLMModel.is_enabled.is_(True))
        .filter(AdminLLMProvider.is_enabled.is_(True))
    )
    models = result.scalars().all()

    new_admin_configs = [model_to_config_dict(m, m.provider) for m in models]

    non_admin_configs = [
        c for c in config.GLOBAL_LLM_CONFIGS if not c.get(ADMIN_DB_SOURCED_MARKER)
    ]
    config.GLOBAL_LLM_CONFIGS = non_admin_configs + new_admin_configs

    # Rebuild the derived GLOBAL_MODELS/GLOBAL_CONNECTIONS projection from the
    # list we just assigned (see this function's docstring, step 1).
    refresh_global_model_catalog()

    # Re-register LiteLLM pricing for the freshly applied catalog so a newly
    # created premium model bills correctly on its first call. Runs before the
    # router rebuild because the router may issue cost-table lookups during
    # deployment registration.
    try:
        from app.services.pricing_registration import (
            register_pricing_from_global_configs,
        )

        register_pricing_from_global_configs()
    except Exception as exc:
        logger.warning("[admin_llm_catalog] pricing re-registration skipped (%s)", exc)

    # Rebuild the LiteLLM router so the freshly applied configs flow through
    # (and so a model disabled/deleted through the dashboard stops being
    # routable), then drop the per-chat router instance cache built off the
    # previous catalog.
    #
    # Skipped when the router has never been initialized, which is exactly the
    # boot case: `lifespan` calls this function (via `_apply_admin_llm_catalog`)
    # *before* `initialize_openrouter_integration()` and `initialize_llm_router()`.
    # `LLMRouterService.initialize` short-circuits once `_initialized` is set, so
    # rebuilding here at boot would claim that one-shot initialization against a
    # config list that does not yet contain OpenRouter's dynamically fetched
    # models, and startup's own `initialize_llm_router()` would then no-op --
    # silently dropping OpenRouter premium deployments from the router pool for
    # the life of the process. At boot, leave the router to the startup sequence
    # that already orders it correctly; at runtime (every dashboard mutation and
    # the reload endpoint) the router is already initialized, so the rebuild runs.
    try:
        from app.config import config as _app_config
        from app.services.llm_router_service import (
            LLMRouterService,
            _router_instance_cache as _chat_router_cache,
        )

        if LLMRouterService.get_instance()._initialized:
            LLMRouterService.rebuild(
                _app_config.GLOBAL_LLM_CONFIGS,
                getattr(_app_config, "ROUTER_SETTINGS", None),
            )
            _chat_router_cache.clear()
        else:
            logger.debug(
                "[admin_llm_catalog] router not initialized yet; "
                "leaving pool build to startup"
            )
    except Exception as exc:
        logger.warning("[admin_llm_catalog] router rebuild skipped (%s)", exc)

    logger.info(
        "[admin_llm_catalog] applied %d admin-managed model config(s)",
        len(new_admin_configs),
    )
    return len(new_admin_configs)


__all__ = [
    "ADMIN_DB_SOURCED_MARKER",
    "SYNTHETIC_ID_OFFSET",
    "apply_admin_llm_configs",
    "model_to_config_dict",
]
