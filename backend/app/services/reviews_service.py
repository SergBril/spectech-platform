"""Сервис отзывов и рейтингов компаний."""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.rental import Rental, RentalStatus
from app.models.review import Review

logger = logging.getLogger("spectech.reviews")

# Константы
MIN_COMMENT_LENGTH = 10
MAX_PHOTOS = 5
RATING_MIN = 1
RATING_MAX = 5


class ReviewTypeError:
    """Типы отзывов (дублируем строки для удобства)."""

    CLIENT_TO_OWNER = "client_to_owner"
    OWNER_TO_CLIENT = "owner_to_client"


class ReviewsService:
    """Сервис управления отзывами и рейтингами."""

    # === СОЗДАНИЕ ОТЗЫВА ===

    @staticmethod
    def create_review(
        db: Session,
        rental_id: int,
        reviewer_contractor_id: int,
        review_type: str,
        rating: int,
        comment: str | None = None,
        pros: str | None = None,
        cons: str | None = None,
        photos: list[str] | None = None,
        quality_rating: int | None = None,
        punctuality_rating: int | None = None,
        communication_rating: int | None = None,
        is_anonymous: bool = False,
    ) -> Review:
        """
        Создаёт отзыв на завершённую аренду.

        Args:
            db: Database session
            rental_id: ID завершённой аренды
            reviewer_contractor_id: ID того, кто оставляет отзыв (Contractor)
            review_type: "client_to_owner" или "owner_to_client"
            rating: Оценка от 1 до 5
            comment: Текст отзыва (опционально, минимум 10 символов)
            pros: Плюсы (опционально)
            cons: Минусы (опционально)
            photos: URL фотографий (до 5 штук)
            quality_rating: Качество техники (1-5)
            punctuality_rating: Пунктуальность (1-5)
            communication_rating: Коммуникация (1-5)
            is_anonymous: Анонимный отзыв

        Returns:
            Созданный Review

        Raises:
            ValueError: При нарушении бизнес-правил
        """
        # === Валидация входных данных ===
        ReviewsService._validate_rating(rating)
        ReviewsService._validate_optional_rating(quality_rating, "quality_rating")
        ReviewsService._validate_optional_rating(
            punctuality_rating, "punctuality_rating"
        )
        ReviewsService._validate_optional_rating(
            communication_rating, "communication_rating"
        )

        if comment is not None:
            if len(comment.strip()) < MIN_COMMENT_LENGTH:
                raise ValueError(
                    f"Comment must be at least {MIN_COMMENT_LENGTH} characters long"
                )

        if photos is not None:
            if len(photos) > MAX_PHOTOS:
                raise ValueError(f"Maximum {MAX_PHOTOS} photos allowed")
            photos = [url for url in photos if url and url.strip()]

        if review_type not in (
            ReviewTypeError.CLIENT_TO_OWNER,
            ReviewTypeError.OWNER_TO_CLIENT,
        ):
            raise ValueError(f"Invalid review_type: {review_type}")

        # === Проверка аренды ===
        rental = db.get(Rental, rental_id)
        if not rental:
            raise ValueError(f"Rental {rental_id} not found")

        if rental.status != RentalStatus.COMPLETED:
            raise ValueError(
                f"Cannot leave review for rental with status '{rental.status.value}'. "
                f"Only COMPLETED rentals can be reviewed."
            )

        # === Проверка, что reviewer — участник аренды ===
        reviewer = db.get(Contractor, reviewer_contractor_id)
        if not reviewer:
            raise ValueError(f"Reviewer contractor {reviewer_contractor_id} not found")

        is_participant = ReviewsService._verify_participant(
            db, rental, reviewer_contractor_id, review_type
        )
        if not is_participant:
            raise ValueError(
                f"Contractor {reviewer_contractor_id} is not a valid participant "
                f"for review_type '{review_type}' on rental {rental_id}"
            )

        # === Проверка дубликата (один отзыв от reviewer на rental + type) ===
        existing = (
            db.query(Review)
            .filter(
                Review.rental_id == rental_id,
                Review.reviewer_contractor_id == reviewer_contractor_id,
                Review.review_type == review_type,
            )
            .first()
        )

        if existing:
            raise ValueError(
                f"You have already left a {review_type} review for rental #{rental_id}"
            )

        # === Определяем reviewed_company_id ===
        reviewed_company_id = ReviewsService._resolve_reviewed_company(
            db, rental, reviewer_contractor_id, review_type
        )

        if not reviewed_company_id:
            raise ValueError(
                "Cannot determine reviewed company. "
                "Make sure rental has valid client and vehicle owner with company_id."
            )

        # === Создаём отзыв ===
        review = Review(
            rental_id=rental_id,
            reviewer_contractor_id=reviewer_contractor_id,
            reviewed_company_id=reviewed_company_id,
            review_type=review_type,
            rating=rating,
            comment=comment,
            pros=pros,
            cons=cons,
            photos=photos or None,
            quality_rating=quality_rating,
            punctuality_rating=punctuality_rating,
            communication_rating=communication_rating,
            is_anonymous=is_anonymous,
            status="approved",  # По умолчанию одобрен (модерация опциональна)
        )
        db.add(review)
        db.flush()

        # === Пересчитываем рейтинг компании ===
        ReviewsService._recalculate_company_rating(db, reviewed_company_id)

        db.commit()
        db.refresh(review)

        logger.info(
            "Review #%s created: rental=%s, type=%s, rating=%s, company=%s",
            review.id,
            rental_id,
            review_type,
            rating,
            reviewed_company_id,
        )

        return review

    # === ОБНОВЛЕНИЕ / УДАЛЕНИЕ ===

    @staticmethod
    def update_review(
        db: Session,
        review_id: int,
        reviewer_contractor_id: int,
        rating: int | None = None,
        comment: str | None = None,
        pros: str | None = None,
        cons: str | None = None,
        photos: list[str] | None = None,
        quality_rating: int | None = None,
        punctuality_rating: int | None = None,
        communication_rating: int | None = None,
    ) -> Review:
        """Обновляет существующий отзыв (только автор)."""
        review = db.get(Review, review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        if review.reviewer_contractor_id != reviewer_contractor_id:
            raise ValueError("You can only update your own reviews")

        if rating is not None:
            ReviewsService._validate_rating(rating)
            review.rating = rating

        if comment is not None:
            if len(comment.strip()) < MIN_COMMENT_LENGTH:
                raise ValueError(
                    f"Comment must be at least {MIN_COMMENT_LENGTH} characters"
                )
            review.comment = comment

        if pros is not None:
            review.pros = pros
        if cons is not None:
            review.cons = cons

        if photos is not None:
            if len(photos) > MAX_PHOTOS:
                raise ValueError(f"Maximum {MAX_PHOTOS} photos allowed")
            review.photos = photos if photos else None

        for field_name, value in [
            ("quality_rating", quality_rating),
            ("punctuality_rating", punctuality_rating),
            ("communication_rating", communication_rating),
        ]:
            if value is not None:
                ReviewsService._validate_optional_rating(value, field_name)
                setattr(review, field_name, value)

        # Пересчитываем рейтинг, если изменилась оценка
        if rating is not None:
            ReviewsService._recalculate_company_rating(db, review.reviewed_company_id)

        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def delete_review(
        db: Session,
        review_id: int,
        reviewer_contractor_id: int,
    ) -> bool:
        """Удаляет отзыв (только автор)."""
        review = db.get(Review, review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        if review.reviewer_contractor_id != reviewer_contractor_id:
            raise ValueError("You can only delete your own reviews")

        reviewed_company_id = review.reviewed_company_id
        db.delete(review)
        db.flush()

        # Пересчитываем рейтинг компании
        ReviewsService._recalculate_company_rating(db, reviewed_company_id)

        db.commit()
        return True

    # === ЗАПРОСЫ ===

    @staticmethod
    def get_company_reviews(
        db: Session,
        company_id: int,
        limit: int = 20,
        offset: int = 0,
        min_rating: int | None = None,
    ) -> list[Review]:
        """Список отзывов о компании (публично)."""
        stmt = (
            select(Review)
            .options(
                joinedload(Review.rental),
                joinedload(Review.reviewer),
            )
            .where(
                Review.reviewed_company_id == company_id,
                Review.status == "approved",
            )
            .order_by(Review.created_at.desc())
        )

        if min_rating is not None:
            stmt = stmt.where(Review.rating >= min_rating)

        return list(db.scalars(stmt.offset(offset).limit(limit)).all())

    @staticmethod
    def get_company_rating(db: Session, company_id: int) -> dict:
        """
        Статистика рейтинга компании.

        Returns:
            {
                "average_rating": 4.7,
                "total_reviews": 23,
                "distribution": {"5": 15, "4": 5, "3": 2, "2": 1, "1": 0},
                "category_averages": {
                    "quality": 4.5,
                    "punctuality": 4.8,
                    "communication": 4.6
                }
            }
        """
        reviews = (
            db.query(Review)
            .filter(
                Review.reviewed_company_id == company_id,
                Review.status == "approved",
            )
            .all()
        )

        if not reviews:
            return {
                "average_rating": None,
                "total_reviews": 0,
                "distribution": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
                "category_averages": {
                    "quality": None,
                    "punctuality": None,
                    "communication": None,
                },
            }

        total = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total

        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for r in reviews:
            distribution[str(r.rating)] += 1

        # Средние по категориям
        def avg_field(field_name):
            values = [
                getattr(r, field_name)
                for r in reviews
                if getattr(r, field_name) is not None
            ]
            return round(sum(values) / len(values), 2) if values else None

        return {
            "average_rating": round(avg_rating, 2),
            "total_reviews": total,
            "distribution": distribution,
            "category_averages": {
                "quality": avg_field("quality_rating"),
                "punctuality": avg_field("punctuality_rating"),
                "communication": avg_field("communication_rating"),
            },
        }

    @staticmethod
    def get_my_reviews(
        db: Session,
        reviewer_contractor_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Review]:
        """Мои оставленные отзывы."""
        stmt = (
            select(Review)
            .options(
                joinedload(Review.rental),
                joinedload(Review.reviewed_company),
            )
            .where(Review.reviewer_contractor_id == reviewer_contractor_id)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def can_leave_review(
        db: Session,
        rental_id: int,
        contractor_id: int,
    ) -> dict:
        """
        Проверяет, может ли contractor оставить отзыв на rental.

        Returns:
            {
                "can_review_owner": bool,
                "can_review_client": bool,
                "has_reviewed_owner": bool,
                "has_reviewed_client": bool,
            }
        """
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != RentalStatus.COMPLETED:
            return {
                "can_review_owner": False,
                "can_review_client": False,
                "has_reviewed_owner": False,
                "has_reviewed_client": False,
            }

        # Является ли contractor клиентом
        is_client = rental.client_id == contractor_id

        # Является ли contractor собственником техники
        is_owner = False
        if rental.items:
            for item in rental.items:
                vehicle = db.get(Vehicle, item.vehicle_id)
                if vehicle and vehicle.owner_id == contractor_id:
                    is_owner = True
                    break

        # Существующие отзывы этого contractor на этот rental
        existing = (
            db.query(Review)
            .filter(
                Review.rental_id == rental_id,
                Review.reviewer_contractor_id == contractor_id,
            )
            .all()
        )

        has_reviewed_owner = any(
            r.review_type == ReviewTypeError.CLIENT_TO_OWNER for r in existing
        )
        has_reviewed_client = any(
            r.review_type == ReviewTypeError.OWNER_TO_CLIENT for r in existing
        )

        return {
            "can_review_owner": is_client and not has_reviewed_owner,
            "can_review_client": is_owner and not has_reviewed_client,
            "has_reviewed_owner": has_reviewed_owner,
            "has_reviewed_client": has_reviewed_client,
        }

    # === ВНУТРЕННИЕ МЕТОДЫ ===

    @staticmethod
    def _validate_rating(rating: int) -> None:
        """Валидация обязательной оценки."""
        if not isinstance(rating, int):
            raise ValueError("Rating must be an integer")
        if rating < RATING_MIN or rating > RATING_MAX:
            raise ValueError(f"Rating must be between {RATING_MIN} and {RATING_MAX}")

    @staticmethod
    def _validate_optional_rating(value: int | None, field_name: str) -> None:
        """Валидация опциональной оценки."""
        if value is not None:
            if not isinstance(value, int):
                raise ValueError(f"{field_name} must be an integer")
            if value < RATING_MIN or value > RATING_MAX:
                raise ValueError(
                    f"{field_name} must be between {RATING_MIN} and {RATING_MAX}"
                )

    @staticmethod
    def _verify_participant(
        db: Session,
        rental: Rental,
        contractor_id: int,
        review_type: str,
    ) -> bool:
        """Проверяет, что contractor — участник аренды для данного типа отзыва."""
        if review_type == ReviewTypeError.CLIENT_TO_OWNER:
            # Reviewer должен быть клиентом
            return rental.client_id == contractor_id

        elif review_type == ReviewTypeError.OWNER_TO_CLIENT:
            # Reviewer должен быть собственником хотя бы одной техники в аренде
            if not rental.items:
                return False
            for item in rental.items:
                vehicle = db.get(Vehicle, item.vehicle_id)
                if vehicle and vehicle.owner_id == contractor_id:
                    return True
            return False

        return False

    @staticmethod
    def _resolve_reviewed_company(
        db: Session,
        rental: Rental,
        reviewer_contractor_id: int,
        review_type: str,
    ) -> int | None:
        """Определяет company_id того, кого оценивают."""
        if review_type == ReviewTypeError.CLIENT_TO_OWNER:
            # Клиент оценивает собственника → нужна компания первого собственника техники
            if not rental.items:
                return None
            for item in rental.items:
                vehicle = db.get(Vehicle, item.vehicle_id)
                if vehicle and vehicle.owner_id:
                    owner_contractor = db.get(Contractor, vehicle.owner_id)
                    if owner_contractor and owner_contractor.company_id:
                        return owner_contractor.company_id
            # Fallback: company_id из rental
            return rental.company_id

        elif review_type == ReviewTypeError.OWNER_TO_CLIENT:
            # Собственник оценивает клиента → компания клиента
            client = db.get(Contractor, rental.client_id)
            if client and client.company_id:
                return client.company_id
            return rental.company_id

        return None

    @staticmethod
    def _recalculate_company_rating(db: Session, company_id: int) -> None:
        """Пересчитывает агрегированный рейтинг компании."""
        if not company_id:
            return

        company = db.get(Company, company_id)
        if not company:
            return

        # Все одобренные отзывы
        reviews = (
            db.query(Review)
            .filter(
                Review.reviewed_company_id == company_id,
                Review.status == "approved",
            )
            .all()
        )

        if not reviews:
            company.average_rating = None
            company.total_reviews = 0
            company.rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
            return

        total = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total

        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for r in reviews:
            distribution[str(r.rating)] += 1

        company.average_rating = Decimal(str(round(avg_rating, 2)))
        company.total_reviews = total
        company.rating_distribution = distribution

        logger.info(
            "Company #%s rating recalculated: avg=%.2f, total=%d",
            company_id,
            avg_rating,
            total,
        )


# Singleton
reviews_service = ReviewsService()
