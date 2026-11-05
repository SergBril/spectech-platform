"""Coverage tests for vehicle_service."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


class TestVehicleServiceError:
    """Cover VehicleServiceError (lines 10-17)."""

    def test_init(self):
        from app.services.vehicle_service import VehicleServiceError

        err = VehicleServiceError(404, "Not found")
        assert err.status_code == 404
        assert err.detail == "Not found"


class TestSaveVehicleAttributes:
    """Cover save_vehicle_attributes (lines 20-77)."""

    def test_no_attributes_returns(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        save_vehicle_attributes(mock_db, 1, None, None)
        mock_db.add.assert_not_called()

    def test_number_attribute(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=1, data_type="number", slug="mass")
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def

        save_vehicle_attributes(mock_db, 1, 2, {"mass": "20.5"})
        mock_db.add.assert_called_once()

    def test_boolean_attribute(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=1, data_type="boolean", slug="has_ac")
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def

        save_vehicle_attributes(mock_db, 1, 2, {"has_ac": True})
        mock_db.add.assert_called_once()

    def test_select_attribute_with_option(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=1, data_type="select", slug="chassis")
        option = SimpleNamespace(id=10)

        query_count = {"n": 0}

        def mock_query(model):
            query_count["n"] += 1
            mq = MagicMock()
            if query_count["n"] == 1:
                mq.filter.return_value.first.return_value = attr_def
            else:
                mq.filter.return_value.first.return_value = option
            return mq

        mock_db.query.side_effect = mock_query

        save_vehicle_attributes(mock_db, 1, 2, {"chassis": "wheeled"})
        mock_db.add.assert_called_once()

    def test_unknown_slug_skipped(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        mock_db.query.return_value.filter.return_value.first.return_value = None

        save_vehicle_attributes(mock_db, 1, 2, {"unknown": "val"})
        mock_db.add.assert_not_called()


class TestLoadVehicleWithRelations:
    """Cover load_vehicle_with_relations (lines 79-101)."""

    def test_returns_vehicle(self, mock_db):
        from app.services.vehicle_service import load_vehicle_with_relations

        vehicle = SimpleNamespace(id=1)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            vehicle
        )

        result = load_vehicle_with_relations(mock_db, 1)
        assert result.id == 1

    def test_returns_none(self, mock_db):
        from app.services.vehicle_service import load_vehicle_with_relations

        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )

        result = load_vehicle_with_relations(mock_db, 999)
        assert result is None


class TestEnrichVehicle:
    """Cover enrich_vehicle (lines 103-166)."""

    def test_with_category_level2(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle

        parent_cat = SimpleNamespace(name="Excavators")
        sub_cat = SimpleNamespace(name="Wheeled", level=2, parent=parent_cat)
        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            category=sub_cat,
            attribute_values=[],
            assigned_driver_id=None,
        )

        with patch("app.schemas.vehicles.VehicleRead") as mock_vr:
            mock_vr.model_validate.return_value.model_dump.return_value = {
                "id": 1,
                "name": "KAMAZ",
                "attribute_values": [],
            }
            result = enrich_vehicle(vehicle, mock_db)

        assert result["category_name"] == "Excavators"
        assert result["subcategory_name"] == "Wheeled"

    def test_with_driver(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle

        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            category=None,
            attribute_values=[],
            assigned_driver_id=10,
        )
        emp = SimpleNamespace(contractor=SimpleNamespace(name="Ivan"))
        mock_db.query.return_value.filter.return_value.first.return_value = emp

        with patch("app.schemas.vehicles.VehicleRead") as mock_vr:
            mock_vr.model_validate.return_value.model_dump.return_value = {
                "id": 1,
                "name": "KAMAZ",
                "attribute_values": [],
            }
            result = enrich_vehicle(vehicle, mock_db)

        assert result["driver_name"] == "Ivan"
        assert result["assigned_driver_name"] == "Ivan"


class TestLogDriverAssignment:
    """Cover log_driver_assignment (lines 168-202)."""

    def test_close_old_and_create_new(self, mock_db):
        from app.services.vehicle_service import log_driver_assignment

        old_log = SimpleNamespace(unassigned_at=None)
        mock_db.query.return_value.filter.return_value.first.return_value = old_log

        log_driver_assignment(mock_db, 1, old_driver_id=5, new_driver_id=10, user_id=1)
        assert old_log.unassigned_at is not None
        mock_db.add.assert_called_once()

    def test_no_change(self, mock_db):
        from app.services.vehicle_service import log_driver_assignment

        log_driver_assignment(mock_db, 1, old_driver_id=5, new_driver_id=5, user_id=1)
        mock_db.add.assert_not_called()


class TestClearVehicleAttributes:
    """Cover clear_vehicle_attributes (lines 204-211)."""

    def test_deletes(self, mock_db):
        from app.services.vehicle_service import clear_vehicle_attributes

        clear_vehicle_attributes(mock_db, 1)
        mock_db.query.return_value.filter.return_value.delete.assert_called_once()


class TestCreateVehicle:
    """Cover create_vehicle (lines 213-268)."""

    def test_duplicate_id_value(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, create_vehicle

        mock_db.scalar.return_value = SimpleNamespace(id=1)

        with pytest.raises(VehicleServiceError) as exc:
            create_vehicle(mock_db, {"id_value": "ABC123"}, company_id=1)
        assert exc.value.status_code == 409

    def test_invalid_subcategory(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, create_vehicle

        mock_db.scalar.return_value = None
        mock_db.get.return_value = SimpleNamespace(level=1)

        with pytest.raises(VehicleServiceError) as exc:
            create_vehicle(mock_db, {"subcategory_id": 99}, company_id=1)
        assert exc.value.status_code == 400

    def test_success(self, mock_db):
        from app.services.vehicle_service import create_vehicle

        sub = SimpleNamespace(level=2, parent_id=1)
        vehicle_obj = SimpleNamespace(id=1)

        def mock_get(model, pk):
            return sub

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1) or None

        with (
            patch(
                "app.services.vehicle_service.load_vehicle_with_relations"
            ) as mock_load,
            patch("app.services.vehicle_service.enrich_vehicle") as mock_enrich,
            patch("app.services.vehicle_service.save_vehicle_attributes"),
        ):
            mock_load.return_value = vehicle_obj
            mock_enrich.return_value = {"id": 1, "name": "Test"}
            result = create_vehicle(
                mock_db, {"name": "Test", "subcategory_id": 2}, company_id=1
            )

        assert result["id"] == 1
        mock_db.commit.assert_called()


class TestUpdateVehicle:
    """Cover update_vehicle (lines 270-end)."""

    def test_not_found(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, update_vehicle

        mock_db.get.return_value = None

        with pytest.raises(VehicleServiceError) as exc:
            update_vehicle(mock_db, 999, {}, None, 1, 1)
        assert exc.value.status_code == 404

    def test_duplicate_id_value_on_update(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, update_vehicle

        vehicle = SimpleNamespace(
            id=1,
            is_deleted=False,
            company_id=1,
            id_value="OLD",
            assigned_driver_id=None,
        )
        mock_db.get.return_value = vehicle
        mock_db.scalar.return_value = SimpleNamespace(id=2)

        with pytest.raises(VehicleServiceError) as exc:
            update_vehicle(mock_db, 1, {"id_value": "NEW"}, None, 1, 1)
        assert exc.value.status_code == 409

    def test_success_with_driver_change(self, mock_db):
        from app.services.vehicle_service import update_vehicle

        vehicle = SimpleNamespace(
            id=1, is_deleted=False, company_id=1, id_value="ABC", assigned_driver_id=5
        )

        mock_db.get.return_value = vehicle
        mock_db.scalar.return_value = None

        with (
            patch("app.services.vehicle_service.log_driver_assignment") as mock_log,
            patch(
                "app.services.vehicle_service.load_vehicle_with_relations"
            ) as mock_load,
            patch("app.services.vehicle_service.enrich_vehicle") as mock_enrich,
        ):
            mock_load.return_value = vehicle
            mock_enrich.return_value = {"id": 1}
            update_vehicle(mock_db, 1, {"assigned_driver_id": 10}, None, 1, 1)

        mock_log.assert_called_once()
        mock_db.commit.assert_called()

    def test_success_with_attributes(self, mock_db):
        from app.services.vehicle_service import update_vehicle

        vehicle = SimpleNamespace(
            id=1,
            is_deleted=False,
            company_id=1,
            id_value="ABC",
            assigned_driver_id=None,
        )
        sub = SimpleNamespace(level=2, parent_id=1)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return vehicle
            return sub

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None

        with (
            patch(
                "app.services.vehicle_service.clear_vehicle_attributes"
            ) as mock_clear,
            patch("app.services.vehicle_service.save_vehicle_attributes") as mock_save,
            patch(
                "app.services.vehicle_service.load_vehicle_with_relations"
            ) as mock_load,
            patch("app.services.vehicle_service.enrich_vehicle") as mock_enrich,
        ):
            mock_load.return_value = vehicle
            mock_enrich.return_value = {"id": 1}
            update_vehicle(
                mock_db,
                1,
                {"subcategory_id": 2},
                {"mass": "20"},
                1,
                1,
            )

        mock_clear.assert_called_once()
        mock_save.assert_called_once()
