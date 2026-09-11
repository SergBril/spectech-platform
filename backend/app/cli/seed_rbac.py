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
from sqlalchemy import delete, func, select

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


def seed_vehicles():
    """Создать тестовую технику с правильной структурой полей."""
    from app.models.catalog import Category, Vehicle

    db = SessionLocal()
    try:
        print("\n🚜 Начинаем seed техники...")

        # Проверяем, есть ли уже техника
        existing_count = db.execute(select(func.count(Vehicle.id))).scalar()
        if existing_count > 0:
            print(f"  ⚠️  В базе уже есть {existing_count} единиц техники, пропускаем")
            return

        # Создаём категории (если их нет)
        categories_data = [
            {"name": "Экскаватор", "code": "excavator"},
            {"name": "Самосвал", "code": "dump_truck"},
            {"name": "Автокран", "code": "crane"},
            {"name": "Бульдозер", "code": "bulldozer"},
            {"name": "Погрузчик", "code": "loader"},
        ]

        category_objects = {}
        for cat_data in categories_data:
            cat = db.execute(
                select(Category).where(Category.code == cat_data["code"])
            ).scalar_one_or_none()
            if not cat:
                cat = Category(**cat_data)
                db.add(cat)
                db.flush()
                print(f"  ➕ Категория: {cat_data['name']}")
            else:
                print(f"  ✅ Категория: {cat_data['name']} (уже есть)")
            category_objects[cat_data["code"]] = cat

        # ✅ ПРАВИЛЬНАЯ структура Vehicle (id_type + id_value)
        vehicles_data = [
            {
                "id_type": "license_plate",
                "id_value": "А123БВ777",
                "name": "Экскаватор CAT 320D",
                "category_id": category_objects["excavator"].id,
                "status": "free",
                "year": 2020,
                "fuel_norm_per_hour": 15.50,
            },
            {
                "id_type": "VIN",
                "id_value": "XTA21099042512345",
                "name": "Самосвал КАМАЗ 65115",
                "category_id": category_objects["dump_truck"].id,
                "status": "busy",
                "year": 2019,
                "fuel_norm_per_100km": 35.00,
            },
            {
                "id_type": "inventory",
                "id_value": "INV-001-2021",
                "name": "Автокран Liebherr LTM 1100",
                "category_id": category_objects["crane"].id,
                "status": "maintenance",
                "year": 2021,
                "fuel_norm_per_hour": 25.00,
            },
            {
                "id_type": "license_plate",
                "id_value": "Е456ГД777",
                "name": "Бульдозер Komatsu D65",
                "category_id": category_objects["bulldozer"].id,
                "status": "free",
                "year": 2022,
                "fuel_norm_per_hour": 20.00,
            },
        ]

        for v_data in vehicles_data:
            vehicle = Vehicle(**v_data)
            db.add(vehicle)
            print(
                f"  🚜 Техника: {v_data['name']} ({v_data['id_type']}: {v_data['id_value']})"
            )

        db.commit()
        print(f"\n✅ Создано {len(vehicles_data)} единиц техники")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Вызываем только один раз!
    seed()
    seed_vehicles()
