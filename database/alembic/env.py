"""
Alembic environment configuration for TradeStream database migrations.

Supports both online (connected) and offline (SQL generation) migration modes.
Connection parameters are read from environment variables via the shared
credentials module.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from services.shared.credentials import PostgresConfig

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_url():
    """Build database URL from the shared credentials module."""
    pg = PostgresConfig()
    return pg.dsn


def run_migrations_offline():
    """Run migrations in 'offline' mode (generates SQL without connecting)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode (connects to database)."""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
