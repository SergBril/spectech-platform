"""Точечные тесты для public_service.py — покрытие оставшихся строк."""
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


class TestListPublicVehiclesFilters:
    """Lines 214, 216: category_id and available_only filters."""

    def test_with_category_and_available(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(
            mock_db, category_id=5, available_only=True,
            min_hourly_rate=None, max_hourly_rate=None, limit=10, offset=0,
        )
        assert isinstance(result, list)


class TestGetVehicleAvailabilityException:
    """Lines 338-340: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        # marketplace_service is imported inside the method
        with patch("app.services.marketplace_service.marketplace_service") as mock_mkt:
            mock_mkt.get_vehicle_details.return_value = SimpleNamespace(id=1, name="Test")
            mock_mkt.get_availability_calendar.side_effect = RuntimeError("boom")
            with pytest.raises(HTTPException, match="Internal error"):
                svc.get_vehicle_availability(mock_db, vehicle_id=1, from_date="2026-11-09", to_date="2026-11-10")


class TestCreateRequestFromListingValueError:
    """Line 454: ValueError handler."""

    def test_value_error(self, svc):
        mock_db = MagicMock()
        vehicle = SimpleNamespace(id=1, company_id=1, status="active", category_id=1)
        mock_db.get.return_value = vehicle
        data = SimpleNamespace(
            work_type="earthworks", object_address="Moscow",
            planned_start=datetime(2026, 12, 1), planned_end=datetime(2026, 12, 5),
            vehicle_category_id=1, description="Test",
        )
        # create_request_from_listing calls RequestService internally
        # Patch at the point of use inside the method
        with patch("app.services.public_service.RequestService") as MockRS:
            MockRS.return_value.create_request.side_effect = ValueError("bad input")
            with pytest.raises(HTTPException, match="bad input"):
                svc.create_request_from_listing(mock_db, vehicle_id=1, data=data, company_id=1)


class TestGetPublicCompanyReviewsException:
    """Lines 536-538: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        # get_public_company_reviews uses db.execute inside try
        mock_db.execute.side_effect = RuntimeError("reviews boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_public_company_reviews(mock_db, limit=10, company_id=1)


class TestListPublicCategoriesException:
    """Lines 568-570: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        # list_public_categories uses db.scalars(stmt) inside try
        mock_db.scalars.side_effect = RuntimeError("cat boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.list_public_categories(mock_db, company_id=1)


class TestRespondToMarketplaceRequestVehicleNotFound:
    """Line 720: vehicle not found or wrong company (async method)."""

    @pytest.mark.asyncio
    async def test_wrong_company(self, svc):
        mock_db = MagicMock()
        request_obj = MagicMock()
        request_obj.source_channel = "marketplace"
        request_obj.status = "new"
        request_obj.company_id = 99
        vehicle = SimpleNamespace(company_id=88, status="active")
        mock_db.get.side_effect = [request_obj, vehicle]
        with patch("app.services.notification_service.create_notification"):
            with pytest.raises(HTTPException, match="not found"):
                await svc.respond_to_marketplace_request(
                    mock_db, company_id=1, request_id=1, vehicle_id=5,
                    current_user=SimpleNamespace(id=1),
                )


class TestExportMarketplaceRequestsImportError:
    """Lines 1067-1068: openpyxl ImportError."""

    def test_import_error(self, svc):
        mock_db = MagicMock()
        import builtins
        original_import = builtins.__import__
        def failing_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("no openpyxl")
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, "__import__", side_effect=failing_import):
            with pytest.raises(HTTPException, match="openpyxl not installed"):
                svc.export_marketplace_requests(mock_db, category_id=None)


class TestMarketplacePayoutsHighlight:
    """Line 1153: payment_days > 7 highlight."""

    def test_extended_payment(self, svc):
        mock_db = MagicMock()
        row = (1, 1, "OOO Contractor", "9876543210", 50000.0, 5000.0, 45000.0,
               "approved", datetime(2026, 11, 1), 14, "Excavator", "earthworks")
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
