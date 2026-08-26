"""Integration tests for the super admin connector credentials vault (Phase D
of the super admin dashboard): `app.services.admin_connector_credentials_service`
and `app.routes.admin.admin_connector_credentials_routes`.

Route handlers are called directly (session + AuthContext passed in), the
same pattern used by `tests/integration/test_admin_settings.py` (Phase B)
and `tests/integration/test_admin_rbac.py` (Phase A), rather than spinning up
an ASGI test client. This file has no shared fixture module to import the
`_auth`/`_fake_request`/`_make_user`/`_make_admin` helpers from, so they're
duplicated here, same as Phase B's own file does.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.context import AuthContext
from app.config import config
from app.config.connector_credentials_registry import CONNECTOR_CREDENTIALS_REGISTRY
from app.db import (
    AdminAuditLog,
    AdminConnectorCredential,
    PlatformRole,
    PlatformRoleAssignment,
    User,
)
from app.routes.admin import admin_connector_credentials_routes
from app.schemas import AdminConnectorCredentialUpdate
from app.services import admin_connector_credentials_service as vault

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


@pytest_asyncio.fixture(autouse=True)
async def _isolate_config_overrides():
    """Guard against `set_connector_credential`/`delete_connector_credential`'s
    live setattr/delattr calls leaking instance-level `config` state across
    tests -- `config` is a process-wide singleton, not something
    `db_session`'s transaction rollback can undo."""
    before = dict(vars(config))
    yield
    for k in list(vars(config).keys()):
        if k not in before:
            delattr(config, k)
    for k, v in before.items():
        if getattr(config, k, object()) is not v and getattr(config, k, object()) != v:
            setattr(config, k, v)


async def _audit_rows(
    session: AsyncSession, *, action: str, target_id: str
) -> list[AdminAuditLog]:
    result = await session.execute(
        select(AdminAuditLog).filter(
            AdminAuditLog.action == action, AdminAuditLog.target_id == target_id
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# app.services.admin_connector_credentials_service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_all_registry_connectors_with_zero_rows(
    db_session: AsyncSession,
):
    snapshots = await vault.list_connector_credentials(db_session)

    assert len(snapshots) == len(CONNECTOR_CREDENTIALS_REGISTRY) == 13
    keys = {s.connector_key for s in snapshots}
    assert keys == set(CONNECTOR_CREDENTIALS_REGISTRY.keys())
    for s in snapshots:
        assert s.has_override is False
        assert s.has_client_id is False
        assert s.has_client_secret is False


@pytest.mark.asyncio
async def test_get_connector_credential_rejects_unknown_key(db_session: AsyncSession):
    with pytest.raises(KeyError):
        await vault.get_connector_credential(db_session, "not_a_real_connector")


@pytest.mark.asyncio
async def test_set_connector_credential_creates_row_and_applies_live(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    original_client_id = config.SLACK_CLIENT_ID
    original_client_secret = config.SLACK_CLIENT_SECRET

    snapshot = await vault.set_connector_credential(
        db_session,
        "slack",
        client_id="new-client-id",
        client_secret="new-client-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    assert snapshot.has_override is True
    assert snapshot.has_client_id is True
    assert snapshot.has_client_secret is True
    assert snapshot.is_enabled is True

    # Live-applied without needing load_all_connector_credential_overrides_and_apply.
    assert config.SLACK_CLIENT_ID == "new-client-id"
    assert config.SLACK_CLIENT_SECRET == "new-client-secret"
    assert original_client_id != config.SLACK_CLIENT_ID
    assert original_client_secret != config.SLACK_CLIENT_SECRET

    # Audit row: booleans only, never plaintext/ciphertext.
    rows = await _audit_rows(
        db_session, action="admin_connector_credential.update", target_id="slack"
    )
    assert len(rows) == 1
    assert rows[0].before is None
    assert rows[0].after == {
        "has_client_id": True,
        "has_client_secret": True,
        "is_enabled": True,
    }
    for row in rows:
        assert "new-client-id" not in str(row.after)
        assert "new-client-secret" not in str(row.after)


@pytest.mark.asyncio
async def test_partial_update_leaves_omitted_field_untouched(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    await vault.set_connector_credential(
        db_session,
        "notion",
        client_id="original-client-id",
        client_secret="original-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    # Only client_secret present in this second call -- client_id must survive.
    snapshot = await vault.set_connector_credential(
        db_session,
        "notion",
        client_id=None,
        client_secret="rotated-secret",
        is_enabled=None,
        client_id_set=False,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    assert snapshot.has_client_id is True
    assert snapshot.has_client_secret is True

    revealed = await vault.reveal_connector_credential(
        db_session, "notion", actor_user_id=admin.id
    )
    assert revealed["client_id"] == "original-client-id"
    assert revealed["client_secret"] == "rotated-secret"


@pytest.mark.asyncio
async def test_explicit_null_clears_previously_stored_secret(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    original_client_secret = config.LINEAR_CLIENT_SECRET

    await vault.set_connector_credential(
        db_session,
        "linear",
        client_id="linear-client-id",
        client_secret="linear-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    assert config.LINEAR_CLIENT_SECRET == "linear-secret"

    snapshot = await vault.set_connector_credential(
        db_session,
        "linear",
        client_id=None,
        client_secret=None,
        is_enabled=None,
        client_id_set=False,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    assert snapshot.has_client_secret is False
    assert snapshot.has_client_id is True  # untouched, still set

    row = await vault._get_row(db_session, "linear")
    assert row.client_secret_encrypted is None

    # The live Config attribute must actually revert to the class default,
    # not just the DB row/snapshot -- this was the Critical review finding:
    # explicit-null clears used to leave the live value stuck at the stale
    # secret indefinitely.
    assert original_client_secret == config.LINEAR_CLIENT_SECRET
    assert config.LINEAR_CLIENT_SECRET != "linear-secret"
    # The still-stored client_id is untouched by this call and must remain
    # live-applied -- clearing is reconciled per-attribute, not as a
    # blanket suspend of the whole connector.
    assert config.LINEAR_CLIENT_ID == "linear-client-id"


@pytest.mark.asyncio
async def test_reenable_without_resubmitting_credentials_restores_live_value(
    db_session: AsyncSession,
):
    """Re-enabling a suspended connector with no client_id/client_secret in
    the request body must reapply the still-stored ciphertext live, not
    leave the Config attributes stuck at the class default -- the Important
    review finding on the same root cause as the explicit-null-clear bug
    above (live-apply must be driven by the row's persisted state, never by
    this call's raw request parameters)."""
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    original_client_id = config.ATLASSIAN_CLIENT_ID
    original_client_secret = config.ATLASSIAN_CLIENT_SECRET

    await vault.set_connector_credential(
        db_session,
        "atlassian",
        client_id="atlassian-client-id",
        client_secret="atlassian-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    assert config.ATLASSIAN_CLIENT_ID == "atlassian-client-id"
    assert config.ATLASSIAN_CLIENT_SECRET == "atlassian-secret"

    # Suspend it live.
    await vault.set_connector_credential(
        db_session,
        "atlassian",
        client_id=None,
        client_secret=None,
        is_enabled=False,
        client_id_set=False,
        client_secret_set=False,
        is_enabled_set=True,
        updated_by_id=admin.id,
    )
    assert original_client_id == config.ATLASSIAN_CLIENT_ID
    assert original_client_secret == config.ATLASSIAN_CLIENT_SECRET

    # Re-enable with a bare {"is_enabled": true} -- no credentials resubmitted.
    snapshot = await vault.set_connector_credential(
        db_session,
        "atlassian",
        client_id=None,
        client_secret=None,
        is_enabled=True,
        client_id_set=False,
        client_secret_set=False,
        is_enabled_set=True,
        updated_by_id=admin.id,
    )

    assert snapshot.is_enabled is True
    assert snapshot.has_client_id is True
    assert snapshot.has_client_secret is True
    # The previously stored (still-persisted) credentials are what's live now,
    # not the class default.
    assert config.ATLASSIAN_CLIENT_ID == "atlassian-client-id"
    assert config.ATLASSIAN_CLIENT_SECRET == "atlassian-secret"


@pytest.mark.asyncio
async def test_composio_client_id_rejected(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    with pytest.raises(ValueError):
        await vault.set_connector_credential(
            db_session,
            "composio",
            client_id="should-not-be-allowed",
            client_secret=None,
            is_enabled=None,
            client_id_set=True,
            client_secret_set=False,
            is_enabled_set=False,
            updated_by_id=admin.id,
        )


@pytest.mark.asyncio
async def test_set_connector_credential_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    with pytest.raises(KeyError):
        await vault.set_connector_credential(
            db_session,
            "not_a_real_connector",
            client_id="x",
            client_secret="y",
            is_enabled=None,
            client_id_set=True,
            client_secret_set=True,
            is_enabled_set=False,
            updated_by_id=admin.id,
        )


@pytest.mark.asyncio
async def test_is_enabled_false_restores_default_live(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    original_client_id = config.DISCORD_CLIENT_ID
    original_client_secret = config.DISCORD_CLIENT_SECRET

    await vault.set_connector_credential(
        db_session,
        "discord",
        client_id="discord-client-id",
        client_secret="discord-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    assert config.DISCORD_CLIENT_ID == "discord-client-id"
    assert config.DISCORD_CLIENT_SECRET == "discord-secret"

    snapshot = await vault.set_connector_credential(
        db_session,
        "discord",
        client_id=None,
        client_secret=None,
        is_enabled=False,
        client_id_set=False,
        client_secret_set=False,
        is_enabled_set=True,
        updated_by_id=admin.id,
    )

    assert snapshot.is_enabled is False
    # The stored row still has the override -- only the live value reverted.
    assert snapshot.has_client_id is True
    assert snapshot.has_client_secret is True
    # Live Config attributes are restored to the class default.
    assert original_client_id == config.DISCORD_CLIENT_ID
    assert original_client_secret == config.DISCORD_CLIENT_SECRET


@pytest.mark.asyncio
async def test_delete_connector_credential_removes_row_and_restores_default(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    original_client_id = config.CLICKUP_CLIENT_ID
    original_client_secret = config.CLICKUP_CLIENT_SECRET

    await vault.set_connector_credential(
        db_session,
        "clickup",
        client_id="clickup-client-id",
        client_secret="clickup-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    assert config.CLICKUP_CLIENT_ID == "clickup-client-id"

    snapshot = await vault.delete_connector_credential(
        db_session, "clickup", actor_user_id=admin.id
    )

    assert snapshot.has_override is False
    assert snapshot.has_client_id is False
    assert snapshot.has_client_secret is False
    assert original_client_id == config.CLICKUP_CLIENT_ID
    assert original_client_secret == config.CLICKUP_CLIENT_SECRET

    row = await vault._get_row(db_session, "clickup")
    assert row is None


@pytest.mark.asyncio
async def test_delete_connector_credential_rejects_unknown_key(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(KeyError):
        await vault.delete_connector_credential(
            db_session, "not_a_real_connector", actor_user_id=admin.id
        )


@pytest.mark.asyncio
async def test_reveal_connector_credential_returns_plaintext_and_audits_separately(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    await vault.set_connector_credential(
        db_session,
        "airtable",
        client_id="airtable-client-id",
        client_secret="airtable-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    revealed = await vault.reveal_connector_credential(
        db_session, "airtable", actor_user_id=admin.id
    )
    assert revealed == {
        "client_id": "airtable-client-id",
        "client_secret": "airtable-secret",
    }

    update_rows = await _audit_rows(
        db_session, action="admin_connector_credential.update", target_id="airtable"
    )
    reveal_rows = await _audit_rows(
        db_session, action="admin_connector_credential.reveal", target_id="airtable"
    )
    assert len(update_rows) == 1
    assert len(reveal_rows) == 1


@pytest.mark.asyncio
async def test_reveal_connector_credential_rejects_unknown_key(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(KeyError):
        await vault.reveal_connector_credential(
            db_session, "not_a_real_connector", actor_user_id=admin.id
        )


@pytest.mark.asyncio
async def test_load_all_overrides_and_apply_skips_disabled_rows(
    db_session: AsyncSession,
):
    admin = await _make_user(db_session)
    original_dropbox_key = config.DROPBOX_APP_KEY
    original_dropbox_secret = config.DROPBOX_APP_SECRET
    original_atlassian_id = config.ATLASSIAN_CLIENT_ID
    original_atlassian_secret = config.ATLASSIAN_CLIENT_SECRET

    enabled_row = AdminConnectorCredential(
        connector_key="dropbox",
        client_id_encrypted=vault.TokenEncryption(config.SECRET_KEY).encrypt_token(
            "dropbox-key"
        ),
        client_secret_encrypted=vault.TokenEncryption(config.SECRET_KEY).encrypt_token(
            "dropbox-secret"
        ),
        is_enabled=True,
        updated_by_id=admin.id,
    )
    disabled_row = AdminConnectorCredential(
        connector_key="atlassian",
        client_id_encrypted=vault.TokenEncryption(config.SECRET_KEY).encrypt_token(
            "atlassian-id"
        ),
        client_secret_encrypted=vault.TokenEncryption(config.SECRET_KEY).encrypt_token(
            "atlassian-secret"
        ),
        is_enabled=False,
        updated_by_id=admin.id,
    )
    db_session.add_all([enabled_row, disabled_row])
    await db_session.flush()

    applied = await vault.load_all_connector_credential_overrides_and_apply(db_session)

    assert applied == 1
    assert config.DROPBOX_APP_KEY == "dropbox-key"
    assert config.DROPBOX_APP_SECRET == "dropbox-secret"
    # Disabled row must NOT be applied live.
    assert original_atlassian_id == config.ATLASSIAN_CLIENT_ID
    assert original_atlassian_secret == config.ATLASSIAN_CLIENT_SECRET

    assert original_dropbox_key != config.DROPBOX_APP_KEY
    assert original_dropbox_secret != config.DROPBOX_APP_SECRET


# ---------------------------------------------------------------------------
# app.routes.admin.admin_connector_credentials_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_route_requires_connectors_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.list_connector_credentials(
            session=db_session, auth=_auth(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_read_only_admin_can_list_but_not_mutate(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:read"])

    result = await admin_connector_credentials_routes.list_connector_credentials(
        session=db_session, auth=_auth(admin)
    )
    assert len(result.connectors) == 13

    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.update_connector_credential(
            "slack",
            AdminConnectorCredentialUpdate(client_secret="x"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.delete_connector_credential(
            "slack", request=_fake_request(), session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.reveal_connector_credential(
            "slack", request=_fake_request(), session=db_session, auth=_auth(admin)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_route_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.update_connector_credential(
            "not_a_real_connector",
            AdminConnectorCredentialUpdate(client_secret="x"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_route_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.delete_connector_credential(
            "not_a_real_connector",
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_reveal_route_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.reveal_connector_credential(
            "not_a_real_connector",
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_route_composio_client_id_returns_400(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_connector_credentials_routes.update_connector_credential(
            "composio",
            AdminConnectorCredentialUpdate(client_id="nope"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_and_delete_routes_round_trip_and_audit(db_session: AsyncSession):
    admin = await _make_admin(
        db_session, permissions=["connectors:write", "connectors:read"]
    )
    original_client_id = config.MICROSOFT_CLIENT_ID
    original_client_secret = config.MICROSOFT_CLIENT_SECRET

    updated = await admin_connector_credentials_routes.update_connector_credential(
        "microsoft",
        AdminConnectorCredentialUpdate(
            client_id="ms-client-id", client_secret="ms-secret"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.has_override is True
    assert updated.has_client_id is True
    assert updated.has_client_secret is True
    assert config.MICROSOFT_CLIENT_ID == "ms-client-id"
    assert config.MICROSOFT_CLIENT_SECRET == "ms-secret"

    update_audit = await _audit_rows(
        db_session, action="admin_connector_credential.update", target_id="microsoft"
    )
    assert len(update_audit) == 1

    reverted = await admin_connector_credentials_routes.delete_connector_credential(
        "microsoft", request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert reverted.has_override is False
    assert original_client_id == config.MICROSOFT_CLIENT_ID
    assert original_client_secret == config.MICROSOFT_CLIENT_SECRET

    delete_audit = await _audit_rows(
        db_session, action="admin_connector_credential.delete", target_id="microsoft"
    )
    assert len(delete_audit) == 1


@pytest.mark.asyncio
async def test_reveal_route_returns_plaintext(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    await admin_connector_credentials_routes.update_connector_credential(
        "google",
        AdminConnectorCredentialUpdate(
            client_id="google-client-id", client_secret="google-secret"
        ),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    response = await admin_connector_credentials_routes.reveal_connector_credential(
        "google", request=_fake_request(), session=db_session, auth=_auth(admin)
    )
    assert response.connector_key == "google"
    assert response.client_id == "google-client-id"
    assert response.client_secret == "google-secret"


# ---------------------------------------------------------------------------
# has_default_client_id / has_default_client_secret (Config class defaults)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_flags_reflect_config_class_defaults(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A connector configured only through `.env` must not read as
    "(not set)" in the dashboard. The two `has_default_*` flags are derived
    from the `Config` *class* attributes, so they describe the environment
    rather than the override row."""
    config_cls = type(config)
    # "linear" has both env-derived values, "clickup" has neither, and
    # "airtable" has env vars that are present but empty (which reach Config
    # as "" and must not read as configured).
    monkeypatch.setattr(config_cls, "LINEAR_CLIENT_ID", "env-linear-id")
    monkeypatch.setattr(config_cls, "LINEAR_CLIENT_SECRET", "env-linear-secret")
    monkeypatch.setattr(config_cls, "CLICKUP_CLIENT_ID", None)
    monkeypatch.setattr(config_cls, "CLICKUP_CLIENT_SECRET", None)
    monkeypatch.setattr(config_cls, "AIRTABLE_CLIENT_ID", "")
    monkeypatch.setattr(config_cls, "AIRTABLE_CLIENT_SECRET", "")

    snapshots = {
        s.connector_key: s for s in await vault.list_connector_credentials(db_session)
    }

    linear = snapshots["linear"]
    assert linear.has_default_client_id is True
    assert linear.has_default_client_secret is True
    # No row exists, so the row-derived booleans stay False -- that pair and
    # the default pair answer different questions.
    assert linear.has_client_id is False
    assert linear.has_client_secret is False
    assert linear.has_override is False

    clickup = snapshots["clickup"]
    assert clickup.has_default_client_id is False
    assert clickup.has_default_client_secret is False

    airtable = snapshots["airtable"]
    assert airtable.has_default_client_id is False
    assert airtable.has_default_client_secret is False

    # Composio has no client_id concept at all.
    assert snapshots["composio"].has_default_client_id is False


@pytest.mark.asyncio
async def test_default_flags_unaffected_by_override_row(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Storing (and then clearing) an override must not change what the
    `has_default_*` flags report -- otherwise "cleared" would again be
    indistinguishable from "never configured"."""
    config_cls = type(config)
    monkeypatch.setattr(config_cls, "LINEAR_CLIENT_ID", "env-linear-id")
    monkeypatch.setattr(config_cls, "LINEAR_CLIENT_SECRET", "env-linear-secret")
    admin = await _make_user(db_session)

    stored = await vault.set_connector_credential(
        db_session,
        "linear",
        client_id="admin-linear-id",
        client_secret="admin-linear-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    assert stored.has_client_id is True
    assert stored.has_default_client_id is True
    assert stored.has_default_client_secret is True

    cleared = await vault.set_connector_credential(
        db_session,
        "linear",
        client_id=None,
        client_secret=None,
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    # Row still exists but both credentials are gone: the live effective
    # value has fallen back to the env default, and the snapshot says so.
    assert cleared.has_override is True
    assert cleared.has_client_id is False
    assert cleared.has_client_secret is False
    assert cleared.has_default_client_id is True
    assert cleared.has_default_client_secret is True


@pytest.mark.asyncio
async def test_read_route_exposes_default_flags(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["connectors:read"])

    result = (
        await admin_connector_credentials_routes.list_connector_credentials(
            session=db_session, auth=_auth(admin)
        )
    ).connectors

    entry = next(c for c in result if c.connector_key == "linear")
    assert entry.has_default_client_id == bool(
        CONNECTOR_CREDENTIALS_REGISTRY["linear"].default_client_id
    )
    assert entry.has_default_client_secret == bool(
        CONNECTOR_CREDENTIALS_REGISTRY["linear"].default_client_secret
    )


# ---------------------------------------------------------------------------
# Empty-payload PUT must not materialize an override row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_payload_does_not_create_override_row(db_session: AsyncSession):
    """Opening the edit dialog on an unconfigured connector and saving with
    no changes sends a body with zero fields set. That must stay a true
    no-op: no row, no audit entry, no "Updated ... by ..." in the UI."""
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    snapshot = await admin_connector_credentials_routes.update_connector_credential(
        "notion",
        AdminConnectorCredentialUpdate(),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    assert snapshot.has_override is False
    assert snapshot.updated_at is None
    assert snapshot.updated_by_id is None

    result = await db_session.execute(
        select(AdminConnectorCredential).filter(
            AdminConnectorCredential.connector_key == "notion"
        )
    )
    assert result.scalars().first() is None

    assert (
        await _audit_rows(
            db_session, action="admin_connector_credential.update", target_id="notion"
        )
        == []
    )


@pytest.mark.asyncio
async def test_empty_payload_leaves_existing_override_row_intact(
    db_session: AsyncSession,
):
    """The no-op guard is scoped to "no row exists"; an existing override row
    is still reachable by an empty payload and must survive it unchanged (no
    credential cleared as a side effect)."""
    admin = await _make_admin(db_session, permissions=["connectors:write"])

    await admin_connector_credentials_routes.update_connector_credential(
        "notion",
        AdminConnectorCredentialUpdate(client_id="n-id", client_secret="n-secret"),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    snapshot = await admin_connector_credentials_routes.update_connector_credential(
        "notion",
        AdminConnectorCredentialUpdate(),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )

    assert snapshot.has_override is True
    assert snapshot.has_client_id is True
    assert snapshot.has_client_secret is True
    assert config.NOTION_CLIENT_ID == "n-id"
    assert config.NOTION_CLIENT_SECRET == "n-secret"


# ---------------------------------------------------------------------------
# Celery worker bootstrap (app.celery_app)
# ---------------------------------------------------------------------------


class _StubSessionMaker:
    """Stand-in for `app.db.async_session_maker` that hands back this test's
    transactional session and never closes it, so the celery bootstrap helper
    (which opens its own session in production) can see rows seeded inside the
    test's rolled-back transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _StubSessionMaker:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_exc: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_celery_bootstrap_applies_both_vault_overrides(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A Celery worker process must end up with the same live `Config` as the
    FastAPI process: both the settings vault and the connector-credentials
    vault applied. Without this, background token refresh reads the class
    default for any credential an admin moved into the vault."""
    import app.celery_app as celery_app_module
    from app.services import settings_vault_service

    admin = await _make_user(db_session)

    await vault.set_connector_credential(
        db_session,
        "dropbox",
        client_id="vault-dropbox-key",
        client_secret="vault-dropbox-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )

    setting_default = int(
        settings_vault_service.SETTINGS_REGISTRY["ANON_MAX_CONCURRENT_STREAMS"].default
    )
    setting_override = setting_default + 9
    await settings_vault_service.set_setting(
        db_session,
        "ANON_MAX_CONCURRENT_STREAMS",
        setting_override,
        updated_by_id=admin.id,
    )

    # Simulate a fresh worker process: the DB rows survive, the live
    # instance-level overrides do not.
    delattr(config, "DROPBOX_APP_KEY")
    delattr(config, "DROPBOX_APP_SECRET")
    delattr(config, "ANON_MAX_CONCURRENT_STREAMS")
    assert config.DROPBOX_APP_KEY != "vault-dropbox-key"
    assert setting_default == config.ANON_MAX_CONCURRENT_STREAMS

    monkeypatch.setattr("app.db.async_session_maker", _StubSessionMaker(db_session))

    await celery_app_module._apply_admin_vault_overrides()

    assert config.DROPBOX_APP_KEY == "vault-dropbox-key"
    assert config.DROPBOX_APP_SECRET == "vault-dropbox-secret"
    assert setting_override == config.ANON_MAX_CONCURRENT_STREAMS


@pytest.mark.asyncio
async def test_celery_bootstrap_is_non_fatal_per_vault(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A settings-vault failure must not stop the connector-credentials vault
    from applying (and neither may take the worker down)."""
    import app.celery_app as celery_app_module
    from app.services import settings_vault_service

    admin = await _make_user(db_session)
    await vault.set_connector_credential(
        db_session,
        "dropbox",
        client_id="vault-dropbox-key",
        client_secret="vault-dropbox-secret",
        is_enabled=None,
        client_id_set=True,
        client_secret_set=True,
        is_enabled_set=False,
        updated_by_id=admin.id,
    )
    delattr(config, "DROPBOX_APP_KEY")
    delattr(config, "DROPBOX_APP_SECRET")

    async def _boom(_session):
        raise RuntimeError("settings vault exploded")

    monkeypatch.setattr(settings_vault_service, "load_all_overrides_and_apply", _boom)
    monkeypatch.setattr("app.db.async_session_maker", _StubSessionMaker(db_session))

    await celery_app_module._apply_admin_vault_overrides()

    assert config.DROPBOX_APP_KEY == "vault-dropbox-key"
    assert config.DROPBOX_APP_SECRET == "vault-dropbox-secret"


def test_init_worker_loads_admin_vault_overrides(monkeypatch: pytest.MonkeyPatch):
    """`init_worker` is the only place a worker process gets a chance to load
    the vaults, so assert the wiring itself exists (the helper's behaviour is
    covered by the two tests above). Everything else `init_worker` does is
    stubbed out -- this test is about the call, not about OTel or the
    routers."""
    import app.celery_app as celery_app_module
    import app.config as app_config_module
    import app.observability.bootstrap as otel_bootstrap
    import app.tasks.celery_tasks as celery_tasks_module

    ran: list[object] = []

    monkeypatch.setattr(otel_bootstrap, "init_otel", lambda **_kwargs: None)
    monkeypatch.setattr(
        celery_tasks_module,
        "run_async_celery_task",
        lambda factory: ran.append(factory),
    )
    for name in (
        "initialize_openrouter_integration",
        "initialize_pricing_registration",
        "initialize_llm_router",
        "initialize_image_gen_router",
    ):
        monkeypatch.setattr(app_config_module, name, lambda: None)

    celery_app_module.init_worker()

    assert ran == [celery_app_module._apply_admin_vault_overrides]
