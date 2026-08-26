"""
Pydantic schemas for the super admin connector credentials vault endpoints
(`app.routes.admin.admin_connector_credentials_routes`).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminConnectorCredentialRead(BaseModel):
    """One connector's current credential state. Never carries decrypted
    client_id/client_secret -- only whether each is currently stored
    (`has_client_id`/`has_client_secret`). Use the dedicated reveal endpoint
    for plaintext.

    `has_default_client_id`/`has_default_client_secret` describe the
    *environment*, not the override row: whether the `Config` class carries a
    non-empty env-derived value for that attribute. They are what lets the
    dashboard tell "cleared / never configured" apart from "no admin
    override, but a working `.env` credential is in effect", which the two
    `has_*` row booleans alone cannot express.
    """

    connector_key: str
    display_name: str
    description: str
    has_client_id: bool
    has_client_secret: bool
    has_default_client_id: bool
    has_default_client_secret: bool
    is_enabled: bool
    has_override: bool
    updated_by_id: UUID | None
    updated_at: datetime | None


class AdminConnectorCredentialsListResponse(BaseModel):
    """Response for `GET /admin/connector-credentials`."""

    connectors: list[AdminConnectorCredentialRead]


class AdminConnectorCredentialUpdate(BaseModel):
    """Request body for `PUT /admin/connector-credentials/{connector_key}`
    (partial update -- only fields present in the request body are changed,
    same convention as `AdminLLMProviderUpdate`). A field explicitly set to
    `null` clears that stored value."""

    client_id: str | None = None
    client_secret: str | None = None
    is_enabled: bool | None = None


class AdminConnectorCredentialRevealResponse(BaseModel):
    """Response for `POST /admin/connector-credentials/{connector_key}/reveal`:
    the one place decrypted client_id/client_secret are ever returned."""

    connector_key: str
    client_id: str | None
    client_secret: str | None
