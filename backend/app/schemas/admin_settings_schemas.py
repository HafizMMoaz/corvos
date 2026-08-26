"""
Pydantic schemas for the super admin settings/secrets vault endpoints
(`app.routes.admin.admin_settings_routes`).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AdminSettingRead(BaseModel):
    """One setting's current effective state. `value` is masked (e.g. `***1234`)
    when `is_secret` is true, except on the dedicated reveal endpoint."""

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


class AdminSettingsListResponse(BaseModel):
    """Response for `GET /admin/settings`."""

    settings: list[AdminSettingRead]
    categories: list[str]


class AdminSettingUpdate(BaseModel):
    """Request body for `PUT /admin/settings/{key}`. `value`'s expected
    JSON shape depends on the setting's `value_type` (bool/int/float/str/
    arbitrary JSON) -- validated server-side against the settings registry."""

    value: Any


class AdminSettingRevealResponse(BaseModel):
    """Response for `POST /admin/settings/{key}/reveal`: the one place a
    secret setting's plaintext value is ever returned over the wire."""

    key: str
    value: Any
