import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import UTC, date, datetime, timedelta

import bcrypt
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor, Employee
from app.models.dispatch import Request
from app.models.rbac import Role, UserRole
from app.services.rbac_service import init_system_data


def create_seed_data():
    db = SessionLocal()

    try:
        print("🔍 Проверка существующих данных...")

        # Инициализация системных ролей и прав
        init_system_data(db)
        print("   ✅ Системные роли и права инициализированы")

        # --- Компания ---
        company = db.scalar(select(Company).where(Company.name == "СпецТехника Про"))
        if not company:
            company = Company(
                name="СпецТехника Про",
                legal_name='ООО "СпецТехника Про"',
                inn="7700000000",
            )
            db.add(company)
            db.flush()
            print("   ✅ Компания создана")
        else:
            print(f"   ⏭️  Компания уже существует (id={company.id})")

        # --- Администратор ---
        admin = db.scalar(select(User).where(User.email == "admin@spectech.dev"))
        if not admin:
            admin_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
            admin = User(
                email="admin@spectech.dev",
                full_name="Администратор",
                password_hash=admin_password,
                company_id=company.id,
                is_superuser=True,
            )
            db.add(admin)
            db.flush()
            print("   ✅ Администратор создан")
        else:
            print(f"   ⏭️  Администратор уже существует (id={admin.id})")

        # --- Категории ---
        cat_earth = db.scalar(select(Category).where(Category.code == "earthmoving"))
        if not cat_earth:
            cat_earth = Category(
                name="Землеройная техника",
                code="earthmoving",
                level=1,
                company_id=company.id,
            )
            db.add(cat_earth)
            db.flush()
            print("   ✅ Категория 'Землеройная техника' создана")
        else:
            print("   ⏭️  Категория 'Землеройная техника' уже существует")

        cat_excavator = db.scalar(select(Category).where(Category.code == "excavators"))
        if not cat_excavator:
            cat_excavator = Category(
                name="Экскаваторы",
                code="excavators",
                level=2,
                parent_id=cat_earth.id,
                company_id=company.id,
            )
            db.add(cat_excavator)
            db.flush()
            print("   ✅ Категория 'Экскаваторы' создана")
        else:
            print("   ⏭️  Категория 'Экскаваторы' уже существует")

        # --- Клиент ---
        client = db.scalar(select(Contractor).where(Contractor.inn == "7711111111"))
        if not client:
            client = Contractor(
                type="client",
                name='ООО "СтройЗаказчик"',
                inn="7711111111",
                company_id=company.id,
            )
            db.add(client)
            db.flush()
            print("   ✅ Клиент создан")
        else:
            print(f"   ⏭️  Клиент уже существует (id={client.id})")

        # --- Собственник ---
        owner = db.scalar(select(Contractor).where(Contractor.inn == "772222222222"))
        if not owner:
            owner = Contractor(
                type="owner",
                name="ИП Петров",
                inn="772222222222",
                company_id=company.id,
                contact_name="Петров Иван Иванович",
                contact_phone="+79001234567",
            )
            db.add(owner)
            db.flush()
            print("   ✅ Собственник создан")
        else:
            print(f"   ⏭️  Собственник уже существует (id={owner.id})")

        # --- Оператор ---
        operator_contractor = db.scalar(
            select(Contractor).where(Contractor.name == "Сидоров Алексей")
        )
        if not operator_contractor:
            operator_contractor = Contractor(
                type="employee",
                name="Сидоров Алексей",
                company_id=company.id,
            )
            db.add(operator_contractor)
            db.flush()

            operator = Employee(
                contractor_id=operator_contractor.id,
                position="Машинист экскаватора",
                role_in_system="operator",
                hire_date=date(2024, 1, 15),
            )
            db.add(operator)
            print("   ✅ Оператор создан")
        else:
            print(f"   ⏭️  Оператор уже существует (id={operator_contractor.id})")

        # --- Техника ---
        vehicle1 = db.scalar(
            select(Vehicle).where(Vehicle.id_value == "X893AB123456789")
        )
        if not vehicle1:
            vehicle1 = Vehicle(
                id_type="vin",
                id_value="X893AB123456789",
                category_id=cat_excavator.id,
                name="Экскаватор CAT 320D",
                year=2020,
                status="free",
                company_id=company.id,
            )
            db.add(vehicle1)
            db.flush()
            print("   ✅ Техника 'Экскаватор CAT 320D' создана")
        else:
            print("   ⏭️  Техника 'Экскаватор CAT 320D' уже существует")

        # --- Заявка ---
        now = datetime.now(UTC)
        existing_request = db.scalar(
            select(Request).where(
                Request.object_address == "г. Москва, ул. Строителей, д. 1"
            )
        )

        if not existing_request:
            request = Request(
                client_id=client.id,
                status="new",
                request_type="one_time",
                vehicle_category_id=cat_excavator.id,
                work_type="Планировка участка",
                object_address="г. Москва, ул. Строителей, д. 1",
                planned_start=now + timedelta(days=1),
                planned_end=now + timedelta(days=1, hours=8),
                shift_duration_hours=8,
                client_rate=15000,
                rate_type="per_shift",
                estimated_amount=15000,
                source_channel="phone",
                priority="normal",
                company_id=company.id,
                created_by=admin.id,
            )
            db.add(request)
            print("   ✅ Заявка создана")
        else:
            print(f"   ⏭️  Заявка уже существует (id={existing_request.id})")

        # --- Назначение роли администратора ---
        admin_role = db.scalar(select(Role).where(Role.code == "admin"))
        if admin_role:
            existing = db.scalar(
                select(UserRole).where(
                    UserRole.user_id == admin.id,
                    UserRole.role_id == admin_role.id,
                )
            )
            if not existing:
                db.add(
                    UserRole(
                        user_id=admin.id,
                        role_id=admin_role.id,
                    )
                )
                print("   ✅ Роль admin назначена администратору")
            else:
                print("   ⏭️  Роль admin уже назначена")

        db.commit()

        print("\n✅ Seed-данные успешно обработаны!")
        print("   Админ: admin@spectech.dev / admin123")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Ошибка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_seed_data()
