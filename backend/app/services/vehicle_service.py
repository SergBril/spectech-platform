"""Vehicle business logic service."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("spectech.vehicles")


class VehicleServiceError(Exception):
    """Business logic error in vehicle operations."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def save_vehicle_attributes(
    db: Session, vehicle_id: int, subcategory_id: int | None, attributes: dict | None
) -> None:
    """Сохраняет динамические атрибуты для техники."""
    from app.models.catalog import (
        EquipmentAttributeDefinition,
        EquipmentAttributeOption,
        EquipmentAttributeValue,
    )

    if not attributes or not subcategory_id:
        return

    for slug, value in attributes.items():
        if value is None or value == "":
            continue

        attr_def = (
            db.query(EquipmentAttributeDefinition)
            .filter(
                EquipmentAttributeDefinition.subcategory_id == subcategory_id,
                EquipmentAttributeDefinition.slug == slug,
                EquipmentAttributeDefinition.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not attr_def:
            continue

        attr_value = EquipmentAttributeValue(
            vehicle_id=vehicle_id,
            attribute_definition_id=attr_def.id,
        )

        if attr_def.data_type == "number":
            try:
                attr_value.value_number = float(value)
                attr_value.value_text = str(value)
            except (TypeError, ValueError):
                attr_value.value_text = str(value)
        elif attr_def.data_type == "boolean":
            attr_value.value_boolean = bool(value)
        else:
            attr_value.value_text = str(value)
            if attr_def.data_type == "select":
                option = (
                    db.query(EquipmentAttributeOption)
                    .filter(
                        EquipmentAttributeOption.attribute_definition_id == attr_def.id,
                        EquipmentAttributeOption.value == value,
                    )
                    .first()
                )
                if option:
                    attr_value.attribute_option_id = option.id

        db.add(attr_value)


def load_vehicle_with_relations(db: Session, vehicle_id: int) -> object | None:
    """Загружает технику с joinedload всех нужных связей."""
    from sqlalchemy.orm import joinedload

    from app.models.catalog import Category, EquipmentAttributeValue, Vehicle

    return (
        db.query(Vehicle)
        .options(
            joinedload(Vehicle.category).joinedload(Category.parent),
            joinedload(Vehicle.attribute_values).joinedload(
                EquipmentAttributeValue.attribute_definition
            ),
        )
        .filter(Vehicle.id == vehicle_id)
        .first()
    )


# ============================================================
# GET /vehicles — список техники
# ============================================================


def enrich_vehicle(vehicle: object, db: Session = None) -> dict:
    """Обогащает VehicleRead названиями категории/подкатегории и атрибутами."""
    from app.models.contractor import Employee
    from app.schemas.vehicles import VehicleRead

    # Сначала получаем базовый dict (attribute_values пока с SQLAlchemy-объектами)
    data = VehicleRead.model_validate(vehicle, from_attributes=True).model_dump()

    # Сразу очищаем attribute_values — заполним вручную ниже
    data["attribute_values"] = []

    # Определяем названия категории и подкатегории
    if vehicle.category:
        if vehicle.category.level == 2 and vehicle.category.parent:
            data["category_name"] = vehicle.category.parent.name
            data["subcategory_name"] = vehicle.category.name
        else:
            data["category_name"] = vehicle.category.name
            data["subcategory_name"] = None
    else:
        data["category_name"] = None
        data["subcategory_name"] = None

    # Собираем значения атрибутов вручную из SQLAlchemy-объектов
    attr_values = []
    for av in vehicle.attribute_values or []:
        try:
            if av.attribute_definition:
                attr_values.append(
                    {
                        "slug": av.attribute_definition.slug,
                        "name": av.attribute_definition.name,
                        "data_type": av.attribute_definition.data_type,
                        "unit": av.attribute_definition.unit,
                        "value_text": av.value_text,
                        "value_number": av.value_number,
                        "value_boolean": av.value_boolean,
                    }
                )
        except Exception:
            continue
    data["attribute_values"] = attr_values

    # Assigned driver name
    data["assigned_driver_name"] = None
    # Алиасы для фронтенда (RequestFormModal ожидает driver_id/driver_name)
    data["driver_id"] = getattr(vehicle, "assigned_driver_id", None)
    data["driver_name"] = None
    if hasattr(vehicle, "assigned_driver_id") and vehicle.assigned_driver_id:
        try:
            # Driver name comes from Contractor.name via Employee
            emp = (
                db.query(Employee)
                .filter(Employee.contractor_id == vehicle.assigned_driver_id)
                .first()
            )
            if emp and emp.contractor:
                data["assigned_driver_name"] = emp.contractor.name
                data["driver_name"] = emp.contractor.name
        except Exception:
            pass

    return data


def log_driver_assignment(
    db: Session,
    vehicle_id: int,
    old_driver_id: int | None,
    new_driver_id: int | None,
    user_id: int | None,
):
    """Записать историю назначения водителя."""
    from datetime import UTC, datetime

    from app.models.contractor import DriverAssignmentLog

    # Закрываем предыдущее назначение (если был старый водитель)
    if old_driver_id and old_driver_id != new_driver_id:
        open_log = (
            db.query(DriverAssignmentLog)
            .filter(
                DriverAssignmentLog.vehicle_id == vehicle_id,
                DriverAssignmentLog.driver_contractor_id == old_driver_id,
                DriverAssignmentLog.unassigned_at.is_(None),
            )
            .first()
        )
        if open_log:
            open_log.unassigned_at = datetime.now(UTC)

    # Создаём новое назначение (если назначен новый водитель)
    if new_driver_id and new_driver_id != old_driver_id:
        new_log = DriverAssignmentLog(
            vehicle_id=vehicle_id,
            driver_contractor_id=new_driver_id,
            assigned_by_user_id=user_id,
        )
        db.add(new_log)


def clear_vehicle_attributes(db: Session, vehicle_id: int) -> None:
    """Удаляет все значения атрибутов для техники (перед пересохранением)."""
    from app.models.catalog import EquipmentAttributeValue

    db.query(EquipmentAttributeValue).filter(
        EquipmentAttributeValue.vehicle_id == vehicle_id
    ).delete()


def create_vehicle(db: Session, payload_data: dict, company_id: int) -> dict:
    """Create a new vehicle with validation and attributes."""
    from app.models.catalog import Category, Vehicle

    existing = db.scalar(
        select(Vehicle).where(
            Vehicle.id_value == payload_data.get("id_value"),
            Vehicle.company_id == company_id,
        )
    )
    if existing:
        raise VehicleServiceError(
            409,
            f"id_value '{payload_data.get(chr(105)+chr(100)+chr(95)+chr(118)+chr(97)+chr(108)+chr(117)+chr(101))}' already exists",
        )

    subcategory_id = payload_data.pop("subcategory_id", None)
    category_id = None

    if subcategory_id:
        sub = db.get(Category, subcategory_id)
        if not sub or sub.level != 2:
            raise VehicleServiceError(400, "Invalid subcategory (must be level=2)")
        category_id = subcategory_id
    elif payload_data.get("category_id"):
        cat = db.get(Category, payload_data["category_id"])
        if cat and cat.level == 1:
            category_id = payload_data["category_id"]

    vehicle_data = {
        k: v
        for k, v in payload_data.items()
        if k not in ("attributes", "company_id", "category_id")
    }
    vehicle_data["category_id"] = category_id
    vehicle_data["company_id"] = company_id

    if "model" in vehicle_data:
        vehicle_data["model_name"] = vehicle_data.pop("model")

    vehicle = Vehicle(**vehicle_data)
    db.add(vehicle)
    db.flush()

    attributes = payload_data.get("attributes")
    try:
        save_vehicle_attributes(db, vehicle.id, subcategory_id, attributes)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to save vehicle attributes: {e}")
        raise VehicleServiceError(400, f"Attribute save error: {str(e)}")

    vehicle = load_vehicle_with_relations(db, vehicle.id)
    return enrich_vehicle(vehicle, db)


def update_vehicle(
    db: Session,
    vehicle_id: int,
    update_data: dict,
    attributes: dict | None,
    company_id: int,
    user_id: int,
) -> dict:
    """Update a vehicle with validation, driver assignment history, and attributes."""
    from app.models.catalog import Category, Vehicle

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise VehicleServiceError(404, "Vehicle not found")

    old_driver_id = getattr(vehicle, "assigned_driver_id", None)
    new_driver_id = update_data.get("assigned_driver_id")
    if new_driver_id is not None:
        db.query(Vehicle).filter(
            Vehicle.assigned_driver_id == new_driver_id,
            Vehicle.id != vehicle_id,
            Vehicle.company_id == company_id,
        ).update({"assigned_driver_id": None}, synchronize_session="fetch")
        db.flush()

    if "assigned_driver_id" in update_data:
        log_driver_assignment(db, vehicle_id, old_driver_id, new_driver_id, user_id)

    if "id_value" in update_data and update_data["id_value"] != vehicle.id_value:
        existing = db.scalar(
            select(Vehicle).where(
                Vehicle.id_value == update_data["id_value"],
                Vehicle.company_id == company_id,
                Vehicle.id != vehicle_id,
            )
        )
        if existing:
            raise VehicleServiceError(
                409,
                f"id_value '{update_data[chr(105)+chr(100)+chr(95)+chr(118)+chr(97)+chr(108)+chr(117)+chr(101)]}' already exists",
            )

    subcategory_id = update_data.pop("subcategory_id", None)
    if subcategory_id:
        sub = db.get(Category, subcategory_id)
        if not sub or sub.level != 2:
            raise VehicleServiceError(400, "Invalid subcategory")
        update_data["category_id"] = sub.parent_id

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    if attributes is not None and subcategory_id:
        clear_vehicle_attributes(db, vehicle.id)
        save_vehicle_attributes(db, vehicle.id, subcategory_id, attributes)

    db.commit()
    vehicle = load_vehicle_with_relations(db, vehicle_id)
    return enrich_vehicle(vehicle, db)
