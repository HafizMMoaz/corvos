"""Unit tests for `app.services.admin_llm_catalog_service`'s pure mapping
logic: `model_to_config_dict` and the synthetic id formula. These exercise
plain (unpersisted) `AdminLLMProvider`/`AdminLLMModel` instances only -- no
DB session is touched.

Tests that exercise `apply_admin_llm_configs` itself (DB reads plus the live
hot-swap against `config.GLOBAL_LLM_CONFIGS`) and the CRUD routes live in
`tests/integration/test_admin_llm_catalog.py` instead, mirroring the
DB-dependency split Phase B's settings vault tests already document (see
that file's module docstring): the `unit` marker here is reserved for pure
logic tests with no DB or external services (see `pyproject.toml`).
"""

from __future__ import annotations

import pytest

from app.config import config
from app.db import AdminLLMModel, AdminLLMProvider
from app.services.admin_llm_catalog_service import (
    ADMIN_DB_SOURCED_MARKER,
    SYNTHETIC_ID_OFFSET,
    model_to_config_dict,
)
from app.utils.oauth_security import TokenEncryption

pytestmark = pytest.mark.unit


def _provider(**overrides) -> AdminLLMProvider:
    defaults = {
        "id": 1,
        "provider_key": "openai",
        "display_name": "OpenAI",
        "transport": "native",
        "litellm_prefix": "openai",
        "default_base_url": None,
        "base_url_required": False,
        "auth_style": "bearer",
        "api_key_encrypted": None,
        "api_base_override": None,
        "is_enabled": True,
        "notes": None,
    }
    defaults.update(overrides)
    return AdminLLMProvider(**defaults)


def _model(**overrides) -> AdminLLMModel:
    defaults = {
        "id": 42,
        "provider_id": 1,
        "name": "GPT-5",
        "model_name": "openai/gpt-5",
        "billing_tier": "premium",
        "anonymous_enabled": False,
        "seo_enabled": False,
        "seo_slug": None,
        "seo_title": None,
        "seo_description": None,
        "quota_reserve_tokens": None,
        "supports_image_input": True,
        "supports_tools": True,
        "max_input_tokens": 200_000,
        "api_base_override": None,
        "api_version": None,
        "rpm": None,
        "tpm": None,
        "litellm_params": None,
        "system_instructions": None,
        "use_default_system_instructions": True,
        "citations_enabled": True,
        "is_planner": False,
        "router_pool_eligible": True,
        "is_enabled": True,
    }
    defaults.update(overrides)
    return AdminLLMModel(**defaults)


# ---------------------------------------------------------------------------
# model_to_config_dict
# ---------------------------------------------------------------------------


def test_model_to_config_dict_maps_every_field_with_correct_types():
    provider = _provider(
        id=7,
        provider_key="anthropic",
        litellm_prefix="anthropic",
        default_base_url="https://api.anthropic.com",
    )
    model = _model(
        id=42,
        provider_id=7,
        name="Claude",
        model_name="anthropic/claude-x",
        quota_reserve_tokens=1000,
        rpm=60,
        tpm=100_000,
        system_instructions="Be helpful.",
    )

    result = model_to_config_dict(model, provider)

    assert result["id"] == -(SYNTHETIC_ID_OFFSET + 42)
    assert isinstance(result["id"], int)
    assert result["name"] == "Claude"
    assert result["billing_tier"] == "premium"
    assert result["anonymous_enabled"] is False
    assert result["seo_enabled"] is False
    assert result["seo_slug"] is None
    assert result["seo_title"] is None
    assert result["seo_description"] is None
    assert result["quota_reserve_tokens"] == 1000
    assert result["provider"] == "anthropic"
    assert result["custom_provider"] == "anthropic"
    assert result["model_name"] == "anthropic/claude-x"
    assert result["supports_image_input"] is True
    assert result["supports_tools"] is True
    assert result["max_input_tokens"] == 200_000
    assert result["api_key"] == ""
    assert result["api_base"] == "https://api.anthropic.com"
    assert result["api_version"] is None
    assert result["rpm"] == 60
    assert result["tpm"] == 100_000
    assert result["litellm_params"] == {}
    assert result["system_instructions"] == "Be helpful."
    assert result["use_default_system_instructions"] is True
    assert result["citations_enabled"] is True
    assert result["is_planner"] is False
    assert result["router_pool_eligible"] is True
    assert result[ADMIN_DB_SOURCED_MARKER] is True


def test_model_to_config_dict_missing_api_key_maps_to_empty_string():
    provider = _provider(api_key_encrypted=None)
    model = _model()
    assert model_to_config_dict(model, provider)["api_key"] == ""


def test_model_to_config_dict_decrypts_provider_api_key():
    secret_key = "unit-test-secret-key-for-admin-llm-catalog"
    ciphertext = TokenEncryption(secret_key).encrypt_token("sk-plaintext-value")
    provider = _provider(api_key_encrypted=ciphertext)
    model = _model()

    original_secret = config.SECRET_KEY
    config.SECRET_KEY = secret_key
    try:
        result = model_to_config_dict(model, provider)
    finally:
        config.SECRET_KEY = original_secret

    assert result["api_key"] == "sk-plaintext-value"
    # The stored ciphertext must never leak into the produced config dict.
    assert ciphertext not in str(result)


def test_model_to_config_dict_api_base_precedence():
    provider = _provider(
        api_base_override="https://provider-override",
        default_base_url="https://provider-default",
    )

    # model override wins over provider override.
    model_with_override = _model(api_base_override="https://model-override")
    assert (
        model_to_config_dict(model_with_override, provider)["api_base"]
        == "https://model-override"
    )

    # provider override wins over provider default when model has none.
    model_no_override = _model(api_base_override=None)
    assert (
        model_to_config_dict(model_no_override, provider)["api_base"]
        == "https://provider-override"
    )

    # provider default is the final fallback.
    provider_no_override = _provider(
        api_base_override=None, default_base_url="https://provider-default"
    )
    assert (
        model_to_config_dict(model_no_override, provider_no_override)["api_base"]
        == "https://provider-default"
    )


def test_model_to_config_dict_custom_provider_set_when_litellm_prefix_present():
    """`custom_provider` must carry the provider's `litellm_prefix` verbatim
    -- `create_chat_litellm_from_config` (app.agents.chat.runtime.llm_config)
    uses it as-is for the litellm call prefix when present, the same
    mechanism `model_resolver.py`'s BYOK path already relies on
    (`spec.litellm_prefix or str(provider)`). Providers whose `provider_key`
    doesn't match a real litellm-recognized identifier (the
    openai_compatible/openai_compatible_raw/lm_studio/ollama_chat transports,
    or any fully custom provider_key) depend on this to build a working
    litellm call at all."""
    provider = _provider(provider_key="my_custom_llm", litellm_prefix="openai")
    model = _model()

    result = model_to_config_dict(model, provider)

    assert result["provider"] == "my_custom_llm"
    assert result["custom_provider"] == "openai"


def test_model_to_config_dict_custom_provider_none_when_litellm_prefix_unset():
    """When `litellm_prefix` is unset (the common case for standard registry
    providers like openai/anthropic), `custom_provider` must be None so
    `create_chat_litellm_from_config` falls through to its existing
    `provider`-based branch -- no behavior change for those providers."""
    provider = _provider(provider_key="openai", litellm_prefix=None)
    model = _model()

    result = model_to_config_dict(model, provider)

    assert result["custom_provider"] is None


def test_model_to_config_dict_litellm_params_defaults_to_empty_dict():
    provider = _provider()

    assert model_to_config_dict(_model(litellm_params=None), provider)[
        "litellm_params"
    ] == {}

    params = {"max_tokens": 4096, "input_cost_per_token": 0.000003}
    assert (
        model_to_config_dict(_model(litellm_params=params), provider)[
            "litellm_params"
        ]
        == params
    )


# ---------------------------------------------------------------------------
# Synthetic id offset -- must stay clear of the YAML static range (-1..-999)
# and OpenRouter's dynamic range (around -10000..).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row_id", [1, 2, 50, 999, 5000, 1_000_000])
def test_synthetic_id_formula(row_id):
    provider = _provider()
    model = _model(id=row_id)

    result = model_to_config_dict(model, provider)

    assert result["id"] == -(100_000 + row_id)


@pytest.mark.parametrize("row_id", [1, 2, 50, 999, 5000, 1_000_000])
def test_synthetic_id_does_not_collide_with_static_or_openrouter_ranges(row_id):
    synthetic_id = -(SYNTHETIC_ID_OFFSET + row_id)

    # YAML static range is -1..-999.
    assert not (-999 <= synthetic_id <= -1)
    # OpenRouter's dynamic range starts around -10000 and only decrements
    # further on collision -- comfortably above -100000 for any plausible
    # catalog size.
    assert synthetic_id < -10_000


def test_synthetic_id_is_injective_across_row_ids():
    ids = [-(SYNTHETIC_ID_OFFSET + row_id) for row_id in range(1, 1000)]
    assert len(ids) == len(set(ids))
