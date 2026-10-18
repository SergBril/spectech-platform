"""
⭐ API отзывов и рейтингов компаний.

Публичные endpoints:
- Просмотр отзывов о компании
- Статистика рейтинга

Приватные endpoints:
- Создание/обновление/удаление отзывов
- Проверка возможности оставить отзыв
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.models.review import Review
from app.services.reviews_service import reviews_service

logger = logging.getLogger("spectech.reviews_api")

router = APIRouter(tags=["⭐ Reviews (Отзывы и рейтинги)"])


# === Pydantic схемы ===


class ReviewCreate(BaseModel):
    """Создание отзыва."""

    rental_id: int = Field(..., gt=0, description="ID завершённой аренды")
    review_type: str = Field(
        ...,
        description="Тип отзыва: client_to_owner | owner_to_client",
        pattern="^(client_to_owner|owner_to_client)$",
    )
    rating: int = Field(..., ge=1, le=5, description="Общая оценка 1-5")
    comment: str | None = Field(
        default=None,
        min_length=10,
        max_length=2000,
        description="Текст отзыва (минимум 10 символов)",
    )
    pros: str | None = Field(default=None, max_length=1000, description="Плюсы")
    cons: str | None = Field(default=None, max_length=1000, description="Минусы")
    photos: list[str] | None = Field(
        default=None,
        max_length=5,
        description="URL фотографий (до 5 штук)",
    )
    quality_rating: int | None = Field(
        default=None, ge=1, le=5, description="Качество техники 1-5"
    )
    punctuality_rating: int | None = Field(
        default=None, ge=1, le=5, description="Пунктуальность 1-5"
    )
    communication_rating: int | None = Field(
        default=None, ge=1, le=5, description="Коммуникация 1-5"
    )
    is_anonymous: bool = Field(default=False, description="Анонимный отзыв")


class ReviewUpdate(BaseModel):
    """Обновление отзыва."""

    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, min_length=10, max_length=2000)
    pros: str | None = Field(default=None, max_length=1000)
    cons: str | None = Field(default=None, max_length=1000)
    photos: list[str] | None = Field(default=None, max_length=5)
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    punctuality_rating: int | None = Field(default=None, ge=1, le=5)
    communication_rating: int | None = Field(default=None, ge=1, le=5)


class ReviewRead(BaseModel):
    """Чтение отзыва."""

    id: int
    rental_id: int
    reviewer_contractor_id: int
    reviewer_name: str | None = None
    reviewed_company_id: int
    reviewed_company_name: str | None = None
    review_type: str

    rating: int
    comment: str | None = None
    pros: str | None = None
    cons: str | None = None
    photos: list[str] | None = None

    quality_rating: int | None = None
    punctuality_rating: int | None = None
    communication_rating: int | None = None

    status: str
    helpful_count: int
    is_anonymous: bool

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyRatingResponse(BaseModel):
    """Статистика рейтинга компании."""

    company_id: int
    company_name: str
    average_rating: float | None = None
    total_reviews: int
    distribution: dict[str, int]
    category_averages: dict[str, float | None]


class CanReviewResponse(BaseModel):
    """Проверка возможности оставить отзыв."""

    rental_id: int
    can_review_owner: bool
    can_review_client: bool
    has_reviewed_owner: bool
    has_reviewed_client: bool


class ReviewListResponse(BaseModel):
    """Список отзывов с пагинацией."""

    items: list[ReviewRead]
    total: int


# === Вспомогательные функции ===


def _get_current_contractor_id(db: Session, current_user: User) -> int:
    """Получает contractor_id текущего пользователя."""
    from app.models.contractor import Employee

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Ищем Employee по user_id
    employee = db.query(Employee).filter(Employee.user_id == current_user.id).first()

    if not employee:
        raise HTTPException(
            status_code=403,
            detail="User is not associated with any contractor. "
            "Cannot create or manage reviews.",
        )

    return employee.contractor_id


def _build_review_response(review: Review, db: Session) -> ReviewRead:
    """Построение ответа с полной информацией."""
    from app.models.company import Company
    from app.models.contractor import Contractor

    # Получаем имя автора (если не анонимный)
    reviewer_name = None
    if not review.is_anonymous:
        reviewer = db.get(Contractor, review.reviewer_contractor_id)
        if reviewer:
            reviewer_name = reviewer.name

    # Получаем название компании
    reviewed_company = db.get(Company, review.reviewed_company_id)
    reviewed_company_name = reviewed_company.name if reviewed_company else None

    # Нормализация photos
    photos = None
    if review.photos:
        if isinstance(review.photos, list):
            photos = [str(p) for p in review.photos if p]
        elif isinstance(review.photos, dict):
            photos = [str(v) for v in review.photos.values() if v]

    return ReviewRead(
        id=review.id,
        rental_id=review.rental_id,
        reviewer_contractor_id=review.reviewer_contractor_id,
        reviewer_name=reviewer_name,
        reviewed_company_id=review.reviewed_company_id,
        reviewed_company_name=reviewed_company_name,
        review_type=review.review_type,
        rating=review.rating,
        comment=review.comment,
        pros=review.pros,
        cons=review.cons,
        photos=photos,
        quality_rating=review.quality_rating,
        punctuality_rating=review.punctuality_rating,
        communication_rating=review.communication_rating,
        status=review.status,
        helpful_count=review.helpful_count,
        is_anonymous=review.is_anonymous,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


# === ПРИВАТНЫЕ ENDPOINTS (требуют авторизацию) ===


@router.post(
    "/reviews",
    response_model=ReviewRead,
    status_code=201,
    summary="Создать отзыв",
    description="Создаёт отзыв на завершённую аренду. Можно оставить только для Rental.status=COMPLETED.",
)
def create_review(
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ⭐ Создать отзыв на завершённую аренду.

    - **rental_id**: ID аренды (должна быть в статусе COMPLETED)
    - **review_type**:
      - `client_to_owner` — клиент оценивает собственника техники
      - `owner_to_client` — собственник оценивает клиента
    - **rating**: Общая оценка от 1 до 5
    - **comment**: Текст отзыва (минимум 10 символов)
    - **pros/cons**: Плюсы и минусы (опционально)
    - **photos**: URL фотографий (до 5 штук)
    - **quality_rating/punctuality_rating/communication_rating**: Детальные оценки (опционально)
    - **is_anonymous**: Анонимный отзыв (имя автора не показывается)

    Один участник аренды может оставить только один отзыв на каждую сторону.
    """
    contractor_id = _get_current_contractor_id(db, current_user)

    try:
        review = reviews_service.create_review(
            db=db,
            rental_id=data.rental_id,
            reviewer_contractor_id=contractor_id,
            review_type=data.review_type,
            rating=data.rating,
            comment=data.comment,
            pros=data.pros,
            cons=data.cons,
            photos=data.photos,
            quality_rating=data.quality_rating,
            punctuality_rating=data.punctuality_rating,
            communication_rating=data.communication_rating,
            is_anonymous=data.is_anonymous,
        )

        logger.info(
            "Review #%s created by user %s (contractor %s)",
            review.id,
            current_user.id,
            contractor_id,
        )

        return _build_review_response(review, db)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create review: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create review")


@router.get(
    "/reviews/my",
    response_model=ReviewListResponse,
    summary="Мои отзывы",
    description="Список отзывов, оставленных текущим пользователем.",
)
def get_my_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """🔐 Получить список моих оставленных отзывов."""
    contractor_id = _get_current_contractor_id(db, current_user)

    reviews = reviews_service.get_my_reviews(
        db=db,
        reviewer_contractor_id=contractor_id,
        limit=limit,
        offset=offset,
    )

    # Общее количество
    from sqlalchemy import func

    total = (
        db.query(func.count(Review.id))
        .filter(Review.reviewer_contractor_id == contractor_id)
        .scalar()
        or 0
    )

    return ReviewListResponse(
        items=[_build_review_response(r, db) for r in reviews],
        total=total,
    )


@router.get(
    "/reviews/can-review/{rental_id}",
    response_model=CanReviewResponse,
    summary="Проверка возможности оставить отзыв",
    description="Проверяет, может ли текущий пользователь оставить отзыв на конкретную аренду.",
)
def can_leave_review(
    rental_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """🔐 Проверить, можно ли оставить отзыв на аренду."""
    contractor_id = _get_current_contractor_id(db, current_user)

    result = reviews_service.can_leave_review(
        db=db,
        rental_id=rental_id,
        contractor_id=contractor_id,
    )

    return CanReviewResponse(rental_id=rental_id, **result)


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Обновить отзыв",
    description="Обновляет существующий отзыв. Может обновить только автор.",
)
def update_review(
    review_id: int,
    data: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """🔐 Обновить свой отзыв."""
    contractor_id = _get_current_contractor_id(db, current_user)

    try:
        updates = data.model_dump(exclude_unset=True)
        review = reviews_service.update_review(
            db=db,
            review_id=review_id,
            reviewer_contractor_id=contractor_id,
            **updates,
        )

        logger.info(
            "Review #%s updated by user %s",
            review.id,
            current_user.id,
        )

        return _build_review_response(review, db)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update review: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update review")


@router.delete(
    "/reviews/{review_id}",
    status_code=204,
    summary="Удалить отзыв",
    description="Удаляет отзыв. Может удалить только автор.",
)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """🔐 Удалить свой отзыв."""
    contractor_id = _get_current_contractor_id(db, current_user)

    try:
        reviews_service.delete_review(
            db=db,
            review_id=review_id,
            reviewer_contractor_id=contractor_id,
        )

        logger.info(
            "Review #%s deleted by user %s",
            review_id,
            current_user.id,
        )

        return None

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to delete review: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete review")


# === ПУБЛИЧНЫЕ ENDPOINTS (без авторизации) ===


@router.post(
    "/public/reviews/{review_id}/helpful",
    summary="Отметить отзыв как полезный",
    description="Увеличивает счётчик helpful_count у отзыва.",
)
def mark_review_helpful(
    review_id: int,
    db: Session = Depends(get_db),
):
    """🌐 Отметить отзыв как полезный (без авторизации)."""
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.status != "approved":
        raise HTTPException(status_code=400, detail="Review is not approved")

    review.helpful_count += 1
    db.commit()

    return {
        "message": "Review marked as helpful",
        "helpful_count": review.helpful_count,
    }
