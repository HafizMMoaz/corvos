"""
Connector credentials vault service: read/write/revert/reveal for the
admin-managed OAuth `client_id`/`client_secret` pairs of the platform's
curated connector integrations, and the live-apply mechanism that makes a
change take effect without a restart.

Storage: one `AdminConnectorCredential` row per overridden connector (see
`app.db.AdminConnectorCredential` and migration
`178_add_admin_connector_credentials`). Both credential fields are encrypted
at rest via `TokenEncryption` (the same class already used for OAuth tokens
and Phase B's settings vault). Absence of a row means the `Config` class
default is in effect for that connector's client_id/client_secret attributes.
`is_enabled=False` suspends a stored override live without deleting the
encrypted secret -- distinct from a full revert (`delete_connector_credential`,
which deletes the row entirely).

Live-apply mechanism: `config = Config()` (`app.config.config`) is a real
singleton *instance*. Because Python resolves instance `__dict__` before the
class body, `setattr(config, attr, value)` transparently overrides any
attribute with zero changes to the hundreds of existing `config.ATTR` read
sites -- the same trick `settings_vault_service` already uses.
`load_all_connector_credential_overrides_and_apply` runs this for every
stored, enabled override at FastAPI lifespan startup (see `app/app.py`);
`set_connector_credential` and `delete_connector_credential` apply it right
after their `session.commit()` succeeds, so a change (or revert) takes
effect on the very next read with no restart needed. Applying it only
post-commit (rather than in the middle of the transaction) keeps the live
value and the DB row from diverging if the commit itself fails and rolls
back -- the same fix-round-1 finding from Phase B.

Callers get a `ValueError` for validation problems (e.g. a client_id on a
connector that has no client_id concept) and a `KeyError` for an unknown
connector key, so routes can translate them into 400/404 without this module
knowing anything about FastAPI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.config.connector_credentials_registry import (
    CONNECTOR_CREDENTIALS_REGISTRY,
    ConnectorCredentialDefinition,
)
from app.db import AdminConnectorCredential
from app.utils.oauth_security import TokenEncryption
from app.utils.platform_rbac import record_admin_action

logger = logging.getLogger(__name__)


@dataclass
class ConnectorCredentialSnapshot:
    """A connector's current effective credential state: registry metadata
    + whether an override is in effect. Never carries decrypted values --
    use `reveal_connector_credential` for plaintext."""

    connector_key: str
    display_name: str
    description: str
    has_client_id: bool
    has_client_secret: bool
    # Whether the `Config` *class* carries a non-empty env-derived value for
    # each attribute. Independent of the override row: this is the state the
    # connector falls back to when no override is stored (or when a stored
    # one is cleared or suspended), which is what makes "cleared" and "never
    # configured anywhere" distinguishable in the dashboard.
    has_default_client_id: bool
    has_default_client_secret: bool
    is_enabled: bool
    has_override: bool
    updated_by_id: UUID | None
    updated_at: datetime | None


# No-override default state (no row exists): a connector with no admin
# override in effect is considered "enabled" in the sense that nothing is
# suspending the `Config` class default that's already applying.
_DEFAULT_AUDIT_STATE: dict[str, Any] = {
    "has_client_id": False,
    "has_client_secret": False,
    "is_enabled": True,
}


def _require_definition(connector_key: str) -> ConnectorCredentialDefinition:
    defn = CONNECTOR_CREDENTIALS_REGISTRY.get(connector_key)
    if defn is None:
        raise KeyError(f"'{connector_key}' is not a managed connector")
    return defn


async def _get_row(
    session: AsyncSession, connector_key: str
) -> AdminConnectorCredential | None:
    result = await session.execute(
        select(AdminConnectorCredential).filter(
            AdminConnectorCredential.connector_key == connector_key
        )
    )
    return result.scalars().first()


def _audit_dict(row: AdminConnectorCredential) -> dict[str, Any]:
    """Redacted snapshot of a row for `admin_audit_logs.before`/`after` --
    never includes decrypted or encrypted secret text, only whether each
    credential is currently set. Mirrors `admin_llm_routes._provider_audit_dict`'s
    `"has_api_key": bool(provider.api_key_encrypted)` pattern."""
    return {
        "has_client_id": bool(row.client_id_encrypted),
        "has_client_secret": bool(row.client_secret_encrypted),
        "is_enabled": row.is_enabled,
    }


def _snapshot(
    defn: ConnectorCredentialDefinition, row: AdminConnectorCredential | None
) -> ConnectorCredentialSnapshot:
    return ConnectorCredentialSnapshot(
        connector_key=defn.connector_key,
        display_name=defn.display_name,
        description=defn.description,
        has_client_id=bool(row.client_id_encrypted) if row is not None else False,
        has_client_secret=bool(row.client_secret_encrypted)
        if row is not None
        else False,
        # Row-independent by design: these describe the env-derived `Config`
        # class default, which stays in effect (and stays reportable) whether
        # or not an override row exists. `bool(...)` rather than
        # `is not None` because an env var present but empty
        # (`COMPOSIO_API_KEY=` in a .env) reaches `Config` as `""`, which is
        # not a usable credential and must not read as "configured".
        has_default_client_id=bool(defn.default_client_id),
        has_default_client_secret=bool(defn.default_client_secret),
        is_enabled=row.is_enabled if row is not None else True,
        has_override=row is not None,
        updated_by_id=row.updated_by_id if row is not None else None,
        updated_at=row.updated_at if row is not None else None,
    )


def _restore_default_live(defn: ConnectorCredentialDefinition) -> None:
    """Remove any live instance-level override for both of `defn`'s `Config`
    attributes, so `config.ATTR` resolves back through to the class
    attribute (the true default). The precise inverse of the
    `setattr(config, attr, value)` shadow trick `_reconcile_live` applies --
    a no-op if nothing overrode it this process's lifetime. Same guarded-
    delattr idiom as `settings_vault_service._restore_default_live`, applied
    to both `client_id_attr` (if the connector has one) and
    `client_secret_attr`."""
    if defn.client_id_attr is not None and defn.client_id_attr in vars(config):
        delattr(config, defn.client_id_attr)
    if defn.client_secret_attr in vars(config):
        delattr(config, defn.client_secret_attr)


def _reconcile_live(
    defn: ConnectorCredentialDefinition, row: AdminConnectorCredential | None
) -> None:
    """Bring the live `Config` singleton in line with what's actually
    persisted for `defn`'s connector -- `row` (its encrypted columns and
    `is_enabled` flag) is the single source of truth, never the raw
    parameters of whichever request triggered this call.

    If there's no row, or it's disabled, both attributes are restored to
    their class defaults (the guarded delattr in `_restore_default_live` is
    a no-op if nothing was ever applied). Otherwise each attribute is
    reconciled independently: applied (decrypted from the stored
    ciphertext) if that column is populated, restored to the class default
    if it's `None`. Deriving this from the row rather than from
    `client_id`/`client_secret` request parameters is what makes an
    explicit-null clear of just one field (leaving the other stored) take
    effect live immediately, and what makes re-enabling a previously
    suspended row with no credentials in the request body correctly
    reapply the still-stored ciphertext rather than leaving the class
    default live. Same per-row logic
    `load_all_connector_credential_overrides_and_apply` needs at boot, so
    both call sites share this one implementation."""
    if row is None or not row.is_enabled:
        _restore_default_live(defn)
        return

    if defn.client_id_attr is not None:
        if row.client_id_encrypted:
            setattr(
                config,
                defn.client_id_attr,
                TokenEncryption(config.SECRET_KEY).decrypt_token(
                    row.client_id_encrypted
                ),
            )
        elif defn.client_id_attr in vars(config):
            delattr(config, defn.client_id_attr)

    if row.client_secret_encrypted:
        setattr(
            config,
            defn.client_secret_attr,
            TokenEncryption(config.SECRET_KEY).decrypt_token(
                row.client_secret_encrypted
            ),
        )
    elif defn.client_secret_attr in vars(config):
        delattr(config, defn.client_secret_attr)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_connector_credential(
    session: AsyncSession, connector_key: str
) -> ConnectorCredentialSnapshot:
    """Read one connector's current effective credential state."""
    defn = _require_definition(connector_key)
    row = await _get_row(session, connector_key)
    return _snapshot(defn, row)


async def list_connector_credentials(
    session: AsyncSession,
) -> list[ConnectorCredentialSnapshot]:
    """List every registry connector's current effective credential state,
    one snapshot per registry entry regardless of whether an override row
    exists -- mirrors `settings_vault_service.list_settings` iterating the
    full registry, not just existing rows."""
    defs = sorted(
        CONNECTOR_CREDENTIALS_REGISTRY.values(), key=lambda d: d.connector_key
    )

    result = await session.execute(select(AdminConnectorCredential))
    rows_by_key = {row.connector_key: row for row in result.scalars().all()}

    return [_snapshot(defn, rows_by_key.get(defn.connector_key)) for defn in defs]


async def set_connector_credential(
    session: AsyncSession,
    connector_key: str,
    *,
    client_id: str | None,
    client_secret: str | None,
    is_enabled: bool | None,
    client_id_set: bool,
    client_secret_set: bool,
    is_enabled_set: bool,
    updated_by_id: UUID | None,
    ip_address: str | None = None,
) -> ConnectorCredentialSnapshot:
    """Partial-update a connector's stored credentials, apply the change
    live, and audit it. Uses the `*_set` flags (derived by the route layer
    from `payload.model_fields_set`, the same idiom Phase C's
    `AdminLLMProviderUpdate` handling uses) to distinguish "field omitted
    from the request" (leave stored value untouched) from "field explicitly
    present, possibly `null`" (apply the change -- `null`/empty clears the
    stored ciphertext).

    Commits the transaction (row upsert + audit row land atomically).
    """
    defn = _require_definition(connector_key)

    if client_id_set and client_id and defn.client_id_attr is None:
        raise ValueError(f"'{connector_key}' has no client_id -- only a client_secret")

    row = await _get_row(session, connector_key)

    # A request that sets nothing at all (no client_id, no client_secret, no
    # is_enabled key) changes nothing, so it must not materialize an
    # override row for a connector that has none: that would flip the
    # dashboard from an accurate "no override -- using environment default"
    # to a misleading "updated ... by ...", and emit an audit entry for a
    # request that did not modify a single value.
    if row is None and not (client_id_set or client_secret_set or is_enabled_set):
        return _snapshot(defn, None)

    had_override = row is not None
    before = _audit_dict(row) if had_override else None

    if row is None:
        row = AdminConnectorCredential(connector_key=connector_key)
        session.add(row)
        if not is_enabled_set:
            row.is_enabled = True

    if client_id_set:
        row.client_id_encrypted = (
            TokenEncryption(config.SECRET_KEY).encrypt_token(client_id)
            if client_id
            else None
        )
    if client_secret_set:
        row.client_secret_encrypted = (
            TokenEncryption(config.SECRET_KEY).encrypt_token(client_secret)
            if client_secret
            else None
        )
    if is_enabled_set:
        row.is_enabled = bool(is_enabled)

    row.updated_by_id = updated_by_id

    await session.flush()

    await record_admin_action(
        session,
        actor_user_id=updated_by_id,
        action="admin_connector_credential.update",
        target_type="admin_connector_credential",
        target_id=connector_key,
        before=before,
        after=_audit_dict(row),
        ip_address=ip_address,
    )

    await session.commit()

    # Live-apply only after the DB write is durably committed -- same
    # atomicity reasoning as `settings_vault_service.set_setting`.
    # Reconciled from the row's actual persisted state (not this call's raw
    # request parameters) -- see `_reconcile_live`'s docstring for why that
    # matters (explicit-null clears and bare is_enabled re-enables both
    # need to take effect live immediately, not just in the DB).
    _reconcile_live(defn, row)

    await session.refresh(row)
    return _snapshot(defn, row)


async def delete_connector_credential(
    session: AsyncSession,
    connector_key: str,
    *,
    actor_user_id: UUID | None,
    ip_address: str | None = None,
) -> ConnectorCredentialSnapshot:
    """Revert a connector to its `Config` class defaults: deletes the
    override row, restores both `Config` attributes live, and audits the
    revert. No-op (but still audited) if there was no override in effect."""
    defn = _require_definition(connector_key)
    row = await _get_row(session, connector_key)

    before = _audit_dict(row) if row is not None else None
    if row is not None:
        await session.delete(row)
        await session.flush()

    await record_admin_action(
        session,
        actor_user_id=actor_user_id,
        action="admin_connector_credential.delete",
        target_type="admin_connector_credential",
        target_id=connector_key,
        before=before,
        after=dict(_DEFAULT_AUDIT_STATE),
        ip_address=ip_address,
    )

    await session.commit()

    # Live-apply the revert only after the DB write (row deletion + audit
    # row) is durably committed -- same atomicity reasoning as
    # `set_connector_credential`. Still run regardless of whether `row`
    # existed, in case `config.ATTR` had drifted (e.g. a previous override
    # applied this process's lifetime but the row was deleted out-of-band).
    _restore_default_live(defn)

    return _snapshot(defn, None)


async def reveal_connector_credential(
    session: AsyncSession,
    connector_key: str,
    *,
    actor_user_id: UUID | None,
    ip_address: str | None = None,
) -> dict[str, str | None]:
    """Return the decrypted plaintext client_id/client_secret for one
    connector, audited separately from a plain read (callers must gate this
    behind the write permission -- see the routes module docstring)."""
    _require_definition(connector_key)  # KeyError for an unknown connector_key
    row = await _get_row(session, connector_key)

    client_id: str | None = None
    client_secret: str | None = None
    if row is not None:
        if row.client_id_encrypted:
            client_id = TokenEncryption(config.SECRET_KEY).decrypt_token(
                row.client_id_encrypted
            )
        if row.client_secret_encrypted:
            client_secret = TokenEncryption(config.SECRET_KEY).decrypt_token(
                row.client_secret_encrypted
            )

    await record_admin_action(
        session,
        actor_user_id=actor_user_id,
        action="admin_connector_credential.reveal",
        target_type="admin_connector_credential",
        target_id=connector_key,
        ip_address=ip_address,
    )
    await session.commit()

    return {"client_id": client_id, "client_secret": client_secret}


async def load_all_connector_credential_overrides_and_apply(
    session: AsyncSession,
) -> int:
    """Load every stored, enabled override and live-apply it against the
    `Config` singleton via the setattr shadow trick. Call once at FastAPI
    lifespan startup, after DB connectivity is confirmed. Rows whose
    `connector_key` is no longer present in `CONNECTOR_CREDENTIALS_REGISTRY`
    (e.g. a connector was retired) are skipped with a warning rather than
    applied or deleted -- deletion is left to a deliberate admin/operator
    action. Rows with `is_enabled=False` are skipped too -- a disabled row's
    stored override must not be applied live (the "suspend without
    deleting" semantic).

    Returns the number of overrides applied.
    """
    result = await session.execute(select(AdminConnectorCredential))
    rows = result.scalars().all()

    applied = 0
    for row in rows:
        defn = CONNECTOR_CREDENTIALS_REGISTRY.get(row.connector_key)
        if defn is None:
            logger.warning(
                "[connector_credentials_vault] admin_connector_credentials row for "
                "unknown connector_key '%s' (no longer in "
                "CONNECTOR_CREDENTIALS_REGISTRY) -- skipping",
                row.connector_key,
            )
            continue
        if not row.is_enabled:
            continue

        _reconcile_live(defn, row)
        applied += 1

    if applied:
        logger.info(
            "[connector_credentials_vault] applied %d connector credential "
            "override(s) at startup",
            applied,
        )
    return applied


__all__ = [
    "ConnectorCredentialSnapshot",
    "delete_connector_credential",
    "get_connector_credential",
    "list_connector_credentials",
    "load_all_connector_credential_overrides_and_apply",
    "reveal_connector_credential",
    "set_connector_credential",
]
