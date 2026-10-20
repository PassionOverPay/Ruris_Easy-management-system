"""add blocked purchase order status

Revision ID: f1a2b3c4d5e6
Revises: 92d5a1b3c847
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "92d5a1b3c847"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE purchase_order_status ADD VALUE IF NOT EXISTS 'blocked'")


def downgrade() -> None:
    connection = op.get_bind()
    blocked_orders = connection.execute(
        sa.text("SELECT count(*) FROM purchase_orders WHERE status = 'blocked'")
    ).scalar_one()
    if blocked_orders:
        raise RuntimeError(
            "Cannot remove the blocked status while blocked purchase orders exist"
        )

    op.execute(
        "CREATE TYPE purchase_order_status_without_blocked AS ENUM "
        "('ordered', 'partially_received', 'received', 'cancelled')"
    )
    op.execute(
        "ALTER TABLE purchase_orders ALTER COLUMN status "
        "TYPE purchase_order_status_without_blocked "
        "USING status::text::purchase_order_status_without_blocked"
    )
    op.execute("DROP TYPE purchase_order_status")
    op.execute(
        "ALTER TYPE purchase_order_status_without_blocked "
        "RENAME TO purchase_order_status"
    )
