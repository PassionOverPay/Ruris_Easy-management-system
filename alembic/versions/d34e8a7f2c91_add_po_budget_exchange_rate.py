"""add purchase order budget exchange rate

Revision ID: d34e8a7f2c91
Revises: a41c7e9d2b60, f1a2b3c4d5e6
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d34e8a7f2c91"
down_revision: Union[str, Sequence[str], None] = (
    "a41c7e9d2b60",
    "f1a2b3c4d5e6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("budget_exchange_rate", sa.Numeric(12, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "budget_exchange_rate")
