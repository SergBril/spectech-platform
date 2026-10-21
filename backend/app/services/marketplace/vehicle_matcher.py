"""
Сервис подбора техники для заказов маркетплейса.
Фильтрует по категории, атрибутам, статусу и согласию на комиссию.
"""
import logging
from sqlalchemy.orm import Session
from app.models.catalog import Vehicle, EquipmentAttributeDefinition, EquipmentAttributeValue, Category
from app.models.dispatch import Request

logger = logging.getLogger("spectech.vehicle_matcher")


class VehicleMatcherService:

    # Маппинг: подкатегория заказа → совместимые категории техники
    REQUEST_SUBCAT_TO_VEHICLE_CATS = {
        8: [2],    # Экскаваторы гусеничные → Экскаваторы
        9: [2],    # Экскаваторы колёсные → Экскаваторы
        10: [2],   # Мини-экскаваторы → Экскаваторы
        11: [6],   # Экскаваторы-погрузчики → Погрузчики
        12: [5],   # Бульдозеры → Бульдозеры
        13: [6],   # Фронтальные погрузчики → Погрузчики
        14: [6],   # Мини-погрузчики → Погрузчики
        15: [6],   # Телескопические погрузчики → Погрузчики
        16: [],    # Грейдеры → нет совместимой категории техники
        17: [],    # Скреперы → нет совместимой категории техники
        19: [],    # Автовышки (АГП) → отдельная категория, НЕ автокраны
        20: [4],   # Автокраны → Автокраны
        21: [],    # Манипуляторы (КМУ) → отдельная категория, НЕ автокраны
        33: [3],   # Самосвалы → Самосвалы
        34: [],    # Тралы → отдельная категория, НЕ самосвалы
    }

    def find_matching_vehicles(
        self, db: Session, request_id: int, company_id: int | None = None,
    ) -> list[dict]:
        request = db.get(Request, request_id)
        if not request:
            return []

        query = db.query(Vehicle).filter(Vehicle.is_deleted == False)

        # Фильтр по категории: маппинг подкатегории заказа → категории техники
        if request.vehicle_category_id:
            compatible_vehicle_cats = self.REQUEST_SUBCAT_TO_VEHICLE_CATS.get(
                request.vehicle_category_id, []
            )
            if compatible_vehicle_cats:
                query = query.filter(Vehicle.category_id.in_(compatible_vehicle_cats))
            else:
                # Если маппинг не найден — пробуем точное совпадение + родительскую
                cat = db.get(Category, request.vehicle_category_id)
                cats_to_check = [request.vehicle_category_id]
                if cat and cat.parent_id:
                    cats_to_check.append(cat.parent_id)
                query = query.filter(Vehicle.category_id.in_(cats_to_check))

        # Исключаем недоступные статусы
        query = query.filter(Vehicle.status.notin_(["maintenance", "repair", "decommissioned"]))

        # Фильтр по компании
        if company_id:
            query = query.filter(Vehicle.company_id == company_id)

        # Marketplace: только техника с согласием на комиссию
        is_marketplace = getattr(request, "source_channel", None) == "marketplace"
        if is_marketplace:
            query = query.filter(Vehicle.marketplace_commission_agreed == True)

        vehicles = query.all()

        results = []
        for v in vehicles:
            score, matched, missing = self._score_vehicle(db, v, request)
            results.append({
                "vehicle_id": v.id,
                "vehicle_name": v.name,
                "category_id": v.category_id,
                "status": v.status,
                "hourly_rate": float(v.hourly_rate) if v.hourly_rate else None,
                "shift_rate": float(v.shift_rate) if v.shift_rate else None,
                "match_score": score,
                "matched_attributes": matched,
                "missing_attributes": missing,
                "marketplace_commission_agreed": getattr(v, "marketplace_commission_agreed", False),
                "marketplace_commission_rate": float(getattr(v, "marketplace_commission_rate", 10)),
            })

        results.sort(key=lambda x: x["match_score"], reverse=True)
        logger.info(f"Found {len(results)} matches for request #{request_id}")
        return results

    # Маппинг: категория техники → совместимые подкатегории заказов
    # Техника хранится в родительских категориях (2,3,4,5,6),
    # заказы — в подкатегориях (8,9,10...). Нужен явный маппинг.
    VEHICLE_CAT_TO_REQUEST_SUBCATS = {
        2: [8, 9, 10],       # Экскаваторы → гусеничные, колёсные, мини
        3: [33],             # Самосвалы → самосвалы (подкатегория)
        4: [20],             # Автокраны → автокраны (подкатегория)
        5: [12],             # Бульдозеры → бульдозеры (подкатегория)
        6: [11, 13, 14, 15], # Погрузчики → экскаваторы-погрузчики, фронтальные, мини, телескопические
    }

    def _get_compatible_categories(self, db: Session, cat_id: int) -> list[int]:
        """Возвращает список категорий, совместимых с данной.
        
        Если cat_id — это подкатегория заказа (например 9=Экскаваторы колёсные),
        возвращаем все подкатегории той же группы + родительскую категорию техники.
        Если cat_id — это категория техники (например 2=Экскаваторы),
        возвращаем все совместимые подкатегории.
        """
        result = {cat_id}
        cat = db.get(Category, cat_id)
        
        # Если это категория техники (родительская) — добавляем совместимые подкатегории
        if cat_id in self.VEHICLE_CAT_TO_REQUEST_SUBCATS:
            result.update(self.VEHICLE_CAT_TO_REQUEST_SUBCATS[cat_id])
        
        # Если это подкатегория заказа — добавляем sibling-подкатегории и родительскую
        if cat and cat.parent_id:
            result.add(cat.parent_id)
            # Все sibling-подкатегории (другие подкатегории того же родителя)
            siblings = db.query(Category).filter(Category.parent_id == cat.parent_id).all()
            for s in siblings:
                result.add(s.id)
        
        # Дочерние категории (если есть)
        children = db.query(Category).filter(Category.parent_id == cat_id).all()
        for c in children:
            result.add(c.id)
        
        return list(result)

    # Атрибуты, где значение техники должно быть >= требуемого
    GTE_ATTRIBUTES = {
        "Грузоподъёмность", "Вылет стрелы", "Высота подъёма",
        "Макс. высота подъёма", "Глубина копания", "Объём ковша",
        "Ширина отвала", "Длина платформы", "Масса",
    }

    # Маппинг ключей requirements → имена атрибутов
    REQ_TO_ATTR = {
        "min_tonnage": ("Грузоподъёмность", "gte"),
        "min_boom_length": ("Вылет стрелы", "gte"),
        "min_lift_height": ("Высота подъёма", "gte"),
        "min_bucket_volume": ("Объём ковша", "gte"),
        "min_dig_depth": ("Глубина копания", "gte"),
        "min_blade_width": ("Ширина отвала", "gte"),
        "chassis_type": ("Тип шасси", "eq"),
        "base_type": ("Базовое шасси", "eq"),
    }

    KEY_ATTRS_BY_CAT = {
        2: ["Масса", "Объём ковша", "Глубина копания"],
        3: ["Масса", "Грузоподъёмность", "Тип шасси"],
        4: ["Масса", "Грузоподъёмность", "Вылет стрелы", "Тип шасси"],
        5: ["Масса", "Ширина отвала"],
        6: ["Масса", "Объём ковша"],
    }

    def _score_vehicle(self, db: Session, vehicle: Vehicle, request: Request) -> tuple[int, list[str], list[str]]:
        score = 50
        matched, missing = [], []
        excluded = False

        attrs = db.query(EquipmentAttributeValue).filter(
            EquipmentAttributeValue.vehicle_id == vehicle.id
        ).all()

        num_map = {}
        text_map = {}
        for va in attrs:
            defn = db.get(EquipmentAttributeDefinition, va.attribute_definition_id)
            if not defn:
                continue
            if va.value_number is not None:
                num_map[defn.name] = va.value_number
            if va.value_text:
                text_map[defn.name] = va.value_text

        requirements = getattr(request, "requirements", None) or {}

        # Проверяем требования из заказа (логика >=)
        for req_key, (attr_name, compare_type) in self.REQ_TO_ATTR.items():
            req_value = requirements.get(req_key)
            if req_value is None:
                continue

            if compare_type == "gte":
                vehicle_value = num_map.get(attr_name)
                if vehicle_value is not None:
                    # Нормализация единиц: если требование в тоннах, а атрибут в кг
                    norm_vehicle = vehicle_value
                    norm_req = float(req_value)
                    # Если разница > 100x, вероятно разные единицы
                    if norm_vehicle > norm_req * 100:
                        norm_vehicle = norm_vehicle / 1000  # кг → т
                    elif norm_req > norm_vehicle * 100:
                        norm_req = norm_req / 1000

                    if norm_vehicle >= norm_req:
                        matched.append(f"{attr_name}>={req_value}")
                        score += 20
                    else:
                        # Техника не соответствует требованию — исключаем
                        missing.append(f"{attr_name}<{req_value}")
                        excluded = True
                else:
                    missing.append(attr_name)
                    score -= 10

            elif compare_type == "eq":
                vehicle_value = text_map.get(attr_name)
                if vehicle_value and str(vehicle_value).lower() == str(req_value).lower():
                    matched.append(f"{attr_name}={req_value}")
                    score += 15
                elif vehicle_value:
                    missing.append(f"{attr_name}!={req_value}")
                    # Не исключаем, но снижаем score
                    score -= 5

        # Если нет требований — проверяем наличие ключевых атрибутов
        if not requirements:
            key_attrs = self.KEY_ATTRS_BY_CAT.get(vehicle.category_id, ["Масса"])
            for attr in key_attrs:
                if attr in num_map or attr in text_map:
                    matched.append(attr)
                    score += 15
                else:
                    missing.append(attr)
                    score -= 5

        if excluded:
            return 0, matched, missing
        return max(0, min(score, 100)), matched, missing


vehicle_matcher = VehicleMatcherService()
