"""Tests for PublicService - real code execution coverage."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def service():
    from app.services.public_service import PublicService

    return PublicService()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestHealthCheck:
    def test_returns_ok(self, service, mock_db):
        result = service.health_check(mock_db)
        assert result["status"] == "ok"
        assert "timestamp" in result


class TestListPublicCompanies:
    def test_empty_result(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_companies(
            mock_db, company_type=None, city=None, limit=10, offset=0
        )
        assert result == []

    def test_with_company_type_filter(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_companies(
            mock_db, company_type="rental", city=None, limit=10, offset=0
        )
        assert isinstance(result, list)

    def test_with_city_filter(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_companies(
            mock_db, company_type=None, city="Москва", limit=10, offset=0
        )
        assert isinstance(result, list)


class TestGetPublicCompany:
    def test_not_found_raises_404(self, service, mock_db):
        mock_db.get.return_value = None
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.get_public_company(mock_db, company_id=999)
        assert exc_info.value.status_code == 404

    def test_inactive_company_raises_404(self, service, mock_db):
        company = MagicMock(is_active=False)
        mock_db.get.return_value = company
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.get_public_company(mock_db, company_id=1)
        assert exc_info.value.status_code == 404


class TestListPublicVehicles:
    def test_empty_result(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_vehicles(
            mock_db,
            category_id=None,
            available_only=False,
            min_hourly_rate=None,
            max_hourly_rate=None,
            limit=10,
            offset=0,
        )
        assert result == []

    def test_with_filters(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_vehicles(
            mock_db,
            category_id=1,
            available_only=True,
            min_hourly_rate=500,
            max_hourly_rate=5000,
            limit=10,
            offset=0,
        )
        assert isinstance(result, list)


class TestGetVehicleAvailability:
    def test_vehicle_not_found(self, service, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = None
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                service.get_vehicle_availability(
                    mock_db,
                    vehicle_id=999,
                    from_date="2026-11-01",
                    to_date="2026-11-07",
                )
            assert exc_info.value.status_code == 404

    def test_invalid_date_format(self, service, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_vehicle = MagicMock(id=1, name="Test")
            mock_ms.get_vehicle_details.return_value = mock_vehicle
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                service.get_vehicle_availability(
                    mock_db, vehicle_id=1, from_date="invalid", to_date="2026-11-07"
                )
            assert exc_info.value.status_code == 400


class TestCreateRequestFromListing:
    def test_vehicle_not_found(self, service, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = None
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                service.create_request_from_listing(mock_db, vehicle_id=999, data={})
            assert exc_info.value.status_code == 404


class TestRespondToMarketplaceRequest:
    @pytest.mark.asyncio
    async def test_request_not_found(self, service, mock_db):
        mock_db.get.return_value = None
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service.respond_to_marketplace_request(
                mock_db, company_id=1, request_id=999, vehicle_id=1
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_source_channel(self, service, mock_db):
        req = MagicMock(source_channel="direct", status="new")
        mock_db.get.return_value = req
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service.respond_to_marketplace_request(
                mock_db, company_id=1, request_id=1, vehicle_id=1
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_status(self, service, mock_db):
        req = MagicMock(source_channel="marketplace", status="completed", company_id=2)
        mock_db.get.return_value = req
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service.respond_to_marketplace_request(
                mock_db, company_id=1, request_id=1, vehicle_id=1
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_self_response_blocked(self, service, mock_db):
        req = MagicMock(source_channel="marketplace", status="new", company_id=1)
        mock_db.get.return_value = req
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service.respond_to_marketplace_request(
                mock_db, company_id=1, request_id=1, vehicle_id=1
            )
        assert exc_info.value.status_code == 403


class TestMarketplacePayoutsReport:
    def test_openpyxl_missing(self, service, mock_db):
        import sys

        saved = sys.modules.get("openpyxl")
        sys.modules["openpyxl"] = None
        try:
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                service.marketplace_payouts_report(
                    mock_db, date_from=None, date_to=None
                )
            assert exc_info.value.status_code == 500
        finally:
            if saved is not None:
                sys.modules["openpyxl"] = saved
            elif "openpyxl" in sys.modules:
                del sys.modules["openpyxl"]


class TestGetPublicCompanyRating:
    def test_company_not_found(self, service, mock_db):
        mock_db.get.return_value = None
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.get_public_company_rating(mock_db, company_id=999)
        assert exc_info.value.status_code == 404


class TestListPublicCategories:
    def test_empty(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_public_categories(mock_db)
        assert isinstance(result, list)


class TestMarketplaceStats:
    def test_returns_dict(self, service, mock_db):
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_db.execute.return_value = mock_scalar
        result = service.marketplace_stats(mock_db)
        assert isinstance(result, dict)


class TestPublicServiceEdgeCases:
    """Cover remaining 37 lines: error handlers, normalize_photos, build_vehicle, create_review."""

    def test_normalize_photos_dict(self, service):
        """Line 76: value is dict with values."""
        result = service._normalize_photos({"a": "url1", "b": None, "c": "url2"})
        assert result == ["url1", "url2"]

    def test_normalize_photos_none(self, service):
        result = service._normalize_photos(None)
        assert result is None

    def test_build_vehicle_response_with_company(self, service, mock_db):
        """Lines 84-85: v.company exists."""
        v = MagicMock()
        v.company = MagicMock(name="TestCo")
        v.category = None  # Avoid MagicMock auto-attribute returning non-string
        v.id = 1
        v.name = "Excavator"
        v.category_id = None
        v.status = "active"
        v.company_id = 1
        v.hourly_rate = 1000
        v.shift_rate = None
        v.is_available_for_rent = True
        v.photos = None
        v.marketplace_commission_agreed = True
        v.marketplace_commission_rate = None
        v.year = 2020
        result = service._build_vehicle_response(
            mock_db, company_id=1, v=v, company_name="TestCo"
        )
        assert result is not None

    def test_build_vehicle_response_no_company(self, service, mock_db):
        """Lines 84-85: v.company raises exception."""
        v = MagicMock()
        type(v).company = property(
            lambda self: (_ for _ in ()).throw(Exception("no company"))
        )
        v.category = None
        v.id = 1
        v.name = "Excavator"
        v.category_id = None
        v.status = "active"
        v.company_id = None
        v.hourly_rate = None
        v.shift_rate = None
        v.is_available_for_rent = False
        v.photos = None
        v.marketplace_commission_agreed = False
        v.marketplace_commission_rate = None
        v.year = None
        result = service._build_vehicle_response(
            mock_db, company_id=None, v=v, company_name=None
        )
        assert result is not None

    def test_list_public_companies_error_handler(self, service, mock_db):
        """Lines 157-159: exception in list_public_companies."""
        mock_db.scalars.side_effect = RuntimeError("DB error")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.list_public_companies(
                mock_db, company_type=None, city=None, limit=10, offset=0
            )
        assert exc_info.value.status_code == 500

    def test_get_public_company_vehicles_error(self, service, mock_db):
        """Lines 228-230: exception in get_public_company_vehicles."""
        company = MagicMock(id=1, name="Test", is_active=True)
        mock_db.get.return_value = company
        # db.query().filter().count() works, but scalars().all() fails
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.scalars.side_effect = RuntimeError("DB fail")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.get_public_company_vehicles(
                mock_db, company_id=1, category_id=None, available_only=False, limit=10
            )
        assert exc_info.value.status_code == 500

    def test_list_public_vehicles_error(self, service, mock_db):
        """Lines 274-276: exception in list_public_vehicles."""
        mock_db.scalars.side_effect = RuntimeError("DB error")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.list_public_vehicles(
                mock_db,
                category_id=None,
                available_only=False,
                min_hourly_rate=None,
                max_hourly_rate=None,
                limit=10,
                offset=0,
            )
        assert exc_info.value.status_code == 500

    def test_get_public_vehicle_details_error(self, service, mock_db):
        """Lines 297-299: exception in get_public_vehicle_details."""
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.side_effect = RuntimeError("fail")
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                service.get_public_vehicle_details(mock_db, vehicle_id=1)
            assert exc_info.value.status_code == 500

    def test_create_company_review_duplicate(self, service, mock_db):
        """Lines 1244-1248: duplicate review check."""
        # Mock existing review found
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock(id=1)
        payload = MagicMock(
            reviewer_name="User",
            reviewer_email="test@test.com",
            rating=5,
            comment="Again",
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            service.create_company_review(mock_db, company_id=1, payload=payload)
        assert exc_info.value.status_code == 400

    def test_create_company_review_success(self, service, mock_db):
        """Lines 1250-1274: successful review creation."""
        # Raw SQL uses .first() for SELECT and .one() for INSERT
        mock_result = MagicMock()
        mock_result.id = 42
        mock_result.rating = 5
        mock_result.comment = "Excellent!"
        mock_result.created_at = datetime(2026, 11, 8, 12, 0)

        select_result = MagicMock()
        select_result.first.return_value = None  # No duplicate

        insert_result = MagicMock()
        insert_result.one.return_value = mock_result

        mock_db.execute.side_effect = [select_result, insert_result]

        payload = MagicMock(
            reviewer_name="Happy User",
            reviewer_email="happy@test.com",
            rating=5,
            comment="Excellent!",
        )
        result = service.create_company_review(mock_db, company_id=1, payload=payload)
        assert "id" in result
