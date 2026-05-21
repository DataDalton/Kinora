"""
Alembic environment configuration for database migrations.

Uses SQLAlchemy Core metadata for autogenerate, runs migrations synchronously.
"""

import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy import create_engine

from alembic import context

# Import the metadata from our models
from app.db.models import metadata

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = metadata


def getUrl() -> str:
    """Get database URL from environment (direct PostgreSQL, not PgBouncer).

    Defaults to localhost:5432 for local development.
    In Docker, DATABASE_URL points to the postgres container.
    """
    return os.environ.get("DATABASE_URL", "postgresql://kinora:kinora_password@localhost:5432/kinora")


def runMigrationsOffline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the SQL to the script output.
    """
    url = getUrl()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def runMigrationsOnline() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = create_engine(
        getUrl(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    runMigrationsOffline()
else:
    runMigrationsOnline()
