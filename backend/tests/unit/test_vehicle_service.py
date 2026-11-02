import pytest
from unittest.mock import MagicMock, patch

from app.services.vehicle_service import (
    create_vehicle,
    update_vehicle,
    VehicleServiceError,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCreateVehicle:
    """Tests for create_vehicle"""

    def test_create_success(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.id = 42

        mock_db.scalar = MagicMock(return_value=None)  # No duplicate
        mock_db.get = MagicMock(return_value=None)  # No subcategory
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()

        with patch('app.services.vehicle_service.load_vehicle_with_relations') as mock_load, \
             patch('app.services.vehicle_service.enrich_vehicle') as mock_enrich, \
             patch('app.services.vehicle_service.save_vehicle_attributes'):
            mock_load.return_value = mock_vehicle
            mock_enrich.return_value = {"id": 42, "name": "CAT 320"}

            result = create_vehicle(
                db=mock_db,
                payload_data={"id_value": "V001", "name": "CAT 320", "attributes": None},
                company_id=7,
            )

        assert result["id"] == 42
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_duplicate_id_value(self, mock_db):
        mock_existing = MagicMock()
        mock_db.scalar = MagicMock(return_value=mock_existing)

        with pytest.raises(VehicleServiceError) as exc_info:
            create_vehicle(
                db=mock_db,
                payload_data={"id_value": "V001", "name": "Test"},
                company_id=7,
            )
        assert exc_info.value.status_code == 409

    def test_create_invalid_subcategory(self, mock_db):
        mock_db.scalar = MagicMock(return_value=None)
        mock_sub = MagicMock()
        mock_sub.level = 1  # Wrong level
        mock_db.get = MagicMock(return_value=mock_sub)

        with pytest.raises(VehicleServiceError) as exc_info:
            create_vehicle(
                db=mock_db,
                payload_data={"id_value": "V001", "subcategory_id": 5},
                company_id=7,
            )
        assert exc_info.value.status_code == 400

    def test_create_attribute_save_error(self, mock_db):
        mock_db.scalar = MagicMock(return_value=None)
        mock_db.get = MagicMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.rollback = MagicMock()

        with patch('app.services.vehicle_service.save_vehicle_attributes', side_effect=ValueError("bad attr")):
            with pytest.raises(VehicleServiceError) as exc_info:
                create_vehicle(
                    db=mock_db,
                    payload_data={"id_value": "V001", "attributes": {"bad": "data"}},
                    company_id=7,
                )
        assert exc_info.value.status_code == 400
        mock_db.rollback.assert_called_once()


class TestUpdateVehicle:
    """Tests for update_vehicle"""

    def test_update_success(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.is_deleted = False
        mock_vehicle.company_id = 7
        mock_vehicle.id_value = "V001"
        mock_vehicle.assigned_driver_id = None

        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalar = MagicMock(return_value=None)
        mock_db.commit = MagicMock()

        with patch('app.services.vehicle_service.load_vehicle_with_relations') as mock_load, \
             patch('app.services.vehicle_service.enrich_vehicle') as mock_enrich:
            mock_load.return_value = mock_vehicle
            mock_enrich.return_value = {"id": 1, "name": "Updated"}

            result = update_vehicle(
                db=mock_db, vehicle_id=1,
                update_data={"name": "Updated"},
                attributes=None, company_id=7, user_id=5,
            )

        assert result["name"] == "Updated"
        mock_db.commit.assert_called_once()

    def test_update_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(VehicleServiceError) as exc_info:
            update_vehicle(
                db=mock_db, vehicle_id=999,
                update_data={"name": "Test"},
                attributes=None, company_id=7, user_id=5,
            )
        assert exc_info.value.status_code == 404

    def test_update_wrong_company(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.is_deleted = False
        mock_vehicle.company_id = 99  # Different company

        mock_db.get = MagicMock(return_value=mock_vehicle)

        with pytest.raises(VehicleServiceError) as exc_info:
            update_vehicle(
                db=mock_db, vehicle_id=1,
                update_data={"name": "Test"},
                attributes=None, company_id=7, user_id=5,
            )
        assert exc_info.value.status_code == 404

    def test_update_duplicate_id_value(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.is_deleted = False
        mock_vehicle.company_id = 7
        mock_vehicle.id_value = "V001"
        mock_vehicle.assigned_driver_id = None

        mock_existing = MagicMock()
        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalar = MagicMock(return_value=mock_existing)

        with pytest.raises(VehicleServiceError) as exc_info:
            update_vehicle(
                db=mock_db, vehicle_id=1,
                update_data={"id_value": "V002"},
                attributes=None, company_id=7, user_id=5,
            )
        assert exc_info.value.status_code == 409

    def test_update_driver_uniqueness(self, mock_db):
        mock_vehicle = MagicMock()
        mock_vehicle.is_deleted = False
        mock_vehicle.company_id = 7
        mock_vehicle.id_value = "V001"
        mock_vehicle.assigned_driver_id = None

        mock_db.get = MagicMock(return_value=mock_vehicle)
        mock_db.scalar = MagicMock(return_value=None)
        mock_db.commit = MagicMock()
        mock_query = MagicMock()
        mock_db.query = MagicMock(return_value=mock_query)
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.update = MagicMock()

        with patch('app.services.vehicle_service.load_vehicle_with_relations') as mock_load, \
             patch('app.services.vehicle_service.enrich_vehicle') as mock_enrich, \
             patch('app.services.vehicle_service.log_driver_assignment'):
            mock_load.return_value = mock_vehicle
            mock_enrich.return_value = {"id": 1}

            update_vehicle(
                db=mock_db, vehicle_id=1,
                update_data={"assigned_driver_id": 42},
                attributes=None, company_id=7, user_id=5,
            )

        mock_query.update.assert_called_once()
