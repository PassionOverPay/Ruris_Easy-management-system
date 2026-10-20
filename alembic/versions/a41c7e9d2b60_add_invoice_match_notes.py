"""add invoice match notes

Revision ID: a41c7e9d2b60
Revises: 8d2f4a6b1c30
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a41c7e9d2b60"
down_revision: Union[str, Sequence[str], None] = "8d2f4a6b1c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("match_notes", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "match_notes")
