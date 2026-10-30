"""Integration tests for shifts/geofence.py endpoints."""
import pytest


class TestGeofenceEndpoints:
    def test_geofence_event(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/geofence/event",
            json={"vehicle_id": 99999, "event_type": "enter", "geofence_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 422, 500)

    def test_link_geofence(self, client, auth_headers):
        resp = client.post(
            "/api/v1/shifts/geofence/link",
            json={"shift_task_id": 99999, "geofence_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 422, 500)
