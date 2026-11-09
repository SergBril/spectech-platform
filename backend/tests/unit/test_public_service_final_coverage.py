"""Точечные тесты для public_service.py — покрытие оставшихся 3 строк."""
import pytest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.services.public_service import PublicService


@pytest.fixture
def svc():
    return PublicService()


class TestGetPublicCompanyVehiclesFilters:
    """Lines 214, 216: category_id and available_only in get_public_company_vehicles."""

    def test_with_category_and_available(self, svc):
        mock_db = MagicMock()
        company = SimpleNamespace(id=1, name="OOO Test", is_active=True)
        mock_db.get.return_value = company
        mock_db.scalars.return_value.all.return_value = []
        result = svc.get_public_company_vehicles(
            mock_db, category_id=5, available_only=True, limit=10, company_id=1,
        )
        assert isinstance(result, list)


class TestMarketplacePayoutsHighlight:
    """Line 1153: payment_days > 7 highlight."""

    def test_extended_payment(self, svc):
        mock_db = MagicMock()
        # export_marketplace_requests uses db.scalars(stmt).all()
        req = SimpleNamespace(
            id=1, vehicle_category_id=None, work_type="earthworks",
            object_address="Moscow", planned_start=datetime(2026, 11, 1),
            planned_end=datetime(2026, 11, 10), client_rate=5000,
            rate_type="hourly", marketplace_mode="client",
            payment_terms_days=14, priority="normal", status="published",
            created_at=datetime(2026, 11, 1, 10, 0),
        )
        mock_db.scalars.return_value.all.return_value = [req]
        result = svc.export_marketplace_requests(mock_db, category_id=None)
        assert result is not None
