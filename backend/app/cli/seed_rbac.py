"""
CLI-скрипт для наполнения БД: роли, пользователи, права, техника.
Запуск: cd backend && python -m app.cli.seed_rbac
"""

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import bcrypt
from sqlalchemy import delete, func, select, text

from app.core.db import Base, SessionLocal, engine
from app.models import auth, rbac
from app.models.auth import UserStatus


def hash_password(password: str) -> str:
    """Хеширование через bcrypt (совместимо с auth_service.py)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


ROLES = [
    {"code": "admin", "name": "Администратор", "description": "Полный доступ ко всему"},
    {
        "code": "dispatcher",
        "name": "Диспетчер",
        "description": "Управление заявками и техникой",
    },
    {
        "code": "operator",
        "name": "Оператор",
        "description": "Работа со сменными заданиями",
    },
    {
        "code": "client",
        "name": "Клиент",
        "description": "Просмотр своих заявок и документов",
    },
    {
        "code": "owner",
        "name": "Собственник",
        "description": "Просмотр доходов и техники",
    },
    {"code": "mechanic", "name": "Механик", "description": "Осмотр и ремонт техники"},
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
        print("🚀 Начинаем seed пользователей и ролей...")

        # 1. Создаём роли
        role_objects = {}
        for role_data in ROLES:
            role = db.execute(
                select(rbac.Role).where(rbac.Role.code == role_data["code"])
            ).scalar_one_or_none()
            if not role:
                role = rbac.Role(
                    code=role_data["code"],
                    name=role_data["name"],
                    description=role_data.get("description", ""),
                )
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
                user.password_hash = hash_password(u["password"])
                user.full_name = u["name"]
                user.status = UserStatus.active
                user.is_superuser = u["is_superuser"]
                print(f"  🔄 Обновлён: {u['email']}")

            # 3. Удаляем старые связи с ролями и назначаем новую
            db.execute(delete(rbac.UserRole).where(rbac.UserRole.user_id == user.id))
            user_role = rbac.UserRole(
                user_id=user.id,
                role_id=role_objects[u["role_code"]].id,
                is_active=True,
            )
            db.add(user_role)
            print(f"     └─ Роль: {u['role_code']}")

        db.commit()
        print("\n✅ Пользователи и роли обновлены!")
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


def seed_permissions():
    """Создать права и назначить их ролям."""
    db = SessionLocal()
    try:
        print("\n🔐 Начинаем seed прав...")

        # Определяем все необходимые права
        permissions_data = [
            ("vehicles", "view"),
            ("vehicles", "create"),
            ("vehicles", "update"),
            ("vehicles", "delete"),
            ("requests", "view"),
            ("requests", "create"),
            ("requests", "update"),
            ("requests", "delete"),
            ("finance", "view"),
            ("finance", "create"),
            ("finance", "update"),
            ("finance", "delete"),
        ]

        # Создаём права (если их нет)
        permission_objects = {}
        for entity, action in permissions_data:
            perm = db.execute(
                select(rbac.Permission).where(
                    rbac.Permission.entity == entity,
                    rbac.Permission.action == action,
                )
            ).scalar_one_or_none()

            if not perm:
                perm = rbac.Permission(entity=entity, action=action)
                db.add(perm)
                db.flush()
                print(f"  ➕ Право: {entity}:{action}")
            else:
                print(f"  ✅ Право: {entity}:{action} (уже есть)")

            permission_objects[f"{entity}:{action}"] = perm

        # Получаем все роли
        roles = db.execute(select(rbac.Role)).scalars().all()
        role_objects = {r.code: r for r in roles}

        # Матрица прав для каждой роли
        role_permissions_map = {
            "admin": [
                "vehicles:view",
                "vehicles:create",
                "vehicles:update",
                "vehicles:delete",
                "requests:view",
                "requests:create",
                "requests:update",
                "requests:delete",
                "finance:view",
                "finance:create",
                "finance:update",
                "finance:delete",
            ],
            "dispatcher": [
                "vehicles:view",
                "vehicles:create",
                "vehicles:update",
                "requests:view",
                "requests:create",
                "requests:update",
                "finance:view",
            ],
            "mechanic": [
                "vehicles:view",
                "vehicles:update",
                "requests:view",
            ],
            "operator": [
                "vehicles:view",
                "requests:view",
            ],
            "client": [
                "vehicles:view",
                "requests:view",
                "finance:view",
            ],
            "owner": [
                "vehicles:view",
                "requests:view",
                "finance:view",
            ],
        }

        # Назначаем права ролям
        links_added = 0
        for role_code, perm_keys in role_permissions_map.items():
            role = role_objects.get(role_code)
            if not role:
                print(f"  ⚠️  Роль {role_code} не найдена, пропускаем")
                continue

            for perm_key in perm_keys:
                perm = permission_objects.get(perm_key)
                if not perm:
                    continue

                # Проверяем, есть ли уже такая связь
                existing = db.execute(
                    select(rbac.RolePermission).where(
                        rbac.RolePermission.role_id == role.id,
                        rbac.RolePermission.permission_id == perm.id,
                    )
                ).scalar_one_or_none()

                if not existing:
                    rp = rbac.RolePermission(role_id=role.id, permission_id=perm.id)
                    db.add(rp)
                    links_added += 1
                    print(f"  🔗 {role_code} ← {perm_key}")

        db.commit()
        print(f"\n✅ Права назначены ролям! (добавлено {links_added} связей)")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


def seed_vehicles():
    """Создать тестовую технику."""
    from app.models.catalog import Category, Vehicle

    db = SessionLocal()
    try:
        print("\n🚜 Начинаем seed техники...")

        existing_count = db.execute(select(func.count(Vehicle.id))).scalar()
        if existing_count > 0:
            print(f"  ⚠️  В базе уже есть {existing_count} единиц техники, пропускаем")
            return

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


def seed_finances():
    """Создать тестовые счета, акты и выплаты."""
    from app.models.catalog import Vehicle
    from app.models.dispatch import Request
    from app.models.finance import Act, Invoice, Payout

    db = SessionLocal()
    try:
        print("\n💰 Начинаем seed финансовых данных...")

        # Проверяем, есть ли уже финансовые данные
        existing_invoices = db.execute(select(func.count(Invoice.id))).scalar()
        if existing_invoices > 0:
            print(f"  ⚠️  В базе уже есть {existing_invoices} счетов, пропускаем")
            return

        # Получаем заявки, контрагента и технику
        requests_list = db.execute(select(Request).order_by(Request.id)).scalars().all()
        if not requests_list:
            print("  ⚠️  В базе нет заявок")
            return

        contractor_result = db.execute(
            text("SELECT id FROM contractors WHERE inn = '7700000000' LIMIT 1")
        ).fetchone()
        if not contractor_result:
            print("  ⚠️  Контрагент не найден")
            return

        # Получаем первую доступную технику (для выплат)
        vehicle = db.execute(select(Vehicle).order_by(Vehicle.id)).scalars().first()
        if not vehicle:
            print("  ⚠️  В базе нет техники")
            return

        contractor_id = contractor_result[0]
        request_ids = [r.id for r in requests_list]
        vehicle_id = vehicle.id
        print(
            f"  📋 Заявки: {request_ids}, Контрагент: {contractor_id}, Техника: #{vehicle_id}"
        )

        # === Счета (Invoices) ===
        invoices_data = [
            {
                "document_number": "СЧ-001",
                "request_id": request_ids[0],
                "client_id": contractor_id,
                "subtotal": "40000.00",
                "vat_amount": "8000.00",
                "vat_rate": "20.00",
                "total": "48000.00",
                "paid_amount": "48000.00",
                "invoice_date": "2026-09-10",
                "due_date": "2026-09-20",
                "status": "paid",
                "comment": "Оплачен: земляные работы",
            },
            {
                "document_number": "СЧ-002",
                "request_id": request_ids[0],
                "client_id": contractor_id,
                "subtotal": "62900.00",
                "vat_amount": "12580.00",
                "vat_rate": "20.00",
                "total": "75480.00",
                "paid_amount": "0.00",
                "invoice_date": "2026-09-11",
                "due_date": "2026-09-25",
                "status": "sent",
                "comment": "Ожидает оплаты",
            },
            {
                "document_number": "СЧ-003",
                "request_id": request_ids[0],
                "client_id": contractor_id,
                "subtotal": "25000.00",
                "vat_amount": "5000.00",
                "vat_rate": "20.00",
                "total": "30000.00",
                "paid_amount": "0.00",
                "invoice_date": "2026-09-01",
                "due_date": "2026-09-10",
                "status": "overdue",
                "comment": "Просрочен",
            },
            {
                "document_number": "СЧ-004",
                "request_id": request_ids[-1],
                "client_id": contractor_id,
                "subtotal": "50000.00",
                "vat_amount": "10000.00",
                "vat_rate": "20.00",
                "total": "60000.00",
                "paid_amount": "30000.00",
                "invoice_date": "2026-09-08",
                "due_date": "2026-09-18",
                "status": "partially_paid",
                "comment": "Частичная оплата",
            },
        ]

        for inv_data in invoices_data:
            db.add(Invoice(**inv_data))
            print(
                f"  💰 Счёт: {inv_data['document_number']} ({inv_data['total']} ₽, {inv_data['status']})"
            )

        # === Акты (Acts) ===
        # Поле суммы: total_amount (НЕ total)
        acts_data = [
            {
                "document_number": "АКТ-001",
                "request_id": request_ids[0],
                "client_id": contractor_id,
                "total_amount": "48000.00",  # ← ПРАВИЛЬНОЕ имя поля
                "act_date": "2026-09-10",
                "status": "paid",
                "comment": "Работы выполнены",
            },
            {
                "document_number": "АКТ-002",
                "request_id": request_ids[0],
                "client_id": contractor_id,
                "total_amount": "75480.00",
                "act_date": "2026-09-11",
                "status": "sent",
                "comment": "Ожидает подписи",
            },
        ]

        for act_data in acts_data:
            db.add(Act(**act_data))
            print(
                f"  📄 Акт: {act_data['document_number']} ({act_data['total_amount']} ₽, {act_data['status']})"
            )

        # === Выплаты (Payouts) ===
        # Обязательные поля: owner_id, vehicle_id, gross_amount, platform_commission, net_amount, commission_rate
        payouts_data = [
            {
                "document_number": "ВП-001",
                "owner_id": contractor_id,  # ← НЕ contractor_id!
                "vehicle_id": vehicle_id,
                "request_id": request_ids[0],
                "gross_amount": "25000.00",
                "platform_commission": "5000.00",  # 20% комиссия платформы
                "net_amount": "20000.00",
                "commission_rate": "20.00",
                "payout_date": "2026-09-10",
                "status": "paid",
                "comment": "Выплачено оператору",
            },
            {
                "document_number": "ВП-002",
                "owner_id": contractor_id,
                "vehicle_id": vehicle_id,
                "request_id": (
                    request_ids[-1] if len(request_ids) > 1 else request_ids[0]
                ),
                "gross_amount": "18750.00",
                "platform_commission": "3750.00",
                "net_amount": "15000.00",
                "commission_rate": "20.00",
                "payout_date": "2026-09-11",
                "status": "draft",
                "comment": "Ожидает одобрения",
            },
        ]

        for pay_data in payouts_data:
            db.add(Payout(**pay_data))
            print(
                f"  💸 Выплата: {pay_data['document_number']} (net: {pay_data['net_amount']} ₽)"
            )

        db.commit()
        print(
            f"\n✅ Создано: {len(invoices_data)} счетов, {len(acts_data)} актов, {len(payouts_data)} выплат"
        )

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
    seed_permissions()
    seed_vehicles()
    seed_finances()
