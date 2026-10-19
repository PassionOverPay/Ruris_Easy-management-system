"""add user provisioning fields and admin role

Revision ID: 92d5a1b3c847
Revises: c0702fec78cf
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "92d5a1b3c847"
down_revision: Union[str, Sequence[str], None] = "c0702fec78cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin'")
    op.add_column(
        "users",
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    )
    op.execute("UPDATE users SET full_name = email WHERE full_name IS NULL")
    op.execute(
        "UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )
    op.alter_column("users", "full_name", nullable=False)
    op.alter_column("users", "created_at", nullable=False)


def downgrade() -> None:
    op.execute(
        "CREATE TYPE user_role_without_admin AS ENUM "
        "('purchasing', 'warehouse', 'accounting')"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_role_without_admin "
        "USING role::text::user_role_without_admin"
    )
    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_without_admin RENAME TO user_role")
    op.drop_column("users", "created_at")
    op.drop_column("users", "full_name")
