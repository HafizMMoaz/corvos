"""Add Paddle billing tables: paddle_customers, paddle_subscriptions,
paddle_transactions.

Phase E, Track 2 of the super admin dashboard plan. Wires Paddle as the
payment processor for plan subscription checkout -- additive to, not a
replacement of, the existing Stripe one-off credit-purchase flow (which
stays fully functional). Paddle customer/subscription/transaction ids are
opaque-but-not-sensitive references, stored in plaintext exactly like
``CreditPurchase.stripe_checkout_session_id`` already is.

``paddle_transactions.status`` reuses the existing ``creditpurchasestatus``
Postgres enum type (created for ``credit_purchases`` back in migration 156,
renamed there from ``premiumtokenpurchasestatus``) rather than defining a
new one -- the plan text explicitly calls for reusing
``CreditPurchase``/``CreditPurchaseStatus`` for this table's idempotent
webhook-fulfillment shape.

Revision ID: 181
Revises: 180
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "181"
down_revision: str | None = "180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'paddle_customers'"
        )
    ).fetchone():
        op.create_table(
            "paddle_customers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("paddle_customer_id", sa.String(length=255), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_paddle_customers_user_id"),
            sa.UniqueConstraint(
                "paddle_customer_id", name="uq_paddle_customers_paddle_customer_id"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_customers_user_id "
            "ON paddle_customers (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_customers_paddle_customer_id "
            "ON paddle_customers (paddle_customer_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'paddle_subscriptions'"
        )
    ).fetchone():
        op.create_table(
            "paddle_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column("paddle_subscription_id", sa.String(length=255), nullable=False),
            sa.Column("paddle_customer_id", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "cancel_at_period_end",
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
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "paddle_subscription_id",
                name="uq_paddle_subscriptions_paddle_subscription_id",
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_subscriptions_user_id "
            "ON paddle_subscriptions (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_subscriptions_plan_id "
            "ON paddle_subscriptions (plan_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS "
            "ix_paddle_subscriptions_paddle_subscription_id "
            "ON paddle_subscriptions (paddle_subscription_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_subscriptions_paddle_customer_id "
            "ON paddle_subscriptions (paddle_customer_id)"
        )

    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'paddle_transactions'"
        )
    ).fetchone():
        op.create_table(
            "paddle_transactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("paddle_transaction_id", sa.String(length=255), nullable=False),
            sa.Column("paddle_subscription_id", sa.String(length=255), nullable=True),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                # ``creditpurchasestatus`` was created for ``credit_purchases``
                # in migration 156 with its labels set to the Python enum's
                # *member names* (PENDING/COMPLETED/FAILED), not its lowercase
                # ``.value`` strings -- SQLAlchemy's ``Enum(CreditPurchaseStatus)``
                # stores/reads by member name by default. Match that exactly.
                postgresql.ENUM(
                    "PENDING",
                    "COMPLETED",
                    "FAILED",
                    name="creditpurchasestatus",
                    create_type=False,
                ),
                nullable=False,
                server_default="PENDING",
            ),
            sa.Column(
                "credit_micros_granted",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("amount_total", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "paddle_transaction_id",
                name="uq_paddle_transactions_paddle_transaction_id",
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paddle_transactions_user_id "
            "ON paddle_transactions (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS "
            "ix_paddle_transactions_paddle_transaction_id "
            "ON paddle_transactions (paddle_transaction_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS "
            "ix_paddle_transactions_paddle_subscription_id "
            "ON paddle_transactions (paddle_subscription_id)"
        )


def downgrade() -> None:
    # The ``creditpurchasestatus`` enum type is owned by ``credit_purchases``
    # (migration 156) -- dropping ``paddle_transactions`` must not drop it.
    op.execute("DROP TABLE IF EXISTS paddle_transactions")
    op.execute("DROP TABLE IF EXISTS paddle_subscriptions")
    op.execute("DROP TABLE IF EXISTS paddle_customers")
