import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ВАЖНО: добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем Base и ВСЕ модели
from app.core.db import Base
from app.models.auth import User, UserSession
from app.models.company import Company
from app.models.catalog import Category, Vehicle
from app.models.contractor import Contractor, Employee, EmployeeCertificate
from app.models.dispatch import Request, RequestStatusLog, RequestAssignment
from app.models.shift import ShiftTask, ShiftReport
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.finance import Invoice, InvoiceItem, Act, Payout, Payment
from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    EngineHoursLog, Alert, Notification, AlertRule,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные всех моделей
target_metadata = Base.metadata

# Отладочный вывод (временно)
print(f"📊 Found {len(target_metadata.tables)} tables in Base.metadata:")
for table_name in target_metadata.tables.keys():
    print(f"   - {table_name}")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()