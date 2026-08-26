"""Integration tests for the super admin settings/secrets vault (Phase B of
the super admin dashboard): `app.services.settings_vault_service` and
`app.routes.admin.admin_settings_routes`.

Route handlers are called directly (session + AuthContext passed in), the
same pattern used by `tests/integration/test_admin_rbac.py` (Phase A),
rather than spinning up an ASGI test client.

NOTE ON TEST LOCATION: the task brief for this phase suggested
`tests/unit/services/test_settings_vault_service.py`, but this suite
exercises real DB rows (admin_settings, admin_audit_logs) and the `unit`
pytest marker is reserved for "pure logic tests, no DB or external
services" (see `pyproject.toml`) -- the `db_session` fixture these tests
need only exists under `tests/integration/conftest.py`. Placed here instead,
mirroring where Phase A's actual RBAC/audit-log tests (which have the same
DB-dependency shape) live: `tests/integration/test_admin_rbac.py`.
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
from app.config.settings_registry import SETTINGS_REGISTRY, SettingDefinition
from app.db import AdminAuditLog, PlatformRole, PlatformRoleAssignment, User
from app.routes.admin import admin_settings_routes
from app.schemas import AdminSettingUpdate
from app.services import settings_vault_service as vault

pytestmark = pytest.mark.integration

_TEST_SECRET_KEY = "TEST_ADMIN_SETTINGS_SECRET"


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
    """Guard against `set_setting`/`delete_setting`'s live setattr/delattr
    calls leaking instance-level `config` state across tests -- `config` is
    a process-wide singleton, not something `db_session`'s transaction
    rollback can undo."""
    before = dict(vars(config))
    yield
    for k in list(vars(config).keys()):
        if k not in before:
            delattr(config, k)
    for k, v in before.items():
        if getattr(config, k, object()) is not v and getattr(config, k, object()) != v:
            setattr(config, k, v)


@pytest.fixture
def secret_setting_key(monkeypatch) -> str:
    """Registers a throwaway `is_secret=True` definition for the duration of
    one test. None of this phase's real curated settings are secrets (API
    keys/DATABASE_URL/SECRET_KEY are explicitly out of scope), so encryption
    round-trip / reveal-gating behavior is exercised against a synthetic key
    -- exactly the "synthetic setting key" case the migration docstring
    anticipates.
    """
    defn = SettingDefinition(
        key=_TEST_SECRET_KEY,
        value_type="string",
        category="test",
        is_secret=True,
        is_disruptive=False,
        description="Synthetic secret setting used only by tests.",
    )
    monkeypatch.setitem(SETTINGS_REGISTRY, _TEST_SECRET_KEY, defn)
    return _TEST_SECRET_KEY


async def _audit_rows(session: AsyncSession, *, action: str, target_id: str) -> list[AdminAuditLog]:
    result = await session.execute(
        select(AdminAuditLog).filter(
            AdminAuditLog.action == action, AdminAuditLog.target_id == target_id
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# app.services.settings_vault_service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_setting_mutates_live_config_not_just_db_row(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    original_default = int(vault.SETTINGS_REGISTRY["ANON_MAX_UPLOAD_SIZE_MB"].default)
    new_value = original_default + 123

    assert original_default == config.ANON_MAX_UPLOAD_SIZE_MB

    snapshot = await vault.set_setting(
        db_session, "ANON_MAX_UPLOAD_SIZE_MB", new_value, updated_by_id=admin.id
    )

    assert snapshot.value == new_value
    assert snapshot.has_override is True
    # The live singleton reflects the change immediately -- not just the DB row.
    assert new_value == config.ANON_MAX_UPLOAD_SIZE_MB


@pytest.mark.asyncio
async def test_revert_to_default_restores_config_class_default(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    original_default = int(vault.SETTINGS_REGISTRY["ANON_TOKEN_LIMIT"].default)
    new_value = original_default + 999

    await vault.set_setting(
        db_session, "ANON_TOKEN_LIMIT", new_value, updated_by_id=admin.id
    )
    assert new_value == config.ANON_TOKEN_LIMIT

    snapshot = await vault.delete_setting(
        db_session, "ANON_TOKEN_LIMIT", actor_user_id=admin.id
    )

    assert snapshot.has_override is False
    assert snapshot.value == original_default
    assert original_default == config.ANON_TOKEN_LIMIT
    # The override row itself is gone.
    assert await vault._get_row(db_session, "ANON_TOKEN_LIMIT") is None


@pytest.mark.asyncio
async def test_set_setting_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    with pytest.raises(KeyError):
        await vault.set_setting(
            db_session, "NOT_A_REAL_SETTING", "x", updated_by_id=admin.id
        )


@pytest.mark.asyncio
async def test_set_setting_rejects_wrong_value_type(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    with pytest.raises(ValueError):
        await vault.set_setting(
            db_session, "ANON_TOKEN_LIMIT", "not-an-int", updated_by_id=admin.id
        )


@pytest.mark.asyncio
async def test_secret_setting_encrypt_decrypt_round_trip(
    db_session: AsyncSession, secret_setting_key: str
):
    admin = await _make_admin(db_session, permissions=["settings:write", "settings:reveal"])
    plaintext = "s3cr3t-value-abcdef"

    await vault.set_setting(
        db_session, secret_setting_key, plaintext, updated_by_id=admin.id
    )

    row = await vault._get_row(db_session, secret_setting_key)
    assert row is not None
    assert row.is_secret is True
    assert row.value_plain is None
    assert row.value_encrypted is not None
    # Stored ciphertext must not equal (or contain) the plaintext.
    assert row.value_encrypted != plaintext
    assert plaintext not in row.value_encrypted

    snapshot = await vault.get_setting(db_session, secret_setting_key)
    assert snapshot.value == plaintext

    revealed = await vault.reveal_setting(
        db_session, secret_setting_key, actor_user_id=admin.id
    )
    assert revealed == plaintext


@pytest.mark.asyncio
async def test_reveal_setting_rejects_non_secret(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:reveal"])
    with pytest.raises(ValueError):
        await vault.reveal_setting(
            db_session, "ANON_TOKEN_LIMIT", actor_user_id=admin.id
        )


@pytest.mark.asyncio
async def test_audit_row_written_on_create_update_delete_reveal(
    db_session: AsyncSession, secret_setting_key: str
):
    admin = await _make_admin(db_session, permissions=["settings:write", "settings:reveal"])

    # create (first set_setting on a key with no prior override)
    await vault.set_setting(db_session, secret_setting_key, "v1", updated_by_id=admin.id)
    create_rows = await _audit_rows(
        db_session, action="admin_setting.update", target_id=secret_setting_key
    )
    assert len(create_rows) == 1
    assert create_rows[0].before is None
    assert create_rows[0].after == {"value": "***"}  # secret redacted in audit log

    # update (second set_setting on the same key)
    await vault.set_setting(db_session, secret_setting_key, "v2", updated_by_id=admin.id)
    update_rows = await _audit_rows(
        db_session, action="admin_setting.update", target_id=secret_setting_key
    )
    assert len(update_rows) == 2
    assert update_rows[1].before == {"value": "***"}

    # reveal
    await vault.reveal_setting(db_session, secret_setting_key, actor_user_id=admin.id)
    reveal_rows = await _audit_rows(
        db_session, action="admin_setting.reveal", target_id=secret_setting_key
    )
    assert len(reveal_rows) == 1

    # delete / revert
    await vault.delete_setting(db_session, secret_setting_key, actor_user_id=admin.id)
    delete_rows = await _audit_rows(
        db_session, action="admin_setting.delete", target_id=secret_setting_key
    )
    assert len(delete_rows) == 1
    assert delete_rows[0].before == {"value": "***"}


@pytest.mark.asyncio
async def test_load_all_overrides_and_apply_restores_override_on_boot(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    original_default = int(vault.SETTINGS_REGISTRY["ANON_MAX_CONCURRENT_STREAMS"].default)
    new_value = original_default + 7

    await vault.set_setting(
        db_session, "ANON_MAX_CONCURRENT_STREAMS", new_value, updated_by_id=admin.id
    )
    assert new_value == config.ANON_MAX_CONCURRENT_STREAMS

    # Simulate a fresh process: drop the live instance override, keep the DB row.
    delattr(config, "ANON_MAX_CONCURRENT_STREAMS")
    assert original_default == config.ANON_MAX_CONCURRENT_STREAMS

    applied = await vault.load_all_overrides_and_apply(db_session)

    assert applied >= 1
    assert new_value == config.ANON_MAX_CONCURRENT_STREAMS


# ---------------------------------------------------------------------------
# app.routes.admin.admin_settings_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_settings_requires_settings_read(db_session: AsyncSession):
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await admin_settings_routes.list_settings(category=None, session=db_session, auth=_auth(user))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_list_settings_returns_registry_entries_with_categories(
    db_session: AsyncSession,
):
    admin = await _make_admin(db_session, permissions=["settings:read"])

    result = await admin_settings_routes.list_settings(category=None, session=db_session, auth=_auth(admin))

    keys = {s.key for s in result.settings}
    assert "ANON_TOKEN_LIMIT" in keys
    assert "quotas" in result.categories
    entry = next(s for s in result.settings if s.key == "ANON_TOKEN_LIMIT")
    assert entry.has_override is False
    assert entry.is_secret is False


@pytest.mark.asyncio
async def test_list_settings_always_masks_secret_value(
    db_session: AsyncSession, secret_setting_key: str
):
    admin = await _make_admin(db_session, permissions=["settings:read", "settings:write"])
    plaintext = "topsecretvalue"
    await vault.set_setting(db_session, secret_setting_key, plaintext, updated_by_id=admin.id)

    result = await admin_settings_routes.list_settings(category=None, session=db_session, auth=_auth(admin))

    entry = next(s for s in result.settings if s.key == secret_setting_key)
    assert entry.value != plaintext
    assert entry.value == f"***{plaintext[-4:]}"


@pytest.mark.asyncio
async def test_reveal_requires_stricter_permission_than_read(
    db_session: AsyncSession, secret_setting_key: str
):
    writer = await _make_admin(db_session, permissions=["settings:write"])
    await vault.set_setting(db_session, secret_setting_key, "value-x", updated_by_id=writer.id)

    read_only_admin = await _make_admin(db_session, permissions=["settings:read"])
    with pytest.raises(HTTPException) as exc:
        await admin_settings_routes.reveal_setting(
            secret_setting_key,
            request=_fake_request(),
            session=db_session,
            auth=_auth(read_only_admin),
        )
    assert exc.value.status_code == 403

    revealer = await _make_admin(db_session, permissions=["settings:reveal"])
    response = await admin_settings_routes.reveal_setting(
        secret_setting_key,
        request=_fake_request(),
        session=db_session,
        auth=_auth(revealer),
    )
    assert response.value == "value-x"


@pytest.mark.asyncio
async def test_update_setting_route_requires_settings_write(db_session: AsyncSession):
    read_only_admin = await _make_admin(db_session, permissions=["settings:read"])
    with pytest.raises(HTTPException) as exc:
        await admin_settings_routes.update_setting(
            "ANON_TOKEN_LIMIT",
            AdminSettingUpdate(value=1234),
            request=_fake_request(),
            session=db_session,
            auth=_auth(read_only_admin),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_setting_route_rejects_unknown_key(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_settings_routes.update_setting(
            "NOT_A_REAL_SETTING",
            AdminSettingUpdate(value="x"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_setting_route_rejects_invalid_type(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write"])
    with pytest.raises(HTTPException) as exc:
        await admin_settings_routes.update_setting(
            "ANON_TOKEN_LIMIT",
            AdminSettingUpdate(value="not-an-int"),
            request=_fake_request(),
            session=db_session,
            auth=_auth(admin),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_and_delete_routes_round_trip_and_audit(db_session: AsyncSession):
    admin = await _make_admin(db_session, permissions=["settings:write", "settings:read"])
    original_default = int(vault.SETTINGS_REGISTRY["ANON_TOKEN_QUOTA_TTL_DAYS"].default)
    new_value = original_default + 5

    updated = await admin_settings_routes.update_setting(
        "ANON_TOKEN_QUOTA_TTL_DAYS",
        AdminSettingUpdate(value=new_value),
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert updated.value == new_value
    assert updated.has_override is True
    assert new_value == config.ANON_TOKEN_QUOTA_TTL_DAYS

    update_audit = await _audit_rows(
        db_session, action="admin_setting.update", target_id="ANON_TOKEN_QUOTA_TTL_DAYS"
    )
    assert len(update_audit) == 1

    reverted = await admin_settings_routes.delete_setting(
        "ANON_TOKEN_QUOTA_TTL_DAYS",
        request=_fake_request(),
        session=db_session,
        auth=_auth(admin),
    )
    assert reverted.value == original_default
    assert reverted.has_override is False
    assert original_default == config.ANON_TOKEN_QUOTA_TTL_DAYS

    delete_audit = await _audit_rows(
        db_session, action="admin_setting.delete", target_id="ANON_TOKEN_QUOTA_TTL_DAYS"
    )
    assert len(delete_audit) == 1
