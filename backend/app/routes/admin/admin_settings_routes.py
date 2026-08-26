"""
Admin settings vault routes: the live-overridable `Config` settings managed
via `app.services.settings_vault_service` (see also
`app.config.settings_registry` for the curated list of manageable keys).

Endpoints:
- GET /admin/settings - list all settings, optionally filtered by category.
  Secret values are always masked here. Requires settings:read.
- POST /admin/settings/{key}/reveal - return one secret setting's decrypted
  plaintext value. Requires settings:reveal (stricter than settings:read).
- PUT /admin/settings/{key} - update a setting's value. Requires settings:write.
- DELETE /admin/settings/{key} - revert a setting to its Config default
  (deletes the override row). Requires settings:write.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config.settings_registry import list_categories
from app.db import PlatformPermission, get_async_session
from app.schemas import (
    AdminSettingRead,
    AdminSettingRevealResponse,
    AdminSettingsListResponse,
    AdminSettingUpdate,
)
from app.services import settings_vault_service as vault
from app.services.settings_vault_service import SettingSnapshot
from app.users import get_auth_context
from app.utils.platform_rbac import check_platform_permission

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_read(snapshot: SettingSnapshot, *, masked: bool) -> AdminSettingRead:
    return AdminSettingRead(
        key=snapshot.key,
        category=snapshot.category,
        value_type=snapshot.value_type,
        is_secret=snapshot.is_secret,
        is_disruptive=snapshot.is_disruptive,
        description=snapshot.description,
        value=vault.mask_value(snapshot) if masked else snapshot.value,
        has_override=snapshot.has_override,
        updated_by_id=snapshot.updated_by_id,
        updated_at=snapshot.updated_at,
    )


@router.get("/settings", response_model=AdminSettingsListResponse)
async def list_settings(
    category: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all managed settings (secrets masked), optionally filtered by
    category. Requires settings:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.SETTINGS_READ.value,
            "You don't have permission to view settings",
        )

        snapshots = await vault.list_settings(session, category=category)
        return AdminSettingsListResponse(
            settings=[_to_read(s, masked=True) for s in snapshots],
            categories=list_categories(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list settings: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list settings: {e!s}"
        ) from e


@router.post("/settings/{key}/reveal", response_model=AdminSettingRevealResponse)
async def reveal_setting(
    key: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return the decrypted plaintext value of one secret setting. Requires
    settings:reveal -- deliberately stricter than settings:read, and audited
    separately from a plain list/read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.SETTINGS_REVEAL.value,
            "You don't have permission to reveal secret settings",
        )

        try:
            value = await vault.reveal_setting(
                session,
                key,
                actor_user_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        return AdminSettingRevealResponse(key=key, value=value)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reveal setting '{key}': {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to reveal setting: {e!s}"
        ) from e


@router.put("/settings/{key}", response_model=AdminSettingRead)
async def update_setting(
    key: str,
    payload: AdminSettingUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a setting's value: validates against the settings registry,
    encrypts + stores it, applies it live against the `Config` singleton,
    and audits the change. Requires settings:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.SETTINGS_WRITE.value,
            "You don't have permission to change settings",
        )

        try:
            snapshot = await vault.set_setting(
                session,
                key,
                payload.value,
                updated_by_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        return _to_read(snapshot, masked=True)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update setting '{key}': {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update setting: {e!s}"
        ) from e


@router.delete("/settings/{key}", response_model=AdminSettingRead)
async def delete_setting(
    key: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Revert a setting to its Config default (deletes the override row,
    re-applies the default live). Requires settings:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.SETTINGS_WRITE.value,
            "You don't have permission to change settings",
        )

        try:
            snapshot = await vault.delete_setting(
                session,
                key,
                actor_user_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return _to_read(snapshot, masked=True)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete setting '{key}': {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete setting: {e!s}"
        ) from e
