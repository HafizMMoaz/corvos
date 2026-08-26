"""Add admin_connector_credentials table for the super admin connectors vault.

Phase D of the super admin dashboard plan. Stores admin-managed overrides of
the curated OAuth `client_id`/`client_secret` pairs for the platform's
connector integrations (see `app.config.connector_credentials_registry`);
presence of a row for a given `connector_key` means an override is in effect,
absence means the `Config` class default applies. Both credential fields are
encrypted at rest (`client_id_encrypted`/`client_secret_encrypted`).
`is_enabled=False` suspends a stored override live without deleting it,
distinct from a full revert (row deletion). Does not seed any rows -- no
overrides are in effect until an admin sets one.

Revision ID: 178
Revises: 177
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "178"
down_revision: str | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'admin_connector_credentials'"
        )
    ).fetchone():
        op.create_table(
            "admin_connector_credentials",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("connector_key", sa.String(length=50), nullable=False),
            sa.Column("client_id_encrypted", sa.Text(), nullable=True),
            sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
            sa.Column("extra", sa.Text(), nullable=True),
            sa.Column(
                "is_enabled",
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
            sa.UniqueConstraint(
                "connector_key", name="uq_admin_connector_credentials_connector_key"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_connector_credentials_connector_key "
            "ON admin_connector_credentials (connector_key)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_connector_credentials")
