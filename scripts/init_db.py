#!/usr/bin/env python3
"""
Инициализация базы данных для Docker окружения.
Запускает миграции Alembic и создаёт начальные данные.
"""

import subprocess
import sys
import time


def wait_for_db():
    """Ждёт пока БД будет готова."""
    print("⏳ Waiting for database...")
    for i in range(30):
        try:
            result = subprocess.run(
                ["pg_isready", "-h", "postgres", "-U", "spectech"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                print("✅ Database is ready!")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("❌ Database not ready after 30 seconds")
    return False


def run_migrations():
    """Запускает Alembic миграции."""
    print("\n🔄 Running migrations...")
    result = subprocess.run(["alembic", "upgrade", "head"], cwd="/app")
    if result.returncode == 0:
        print("✅ Migrations completed!")
        return True
    else:
        print("❌ Migrations failed!")
        return False


def seed_data():
    """Создаёт начальные данные."""
    print("\n🌱 Seeding initial data...")
    result = subprocess.run(["python", "-m", "app.scripts.seed"], cwd="/app")
    if result.returncode == 0:
        print("✅ Seed data created!")
        return True
    else:
        print("⚠️  Seed script not found or failed (this is OK)")
        return True


if __name__ == "__main__":
    if not wait_for_db():
        sys.exit(1)

    if not run_migrations():
        sys.exit(1)

    seed_data()

    print("\n🎉 Database initialization complete!")
