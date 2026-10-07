"""Модель отзывов на завершённые аренды."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class ReviewType(str):
    """Тип отзыва (кто кого оценивает)."""
    CLIENT_TO_OWNER = "client_to_owner"    # Клиент оценивает собственника
    OWNER_TO_CLIENT = "owner_to_client"    # Собственник оценивает клиента


class ReviewStatus(str):
    """Статус отзыва (модерация)."""
    PENDING = "pending"       # На модерации
    APPROVED = "approved"     # Одобрено
    REJECTED = "rejected"     # Отклонено
    HIDDEN = "hidden"         # Скрыто администратором


class Review(Base):
    """
    Отзыв на завершённую аренду.
    
    Один Rental может иметь до 2 отзывов:
    - Один от клиента (о компании-собственнике техники)
    - Один от собственника (о клиенте)
    """

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    # === Связи ===
    rental_id = Column(
        Integer,
        ForeignKey("rentals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Завершённая аренда, по которой оставлен отзыв",
    )
    
    reviewer_contractor_id = Column(
        Integer,
        ForeignKey("contractors.id"),
        nullable=False,
        index=True,
        comment="Кто оставил отзыв (Contractor)",
    )
    
    reviewed_company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
        comment="Кого оценили (Company)",
    )

    # === Тип отзыва ===
    review_type = Column(
        String(30),
        nullable=False,
        comment="client_to_owner | owner_to_client",
    )

    # === Оценка ===
    rating = Column(
        Integer,
        nullable=False,
        comment="Оценка от 1 до 5",
    )
    comment = Column(
        Text,
        nullable=True,
        comment="Текст отзыва",
    )
    pros = Column(
        Text,
        nullable=True,
        comment="Плюсы (опционально)",
    )
    cons = Column(
        Text,
        nullable=True,
        comment="Минусы (опционально)",
    )
    photos = Column(
        JSON,
        nullable=True,
        comment="Список URL фотографий (до 5 штук)",
    )

    # === Категории оценки (для детальной статистики) ===
    quality_rating = Column(
        Integer, nullable=True,
        comment="Качество техники (1-5)",
    )
    punctuality_rating = Column(
        Integer, nullable=True,
        comment="Пунктуальность (1-5)",
    )
    communication_rating = Column(
        Integer, nullable=True,
        comment="Коммуникация (1-5)",
    )

    # === Модерация ===
    status = Column(
        String(20),
        default=ReviewStatus.APPROVED,
        nullable=False,
        comment="pending | approved | rejected | hidden",
    )
    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Причина отклонения (если status=rejected)",
    )
    
    # Полезность отзыва
    helpful_count = Column(
        Integer, default=0, nullable=False,
        comment="Сколько раз отзыв был полезен",
    )
    
    # Публичность
    is_anonymous = Column(
        Boolean, default=False, nullable=False,
        comment="Анонимный отзыв (не показывать имя автора)",
    )
    
    # Кто отредактировал (для модерации)
    reviewed_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    # === Метаданные ===
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # === Связи ===
    rental = relationship("Rental", foreign_keys=[rental_id])
    reviewer = relationship("Contractor", foreign_keys=[reviewer_contractor_id])
    reviewed_company = relationship("Company", foreign_keys=[reviewed_company_id])

    def __repr__(self):
        return (
            f"<Review(id={self.id}, rental={self.rental_id}, "
            f"rating={self.rating}, type={self.review_type})>"
        )