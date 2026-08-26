"""
Curated registry of `Config` attributes the super admin settings vault is
allowed to read and override live (see `app.services.settings_vault_service`
and `app.routes.admin.admin_settings_routes`).

Each `SettingDefinition` drives both request validation (value_type) and the
admin dashboard UI form (category grouping, is_secret masking,
is_disruptive warning banner, human-readable description). `default` is
read live from the `Config` class/instance so it always reflects the actual
env-derived default, not a value frozen at registry-authoring time.

Deliberately excludes:
- `DATABASE_URL`, `SECRET_KEY` -- the two unavoidable bootstrap values that
  must stay real container env vars (see phase plan / CLAUDE.md).
- Any provider/connector API keys (OpenAI, Stripe, OAuth client secrets,
  etc.) -- those get dedicated tables in later phases (C/D), not this
  generic vault.

To add a new manageable setting: add a `SettingDefinition` below. No
migration is needed -- `admin_settings` rows are created lazily the first
time an admin overrides a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.config import config as _config

ValueType = Literal["string", "int", "float", "bool", "json"]


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    value_type: ValueType
    category: str
    is_secret: bool
    is_disruptive: bool
    description: str

    @property
    def default(self) -> Any:
        """The `Config` class's original (env-derived) value for this
        attribute.

        Reads off the *class*, not the `config` singleton instance --
        `settings_vault_service.set_setting` applies live overrides via
        ``setattr(config, key, value)``, which shadows the class attribute
        with an instance attribute (Python resolves instance `__dict__`
        before the class body). Reading off the instance here would
        therefore keep returning the last-applied override, not the true
        default, for the remainder of the process's life. Reading off the
        class sidesteps that entirely.
        """
        return getattr(type(_config), self.key, None)


_DEFINITIONS: list[SettingDefinition] = [
    # ---------------------------------------------------------------
    # auth
    # ---------------------------------------------------------------
    SettingDefinition(
        key="REGISTRATION_ENABLED",
        value_type="bool",
        category="auth",
        is_secret=False,
        is_disruptive=True,
        description=(
            "Master kill switch for new sessions: when disabled, blocks "
            "email/password registration and login, and the Google OAuth "
            "authorize/callback routes, platform-wide. Takes effect "
            "immediately on the next request -- does not invalidate "
            "existing sessions."
        ),
    ),
    SettingDefinition(
        key="NOLOGIN_MODE_ENABLED",
        value_type="bool",
        category="auth",
        is_secret=False,
        is_disruptive=True,
        description=(
            "Enables anonymous/no-login usage mode. Changes platform-wide "
            "auth behavior for every visitor."
        ),
    ),
    # ---------------------------------------------------------------
    # gateway
    # ---------------------------------------------------------------
    SettingDefinition(
        key="GATEWAY_ENABLED",
        value_type="bool",
        category="gateway",
        is_secret=False,
        is_disruptive=True,
        description=(
            "Global master switch for the messaging gateway (Telegram, "
            "WhatsApp, Slack, Discord). Gateway supervisors/workers are "
            "only started once at process boot, so toggling this live "
            "changes gated route availability immediately but a backend "
            "restart is required for supervisors to actually start or stop."
        ),
    ),
    # ---------------------------------------------------------------
    # quotas
    # ---------------------------------------------------------------
    SettingDefinition(
        key="ANON_TOKEN_LIMIT",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description="Token quota cap for anonymous (no-login) sessions.",
    ),
    SettingDefinition(
        key="ANON_TOKEN_WARNING_THRESHOLD",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Token usage threshold at which anonymous sessions see a "
            "low-quota warning."
        ),
    ),
    SettingDefinition(
        key="ANON_TOKEN_QUOTA_TTL_DAYS",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description="Days before an anonymous session's token quota resets.",
    ),
    SettingDefinition(
        key="ANON_MAX_UPLOAD_SIZE_MB",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description="Max file upload size (MB) for anonymous sessions.",
    ),
    SettingDefinition(
        key="ANON_MAX_CONCURRENT_STREAMS",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Max concurrent chat streams allowed per anonymous session "
            "(abuse prevention)."
        ),
    ),
    SettingDefinition(
        key="QUOTA_MAX_RESERVE_MICROS",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Safety ceiling (micro-USD) on the per-call premium credit "
            "reservation, regardless of the estimated model cost."
        ),
    ),
    SettingDefinition(
        key="QUOTA_MAX_RESERVE_PER_CALL",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description="Default quota reserve tokens when not specified per-model.",
    ),
    SettingDefinition(
        key="FREE_MODEL_GLOBAL_MONTHLY_CAP_TOKENS",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Platform-wide monthly token cap shared across all free-tier model "
            "calls. Blocks every user's free-model use once hit, until the "
            "monthly reset."
        ),
    ),
    SettingDefinition(
        key="FREE_MODEL_USER_MONTHLY_CAP_TOKENS",
        value_type="int",
        category="quotas",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Per-user monthly token cap for free-tier model calls. Blocks that "
            "user's free-model use once hit, independent of the global cap."
        ),
    ),
    # ---------------------------------------------------------------
    # billing
    # ---------------------------------------------------------------
    SettingDefinition(
        key="DEFAULT_CREDIT_MICROS_BALANCE",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Starting credit wallet balance (micro-USD) for new users.",
    ),
    SettingDefinition(
        key="CREDIT_LOW_BALANCE_WARNING_MICROS",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Low-balance warning threshold (micro-USD) surfaced by the "
            "quota service to nudge users to top up."
        ),
    ),
    SettingDefinition(
        key="AUTO_RELOAD_ENABLED",
        value_type="bool",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Feature flag for off-session (auto-reload) credit top-ups.",
    ),
    SettingDefinition(
        key="AUTO_RELOAD_MIN_AMOUNT_MICROS",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Minimum configurable auto-reload amount (micro-USD).",
    ),
    SettingDefinition(
        key="AUTO_RELOAD_COOLDOWN_MINUTES",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Cooldown (minutes) between auto-reload charges so a burst of "
            "debits can't fire multiple charges."
        ),
    ),
    SettingDefinition(
        key="ETL_CREDIT_BILLING_ENABLED",
        value_type="bool",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Whether ETL page processing debits the credit wallet.",
    ),
    SettingDefinition(
        key="MICROS_PER_PAGE",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Price per ETL page processed (micro-USD), when ETL billing is on.",
    ),
    SettingDefinition(
        key="WEB_CRAWL_CREDIT_BILLING_ENABLED",
        value_type="bool",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description="Whether successful web-crawl requests debit the credit wallet.",
    ),
    SettingDefinition(
        key="WEB_CRAWL_MICROS_PER_SUCCESS",
        value_type="int",
        category="billing",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Price per successful web-crawl request (micro-USD), when "
            "web-crawl billing is on."
        ),
    ),
    # ---------------------------------------------------------------
    # paddle
    # ---------------------------------------------------------------
    SettingDefinition(
        key="PADDLE_API_KEY",
        value_type="string",
        category="paddle",
        is_secret=True,
        is_disruptive=False,
        description=(
            "Paddle API key used to create customers, checkout transactions, "
            "and look up transactions for reconciliation. Required for "
            "Paddle subscription checkout to work."
        ),
    ),
    SettingDefinition(
        key="PADDLE_WEBHOOK_SECRET",
        value_type="string",
        category="paddle",
        is_secret=True,
        is_disruptive=False,
        description=(
            "Secret Paddle uses to sign webhook notifications. Required to "
            "verify that incoming /paddle/webhook requests genuinely come "
            "from Paddle before granting any subscription credit."
        ),
    ),
    SettingDefinition(
        key="PADDLE_VENDOR_ID",
        value_type="string",
        category="paddle",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Paddle vendor/seller id, kept for operator reference. Not "
            "currently sent on any Paddle Billing API call this app makes."
        ),
    ),
    SettingDefinition(
        key="PADDLE_ENVIRONMENT",
        value_type="string",
        category="paddle",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Which Paddle environment to call: 'sandbox' for test payments "
            "or 'production' for real ones."
        ),
    ),
    SettingDefinition(
        key="PADDLE_RECONCILIATION_INTERVAL",
        value_type="string",
        category="paddle",
        is_secret=False,
        is_disruptive=False,
        description=(
            "How often the background job re-checks pending Paddle "
            "transactions that might have missed webhook delivery (e.g. "
            "'10m' for every 10 minutes)."
        ),
    ),
    SettingDefinition(
        key="PADDLE_RECONCILIATION_LOOKBACK_MINUTES",
        value_type="int",
        category="paddle",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Minimum age (in minutes) a pending Paddle transaction must "
            "reach before the reconciliation job checks it against Paddle "
            "directly."
        ),
    ),
    SettingDefinition(
        key="PADDLE_RECONCILIATION_BATCH_SIZE",
        value_type="int",
        category="paddle",
        is_secret=False,
        is_disruptive=False,
        description=(
            "Maximum number of pending Paddle transactions checked in a "
            "single reconciliation run."
        ),
    ),
]

SETTINGS_REGISTRY: dict[str, SettingDefinition] = {d.key: d for d in _DEFINITIONS}


def get_definition(key: str) -> SettingDefinition | None:
    """Look up a setting's registry definition, or None if key is unmanaged."""
    return SETTINGS_REGISTRY.get(key)


def list_categories() -> list[str]:
    """All distinct categories currently present in the registry, sorted."""
    return sorted({d.category for d in SETTINGS_REGISTRY.values()})


__all__ = [
    "SETTINGS_REGISTRY",
    "SettingDefinition",
    "get_definition",
    "list_categories",
]
