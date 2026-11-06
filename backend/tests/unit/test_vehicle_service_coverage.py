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




class TestSaveVehicleAttributes:
    """Cover save_vehicle_attributes function (lines 20-95)."""

    def test_number_type_error_fallback(self, mock_db):
        """Cover line 35: TypeError/ValueError fallback to value_text."""
        from app.services.vehicle_service import save_vehicle_attributes
        attr_def = MagicMock()
        attr_def.id = 1
        attr_def.data_type = "number"
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def
        # Pass a value that can't be converted to float
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=10, attributes={"weight": "not_a_number"})
        mock_db.add.assert_called()

    def test_boolean_type(self, mock_db):
        """Cover boolean branch."""
        from app.services.vehicle_service import save_vehicle_attributes
        attr_def = MagicMock()
        attr_def.id = 1
        attr_def.data_type = "boolean"
        mock_db.query.return_value.filter.return_value.first.return_value = attr_def
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=10, attributes={"has_gps": "true"})
        mock_db.add.assert_called()

    def test_empty_attributes(self, mock_db):
        """Cover early return on empty attributes."""
        from app.services.vehicle_service import save_vehicle_attributes
        save_vehicle_attributes(mock_db, vehicle_id=1, subcategory_id=None, attributes=None)
        mock_db.add.assert_not_called()


class TestEnrichVehicle:
    """Cover enrich_vehicle function (lines 120-165)."""

    def test_category_level2_with_parent(self, mock_db):
        """Cover lines 58-59: category level 2 with parent."""
        from app.services.vehicle_service import enrich_vehicle
        vehicle = MagicMock()
        vehicle.category = MagicMock()
        vehicle.category.level = 2
        vehicle.category.name = "SubCat"
        vehicle.category.parent = MagicMock()
        vehicle.category.parent.name = "ParentCat"
        vehicle.attribute_values = []
        vehicle.assigned_driver_id = None

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] == "ParentCat"
        assert result["subcategory_name"] == "SubCat"

    def test_category_level1(self, mock_db):
        """Cover else branch: category not level 2."""
        from app.services.vehicle_service import enrich_vehicle
        vehicle = MagicMock()
        vehicle.category = MagicMock()
        vehicle.category.level = 1
        vehicle.category.name = "Excavators"
        vehicle.attribute_values = []
        vehicle.assigned_driver_id = None

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] == "Excavators"
        assert result["subcategory_name"] is None

    def test_no_category(self, mock_db):
        """Cover no category branch."""
        from app.services.vehicle_service import enrich_vehicle
        vehicle = MagicMock()
        vehicle.category = None
        vehicle.attribute_values = []
        vehicle.assigned_driver_id = None

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["category_name"] is None

    def test_attribute_values_with_definition(self, mock_db):
        """Cover lines 129-143: attribute values with definition."""
        from app.services.vehicle_service import enrich_vehicle
        av = MagicMock()
        av.attribute_definition = MagicMock()
        av.attribute_definition.slug = "weight"
        av.attribute_definition.name = "Weight"
        av.attribute_definition.data_type = "number"
        av.attribute_definition.unit = "kg"
        av.value_text = "5000"
        av.value_number = 5000.0
        av.value_boolean = None

        vehicle = MagicMock()
        vehicle.category = None
        vehicle.attribute_values = [av]
        vehicle.assigned_driver_id = None

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert len(result["attribute_values"]) == 1
        assert result["attribute_values"][0]["slug"] == "weight"

    def test_attribute_values_exception(self, mock_db):
        """Cover lines 162-163: except Exception continue."""
        from app.services.vehicle_service import enrich_vehicle
        bad_av = MagicMock()
        bad_av.attribute_definition = property(lambda self: (_ for _ in ()).throw(Exception("fail")))
        type(bad_av).attribute_definition = property(lambda self: (_ for _ in ()).throw(Exception("fail")))

        vehicle = MagicMock()
        vehicle.category = None
        vehicle.attribute_values = [bad_av]
        vehicle.assigned_driver_id = None

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["attribute_values"] == []

    def test_assigned_driver_name(self, mock_db):
        """Cover driver name lookup."""
        from app.services.vehicle_service import enrich_vehicle
        vehicle = MagicMock()
        vehicle.category = None
        vehicle.attribute_values = []
        vehicle.assigned_driver_id = 42

        emp = MagicMock()
        emp.contractor = MagicMock()
        emp.contractor.name = "Driver Ivan"
        mock_db.query.return_value.filter.return_value.first.return_value = emp

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["assigned_driver_name"] == "Driver Ivan"
        assert result["driver_name"] == "Driver Ivan"

    def test_driver_lookup_exception(self, mock_db):
        """Cover lines 162-163: except Exception pass in driver lookup."""
        from app.services.vehicle_service import enrich_vehicle
        vehicle = MagicMock()
        vehicle.category = None
        vehicle.attribute_values = []
        vehicle.assigned_driver_id = 42

        mock_db.query.return_value.filter.return_value.first.side_effect = Exception("DB error")

        with patch("app.services.vehicle_service.VehicleRead") as MockRead:
            MockRead.model_validate.return_value.model_dump.return_value = {
                "attribute_values": [], "id": 1,
            }
            result = enrich_vehicle(vehicle, mock_db)
        assert result["assigned_driver_name"] is None


class TestCreateVehicleExtraBranches:
    """Cover remaining create_vehicle branches."""

    def test_category_level1_from_payload(self, mock_db):
        """Cover lines 237-240: category_id from level 1 category."""
        from app.services.vehicle_service import create_vehicle
        cat = MagicMock()
        cat.level = 1
        # db.get calls: Category check for subcategory_id (None), then Category for category_id
        mock_db.get.side_effect = [cat]
        mock_db.query.return_value.filter.return_value.first.return_value = None  # no duplicate

        payload = {"name": "Test", "category_id": 5, "company_id": 7}
        with patch("app.services.vehicle_service.load_vehicle_with_relations") as mock_load,              patch("app.services.vehicle_service.enrich_vehicle") as mock_enrich,              patch("app.services.vehicle_service.save_vehicle_attributes"):
            mock_load.return_value = MagicMock()
            mock_enrich.return_value = {"id": 1}
            result = create_vehicle(mock_db, payload, company_id=7)
        mock_db.add.assert_called()

    def test_model_pop(self, mock_db):
        """Cover line 251: model -> model_name pop."""
        from app.services.vehicle_service import create_vehicle
        mock_db.get.return_value = None  # no subcategory
        mock_db.query.return_value.filter.return_value.first.return_value = None

        payload = {"name": "Test", "model": "KAMAZ-65115", "company_id": 7}
        with patch("app.services.vehicle_service.load_vehicle_with_relations") as mock_load,              patch("app.services.vehicle_service.enrich_vehicle") as mock_enrich,              patch("app.services.vehicle_service.save_vehicle_attributes"):
            mock_load.return_value = MagicMock()
            mock_enrich.return_value = {"id": 1}
            result = create_vehicle(mock_db, payload, company_id=7)
        mock_db.add.assert_called()

    def test_save_attributes_exception(self, mock_db):
        """Cover lines 261-264: save_vehicle_attributes raises exception."""
        from app.services.vehicle_service import create_vehicle, VehicleServiceError
        mock_db.get.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        payload = {"name": "Test", "company_id": 7, "attributes": {"weight": "5000"}}
        with patch("app.services.vehicle_service.load_vehicle_with_relations"),              patch("app.services.vehicle_service.enrich_vehicle"),              patch("app.services.vehicle_service.save_vehicle_attributes", side_effect=ValueError("bad attr")):
            with pytest.raises(VehicleServiceError, match="Attribute save error"):
                create_vehicle(mock_db, payload, company_id=7)
        mock_db.rollback.assert_called()


class TestUpdateVehicleExtraBranches:
    """Cover remaining update_vehicle branches."""

    def test_invalid_subcategory(self, mock_db):
        """Cover line 316: invalid subcategory in update."""
        from app.services.vehicle_service import update_vehicle, VehicleServiceError
        vehicle = MagicMock()
        vehicle.company_id = 7
        mock_db.get.side_effect = [vehicle, None]  # vehicle found, subcategory not found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(VehicleServiceError, match="Invalid subcategory"):
            update_vehicle(mock_db, vehicle_id=1, company_id=7, update_data={"subcategory_id": 999})
