"""Integration tests for shifts/bank.py endpoints."""
import pytest


class TestBankEndpoints:
    def test_export_transactions(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/bank/transactions/export", headers=auth_headers)
        assert resp.status_code == 200

    def test_unpaid_acts(self, client, auth_headers):
        resp = client.get("/api/v1/shifts/acts/unpaid", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
