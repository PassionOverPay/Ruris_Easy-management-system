import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "backend"))
load_dotenv(repo_root / ".env.local")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app import models  # noqa: E402,F401

target_metadata = SQLModel.metadata


def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required for migrations. "
            "Set it in the process environment or root .env.local."
        )

    url = make_url(database_url)
    if url.host and "-pooler" in url.host:
        raise RuntimeError("Alembic migrations must use the direct Neon URL")
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_database_url(), poolclass=NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
