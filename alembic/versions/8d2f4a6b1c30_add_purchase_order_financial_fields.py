"""add purchase order financial fields

Revision ID: 8d2f4a6b1c30
Revises: 7c9d2e4f5a61
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2f4a6b1c30"
down_revision: Union[str, Sequence[str], None] = "7c9d2e4f5a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="RON",
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("expected_total_original", sa.Float(), nullable=True),
    )
    op.alter_column("purchase_orders", "currency", server_default=None)


def downgrade() -> None:
    op.drop_column("purchase_orders", "expected_total_original")
    op.drop_column("purchase_orders", "currency")
