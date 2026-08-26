"""Add user.plan_id, referencing the plans table added in migration 179.

Phase E, Track 1 of the super admin dashboard plan. Single nullable column
on the real `user` table -- `plan_id IS NULL` means the user has no plan
assigned, which `app.services.entitlement_service.get_effective_entitlements`
treats as unrestricted model access and every feature flag defaulting to its
plan-less (disabled) value. `ON DELETE SET NULL` so deleting a plan
un-assigns its members instead of erroring or cascading. No backfill: NULL is
correct for every existing user.

Revision ID: 180
Revises: 179
"""

from collections.abc import Sequence

from alembic import op

revision: str = "180"
down_revision: str | None = "179"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS plan_id INTEGER '
        "REFERENCES plans(id) ON DELETE SET NULL"
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_user_plan_id ON "user" (plan_id)')


def downgrade() -> None:
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS plan_id')
