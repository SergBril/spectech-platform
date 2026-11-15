"""Alembic environment configuration for PostgreSQL."""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import Base and all models to register them with metadata
from app.core.db import Base
from app.models import *  # noqa: F401, F403

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from the environment.
# Credentials must not live in source: the previous fallback embedded a
# real database password, which detect-secrets correctly flagged.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Alembic requires an explicit database URL; "
        "set it in .env / .env.prod or export it before running migrations."
    )
config.set_main_option("sqlalchemy.url", database_url)

# Model metadata for 'autogenerate' support
# Регистрируем ВСЕ модели в Base.metadata.
# Без этого autogenerate видит только импортированные модели и молча
# пропускает остальные таблицы: так цепочка миграций и оказалась неполной
# (11 таблиц никогда не попадали в autogenerate).
import importlib as _importlib
import pkgutil as _pkgutil

import app.models as _models

for _mod in _pkgutil.iter_modules(_models.__path__):
    _importlib.import_module(f"app.models.{_mod.name}")

target_metadata = Base.metadata

print(f"[INFO] Found {len(Base.metadata.tables)} tables in Base.metadata:")
for table_name in Base.metadata.tables.keys():
    print(f"   - {table_name}")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
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
