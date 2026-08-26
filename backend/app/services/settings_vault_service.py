"""
Settings vault service: read/write/revert for admin-managed `Config`
overrides, and the live-apply mechanism that makes a change take effect
without a restart.

Storage: one `AdminSetting` row per overridden key (see `app.db.AdminSetting`
and migration `176_add_admin_settings_vault`). Secret values are encrypted
at rest via `TokenEncryption` (the same class already used for OAuth
tokens); non-secret values are stored as plain text. Absence of a row means
the `Config` class default is in effect.

Live-apply mechanism: `config = Config()` (`app.config.config`) is a real
singleton *instance*. Because Python resolves instance `__dict__` before the
class body, `setattr(config, key, value)` transparently overrides any
attribute with zero changes to the hundreds of existing `config.ATTR` read
sites -- the same trick already used by
`app.services.openrouter_integration_service` to hot-swap
`GLOBAL_LLM_CONFIGS`. `load_all_overrides_and_apply` runs this for every
stored override at FastAPI lifespan startup (see `app/app.py`); `set_setting`
and `delete_setting` apply it right after their `session.commit()` succeeds,
so a change (or revert) takes effect on the very next read with no restart
needed -- consistent with the single-backend-instance deployment topology
this phase targets. Applying it only post-commit (rather than in the middle
of the transaction) keeps the live value and the DB row from diverging if
the commit itself fails and rolls back.

Callers get a `ValueError` for validation problems (unknown key, wrong
value_type, revealing a non-secret) and a `KeyError` for an unknown setting
key, so routes can translate them into 400/404 without this module knowing
anything about FastAPI.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.config.settings_registry import SETTINGS_REGISTRY, SettingDefinition
from app.db import AdminSetting
from app.utils.oauth_security import TokenEncryption
from app.utils.platform_rbac import record_admin_action

logger = logging.getLogger(__name__)


@dataclass
class SettingSnapshot:
    """A setting's current effective state: registry metadata + live value."""

    key: str
    category: str
    value_type: str
    is_secret: bool
    is_disruptive: bool
    description: str
    value: Any
    has_override: bool
    updated_by_id: UUID | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Value (de)serialization -- admin_settings stores everything as text
# ---------------------------------------------------------------------------


def _validate_input(defn: SettingDefinition, raw_value: Any) -> Any:
    """Validate + normalize a JSON-decoded request value against value_type."""
    if defn.value_type == "bool":
        if isinstance(raw_value, bool):
            return raw_value
        raise ValueError(f"'{defn.key}' expects a boolean value")
    if defn.value_type == "int":
        if isinstance(raw_value, int) and not isinstance(raw_value, bool):
            return raw_value
        raise ValueError(f"'{defn.key}' expects an integer value")
    if defn.value_type == "float":
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            return float(raw_value)
        raise ValueError(f"'{defn.key}' expects a numeric value")
    if defn.value_type == "json":
        return raw_value
    # string
    if isinstance(raw_value, str):
        return raw_value
    raise ValueError(f"'{defn.key}' expects a string value")


def _to_storage(defn: SettingDefinition, value: Any) -> str:
    """Serialize a validated typed value to the text form stored in the DB."""
    if defn.value_type == "json":
        return json.dumps(value)
    if defn.value_type == "bool":
        return "true" if value else "false"
    return str(value)


def _from_storage(defn: SettingDefinition, raw: str) -> Any:
    """Deserialize the DB's stored text form back into a typed Python value."""
    if defn.value_type == "bool":
        return raw.strip().lower() == "true"
    if defn.value_type == "int":
        return int(raw)
    if defn.value_type == "float":
        return float(raw)
    if defn.value_type == "json":
        return json.loads(raw)
    return raw


def _audit_value(defn: SettingDefinition, value: Any) -> Any:
    """Redact a value before it goes into `AdminAuditLog.before`/`after`."""
    return "***" if defn.is_secret else value


def mask_value(snapshot: SettingSnapshot) -> Any:
    """Mask a secret's value for display (e.g. list endpoint). Non-secrets
    pass through unchanged. Mirrors the last-4 masking convention used for
    displaying stored secrets elsewhere in the product."""
    if not snapshot.is_secret:
        return snapshot.value
    if snapshot.value is None:
        return None
    s = str(snapshot.value)
    if len(s) <= 4:
        return "***"
    return f"***{s[-4:]}"


def _restore_default_live(key: str) -> None:
    """Remove any live instance-level override for `key` so `config.KEY`
    resolves back through to the `Config` class attribute (the true
    default). The precise inverse of the `setattr(config, key, value)`
    shadow trick `set_setting` applies -- a no-op if nothing overrode it
    this process's lifetime."""
    if key in vars(config):
        delattr(config, key)


def _require_definition(key: str) -> SettingDefinition:
    defn = SETTINGS_REGISTRY.get(key)
    if defn is None:
        raise KeyError(f"'{key}' is not a managed setting")
    return defn


async def _get_row(session: AsyncSession, key: str) -> AdminSetting | None:
    result = await session.execute(select(AdminSetting).filter(AdminSetting.key == key))
    return result.scalars().first()


def _decode_row(defn: SettingDefinition, row: AdminSetting | None) -> Any:
    """The effective value for `defn`: decoded override if present, else default."""
    if row is None:
        return defn.default
    raw = row.value_encrypted if row.is_secret else row.value_plain
    if raw is None:
        return defn.default
    if row.is_secret:
        raw = TokenEncryption(config.SECRET_KEY).decrypt_token(raw)
    return _from_storage(defn, raw)


def _snapshot(defn: SettingDefinition, row: AdminSetting | None) -> SettingSnapshot:
    return SettingSnapshot(
        key=defn.key,
        category=defn.category,
        value_type=defn.value_type,
        is_secret=defn.is_secret,
        is_disruptive=defn.is_disruptive,
        description=defn.description,
        value=_decode_row(defn, row),
        has_override=row is not None,
        updated_by_id=row.updated_by_id if row else None,
        updated_at=row.updated_at if row else None,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_setting(session: AsyncSession, key: str) -> SettingSnapshot:
    """Read one setting's current effective value (decrypted if secret)."""
    defn = _require_definition(key)
    row = await _get_row(session, key)
    return _snapshot(defn, row)


async def list_settings(
    session: AsyncSession, *, category: str | None = None
) -> list[SettingSnapshot]:
    """List every managed setting's current effective value, optionally
    filtered to one category. Callers are responsible for masking secrets
    before returning them over the wire -- use `mask_value`."""
    defs = list(SETTINGS_REGISTRY.values())
    if category is not None:
        defs = [d for d in defs if d.category == category]
    defs.sort(key=lambda d: (d.category, d.key))

    result = await session.execute(select(AdminSetting))
    rows_by_key = {row.key: row for row in result.scalars().all()}

    return [_snapshot(defn, rows_by_key.get(defn.key)) for defn in defs]


async def set_setting(
    session: AsyncSession,
    key: str,
    value: Any,
    *,
    updated_by_id: UUID | None,
    ip_address: str | None = None,
) -> SettingSnapshot:
    """Validate + store a new value for `key`, apply it live, and audit it.

    Commits the transaction (row upsert + audit row land atomically).
    """
    defn = _require_definition(key)
    typed_value = _validate_input(defn, value)

    row = await _get_row(session, key)
    had_override = row is not None
    before = _audit_value(defn, _decode_row(defn, row)) if had_override else None

    if row is None:
        row = AdminSetting(key=key)
        session.add(row)

    row.is_secret = defn.is_secret
    row.value_type = defn.value_type
    row.category = defn.category
    row.description = defn.description
    row.is_disruptive = defn.is_disruptive
    row.updated_by_id = updated_by_id

    stored = _to_storage(defn, typed_value)
    if defn.is_secret:
        row.value_encrypted = TokenEncryption(config.SECRET_KEY).encrypt_token(stored)
        row.value_plain = None
    else:
        row.value_plain = stored
        row.value_encrypted = None

    await session.flush()

    await record_admin_action(
        session,
        actor_user_id=updated_by_id,
        action="admin_setting.update",
        target_type="admin_setting",
        target_id=key,
        before={"value": before} if had_override else None,
        after={"value": _audit_value(defn, typed_value)},
        ip_address=ip_address,
    )

    await session.commit()

    # Live-apply only after the DB write is durably committed -- applying
    # this any earlier risks the live singleton and the DB row diverging if
    # the audit-log flush or the commit itself fails and the transaction
    # rolls back (single-instance topology: nothing else would correct the
    # live value until the next restart, which would then fight the DB).
    setattr(config, key, typed_value)

    await session.refresh(row)
    return _snapshot(defn, row)


async def delete_setting(
    session: AsyncSession,
    key: str,
    *,
    actor_user_id: UUID | None,
    ip_address: str | None = None,
) -> SettingSnapshot:
    """Revert `key` to its `Config` class default: deletes the override row,
    re-applies the default live, and audits the revert. No-op (but still
    audited) if there was no override in effect."""
    defn = _require_definition(key)
    row = await _get_row(session, key)

    before = _audit_value(defn, _decode_row(defn, row)) if row is not None else None
    if row is not None:
        await session.delete(row)
        await session.flush()

    await record_admin_action(
        session,
        actor_user_id=actor_user_id,
        action="admin_setting.delete",
        target_type="admin_setting",
        target_id=key,
        before={"value": before} if before is not None else None,
        after={"value": _audit_value(defn, defn.default)},
        ip_address=ip_address,
    )

    await session.commit()

    # Live-apply the revert only after the DB write (row deletion + audit
    # row) is durably committed -- same atomicity reasoning as `set_setting`.
    # Still run regardless of whether `row` existed, in case `config.ATTR`
    # had drifted (e.g. a previous override applied this process's lifetime
    # but the row was deleted out-of-band).
    _restore_default_live(key)

    return _snapshot(defn, None)


async def reveal_setting(
    session: AsyncSession,
    key: str,
    *,
    actor_user_id: UUID | None,
    ip_address: str | None = None,
) -> Any:
    """Return the decrypted plaintext value of one secret setting, audited
    separately from a plain read (callers must gate this behind a stricter
    permission than list/get)."""
    defn = _require_definition(key)
    if not defn.is_secret:
        raise ValueError(f"'{key}' is not a secret setting")

    row = await _get_row(session, key)
    value = _decode_row(defn, row)

    await record_admin_action(
        session,
        actor_user_id=actor_user_id,
        action="admin_setting.reveal",
        target_type="admin_setting",
        target_id=key,
        ip_address=ip_address,
    )
    await session.commit()
    return value


async def load_all_overrides_and_apply(session: AsyncSession) -> int:
    """Load every stored override and live-apply it against the `Config`
    singleton via the setattr shadow trick. Call once at FastAPI lifespan
    startup, after DB connectivity is confirmed. Rows whose key is no longer
    present in `SETTINGS_REGISTRY` (e.g. a setting was retired) are skipped
    with a warning rather than applied or deleted -- deletion is left to a
    deliberate admin/operator action.

    Returns the number of overrides applied.
    """
    result = await session.execute(select(AdminSetting))
    rows = result.scalars().all()

    applied = 0
    for row in rows:
        defn = SETTINGS_REGISTRY.get(row.key)
        if defn is None:
            logger.warning(
                "[settings_vault] admin_settings row for unknown key '%s' "
                "(no longer in SETTINGS_REGISTRY) -- skipping",
                row.key,
            )
            continue
        setattr(config, row.key, _decode_row(defn, row))
        applied += 1

    if applied:
        logger.info("[settings_vault] applied %d setting override(s) at startup", applied)
    return applied


__all__ = [
    "SettingSnapshot",
    "delete_setting",
    "get_setting",
    "list_settings",
    "load_all_overrides_and_apply",
    "mask_value",
    "reveal_setting",
    "set_setting",
]
