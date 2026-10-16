"""CRUD endpoints для водителей (DriverProfile + Employee/Contractor)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor, Employee, DriverProfile, DriverAssignmentLog
from app.models.user_company import UserCompany

router = APIRouter()


def _enrich_driver(emp: Employee, ctr: Contractor, profile: DriverProfile | None) -> dict:
    """Обогащает данные водителя."""
    data = {
        "contractor_id": emp.contractor_id,
        "full_name": ctr.name,
        "position": emp.position,
        "user_id": emp.user_id,
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
        "is_active": ctr.is_active,
    }
    if profile:
        data.update({
            "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            "passport_series": profile.passport_series,
            "passport_number": profile.passport_number,
            "passport_issued_by": profile.passport_issued_by,
            "passport_issue_date": profile.passport_issue_date.isoformat() if profile.passport_issue_date else None,
            "license_number": profile.license_number,
            "license_category": profile.license_category,
            "license_issue_date": profile.license_issue_date.isoformat() if profile.license_issue_date else None,
            "license_expiry_date": profile.license_expiry_date.isoformat() if profile.license_expiry_date else None,
            "machinist_certificate": profile.machinist_certificate,
            "machinist_certificate_type": profile.machinist_certificate_type,
            "machinist_certificate_expiry": profile.machinist_certificate_expiry.isoformat() if profile.machinist_certificate_expiry else None,
            "medical_cert_expiry": profile.medical_cert_expiry.isoformat() if profile.medical_cert_expiry else None,
            "safety_training_expiry": profile.safety_training_expiry.isoformat() if profile.safety_training_expiry else None,
            "notes": profile.notes,
        })
    else:
        for key in ["date_of_birth", "passport_series", "passport_number", "passport_issued_by",
                     "passport_issue_date", "license_number", "license_category",
                     "license_issue_date", "license_expiry_date", "machinist_certificate",
                     "machinist_certificate_type", "machinist_certificate_expiry",
                     "medical_cert_expiry", "safety_training_expiry", "notes"]:
            data[key] = None
    return data


@router.get("", summary="Список водителей")
def list_drivers(
    search: str | None = Query(None, description="Поиск по ФИО"),
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить список водителей компании."""
    stmt = (
        select(Employee, Contractor, DriverProfile)
        .join(Contractor, Employee.contractor_id == Contractor.id)
        .outerjoin(DriverProfile, Employee.contractor_id == DriverProfile.employee_contractor_id)
        .where(
            Contractor.company_id == company_id,
            Contractor.is_active == True,  # noqa: E712
        )
    )
    if search:
        q = f"%{search.lower()}%"
        stmt = stmt.where(Contractor.name.ilike(q))

    count_stmt = select(Employee.contractor_id).join(Contractor, Employee.contractor_id == Contractor.id).where(
        Contractor.company_id == company_id,
        Contractor.is_active == True,
        Employee.user_id.isnot(None),
    )
    if search:
        count_stmt = count_stmt.where(Contractor.name.ilike(f"%{search.lower()}%"))
    total = len(db.scalars(count_stmt).all())

    stmt = stmt.offset(skip).limit(limit)
    rows = db.execute(stmt).all()

    return {
        "items": [_enrich_driver(emp, ctr, prof) for emp, ctr, prof in rows],
        "total": total,
    }


@router.get("/{contractor_id}", summary="Профиль водителя")
def get_driver(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить профиль водителя по contractor_id."""
    row = db.execute(
        select(Employee, Contractor, DriverProfile)
        .join(Contractor, Employee.contractor_id == Contractor.id)
        .outerjoin(DriverProfile, Employee.contractor_id == DriverProfile.employee_contractor_id)
        .where(
            Employee.contractor_id == contractor_id,
            Contractor.company_id == company_id,
        )
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Водитель не найден")

    emp, ctr, prof = row
    return _enrich_driver(emp, ctr, prof)


@router.put("/{contractor_id}/profile", summary="Создать/обновить профиль водителя")
def upsert_driver_profile(
    contractor_id: int,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Создать или обновить профиль водителя."""
    # Проверяем что сотрудник существует и принадлежит компании
    row = db.execute(
        select(Employee, Contractor)
        .join(Contractor, Employee.contractor_id == Contractor.id)
        .where(
            Employee.contractor_id == contractor_id,
            Contractor.company_id == company_id,
        )
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    emp, ctr = row

    # Upsert профиля
    profile = db.get(DriverProfile, contractor_id)
    allowed_fields = [
        "date_of_birth", "passport_series", "passport_number", "passport_issued_by",
        "passport_issue_date", "license_number", "license_category",
        "license_issue_date", "license_expiry_date", "machinist_certificate",
        "machinist_certificate_type", "machinist_certificate_expiry",
        "medical_cert_expiry", "safety_training_expiry", "notes",
    ]

    if profile is None:
        profile = DriverProfile(employee_contractor_id=contractor_id)
        db.add(profile)

    for field in allowed_fields:
        if field in payload:
            val = payload[field]
            # Convert date strings to date objects
            if field.endswith("_date") or field in ("date_of_birth",) and isinstance(val, str) and val:
                try:
                    val = date.fromisoformat(val)
                except (ValueError, TypeError):
                    val = None
            elif val == "":
                val = None
            setattr(profile, field, val)

    # Привязка пользователя (user_id)
    if "user_id" in payload:
        new_user_id = payload["user_id"]
        if new_user_id is not None:
            # Проверяем что пользователь существует
            user = db.get(User, new_user_id)
            if not user:
                raise HTTPException(status_code=400, detail="Пользователь не найден")
            # Проверяем что пользователь не привязан к другому сотруднику
            existing_emp = db.query(Employee).filter(
                Employee.user_id == new_user_id,
                Employee.contractor_id != contractor_id,
            ).first()
            if existing_emp:
                raise HTTPException(
                    status_code=409,
                    detail=f"Пользователь уже привязан к другому сотруднику (contractor_id={existing_emp.contractor_id})"
                )
        emp.user_id = new_user_id

    db.commit()
    db.refresh(profile)

    return {"message": "Профиль сохранён", "contractor_id": contractor_id}


@router.post("", summary="Создать нового водителя")
def create_driver(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Создать нового водителя (Contractor + Employee + DriverProfile)."""
    from app.models.contractor import Contractor, Employee, DriverProfile

    full_name = payload.get("full_name", "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="ФИО обязательно")

    # 1. Создаём Contractor
    contractor = Contractor(
        type="employee",
        name=full_name,
        company_id=company_id,
        is_active=True,
        contact_phone=payload.get("phone"),
        contact_email=payload.get("email"),
    )
    db.add(contractor)
    db.flush()  # Получаем contractor.id

    # 2. Создаём Employee
    employee = Employee(
        contractor_id=contractor.id,
        position=payload.get("position", "Водитель"),
        role_in_system="driver",
        hire_date=payload.get("hire_date"),
        user_id=None,  # Привяжется позже
    )
    db.add(employee)
    db.flush()

    # 3. Создаём DriverProfile
    profile = DriverProfile(employee_contractor_id=contractor.id)
    date_fields = [
        "date_of_birth", "passport_issue_date", "license_issue_date",
        "license_expiry_date", "machinist_certificate_expiry",
        "medical_cert_expiry", "safety_training_expiry",
    ]
    str_fields = [
        "passport_series", "passport_number", "passport_issued_by",
        "license_number", "license_category",
        "machinist_certificate", "machinist_certificate_type",
        "notes",
    ]
    for field in str_fields:
        if field in payload and payload[field]:
            setattr(profile, field, payload[field])
    for field in date_fields:
        if field in payload and payload[field]:
            try:
                setattr(profile, field, date.fromisoformat(payload[field]))
            except (ValueError, TypeError):
                pass

    db.add(profile)
    db.commit()

    return {"contractor_id": contractor.id, "message": "Водитель создан"}


@router.get("/users", summary="Список пользователей компании (для привязки)")
def list_company_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список пользователей компании для выбора при привязке водителя."""
    from app.models.user_company import UserCompany

    stmt = (
        select(User)
        .join(UserCompany, User.id == UserCompany.user_id)
        .where(UserCompany.company_id == company_id)
        .order_by(User.full_name)
    )
    users = db.scalars(stmt).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name or u.email,
        }
        for u in users
    ]


@router.post("/create-user", summary="Создать пользователя и привязать к водителю")
def create_and_bind_user(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("vehicles", "update")),
):
    """Создать нового пользователя и привязать к водителю."""
    from app.core.security import get_password_hash
    from app.models.user_company import UserCompany

    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    contractor_id = payload.get("contractor_id")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email и пароль обязательны")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль минимум 6 символов")
    if not contractor_id:
        raise HTTPException(status_code=400, detail="contractor_id обязателен")

    # Проверяем что сотрудник существует
    emp = db.query(Employee).filter(
        Employee.contractor_id == contractor_id,
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    # Проверяем уникальность email
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Пользователь с email '{email}' уже существует")

    # Создаём пользователя
    full_name = payload.get("full_name", "").strip()
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name or None,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Привязываем к компании
    uc = UserCompany(user_id=user.id, company_id=company_id)
    db.add(uc)

    # Привязываем к сотруднику
    emp.user_id = user.id

    db.commit()

    return {"user_id": user.id, "email": email, "message": "Пользователь создан и привязан"}


@router.get("/{contractor_id}/history", summary="История назначений водителя")
def get_driver_history(
    contractor_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить историю назначений водителя на технику."""
    from app.models.catalog import Vehicle
    
    # Проверяем что водитель принадлежит компании
    ctr = db.query(Contractor).filter(
        Contractor.id == contractor_id,
        Contractor.company_id == company_id,
    ).first()
    if not ctr:
        raise HTTPException(status_code=404, detail="Водитель не найден")
    
    stmt = (
        select(DriverAssignmentLog, Vehicle)
        .join(Vehicle, DriverAssignmentLog.vehicle_id == Vehicle.id)
        .where(DriverAssignmentLog.driver_contractor_id == contractor_id)
        .order_by(DriverAssignmentLog.assigned_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    
    return [
        {
            "id": log.id,
            "vehicle_id": log.vehicle_id,
            "vehicle_name": veh.name,
            "vehicle_plate": veh.psm_number,
            "assigned_at": log.assigned_at.isoformat() if log.assigned_at else None,
            "unassigned_at": log.unassigned_at.isoformat() if log.unassigned_at else None,
            "notes": log.notes,
        }
        for log, veh in rows
    ]
