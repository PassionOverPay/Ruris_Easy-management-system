"""create exchange rates table

Revision ID: e5f6a7b8c9d0
Revises: d34e8a7f2c91
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d34e8a7f2c91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("currency_pair", sa.String(length=7), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_exchange_rates_date"),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
