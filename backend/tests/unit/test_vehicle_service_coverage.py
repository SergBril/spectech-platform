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
    """Cover save_vehicle_attributes function."""

    def test_number_type_error_fallback(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes
        attr_def = MagicMock()
        attr_def.id = 1
        attr_def.data_type = "number"
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=10, attributes={"weight": "not_a_number"})
        mock_db.add.assert_called()

    def test_boolean_type(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes
        attr_def = MagicMock()
        attr_def.id = 1
        attr_def.data_type = "boolean"
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=10, attributes={"has_gps": "true"})
        mock_db.add.assert_called()

    def test_empty_attributes(self, mock_db):
        from app.services.vehicle_service import save_vehicle_attributes
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=None, attributes=None)
        mock_db.add.assert_not_called()


class TestEnrichVehicle:
    """Cover enrich_vehicle - VehicleRead imported inside function."""

    def _make_vehicle(self, category=None, attr_values=None, driver_id=None):
        v = MagicMock()
        v.category = category
        v.attribute_values = attr_values or []
        v.assigned_driver_id = driver_id
        return v

    def test_category_level2_with_parent(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        cat = MagicMock()
        cat.level = 2
        cat.name = "SubCat"
        cat.parent = MagicMock()
        cat.parent.name = "ParentCat"
        vehicle = self._make_vehicle(category=cat)

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] == "ParentCat"
        assert result["subcategory_name"] == "SubCat"

    def test_category_level1(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        cat = MagicMock()
        cat.level = 1
        cat.name = "Excavators"
        vehicle = self._make_vehicle(category=cat)

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] == "Excavators"
        assert result["subcategory_name"] is None

    def test_no_category(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        vehicle = self._make_vehicle(category=None)

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] is None

    def test_attribute_values_with_definition(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        av = MagicMock()
        av.attribute_definition.slug = "weight"
        av.attribute_definition.name = "Weight"
        av.attribute_definition.data_type = "number"
        av.attribute_definition.unit = "kg"
        av.value_text = "5000"
        av.value_number = 5000.0
        av.value_boolean = None
        vehicle = self._make_vehicle(attr_values=[av])

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert len(result["attribute_values"]) == 1

    def test_attribute_values_exception_continue(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        bad_av = MagicMock(spec=[])
        vehicle = self._make_vehicle(attr_values=[bad_av])

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["attribute_values"] == []

    def test_assigned_driver_name(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        vehicle = self._make_vehicle(driver_id=42)
        emp = MagicMock()
        emp.contractor.name = "Driver Ivan"
        mock_db.query.return_value.filter.return_value.first.return_value = emp

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["assigned_driver_name"] == "Driver Ivan"

    def test_driver_lookup_exception(self, mock_db):
        from app.services.vehicle_service import enrich_vehicle
        vehicle = self._make_vehicle(driver_id=42)
        mock_db.query.return_value.filter.return_value.first.side_effect = Exception("DB error")

        with patch("app.schemas.vehicles.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {"attribute_values": [], "id": 1}
            result = enrich_vehicle(vehicle, mock_db)
        assert result["assigned_driver_name"] is None


class TestCreateVehicleExtraBranches:
    """Cover remaining create_vehicle branches."""

    def test_category_level1_from_payload(self, mock_db):
        from app.services.vehicle_service import create_vehicle
        cat = MagicMock()
        cat.level = 1
        # db.scalar for duplicate check -> None, db.get for category
        mock_db.scalar.return_value = None
        mock_db.get.return_value = cat

        payload = {"name": "Test", "category_id": 5}
        with patch("app.services.vehicle_service.load_vehicle_with_relations") as mock_load, \
             patch("app.services.vehicle_service.enrich_vehicle", return_value={"id": 1}), \
             patch("app.services.vehicle_service.save_vehicle_attributes"):
            mock_load.return_value = MagicMock()
            result = create_vehicle(mock_db, payload, company_id=7)
        mock_db.add.assert_called()

    def test_model_pop(self, mock_db):
        from app.services.vehicle_service import create_vehicle
        mock_db.scalar.return_value = None
        mock_db.get.return_value = None

        payload = {"name": "Test", "model": "KAMAZ-65115"}
        with patch("app.services.vehicle_service.load_vehicle_with_relations") as mock_load, \
             patch("app.services.vehicle_service.enrich_vehicle", return_value={"id": 1}), \
             patch("app.services.vehicle_service.save_vehicle_attributes"):
            mock_load.return_value = MagicMock()
            result = create_vehicle(mock_db, payload, company_id=7)
        mock_db.add.assert_called()

    def test_save_attributes_exception(self, mock_db):
        from app.services.vehicle_service import create_vehicle, VehicleServiceError
        mock_db.scalar.return_value = None
        mock_db.get.return_value = None

        payload = {"name": "Test", "attributes": {"weight": "5000"}}
        with patch("app.services.vehicle_service.load_vehicle_with_relations"), \
             patch("app.services.vehicle_service.enrich_vehicle"), \
             patch("app.services.vehicle_service.save_vehicle_attributes", side_effect=ValueError("bad")):
            with pytest.raises(VehicleServiceError, match="Attribute save error"):
                create_vehicle(mock_db, payload, company_id=7)
        mock_db.rollback.assert_called()


class TestUpdateVehicleExtraBranches:
    def test_invalid_subcategory(self, mock_db):
        from app.services.vehicle_service import update_vehicle, VehicleServiceError
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_deleted = False
        vehicle.assigned_driver_id = None
        mock_db.get.side_effect = [vehicle, None]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(VehicleServiceError, match="Invalid subcategory"):
            update_vehicle(mock_db, vehicle_id=1, update_data={"subcategory_id": 999},
                          attributes=None, company_id=7, user_id=1)
