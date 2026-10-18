"""Pydantic схемы для отзывов о компаниях."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CompanyReviewCreate(BaseModel):
    """Схема создания отзыва."""

    company_id: int
    rating: int = Field(..., ge=1, le=5, description="Рейтинг от 1 до 5")
    comment: str = Field(..., min_length=10, max_length=2000)
    request_id: int | None = None

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Комментарий должен содержать минимум 10 символов")
        return v.strip()


class CompanyReviewResponse(BaseModel):
    """Схема ответа на отзыв от компании."""

    response: str = Field(..., min_length=10, max_length=2000)

    @field_validator("response")
    @classmethod
    def validate_response(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Ответ должен содержать минимум 10 символов")
        return v.strip()


class CompanyReviewRead(BaseModel):
    """Схема для чтения отзыва."""

    id: int
    company_id: int
    reviewer_contractor_id: int
    reviewer_contractor_name: str | None = None
    reviewer_user_id: int | None = None
    request_id: int | None = None
    rating: int
    comment: str
    response: str | None = None
    responded_at: datetime | None = None
    is_verified: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompanyRatingSummary(BaseModel):
    """Сводка по рейтингу компании."""

    company_id: int
    company_name: str
    average_rating: float
    total_reviews: int
    rating_distribution: dict[str, int] = Field(
        default_factory=lambda: {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    )

    class Config:
        from_attributes = True
