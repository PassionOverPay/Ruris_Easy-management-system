"""add user active status

Revision ID: 7c9d2e4f5a61
Revises: 6b8c1d2e3f40
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c9d2e4f5a61"
down_revision: Union[str, Sequence[str], None] = "6b8c1d2e3f40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("users", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_active")
