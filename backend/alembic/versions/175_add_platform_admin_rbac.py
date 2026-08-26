"""Add platform-wide admin RBAC tables for the super admin dashboard.

Creates platform_roles, platform_role_assignments, and admin_audit_logs.
Seeds three system roles (super_admin, billing_admin, support_admin) but
intentionally assigns no user to any of them -- the first super_admin must
be granted manually (documented operational runbook) to avoid a
self-granting privilege-escalation path.

Revision ID: 175
Revises: 174
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "175"
down_revision: str | None = "174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM_ROLES: dict[str, list[str]] = {
    "super_admin": ["*"],
    "billing_admin": [
        "billing:read",
        "billing:write",
        "plans:read",
        "plans:write",
        "users:read",
        "audit_log:read",
    ],
    "support_admin": [
        "users:read",
        "users:write",
        "quotas:read",
        "audit_log:read",
    ],
}


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'platform_roles'"
        )
    ).fetchone():
        op.create_table(
            "platform_roles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column(
                "permissions",
                postgresql.ARRAY(sa.String()),
                nullable=False,
                server_default="{}",
            ),
            sa.Column(
                "is_system_role",
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_platform_roles_name"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_platform_roles_name ON platform_roles (name)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'platform_role_assignments'"
        )
    ).fetchone():
        op.create_table(
            "platform_role_assignments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column(
                "assigned_by_id", postgresql.UUID(as_uuid=True), nullable=True
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["role_id"], ["platform_roles.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["assigned_by_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "role_id", name="uq_user_platform_role"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_platform_role_assignments_user_id "
            "ON platform_role_assignments (user_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'admin_audit_logs'"
        )
    ).fetchone():
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("target_type", sa.String(length=100), nullable=False),
            sa.Column("target_id", sa.String(length=100), nullable=True),
            sa.Column("before", postgresql.JSONB(), nullable=True),
            sa.Column("after", postgresql.JSONB(), nullable=True),
            sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["actor_user_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action "
            "ON admin_audit_logs (action)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_target_type "
            "ON admin_audit_logs (target_type)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_target_id "
            "ON admin_audit_logs (target_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at "
            "ON admin_audit_logs (created_at)"
        )

    # Seed system roles idempotently. No user is assigned -- see module docstring.
    seed_stmt = sa.text(
        "INSERT INTO platform_roles (name, description, permissions, "
        "is_system_role, created_at) "
        "VALUES (:name, :description, :permissions, true, now()) "
        "ON CONFLICT (name) DO NOTHING"
    ).bindparams(sa.bindparam("permissions", type_=postgresql.ARRAY(sa.String())))
    for name, permissions in _SYSTEM_ROLES.items():
        conn.execute(
            seed_stmt,
            {
                "name": name,
                "description": f"Built-in {name.replace('_', ' ')} role",
                "permissions": permissions,
            },
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_audit_logs")
    op.execute("DROP TABLE IF EXISTS platform_role_assignments")
    op.execute("DROP TABLE IF EXISTS platform_roles")
