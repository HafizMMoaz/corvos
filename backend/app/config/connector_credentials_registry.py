"""
Curated registry of `Config` attributes the super admin connectors vault is
allowed to read and override live (see
`app.services.admin_connector_credentials_service` and
`app.routes.admin.admin_connector_credentials_routes`).

Each `ConnectorCredentialDefinition` drives both request validation (which
connector keys are known, and whether a client_id concept even applies) and
the admin dashboard UI form (display name, description). `default_client_id`/
`default_client_secret` are read live from the `Config` class so they always
reflect the actual env-derived default, not a value frozen at
registry-authoring time.

To add a new manageable connector: add a `ConnectorCredentialDefinition`
below. No migration is needed -- `admin_connector_credentials` rows are
created lazily the first time an admin overrides a connector's credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import config as _config


@dataclass(frozen=True)
class ConnectorCredentialDefinition:
    connector_key: str
    display_name: str
    description: str
    client_id_attr: str | None  # Config attribute name, or None if this
    # connector has no client_id concept (Composio: a single API key, no
    # OAuth client_id/secret pair)
    client_secret_attr: str  # Config attribute name for the secret/API key

    @property
    def default_client_id(self) -> str | None:
        """The `Config` class's original (env-derived) client_id value.

        Reads off the *class*, not the `config` singleton instance -- same
        reasoning as `SettingDefinition.default`
        (`app.config.settings_registry`): live overrides are applied via
        ``setattr(config, attr, value)``, which shadows the class attribute
        with an instance attribute, so reading off the instance would keep
        returning the last-applied override instead of the true default.
        """
        if self.client_id_attr is None:
            return None
        return getattr(type(_config), self.client_id_attr, None)

    @property
    def default_client_secret(self) -> str | None:
        """The `Config` class's original (env-derived) client_secret value.
        Same class-not-instance reasoning as `default_client_id`."""
        return getattr(type(_config), self.client_secret_attr, None)


_DEFINITIONS: list[ConnectorCredentialDefinition] = [
    ConnectorCredentialDefinition(
        connector_key="slack",
        display_name="Slack",
        description="OAuth app credentials for the workspace-level Slack connector.",
        client_id_attr="SLACK_CLIENT_ID",
        client_secret_attr="SLACK_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="gateway_slack",
        display_name="Slack Gateway",
        description=(
            "OAuth app credentials for the platform-wide inbound Slack "
            "messaging gateway bot. Independent of the 'slack' connector "
            "above even though both may point at the same Slack app in "
            "practice."
        ),
        client_id_attr="GATEWAY_SLACK_CLIENT_ID",
        client_secret_attr="GATEWAY_SLACK_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="notion",
        display_name="Notion",
        description="OAuth app credentials for the Notion connector.",
        client_id_attr="NOTION_CLIENT_ID",
        client_secret_attr="NOTION_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="atlassian",
        display_name="Atlassian (Jira & Confluence)",
        description="OAuth app credentials shared by the Jira and Confluence connectors.",
        client_id_attr="ATLASSIAN_CLIENT_ID",
        client_secret_attr="ATLASSIAN_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="linear",
        display_name="Linear",
        description="OAuth app credentials for the Linear connector.",
        client_id_attr="LINEAR_CLIENT_ID",
        client_secret_attr="LINEAR_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="discord",
        display_name="Discord",
        description="OAuth app credentials for the Discord connector.",
        client_id_attr="DISCORD_CLIENT_ID",
        client_secret_attr="DISCORD_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="microsoft",
        display_name="Microsoft (Teams & OneDrive)",
        description="OAuth app credentials shared by the Teams and OneDrive connectors.",
        client_id_attr="MICROSOFT_CLIENT_ID",
        client_secret_attr="MICROSOFT_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="clickup",
        display_name="ClickUp",
        description="OAuth app credentials for the ClickUp connector.",
        client_id_attr="CLICKUP_CLIENT_ID",
        client_secret_attr="CLICKUP_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="airtable",
        display_name="Airtable",
        description="OAuth app credentials for the Airtable connector.",
        client_id_attr="AIRTABLE_CLIENT_ID",
        client_secret_attr="AIRTABLE_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="dropbox",
        display_name="Dropbox",
        description="OAuth app credentials for the Dropbox connector.",
        client_id_attr="DROPBOX_APP_KEY",
        client_secret_attr="DROPBOX_APP_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="google",
        display_name="Google",
        description="OAuth app credentials for Google Calendar/Gmail/Drive connectors.",
        client_id_attr="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_attr="GOOGLE_OAUTH_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="google_desktop",
        display_name="Google (Desktop App)",
        description="OAuth app credentials for the desktop-app variant of the Google integration.",
        client_id_attr="GOOGLE_DESKTOP_CLIENT_ID",
        client_secret_attr="GOOGLE_DESKTOP_CLIENT_SECRET",
    ),
    ConnectorCredentialDefinition(
        connector_key="composio",
        display_name="Composio",
        description=(
            "API key for Composio-managed OAuth integrations. Composio has "
            "no separate client_id -- only a single API key."
        ),
        client_id_attr=None,
        client_secret_attr="COMPOSIO_API_KEY",
    ),
]

CONNECTOR_CREDENTIALS_REGISTRY: dict[str, ConnectorCredentialDefinition] = {
    d.connector_key: d for d in _DEFINITIONS
}


def get_definition(connector_key: str) -> ConnectorCredentialDefinition | None:
    """Look up a connector's registry definition, or None if unmanaged."""
    return CONNECTOR_CREDENTIALS_REGISTRY.get(connector_key)


__all__ = [
    "CONNECTOR_CREDENTIALS_REGISTRY",
    "ConnectorCredentialDefinition",
    "get_definition",
]
