"""replace single user role with roles JSON array

Revision ID: 6b8c1d2e3f40
Revises: f1a2b3c4d5e6
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6b8c1d2e3f40"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("roles", sa.JSON(), nullable=True),
    )
    op.execute("UPDATE users SET roles = json_build_array(role::text)")
    op.alter_column("users", "roles", nullable=False)
    op.drop_column("users", "role")


def downgrade() -> None:
    connection = op.get_bind()
    multi_role_users = connection.execute(
        sa.text("SELECT count(*) FROM users WHERE json_array_length(roles) <> 1")
    ).scalar_one()
    if multi_role_users:
        raise RuntimeError(
            "Cannot downgrade while users have multiple roles; "
            "remove extra roles before retrying."
        )

    op.execute("ALTER TABLE users ADD COLUMN role user_role")
    op.execute("UPDATE users SET role = (roles->>0)::user_role")
    op.alter_column("users", "role", nullable=False)
    op.drop_column("users", "roles")
