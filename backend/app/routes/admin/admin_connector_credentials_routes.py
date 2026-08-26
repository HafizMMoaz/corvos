"""
Admin connector credentials vault routes: the live-overridable OAuth
`client_id`/`client_secret` pairs for the platform's curated connector
integrations, managed via
`app.services.admin_connector_credentials_service` (see also
`app.config.connector_credentials_registry` for the curated list of
manageable connectors).

Endpoints:
- GET /admin/connector-credentials - list all 13 registry connectors and
  their current override state (secrets never returned, only
  has_client_id/has_client_secret booleans). Requires connectors:read.
- PUT /admin/connector-credentials/{connector_key} - partial update of a
  connector's stored client_id/client_secret/is_enabled. Requires
  connectors:write.
- DELETE /admin/connector-credentials/{connector_key} - revert a connector
  to its Config defaults (deletes the override row). Requires
  connectors:write.
- POST /admin/connector-credentials/{connector_key}/reveal - return a
  connector's decrypted client_id/client_secret. Requires
  connectors:write (there is no separate reveal permission for this vault,
  exactly mirroring `admin_llm_routes.py`'s provider-key reveal endpoint,
  which documents "Requires llm_providers:write (there is no separate
  reveal permission...)").
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import PlatformPermission, get_async_session
from app.schemas import (
    AdminConnectorCredentialRead,
    AdminConnectorCredentialRevealResponse,
    AdminConnectorCredentialsListResponse,
    AdminConnectorCredentialUpdate,
)
from app.services import admin_connector_credentials_service as vault
from app.services.admin_connector_credentials_service import ConnectorCredentialSnapshot
from app.users import get_auth_context
from app.utils.platform_rbac import check_platform_permission

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_read(snapshot: ConnectorCredentialSnapshot) -> AdminConnectorCredentialRead:
    return AdminConnectorCredentialRead(
        connector_key=snapshot.connector_key,
        display_name=snapshot.display_name,
        description=snapshot.description,
        has_client_id=snapshot.has_client_id,
        has_client_secret=snapshot.has_client_secret,
        has_default_client_id=snapshot.has_default_client_id,
        has_default_client_secret=snapshot.has_default_client_secret,
        is_enabled=snapshot.is_enabled,
        has_override=snapshot.has_override,
        updated_by_id=snapshot.updated_by_id,
        updated_at=snapshot.updated_at,
    )


@router.get(
    "/connector-credentials", response_model=AdminConnectorCredentialsListResponse
)
async def list_connector_credentials(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List all managed connectors and their current override state (secrets
    never included). Requires connectors:read."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.CONNECTORS_READ.value,
            "You don't have permission to view connector credentials",
        )

        snapshots = await vault.list_connector_credentials(session)
        return AdminConnectorCredentialsListResponse(
            connectors=[_to_read(s) for s in snapshots]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list connector credentials: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list connector credentials: {e!s}"
        ) from e


@router.put(
    "/connector-credentials/{connector_key}",
    response_model=AdminConnectorCredentialRead,
)
async def update_connector_credential(
    connector_key: str,
    payload: AdminConnectorCredentialUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a connector's stored credentials (partial update): encrypts +
    stores whichever of client_id/client_secret/is_enabled are present in
    the request body, applies the change live against the `Config`
    singleton, and audits it. Requires connectors:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.CONNECTORS_WRITE.value,
            "You don't have permission to manage connector credentials",
        )

        fields_set = payload.model_fields_set

        try:
            snapshot = await vault.set_connector_credential(
                session,
                connector_key,
                client_id=payload.client_id,
                client_secret=payload.client_secret,
                is_enabled=payload.is_enabled,
                client_id_set="client_id" in fields_set,
                client_secret_set="client_secret" in fields_set,
                is_enabled_set="is_enabled" in fields_set,
                updated_by_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        return _to_read(snapshot)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to update connector credential '{connector_key}': {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update connector credential: {e!s}"
        ) from e


@router.delete(
    "/connector-credentials/{connector_key}",
    response_model=AdminConnectorCredentialRead,
)
async def delete_connector_credential(
    connector_key: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Revert a connector to its Config defaults (deletes the override row,
    re-applies the defaults live). Requires connectors:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.CONNECTORS_WRITE.value,
            "You don't have permission to manage connector credentials",
        )

        try:
            snapshot = await vault.delete_connector_credential(
                session,
                connector_key,
                actor_user_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return _to_read(snapshot)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to delete connector credential '{connector_key}': {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete connector credential: {e!s}"
        ) from e


@router.post(
    "/connector-credentials/{connector_key}/reveal",
    response_model=AdminConnectorCredentialRevealResponse,
)
async def reveal_connector_credential(
    connector_key: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return a connector's decrypted plaintext client_id/client_secret.
    Gated behind connectors:write (the higher bar; this vault has no
    separate reveal permission). Requires connectors:write."""
    try:
        await check_platform_permission(
            session,
            auth,
            PlatformPermission.CONNECTORS_WRITE.value,
            "You don't have permission to reveal connector credentials",
        )

        try:
            revealed = await vault.reveal_connector_credential(
                session,
                connector_key,
                actor_user_id=auth.user.id,
                ip_address=_client_ip(request),
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return AdminConnectorCredentialRevealResponse(
            connector_key=connector_key,
            client_id=revealed["client_id"],
            client_secret=revealed["client_secret"],
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to reveal connector credential '{connector_key}': {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to reveal connector credential: {e!s}"
        ) from e
