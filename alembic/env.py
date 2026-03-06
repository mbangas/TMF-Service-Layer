"""Alembic environment configuration — async SQLAlchemy with asyncpg."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all ORM models so Alembic detects them for autogenerate ────────────
# Keep these imports here; add new domain models as modules are added.
from src.shared.db.base import Base  # noqa: E402
import src.catalog.models.orm  # noqa: E402, F401  — registers catalog tables
import src.order.models.orm  # noqa: E402, F401  — registers order tables

target_metadata = Base.metadata

# ── DATABASE_URL override ─────────────────────────────────────────────────────
# Allow overriding the URL from the environment (used by docker-compose / CI).
def get_url() -> str:
    """Return the database URL from environment or alembic.ini."""
    return os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))


# ── Offline migrations (SQL script generation) ────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection.

    Generates SQL DDL to stdout for review or manual execution.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (live DB) ───────────────────────────────────────────────
def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within its connection."""
    connectable = create_async_engine(get_url(), echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry-point for Alembic when a live connection is available."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
