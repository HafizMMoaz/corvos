"""Integration tests for the super admin LLM provider/model catalog (Phase C
Track 1 of the super admin dashboard): `app.services.admin_llm_catalog_service`
and `app.routes.admin.admin_llm_routes`.

Route handlers are called directly (session + AuthContext passed in), the
same pattern used by `tests/integration/test_admin_rbac.py` (Phase A) and
`tests/integration/test_admin_settings.py` (Phase B), rather than spinning up
an ASGI test client.

NOTE ON TEST LOCATION: mirrors Phase B's documented deviation from the task
brief's suggested `tests/unit/...` path for this same reason -- these tests
exercise real DB rows (admin_llm_providers, admin_llm_models,
admin_audit_logs) and the `unit` pytest marker is reserved for pure logic
tests with no DB or external services (see `pyproject.toml`); the
`db_session` fixture these tests need only exists under
`tests/integration/conftest.py`. Pure-logic coverage of the DB-row -> YAML
dict mapping and the synthetic id formula lives in
`tests/unit/services/test_admin_llm_catalog_service.py` instead.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    AdminAuditLog,
    AdminLLMModel,
    AdminLLMProvider,
    PlatformRole,
    PlatformRoleAssignment,
    User,
)
from app.routes.admin import admin_llm_routes as routes
from app.schemas import (
    AdminLLMModelCreate,
    AdminLLMModelUpdate,
    AdminLLMProviderCreate,
    AdminLLMProviderUpdate,
)
from app.services import admin_llm_catalog_service as catalog
from app.utils.oauth_security import TokenEncryption

pytestmark = pytest.mark.integration


def _auth(user: User) -> AuthContext:
    return AuthContext.session(user)


def _fake_request() -> Request:
    return Request(scope={"type": "http", "client": ("127.0.0.1", 0), "headers": []})


async def _make_user(session: AsyncSession, *, email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"{uuid.uuid4()}@corvos.test",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_admin(
    session: AsyncSession, *, permissions: list[str], name: str | None = None
) -> User:
    """Create a user granted exactly `permissions` via a fresh platform role."""
    user = await _make_user(session)
    role = PlatformRole(
        name=name or f"role_{uuid.uuid4().hex[:8]}",
        permissions=permissions,
        is_system_role=False,
    )
    session.add(role)
    await session.flush()
    session.add(PlatformRoleAssignment(user_id=user.id, role_id=role.id))
    await session.flush()
    return user


async def _make_provider(
    session: AsyncSession,
    *,
    provider_key: str | None = None,
    is_enabled: bool = True,
    api_key_encrypted: str | None = None,
    litellm_prefix: str | None = None,
) -> AdminLLMProvider:
    provider = AdminLLMProvider(
        provider_key=provider_key or f"provider_{uuid.uuid4().hex[:8]}",
        display_name="Test Provider",
        transport="native",
        auth_style="bearer",
        is_enabled=is_enabled,
        api_key_encrypted=api_key_encrypted,
        litellm_prefix=litellm_prefix,
    )
    session.add(provider)
    await session.flush()
    return provider


async def _make_model(
    session: AsyncSession,
    provider: AdminLLMProvider,
    *,
    model_name: str | None = None,
    is_enabled: bool = True,
    billing_tier: str = "premium",
) -> AdminLLMModel:
    model = AdminLLMModel(
        provider_id=provider.id,
        name="Test Model",
        model_name=model_name or f"model-{uuid.uuid4().hex[:8]}",
        is_enabled=is_enabled,
        billing_tier=billing_tier,
    )
    session.add(model)
    await session.flush()
    return model


async def _audit_rows(
    session: AsyncSession, *, action: str, target_id: str
) -> list[AdminAuditLog]:
    result = await session.execute(
        select(AdminAuditLog).filter(
            AdminAuditLog.action == action, AdminAuditLog.target_id == target_id
        )
    )
    return list(result.scalars().all())


@pytest_asyncio.fixture(autouse=True)
async def _isolate_global_llm_configs():
    """`config.GLOBAL_LLM_CONFIGS` is a process-wide singleton list that
    `apply_admin_llm_configs` reassigns -- not something `db_session`'s
    transaction rollback can undo. Save/restore it around every test so
    catalog mutations from one test never leak into the next.

    `GLOBAL_MODELS`/`GLOBAL_CONNECTIONS` are the derived projection the apply
    now also rebuilds, so they need the same save/restore treatment."""
    before = list(config.GLOBAL_LLM_CONFIGS)
    before_models = list(getattr(config, "GLOBAL_MODELS", []))
    before_connections = list(getattr(config, "GLOBAL_CONNECTIONS", []))
    yield
    config.GLOBAL_LLM_CONFIGS = before
    config.GLOBAL_MODELS = before_models
    config.GLOBAL_CONNECTIONS = before_connections


# ---------------------------------------------------------------------------
# app.services.admin_llm_catalog_service.apply_admin_llm_configs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_excludes_disabled_provider_and_model(
    db_session: AsyncSession,
):
    enabled_provider = await _make_provider(db_session)
    await _make_model(db_session, enabled_provider, model_name="enabled-model")

    disabled_provider = await _make_provider(db_session, is_enabled=False)
    await _make_model(
        db_session, disabled_provider, model_name="model-under-disabled-provider"
    )

    await _make_model(
        db_session, enabled_provider, model_name="disabled-model", is_enabled=False
    )

    applied = await catalog.apply_admin_llm_configs(db_session)

    admin_entries = [
        c for c in config.GLOBAL_LLM_CONFIGS if c.get(catalog.ADMIN_DB_SOURCED_MARKER)
    ]
    assert applied == len(admin_entries)
    model_names = {c["model_name"] for c in admin_entries}
    assert "enabled-model" in model_names
    assert "model-under-disabled-provider" not in model_names
    assert "disabled-model" not in model_names


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_sets_custom_provider_from_litellm_prefix(
    db_session: AsyncSession,
):
    """A provider with a `litellm_prefix` that differs from its
    `provider_key` (e.g. an admin-entered custom provider, or the
    openai_compatible/lm_studio/ollama_chat transports) must end up with
    `custom_provider` populated in the applied config -- otherwise
    `create_chat_litellm_from_config` builds the litellm call with the wrong
    prefix and it fails at call time."""
    custom_provider = await _make_provider(
        db_session, provider_key="my_openai_compatible_llm", litellm_prefix="openai"
    )
    await _make_model(db_session, custom_provider, model_name="custom-prefix-model")

    registry_provider = await _make_provider(db_session, provider_key="anthropic")
    await _make_model(db_session, registry_provider, model_name="registry-model")

    await catalog.apply_admin_llm_configs(db_session)

    custom_entry = next(
        c
        for c in config.GLOBAL_LLM_CONFIGS
        if c.get("model_name") == "custom-prefix-model"
    )
    assert custom_entry["provider"] == "my_openai_compatible_llm"
    assert custom_entry["custom_provider"] == "openai"

    registry_entry = next(
        c for c in config.GLOBAL_LLM_CONFIGS if c.get("model_name") == "registry-model"
    )
    assert registry_entry["provider"] == "anthropic"
    assert registry_entry["custom_provider"] is None


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_replaces_only_previously_injected_entries(
    db_session: AsyncSession,
):
    static_entry = {"id": -1, "name": "Static YAML model", "provider": "openai"}
    openrouter_entry = {
        "id": -10001,
        "name": "OpenRouter model",
        "provider": "openrouter",
        "__openrouter_dynamic__": True,
    }
    config.GLOBAL_LLM_CONFIGS = [static_entry, openrouter_entry]

    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="first-call-model")

    applied_1 = await catalog.apply_admin_llm_configs(db_session)
    assert applied_1 == 1
    assert config.GLOBAL_LLM_CONFIGS.count(static_entry) == 1
    assert config.GLOBAL_LLM_CONFIGS.count(openrouter_entry) == 1
    admin_entries_1 = [
        c for c in config.GLOBAL_LLM_CONFIGS if c.get(catalog.ADMIN_DB_SOURCED_MARKER)
    ]
    assert len(admin_entries_1) == 1

    # Second call must not duplicate the static/OpenRouter entries, and must
    # replace (not append to) the previously-injected admin entry.
    applied_2 = await catalog.apply_admin_llm_configs(db_session)
    assert applied_2 == 1
    assert config.GLOBAL_LLM_CONFIGS.count(static_entry) == 1
    assert config.GLOBAL_LLM_CONFIGS.count(openrouter_entry) == 1
    admin_entries_2 = [
        c for c in config.GLOBAL_LLM_CONFIGS if c.get(catalog.ADMIN_DB_SOURCED_MARKER)
    ]
    assert len(admin_entries_2) == 1


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_rebuilds_derived_global_model_catalog(
    db_session: AsyncSession,
):
    """`config.GLOBAL_MODELS`/`GLOBAL_CONNECTIONS` are a *derived* projection
    of `GLOBAL_LLM_CONFIGS`, and they -- not `GLOBAL_LLM_CONFIGS` -- are what
    every authenticated-user consumer reads (the chat model loader in
    `llm_bundle.py`, `GET /global-model-connections`, Auto-mode pin
    candidates). Applying the admin catalog must rebuild them, or an
    admin-created model is invisible everywhere that matters until the
    process restarts."""
    provider = await _make_provider(db_session, provider_key="openai")
    model = await _make_model(db_session, provider, model_name="projected-model")

    await catalog.apply_admin_llm_configs(db_session)

    synthetic_id = -(catalog.SYNTHETIC_ID_OFFSET + model.id)
    projected = next(
        (m for m in config.GLOBAL_MODELS if m.get("id") == synthetic_id), None
    )
    assert projected is not None
    assert projected["model_id"] == "projected-model"
    assert projected["supports_chat"] is True

    connection = next(
        (
            c
            for c in config.GLOBAL_CONNECTIONS
            if c.get("id") == projected.get("connection_id")
        ),
        None,
    )
    assert connection is not None
    assert connection["provider"] == "openai"


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_rebuilds_projection_on_every_apply(
    db_session: AsyncSession,
):
    """The projection must be rebuilt on *every* apply, not just the first.
    A runtime mutation through the dashboard (create, update, delete, or the
    reload endpoint) re-applies the catalog, and a stale projection is
    exactly the bug that made an admin-disabled model still reachable and an
    admin-created model still missing."""
    provider = await _make_provider(db_session, provider_key="openai")
    model = await _make_model(db_session, provider, model_name="churn-model")
    synthetic_id = -(catalog.SYNTHETIC_ID_OFFSET + model.id)

    await catalog.apply_admin_llm_configs(db_session)
    assert any(m.get("id") == synthetic_id for m in config.GLOBAL_MODELS)

    # Disable the model and re-apply: the projection must drop it too.
    model.is_enabled = False
    await db_session.flush()
    await catalog.apply_admin_llm_configs(db_session)
    assert not any(m.get("id") == synthetic_id for m in config.GLOBAL_MODELS)

    # Re-enable and re-apply: it must come back.
    model.is_enabled = True
    await db_session.flush()
    await catalog.apply_admin_llm_configs(db_session)
    assert any(m.get("id") == synthetic_id for m in config.GLOBAL_MODELS)


@pytest.mark.asyncio
async def test_admin_model_is_resolvable_by_the_authenticated_chat_loader(
    db_session: AsyncSession,
):
    """End-to-end for the actual consumer named in the finding: after the
    admin catalog is applied, `load_llm_bundle` (the authenticated chat model
    loader) must be able to resolve the new model's synthetic negative config
    id into a working LLM + AgentConfig."""
    from app.db import Workspace
    from app.tasks.chat.streaming.flows.shared.free_quota import needs_free_quota
    from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle

    ciphertext = TokenEncryption(config.SECRET_KEY).encrypt_token("sk-loader-key")
    provider = await _make_provider(
        db_session, provider_key="openai", api_key_encrypted=ciphertext
    )
    model = await _make_model(
        db_session, provider, model_name="loadable-model", billing_tier="free"
    )

    user = await _make_user(db_session)
    workspace = Workspace(name=f"WS {uuid.uuid4().hex[:8]}", user_id=user.id)
    db_session.add(workspace)
    await db_session.flush()

    await catalog.apply_admin_llm_configs(db_session)

    synthetic_id = -(catalog.SYNTHETIC_ID_OFFSET + model.id)
    llm, agent_config, error = await load_llm_bundle(
        db_session, config_id=synthetic_id, workspace_id=workspace.id
    )

    assert error is None
    assert llm is not None
    assert agent_config is not None
    assert agent_config.config_id == synthetic_id
    assert agent_config.model_name == "loadable-model"
    # An admin-created *free* model is platform-funded, so it must still be
    # charged against the free-tier caps (the other half of the BYOK fix in
    # `needs_free_quota`: negative ids stay capped, positive BYOK ids don't).
    assert needs_free_quota(agent_config, str(user.id)) is True


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_reregisters_litellm_pricing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Without this, a newly created admin *premium* model has no LiteLLM
    cost entry until the next restart, so its real provider cost is never
    billed. Mirrors `openrouter_integration_service.refresh`."""
    import app.services.pricing_registration as pricing

    calls: list[int] = []
    monkeypatch.setattr(
        pricing, "register_pricing_from_global_configs", lambda: calls.append(1)
    )

    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="priced-model")

    await catalog.apply_admin_llm_configs(db_session)

    assert calls == [1]


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_rebuilds_router_when_already_initialized(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A model disabled or deleted through the dashboard must stop being
    reachable through the Auto-mode/router-pool flows immediately, not only
    after a restart."""
    from app.services import llm_router_service as router_module

    rebuilt: list[list[dict]] = []
    monkeypatch.setattr(
        router_module.LLMRouterService,
        "rebuild",
        classmethod(lambda cls, configs, settings=None: rebuilt.append(configs)),
    )
    monkeypatch.setattr(
        router_module.LLMRouterService.get_instance(), "_initialized", True
    )
    router_module._router_instance_cache[True] = object()  # type: ignore[assignment]

    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="routed-model")

    await catalog.apply_admin_llm_configs(db_session)

    assert len(rebuilt) == 1
    assert any(c.get("model_name") == "routed-model" for c in rebuilt[0])
    # The per-chat router instance cache built off the previous catalog must
    # be dropped too, or in-flight flows keep the stale router.
    assert router_module._router_instance_cache == {}


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_does_not_rebuild_router_before_startup_init(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Boot ordering guard. `lifespan` applies the admin catalog *before*
    `initialize_openrouter_integration()` / `initialize_llm_router()`, and
    `LLMRouterService.initialize` short-circuits once `_initialized` is set.
    Rebuilding here at boot would claim that one-shot init against a config
    list with no OpenRouter models in it yet and make startup's own
    `initialize_llm_router()` a no-op, silently dropping OpenRouter premium
    deployments from the router pool for the whole process lifetime."""
    from app.services import llm_router_service as router_module

    rebuilt: list[list[dict]] = []
    monkeypatch.setattr(
        router_module.LLMRouterService,
        "rebuild",
        classmethod(lambda cls, configs, settings=None: rebuilt.append(configs)),
    )
    monkeypatch.setattr(
        router_module.LLMRouterService.get_instance(), "_initialized", False
    )

    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="boot-model")

    applied = await catalog.apply_admin_llm_configs(db_session)

    assert applied == 1
    assert rebuilt == []
    # The catalog itself still applied, including the derived projection.
    assert any(c.get("model_name") == "boot-model" for c in config.GLOBAL_LLM_CONFIGS)


@pytest.mark.asyncio
async def test_apply_admin_llm_configs_decrypts_provider_api_key(
    db_session: AsyncSession,
):
    plaintext = "sk-super-secret-key"
    ciphertext = TokenEncryption(config.SECRET_KEY).encrypt_token(plaintext)
    provider = await _make_provider(db_session, api_key_encrypted=ciphertext)
    await _make_model(db_session, provider, model_name="keyed-model")

    await catalog.apply_admin_llm_configs(db_session)

    entry = next(
        c for c in config.GLOBAL_LLM_CONFIGS if c.get("model_name") == "keyed-model"
    )
    assert entry["api_key"] == plaintext


# ---------------------------------------------------------------------------
# app.routes.admin.admin_llm_routes -- providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_providers_requires_llm_providers_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.list_llm_providers(session=db_session, auth=_auth(user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_provider_requires_llm_providers_write(db_session: AsyncSession):
    user = await _make_admin(db_session, permissions=["llm_providers:read"])
    with pytest.raises(HTTPException) as exc:
        await routes.create_llm_provider(
            AdminLLMProviderCreate(
                provider_key="openai",
                display_name="OpenAI",
                transport="native",
                auth_style="bearer",
            ),
            request=_fake_request(),
            session=db_session,
            auth=_auth(user),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_provider_encrypts_api_key_and_masks_in_list(
    db_session: AsyncSession,
):
    admin = await _make_admin(
        db_session, permissions=["llm_providers:read", "llm_providers:write"]
    )
    plaintext = "sk-test-abcdef"

    created = await routes.create_llm_provider(
        AdminLLMProviderCreate(
            provider_key="openai_test",
            display_name="OpenAI Test",
            transport="native",
            auth_style="bearer",
            api_key=plaintext,
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert created.has_api_key is True
    assert not hasattr(created, "api_key")
    assert not hasattr(created, "api_key_encrypted")

    row = (
        (
            await db_session.execute(
                select(AdminLLMProvider).filter(AdminLLMProvider.id == created.id)
            )
        )
        .scalars()
        .first()
    )
    assert row.api_key_encrypted is not None
    assert row.api_key_encrypted != plaintext
    assert plaintext not in row.api_key_encrypted

    listed = await routes.list_llm_providers(session=db_session, auth=_auth(admin))
    entry = next(p for p in listed if p.id == created.id)
    assert entry.has_api_key is True
    assert plaintext not in str(entry.model_dump())

    create_audit = await _audit_rows(
        db_session, action="admin_llm_provider.create", target_id=str(created.id)
    )
    assert len(create_audit) == 1
    assert "api_key" not in create_audit[0].after
    assert "api_key_encrypted" not in create_audit[0].after
    assert plaintext not in str(create_audit[0].after)


@pytest.mark.asyncio
async def test_reveal_provider_api_key_round_trip_and_audit(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    plaintext = "sk-reveal-me"
    created = await routes.create_llm_provider(
        AdminLLMProviderCreate(
            provider_key="reveal_test",
            display_name="Reveal Test",
            transport="native",
            auth_style="bearer",
            api_key=plaintext,
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    revealed = await routes.reveal_llm_provider_api_key(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert revealed.api_key == plaintext

    reveal_audit = await _audit_rows(
        db_session, action="admin_llm_provider.reveal", target_id=str(created.id)
    )
    assert len(reveal_audit) == 1


@pytest.mark.asyncio
async def test_reveal_provider_with_no_key_set_returns_none(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)

    revealed = await routes.reveal_llm_provider_api_key(
        provider.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert revealed.api_key is None


@pytest.mark.asyncio
async def test_update_provider_partial_updates_and_replaces_api_key(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    created = await routes.create_llm_provider(
        AdminLLMProviderCreate(
            provider_key="update_test",
            display_name="Before",
            transport="native",
            auth_style="bearer",
            api_key="sk-old-key",
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    updated = await routes.update_llm_provider(
        created.id,
        AdminLLMProviderUpdate(
            display_name="After", is_enabled=False, api_key="sk-new-key"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.display_name == "After"
    assert updated.is_enabled is False
    assert updated.provider_key == "update_test"  # untouched field preserved
    assert updated.has_api_key is True

    revealed = await routes.reveal_llm_provider_api_key(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert revealed.api_key == "sk-new-key"

    update_audit = await _audit_rows(
        db_session, action="admin_llm_provider.update", target_id=str(created.id)
    )
    assert len(update_audit) == 1
    assert update_audit[0].before["display_name"] == "Before"
    assert update_audit[0].after["display_name"] == "After"
    assert "api_key" not in update_audit[0].after
    assert "sk-new-key" not in str(update_audit[0].after)


@pytest.mark.asyncio
async def test_delete_provider_cascades_to_its_models_and_audits(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    model = await _make_model(db_session, provider)

    await routes.delete_llm_provider(
        provider.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    provider_row = (
        (
            await db_session.execute(
                select(AdminLLMProvider).filter(AdminLLMProvider.id == provider.id)
            )
        )
        .scalars()
        .first()
    )
    assert provider_row is None

    model_row = (
        (
            await db_session.execute(
                select(AdminLLMModel).filter(AdminLLMModel.id == model.id)
            )
        )
        .scalars()
        .first()
    )
    assert model_row is None

    delete_audit = await _audit_rows(
        db_session, action="admin_llm_provider.delete", target_id=str(provider.id)
    )
    assert len(delete_audit) == 1


# ---------------------------------------------------------------------------
# app.routes.admin.admin_llm_routes -- live model discovery (Phase C Track 4)
# ---------------------------------------------------------------------------


class _StubDiscoveryResponse:
    """Minimal drop-in for an ``httpx.Response`` used by the discovery HTTP
    calls in ``model_connection_service``."""

    def __init__(self, *, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self
            )

    def json(self) -> dict:
        return self._payload


class _StubDiscoveryAsyncClient:
    """Minimal drop-in for ``httpx.AsyncClient`` so discovery tests never make
    a real network call. ``responder`` is called with (url, headers) and must
    return a ``_StubDiscoveryResponse`` or raise an ``httpx.HTTPError``."""

    def __init__(self, responder):
        self._responder = responder
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict | None = None):
        headers = headers or {}
        self.calls.append((url, headers))
        return self._responder(url, headers)


def _patch_discovery_async_client(monkeypatch, responder) -> _StubDiscoveryAsyncClient:
    client = _StubDiscoveryAsyncClient(responder)
    monkeypatch.setattr(
        "app.services.model_connection_service.httpx.AsyncClient",
        lambda *args, **kwargs: client,
    )
    return client


@pytest.mark.asyncio
async def test_discover_models_requires_llm_providers_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    provider = await _make_provider(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.discover_llm_provider_models(
            provider.id, session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_discover_models_unknown_provider_404(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    with pytest.raises(HTTPException) as exc:
        await routes.discover_llm_provider_models(
            999_999, session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_discover_models_static_provider_returns_list_without_network_call(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A `static`-discovery provider (e.g. gemini) reads LiteLLM's own
    bundled cost map -- it must return a non-error, non-empty list and must
    never construct an `httpx.AsyncClient` at all."""
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    provider = await _make_provider(db_session, provider_key="gemini")

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("static discovery must not make a network call")

    monkeypatch.setattr(
        "app.services.model_connection_service.httpx.AsyncClient", _fail_if_called
    )

    result = await routes.discover_llm_provider_models(
        provider.id, session=db_session, auth=_auth(admin)
    )

    assert len(result) > 0
    assert all(item.model_id for item in result)


@pytest.mark.asyncio
async def test_discover_models_none_discovery_kind_returns_empty_list(
    db_session: AsyncSession,
):
    """A provider whose registry entry has no discovery mechanism at all
    (`discovery: "none"`, e.g. `openai_compatible_raw`) is a valid, non-error
    empty response -- not something this route special-cases."""
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    provider = await _make_provider(db_session, provider_key="openai_compatible_raw")

    result = await routes.discover_llm_provider_models(
        provider.id, session=db_session, auth=_auth(admin)
    )

    assert result == []


@pytest.mark.asyncio
async def test_discover_models_with_no_stored_api_key_still_attempts_discovery(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A provider with no API key stored (`has_api_key=False`) must not be
    rejected up front -- some discovery kinds work unauthenticated. The route
    lets `discover_models` attempt the call and surface whatever it returns,
    here an empty result from a stubbed 200 response with no Authorization
    header sent."""
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    provider = await _make_provider(db_session, provider_key="openai")
    assert provider.api_key_encrypted is None

    client = _patch_discovery_async_client(
        monkeypatch,
        lambda url, headers: _StubDiscoveryResponse(payload={"data": []}),
    )

    result = await routes.discover_llm_provider_models(
        provider.id, session=db_session, auth=_auth(admin)
    )

    assert result == []
    assert len(client.calls) == 1
    _url, sent_headers = client.calls[0]
    assert "Authorization" not in sent_headers


@pytest.mark.asyncio
async def test_discover_models_network_failure_surfaces_as_400(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A genuine network/auth failure during discovery must come back as a
    400 with the error message, not a 500 -- mirrors
    `POST /model-connections/discover-preview`'s `ModelDiscoveryError`
    handling."""
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    provider = await _make_provider(db_session, provider_key="openai")

    def _raise_connect_error(url, headers):
        raise httpx.ConnectError("Connection refused")

    _patch_discovery_async_client(monkeypatch, _raise_connect_error)

    with pytest.raises(HTTPException) as exc:
        await routes.discover_llm_provider_models(
            provider.id, session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 400
    assert exc.value.detail


@pytest.mark.asyncio
async def test_discover_models_response_never_contains_api_key(
    db_session: AsyncSession,
):
    """The provider's decrypted API key is used server-side only to make the
    discovery call -- it must never appear anywhere in the response."""
    admin = await _make_admin(db_session, permissions=["llm_providers:read"])
    plaintext = "sk-should-never-leak"
    ciphertext = TokenEncryption(config.SECRET_KEY).encrypt_token(plaintext)
    provider = await _make_provider(
        db_session, provider_key="gemini", api_key_encrypted=ciphertext
    )

    result = await routes.discover_llm_provider_models(
        provider.id, session=db_session, auth=_auth(admin)
    )

    for item in result:
        assert not hasattr(item, "api_key")
        assert not hasattr(item, "api_key_encrypted")
    assert plaintext not in str([item.model_dump() for item in result])


# ---------------------------------------------------------------------------
# app.routes.admin.admin_llm_routes -- models
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models_requires_llm_providers_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.list_llm_models(
            provider_id=None, session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_model_requires_llm_providers_write(db_session: AsyncSession):
    user = await _make_admin(db_session, permissions=["llm_providers:read"])
    provider = await _make_provider(db_session)
    with pytest.raises(HTTPException) as exc:
        await routes.create_llm_model(
            AdminLLMModelCreate(provider_id=provider.id, name="X", model_name="x"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(user),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_model_and_list_filters_by_provider(db_session: AsyncSession):
    admin = await _make_admin(
        db_session, permissions=["llm_providers:read", "llm_providers:write"]
    )
    provider_a = await _make_provider(db_session)
    provider_b = await _make_provider(db_session)

    created = await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider_a.id, name="Model A", model_name="model-a"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider_b.id, name="Model B", model_name="model-b"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    create_audit = await _audit_rows(
        db_session, action="admin_llm_model.create", target_id=str(created.id)
    )
    assert len(create_audit) == 1

    filtered = await routes.list_llm_models(
        provider_id=provider_a.id, session=db_session, auth=_auth(admin)
    )
    assert {m.model_name for m in filtered} == {"model-a"}


@pytest.mark.asyncio
async def test_create_model_rejects_unknown_provider(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    with pytest.raises(HTTPException) as exc:
        await routes.create_llm_model(
            AdminLLMModelCreate(provider_id=999_999, name="X", model_name="x"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_model_rejects_duplicate_provider_model_name(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider.id, name="First", model_name="dup-model"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    with pytest.raises(HTTPException) as exc:
        await routes.create_llm_model(
            AdminLLMModelCreate(
                provider_id=provider.id, name="Second", model_name="dup-model"
            ),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_and_delete_model_round_trip_with_audit(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    created = await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider.id, name="Before", model_name="model-x"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    updated = await routes.update_llm_model(
        created.id,
        AdminLLMModelUpdate(name="After", is_enabled=False),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.name == "After"
    assert updated.is_enabled is False
    assert updated.model_name == "model-x"  # untouched field preserved

    update_audit = await _audit_rows(
        db_session, action="admin_llm_model.update", target_id=str(created.id)
    )
    assert len(update_audit) == 1
    assert update_audit[0].before["name"] == "Before"
    assert update_audit[0].after["name"] == "After"

    await routes.delete_llm_model(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    delete_audit = await _audit_rows(
        db_session, action="admin_llm_model.delete", target_id=str(created.id)
    )
    assert len(delete_audit) == 1

    row = (
        (
            await db_session.execute(
                select(AdminLLMModel).filter(AdminLLMModel.id == created.id)
            )
        )
        .scalars()
        .first()
    )
    assert row is None


@pytest.mark.asyncio
async def test_update_model_audit_row_captures_every_mutable_field(
    db_session: AsyncSession,
):
    """The audit row for a model update must show what actually changed for
    every mutable field, not just the ~10 headline ones -- pricing/behavior
    fields like litellm_params, system_instructions, rpm, and tpm are exactly
    the fields a compliance/security review of the audit log needs visible."""
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    created = await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider.id,
            name="Pricing Test",
            model_name="pricing-model",
            rpm=10,
            tpm=1000,
            litellm_params={"input_cost_per_token": 0.000001},
            system_instructions="Old instructions.",
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    await routes.update_llm_model(
        created.id,
        AdminLLMModelUpdate(
            rpm=500,
            tpm=50_000,
            litellm_params={"input_cost_per_token": 0.000009},
            system_instructions="New instructions.",
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    update_audit = await _audit_rows(
        db_session, action="admin_llm_model.update", target_id=str(created.id)
    )
    assert len(update_audit) == 1
    before, after = update_audit[0].before, update_audit[0].after

    assert before["rpm"] == 10
    assert after["rpm"] == 500
    assert before["tpm"] == 1000
    assert after["tpm"] == 50_000
    assert before["litellm_params"] == {"input_cost_per_token": 0.000001}
    assert after["litellm_params"] == {"input_cost_per_token": 0.000009}
    assert before["system_instructions"] == "Old instructions."
    assert after["system_instructions"] == "New instructions."


@pytest.mark.asyncio
async def test_mutations_reapply_catalog_live(db_session: AsyncSession):
    """Creating an enabled model immediately shows up in
    `config.GLOBAL_LLM_CONFIGS` without a separate reload call, and deleting
    it removes it again -- the automatic re-apply-on-every-mutation."""
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)

    created = await routes.create_llm_model(
        AdminLLMModelCreate(
            provider_id=provider.id, name="Live", model_name="live-model"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    assert any(c.get("model_name") == "live-model" for c in config.GLOBAL_LLM_CONFIGS)
    # ...and in the derived projection the model picker / chat loader read.
    synthetic_id = -(catalog.SYNTHETIC_ID_OFFSET + created.id)
    assert any(m.get("id") == synthetic_id for m in config.GLOBAL_MODELS)

    await routes.delete_llm_model(
        created.id, request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    assert not any(
        c.get("model_name") == "live-model" for c in config.GLOBAL_LLM_CONFIGS
    )
    assert not any(m.get("id") == synthetic_id for m in config.GLOBAL_MODELS)


@pytest.mark.asyncio
async def test_reload_endpoint_requires_llm_providers_write(db_session: AsyncSession):
    user = await _make_admin(db_session, permissions=["llm_providers:read"])
    with pytest.raises(HTTPException) as exc:
        await routes.reload_llm_catalog(
            request=_fake_request(), session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reload_endpoint_returns_applied_count(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="reload-model")

    result = await routes.reload_llm_catalog(
        request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert result.applied_count >= 1


@pytest.mark.asyncio
async def test_reload_endpoint_writes_audit_row(db_session: AsyncSession):
    """The reload endpoint mutates live process state (it can swap the whole
    model catalog under in-flight traffic) and is `llm_providers:write`-gated,
    so it must be audited like every other write endpoint in this dashboard --
    even the read-only reveal endpoint is."""
    admin = await _make_admin(db_session, permissions=["llm_providers:write"])
    provider = await _make_provider(db_session)
    await _make_model(db_session, provider, model_name="audited-reload-model")

    result = await routes.reload_llm_catalog(
        request=_fake_request(), session=db_session, auth=_auth(admin)
    )

    rows = (
        (
            await db_session.execute(
                select(AdminAuditLog).filter(
                    AdminAuditLog.action == "admin_llm_catalog.reload"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].target_type == "admin_llm_catalog"
    assert rows[0].target_id is None
    assert rows[0].after == {"applied_count": result.applied_count}
    assert rows[0].actor_user_id == admin.id
