"""GPS config: secrets stay server-side, and editing must not destroy data.

Two real defects, both verified before fixing:
  * GET /gps/providers/vehicles returned the provider password in plain JSON,
    so any employee of the company could read it.
  * PATCH replaced the whole config, while the admin page sends only
    login/password/api_url - object_ids were silently erased on every edit,
    breaking the provider mapping while the UI reported success.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle

pytestmark = [pytest.mark.integration]

CONFIG = {
    "login": "fleet",
    "password": "super-secret",
    "api_url": "https://gps.mapix.su",
    "object_ids": ["12345", "67890"],
}


@pytest.fixture
def gps_vehicle(db_session: Session, sample_vehicle: Vehicle) -> Vehicle:
    """Своя техника с заполненным GPS-конфигом, включая секрет и маппинг."""
    sample_vehicle.gps_provider = "mapix"
    sample_vehicle.gps_provider_config = dict(CONFIG)
    db_session.commit()
    db_session.refresh(sample_vehicle)
    return sample_vehicle


def _patch(client: TestClient, headers: dict, vehicle_id: int, config: dict):
    return client.patch(
        f"/api/v1/gps/providers/vehicles/{vehicle_id}",
        headers=headers,
        json={"gps_provider_config": config},
    )


class TestSecretsNeverLeaveTheServer:
    def test_list_does_not_return_the_password(
        self, client: TestClient, auth_headers, gps_vehicle
    ):
        r = client.get("/api/v1/gps/providers/vehicles", headers=auth_headers)
        assert r.status_code == 200
        row = next(v for v in r.json() if v["id"] == gps_vehicle.id)
        cfg = row["gps_provider_config"]
        assert "password" not in cfg
        assert "super-secret" not in r.text
        assert cfg["password_set"] is True
        assert cfg["login"] == "fleet"
        assert cfg["object_ids"] == ["12345", "67890"]

    def test_patch_response_does_not_echo_the_password(
        self, client: TestClient, auth_headers, gps_vehicle
    ):
        r = _patch(client, auth_headers, gps_vehicle.id, {"password": "new-secret"})
        assert r.status_code == 200
        assert "new-secret" not in r.text
        assert r.json()["gps_provider_config"]["password_set"] is True


class TestEditingPreservesData:
    def test_object_ids_survive_a_login_only_edit(
        self, client: TestClient, auth_headers, gps_vehicle, db_session
    ):
        r = _patch(client, auth_headers, gps_vehicle.id, {"login": "changed"})
        assert r.status_code == 200
        db_session.refresh(gps_vehicle)
        assert gps_vehicle.gps_provider_config["object_ids"] == ["12345", "67890"]
        assert gps_vehicle.gps_provider_config["login"] == "changed"

    def test_empty_password_does_not_erase_the_stored_one(
        self, client: TestClient, auth_headers, gps_vehicle, db_session
    ):
        r = _patch(
            client, auth_headers, gps_vehicle.id, {"login": "fleet", "password": ""}
        )
        assert r.status_code == 200
        db_session.refresh(gps_vehicle)
        assert gps_vehicle.gps_provider_config["password"] == "super-secret"

    def test_absent_password_keeps_the_stored_one(
        self, client: TestClient, auth_headers, gps_vehicle, db_session
    ):
        _patch(client, auth_headers, gps_vehicle.id, {"api_url": "https://new"})
        db_session.refresh(gps_vehicle)
        assert gps_vehicle.gps_provider_config["password"] == "super-secret"

    def test_explicit_new_password_replaces_the_old(
        self, client: TestClient, auth_headers, gps_vehicle, db_session
    ):
        _patch(client, auth_headers, gps_vehicle.id, {"password": "rotated"})
        db_session.refresh(gps_vehicle)
        assert gps_vehicle.gps_provider_config["password"] == "rotated"
