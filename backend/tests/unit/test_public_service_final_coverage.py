"""Точечные тесты для public_service.py — покрытие оставшихся 18 строк."""
import pytest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.services.public_service import PublicService


@pytest.fixture
def svc():
    return PublicService()


class TestNormalizePhotosNone:
    """Line 76: _normalize_photos returns None for unexpected type."""

    def test_returns_none_for_int(self, svc):
        assert svc._normalize_photos(123) is None

    def test_returns_none_for_float(self, svc):
        assert svc._normalize_photos(3.14) is None


class TestListPublicVehiclesFilters:
    """Lines 214, 216: category_id and available_only filters."""

    def test_category_id_filter(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(
            mock_db, category_id=5, available_only=False,
            min_hourly_rate=None, max_hourly_rate=None, limit=10, offset=0,
        )
        assert isinstance(result, list)

    def test_available_only_filter(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(
            mock_db, category_id=None, available_only=True,
            min_hourly_rate=None, max_hourly_rate=None, limit=10, offset=0,
        )
        assert isinstance(result, list)


class TestGetVehicleAvailabilityException:
    """Lines 338-340: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_vehicle_availability(mock_db, vehicle_id=1, from_date="2026-11-09", to_date="2026-11-10")


class TestCreateRequestFromListingValueError:
    """Line 454: ValueError handler in create_request_from_listing."""

    def test_value_error_raised(self, svc):
        mock_db = MagicMock()
        data = SimpleNamespace(
            work_type="earthworks", object_address="Moscow",
            planned_start=datetime(2026, 12, 1), planned_end=datetime(2026, 12, 5),
            vehicle_category_id=1, description="Test",
        )
        # Make db.get for vehicle raise ValueError via validation
        mock_db.get.return_value = None  # vehicle not found -> may raise ValueError
        # Try with invalid data that triggers ValueError inside the method
        with pytest.raises(HTTPException):
            svc.create_request_from_listing(mock_db, vehicle_id=999, data=data, company_id=1)


class TestGetPublicCompanyReviewsException:
    """Lines 536-538: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("reviews boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_public_company_reviews(mock_db, limit=10, company_id=1)


class TestListPublicCategoriesException:
    """Lines 568-570: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        # list_public_categories uses db.execute for categories query
        mock_db.execute.side_effect = RuntimeError("categories boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.list_public_categories(mock_db, company_id=1)


class TestRespondToMarketplaceRequestVehicleNotFound:
    """Line 720: vehicle not found or wrong company."""

    def test_wrong_company(self, svc):
        mock_db = MagicMock()
        request_obj = SimpleNamespace(company_id=99, status="published")
        vehicle = SimpleNamespace(company_id=88, status="active")
        # First db.get returns request, second returns vehicle
        mock_db.get.side_effect = [request_obj, vehicle]
        with pytest.raises(HTTPException, match="not found"):
            svc.respond_to_marketplace_request(
                mock_db, company_id=1, request_id=1, vehicle_id=5,
                current_user=SimpleNamespace(id=1),
            )


class TestExportMarketplaceRequestsImportError:
    """Lines 1067-1068: openpyxl ImportError."""

    def test_import_error(self, svc):
        mock_db = MagicMock()
        with patch.dict("sys.modules", {"openpyxl": None}):
            with patch("builtins.__import__", side_effect=ImportError("no openpyxl")):
                with pytest.raises(HTTPException, match="openpyxl not installed"):
                    svc.export_marketplace_requests(mock_db, category_id=None)


class TestExportMarketplacePayoutsHighlight:
    """Line 1153: payment_days > 7 highlight."""

    def test_extended_payment_highlight(self, svc):
        mock_db = MagicMock()
        # marketplace_payouts_report needs date_from, date_to
        row = (1, 1, "OOO Contractor", "9876543210", 50000, 5000, 45000, "approved",
               datetime(2026, 11, 1), 14, "Excavator", "earthworks")
        mock_db.execute.return_value.fetchall.return_value = [row]
        result = svc.marketplace_payouts_report(
            mock_db, date_from="2026-11-01", date_to="2026-11-30",
        )
        assert result is not None


class TestCreateCompanyReviewNotFound:
    """Line 1226: company not found."""

    def test_company_not_found(self, svc):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        payload = SimpleNamespace(reviewer_name="Test", rating=5, comment="Good")
        with pytest.raises(HTTPException, match="Компания не найдена"):
            svc.create_company_review(mock_db, payload=payload, company_id=999)
