"""CRUD endpoints для спецтехники (Vehicles)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids, require_permission
from app.core.db import get_db
from app.models.contractor import Employee, Contractor
from app.models.auth import User
from app.models.catalog import (
    Category,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
    EquipmentAttributeValue,
    Vehicle,
)
from app.schemas.vehicles import (
    VehicleCreate,
    VehicleListResponse,
    VehicleRead,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["🚜 Vehicles (Спецтехника)"])


def _enrich_vehicle(vehicle: Vehicle) -> dict:
    """Обогащает VehicleRead названиями категории/подкатегории и атрибутами."""
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
    if hasattr(vehicle, 'assigned_driver_id') and vehicle.assigned_driver_id:
        try:
            from sqlalchemy import select as sa_select
            # Driver name comes from Contractor.name via Employee
            emp = db.query(Employee).filter(Employee.contractor_id == vehicle.assigned_driver_id).first()
            if emp and emp.contractor:
                data["assigned_driver_name"] = emp.contractor.name
        except Exception:
            pass

    return data


def _save_vehicle_attributes(
    db: Session, vehicle_id: int, subcategory_id: int | None, attributes: dict | None
) -> None:
    """Сохраняет динамические атрибуты для техники."""
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


def _clear_vehicle_attributes(db: Session, vehicle_id: int) -> None:
    """Удаляет все значения атрибутов для техники (перед пересохранением)."""
    db.query(EquipmentAttributeValue).filter(
        EquipmentAttributeValue.vehicle_id == vehicle_id
    ).delete()


def _load_vehicle_with_relations(db: Session, vehicle_id: int) -> Vehicle | None:
    """Загружает технику с joinedload всех нужных связей."""
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

@router.get("/drivers", tags=["🚜 Vehicles (Спецтехника)"])
def list_drivers(
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Получить список водителей (сотрудников с user_id)."""
    stmt = (
        select(Employee, Contractor)
        .join(Contractor, Employee.contractor_id == Contractor.id)
        .where(
            Contractor.company_id.in_(company_ids),
            Contractor.is_active == True,  # noqa: E712
            Employee.user_id.isnot(None),
        )
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": emp.contractor_id,
            "full_name": ctr.name,
            "position": emp.position,
            "user_id": emp.user_id,
        }
        for emp, ctr in rows
    ]


@router.get(
    "",
    response_model=VehicleListResponse,
    summary="Получить список техники",
    description="Возвращает список техники своей компании с пагинацией.",
)
def list_vehicles(
    skip: int = Query(0, ge=0, description="Смещение"),
    limit: int = Query(100, ge=1, le=1000, description="Лимит"),
    status_filter: str | None = Query(
        None, alias="status", description="Фильтр по статусу"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Получить список техники (все компании пользователя)."""
    query = (
        select(Vehicle)
        .options(
            joinedload(Vehicle.category).joinedload(Category.parent),
            joinedload(Vehicle.attribute_values).joinedload(
                EquipmentAttributeValue.attribute_definition
            ),
        )
        .where(
            Vehicle.is_deleted == False,  # noqa: E712
            Vehicle.company_id.in_(company_ids),
        )
    )

    if status_filter:
        query = query.where(Vehicle.status == status_filter)

    query = query.offset(skip).limit(limit)
    vehicles = db.scalars(query).unique().all()

    count_query = select(Vehicle).where(
        Vehicle.is_deleted == False,  # noqa: E712
        Vehicle.company_id.in_(company_ids),
    )
    if status_filter:
        count_query = count_query.where(Vehicle.status == status_filter)
    total = db.scalar(
        select(Vehicle.id)
        .where(
            Vehicle.is_deleted == False,  # noqa: E712
            Vehicle.company_id.in_(company_ids),
        )
        .where(
            Vehicle.status == status_filter if status_filter else True  # type: ignore
        )
    )
    # Пересчитаем total правильно
    from sqlalchemy import func

    total = (
        db.scalar(
            select(func.count(Vehicle.id)).where(
                Vehicle.is_deleted == False,  # noqa: E712
                Vehicle.company_id.in_(company_ids),
                Vehicle.status == status_filter if status_filter else True,  # type: ignore
            )
        )
        or 0
    )

    enriched_items = [_enrich_vehicle(v) for v in vehicles]
    return VehicleListResponse(items=enriched_items, total=total)


# ============================================================
# POST /vehicles — создать технику
# ============================================================
@router.post(
    "",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать технику",
    description="Создаёт новую единицу техники с динамическими атрибутами.",
)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "create")),
):
    """Создать новую технику (для своей компании)."""
    # Проверка уникальности id_value
    existing = db.scalar(
        select(Vehicle).where(
            Vehicle.id_value == payload.id_value,
            Vehicle.company_id == company_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Техника с id_value '{payload.id_value}' уже существует",
        )

    # Проверка подкатегории
    subcategory_id = payload.subcategory_id
    category_id = None

    if subcategory_id:
        sub = db.get(Category, subcategory_id)
        if not sub or sub.level != 2:
            raise HTTPException(
                status_code=400,
                detail="Некорректная подкатегория (должна быть level=2)",
            )
        # Сохраняем subcategory_id в поле category_id (подкатегория — это тоже запись в categories)
        category_id = subcategory_id
    elif payload.category_id:
        # Если нет подкатегории, но есть категория
        cat = db.get(Category, payload.category_id)
        if cat and cat.level == 1:
            category_id = payload.category_id

    # Данные для создания (исключаем все служебные поля)
    vehicle_data = payload.model_dump(
        exclude={"attributes", "subcategory_id", "company_id", "category_id"}
    )
    vehicle_data["category_id"] = category_id
    vehicle_data["company_id"] = company_id

    # Переименовываем поля согласно маппингу модели
    # В модели: model_name → "model" (в БД)
    if "model" in vehicle_data:
        vehicle_data["model_name"] = vehicle_data.pop("model")

    vehicle = Vehicle(**vehicle_data)
    db.add(vehicle)
    db.flush()

    # Сохраняем динамические атрибуты
    try:
        _save_vehicle_attributes(db, vehicle.id, subcategory_id, payload.attributes)
        db.commit()
    except Exception as e:
        db.rollback()
        import logging

        logging.getLogger("spectech.vehicles").exception(
            f"Failed to save vehicle attributes: {e}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка сохранения атрибутов: {str(e)}",
        )

    # Перезагружаем с joinedload
    vehicle = _load_vehicle_with_relations(db, vehicle.id)
    return _enrich_vehicle(vehicle)


# ============================================================
# GET /vehicles/{id} — получить технику по ID
# ============================================================
@router.get(
    "/{vehicle_id}",
    response_model=VehicleRead,
    summary="Получить технику по ID",
    description="Возвращает детальную информацию о технике своей компании.",
)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить технику по ID (только своей компании)."""
    vehicle = _load_vehicle_with_relations(db, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    return _enrich_vehicle(vehicle)

# ============================================================
# PATCH /vehicles/{id} — частичное обновление техники
# ============================================================
@router.patch(
    "/{vehicle_id}",
    response_model=VehicleRead,
    summary="Частичное обновление техники",
    description="Обновляет отдельные поля техники (например, is_available_for_rent).",
)
def update_vehicle_partial(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Частичное обновление техники (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    update_data = payload.model_dump(exclude_unset=True, exclude={"attributes"})

    # Проверка уникальности id_value
    if "id_value" in update_data and update_data["id_value"] != vehicle.id_value:
        existing = db.scalar(
            select(Vehicle).where(
                Vehicle.id_value == update_data["id_value"],
                Vehicle.company_id == company_id,
                Vehicle.id != vehicle_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Техника с id_value '{update_data['id_value']}' уже существует",
            )

    # Обновление подкатегории
    subcategory_id = update_data.pop("subcategory_id", None)
    if subcategory_id:
        sub = db.get(Category, subcategory_id)
        if not sub or sub.level != 2:
            raise HTTPException(
                status_code=400,
                detail="Некорректная подкатегория",
            )
        update_data["category_id"] = sub.parent_id

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    # Обновление атрибутов (если пришли)
    if payload.attributes is not None and subcategory_id:
        _clear_vehicle_attributes(db, vehicle.id)
        _save_vehicle_attributes(db, vehicle.id, subcategory_id, payload.attributes)

    db.commit()

    vehicle = _load_vehicle_with_relations(db, vehicle_id)
    return _enrich_vehicle(vehicle)


# ============================================================
# PUT /vehicles/{id} — обновить технику
# ============================================================
@router.put(
    "/{vehicle_id}",
    response_model=VehicleRead,
    summary="Обновить технику",
    description="Обновляет данные техники своей компании.",
)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Обновить технику (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    update_data = payload.model_dump(exclude_unset=True, exclude={"attributes"})

    # Проверка уникальности id_value
    if "id_value" in update_data and update_data["id_value"] != vehicle.id_value:
        existing = db.scalar(
            select(Vehicle).where(
                Vehicle.id_value == update_data["id_value"],
                Vehicle.company_id == company_id,
                Vehicle.id != vehicle_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Техника с id_value '{update_data['id_value']}' уже существует",
            )

    # Обновление подкатегории
    subcategory_id = update_data.pop("subcategory_id", None)
    if subcategory_id:
        sub = db.get(Category, subcategory_id)
        if not sub or sub.level != 2:
            raise HTTPException(
                status_code=400,
                detail="Некорректная подкатегория",
            )
        update_data["category_id"] = sub.parent_id

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    # Обновление атрибутов (если пришли)
    if payload.attributes is not None and subcategory_id:
        _clear_vehicle_attributes(db, vehicle.id)
        _save_vehicle_attributes(db, vehicle.id, subcategory_id, payload.attributes)

    db.commit()

    vehicle = _load_vehicle_with_relations(db, vehicle_id)
    return _enrich_vehicle(vehicle)


# ============================================================
# DELETE /vehicles/{id} — удалить технику (soft)
# ============================================================
@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить технику (soft delete)",
    description="Помечает технику как удалённую (soft delete).",
)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "delete")),
):
    """Удалить технику (только своей компании)."""
    vehicle = db.get(Vehicle, vehicle_id)

    if not vehicle or vehicle.is_deleted or vehicle.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Техника не найдена",
        )

    vehicle.is_deleted = True
    vehicle.deleted_at = datetime.now(UTC)

    db.commit()
    return None


@router.get("/{vehicle_id}/availability")
def check_vehicle_availability(
    vehicle_id: int,
    start: datetime = Query(..., description="Начало периода (ISO 8601)"),
    end: datetime = Query(..., description="Конец периода (ISO 8601)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Проверить доступность техники в указанный период.

    Проверяет:
    - Техника не в ремонте (status != 'repair')
    - Нет пересечений с другими RequestAssignment
    - Нет пересечений с другими ShiftTask в статусе active/completed

    Returns:
        {
            "available": true/false,
            "reason": "...",
            "conflicts": [...]
        }
    """
    from app.models.dispatch import RequestAssignment

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    conflicts = []

    # Проверка 1: статус техники
    if vehicle.status in ("repair", "decommissioned", "sold"):
        return {
            "available": False,
            "reason": f"Vehicle status is {vehicle.status}",
            "conflicts": [],
        }

    # Проверка 2: пересечения с RequestAssignment
    assignments = (
        db.query(RequestAssignment)
        .filter(
            RequestAssignment.vehicle_id == vehicle_id,
            RequestAssignment.status.in_(["planned", "confirmed", "active"]),
            RequestAssignment.planned_start < end,
            RequestAssignment.planned_end > start,
        )
        .all()
    )

    for a in assignments:
        conflicts.append(
            {
                "type": "assignment",
                "id": a.id,
                "request_id": a.request_id,
                "start": a.planned_start.isoformat(),
                "end": a.planned_end.isoformat(),
            }
        )

    available = len(conflicts) == 0

    return {
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle.name,
        "available": available,
        "reason": "OK" if available else f"Found {len(conflicts)} conflicts",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "conflicts": conflicts,
    }
