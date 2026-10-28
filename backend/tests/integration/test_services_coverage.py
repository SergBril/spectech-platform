"""Tests for services coverage improvement."""

import pytest


class TestFuelService:
    """Cover FuelService methods."""

    def test_get_fuel_analytics(self, db_session):
        from app.services.fuel_service import FuelService
        svc = FuelService()
        result = svc.get_fuel_analytics(db_session, company_id=1)
        assert isinstance(result, dict)

    def test_detect_anomalies(self, db_session):
        from app.services.fuel_service import FuelService
        svc = FuelService()
        result = svc.detect_anomalies(db_session, company_id=1)
        assert isinstance(result, (list, dict))

    def test_get_consumption_rates(self, db_session):
        from app.services.fuel_service import FuelService
        svc = FuelService()
        result = svc.get_consumption_rates(db_session, company_id=1)
        assert isinstance(result, (list, dict))


class TestDadataService:
    """Cover DaDataService methods."""

    @pytest.mark.asyncio
    async def test_suggest_party_empty(self):
        from app.services.dadata_service import DaDataService
        svc = DaDataService()
        result = await svc.suggest_party_by_inn("")
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_suggest_bank_by_bik(self):
        from app.services.dadata_service import DaDataService
        svc = DaDataService()
        result = await svc.suggest_bank_by_bik("000000000")
        assert result is None or isinstance(result, dict)


class TestMaintenanceService:
    """Cover MaintenanceService methods."""

    def test_generate_order_number(self, db_session):
        from app.services.maintenance_service import MaintenanceService
        result = MaintenanceService.generate_order_number(db_session)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_upcoming_maintenance(self, db_session):
        from app.services.maintenance_service import MaintenanceService
        svc = MaintenanceService()
        result = svc.get_upcoming_maintenance(db_session, company_id=1)
        assert isinstance(result, list)


class TestAlertEngineChecks:
    """Cover alert_engine check functions."""

    def test_check_speed_no_alert(self, db_session, sample_vehicle):
        from app.services.alert_engine import _check_speed
        from app.models.telematics import GpsPoint, AlertRule
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            speed=50.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        rule = AlertRule(
            company_id=1,
            rule_type="speed",
            threshold=100.0,
            is_active=True,
        )
        result = _check_speed(db_session, point, rule)
        assert result is None

    def test_check_fuel_no_prev(self, db_session, sample_vehicle):
        from app.services.alert_engine import _check_fuel
        from app.models.telematics import GpsPoint, AlertRule
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            fuel_level=80.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        rule = AlertRule(
            company_id=1,
            rule_type="fuel_drop",
            threshold=10.0,
            is_active=True,
        )
        result = _check_fuel(db_session, point, rule)
        assert result is None


class TestVehicleMatcherService:
    """Cover VehicleMatcherService methods."""

    def test_find_matching_vehicles(self, db_session):
        from app.services.marketplace.vehicle_matcher import VehicleMatcherService
        svc = VehicleMatcherService()
        result = svc.find_matching_vehicles(db_session, request_id=99999, company_id=1)
        assert isinstance(result, list)
