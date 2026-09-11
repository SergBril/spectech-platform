"""
CLI-скрипт для наполнения БД базовыми ролями RBAC и тестовыми пользователями.
Запуск: python -m app.cli.seed_rbac
"""

import os
import sys

# Добавляем корень backend в PATH для корректного импорта
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from passlib.context import CryptContext
from sqlalchemy import select

from app.core.db import Base, SessionLocal, engine

# Импортируем ВСЕ модели, чтобы они зарегистрировались в Base.metadata
from app.models import (
    auth,
    rbac,
)
from app.models.auth import UserStatus  # ← импорт enum'а статусов

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 6 ролей из README
ROLES = [
    {"code": "admin", "name": "Администратор"},
    {"code": "dispatcher", "name": "Диспетчер"},
    {"code": "operator", "name": "Оператор"},
    {"code": "client", "name": "Клиент"},
    {"code": "owner", "name": "Собственник"},
    {"code": "mechanic", "name": "Механик"},
]

TEST_USERS = [
    {
        "email": "admin@spectech.dev",
        "password": "admin123",
        "role_code": "admin",
        "name": "Главный Админ",
    },
    {
        "email": "dispatcher@spectech.dev",
        "password": "pass123",
        "role_code": "dispatcher",
        "name": "Иван Диспетчеров",
    },
    {
        "email": "mechanic@spectech.dev",
        "password": "pass123",
        "role_code": "mechanic",
        "name": "Петр Механиков",
    },
]


def ensure_tables_exist():
    """Создаёт таблицы, если их нет (fallback для случаев, когда Alembic не отработал)."""
    print("🔧 Проверяем существование таблиц...")
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы готовы")


def seed_roles_and_users():
    """Синхронное сидирование БД."""
    ensure_tables_exist()

    db = SessionLocal()
    try:
        print("🚀 Начинаем сидирование RBAC...")

        # 1. Создаем роли
        role_objects = {}
        for role_data in ROLES:
            stmt = select(rbac.Role).where(rbac.Role.code == role_data["code"])
            role = db.execute(stmt).scalar_one_or_none()

            if not role:
                role = rbac.Role(code=role_data["code"], name=role_data["name"])
                db.add(role)
                db.flush()
                print(f"  ➕ Создана роль: {role_data['code']} ({role_data['name']})")
            else:
                print(f"  ✅ Роль {role_data['code']} уже существует")
            role_objects[role_data["code"]] = role

        # 2. Создаем тестовых пользователей
        for u in TEST_USERS:
            stmt = select(auth.User).where(auth.User.email == u["email"])
            user = db.execute(stmt).scalar_one_or_none()

            if not user:
                # ✅ Используем правильные поля модели User
                user = auth.User(
                    email=u["email"],
                    password_hash=pwd_context.hash(u["password"]),  # ✅ правильное поле
                    full_name=u["name"],
                    status=UserStatus.active,  # ✅ вместо is_active
                    is_superuser=(u["role_code"] == "admin"),  # ✅ это поле есть
                )
                db.add(user)
                db.flush()

                # Назначаем роль (UserRole имеет is_active)
                user_role = rbac.UserRole(
                    user_id=user.id,
                    role_id=role_objects[u["role_code"]].id,
                    is_active=True,  # ← это поле в таблице user_roles, не в users
                )
                db.add(user_role)
                print(f"  👤 Создан пользователь: {u['email']} ({u['role_code']})")
            else:
                print(f"  ⚠️  Пользователь {u['email']} уже существует, пропускаем")

        db.commit()
        print("\n✅ RBAC роли и тестовые пользователи успешно добавлены в БД!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка при сидировании: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_users()
