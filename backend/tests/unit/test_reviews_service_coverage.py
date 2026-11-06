"""Coverage tests for reviews_service."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


class TestConstants:
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
    def test_valid(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_rating(3)

    def test_low(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_rating(0)

    def test_high(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_rating(6)

    def test_optional_none(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(None, "q")

    def test_optional_valid(self):
        from app.services.reviews_service import ReviewsService
        ReviewsService._validate_optional_rating(4, "q")

    def test_optional_invalid(self):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError):
            ReviewsService._validate_optional_rating(0, "q")


class TestVerifyParticipant:
    """_verify_participant(db, rental, contractor_id, review_type) -> bool"""

    def test_client_to_owner_true(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, items=[])
        assert ReviewsService._verify_participant(mock_db, rental, 10, "client_to_owner") is True

    def test_client_to_owner_false(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, items=[])
        assert ReviewsService._verify_participant(mock_db, rental, 99, "client_to_owner") is False

    def test_owner_to_client_true(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental_item = SimpleNamespace(vehicle_id=1)
        rental = SimpleNamespace(client_id=10, items=[rental_item])
        vehicle = SimpleNamespace(owner_id=20)
        mock_db.get.return_value = vehicle
        assert ReviewsService._verify_participant(mock_db, rental, 20, "owner_to_client") is True

    def test_owner_to_client_no_items(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, items=[])
        assert ReviewsService._verify_participant(mock_db, rental, 20, "owner_to_client") is False

    def test_unknown_type(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, items=[])
        assert ReviewsService._verify_participant(mock_db, rental, 10, "unknown") is False


class TestResolveReviewedCompany:
    """_resolve_reviewed_company(db, rental, reviewer_contractor_id, review_type) -> int|None"""

    def test_client_to_owner_with_vehicle(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental_item = SimpleNamespace(vehicle_id=1)
        rental = SimpleNamespace(client_id=10, company_id=99, items=[rental_item])
        vehicle = SimpleNamespace(owner_id=20)
        owner_contractor = SimpleNamespace(company_id=7)
        # db.get called twice: Vehicle then Contractor
        mock_db.get.side_effect = [vehicle, owner_contractor]
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, 10, "client_to_owner")
        assert result == 7

    def test_client_to_owner_fallback_no_valid_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental_item = SimpleNamespace(vehicle_id=1)
        rental = SimpleNamespace(client_id=10, company_id=99, items=[rental_item])
        # Vehicle has no owner_id -> falls through to rental.company_id
        vehicle = SimpleNamespace(owner_id=None)
        mock_db.get.return_value = vehicle
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, 10, "client_to_owner")
        assert result == 99

    def test_owner_to_client(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, company_id=99, items=[])
        client = SimpleNamespace(company_id=5)
        mock_db.get.return_value = client
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, 20, "owner_to_client")
        assert result == 5

    def test_owner_to_client_fallback(self, mock_db):
        from app.services.reviews_service import ReviewsService
        rental = SimpleNamespace(client_id=10, company_id=99, items=[])
        mock_db.get.return_value = None
        result = ReviewsService._resolve_reviewed_company(mock_db, rental, 20, "owner_to_client")
        assert result == 99


class TestGetCompanyRating:
    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = ReviewsService.get_company_rating(mock_db, 7)
        assert result["total_reviews"] == 0
        assert result["average_rating"] is None

    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        reviews = [
            SimpleNamespace(rating=5, quality_rating=4, punctuality_rating=5, communication_rating=4),
            SimpleNamespace(rating=4, quality_rating=3, punctuality_rating=4, communication_rating=None),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = reviews
        result = ReviewsService.get_company_rating(mock_db, 7)
        assert result["average_rating"] == 4.5
        assert result["total_reviews"] == 2
        assert result["distribution"]["5"] == 1
        assert result["distribution"]["4"] == 1


class TestRecalculateCompanyRating:
    def test_with_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        reviews = [SimpleNamespace(rating=5, quality_rating=4, punctuality_rating=5, communication_rating=4),
                   SimpleNamespace(rating=3, quality_rating=3, punctuality_rating=3, communication_rating=3)]
        company = SimpleNamespace(id=7)
        mock_db.get.return_value = company
        mock_db.query.return_value.filter.return_value.all.return_value = reviews
        ReviewsService._recalculate_company_rating(mock_db, 7)
        # Method sets company attributes; caller is responsible for commit
        assert company.average_rating is not None
        assert company.total_reviews == 2

    def test_no_company(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.get.return_value = None
        ReviewsService._recalculate_company_rating(mock_db, 7)
        mock_db.commit.assert_not_called()

    def test_no_company_id(self, mock_db):
        from app.services.reviews_service import ReviewsService
        ReviewsService._recalculate_company_rating(mock_db, None)
        mock_db.get.assert_not_called()

    def test_no_reviews(self, mock_db):
        from app.services.reviews_service import ReviewsService
        company = SimpleNamespace(id=7)
        call_count = [0]
        def query_side_effect(*args):
            call_count[0] += 1
            q = MagicMock()
            if call_count[0] == 1:
                q.filter.return_value.all.return_value = []
            else:
                q.filter.return_value.first.return_value = company
            return q
        mock_db.query.side_effect = query_side_effect
        ReviewsService._recalculate_company_rating(mock_db, 7)


class TestCanLeaveReview:
    def test_client_can_review_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus
        rental = SimpleNamespace(client_id=10, items=[], status=RentalStatus.COMPLETED)
        mock_db.get.return_value = rental
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = ReviewsService.can_leave_review(mock_db, 100, 10)
        assert result["can_review_owner"] is True
        assert result["has_reviewed_owner"] is False

    def test_already_reviewed_owner(self, mock_db):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus
        rental = SimpleNamespace(client_id=10, items=[], status=RentalStatus.COMPLETED)
        existing = SimpleNamespace(review_type="client_to_owner")
        mock_db.get.return_value = rental
        mock_db.query.return_value.filter.return_value.all.return_value = [existing]
        result = ReviewsService.can_leave_review(mock_db, 100, 10)
        assert result["can_review_owner"] is False
        assert result["has_reviewed_owner"] is True

    def test_rental_not_completed(self, mock_db):
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus
        rental = SimpleNamespace(client_id=10, items=[], status=RentalStatus.ACTIVE)
        mock_db.get.return_value = rental
        result = ReviewsService.can_leave_review(mock_db, 100, 10)
        assert result["can_review_owner"] is False


class TestCreateReview:
    """Cover create_review (lines 37-207)."""

    def test_success_owner_to_client(self, mock_db):
        """Test create_review with owner_to_client type."""
        from app.services.reviews_service import ReviewsService
        from app.models.rental import RentalStatus
        from unittest.mock import MagicMock as MM

        # Use plain object for rental item to ensure int vehicle_id
        item = type("Item", (), {"vehicle_id": 1})()
        m_rental = MM()
        m_rental.id = 100
        m_rental.client_id = 10
        m_rental.company_id = 7
        m_rental.status = RentalStatus.COMPLETED
        m_rental.items = [item]

        m_reviewer = MM()
        m_reviewer.id = 20
        m_reviewer.company_id = 5

        m_vehicle = MM()
        m_vehicle.id = 1
        m_vehicle.owner_id = 20

        m_client = MM()
        m_client.id = 10
        m_client.company_id = 8

        # Sequential db.get: Rental(100), Contractor(20), Vehicle(1), Contractor(10), Company(8)
        m_company = MM()
        m_company.id = 8
        m_company.average_rating = None
        m_company.total_reviews = 0
        m_company.rating_distribution = {}
        mock_db.get.side_effect = [m_rental, m_reviewer, m_vehicle, m_client, m_company]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = ReviewsService.create_review(
            mock_db, rental_id=100, reviewer_contractor_id=20,
            review_type="owner_to_client", rating=5, comment="Great client!!!",
        )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_rental_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ReviewsService.create_review(mock_db, rental_id=999, reviewer_contractor_id=10,
                                         review_type="client_to_owner", rating=5)

    def test_comment_too_short(self, mock_db):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError, match="at least"):
            ReviewsService.create_review(mock_db, rental_id=100, reviewer_contractor_id=10,
                                         review_type="client_to_owner", rating=5, comment="short")

    def test_too_many_photos(self, mock_db):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError, match="Maximum"):
            ReviewsService.create_review(mock_db, rental_id=100, reviewer_contractor_id=10,
                                         review_type="client_to_owner", rating=5,
                                         photos=["url"] * 6)

    def test_invalid_review_type(self, mock_db):
        from app.services.reviews_service import ReviewsService
        with pytest.raises(ValueError, match="Invalid review_type"):
            ReviewsService.create_review(mock_db, rental_id=100, reviewer_contractor_id=10,
                                         review_type="invalid", rating=5)



class TestUpdateReview:
    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService
        review = SimpleNamespace(
            id=1, reviewer_contractor_id=10, rating=4, comment="old",
            pros=None, cons=None, photos=[], quality_rating=None,
            punctuality_rating=None, communication_rating=None,
            reviewed_company_id=7,
        )
        # db.get(Review) -> review; then _recalculate uses db.query
        mock_db.get.return_value = review
        mock_db.query.return_value.filter.return_value.all.return_value = [review]
        mock_db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=7)
        result = ReviewsService.update_review(mock_db, review_id=1, reviewer_contractor_id=10,
                                              rating=5, comment="updated comment!")
        assert result.rating == 5
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.get.return_value = None
        with pytest.raises(ValueError):
            ReviewsService.update_review(mock_db, review_id=999, reviewer_contractor_id=10, rating=5)


class TestDeleteReview:
    def test_success(self, mock_db):
        from app.services.reviews_service import ReviewsService
        review = SimpleNamespace(id=1, reviewer_contractor_id=10, reviewed_company_id=7)
        mock_db.get.return_value = review
        # _recalculate uses db.query
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=7)
        result = ReviewsService.delete_review(mock_db, review_id=1, reviewer_contractor_id=10)
        assert result is True
        mock_db.delete.assert_called()
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_db.get.return_value = None
        with pytest.raises(ValueError):
            ReviewsService.delete_review(mock_db, review_id=999, reviewer_contractor_id=10)


class TestGetCompanyReviews:
    def test_empty(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = ReviewsService.get_company_reviews(mock_db, 7)
        assert result == []


class TestGetMyReviews:
    def test_empty(self, mock_db):
        from app.services.reviews_service import ReviewsService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = ReviewsService.get_my_reviews(mock_db, 10)
        assert result == []
