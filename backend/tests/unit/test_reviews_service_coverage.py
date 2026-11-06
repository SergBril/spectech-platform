"""Coverage tests for reviews_service."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestConstants:
    """Cover module-level constants and ReviewTypeError."""

    def test_constants(self):
        from app.services.reviews_service import MIN_COMMENT_LENGTH, MAX_PHOTOS, RATING_MIN, RATING_MAX
        assert MIN_COMMENT_LENGTH == 10
        assert MAX_PHOTOS == 5
        assert RATING_MIN == 1
        assert RATING_MAX == 5

    def test_review_type_error(self):
        from app.services.reviews_service import ReviewTypeError
        assert ReviewTypeError.CLIENT_TO_OWNER == "client_to_owner"
        assert ReviewTypeError.OWNER_TO_CLIENT == "owner_to_client"


class TestValidateRating:
    """Cover _validate_rating and _validate_optional_rating."""

    def test_valid_rating(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_rating(3)  # Should not raise

    def test_invalid_rating_low(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_rating(0)

    def test_invalid_rating_high(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_rating(6)

    def test_optional_rating_none(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(None, "quality")  # OK

    def test_optional_rating_valid(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(4, "quality")  # OK

    def test_optional_rating_invalid(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_optional_rating(0, "quality")


class TestVerifyParticipant:
    """Cover _verify_participant."""

    def test_valid_participant(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(
            client_contractor_id=10, owner_contractor_id=20,
            status=SimpleNamespace(value="completed"),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = rental
        result = ReviewsService._verify_participant(mock_db, 100, 10, "client_to_owner")
        assert result == rental

    def test_rental_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService._verify_participant(mock_db, 100, 10, "client_to_owner")

    def test_not_participant(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_contractor_id=10, owner_contractor_id=20, status=SimpleNamespace(value="completed"))
        mock_db.query.return_value.filter.return_value.first.return_value = rental
        with pytest.raises(ValueError, match="participant"):
            ReviewsService._verify_participant(mock_db, 100, 99, "client_to_owner")


class TestResolveReviewedCompany:
    """Cover _resolve_reviewed_company."""

    def test_client_to_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(owner_contractor_id=20)
        contractor = SimpleNamespace(company_id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = contractor
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, "client_to_owner")
        assert result == 7

    def test_owner_to_client(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_contractor_id=10)
        contractor = SimpleNamespace(company_id=5)
        mock_db.query.return_value.filter.return_value.first.return_value = contractor
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, "owner_to_client")
        assert result == 5

    def test_contractor_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(owner_contractor_id=20)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, "client_to_owner")
        assert result is None


class TestRecalculateCompanyRating:
    """Cover _recalculate_company_rating."""

    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        review = SimpleNamespace(rating=4, quality_rating=5, punctuality_rating=3, communication_rating=4)
        mock_db.query.return_value.filter.return_value.all.return_value = [review]
        company = SimpleNamespace(id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = company
        ReviewsService._recalculate_company_rating(mock_db, 7)
        # Should have updated company rating fields

    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.all.return_value = []
        company = SimpleNamespace(id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = company
        ReviewsService._recalculate_company_rating(mock_db, 7)


class TestGetCompanyRating:
    """Cover get_company_rating."""

    def test_returns_dict(self, mock_db):
        from app.services.reviews_service import ReviewsService
        company = SimpleNamespace(
            id=7, avg_rating=Decimal("4.5"), total_reviews=10,
            avg_quality=Decimal("4.0"), avg_punctuality=Decimal("4.5"), avg_communication=Decimal("5.0"),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = company
        result = ReviewsService.get_company_rating(mock_db, 7)
        assert isinstance(result, dict)
        assert "avg_rating" in result

    def test_company_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = ReviewsService.get_company_rating(mock_db, 999)
        assert isinstance(result, dict)


class TestCanLeaveReview:
    """Cover can_leave_review."""

    def test_can_leave(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(
            client_contractor_id=10, owner_contractor_id=20,
            status=SimpleNamespace(value="completed"),
        )
        mock_db.query.return_value.filter.return_value.first.side_effect = [rental, None]
        result = ReviewsService.can_leave_review(mock_db, 100, 10, "client_to_owner")
        assert result["can_leave"] is True

    def test_already_reviewed(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(
            client_contractor_id=10, owner_contractor_id=20,
            status=SimpleNamespace(value="completed"),
        )
        existing_review = SimpleNamespace(id=1)
        mock_db.query.return_value.filter.return_value.first.side_effect = [rental, existing_review]
        result = ReviewsService.can_leave_review(mock_db, 100, 10, "client_to_owner")
        assert result["can_leave"] is False


class TestGetCompanyReviews:
    """Cover get_company_reviews."""

    def test_empty(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_q = MagicMock()
        mock_q.options.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_q.options.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value = mock_q
        result = ReviewsService.get_company_reviews(mock_db, 7)
        assert "reviews" in result
        assert "total" in result


class TestGetMyReviews:
    """Cover get_my_reviews."""

    def test_empty(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_q = MagicMock()
        mock_q.options.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_q.options.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value = mock_q
        result = ReviewsService.get_my_reviews(mock_db, 10)
        assert "reviews" in result


class TestCreateReview:
    """Cover create_review (lines 37-207)."""

    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(
            id=100, client_contractor_id=10, owner_contractor_id=20,
            status=SimpleNamespace(value="completed"), vehicle_id=1,
        )
        contractor = SimpleNamespace(company_id=7)
        
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                # _verify_participant: rental query
                mock_q.filter.return_value.first.return_value = rental
            elif call_count[0] == 2:
                # _resolve_reviewed_company: contractor query
                mock_q.filter.return_value.first.return_value = contractor
            elif call_count[0] == 3:
                # duplicate check
                mock_q.filter.return_value.first.return_value = None
            else:
                mock_q.filter.return_value.first.return_value = None
            return mock_q
        
        mock_db.query.side_effect = query_side_effect
        result = ReviewsService.create_review(
            mock_db, rental_id=100, reviewer_contractor_id=10,
            review_type="client_to_owner", rating=5, comment="Great service!",
        )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestUpdateReview:
    """Cover update_review."""

    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService
        review = SimpleNamespace(
            id=1, reviewer_contractor_id=10, rating=4, comment="old",
            pros=None, cons=None, photos=[], quality_rating=None,
            punctuality_rating=None, communication_rating=None,
        )
        mock_db.query.return_value.filter.return_value.first.return_value = review
        result = ReviewsService.update_review(mock_db, review_id=1, reviewer_contractor_id=10, rating=5, comment="updated")
        assert result.rating == 5
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            ReviewsService.update_review(mock_db, review_id=999, reviewer_contractor_id=10, rating=5)


class TestDeleteReview:
    """Cover delete_review."""

    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService
        review = SimpleNamespace(id=1, reviewer_contractor_id=10, reviewed_company_id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = review
        result = ReviewsService.delete_review(mock_db, review_id=1, reviewer_contractor_id=10)
        assert result is True
        mock_db.delete.assert_called()
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            ReviewsService.delete_review(mock_db, review_id=999, reviewer_contractor_id=10)
