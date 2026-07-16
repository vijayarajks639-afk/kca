"""Alembic environment for the KCA local stack.

No ORM metadata is registered yet — migrations are hand-written until the first
schema-owning work package lands. The database URL comes from KCA_DATABASE_URL
when set, otherwise the compose-stack default in alembic.ini.
"""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

env_url = os.environ.get("KCA_DATABASE_URL")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
