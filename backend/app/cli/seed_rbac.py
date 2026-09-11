"""
CLI-скрипт для создания/обновления тестовых пользователей и назначения ролей.
Запуск: cd backend && python -m app.cli.seed_rbac
"""

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import bcrypt
from sqlalchemy import delete, select

from app.core.db import Base, SessionLocal, engine
from app.models import auth, rbac
from app.models.auth import UserStatus


def hash_password(password: str) -> str:
    """Хеширование через bcrypt (совместимо с auth_service.py)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
        "is_superuser": True,
    },
    {
        "email": "dispatcher@spectech.dev",
        "password": "pass123",
        "role_code": "dispatcher",
        "name": "Иван Диспетчеров",
        "is_superuser": False,
    },
    {
        "email": "mechanic@spectech.dev",
        "password": "pass123",
        "role_code": "mechanic",
        "name": "Петр Механиков",
        "is_superuser": False,
    },
    {
        "email": "operator@spectech.dev",
        "password": "pass123",
        "role_code": "operator",
        "name": "Ольга Операторова",
        "is_superuser": False,
    },
]


def seed():
    """Создать/обновить пользователей и назначить роли."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("🚀 Начинаем seed...")

        # 1. Создаём роли
        role_objects = {}
        for role_data in ROLES:
            role = db.execute(
                select(rbac.Role).where(rbac.Role.code == role_data["code"])
            ).scalar_one_or_none()
            if not role:
                role = rbac.Role(code=role_data["code"], name=role_data["name"])
                db.add(role)
                db.flush()
                print(f"  ➕ Роль: {role_data['code']}")
            else:
                print(f"  ✅ Роль: {role_data['code']} (уже есть)")
            role_objects[role_data["code"]] = role

        # 2. Создаём/обновляем пользователей
        for u in TEST_USERS:
            user = db.execute(
                select(auth.User).where(auth.User.email == u["email"])
            ).scalar_one_or_none()

            if not user:
                user = auth.User(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    full_name=u["name"],
                    status=UserStatus.active,
                    is_superuser=u["is_superuser"],
                )
                db.add(user)
                db.flush()
                print(f"  👤 Создан: {u['email']}")
            else:
                # Обновляем пароль и данные
                user.password_hash = hash_password(u["password"])
                user.full_name = u["name"]
                user.status = UserStatus.active
                user.is_superuser = u["is_superuser"]
                print(f"  🔄 Обновлён: {u['email']}")

            # 3. Удаляем старые роли и назначаем новую
            db.execute(delete(rbac.UserRole).where(rbac.UserRole.user_id == user.id))
            user_role = rbac.UserRole(
                user_id=user.id, role_id=role_objects[u["role_code"]].id, is_active=True
            )
            db.add(user_role)
            print(f"     └─ Роль: {u['role_code']}")

        db.commit()
        print("\n✅ Seed завершён успешно!")
        print("\n📋 Тестовые аккаунты:")
        for u in TEST_USERS:
            print(f"   {u['email']:30s} | {u['password']:10s} | {u['role_code']}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
