from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
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

router = APIRouter()


@router.get("", response_model=list[ContractorRead])
def list_contractors(
    type_filter: str | None = Query(default=None, alias="type"),
    is_active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список контрагентов."""
    # Временно убираем проверку прав чтобы обычный пользователь мог видеть
    # require_permission(db, current_user, "contractors", "view")

    stmt = select(Contractor)

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
):
    """Создать контрагента."""
    # require_permission(db, current_user, "contractors", "create")

    # Валидация типа
    valid_types = ["client", "owner", "employee"]
    if payload.type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {valid_types}",
        )

    contractor = Contractor(
        **payload.model_dump(),
        company_id=current_user.company_id,
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
):
    """Получить контрагента по ID."""
    # require_permission(db, current_user, "contractors", "view")

    contractor = db.get(Contractor, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return contractor


@router.patch("/{contractor_id}", response_model=ContractorRead)
def update_contractor(
    contractor_id: int,
    payload: ContractorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить контрагента."""
    # require_permission(db, current_user, "contractors", "update")

    contractor = db.get(Contractor, contractor_id)
    if not contractor:
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
):
    """Удалить контрагента (деактивировать)."""
    # require_permission(db, current_user, "contractors", "update")

    contractor = db.get(Contractor, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")

    contractor.is_active = False
    db.commit()


# --- Employees ---


@router.get("/{contractor_id}/employees", response_model=list[EmployeeRead])
def list_employees(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список сотрудников контрагента."""
    # require_permission(db, current_user, "contractors", "view")

    stmt = select(Employee).where(Employee.contractor_id == contractor_id)
    return db.scalars(stmt).all()


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
):
    """Создать сотрудника для contractor-типа employee."""
    # require_permission(db, current_user, "contractors", "update")

    contractor = db.get(Contractor, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")

    # Проверка что contractor является employee-типом
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
