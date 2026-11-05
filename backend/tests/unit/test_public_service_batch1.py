"""Coverage tests for PublicService - batch 1."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def svc():
    from app.services.public_service import PublicService

    return PublicService()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHelperMethods:
    """Cover _to_float, _normalize_photos (lines 54-77)."""

    def test_to_float_none(self, svc):
        assert svc._to_float(None) is None

    def test_to_float_decimal(self, svc):
        assert svc._to_float(Decimal("123.45")) == 123.45

    def test_to_float_int(self, svc):
        assert svc._to_float(42) == 42.0

    def test_to_float_invalid(self, svc):
        assert svc._to_float("abc") is None

    def test_normalize_photos_none(self, svc):
        assert svc._normalize_photos(None) is None

    def test_normalize_photos_list(self, svc):
        assert svc._normalize_photos(["a.jpg", None, "b.jpg"]) == ["a.jpg", "b.jpg"]

    def test_normalize_photos_str(self, svc):
        assert svc._normalize_photos("photo.jpg") == ["photo.jpg"]

    def test_normalize_photos_empty_str(self, svc):
        assert svc._normalize_photos("") is None

    def test_normalize_photos_dict(self, svc):
        result = svc._normalize_photos({"a": "x.jpg", "b": None})
        assert result == ["x.jpg"]


class TestHealthCheck:
    """Cover health_check (line 107)."""

    def test_returns_ok(self, svc, mock_db):
        result = svc.health_check(mock_db)
        assert result["status"] == "ok"


class TestListPublicCompanies:
    """Cover list_public_companies (lines 111-160)."""

    def test_empty(self, svc, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = svc.list_public_companies(mock_db, None, None, 10, 0)
        assert result == []

    def test_with_companies(self, svc, mock_db):
        company = SimpleNamespace(
            id=1,
            name="TestCo",
            legal_name="OOO Test",
            company_type="owner",
            description="Desc",
            logo_url=None,
            city="Moscow",
            phone="+7999",
            website=None,
            is_verified=True,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [company]
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = svc.list_public_companies(mock_db, None, None, 10, 0)
        assert len(result) == 1
        assert result[0].name == "TestCo"
        assert result[0].vehicles_count == 5


class TestGetPublicCompany:
    """Cover get_public_company (lines 161-196)."""

    def test_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.get_public_company(mock_db, 999)
        assert exc.value.status_code == 404

    def test_inactive(self, svc, mock_db):
        company = SimpleNamespace(is_active=False)
        mock_db.get.return_value = company
        with pytest.raises(HTTPException) as exc:
            svc.get_public_company(mock_db, 1)
        assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        company = SimpleNamespace(
            id=1,
            name="TestCo",
            legal_name="OOO",
            is_active=True,
            company_type=None,
            description=None,
            logo_url=None,
            city=None,
            phone=None,
            website=None,
            is_verified=False,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_db.get.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 3

        result = svc.get_public_company(mock_db, 1)
        assert result.name == "TestCo"
        assert result.vehicles_count == 3


class TestGetPublicCompanyVehicles:
    """Cover get_public_company_vehicles (lines 197-231)."""

    def test_company_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.get_public_company_vehicles(mock_db, None, False, 10, 999)
        assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        company = SimpleNamespace(id=1, name="TestCo", is_active=True)
        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            category=SimpleNamespace(name="Crane"),
            year=2020,
            status="available",
            hourly_rate=Decimal("1500"),
            shift_rate=Decimal("12000"),
            is_available_for_rent=True,
            photos=["a.jpg"],
            company_id=1,
            company=company,
            marketplace_commission_agreed=True,
            marketplace_commission_rate=Decimal("10"),
        )
        mock_db.get.return_value = company
        mock_db.scalars.return_value.all.return_value = [vehicle]

        result = svc.get_public_company_vehicles(mock_db, None, False, 10, 1)
        assert len(result) == 1
        assert result[0].name == "KAMAZ"


class TestListPublicVehicles:
    """Cover list_public_vehicles (lines 232-277)."""

    def test_empty(self, svc, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(mock_db, None, False, None, None, 10, 0)
        assert result == []

    def test_with_filters(self, svc, mock_db):
        vehicle = SimpleNamespace(
            id=1,
            name="Excavator",
            category=SimpleNamespace(name="Excavators"),
            year=2021,
            status="available",
            hourly_rate=Decimal("2000"),
            shift_rate=None,
            is_available_for_rent=True,
            photos=None,
            company_id=1,
            company=None,
            marketplace_commission_agreed=True,
            marketplace_commission_rate=Decimal("10"),
        )
        mock_db.scalars.return_value.all.return_value = [vehicle]

        result = svc.list_public_vehicles(
            mock_db, 2, True, 1000, 5000, 10, 0, company_id=1
        )
        assert len(result) == 1


class TestGetPublicVehicleDetails:
    """Cover get_public_vehicle_details (lines 278-300)."""

    def test_not_found(self, svc, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = None
            with pytest.raises(HTTPException) as exc:
                svc.get_public_vehicle_details(mock_db, 999)
            assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            category=SimpleNamespace(name="Truck"),
            year=2020,
            status="available",
            hourly_rate=Decimal("1500"),
            shift_rate=None,
            is_available_for_rent=True,
            photos=None,
            company_id=1,
            company=None,
            marketplace_commission_agreed=True,
            marketplace_commission_rate=None,
        )
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = vehicle
            result = svc.get_public_vehicle_details(mock_db, 1)
        assert result.name == "KAMAZ"


class TestGetVehicleAvailability:
    """Cover get_vehicle_availability (lines 301-341)."""

    def test_vehicle_not_found(self, svc, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = None
            with pytest.raises(HTTPException) as exc:
                svc.get_vehicle_availability(mock_db, 999, "2026-11-01", "2026-11-30")
            assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ")
        calendar = [{"date": "2026-11-01", "available": True}]
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = vehicle
            mock_ms.get_availability_calendar.return_value = calendar
            result = svc.get_vehicle_availability(
                mock_db, 1, "2026-11-01", "2026-11-30"
            )
        assert result.vehicle_id == 1
        assert len(result.calendar) == 1


class TestListPublicCategories:
    """Cover list_public_categories (lines 540-571)."""

    def test_success(self, svc, mock_db):
        cat = SimpleNamespace(
            id=1,
            name="Cranes",
            code="crane",
            level=1,
            parent_id=None,
            is_active=True,
            company_id=None,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        mock_db.scalars.return_value.all.return_value = [cat]
        mock_db.query.return_value.filter.return_value.count.return_value = 10

        result = svc.list_public_categories(mock_db)
        assert len(result) == 1
        assert result[0]["name"] == "Cranes"
        assert result[0]["vehicles_count"] == 10


class TestGetPublicCompanyRating:
    """Cover get_public_company_rating (lines 461-496)."""

    def test_company_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.get_public_company_rating(mock_db, 999)
        assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        company = SimpleNamespace(is_active=True)
        mock_db.get.return_value = company
        mock_db.query.return_value.filter.return_value.one.return_value = (
            SimpleNamespace(avg_rating=4.5, total=10)
        )
        result = svc.get_public_company_rating(mock_db, 1)
        assert result["average_rating"] == 4.5
        assert result["total_reviews"] == 10


class TestGetPublicCompanyReviews:
    """Cover get_public_company_reviews (lines 497-539)."""

    def test_company_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.get_public_company_reviews(mock_db, 10, 999)
        assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        company = SimpleNamespace(is_active=True)
        review = SimpleNamespace(
            id=1,
            rating=5,
            comment="Great!",
            reviewer=SimpleNamespace(name="Client"),
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        mock_db.get.return_value = company
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            review
        ]

        result = svc.get_public_company_reviews(mock_db, 10, 1)
        assert len(result) == 1
        assert result[0]["rating"] == 5
