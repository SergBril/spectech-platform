"""Полные тесты для public_service.py — покрытие всех строк."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.public_service import PublicService


@pytest.fixture
def svc():
    return PublicService()


# === Line 76: _normalize_photos returns None for unexpected type ===
class TestNormalizePhotosNone:
    def test_returns_none_for_int(self, svc):
        assert svc._normalize_photos(123) is None


# === Lines 214, 216: category_id and available_only filters ===
class TestGetPublicCompanyVehiclesFilters:
    def test_with_category_and_available(self, svc):
        mock_db = MagicMock()
        company = SimpleNamespace(id=1, name="OOO Test", is_active=True)
        mock_db.get.return_value = company
        mock_db.scalars.return_value.all.return_value = []
        result = svc.get_public_company_vehicles(
            mock_db,
            category_id=5,
            available_only=True,
            limit=10,
            company_id=1,
        )
        assert isinstance(result, list)


# === Lines 338-340: get_vehicle_availability generic exception ===
class TestGetVehicleAvailabilityException:
    def test_internal_error(self, svc):
        mock_db = MagicMock()
        with patch("app.services.marketplace_service.marketplace_service") as mock_mkt:
            mock_mkt.get_vehicle_details.return_value = SimpleNamespace(
                id=1, name="Test"
            )
            mock_mkt.get_availability_calendar.side_effect = RuntimeError("boom")
            with pytest.raises(HTTPException, match="Internal error"):
                svc.get_vehicle_availability(
                    mock_db, vehicle_id=1, from_date="2026-11-09", to_date="2026-11-10"
                )


# === Line 454: create_request_from_listing ValueError handler ===
class TestCreateRequestFromListingValueError:
    def test_value_error_from_marketplace(self, svc):
        mock_db = MagicMock()
        data = SimpleNamespace(
            work_type="earthworks",
            object_address="Moscow",
            planned_start="2026-12-01T00:00:00",
            planned_end="2026-12-05T00:00:00",
            contact_name="Test",
            contact_phone="+79990000000",
            contact_email="test@test.com",
            comment="Test",
        )
        with patch("app.services.marketplace_service.marketplace_service") as mock_mkt:
            mock_mkt.get_vehicle_details.return_value = SimpleNamespace(
                id=1, name="Test", company_id=1
            )
            mock_mkt.create_request_from_listing.side_effect = ValueError("bad value")
            with pytest.raises(HTTPException, match="bad value"):
                svc.create_request_from_listing(
                    mock_db, vehicle_id=1, data=data, company_id=1
                )


# === Lines 536-538: get_public_company_reviews generic exception ===
class TestGetPublicCompanyReviewsException:
    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("reviews boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.get_public_company_reviews(mock_db, limit=10, company_id=1)


# === Lines 568-570: list_public_categories generic exception ===
class TestListPublicCategoriesException:
    def test_internal_error(self, svc):
        mock_db = MagicMock()
        mock_db.scalars.side_effect = RuntimeError("cat boom")
        with pytest.raises(HTTPException, match="Internal error"):
            svc.list_public_categories(mock_db, company_id=1)


# === Line 720: respond_to_marketplace_request vehicle not found (async) ===
class TestRespondToMarketplaceRequestVehicleNotFound:
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
                    mock_db,
                    company_id=1,
                    request_id=1,
                    vehicle_id=5,
                    current_user=SimpleNamespace(id=1),
                )


# === Lines 1067-1068: openpyxl ImportError ===
class TestExportMarketplaceRequestsImportError:
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
                svc.export_marketplace_requests(mock_db, category_id=None, company_id=1)


# === Line 1153: payment_days > 7 highlight ===
class TestMarketplacePayoutsHighlight:
    def test_extended_payment(self, svc):
        mock_db = MagicMock()
        req = SimpleNamespace(
            id=1,
            vehicle_category_id=None,
            work_type="earthworks",
            object_address="Moscow",
            planned_start=datetime(2026, 11, 1),
            planned_end=datetime(2026, 11, 10),
            client_rate=5000,
            rate_type="hourly",
            marketplace_mode="client",
            payment_terms_days=14,
            priority="normal",
            status="published",
            created_at=datetime(2026, 11, 1, 10, 0),
        )
        mock_db.scalars.return_value.all.return_value = [req]
        result = svc.export_marketplace_requests(
            mock_db, category_id=None, company_id=1
        )
        assert result is not None


# === Line 1226: create_company_review company not found ===
class TestCreateCompanyReviewNotFound:
    def test_company_not_found(self, svc):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        payload = SimpleNamespace(reviewer_name="Test", rating=5, comment="Good")
        with pytest.raises(HTTPException, match="Компания не найдена"):
            svc.create_company_review(mock_db, payload=payload, company_id=999)
