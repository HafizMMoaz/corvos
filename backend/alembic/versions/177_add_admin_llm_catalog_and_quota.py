"""Add admin LLM provider/model catalog and free-model quota tables.

Phase C of the super admin dashboard plan. `admin_llm_providers` and
`admin_llm_models` are a DB-backed replacement for the gitignored,
hand-edited `backend/app/config/global_llm_config.yaml`, managed through the
super admin dashboard instead of YAML edits and redeploys (see
`app.services.admin_llm_catalog_service`). `free_model_global_quota` and
`free_model_user_quota` belong to the free-model quota enforcement track;
both tables are created here (per the phase's migration ordering) but are not
read or written by this track's service/routes.

Revision ID: 177
Revises: 176
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "177"
down_revision: str | None = "176"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'admin_llm_providers'"
        )
    ).fetchone():
        op.create_table(
            "admin_llm_providers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider_key", sa.String(length=50), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("transport", sa.String(length=30), nullable=False),
            sa.Column("litellm_prefix", sa.String(length=50), nullable=True),
            sa.Column("default_base_url", sa.String(length=500), nullable=True),
            sa.Column(
                "base_url_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("auth_style", sa.String(length=20), nullable=False),
            sa.Column("api_key_encrypted", sa.Text(), nullable=True),
            sa.Column("api_base_override", sa.String(length=500), nullable=True),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
                ["created_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider_key", name="uq_admin_llm_providers_provider_key"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_llm_providers_provider_key "
            "ON admin_llm_providers (provider_key)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'admin_llm_models'"
        )
    ).fetchone():
        op.create_table(
            "admin_llm_models",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("model_name", sa.String(length=300), nullable=False),
            sa.Column(
                "billing_tier",
                sa.String(length=20),
                nullable=False,
                server_default="premium",
            ),
            sa.Column(
                "anonymous_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "seo_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("seo_slug", sa.String(length=200), nullable=True),
            sa.Column("seo_title", sa.String(length=300), nullable=True),
            sa.Column("seo_description", sa.Text(), nullable=True),
            sa.Column("quota_reserve_tokens", sa.Integer(), nullable=True),
            sa.Column(
                "supports_image_input",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "supports_tools",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("max_input_tokens", sa.Integer(), nullable=True),
            sa.Column("api_base_override", sa.String(length=500), nullable=True),
            sa.Column("api_version", sa.String(length=50), nullable=True),
            sa.Column("rpm", sa.Integer(), nullable=True),
            sa.Column("tpm", sa.Integer(), nullable=True),
            sa.Column("litellm_params", postgresql.JSONB(), nullable=True),
            sa.Column("system_instructions", sa.Text(), nullable=True),
            sa.Column(
                "use_default_system_instructions",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "citations_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "is_planner",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "router_pool_eligible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
                ["provider_id"], ["admin_llm_providers.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seo_slug", name="uq_admin_llm_models_seo_slug"),
            sa.UniqueConstraint(
                "provider_id",
                "model_name",
                name="uq_admin_llm_model_provider_model",
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_llm_models_provider_id "
            "ON admin_llm_models (provider_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'free_model_global_quota'"
        )
    ).fetchone():
        op.create_table(
            "free_model_global_quota",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column(
                "tokens_reserved",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "tokens_used",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'free_model_user_quota'"
        )
    ).fetchone():
        op.create_table(
            "free_model_user_quota",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column(
                "tokens_reserved",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "tokens_used",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_free_model_user_quota_user_id"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_free_model_user_quota_user_id "
            "ON free_model_user_quota (user_id)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS free_model_user_quota")
    op.execute("DROP TABLE IF EXISTS free_model_global_quota")
    op.execute("DROP TABLE IF EXISTS admin_llm_models")
    op.execute("DROP TABLE IF EXISTS admin_llm_providers")
