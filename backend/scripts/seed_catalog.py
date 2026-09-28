"""
Seed данные для каталога техники.

Запуск:
    docker-compose exec backend python scripts/seed_catalog.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.catalog import (
    Category,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
)


def seed_categories(db: Session):
    """Создаёт иерархию категорий техники."""

    # Проверяем, есть ли уже данные
    if db.query(Category).count() > 0:
        print("⚠️  Категории уже существуют. Пропускаем.")
        return

    categories_data = [
        # Уровень 1: Корневые категории
        {
            "name": "Землеройная техника",
            "code": "earthmoving",
            "level": 1,
            "icon": "excavator",
            "sort_order": 1,
        },
        {
            "name": "Грузоподъёмная техника",
            "code": "lifting",
            "level": 1,
            "icon": "crane",
            "sort_order": 2,
        },
        {
            "name": "Самосвалы",
            "code": "dump_trucks",
            "level": 1,
            "icon": "truck",
            "sort_order": 3,
        },
        {
            "name": "Дорожная техника",
            "code": "road",
            "level": 1,
            "icon": "roller",
            "sort_order": 4,
        },
        {
            "name": "Буровая техника",
            "code": "drilling",
            "level": 1,
            "icon": "drill",
            "sort_order": 5,
        },
    ]

    # Создаём корневые категории
    root_categories = {}
    for data in categories_data:
        cat = Category(**data)
        db.add(cat)
        db.flush()
        root_categories[data["code"]] = cat.id

    # Уровень 2: Подкатегории
    subcategories_data = [
        # Землеройная техника
        {
            "parent": "earthmoving",
            "name": "Экскаваторы гусеничные",
            "code": "excavator_track",
            "icon": "excavator-track",
        },
        {
            "parent": "earthmoving",
            "name": "Экскаваторы колёсные",
            "code": "excavator_wheel",
            "icon": "excavator-wheel",
        },
        {
            "parent": "earthmoving",
            "name": "Мини-экскаваторы",
            "code": "mini_excavator",
            "icon": "mini-excavator",
        },
        {
            "parent": "earthmoving",
            "name": "Бульдозеры",
            "code": "bulldozer",
            "icon": "bulldozer",
        },
        {
            "parent": "earthmoving",
            "name": "Погрузчики фронтальные",
            "code": "loader_front",
            "icon": "loader",
        },
        # Грузоподъёмная техника
        {
            "parent": "lifting",
            "name": "Автокраны 16-25т",
            "code": "crane_16_25",
            "icon": "crane",
        },
        {
            "parent": "lifting",
            "name": "Автокраны 50т+",
            "code": "crane_50_plus",
            "icon": "crane-heavy",
        },
        {
            "parent": "lifting",
            "name": "Краны-манипуляторы (КМУ)",
            "code": "kmu",
            "icon": "manipulator",
        },
        {
            "parent": "lifting",
            "name": "Автовышки",
            "code": "aerial_platform",
            "icon": "aerial",
        },
        # Самосвалы
        {
            "parent": "dump_trucks",
            "name": "Самосвалы 10-15т",
            "code": "dump_10_15",
            "icon": "dump-truck",
        },
        {
            "parent": "dump_trucks",
            "name": "Самосвалы 20-30т",
            "code": "dump_20_30",
            "icon": "dump-truck-heavy",
        },
        {
            "parent": "dump_trucks",
            "name": "Карьерные самосвалы",
            "code": "dump_quarry",
            "icon": "dump-quarry",
        },
        # Дорожная техника
        {
            "parent": "road",
            "name": "Катки дорожные",
            "code": "roller",
            "icon": "roller",
        },
        {
            "parent": "road",
            "name": "Асфальтоукладчики",
            "code": "paver",
            "icon": "paver",
        },
        {
            "parent": "road",
            "name": "Фрезы дорожные",
            "code": "milling",
            "icon": "milling",
        },
        # Буровая техника
        {
            "parent": "drilling",
            "name": "Буровые установки",
            "code": "drill_rig",
            "icon": "drill-rig",
        },
        {
            "parent": "drilling",
            "name": "Копры",
            "code": "pile_driver",
            "icon": "pile-driver",
        },
    ]

    for data in subcategories_data:
        cat = Category(
            name=data["name"],
            code=data["code"],
            parent_id=root_categories[data["parent"]],
            level=2,
            icon=data.get("icon"),
            sort_order=0,
        )
        db.add(cat)

    db.commit()
    print(f"✅ Создано {len(categories_data)} корневых категорий")
    print(f"✅ Создано {len(subcategories_data)} подкатегорий")


def seed_attributes(db: Session):
    """Создаёт атрибуты для подкатегорий."""

    if db.query(EquipmentAttributeDefinition).count() > 0:
        print("⚠️  Атрибуты уже существуют. Пропускаем.")
        return

    # Получаем подкатегории
    excavator_track = (
        db.query(Category).filter(Category.code == "excavator_track").first()
    )
    dump_20_30 = db.query(Category).filter(Category.code == "dump_20_30").first()

    if not excavator_track:
        print("❌ Подкатегория 'excavator_track' не найдена")
        return

    # Атрибуты для экскаваторов гусеничных
    excavator_attrs = [
        {
            "name": "Масса",
            "slug": "weight",
            "data_type": "number",
            "unit": "т",
            "is_required": True,
        },
        {
            "name": "Объём ковша",
            "slug": "bucket_volume",
            "data_type": "number",
            "unit": "м³",
            "is_required": True,
        },
        {
            "name": "Глубина копания",
            "slug": "dig_depth",
            "data_type": "number",
            "unit": "м",
            "is_required": False,
        },
        {
            "name": "Мощность двигателя",
            "slug": "engine_power",
            "data_type": "number",
            "unit": "л.с.",
            "is_required": True,
        },
        {
            "name": "Производитель",
            "slug": "manufacturer",
            "data_type": "select",
            "is_required": True,
        },
    ]

    for i, attr_data in enumerate(excavator_attrs):
        attr = EquipmentAttributeDefinition(
            subcategory_id=excavator_track.id,
            sort_order=i,
            allow_custom_values=True,
            is_active=True,
            **attr_data,
        )
        db.add(attr)
        db.flush()

        # Добавляем варианты для select-атрибутов
        if attr_data["slug"] == "manufacturer":
            manufacturers = [
                "Caterpillar",
                "Komatsu",
                "Hitachi",
                "Volvo",
                "JCB",
                "Hyundai",
                "Doosan",
            ]
            for j, mfr in enumerate(manufacturers):
                option = EquipmentAttributeOption(
                    attribute_definition_id=attr.id,
                    value=mfr,
                    sort_order=j,
                    is_custom=False,
                    is_active=True,
                )
                db.add(option)

    # Атрибуты для самосвалов 20-30т
    if dump_20_30:
        dump_attrs = [
            {
                "name": "Грузоподъёмность",
                "slug": "load_capacity",
                "data_type": "number",
                "unit": "т",
                "is_required": True,
            },
            {
                "name": "Объём кузова",
                "slug": "body_volume",
                "data_type": "number",
                "unit": "м³",
                "is_required": True,
            },
            {
                "name": "Тип кузова",
                "slug": "body_type",
                "data_type": "select",
                "is_required": True,
            },
        ]

        for i, attr_data in enumerate(dump_attrs):
            attr = EquipmentAttributeDefinition(
                subcategory_id=dump_20_30.id,
                sort_order=i,
                allow_custom_values=True,
                is_active=True,
                **attr_data,
            )
            db.add(attr)
            db.flush()

            if attr_data["slug"] == "body_type":
                body_types = ["Стандартный", "Угольный", "Скальный"]
                for j, bt in enumerate(body_types):
                    option = EquipmentAttributeOption(
                        attribute_definition_id=attr.id,
                        value=bt,
                        sort_order=j,
                        is_custom=False,
                        is_active=True,
                    )
                    db.add(option)

    db.commit()
    print("✅ Созданы атрибуты для подкатегорий")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        print("🌱 Запуск seed данных для каталога...")
        seed_categories(db)
        seed_attributes(db)
        print("✅ Seed завершён успешно!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()
