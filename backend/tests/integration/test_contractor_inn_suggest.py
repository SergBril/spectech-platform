"""Tests for contractor INN suggestion endpoint."""

import pytest
from fastapi.testclient import TestClient


class TestSuggestContractorByINN:
    """Tests for POST /api/v1/contractors/suggest-inn."""

    def test_suggest_inn_empty(self, client: TestClient, auth_headers: dict):
        """Empty INN should return 400."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={"inn": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_suggest_inn_missing_field(self, client: TestClient, auth_headers: dict):
        """Missing inn field should return 400 or 422."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)

    def test_suggest_inn_existing_contractor(
        self, client: TestClient, auth_headers: dict, db_session, company
    ):
        """Should detect duplicate contractor by INN."""
        from app.models.contractor import Contractor

        contractor = Contractor(
            name="Тестовый контрагент",
            inn="7707083893",
            type="legal_entity",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.commit()

        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={"inn": "7707083893"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["duplicate"] is True
        assert data["existing_name"] == "Тестовый контрагент"

    def test_suggest_inn_not_found(self, client: TestClient, auth_headers: dict):
        """Non-existent INN should return found=false."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={"inn": "0000000000"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is False
        assert data["duplicate"] is False

    def test_suggest_inn_unauthorized(self, client: TestClient):
        """Should require authentication."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={"inn": "7707083893"},
        )
        assert resp.status_code == 401
