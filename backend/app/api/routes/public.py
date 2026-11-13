import logging

"""Публичные API эндпоинты — тонкие wrapper'ы над PublicService."""


from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_company_id,
    get_current_company_id_optional,
    get_current_user,
    get_current_user_optional,
)
from app.core.db import get_db
from app.models.auth import User
from app.schemas.public import PublicVehicleRead
from app.services.public_service import public_service

router = APIRouter()

logger = logging.getLogger("spectech.public")

router = APIRouter(prefix="/public", tags=["marketplace"])


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


class VehicleAvailabilityResponse(BaseModel):
    """Календарь доступности техники."""

    vehicle_id: int
    vehicle_name: str
    from_date: str
    to_date: str
    calendar: list[dict]

    model_config = {"from_attributes": True}


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


class PublicCompanyReviewCreate(BaseModel):
    """Схема для создания отзыва о компании."""

    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=10, max_length=2000)
    reviewer_name: str | None = Field(None, max_length=255)
    reviewer_contractor_id: int | None = None


@router.get("/health")
def health_check(
    db: Session = Depends(get_db),
):
    """🌐 Проверка работоспособности."""

    return public_service.health_check(db=db)


@router.get("/companies")
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

    return public_service.list_public_companies(
        db=db, company_type=company_type, city=city, limit=limit, offset=offset
    )


@router.get("/companies/{company_id}", response_model=PublicCompanyRead)
def get_public_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Публичный профиль компании."""

    return public_service.get_public_company(db=db, company_id=company_id)


@router.get("/companies/{company_id}/vehicles")
def get_public_company_vehicles(
    company_id: int,
    category_id: int | None = None,
    available_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """🌐 Публичный список техники компании."""

    return public_service.get_public_company_vehicles(
        db=db,
        company_id=company_id,
        category_id=category_id,
        available_only=available_only,
        limit=limit,
    )


@router.get("/vehicles")
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

    return public_service.list_public_vehicles(
        db=db,
        category_id=category_id,
        available_only=available_only,
        min_hourly_rate=min_hourly_rate,
        max_hourly_rate=max_hourly_rate,
        limit=limit,
        offset=offset,
    )


@router.get("/vehicles/{vehicle_id}", response_model=PublicVehicleRead)
def get_public_vehicle_details(
    vehicle_id: int,
    db: Session = Depends(get_db),
):
    """

    🌐 Детальная страница техники (публичная).



    Возвращает только опубликованную технику.

    """

    return public_service.get_public_vehicle_details(db=db, vehicle_id=vehicle_id)


@router.get(
    "/vehicles/{vehicle_id}/availability", response_model=VehicleAvailabilityResponse
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

    return public_service.get_vehicle_availability(
        db=db, vehicle_id=vehicle_id, from_date=from_date, to_date=to_date
    )


@router.post(
    "/vehicles/{vehicle_id}/request",
    status_code=201,
    response_model=PublicRequestResponse,
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

    return public_service.create_request_from_listing(
        db=db, vehicle_id=vehicle_id, data=data
    )


@router.get("/companies/{company_id}/rating")
def get_public_company_rating(
    company_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Рейтинг компании (средний балл и количество отзывов)."""

    return public_service.get_public_company_rating(db=db, company_id=company_id)


@router.get("/companies/{company_id}/reviews")
def get_public_company_reviews(
    company_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """🌐 Отзывы о компании."""

    return public_service.get_public_company_reviews(
        db=db, company_id=company_id, limit=limit
    )


@router.get("/categories")
def list_public_categories(
    db: Session = Depends(get_db),
):
    """🌐 Публичный список категорий техники."""

    return public_service.list_public_categories(db=db)


@router.get("/marketplace/requests")
def list_marketplace_requests(
    category_id: int | None = None,
    cross_category: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User | None = Depends(get_current_user_optional),
    company_id: int | None = Depends(get_current_company_id_optional),
    db: Session = Depends(get_db),
):
    """

    🌐 Публичный список заявок в маркетплейсе.



    Возвращает только опубликованные заявки из маркетплейса с условиями оплаты.

    Исполнители видят: требования, срок оплаты, режим (заказчик/диспетчер).

    """

    return public_service.list_marketplace_requests(
        db=db,
        company_id=company_id,
        category_id=category_id,
        cross_category=cross_category,
        limit=limit,
        offset=offset,
    )


@router.post("/marketplace/requests/{request_id}/respond", status_code=201)
async def respond_to_marketplace_request(
    request_id: int,
    vehicle_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """

    🌐 Откликнуться на заявку маркетплейса.



    Исполнитель указывает свою технику для выполнения заказа.

    Владелец заявки получает уведомление об отклике.

    """

    return public_service.respond_to_marketplace_request(
        db=db,
        company_id=company_id,
        current_user=current_user,
        request_id=request_id,
        vehicle_id=vehicle_id,
    )


@router.get("/marketplace/payouts-report")
def marketplace_payouts_report(
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта по выплатам маркетплейса в Excel."""

    return public_service.marketplace_payouts_report(
        db=db, date_from=date_from, date_to=date_to, company_id=company_id
    )


@router.get("/marketplace/stats")
def marketplace_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика маркетплейса для дашборда."""

    return public_service.marketplace_stats(db=db, company_id=company_id)


@router.get("/marketplace/requests/export")
def export_marketplace_requests(
    category_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт заявок маркетплейса в Excel."""

    return public_service.export_marketplace_requests(
        db=db, category_id=category_id, company_id=company_id
    )


@router.get("/marketplace/my-responses")
def list_my_responses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список откликов текущей компании на заявки маркетплейса."""

    return public_service.list_my_responses(db=db, company_id=company_id)


@router.post("/companies/{company_id}/marketplace-reviews")
def create_company_review(
    company_id: int,
    payload: PublicCompanyReviewCreate,
    db: Session = Depends(get_db),
):
    """🌐 Создать отзыв о компании на маркетплейсе."""

    return public_service.create_company_review(
        db=db, company_id=company_id, payload=payload
    )


@router.get("/companies/{company_id}/marketplace-reviews")
def get_company_reviews_public(
    company_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """🌐 Получить отзывы о компании."""

    return public_service.get_company_reviews_public(
        db=db, company_id=company_id, limit=limit, offset=offset
    )
