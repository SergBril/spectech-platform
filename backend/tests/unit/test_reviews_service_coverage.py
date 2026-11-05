"""Coverage tests for reviews_service."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    return db


class TestValidateRating:
    """Cover _validate_rating (lines 472-478)."""

    def test_valid(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_rating(3)  # no exception

    def test_too_low(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService._validate_rating(0)

    def test_too_high(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService._validate_rating(6)

    def test_not_int(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="integer"):
            ReviewsService._validate_rating("3")


class TestValidateOptionalRating:
    """Cover _validate_optional_rating (lines 480-489)."""

    def test_none_ok(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_optional_rating(None, "quality")

    def test_valid(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_optional_rating(5, "quality")

    def test_invalid(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError):
            ReviewsService._validate_optional_rating(0, "quality")


class TestVerifyParticipant:
    """Cover _verify_participant (lines 491-513)."""

    def test_client_to_owner_is_client(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        rental = SimpleNamespace(client_id=1, items=[])
        assert (
            ReviewsService._verify_participant(
                mock_db, rental, 1, ReviewTypeError.CLIENT_TO_OWNER
            )
            is True
        )

    def test_client_to_owner_not_client(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        rental = SimpleNamespace(client_id=1, items=[])
        assert (
            ReviewsService._verify_participant(
                mock_db, rental, 2, ReviewTypeError.CLIENT_TO_OWNER
            )
            is False
        )

    def test_owner_to_client_is_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        item = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(owner_id=2)
        rental = SimpleNamespace(client_id=1, items=[item])
        mock_db.get.return_value = vehicle
        assert (
            ReviewsService._verify_participant(
                mock_db, rental, 2, ReviewTypeError.OWNER_TO_CLIENT
            )
            is True
        )

    def test_owner_to_client_no_items(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        rental = SimpleNamespace(client_id=1, items=[])
        assert (
            ReviewsService._verify_participant(
                mock_db, rental, 2, ReviewTypeError.OWNER_TO_CLIENT
            )
            is False
        )


class TestResolveReviewedCompany:
    """Cover _resolve_reviewed_company (lines 515-543)."""

    def test_client_to_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        item = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(owner_id=2)
        owner = SimpleNamespace(company_id=5)
        rental = SimpleNamespace(client_id=1, items=[item], company_id=3)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return vehicle if call_count["n"] == 1 else owner

        mock_db.get.side_effect = mock_get

        result = ReviewsService._resolve_reviewed_company(
            mock_db, rental, 1, ReviewTypeError.CLIENT_TO_OWNER
        )
        assert result == 5

    def test_owner_to_client(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        client = SimpleNamespace(company_id=7)
        rental = SimpleNamespace(client_id=1, items=[], company_id=3)
        mock_db.get.return_value = client

        result = ReviewsService._resolve_reviewed_company(
            mock_db, rental, 2, ReviewTypeError.OWNER_TO_CLIENT
        )
        assert result == 7

    def test_no_items_returns_none(self, mock_db):
        from app.services.reviews_service import ReviewsService, ReviewTypeError

        rental = SimpleNamespace(client_id=1, items=[], company_id=3)
        result = ReviewsService._resolve_reviewed_company(
            mock_db, rental, 1, ReviewTypeError.CLIENT_TO_OWNER
        )
        assert result is None


class TestRecalculateCompanyRating:
    """Cover _recalculate_company_rating (lines 545-end)."""

    def test_no_company(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        ReviewsService._recalculate_company_rating(mock_db, 999)  # no exception

    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        company = SimpleNamespace(
            average_rating=None, total_reviews=0, rating_distribution=None
        )
        mock_db.get.return_value = company
        mock_db.query.return_value.filter.return_value.all.return_value = []

        ReviewsService._recalculate_company_rating(mock_db, 1)
        assert company.average_rating is None
        assert company.total_reviews == 0

    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        company = SimpleNamespace(
            average_rating=None, total_reviews=0, rating_distribution=None
        )
        r1 = SimpleNamespace(rating=5)
        r2 = SimpleNamespace(rating=3)
        mock_db.get.return_value = company
        mock_db.query.return_value.filter.return_value.all.return_value = [r1, r2]

        ReviewsService._recalculate_company_rating(mock_db, 1)
        assert company.average_rating == Decimal("4.00")
        assert company.total_reviews == 2
        assert company.rating_distribution["5"] == 1
        assert company.rating_distribution["3"] == 1


class TestGetCompanyRating:
    """Cover get_company_rating (lines 322-385)."""

    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = ReviewsService.get_company_rating(mock_db, 1)
        assert result["average_rating"] is None
        assert result["total_reviews"] == 0

    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        r1 = SimpleNamespace(
            rating=5, quality_rating=4, punctuality_rating=5, communication_rating=4
        )
        r2 = SimpleNamespace(
            rating=3, quality_rating=3, punctuality_rating=None, communication_rating=3
        )
        mock_db.query.return_value.filter.return_value.all.return_value = [r1, r2]

        result = ReviewsService.get_company_rating(mock_db, 1)
        assert result["average_rating"] == 4.0
        assert result["total_reviews"] == 2
        assert result["distribution"]["5"] == 1
        assert result["category_averages"]["quality"] == 3.5
        assert result["category_averages"]["punctuality"] == 5.0


class TestCanLeaveReview:
    """Cover can_leave_review (lines 408-470)."""

    def test_rental_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        result = ReviewsService.can_leave_review(mock_db, 999, 1)
        assert result["can_review_owner"] is False

    def test_client_can_review_owner(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(status=RentalStatus.COMPLETED, client_id=1, items=[])
        mock_db.get.return_value = rental
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = ReviewsService.can_leave_review(mock_db, 1, 1)
        assert result["can_review_owner"] is True
        assert result["can_review_client"] is False


class TestDeleteReview:
    """Cover delete_review (lines 269-293)."""

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.delete_review(mock_db, 999, 1)

    def test_not_author(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1, reviewed_company_id=5)
        mock_db.get.return_value = review
        with pytest.raises(ValueError, match="own reviews"):
            ReviewsService.delete_review(mock_db, 1, 2)

    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1, reviewed_company_id=5)
        mock_db.get.return_value = review
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                ReviewsService,
                "_recalculate_company_rating",
                staticmethod(lambda db, cid: None),
            )
            result = ReviewsService.delete_review(mock_db, 1, 1)
        assert result is True
        mock_db.delete.assert_called_once()


class TestUpdateReview:
    """Cover update_review (lines 209-267)."""

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.update_review(mock_db, 999, 1)

    def test_not_author(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1, reviewed_company_id=5)
        mock_db.get.return_value = review
        with pytest.raises(ValueError, match="own reviews"):
            ReviewsService.update_review(mock_db, 1, 2)

    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(
            reviewer_contractor_id=1,
            reviewed_company_id=5,
            rating=3,
            comment=None,
            pros=None,
            cons=None,
            photos=None,
            quality_rating=None,
            punctuality_rating=None,
            communication_rating=None,
        )
        mock_db.get.return_value = review
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                ReviewsService,
                "_recalculate_company_rating",
                staticmethod(lambda db, cid: None),
            )
            result = ReviewsService.update_review(
                mock_db, 1, 1, rating=5, comment="Great service!"
            )
        assert result.rating == 5
        assert result.comment == "Great service!"


class TestCreateReview:
    """Cover create_review (lines 37-207)."""

    def test_invalid_rating(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService.create_review(mock_db, 1, 1, "client_to_owner", 0)

    def test_comment_too_short(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="at least"):
            ReviewsService.create_review(
                mock_db, 1, 1, "client_to_owner", 5, comment="short"
            )

    def test_too_many_photos(self, mock_db):
        from app.services.reviews_service import ReviewsService

        photos = [f"http://img{i}.jpg" for i in range(6)]
        with pytest.raises(ValueError, match="Maximum"):
            ReviewsService.create_review(
                mock_db, 1, 1, "client_to_owner", 5, photos=photos
            )

    def test_invalid_review_type(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="Invalid review_type"):
            ReviewsService.create_review(mock_db, 1, 1, "invalid_type", 5)

    def test_rental_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.create_review(mock_db, 999, 1, "client_to_owner", 5)

    def test_self_review_prevention(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        item = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(owner_id=1)  # same as reviewer
        # reviewer must be client for client_to_owner
        rental = SimpleNamespace(
            status=RentalStatus.COMPLETED, client_id=1, items=[item]
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return rental
            if call_count["n"] == 2:
                return SimpleNamespace(id=1)  # reviewer contractor
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="yourself"):
            ReviewsService.create_review(mock_db, 1, 1, "client_to_owner", 5)
