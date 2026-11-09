"""Comprehensive tests for fuel_card_service -> 100%."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInit:
    def test_enabled_with_key(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "test-key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            assert svc.enabled is True
            assert svc.provider == "gazpromneft"

    def test_disabled_without_key(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = ""
            s.FUEL_CARD_PROVIDER = "custom"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            assert svc.enabled is False


class TestFetchTransactions:
    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = ""
            s.FUEL_CARD_PROVIDER = "custom"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            r = await svc.fetch_transactions("2026-01-01", "2026-01-31")
            assert r == []

    @pytest.mark.asyncio
    async def test_gazpromneft_success(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            s.FUEL_CARD_BASE_URL = "https://api.test.com"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"items": [
                {"vehicle_reg_number": "A123BC", "card_number": "1234",
                 "transaction_date": "2026-01-15T10:00:00", "volume": 50.5,
                 "fuel_type": "Diesel", "odometer": 12345, "amount": 3000,
                 "station_name": "GPN Station"}
            ]}
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.fuel_card_service.httpx.AsyncClient", return_value=mock_client):
                r = await svc.fetch_transactions("2026-01-01", "2026-01-31", ["1234"])
            assert len(r) == 1
            assert r[0]["vehicle_plate"] == "A123BC"
            assert r[0]["liters"] == 50.5
            assert r[0]["fuel_type"] == "diesel"

    @pytest.mark.asyncio
    async def test_lukoil_success(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "lukoil"
            s.FUEL_CARD_BASE_URL = "https://api.lukoil.test"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"data": [
                {"gos_number": "B456CD", "card_num": "5678",
                 "operation_date": "2026-02-10T12:00:00", "volume_litres": 40.0,
                 "fuel_code": "ai95", "mileage": 54321, "sum_nds": 2500,
                 "azs_name": "Lukoil AZS"}
            ]}
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.fuel_card_service.httpx.AsyncClient", return_value=mock_client):
                r = await svc.fetch_transactions("2026-02-01", "2026-02-28")
            assert len(r) == 1
            assert r[0]["vehicle_plate"] == "B456CD"
            assert r[0]["fuel_type"] == "ai95"

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "unknown"
            s.FUEL_CARD_BASE_URL = "https://test.com"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.fuel_card_service.httpx.AsyncClient", return_value=mock_client):
                r = await svc.fetch_transactions("2026-01-01", "2026-01-31")
            assert r == []

    @pytest.mark.asyncio
    async def test_api_error(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            s.FUEL_CARD_BASE_URL = "https://test.com"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("API down"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.fuel_card_service.httpx.AsyncClient", return_value=mock_client):
                r = await svc.fetch_transactions("2026-01-01", "2026-01-31")
            assert r == []

    @pytest.mark.asyncio
    async def test_gazpromneft_list_response(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            s.FUEL_CARD_BASE_URL = "https://test.com"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            mock_resp = MagicMock()
            mock_resp.json.return_value = [
                {"plate": "X789YZ", "card_number": "9999",
                 "date": "2026-03-01", "quantity": 30,
                 "fuel_type": "gasoline", "amount": 1800,
                 "station_name": "Test"}
            ]
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.fuel_card_service.httpx.AsyncClient", return_value=mock_client):
                r = await svc.fetch_transactions("2026-03-01", "2026-03-31")
            assert len(r) == 1
            assert r[0]["vehicle_plate"] == "X789YZ"


class TestSyncToShiftEntries:
    @pytest.mark.asyncio
    async def test_sync_success(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            db = MagicMock()
            vehicle = SimpleNamespace(id=1)
            shift = SimpleNamespace(id=10)
            db.execute.return_value.scalar_one_or_none.side_effect = [vehicle, None]
            db.execute.return_value.scalars.return_value.first.return_value = shift
            txns = [{"vehicle_plate": "A123BC", "date": "2026-01-15",
                     "fuel_type": "diesel", "liters": 50, "odometer": 12345,
                     "card_number": "1234"}]
            r = await svc.sync_to_shift_entries(db, 1, txns)
            assert r["synced"] == 1
            assert r["skipped"] == 0

    @pytest.mark.asyncio
    async def test_skip_no_vehicle(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            db = MagicMock()
            db.execute.return_value.scalar_one_or_none.return_value = None
            txns = [{"vehicle_plate": "UNKNOWN", "date": "2026-01-15",
                     "fuel_type": "diesel", "liters": 50}]
            r = await svc.sync_to_shift_entries(db, 1, txns)
            assert r["synced"] == 0
            assert r["skipped"] == 1

    @pytest.mark.asyncio
    async def test_skip_no_shift(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            db = MagicMock()
            vehicle = SimpleNamespace(id=1)
            exec_results = [MagicMock(), MagicMock()]
            exec_results[0].scalar_one_or_none.return_value = vehicle
            exec_results[1].scalars.return_value.first.return_value = None
            db.execute.side_effect = exec_results
            txns = [{"vehicle_plate": "A123BC", "date": "2026-01-15",
                     "fuel_type": "diesel", "liters": 50}]
            r = await svc.sync_to_shift_entries(db, 1, txns)
            assert r["synced"] == 0
            assert r["skipped"] == 1

    @pytest.mark.asyncio
    async def test_skip_duplicate(self):
        with patch("app.core.config.settings") as s:
            s.FUEL_CARD_API_KEY = "key"
            s.FUEL_CARD_PROVIDER = "gazpromneft"
            from app.services.fuel_card_service import FuelCardService
            svc = FuelCardService()
            db = MagicMock()
            vehicle = SimpleNamespace(id=1)
            shift = SimpleNamespace(id=10)
            existing = SimpleNamespace(id=100)
            exec_results = [MagicMock(), MagicMock(), MagicMock()]
            exec_results[0].scalar_one_or_none.return_value = vehicle
            exec_results[1].scalars.return_value.first.return_value = shift
            exec_results[2].scalar_one_or_none.return_value = existing
            db.execute.side_effect = exec_results
            txns = [{"vehicle_plate": "A123BC", "date": "2026-01-15",
                     "fuel_type": "diesel", "liters": 50}]
            r = await svc.sync_to_shift_entries(db, 1, txns)
            assert r["synced"] == 0
            assert r["skipped"] == 1
