"""Add plans, feature flags, and entitlement tables.

Phase E, Track 1 of the super admin dashboard plan. Introduces the
subscription **plan** primitive (Free/Pro/Team-style) and **feature flags**,
with per-plan defaults and per-user overrides, resolved by
`app.services.entitlement_service`. `plans.monthly_credit_micros` and
`plans.paddle_price_id` are written by this track but read/granted by a later
Paddle billing track -- no granting logic lives here.

`plan_feature_values` absence means a flag is disabled for that plan (a
deny-by-default allowlist of *enabled* flags). `plan_model_entitlements`
absence (zero rows for a plan) means every model is allowed for that plan --
the opposite default direction, deliberately: every existing user gets
`plan_id = NULL` after migration 180 and must see zero behavior change, and a
freshly created plan with no entitlements configured yet must not silently
lock its members out of every model.

Revision ID: 179
Revises: 178
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "179"
down_revision: str | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'plans'")
    ).fetchone():
        op.create_table(
            "plans",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_key", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "monthly_credit_micros",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("paddle_price_id", sa.String(length=255), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("plan_key", name="uq_plans_plan_key"),
            sa.UniqueConstraint("paddle_price_id", name="uq_plans_paddle_price_id"),
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_plans_plan_key ON plans (plan_key)")

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'feature_flags'"
        )
    ).fetchone():
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("flag_key", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flag_key", name="uq_feature_flags_flag_key"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_feature_flags_flag_key "
            "ON feature_flags (flag_key)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'plan_feature_values'"
        )
    ).fetchone():
        op.create_table(
            "plan_feature_values",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("feature_flag_id", sa.Integer(), nullable=False),
            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["feature_flag_id"], ["feature_flags.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "plan_id", "feature_flag_id", name="uq_plan_feature_value"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_plan_feature_values_plan_id "
            "ON plan_feature_values (plan_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_plan_feature_values_feature_flag_id "
            "ON plan_feature_values (feature_flag_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'user_feature_overrides'"
        )
    ).fetchone():
        op.create_table(
            "user_feature_overrides",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("feature_flag_id", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["feature_flag_id"], ["feature_flags.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "feature_flag_id", name="uq_user_feature_override"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_user_feature_overrides_user_id "
            "ON user_feature_overrides (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_user_feature_overrides_feature_flag_id "
            "ON user_feature_overrides (feature_flag_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'plan_model_entitlements'"
        )
    ).fetchone():
        op.create_table(
            "plan_model_entitlements",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("config_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "plan_id", "config_id", name="uq_plan_model_entitlement"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_plan_model_entitlements_plan_id "
            "ON plan_model_entitlements (plan_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_plan_model_entitlements_config_id "
            "ON plan_model_entitlements (config_id)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS plan_model_entitlements")
    op.execute("DROP TABLE IF EXISTS user_feature_overrides")
    op.execute("DROP TABLE IF EXISTS plan_feature_values")
    op.execute("DROP TABLE IF EXISTS feature_flags")
    op.execute("DROP TABLE IF EXISTS plans")
