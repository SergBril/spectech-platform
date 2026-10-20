"""Расширенный seed скрипт с реальными данными."""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.user_company import UserCompany


def seed_companies(db):
    companies_data = [
        {
            "name": "ООО СпецТех Москва",
            "legal_name": "Общество с ограниченной ответственностью Специальная Техника",
            "inn": "7707083893",
            "default_tax_system": "osno",
        },
        {
            "name": "ИП Иванов А.В.",
            "legal_name": "Индивидуальный предприниматель Иванов Алексей Владимирович",
            "inn": "771234567890",
            "default_tax_system": "usn_6",
        },
        {
            "name": "ООО СтройМастер",
            "legal_name": "Общество с ограниченной ответственностью СтройМастер",
            "inn": "5024123456",
            "default_tax_system": "usn_15",
        },
    ]
    created = 0
    for data in companies_data:
        existing = db.scalar(select(Company).where(Company.inn == data["inn"]))
        if not existing:
            db.add(Company(**data, is_active=True))
            created += 1
    if created > 0:
        db.commit()
        print(f"✅ Created {created} companies")
    else:
        print("ℹ️  Companies already exist")
    return db.query(Company).all()


def seed_categories(db, companies):
    if not companies:
        return []
    # company_id=4 — это первая существующая компания "СпецТехника Про"
    first_company_id = companies[0].id if companies else 1
    categories_data = [
        {
            "name": "Экскаваторы",
            "code": "EXCAVATOR",
            "level": 1,
            "company_id": first_company_id,
        },
        {
            "name": "Самосвалы",
            "code": "DUMP_TRUCK",
            "level": 1,
            "company_id": first_company_id,
        },
        {
            "name": "Автокраны",
            "code": "CRANE",
            "level": 1,
            "company_id": first_company_id,
        },
        {
            "name": "Бульдозеры",
            "code": "BULLDOZER",
            "level": 1,
            "company_id": first_company_id,
        },
        {
            "name": "Погрузчики",
            "code": "LOADER",
            "level": 1,
            "company_id": first_company_id,
        },
    ]
    created = 0
    for data in categories_data:
        existing = db.scalar(select(Category).where(Category.code == data["code"]))
        if not existing:
            db.add(Category(**data, is_active=True))
            created += 1
    if created > 0:
        db.commit()
        print(f"✅ Created {created} categories")
    else:
        print("ℹ️  Categories already exist")
    return db.query(Category).all()


def seed_vehicles(db, companies, categories):
    if not companies:
        return
    # Берём первую компанию (id=4 "СпецТехника Про") и вторую (id=5)
    cid1 = companies[0].id
    cid2 = companies[1].id if len(companies) > 1 else companies[0].id

    cat_map = {c.code: c.id for c in categories} if categories else {}

    vehicles_data = [
        {
            "id_type": "license_plate",
            "id_value": "А123БВ777",
            "name": "Экскаватор CAT 320D",
            "year": 2020,
            "status": "free",
            "fuel_norm_per_hour": 15.5,
            "company_id": cid1,
            "category_id": cat_map.get("EXCAVATOR"),
        },
        {
            "id_type": "license_plate",
            "id_value": "В456ГД777",
            "name": "Самосвал КАМАЗ 65115",
            "year": 2019,
            "status": "busy",
            "fuel_norm_per_100km": 35.0,
            "company_id": cid1,
            "category_id": cat_map.get("DUMP_TRUCK"),
        },
        {
            "id_type": "license_plate",
            "id_value": "Е789ЖЗ777",
            "name": "Автокран Liebherr LTM 1100",
            "year": 2021,
            "status": "maintenance",
            "fuel_norm_per_hour": 25.0,
            "company_id": cid1,
            "category_id": cat_map.get("CRANE"),
        },
        {
            "id_type": "license_plate",
            "id_value": "К012ЛМ550",
            "name": "Экскаватор Komatsu PC200",
            "year": 2018,
            "status": "free",
            "fuel_norm_per_hour": 18.0,
            "company_id": cid2,
            "category_id": cat_map.get("EXCAVATOR"),
        },
        {
            "id_type": "license_plate",
            "id_value": "Н345ОП550",
            "name": "Бульдозер CAT D6",
            "year": 2022,
            "status": "busy",
            "fuel_norm_per_hour": 20.0,
            "company_id": cid2,
            "category_id": cat_map.get("BULLDOZER"),
        },
        {
            "id_type": "license_plate",
            "id_value": "Р678СТ777",
            "name": "Погрузчик JCB 3CX",
            "year": 2021,
            "status": "free",
            "fuel_norm_per_hour": 12.0,
            "company_id": cid1,
            "category_id": cat_map.get("LOADER"),
        },
    ]
    created = 0
    for data in vehicles_data:
        existing = db.scalar(
            select(Vehicle).where(Vehicle.id_value == data["id_value"])
        )
        if not existing:
            db.add(Vehicle(**data))
            created += 1
    if created > 0:
        db.commit()
        print(f"✅ Created {created} vehicles")
    else:
        print("ℹ️  Vehicles already exist")


def seed_contractors(db, companies):
    if not companies:
        return
    cid1 = companies[0].id
    cid2 = companies[1].id if len(companies) > 1 else companies[0].id

    contractors_data = [
        {
            "name": "ООО Заказчик 1",
            "inn": "7710123456",
            "type": "client",
            "email": "client1@example.com",
            "contact_name": "Петров П.П.",
            "contact_phone": "+7 (999) 123-45-67",
            "company_id": cid1,
        },
        {
            "name": "ООО Заказчик 2",
            "inn": "7720987654",
            "type": "client",
            "email": "client2@example.com",
            "contact_name": "Сидоров С.С.",
            "contact_phone": "+7 (999) 234-56-78",
            "company_id": cid1,
        },
        {
            "name": "ИП Поставщик",
            "inn": "773012345678",
            "type": "subcontractor",
            "email": "supplier@example.com",
            "contact_name": "Иванов И.И.",
            "contact_phone": "+7 (999) 345-67-89",
            "company_id": cid1,
        },
        {
            "name": "ООО СтройЗаказ",
            "inn": "5030987654",
            "type": "client",
            "email": "stroy@example.com",
            "contact_name": "Кузнецов К.К.",
            "contact_phone": "+7 (999) 456-78-90",
            "company_id": cid2,
        },
        {
            "name": "ООО МегаСтрой",
            "inn": "7740112233",
            "type": "client",
            "email": "mega@example.com",
            "contact_name": "Орлов О.О.",
            "contact_phone": "+7 (999) 567-89-01",
            "company_id": cid1,
        },
    ]
    created = 0
    for data in contractors_data:
        existing = db.scalar(select(Contractor).where(Contractor.inn == data["inn"]))
        if not existing:
            db.add(Contractor(**data, is_active=True))
            created += 1
    if created > 0:
        db.commit()
        print(f"✅ Created {created} contractors")
    else:
        print("ℹ️  Contractors already exist")


def seed_user_companies(db, companies):
    if not companies:
        return
    users = db.query(User).all()
    created = 0
    for user in users:
        for company in companies:
            existing = db.scalar(
                select(UserCompany).where(
                    UserCompany.user_id == user.id, UserCompany.company_id == company.id
                )
            )
            if not existing:
                db.add(
                    UserCompany(user_id=user.id, company_id=company.id, is_active=True)
                )
                created += 1
    if created > 0:
        db.commit()
        print(f"✅ Created {created} user-company links")
    else:
        print("ℹ️  User-company links already exist")


def run_full_seed():
    db = SessionLocal()
    try:
        print("🌱 Starting full seed...")
        companies = seed_companies(db)
        print(f"📊 Companies in DB: {len(companies)}")
        for c in companies:
            print(f"   - {c.id}: {c.name} (inn={c.inn})")

        categories = seed_categories(db, companies)
        seed_vehicles(db, companies, categories)
        seed_contractors(db, companies)
        seed_user_companies(db, companies)

        print("\n=== Итог ===")
        print(f"Companies: {db.query(Company).count()}")
        print(f"Users: {db.query(User).count()}")
        print(f"Vehicles: {db.query(Vehicle).count()}")
        print(f"Contractors: {db.query(Contractor).count()}")
        print(f"Categories: {db.query(Category).count()}")
        print(f"UserCompany: {db.query(UserCompany).count()}")

        print("\n🎉 Full seed completed!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    run_full_seed()
