"""Tests for ReviewsService."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestValidators:
    """Cover _validate_rating and _validate_optional_rating (lines 472-490)."""

    def test_valid_rating(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_rating(3)  # No raise

    def test_invalid_rating_type(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="integer"):
            ReviewsService._validate_rating("5")

    def test_rating_out_of_range(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService._validate_rating(6)

    def test_optional_none_ok(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_optional_rating(None, "quality")  # No raise

    def test_optional_valid(self):
        from app.services.reviews_service import ReviewsService

        ReviewsService._validate_optional_rating(4, "quality")  # No raise

    def test_optional_invalid(self):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService._validate_optional_rating(0, "quality")


class TestVerifyParticipant:
    """Cover _verify_participant (lines 491-514)."""

    def test_client_to_owner_valid(self, mock_db):
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(client_id=10, items=None)
        assert (
            ReviewsService._verify_participant(mock_db, rental, 10, "client_to_owner")
            is True
        )

    def test_client_to_owner_invalid(self, mock_db):
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(client_id=10, items=None)
        assert (
            ReviewsService._verify_participant(mock_db, rental, 99, "client_to_owner")
            is False
        )

    def test_owner_to_client_valid(self, mock_db):
        from app.services.reviews_service import ReviewsService

        item = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(owner_id=20)
        rental = SimpleNamespace(client_id=10, items=[item])
        mock_db.get.return_value = vehicle
        assert (
            ReviewsService._verify_participant(mock_db, rental, 20, "owner_to_client")
            is True
        )

    def test_owner_to_client_no_items(self, mock_db):
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(client_id=10, items=None)
        assert (
            ReviewsService._verify_participant(mock_db, rental, 20, "owner_to_client")
            is False
        )


class TestResolveReviewedCompany:
    """Cover _resolve_reviewed_company (lines 515-544)."""

    def test_client_to_owner_with_vehicle(self, mock_db):
        from app.services.reviews_service import ReviewsService

        item = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(owner_id=20)
        owner = SimpleNamespace(company_id=5)
        rental = SimpleNamespace(client_id=10, items=[item], company_id=1)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return vehicle
            return owner

        mock_db.get.side_effect = mock_get

        ReviewsService._resolve_reviewed_company(mock_db, rental, 10, "client_to_owner")
        assert result == 5

    def test_owner_to_client(self, mock_db):
        from app.services.reviews_service import ReviewsService

        client = SimpleNamespace(company_id=3)
        rental = SimpleNamespace(client_id=10, items=[], company_id=1)
        mock_db.get.return_value = client

        ReviewsService._resolve_reviewed_company(mock_db, rental, 20, "owner_to_client")
        assert result == 3


class TestGetCompanyRating:
    """Cover get_company_rating (lines 322-386)."""

    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.query.return_value.filter.return_value.all.return_value = []

        ReviewsService.get_company_rating(mock_db, 1)
        assert result["average_rating"] is None
        assert result["total_reviews"] == 0

    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService

        reviews = [
            SimpleNamespace(
                rating=5, quality_rating=5, punctuality_rating=4, communication_rating=5
            ),
            SimpleNamespace(
                rating=4,
                quality_rating=4,
                punctuality_rating=None,
                communication_rating=4,
            ),
            SimpleNamespace(
                rating=3,
                quality_rating=None,
                punctuality_rating=3,
                communication_rating=None,
            ),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = reviews

        ReviewsService.get_company_rating(mock_db, 1)
        assert result["average_rating"] == 4.0
        assert result["total_reviews"] == 3
        assert result["distribution"]["5"] == 1
        assert result["category_averages"]["quality"] == 4.5


class TestUpdateReview:
    """Cover update_review (lines 209-268)."""

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.update_review(mock_db, 999, 1)

    def test_wrong_author(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1)
        mock_db.get.return_value = review
        with pytest.raises(ValueError, match="your own"):
            ReviewsService.update_review(mock_db, 1, 999)

    def test_update_success(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(
            reviewer_contractor_id=1,
            rating=3,
            comment="old",
            reviewed_company_id=5,
            pros=None,
            cons=None,
            photos=None,
            quality_rating=None,
            punctuality_rating=None,
            communication_rating=None,
        )
        mock_db.get.return_value = review

        with patch.object(ReviewsService, "_recalculate_company_rating"):
            ReviewsService.update_review(
                mock_db, 1, 1, rating=5, comment="Отличный сервис!"
            )

        assert review.rating == 5
        assert review.comment == "Отличный сервис!"
        mock_db.commit.assert_called_once()


class TestDeleteReview:
    """Cover delete_review (lines 269-294)."""

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.delete_review(mock_db, 999, 1)

    def test_wrong_author(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1)
        mock_db.get.return_value = review
        with pytest.raises(ValueError, match="your own"):
            ReviewsService.delete_review(mock_db, 1, 999)

    def test_delete_success(self, mock_db):
        from app.services.reviews_service import ReviewsService

        review = SimpleNamespace(reviewer_contractor_id=1, reviewed_company_id=5)
        mock_db.get.return_value = review

        with patch.object(ReviewsService, "_recalculate_company_rating"):
            ReviewsService.delete_review(mock_db, 1, 1)

        assert result is True
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()


class TestCanLeaveReview:
    """Cover can_leave_review (lines 408-471)."""

    def test_rental_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        ReviewsService.can_leave_review(mock_db, 999, 1)
        assert result["can_review_owner"] is False

    def test_client_can_review_owner(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(status=RentalStatus.COMPLETED, client_id=10, items=[])
        mock_db.get.return_value = rental
        mock_db.query.return_value.filter.return_value.all.return_value = []

        ReviewsService.can_leave_review(mock_db, 1, 10)
        assert result["can_review_owner"] is True
        assert result["can_review_client"] is False

    def test_already_reviewed(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(status=RentalStatus.COMPLETED, client_id=10, items=[])
        existing_review = SimpleNamespace(review_type="client_to_owner")
        mock_db.get.return_value = rental
        mock_db.query.return_value.filter.return_value.all.return_value = [
            existing_review
        ]

        ReviewsService.can_leave_review(mock_db, 1, 10)
        assert result["can_review_owner"] is False
        assert result["has_reviewed_owner"] is True


class TestRecalculateCompanyRating:
    """Cover _recalculate_company_rating (lines 545-end)."""

    def test_no_company_id(self, mock_db):
        from app.services.reviews_service import ReviewsService

        ReviewsService._recalculate_company_rating(mock_db, None)  # No raise

    def test_recalculates(self, mock_db):
        from app.services.reviews_service import ReviewsService

        company = SimpleNamespace(
            id=1, average_rating=None, total_reviews=0, rating_distribution=None
        )
        reviews = [
            SimpleNamespace(rating=5),
            SimpleNamespace(rating=3),
        ]

        # db.get returns company
        mock_db.get.return_value = company

        # db.query returns reviews
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = reviews
        mock_db.query.return_value = mock_query

        ReviewsService._recalculate_company_rating(mock_db, 1)
        assert company.average_rating == Decimal("4.0")
        assert company.total_reviews == 2


class TestCreateReview:
    """Cover create_review (lines 37-208)."""

    def _make_base_mocks(self, mock_db):
        """Helper to setup common mocks for create_review."""
        from app.models.rental import RentalStatus

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.COMPLETED,
            client_id=10,
            items=[SimpleNamespace(vehicle_id=1)],
            company_id=1,
        )
        reviewer = SimpleNamespace(id=10, company_id=2)
        vehicle = SimpleNamespace(id=1, owner_id=20)
        owner_contractor = SimpleNamespace(id=20, company_id=5)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            # Return based on call order or model type
            if hasattr(model, "__tablename__"):
                tn = model.__tablename__
                if tn == "rentals":
                    return rental
                if tn == "contractors":
                    if pk == 10:
                        return reviewer
                    if pk == 20:
                        return owner_contractor
                if tn == "vehicles":
                    return vehicle
            # Fallback by call count
            if call_count["n"] <= 1:
                return rental
            if call_count["n"] == 2:
                return reviewer
            if call_count["n"] == 3:
                return vehicle
            return owner_contractor

        mock_db.get.side_effect = mock_get
        # No existing review
        mock_db.query.return_value.filter.return_value.first.return_value = None
        return rental, reviewer

    def test_invalid_rating_raises(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="between"):
            ReviewsService.create_review(mock_db, 1, 10, "client_to_owner", rating=6)

    def test_short_comment_raises(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="at least"):
            ReviewsService.create_review(
                mock_db, 1, 10, "client_to_owner", rating=5, comment="short"
            )

    def test_too_many_photos_raises(self, mock_db):
        from app.services.reviews_service import ReviewsService

        photos = [f"url{i}" for i in range(6)]
        with pytest.raises(ValueError, match="Maximum"):
            ReviewsService.create_review(
                mock_db, 1, 10, "client_to_owner", rating=5, photos=photos
            )

    def test_invalid_review_type_raises(self, mock_db):
        from app.services.reviews_service import ReviewsService

        with pytest.raises(ValueError, match="Invalid review_type"):
            ReviewsService.create_review(mock_db, 1, 10, "invalid_type", rating=5)

    def test_rental_not_found_raises(self, mock_db):
        from app.services.reviews_service import ReviewsService

        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.create_review(mock_db, 999, 10, "client_to_owner", rating=5)

    def test_rental_not_completed_raises(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(status=RentalStatus.ACTIVE)
        mock_db.get.return_value = rental
        with pytest.raises(ValueError, match="COMPLETED"):
            ReviewsService.create_review(mock_db, 1, 10, "client_to_owner", rating=5)

    def test_duplicate_review_raises(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(
            status=RentalStatus.COMPLETED, client_id=10, items=[], company_id=1
        )
        reviewer = SimpleNamespace(id=10)
        existing = SimpleNamespace(id=1)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return rental
            return reviewer

        mock_db.get.side_effect = mock_get
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        with pytest.raises(ValueError, match="already left"):
            ReviewsService.create_review(mock_db, 1, 10, "client_to_owner", rating=5)

    def test_success_client_to_owner(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.COMPLETED,
            client_id=10,
            items=[SimpleNamespace(vehicle_id=1)],
            company_id=1,
        )
        reviewer = SimpleNamespace(id=10, company_id=2)
        vehicle = SimpleNamespace(id=1, owner_id=20)
        owner_contractor = SimpleNamespace(id=20, company_id=5)

        # Map pk -> object for reliable lookup
        objects_by_pk = {1: rental, 10: reviewer, 20: owner_contractor}

        # Vehicle is always returned for vehicle_id lookups
        def mock_get(model, pk):
            if (
                pk == 1
                and hasattr(model, "__name__")
                and "Vehicle" in getattr(model, "__name__", "")
            ):
                return vehicle
            if (
                pk == 1
                and hasattr(model, "__name__")
                and "Rental" in getattr(model, "__name__", "")
            ):
                return rental
            # For _verify_participant and _resolve_reviewed_company vehicle lookups
            if pk == 1:
                return vehicle
            return objects_by_pk.get(pk, owner_contractor)

        mock_db.get.side_effect = mock_get
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(ReviewsService, "_recalculate_company_rating"):
            ReviewsService.create_review(
                mock_db,
                1,
                10,
                "client_to_owner",
                rating=5,
                comment="Отличный сервис, рекомендую!",
                pros="Быстро",
                cons="Дорого",
            )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_self_review_raises(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.reviews_service import ReviewsService

        # Owner tries to review themselves as client
        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.COMPLETED,
            client_id=20,
            items=[SimpleNamespace(vehicle_id=1)],
            company_id=1,
        )
        reviewer = SimpleNamespace(id=20, company_id=5)
        vehicle = SimpleNamespace(id=1, owner_id=20)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return rental
            if call_count["n"] == 2:
                return reviewer
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="yourself"):
            ReviewsService.create_review(mock_db, 1, 20, "owner_to_client", rating=5)
