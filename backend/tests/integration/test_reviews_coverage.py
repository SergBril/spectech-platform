"""Tests for reviews_service coverage improvement."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


class TestCreateReviewValidation:
    """Cover validation branches in create_review (lines 88-117)."""

    def test_comment_too_short_raises(self, db_session, sample_rental, company):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.COMPLETED
        db_session.commit()

        with pytest.raises(ValueError, match="at least"):
            ReviewsService.create_review(
                db=db_session,
                rental_id=sample_rental.id,
                reviewer_contractor_id=sample_rental.client_id,
                review_type="client_to_owner",
                rating=5,
                comment="ab",  # too short
            )

    def test_too_many_photos_raises(self, db_session, sample_rental, company):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.COMPLETED
        db_session.commit()

        photos = [f"https://example.com/photo{i}.jpg" for i in range(20)]
        with pytest.raises(ValueError, match="Maximum"):
            ReviewsService.create_review(
                db=db_session,
                rental_id=sample_rental.id,
                reviewer_contractor_id=sample_rental.client_id,
                review_type="client_to_owner",
                rating=5,
                photos=photos,
            )

    def test_invalid_review_type_raises(self, db_session, sample_rental, company):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.COMPLETED
        db_session.commit()

        with pytest.raises(ValueError, match="Invalid review_type"):
            ReviewsService.create_review(
                db=db_session,
                rental_id=sample_rental.id,
                reviewer_contractor_id=sample_rental.client_id,
                review_type="invalid_type",
                rating=5,
            )

    def test_non_completed_rental_raises(self, db_session, sample_rental, company):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.ACTIVE
        db_session.commit()

        with pytest.raises(ValueError, match="COMPLETED"):
            ReviewsService.create_review(
                db=db_session,
                rental_id=sample_rental.id,
                reviewer_contractor_id=sample_rental.client_id,
                review_type="client_to_owner",
                rating=5,
            )

    def test_nonexistent_rental_raises(self, db_session, company):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="not found"):
            ReviewsService.create_review(
                db=db_session,
                rental_id=99999,
                reviewer_contractor_id=1,
                review_type="client_to_owner",
                rating=5,
            )


class TestGetCompanyRating:
    """Cover get_company_rating (lines 310-361)."""

    def test_no_reviews_returns_empty(self, db_session, company):
        from app.services.reviews_service import ReviewsService

        result = ReviewsService.get_company_rating(db_session, company.id)
        assert result["average_rating"] is None
        assert result["total_reviews"] == 0
        assert result["distribution"]["5"] == 0

    def test_with_reviews_returns_stats(self, db_session, company, sample_rental, sample_rental_client):
        from app.services.reviews_service import ReviewsService
        from app.models.review import Review
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.COMPLETED
        db_session.commit()

        # Create approved reviews
        for rating in [5, 5, 4, 3]:
            review = Review(
                rental_id=sample_rental.id,
                reviewer_contractor_id=sample_rental_client.id,
                reviewed_company_id=company.id,
                review_type="client_to_owner",
                rating=rating,
                quality_rating=rating,
                punctuality_rating=rating,
                communication_rating=rating,
                status="approved",
            )
            db_session.add(review)
        db_session.commit()

        result = ReviewsService.get_company_rating(db_session, company.id)
        assert result["total_reviews"] == 4
        assert result["average_rating"] is not None
        assert result["distribution"]["5"] == 2
        assert result["distribution"]["4"] == 1
        assert result["category_averages"]["quality"] is not None


class TestVerifyParticipant:
    """Cover _verify_participant (lines 491-528)."""

    def test_client_to_owner_valid(self, db_session, sample_rental, sample_rental_client):
        from app.services.reviews_service import ReviewsService

        result = ReviewsService._verify_participant(
            db_session, sample_rental, sample_rental.client_id, "client_to_owner"
        )
        assert result is True

    def test_client_to_owner_invalid(self, db_session, sample_rental):
        from app.services.reviews_service import ReviewsService

        result = ReviewsService._verify_participant(
            db_session, sample_rental, 99999, "client_to_owner"
        )
        assert result is False

    def test_owner_to_client_no_items(self, db_session, sample_rental):
        from app.services.reviews_service import ReviewsService

        sample_rental.items = []
        result = ReviewsService._verify_participant(
            db_session, sample_rental, 1, "owner_to_client"
        )
        assert result is False

    def test_unknown_review_type(self, db_session, sample_rental):
        from app.services.reviews_service import ReviewsService

        result = ReviewsService._verify_participant(
            db_session, sample_rental, 1, "unknown_type"
        )
        assert result is False


class TestValidateOptionalRating:
    """Cover _validate_optional_rating (lines 470-477)."""

    def test_none_is_valid(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(None, "test_field")

    def test_valid_value(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(4, "test_field")

    def test_non_integer_raises(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError, match="must be an integer"):
            ReviewsService._validate_optional_rating("5", "test_field")

    def test_out_of_range_raises(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError, match="must be between"):
            ReviewsService._validate_optional_rating(10, "test_field")


class TestResolveReviewedCompany:
    """Cover _resolve_reviewed_company (lines 530-538)."""

    def test_unknown_type_returns_none(self, db_session, sample_rental):
        from app.services.reviews_service import ReviewsService

        result = ReviewsService._resolve_reviewed_company(
            db_session, sample_rental, 1, "unknown_type"
        )
        assert result is None
