"""Add admin_settings table for the super admin settings/secrets vault.

Phase B of the super admin dashboard plan. Stores admin-managed overrides of
curated `Config` attributes (see `app.config.settings_registry`); presence of
a row for a given `key` means an override is in effect, absence means the
`Config` class default applies. Secret values are encrypted at rest
(`value_encrypted`); non-secret values are stored as plain text
(`value_plain`). Does not seed any rows -- no overrides are in effect until
an admin sets one.

Revision ID: 176
Revises: 175
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "176"
down_revision: str | None = "175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'admin_settings'"
        )
    ).fetchone():
        op.create_table(
            "admin_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=200), nullable=False),
            sa.Column("value_encrypted", sa.Text(), nullable=True),
            sa.Column("value_plain", sa.Text(), nullable=True),
            sa.Column(
                "is_secret",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("value_type", sa.String(length=20), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column(
                "is_disruptive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
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
            sa.UniqueConstraint("key", name="uq_admin_settings_key"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_settings_key ON admin_settings (key)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_settings_category "
            "ON admin_settings (category)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_settings")
