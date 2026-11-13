"""Integration tests for shifts/geofence.py endpoints.

Loose-assert'ы сужены до конкретных кодов. auth_headers = admin (superuser).
"""


class TestGeofenceEndpoints:
    def test_geofence_event(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/geofence/event",
            json={"vehicle_id": 99999, "event_type": "enter", "geofence_id": 1},
            headers=auth_headers,
        )
        # 422: валидация тела раньше поиска техники
        assert resp.status_code == 422

    def test_link_geofence(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/geofence/link",
            json={"shift_task_id": 99999, "geofence_id": 1},
            headers=auth_headers,
        )
        # 422: валидация тела раньше поиска смены
        assert resp.status_code == 422
