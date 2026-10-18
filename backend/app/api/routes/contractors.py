from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor, Employee
from app.schemas.contractor import (
    ContractorCreate,
    ContractorRead,
    ContractorUpdate,
    EmployeeCreate,
    EmployeeRead,
)
from app.services.dadata_service import dadata_service

router = APIRouter()


# 🆕 ВАЖНО: /me должен быть ПЕРЕД /{contractor_id}, иначе FastAPI воспримет "me" как ID
@router.get(
    "/me", response_model=ContractorRead, summary="Текущий contractor пользователя"
)
def get_my_contractor(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Возвращает contractor текущего пользователя.

    Логика:
    1. Ищем Employee связанного с user_id
    2. Если нет — возвращаем первого client-контрагента компании (fallback)
    """
    # Вариант 1: через Employee
    employee = db.scalar(select(Employee).where(Employee.user_id == current_user.id))

    if employee:
        contractor = db.get(Contractor, employee.contractor_id)
        if contractor:
            return contractor

    # Вариант 2 (fallback): первый client компании
    contractor = db.scalar(
        select(Contractor)
        .where(
            Contractor.company_id.in_(company_ids),
            Contractor.type == "client",
            Contractor.is_active == True,
        )
        .order_by(Contractor.id)
    )

    if not contractor:
        raise HTTPException(
            status_code=404,
            detail="Вы не привязаны ни к одному контрагенту. Создайте client-контрагента.",
        )

    return contractor


@router.get("", response_model=list[ContractorRead])
def list_contractors(
    type_filter: str | None = Query(default=None, alias="type"),
    is_active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список контрагентов (только своей компании)."""
    stmt = select(Contractor).where(Contractor.company_id.in_(company_ids))

    if type_filter:
        stmt = stmt.where(Contractor.type == type_filter)

    if is_active is not None:
        stmt = stmt.where(Contractor.is_active == is_active)

    stmt = stmt.order_by(Contractor.name).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=ContractorRead, status_code=201)
def create_contractor(
    payload: ContractorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать контрагента (для своей компании)."""
    valid_types = ["client", "owner", "employee"]
    if payload.type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {valid_types}",
        )

    contractor = Contractor(
        **payload.model_dump(),
        company_id=company_id,
    )
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    return contractor


@router.get("/{contractor_id}", response_model=ContractorRead)
def get_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Получить контрагента по ID (только своей компании)."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id not in company_ids:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return contractor


@router.patch("/{contractor_id}", response_model=ContractorRead)
def update_contractor(
    contractor_id: int,
    payload: ContractorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить контрагента (только своей компании)."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contractor, field, value)

    db.commit()
    db.refresh(contractor)
    return contractor


@router.delete("/{contractor_id}", status_code=204)
def delete_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить контрагента (только своей компании)."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")

    contractor.is_active = False
    db.commit()


# --- Employees ---


@router.get("/{contractor_id}/employees", response_model=list[EmployeeRead])
def list_employees(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список сотрудников контрагента (только своей компании)."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")

    stmt = select(Employee).where(Employee.contractor_id == contractor_id)
    return db.scalars(stmt).all()


@router.post("/suggest-inn")
async def suggest_contractor_by_inn(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Поиск контрагента по ИНН через DaData API."""
    inn = payload.get("inn", "").strip()

    if not inn:
        raise HTTPException(status_code=400, detail="ИНН обязателен")

    existing = db.scalar(
        select(Contractor).where(
            Contractor.inn == inn,
            Contractor.company_id.in_(company_ids),
        )
    )

    if existing:
        return {
            "found": True,
            "duplicate": True,
            "existing_id": existing.id,
            "existing_name": existing.name,
            "message": f"Контрагент '{existing.name}' с ИНН {inn} уже существует в системе",
        }

    result = await dadata_service.suggest_party_by_inn(inn)

    if not result:
        return {
            "found": False,
            "duplicate": False,
            "message": f"Контрагент с ИНН {inn} не найден в ЕГРЮЛ",
        }

    return {
        "found": True,
        "duplicate": False,
        "data": result,
        "message": f"Найден контрагент: {result['name']}",
    }


@router.post(
    "/{contractor_id}/employees",
    response_model=EmployeeRead,
    status_code=201,
)
def create_employee(
    contractor_id: int,
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать сотрудника (только для employee-типа контрагента своей компании)."""
    contractor = db.get(Contractor, contractor_id)
    if not contractor or contractor.company_id != company_id:
        raise HTTPException(status_code=404, detail="Contractor not found")

    if contractor.type != "employee":
        raise HTTPException(
            status_code=409,
            detail="Employee can only be added to employee-type contractor",
        )

    existing = db.get(Employee, contractor_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Employee already exists for this contractor",
        )

    employee = Employee(
        contractor_id=contractor_id,
        position=payload.position,
        role_in_system=payload.role_in_system,
        hire_date=payload.hire_date,
        user_id=payload.user_id,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee
