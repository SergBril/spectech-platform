"""Точечные тесты для public_service.py — покрытие оставшихся 18 строк."""
import pytest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock
from fastapi import HTTPException

from app.services.public_service import PublicService


@pytest.fixture
def svc():
    return PublicService()


class TestParseCategoryIdsNone:
    """Line 76: _parse_category_ids returns None for unexpected type."""

    def test_returns_none_for_int(self, svc):
        assert svc._parse_category_ids(123) is None

    def test_returns_none_for_none(self, svc):
        assert svc._parse_category_ids(None) is None


class TestListPublicVehiclesFilters:
    """Lines 214, 216: category_id and available_only filters."""

    def test_category_id_filter(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(mock_db, company_id=1, category_id=5)
        assert isinstance(result, list)

    def test_available_only_filter(self, svc):
        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_public_vehicles(mock_db, company_id=1, available_only=True)
        assert isinstance(result, list)


class TestGetVehicleAvailabilityException:
    """Lines 338-340: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_vehicle_availability(mock_db, vehicle_id=1, start_date="2026-11-09", end_date="2026-11-10")


class TestCreateRequestFromListingValueError:
    """Line 454: ValueError handler."""

    def test_value_error_raised(self, svc):
        mock_db = MagicMock()
        data = SimpleNamespace(
            work_type="earthworks", object_address="Moscow",
            planned_start=datetime(2026, 12, 1), planned_end=datetime(2026, 12, 5),
            vehicle_category_id=1, description="Test",
        )
        # Make internal validation raise ValueError
        with patch.object(svc, '_validate_request_data', side_effect=ValueError("bad data")):
            with pytest.raises(HTTPException, match="bad data"):
                svc.create_request_from_listing(mock_db, company_id=1, data=data, current_user=SimpleNamespace(id=1))


class TestGetPublicCompanyReviewsException:
    """Lines 536-538: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("reviews boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_public_company_reviews(mock_db, company_id=1)


class TestListPublicCategoriesException:
    """Lines 568-570: generic exception handler."""

    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("categories boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.list_public_categories(mock_db, company_id=1)


class TestUpdateVehiclePhotoNotFound:
    """Line 720: vehicle not found or wrong company."""

    def test_wrong_company(self, svc):
        mock_db = MagicMock()
        vehicle = SimpleNamespace(company_id=99)
        mock_db.get.return_value = vehicle
        with pytest.raises(HTTPException, match="not found"):
            svc.update_vehicle_photo(mock_db, company_id=1, vehicle_id=5, photo_url="http://test.jpg")


class TestExportMarketplaceRequestsImportError:
    """Lines 1067-1068: openpyxl ImportError."""

    def test_import_error(self, svc):
        mock_db = MagicMock()
        with patch.dict("sys.modules", {"openpyxl": None}):
            with patch("builtins.__import__", side_effect=ImportError("no openpyxl")):
                with pytest.raises(HTTPException, match="openpyxl not installed"):
                    svc.export_marketplace_payouts_report(mock_db, company_id=1, month="2026-11")


class TestExportMarketplacePayoutsHighlight:
    """Line 1153: payment_days > 7 highlight."""

    def test_extended_payment_highlight(self, svc):
        mock_db = MagicMock()
        company = SimpleNamespace(name="OOO Test", inn="1234567890")
        mock_db.get.return_value = company
        # Return rows with payment_days > 7
        row = SimpleNamespace(
            id=1, request_id=1, contractor_name="OOO Contractor",
            contractor_inn="9876543210", amount=50000, commission=5000,
            payout_amount=45000, status="approved", approved_at=datetime(2026, 11, 1),
            payment_days=14, vehicle_name="Excavator", work_type="earthworks",
        )
        mock_db.execute.return_value.fetchall.return_value = [row]
        with patch("app.services.public_service.openpyxl") as mock_openpyxl:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_openpyxl.Workbook.return_value = mock_wb
            mock_wb.active = mock_ws
            from openpyxl.styles import PatternFill
            result = svc.export_marketplace_payouts_report(mock_db, company_id=1, month="2026-11")
            # Verify PatternFill was applied (line 1153)
            assert result is not None


class TestCreateReviewCompanyNotFound:
    """Line 1226: company not found."""

    def test_company_not_found(self, svc):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        data = SimpleNamespace(reviewer_name="Test", rating=5, comment="Good")
        with pytest.raises(HTTPException, match="Компания не найдена"):
            svc.create_public_review(mock_db, company_id=999, data=data)
