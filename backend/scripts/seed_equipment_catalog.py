"""
Наполнение каталога техники: категории, подкатегории, атрибуты.

Использование:
    python scripts/seed_equipment_catalog.py

Скрипт идемпотентный — можно запускать повторно без дублирования.
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.catalog import (
    Category,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
)


def get_or_create_category(db: Session, code: str, **kwargs) -> Category:
    """Получить или создать категорию."""
    cat = db.query(Category).filter(Category.code == code).first()
    if not cat:
        cat = Category(code=code, **kwargs)
        db.add(cat)
        db.flush()
    return cat


def get_or_create_attribute(
    db: Session, subcategory_id: int, slug: str, **kwargs
) -> EquipmentAttributeDefinition:
    """Получить или создать определение атрибута."""
    attr = (
        db.query(EquipmentAttributeDefinition)
        .filter(
            EquipmentAttributeDefinition.subcategory_id == subcategory_id,
            EquipmentAttributeDefinition.slug == slug,
        )
        .first()
    )
    if not attr:
        attr = EquipmentAttributeDefinition(
            subcategory_id=subcategory_id, slug=slug, **kwargs
        )
        db.add(attr)
        db.flush()
    return attr


def add_options(db: Session, attr: EquipmentAttributeDefinition, options: list[str]):
    """Добавить варианты значений для атрибута."""
    existing = {opt.value for opt in attr.options if not opt.is_custom}
    for i, value in enumerate(options):
        if value not in existing:
            opt = EquipmentAttributeOption(
                attribute_definition_id=attr.id,
                value=value,
                sort_order=i,
                is_custom=False,
            )
            db.add(opt)


def seed_catalog():
    """Наполнить каталог техники."""
    db: Session = SessionLocal()

    try:
        print("🚀 Начинаем наполнение каталога техники...")

        # ============================================================
        # 1. ЗЕМЛЕРОЙНАЯ И КАРЬЕРНАЯ ТЕХНИКА
        # ============================================================
        cat1 = get_or_create_category(
            db,
            code="earthmoving",
            name="Землеройная и карьерная техника",
            level=1,
            icon="🚜",
            sort_order=1,
        )
        db.flush()

        # 1.1 Экскаваторы гусеничные
        sub1_1 = get_or_create_category(
            db,
            code="excavator-tracked",
            name="Экскаваторы гусеничные",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_1.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_1.id,
            "digging_depth",
            name="Глубина копания",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_1.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_1.id,
            "engine_power",
            name="Мощность двигателя",
            data_type="number",
            unit="л.с.",
        )

        # 1.2 Экскаваторы колёсные
        sub1_2 = get_or_create_category(
            db,
            code="excavator-wheeled",
            name="Экскаваторы колёсные",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_2.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_2.id,
            "digging_depth",
            name="Глубина копания",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_2.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_2.id,
            "speed",
            name="Скорость передвижения",
            data_type="number",
            unit="км/ч",
        )

        # 1.3 Мини-экскаваторы
        sub1_3 = get_or_create_category(
            db,
            code="mini-excavator",
            name="Мини-экскаваторы",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=3,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_3.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_3.id,
            "digging_depth",
            name="Глубина копания",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_3.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
            is_required=True,
        )

        # 1.4 Экскаваторы-погрузчики
        sub1_4 = get_or_create_category(
            db,
            code="backhoe-loader",
            name="Экскаваторы-погрузчики",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=4,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_4.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_4.id,
            "front_bucket_volume",
            name="Объём фронтального ковша",
            data_type="number",
            unit="м³",
        )
        attr = get_or_create_attribute(
            db,
            sub1_4.id,
            "backhoe_depth",
            name="Глубина копания обратной лопаты",
            data_type="number",
            unit="м",
        )

        # 1.5 Бульдозеры
        sub1_5 = get_or_create_category(
            db,
            code="bulldozer",
            name="Бульдозеры",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=5,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_5.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_5.id,
            "engine_power",
            name="Мощность",
            data_type="number",
            unit="л.с.",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_5.id,
            "blade_width",
            name="Ширина отвала",
            data_type="number",
            unit="м",
        )
        attr = get_or_create_attribute(
            db,
            sub1_5.id,
            "blade_type",
            name="Тип отвала",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["Прямой", "Полусферический", "Поворотный", "Угольный"])

        # 1.6 Фронтальные погрузчики
        sub1_6 = get_or_create_category(
            db,
            code="wheel-loader",
            name="Фронтальные погрузчики",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=6,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_6.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_6.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_6.id,
            "dump_height",
            name="Высота разгрузки",
            data_type="number",
            unit="м",
        )
        attr = get_or_create_attribute(
            db,
            sub1_6.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="number",
            unit="кг",
        )

        # 1.7 Мини-погрузчики
        sub1_7 = get_or_create_category(
            db,
            code="skid-steer-loader",
            name="Мини-погрузчики",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=7,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_7.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_7.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
        )
        attr = get_or_create_attribute(
            db,
            sub1_7.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="number",
            unit="кг",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db, sub1_7.id, "type", name="Тип", data_type="select", is_required=True
        )
        add_options(db, attr, ["С бортовым поворотом", "Колёсный", "Гусеничный"])

        # 1.8 Телескопические погрузчики
        sub1_8 = get_or_create_category(
            db,
            code="telehandler",
            name="Телескопические погрузчики",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=8,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_8.id,
            "lift_height",
            name="Макс. высота подъёма",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_8.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="number",
            unit="кг",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db, sub1_8.id, "reach", name="Вылет стрелы", data_type="number", unit="м"
        )

        # 1.9 Грейдеры
        sub1_9 = get_or_create_category(
            db,
            code="grader",
            name="Грейдеры",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=9,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_9.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_9.id,
            "blade_width",
            name="Ширина отвала",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_9.id,
            "engine_power",
            name="Мощность",
            data_type="number",
            unit="л.с.",
        )

        # 1.10 Скреперы
        sub1_10 = get_or_create_category(
            db,
            code="scraper",
            name="Скреперы",
            level=2,
            parent_id=cat1.id,
            icon="🚜",
            sort_order=10,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub1_10.id,
            "bucket_volume",
            name="Объём ковша",
            data_type="number",
            unit="м³",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub1_10.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="number",
            unit="т",
        )

        print("✅ Категория 1: Землеройная техника (10 подкатегорий)")

        # ============================================================
        # 2. ПОДЪЁМНО-ТРАНСПОРТНАЯ ТЕХНИКА
        # ============================================================
        cat2 = get_or_create_category(
            db,
            code="lifting",
            name="Подъёмно-транспортная техника",
            level=1,
            icon="🏗️",
            sort_order=2,
        )
        db.flush()

        # 2.1 Автовышки (АГП)
        sub2_1 = get_or_create_category(
            db,
            code="aerial-platform",
            name="Автовышки (АГП)",
            level=2,
            parent_id=cat2.id,
            icon="🏗️",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub2_1.id,
            "boom_type",
            name="Тип стрелы",
            data_type="select",
            is_required=True,
        )
        add_options(
            db,
            attr,
            [
                "Телескопическая",
                "Коленчатая",
                "Коленчато-телескопическая",
                "Комбинированная с гуськом",
            ],
        )

        attr = get_or_create_attribute(
            db,
            sub2_1.id,
            "lift_height",
            name="Высота подъёма",
            data_type="select",
            is_required=True,
        )
        add_options(
            db, attr, ["12 м", "15 м", "18 м", "22 м", "28 м", "32 м", "45 м", "50 м+"]
        )

        attr = get_or_create_attribute(
            db, sub2_1.id, "reach", name="Вылет стрелы", data_type="number", unit="м"
        )

        attr = get_or_create_attribute(
            db,
            sub2_1.id,
            "basket_capacity",
            name="Грузоподъёмность корзины",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["200 кг", "250 кг", "300 кг", "400 кг"])

        attr = get_or_create_attribute(
            db, sub2_1.id, "basket_type", name="Тип корзины", data_type="select"
        )
        add_options(
            db,
            attr,
            [
                "Раскладная",
                "Балкон-платформа",
                "С поворотным устройством",
                "Двухсекционная",
            ],
        )

        attr = get_or_create_attribute(
            db, sub2_1.id, "chassis", name="Базовое шасси", data_type="select"
        )
        add_options(
            db, attr, ["ГАЗ", "КАМАЗ", "УРАЛ", "МАЗ", "ЗИЛ", "ISUZU", "Hino", "Hyundai"]
        )

        attr = get_or_create_attribute(
            db, sub2_1.id, "insulation", name="Электроизоляция", data_type="select"
        )
        add_options(db, attr, ["До 1000 В", "До 10 кВ", "Нет"])

        # 2.2 Автокраны
        sub2_2 = get_or_create_category(
            db,
            code="truck-crane",
            name="Автокраны",
            level=2,
            parent_id=cat2.id,
            icon="🏗️",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub2_2.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="select",
            is_required=True,
        )
        add_options(
            db, attr, ["10 т", "16 т", "25 т", "32 т", "50 т", "80 т", "100 т+"]
        )

        attr = get_or_create_attribute(
            db,
            sub2_2.id,
            "boom_length",
            name="Длина стрелы",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["10 м", "14 м", "18 м", "22 м", "28 м", "34 м", "40 м+"])

        attr = get_or_create_attribute(
            db, sub2_2.id, "reach", name="Вылет стрелы", data_type="number", unit="м"
        )

        attr = get_or_create_attribute(
            db,
            sub2_2.id,
            "boom_sections",
            name="Количество секций стрелы",
            data_type="number",
        )

        attr = get_or_create_attribute(
            db, sub2_2.id, "chassis", name="Базовое шасси", data_type="select"
        )
        add_options(db, attr, ["КАМАЗ", "МАЗ", "УРАЛ", "Volvo", "MAN", "Scania"])

        # 2.3 Манипуляторы (КМУ)
        sub2_3 = get_or_create_category(
            db,
            code="manipulator",
            name="Манипуляторы (КМУ)",
            level=2,
            parent_id=cat2.id,
            icon="🏗️",
            sort_order=3,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub2_3.id,
            "crane_capacity",
            name="Грузоподъёмность КМУ",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["1 т", "3 т", "5 т", "7 т", "10 т", "15 т", "20 т+"])

        attr = get_or_create_attribute(
            db,
            sub2_3.id,
            "reach",
            name="Вылет стрелы",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["6 м", "8 м", "10 м", "12 м", "15 м", "19 м+"])

        attr = get_or_create_attribute(
            db,
            sub2_3.id,
            "boom_type",
            name="Тип стрелы",
            data_type="select",
            is_required=True,
        )
        add_options(
            db, attr, ["L-образная", "Z-образная (складная)", "Телескопическая"]
        )

        attr = get_or_create_attribute(
            db,
            sub2_3.id,
            "bed_capacity",
            name="Грузоподъёмность борта",
            data_type="select",
        )
        add_options(db, attr, ["5 т", "10 т", "15 т", "20 т"])

        attr = get_or_create_attribute(
            db, sub2_3.id, "bed_length", name="Длина борта", data_type="select"
        )
        add_options(db, attr, ["4 м", "5 м", "6 м", "6.5 м", "7 м+"])

        attr = get_or_create_attribute(
            db, sub2_3.id, "bed_type", name="Тип борта", data_type="select"
        )
        add_options(
            db,
            attr,
            ["Бортовой", "Бортовой с тентом", "Самосвальный", "Эвакуаторная платформа"],
        )

        attr = get_or_create_attribute(
            db, sub2_3.id, "chassis", name="Базовое шасси", data_type="select"
        )
        add_options(
            db,
            attr,
            ["ГАЗ", "КАМАЗ", "УРАЛ", "МАЗ", "ISUZU", "Hino", "Hyundai", "FUSO"],
        )

        print("✅ Категория 2: Подъёмно-транспортная техника (3 подкатегории)")

        # ============================================================
        # 3. БУРОВАЯ И СВАЕБОЙНАЯ ТЕХНИКА
        # ============================================================
        cat3 = get_or_create_category(
            db,
            code="drilling",
            name="Буровая и сваебойная техника",
            level=1,
            icon="⛏️",
            sort_order=3,
        )
        db.flush()

        # 3.1 Ямобуры
        sub3_1 = get_or_create_category(
            db,
            code="auger",
            name="Ямобуры",
            level=2,
            parent_id=cat3.id,
            icon="⛏️",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub3_1.id,
            "max_depth",
            name="Макс. глубина бурения",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["2 м", "3 м", "4 м", "5 м", "7 м", "10 м+"])

        attr = get_or_create_attribute(
            db,
            sub3_1.id,
            "diameter",
            name="Диаметр бурения",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["250 мм", "350 мм", "500 мм", "800 мм"])

        attr = get_or_create_attribute(
            db,
            sub3_1.id,
            "torque",
            name="Крутящий момент",
            data_type="number",
            unit="Н·м",
        )

        attr = get_or_create_attribute(
            db,
            sub3_1.id,
            "base_type",
            name="Тип базы",
            data_type="select",
            is_required=True,
        )
        add_options(
            db,
            attr,
            ["На базе грузовика", "На базе трактора", "Гусеничная", "Прицепная"],
        )

        # 3.2 Буровые установки (УРБ)
        sub3_2 = get_or_create_category(
            db,
            code="drilling-rig",
            name="Буровые установки (УРБ)",
            level=2,
            parent_id=cat3.id,
            icon="⛏️",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub3_2.id,
            "max_depth",
            name="Глубина бурения",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub3_2.id,
            "diameter",
            name="Диаметр бурения",
            data_type="number",
            unit="мм",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub3_2.id,
            "drilling_method",
            name="Способ бурения",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["Шнековый", "Роторный", "Ударный", "Комбинированный"])

        # 3.3 Сваебои
        sub3_3 = get_or_create_category(
            db,
            code="pile-driver",
            name="Сваебои",
            level=2,
            parent_id=cat3.id,
            icon="⛏️",
            sort_order=3,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub3_3.id,
            "impact_energy",
            name="Энергия удара",
            data_type="number",
            unit="Дж",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub3_3.id,
            "pile_depth",
            name="Глубина погружения",
            data_type="number",
            unit="м",
        )
        attr = get_or_create_attribute(
            db,
            sub3_3.id,
            "hammer_weight",
            name="Масса молота",
            data_type="number",
            unit="т",
        )
        attr = get_or_create_attribute(
            db,
            sub3_3.id,
            "hammer_type",
            name="Тип молота",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["Дизельный", "Гидравлический", "Пневматический"])

        print("✅ Категория 3: Буровая техника (3 подкатегории)")

        # ============================================================
        # 4. ДОРОЖНО-СТРОИТЕЛЬНАЯ ТЕХНИКА
        # ============================================================
        cat4 = get_or_create_category(
            db,
            code="road-construction",
            name="Дорожно-строительная техника",
            level=1,
            icon="🛣️",
            sort_order=4,
        )
        db.flush()

        # 4.1 Катки дорожные
        sub4_1 = get_or_create_category(
            db,
            code="road-roller",
            name="Катки дорожные",
            level=2,
            parent_id=cat4.id,
            icon="🛣️",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub4_1.id,
            "weight",
            name="Масса",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub4_1.id,
            "roller_type",
            name="Тип вальца",
            data_type="select",
            is_required=True,
        )
        add_options(
            db, attr, ["Гладкий", "Кулачковый", "Пневмоколёсный", "Комбинированный"]
        )
        attr = get_or_create_attribute(
            db,
            sub4_1.id,
            "roller_width",
            name="Ширина вальца",
            data_type="number",
            unit="м",
        )

        # 4.2 Асфальтоукладчики
        sub4_2 = get_or_create_category(
            db,
            code="asphalt-paver",
            name="Асфальтоукладчики",
            level=2,
            parent_id=cat4.id,
            icon="🛣️",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub4_2.id,
            "paving_width",
            name="Ширина укладки",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub4_2.id,
            "productivity",
            name="Производительность",
            data_type="number",
            unit="т/ч",
        )
        attr = get_or_create_attribute(
            db, sub4_2.id, "drive_type", name="Тип хода", data_type="select"
        )
        add_options(db, attr, ["Колёсный", "Гусеничный"])

        print("✅ Категория 4: Дорожно-строительная техника (2 подкатегории)")

        # ============================================================
        # 5. БЕТОННАЯ ТЕХНИКА
        # ============================================================
        cat5 = get_or_create_category(
            db,
            code="concrete",
            name="Бетонная техника",
            level=1,
            icon="🏭",
            sort_order=5,
        )
        db.flush()

        # 5.1 Автобетононасосы
        sub5_1 = get_or_create_category(
            db,
            code="concrete-pump-truck",
            name="Автобетононасосы",
            level=2,
            parent_id=cat5.id,
            icon="🏭",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub5_1.id,
            "boom_length",
            name="Длина стрелы",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["20 м", "24 м", "28 м", "32 м", "36 м", "42 м", "52 м+"])
        attr = get_or_create_attribute(
            db,
            sub5_1.id,
            "productivity",
            name="Производительность",
            data_type="number",
            unit="м³/ч",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub5_1.id,
            "pipeline_diameter",
            name="Диаметр трубопровода",
            data_type="number",
            unit="мм",
        )

        # 5.2 Автобетоносмесители (миксеры)
        sub5_2 = get_or_create_category(
            db,
            code="concrete-mixer",
            name="Автобетоносмесители (миксеры)",
            level=2,
            parent_id=cat5.id,
            icon="🏭",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub5_2.id,
            "drum_volume",
            name="Объём барабана",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["5 м³", "6 м³", "7 м³", "8 м³", "9 м³", "10 м³+"])

        print("✅ Категория 5: Бетонная техника (2 подкатегории)")

        # ============================================================
        # 6. ГРУЗОВАЯ И ТРАНСПОРТНАЯ ТЕХНИКА
        # ============================================================
        cat6 = get_or_create_category(
            db,
            code="transport",
            name="Грузовая и транспортная техника",
            level=1,
            icon="🚚",
            sort_order=6,
        )
        db.flush()

        # 6.1 Самосвалы
        sub6_1 = get_or_create_category(
            db,
            code="dump-truck",
            name="Самосвалы",
            level=2,
            parent_id=cat6.id,
            icon="🚚",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub6_1.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["5 т", "10 т", "15 т", "20 т", "25 т", "30 т", "40 т+"])
        attr = get_or_create_attribute(
            db,
            sub6_1.id,
            "bed_volume",
            name="Объём кузова",
            data_type="number",
            unit="м³",
        )
        attr = get_or_create_attribute(
            db, sub6_1.id, "dump_type", name="Тип разгрузки", data_type="select"
        )
        add_options(db, attr, ["Назад", "Вбок", "Трёхсторонняя"])

        # 6.2 Тралы (низкорамные)
        sub6_2 = get_or_create_category(
            db,
            code="lowbed-trailer",
            name="Тралы (низкорамные)",
            level=2,
            parent_id=cat6.id,
            icon="🚚",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub6_2.id,
            "load_capacity",
            name="Грузоподъёмность",
            data_type="number",
            unit="т",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub6_2.id,
            "platform_length",
            name="Длина платформы",
            data_type="number",
            unit="м",
        )
        attr = get_or_create_attribute(
            db,
            sub6_2.id,
            "loading_height",
            name="Высота погрузки",
            data_type="number",
            unit="м",
        )

        print("✅ Категория 6: Грузовая техника (2 подкатегории)")

        # ============================================================
        # 7. КОММУНАЛЬНАЯ ТЕХНИКА
        # ============================================================
        cat7 = get_or_create_category(
            db,
            code="municipal",
            name="Коммунальная техника",
            level=1,
            icon="🏙️",
            sort_order=7,
        )
        db.flush()

        # 7.1 Мусоровозы
        sub7_1 = get_or_create_category(
            db,
            code="garbage-truck",
            name="Мусоровозы",
            level=2,
            parent_id=cat7.id,
            icon="🏙️",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub7_1.id,
            "body_volume",
            name="Объём кузова",
            data_type="select",
            is_required=True,
        )
        add_options(db, attr, ["8 м³", "12 м³", "16 м³", "20 м³", "25 м³+"])
        attr = get_or_create_attribute(
            db, sub7_1.id, "loading_type", name="Тип загрузки", data_type="select"
        )
        add_options(db, attr, ["Задняя", "Боковая"])

        # 7.2 Снегоуборочные машины
        sub7_2 = get_or_create_category(
            db,
            code="snow-removal",
            name="Снегоуборочные машины",
            level=2,
            parent_id=cat7.id,
            icon="🏙️",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub7_2.id,
            "width",
            name="Ширина захвата",
            data_type="number",
            unit="м",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub7_2.id,
            "throw_distance",
            name="Дальность выброса",
            data_type="number",
            unit="м",
        )
        attr = get_or_create_attribute(
            db, sub7_2.id, "type", name="Тип", data_type="select"
        )
        add_options(db, attr, ["Роторный", "Шнекороторный", "Фрезерно-роторный"])

        print("✅ Категория 7: Коммунальная техника (2 подкатегории)")

        # ============================================================
        # 8. АВАРИЙНО-СПАСАТЕЛЬНАЯ ТЕХНИКА
        # ============================================================
        cat8 = get_or_create_category(
            db,
            code="emergency",
            name="Аварийно-спасательная техника",
            level=1,
            icon="🚨",
            sort_order=8,
        )
        db.flush()

        # 8.1 Передвижные электростанции (ДГУ)
        sub8_1 = get_or_create_category(
            db,
            code="generator",
            name="Передвижные электростанции (ДГУ)",
            level=2,
            parent_id=cat8.id,
            icon="🚨",
            sort_order=1,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub8_1.id,
            "power",
            name="Мощность",
            data_type="select",
            is_required=True,
        )
        add_options(
            db,
            attr,
            ["10 кВт", "20 кВт", "30 кВт", "50 кВт", "100 кВт", "200 кВт", "500 кВт+"],
        )
        attr = get_or_create_attribute(
            db, sub8_1.id, "voltage", name="Напряжение", data_type="select"
        )
        add_options(db, attr, ["220 В", "380 В", "6 кВ", "10 кВ"])

        # 8.2 Компрессорные станции
        sub8_2 = get_or_create_category(
            db,
            code="compressor",
            name="Компрессорные станции",
            level=2,
            parent_id=cat8.id,
            icon="🚨",
            sort_order=2,
        )
        db.flush()

        attr = get_or_create_attribute(
            db,
            sub8_2.id,
            "productivity",
            name="Производительность",
            data_type="number",
            unit="м³/мин",
            is_required=True,
        )
        attr = get_or_create_attribute(
            db,
            sub8_2.id,
            "pressure",
            name="Давление",
            data_type="number",
            unit="бар",
            is_required=True,
        )

        print("✅ Категория 8: Аварийно-спасательная техника (2 подкатегории)")

        db.commit()
        print("\n🎉 Каталог успешно наполнен!")
        print(f"   Категорий: {db.query(Category).filter(Category.level == 1).count()}")
        print(
            f"   Подкатегорий: {db.query(Category).filter(Category.level == 2).count()}"
        )
        print(f"   Атрибутов: {db.query(EquipmentAttributeDefinition).count()}")
        print(f"   Вариантов значений: {db.query(EquipmentAttributeOption).count()}")

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_catalog()
