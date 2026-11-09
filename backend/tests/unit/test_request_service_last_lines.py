"""Точечные тесты для request_service.py: 233."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from datetime import datetime, UTC


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    from app.services.request_service import RequestService
    return RequestService(mock_db)


class TestAssignVehicleReraise:
    @pytest.mark.asyncio
    async def test_reraise_on_integrity_error(self, service, mock_db):
        from sqlalchemy.exc import IntegrityError
        from app.services.request_service import RequestServiceError

        req = SimpleNamespace(
            id=1, company_id=1, status="new",
            planned_start=datetime(2026, 11, 10, tzinfo=UTC),
            planned_end=datetime(2026, 11, 15, tzinfo=UTC),
            source_channel="direct",
        )
        vehicle = SimpleNamespace(
            id=2, company_id=1, status="active", name="Truck",
            marketplace_commission_agreed=True,
        )
        mock_db.get.side_effect = lambda m, i: req if i == 1 else vehicle

        # db.scalar() for overlap check -> return None (no overlap)
        # db.query().filter().first() for idempotency -> return None
        mock_db.scalar.return_value = None
        mock_query_chain = MagicMock()
        mock_query_chain.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query_chain

        # Make commit raise IntegrityError -> caught at line 228 -> RequestServiceError(409) -> line 233 re-raise
        mock_db.commit.side_effect = IntegrityError("duplicate", None, None)

        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            with pytest.raises(RequestServiceError) as exc_info:
                await service.assign_vehicle(1, 2, None, 1, 1)
            assert exc_info.value.status_code == 409
