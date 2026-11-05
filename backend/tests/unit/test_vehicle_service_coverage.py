"""Tests for vehicle_service functions."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestSaveVehicleAttributes:
    """Cover save_vehicle_attributes (lines 20-72)."""

    def test_no_attributes_returns(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        save_vehicle_attributes(mock_db, 1, 1, None)
        mock_db.add.assert_not_called()

    def test_no_subcategory_returns(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        save_vehicle_attributes(mock_db, 1, None, {"slug": "val"})
        mock_db.add.assert_not_called()

    def test_skips_empty_values(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        save_vehicle_attributes(mock_db, 1, 1, {"slug": "", "slug2": None})
        mock_db.add.assert_not_called()

    def test_number_attribute(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=10, data_type="number", slug="weight")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = attr_def
        mock_db.query.return_value = mock_query

        save_vehicle_attributes(mock_db, 1, 1, {"weight": "150.5"})
        mock_db.add.assert_called_once()

    def test_boolean_attribute(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=10, data_type="boolean", slug="has_gps")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = attr_def
        mock_db.query.return_value = mock_query

        save_vehicle_attributes(mock_db, 1, 1, {"has_gps": True})
        mock_db.add.assert_called_once()

    def test_select_attribute_with_option(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        attr_def = SimpleNamespace(id=10, data_type="select", slug="color")
        option = SimpleNamespace(id=20)

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.filter.return_value.first.return_value = attr_def
            else:
                mq.filter.return_value.first.return_value = option
            return mq

        mock_db.query.side_effect = mock_query

        save_vehicle_attributes(mock_db, 1, 1, {"color": "red"})
        mock_db.add.assert_called_once()

    def test_unknown_slug_skipped(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        save_vehicle_attributes(mock_db, 1, 1, {"unknown": "val"})
        mock_db.add.assert_not_called()


class TestLoadVehicleWithRelations:
    """Cover load_vehicle_with_relations (lines 73-90)."""

    def test_returns_vehicle(self, mock_db):
        from app.services.vehicle_service import load_vehicle_with_relations

        vehicle = SimpleNamespace(id=1)
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = vehicle
        mock_db.query.return_value = mock_query

        load_vehicle_with_relations(mock_db, 1)
        assert result == vehicle


class TestEnrichVehicle:
    """Cover enrich_vehicle (lines 97-161)."""

    def test_basic_enrichment(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle

        category = SimpleNamespace(
            name="Экскаваторы", level=2, parent=SimpleNamespace(name="Спецтехника")
        )
        attr_def = SimpleNamespace(
            slug="weight", name="Вес", data_type="number", unit="т"
        )
        attr_val = SimpleNamespace(
            attribute_definition=attr_def,
            value_text="15",
            value_number=15.0,
            value_boolean=None,
        )
        vehicle = SimpleNamespace(
            category=category,
            attribute_values=[attr_val],
            assigned_driver_id=None,
            id=1,
            name="CAT 320",
            company_id=1,
            is_deleted=False,
        )

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            mock_dump = {"id": 1, "name": "CAT 320", "attribute_values": []}
            MockRead.model_validate.return_value.model_dump.return_value = mock_dump
            enrich_vehicle(vehicle, mock_db)

        assert result["category_name"] == "Спецтехника"
        assert result["subcategory_name"] == "Экскаваторы"
        assert len(result["attribute_values"]) == 1

    def test_no_category(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle

        vehicle = SimpleNamespace(
            category=None, attribute_values=[], assigned_driver_id=None
        )

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": []
            }
            enrich_vehicle(vehicle, mock_db)

        assert result["category_name"] is None

    def test_with_driver(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle

        emp = SimpleNamespace(contractor=SimpleNamespace(name="Иванов"))
        vehicle = SimpleNamespace(
            category=None, attribute_values=[], assigned_driver_id=5
        )
        mock_db.query.return_value.filter.return_value.first.return_value = emp

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": []
            }
            enrich_vehicle(vehicle, mock_db)

        assert result["driver_name"] == "Иванов"


class TestLogDriverAssignment:
    """Cover log_driver_assignment (lines 162-195)."""

    def test_closes_old_and_creates_new(self, mock_db):
        from app.services.vehicle_service import log_driver_assignment

        old_log = SimpleNamespace(unassigned_at=None)
        mock_db.query.return_value.filter.return_value.first.return_value = old_log

        log_driver_assignment(mock_db, 1, old_driver_id=10, new_driver_id=20, user_id=5)

        assert old_log.unassigned_at is not None
        mock_db.add.assert_called_once()

    def test_no_change(self, mock_db):
        from app.services.vehicle_service import log_driver_assignment

        log_driver_assignment(mock_db, 1, old_driver_id=10, new_driver_id=10, user_id=5)
        mock_db.add.assert_not_called()


class TestClearVehicleAttributes:
    """Cover clear_vehicle_attributes (lines 196-202)."""

    def test_deletes(self, mock_db):
        from app.services.vehicle_service import clear_vehicle_attributes

        clear_vehicle_attributes(mock_db, 1)
        mock_db.query.return_value.filter.return_value.delete.assert_called_once()


class TestCreateVehicle:
    """Cover create_vehicle (lines 203-259)."""

    def test_duplicate_id_value_raises(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, create_vehicle

        mock_db.scalar.return_value = SimpleNamespace(id=1)

        with pytest.raises(VehicleServiceError) as exc_info:
            create_vehicle(mock_db, {"id_value": "ABC123"}, company_id=1)
        assert exc_info.value.status_code == 409

    def test_invalid_subcategory_raises(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, create_vehicle

        mock_db.scalar.return_value = None
        mock_db.get.return_value = SimpleNamespace(level=1)  # Not level 2

        with pytest.raises(VehicleServiceError) as exc_info:
            create_vehicle(mock_db, {"subcategory_id": 5}, company_id=1)
        assert exc_info.value.status_code == 400

    def test_success(self, mock_db):
        from app.services.vehicle_service import create_vehicle

        sub = SimpleNamespace(level=2, parent_id=1)
        mock_db.scalar.return_value = None
        mock_db.get.return_value = sub
        vehicle = SimpleNamespace(id=1)

        with (
            patch("app.services.vehicle_service.save_vehicle_attributes"),
            patch(
                "app.services.vehicle_service.load_vehicle_with_relations",
                return_value=vehicle,
            ),
            patch(
                "app.services.vehicle_service.enrich_vehicle", return_value={"id": 1}
            ),
        ):
            create_vehicle(mock_db, {"subcategory_id": 5, "name": "Test"}, company_id=1)

        assert result["id"] == 1
        mock_db.commit.assert_called_once()


class TestUpdateVehicle:
    """Cover update_vehicle (lines 260-end)."""

    def test_not_found_raises(self, mock_db):
        from app.services.vehicle_service import VehicleServiceError, update_vehicle

        mock_db.get.return_value = None

        with pytest.raises(VehicleServiceError) as exc_info:
            update_vehicle(mock_db, 999, {}, None, company_id=1, user_id=1)
        assert exc_info.value.status_code == 404

    def test_success_with_driver_change(self, mock_db):
        from app.services.vehicle_service import update_vehicle

        vehicle = SimpleNamespace(
            id=1, is_deleted=False, company_id=1, assigned_driver_id=10, id_value="OLD"
        )
        mock_db.get.return_value = vehicle
        mock_db.scalar.return_value = None  # No duplicate

        with (
            patch("app.services.vehicle_service.log_driver_assignment") as mock_log,
            patch(
                "app.services.vehicle_service.load_vehicle_with_relations",
                return_value=vehicle,
            ),
            patch(
                "app.services.vehicle_service.enrich_vehicle", return_value={"id": 1}
            ),
        ):
            update_vehicle(
                mock_db, 1, {"assigned_driver_id": 20}, None, company_id=1, user_id=5
            )

        mock_log.assert_called_once_with(mock_db, 1, 10, 20, 5)
        mock_db.commit.assert_called_once()
