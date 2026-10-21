"""
🌐 Публичные endpoints для маркетплейса.
Эти endpoints НЕ требуют аутентификации (или требуют опциональную).
Используются для:
- Публичного каталога техники
- Публичной доски заявок
- Публичных профилей компаний
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.catalog import Category, Vehicle
from app.models.company import Company

logger = logging.getLogger("spectech.public")

router = APIRouter(prefix="/public", tags=["🌐 Public (Маркетплейс)"])


# === Схемы ===


class PublicCompanyRead(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    company_type: str | None = None  # 'owner', 'client', 'dispatcher', 'mixed'
    description: str | None = None
    logo_url: str | None = None
    city: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    total_deals: int = 0
    is_verified: bool = False
    vehicles_count: int = 0
    created_at: str | None = None

    model_config = {"from_attributes": True}


class PublicVehicleRead(BaseModel):
    id: int
    name: str
    category_name: str | None = None
    year: int | None = None
    status: str
    hourly_rate: float | None = None
    shift_rate: float | None = None
    is_available_for_rent: bool = False
    photos: list[str] | None = None
    owner_company_id: int
    owner_company_name: str | None = None
    marketplace_commission_agreed: bool = False
    marketplace_commission_rate: float | None = None

    model_config = {"from_attributes": True}


# === Вспомогательные функции ===


def _to_float(value) -> float | None:
    """Безопасное конвертирование Decimal/str/int → float."""
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_photos(value) -> list[str] | None:
    """Нормализация поля photos из БД (может быть list, dict, str, None)."""
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    if isinstance(value, str):
        return [value] if value else None
    if isinstance(value, dict):
        # Если это объект, преобразуем в список значений
        return [str(v) for v in value.values() if v is not None]
    return None


def _build_vehicle_response(
    v: Vehicle, company_name: str | None = None
) -> PublicVehicleRead:
    """Построение ответа для техники."""
    # Получаем имя компании из relationship, если не передано явно
    if company_name is None:
        try:
            company_name = v.company.name if v.company else None
        except Exception:
            company_name = None

    return PublicVehicleRead(
        id=v.id,
        name=v.name,
        category_name=v.category.name if v.category else None,
        year=v.year,
        status=v.status,
        hourly_rate=_to_float(getattr(v, "hourly_rate", None)),
        shift_rate=_to_float(getattr(v, "shift_rate", None)),
        is_available_for_rent=bool(getattr(v, "is_available_for_rent", False)),
        photos=_normalize_photos(getattr(v, "photos", None)),
        owner_company_id=v.company_id or 0,
        owner_company_name=company_name,
    )


# === Endpoints: Компании ===


@router.get("/health", summary="Health check")
def health_check():
    """🌐 Проверка работоспособности."""
    return {"status": "ok", "timestamp": "2026-10-12"}


@router.get("/companies", response_model=list[PublicCompanyRead])
def list_public_companies(
    company_type: str | None = Query(
        default=None, description="Фильтр по типу: owner, client, dispatcher, mixed"
    ),
    city: str | None = Query(default=None, description="Фильтр по городу"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """🌐 Публичный список компаний (для маркетплейса)."""
    try:
        stmt = select(Company).where(Company.is_active == True)

        if company_type and hasattr(Company, "company_type"):
            stmt = stmt.where(Company.company_type == company_type)
        if city and hasattr(Company, "city"):
            stmt = stmt.where(Company.city == city)

        stmt = stmt.offset(offset).limit(limit).order_by(Company.created_at.desc())
        companies = db.scalars(stmt).all()

        result = []
        for c in companies:
            vehicles_count = (
                db.query(Vehicle).filter(Vehicle.company_id == c.id).count()
            )
            result.append(
                PublicCompanyRead(
                    id=c.id,
                    name=c.name,
                    legal_name=c.legal_name,
                    company_type=getattr(c, "company_type", None),
                    description=getattr(c, "description", None),
                    logo_url=getattr(c, "logo_url", None),
                    city=getattr(c, "city", None),
                    phone=getattr(c, "phone", None),
                    website=getattr(c, "website", None),
                    rating=4.5,  # TODO: реальный рейтинг из user_ratings
                    total_deals=10,  # TODO: реальный подсчёт сделок
                    is_verified=bool(getattr(c, "is_verified", False)),
                    vehicles_count=vehicles_count,
                    created_at=c.created_at.isoformat() if c.created_at else None,
                )
            )
        return result

    except Exception as e:
        logger.exception("❌ Error in list_public_companies: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/companies/{company_id}", response_model=PublicCompanyRead)
def get_public_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Публичный профиль компании."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        vehicles_count = (
            db.query(Vehicle).filter(Vehicle.company_id == company.id).count()
        )

        return PublicCompanyRead(
            id=company.id,
            name=company.name,
            legal_name=company.legal_name,
            company_type=getattr(company, "company_type", None),
            description=getattr(company, "description", None),
            logo_url=getattr(company, "logo_url", None),
            city=getattr(company, "city", None),
            phone=getattr(company, "phone", None),
            website=getattr(company, "website", None),
            rating=4.5,
            total_deals=10,
            is_verified=bool(getattr(company, "is_verified", False)),
            vehicles_count=vehicles_count,
            created_at=company.created_at.isoformat() if company.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/companies/{company_id}/vehicles", response_model=list[PublicVehicleRead])
def get_public_company_vehicles(
    company_id: int,
    category_id: int | None = None,
    available_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """🌐 Публичный список техники компании."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        stmt = select(Vehicle).where(Vehicle.company_id == company_id)

        if category_id:
            stmt = stmt.where(Vehicle.category_id == category_id)
        if available_only and hasattr(Vehicle, "is_available_for_rent"):
            stmt = stmt.where(Vehicle.is_available_for_rent == True)

        stmt = stmt.limit(limit)
        vehicles = db.scalars(stmt).all()

        return [_build_vehicle_response(v, company.name) for v in vehicles]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company_vehicles: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Техника (глобальный каталог) ===


@router.get("/vehicles", response_model=list[PublicVehicleRead])
def list_public_vehicles(
    category_id: int | None = None,
    company_id: int | None = None,
    available_only: bool = Query(default=False),
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    🌐 Публичный каталог доступной техники (для маркетплейса).

    Основной endpoint для поиска техники заказчиками.
    """
    try:
        stmt = (
            select(Vehicle)
            .join(Company, Vehicle.company_id == Company.id)
            .where(Company.is_active == True)
        )

        # В маркетплейсе показываем только технику с согласием на комиссию
        stmt = stmt.where(Vehicle.marketplace_commission_agreed == True)

        if category_id:
            stmt = stmt.where(Vehicle.category_id == category_id)
        if company_id:
            stmt = stmt.where(Vehicle.company_id == company_id)
        if available_only and hasattr(Vehicle, "is_available_for_rent"):
            stmt = stmt.where(Vehicle.is_available_for_rent == True)
        if min_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
            stmt = stmt.where(Vehicle.hourly_rate >= min_hourly_rate)
        if max_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
            stmt = stmt.where(Vehicle.hourly_rate <= max_hourly_rate)

        stmt = stmt.offset(offset).limit(limit)
        vehicles = db.scalars(stmt).all()

        return [_build_vehicle_response(v) for v in vehicles]

    except Exception as e:
        logger.exception("❌ Error in list_public_vehicles: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Детальная страница техники ===


@router.get("/vehicles/{vehicle_id}", response_model=PublicVehicleRead)
def get_public_vehicle_details(
    vehicle_id: int,
    db: Session = Depends(get_db),
):
    """
    🌐 Детальная страница техники (публичная).

    Возвращает только опубликованную технику.
    """
    try:
        from app.services.marketplace_service import marketplace_service

        vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=404, detail="Vehicle not found or not published"
            )

        return _build_vehicle_response(vehicle)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_vehicle_details: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


class VehicleAvailabilityResponse(BaseModel):
    """Календарь доступности техники."""

    vehicle_id: int
    vehicle_name: str
    from_date: str
    to_date: str
    calendar: list[dict]

    model_config = {"from_attributes": True}


@router.get(
    "/vehicles/{vehicle_id}/availability",
    response_model=VehicleAvailabilityResponse,
)
def get_vehicle_availability(
    vehicle_id: int,
    from_date: str | None = Query(
        default=None,
        description="Начальная дата (YYYY-MM-DD), по умолчанию сегодня",
    ),
    to_date: str | None = Query(
        default=None,
        description="Конечная дата (YYYY-MM-DD), по умолчанию +30 дней",
    ),
    db: Session = Depends(get_db),
):
    """
    🌐 Календарь доступности техники на основе Rental.

    Возвращает список дат с флагом `available` и `rental_id` (если занята).
    """
    from datetime import date as DateType

    from app.services.marketplace_service import marketplace_service

    try:
        vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=404, detail="Vehicle not found or not published"
            )

        # Парсим даты
        from_dt = DateType.fromisoformat(from_date) if from_date else None
        to_dt = DateType.fromisoformat(to_date) if to_date else None

        calendar = marketplace_service.get_availability_calendar(
            db, vehicle_id, from_dt, to_dt
        )

        return VehicleAvailabilityResponse(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            from_date=calendar[0]["date"] if calendar else "",
            to_date=calendar[-1]["date"] if calendar else "",
            calendar=calendar,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_vehicle_availability: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Создание заявки из витрины ===


class PublicRequestCreate(BaseModel):
    """Схема создания заявки из публичной витрины."""

    work_type: str = Field(..., min_length=1, max_length=255, description="Тип работ")
    planned_start: str = Field(..., description="Начало (ISO format)")
    planned_end: str = Field(..., description="Окончание (ISO format)")
    comment: str | None = Field(
        default=None, max_length=2000, description="Комментарий"
    )

    # Контакты (для связи с заказчиком)
    contact_name: str = Field(..., min_length=1, max_length=255)
    contact_phone: str = Field(..., min_length=10, max_length=20)
    contact_email: str | None = Field(default=None)


class PublicRequestResponse(BaseModel):
    """Ответ с созданной заявкой."""

    request_id: int
    vehicle_id: int
    vehicle_name: str
    status: str
    planned_start: str
    planned_end: str
    message: str

    model_config = {"from_attributes": True}


@router.post(
    "/vehicles/{vehicle_id}/request",
    response_model=PublicRequestResponse,
    status_code=201,
)
def create_request_from_listing(
    vehicle_id: int,
    data: PublicRequestCreate,
    db: Session = Depends(get_db),
):
    """
    🌐 Создание заявки из публичной витрины (без регистрации).

    Отправляет уведомление собственнику техники.

    **Примечание:** В production здесь должна быть проверка reCAPTCHA
    или регистрация через телефон/email для защиты от спама.
    """
    from datetime import datetime as dt

    from app.models.contractor import Contractor
    from app.services.marketplace_service import marketplace_service

    try:
        # 1. Проверяем технику
        vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=404, detail="Vehicle not found or not published"
            )

        # 2. Парсим даты
        try:
            planned_start = dt.fromisoformat(data.planned_start)
            planned_end = dt.fromisoformat(data.planned_end)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid datetime format: {e}")

        if planned_start >= planned_end:
            raise HTTPException(
                status_code=400,
                detail="planned_end must be after planned_start",
            )

        # 3. Создаём или находим Contractor (клиента) по контактным данным
        # В production: через регистрацию или привязку к user
        # Сейчас: создаём временного contractor для заявки
        client_contractor = Contractor(
            name=data.contact_name,
            type="client",
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
            email=data.contact_email,
            company_id=vehicle.company_id,  # Привязываем к компании маркетплейса
        )
        db.add(client_contractor)
        db.flush()

        # 4. Создаём заявку
        request = marketplace_service.create_request_from_listing(
            db=db,
            vehicle_id=vehicle_id,
            client_contractor_id=client_contractor.id,
            company_id=vehicle.company_id or 1,
            work_type=data.work_type,
            planned_start=planned_start,
            planned_end=planned_end,
            comment=data.comment,
        )

        return PublicRequestResponse(
            request_id=request.id,
            vehicle_id=vehicle_id,
            vehicle_name=vehicle.name,
            status=(
                request.status.value
                if hasattr(request.status, "value")
                else str(request.status)
            ),
            planned_start=planned_start.isoformat(),
            planned_end=planned_end.isoformat(),
            message=(
                f"✅ Заявка #{request.id} создана. "
                f"Собственник техники '{vehicle.name}' получит уведомление."
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in create_request_from_listing: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Рейтинг и отзывы компании ===


@router.get("/companies/{company_id}/rating")
def get_public_company_rating(
    company_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Рейтинг компании (средний балл и количество отзывов)."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        # TODO: когда будет таблица Review - заменить на реальный подсчёт
        # Сейчас возвращаем захардкоженные значения из PublicCompanyRead
        from sqlalchemy import func

        from app.models.review import Review

        result = (
            db.query(
                func.coalesce(func.avg(Review.rating), 0).label("avg_rating"),
                func.count(Review.id).label("total"),
            )
            .filter(
                Review.reviewed_company_id == company_id,
                Review.status == "approved",
            )
            .one()
        )

        return {
            "average_rating": (
                round(float(result.avg_rating), 2) if result.total > 0 else None
            ),
            "total_reviews": int(result.total or 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company_rating: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/companies/{company_id}/reviews")
def get_public_company_reviews(
    company_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """🌐 Отзывы о компании."""
    try:
        company = db.get(Company, company_id)
        if not company or not company.is_active:
            raise HTTPException(status_code=404, detail="Company not found")

        # TODO: когда будет таблица Review - заменить на реальные отзывы
        # Сейчас возвращаем мок-данные для демонстрации
        from app.models.contractor import Contractor
        from app.models.review import Review

        reviews = (
            db.query(Review)
            .join(Contractor, Review.reviewer_contractor_id == Contractor.id)
            .filter(
                Review.reviewed_company_id == company_id,
                Review.status == "approved",
            )
            .order_by(Review.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "reviewer_contractor_name": (
                    r.reviewer.name if r.reviewer else "Anonymous"
                ),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error in get_public_company_reviews: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# === Endpoints: Категории техники ===


@router.get("/categories")
def list_public_categories(db: Session = Depends(get_db)):
    """🌐 Публичный список категорий техники."""
    try:
        stmt = select(Category).order_by(Category.level, Category.name)
        categories = db.scalars(stmt).all()

        result = []
        for c in categories:
            vehicles_count = (
                db.query(Vehicle).filter(Vehicle.category_id == c.id).count()
            )
            result.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "level": c.level,
                    "parent_id": c.parent_id,
                    "is_active": c.is_active,
                    "company_id": c.company_id,
                    "vehicles_count": vehicles_count,
                    "created_at": (c.created_at.isoformat() if c.created_at else None),
                }
            )
        return result

    except Exception as e:
        logger.exception("❌ Error in list_public_categories: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ============================================================
# 🌟 СОЗДАНИЕ ОТЗЫВА О КОМПАНИИ (публичный)
# ============================================================


class PublicCompanyReviewCreate(BaseModel):
    """Схема для создания отзыва о компании."""

    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=10, max_length=2000)
    reviewer_name: str | None = Field(None, max_length=255)
    reviewer_contractor_id: int | None = None


@router.post("/companies/{company_id}/marketplace-reviews", status_code=201)
def create_company_review(
    company_id: int,
    payload: PublicCompanyReviewCreate,
    db: Session = Depends(get_db),
):
    """🌐 Создать отзыв о компании на маркетплейсе."""
    from sqlalchemy import text

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    # Проверяем дубликат по reviewer_name + company_id
    existing = db.execute(
        text(
            """
            SELECT id FROM company_reviews
            WHERE company_id = :cid
              AND reviewer_name = :rname
              AND is_published = true
        """
        ),
        {"cid": company_id, "rname": payload.reviewer_name or "Анонимный пользователь"},
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Вы уже оставляли отзыв об этой компании"
        )

    # Создаём отзыв (используем reviewer_user_id = NULL для анонимных)
    result = db.execute(
        text(
            """
            INSERT INTO company_reviews
                (company_id, reviewer_user_id, reviewer_name, reviewer_email,
                 rating, comment, is_verified, is_published, moderation_status,
                 created_at, updated_at)
            VALUES
                (:cid, NULL, :rname, :remail,
                 :rating, :comment, false, true, 'approved',
                 NOW(), NOW())
            RETURNING id, rating, comment, created_at
        """
        ),
        {
            "cid": company_id,
            "rname": payload.reviewer_name or "Анонимный пользователь",
            "remail": None,
            "rating": payload.rating,
            "comment": payload.comment,
        },
    ).one()
    db.commit()

    return {
        "id": result.id,
        "rating": result.rating,
        "comment": result.comment,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "message": "Отзыв успешно опубликован",
    }


@router.get("/companies/{company_id}/marketplace-reviews")
def get_company_reviews_public(
    company_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """🌐 Получить отзывы о компании."""
    from sqlalchemy import text

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    avg_result = db.execute(
        text(
            "SELECT COALESCE(AVG(rating), 0) as avg_rating, COUNT(*) as total FROM company_reviews WHERE company_id = :cid AND is_published = true"
        ),
        {"cid": company_id},
    ).one()

    dist_result = db.execute(
        text(
            "SELECT rating, COUNT(*) as cnt FROM company_reviews WHERE company_id = :cid AND is_published = true GROUP BY rating"
        ),
        {"cid": company_id},
    ).all()
    distribution = {str(i): 0 for i in range(1, 6)}
    for row in dist_result:
        distribution[str(row.rating)] = row.cnt

    reviews_result = db.execute(
        text(
            """
            SELECT id, rating, comment, reviewer_name, is_verified, created_at
            FROM company_reviews
            WHERE company_id = :cid AND is_published = true
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        ),
        {"cid": company_id, "limit": limit, "offset": offset},
    ).all()

    items = [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "reviewer_name": r.reviewer_name or "Аноним",
            "reviewer_contractor_name": r.reviewer_name or "Аноним",
            "is_verified": r.is_verified,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews_result
    ]

    return {
        "items": items,
        "total": int(avg_result.total or 0),
        "average_rating": float(avg_result.avg_rating or 0),
        "rating_distribution": distribution,
    }
