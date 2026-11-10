"""Locust load test scenarios for SpectechPlatform API."""

import random
from locust import HttpUser, task, between, events


class SpectechUser(HttpUser):
    """Simulates a regular platform user."""
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Login and get auth token."""
        self.token = None
        self.company_id = None
        try:
            resp = self.client.post("/api/v1/auth/login", json={
                "email": "admin@spectech.dev",
                "password": "admin123",
            })
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.company_id = data.get("company_id", 7)
        except Exception:
            pass

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.company_id:
            h["X-Company-Id"] = str(self.company_id)
        return h

    @task(5)
    def health_check(self):
        self.client.get("/api/v1/system/health", name="/system/health")

    @task(3)
    def get_dashboard(self):
        self.client.get("/api/v1/analytics/revenue-chart", headers=self._headers(), name="/analytics/revenue-chart")

    @task(3)
    def get_sparkline(self):
        self.client.get("/api/v1/analytics/sparkline?days=7", headers=self._headers(), name="/analytics/sparkline")

    @task(4)
    def list_vehicles(self):
        self.client.get("/api/v1/vehicles/?limit=20", headers=self._headers(), name="/vehicles/")

    @task(3)
    def list_requests(self):
        self.client.get("/api/v1/marketplace/requests?limit=20", headers=self._headers(), name="/marketplace/requests")

    @task(2)
    def list_invoices(self):
        self.client.get("/api/v1/finance/invoices?limit=20", headers=self._headers(), name="/finance/invoices")

    @task(2)
    def list_maintenance(self):
        self.client.get("/api/v1/maintenance/orders?limit=20", headers=self._headers(), name="/maintenance/orders")

    @task(1)
    def status_chart(self):
        self.client.get("/api/v1/analytics/status-chart", headers=self._headers(), name="/analytics/status-chart")

    @task(1)
    def top_requests(self):
        self.client.get("/api/v1/analytics/top-requests?limit=5", headers=self._headers(), name="/analytics/top-requests")


class HeavyUser(HttpUser):
    """Simulates heavy operations (exports, reports)."""
    wait_time = between(3, 8)
    host = "http://localhost:8000"

    def on_start(self):
        self.token = None
        self.company_id = None
        try:
            resp = self.client.post("/api/v1/auth/login", json={
                "email": "admin@spectech.dev",
                "password": "admin123",
            })
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.company_id = data.get("company_id", 7)
        except Exception:
            pass

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.company_id:
            h["X-Company-Id"] = str(self.company_id)
        return h

    @task(2)
    def revenue_chart_24m(self):
        self.client.get("/api/v1/analytics/revenue-chart?months=24", headers=self._headers(), name="/analytics/revenue-chart[24m]")

    @task(1)
    def sparkline_30d(self):
        self.client.get("/api/v1/analytics/sparkline?days=30", headers=self._headers(), name="/analytics/sparkline[30d]")

    @task(1)
    def list_all_vehicles(self):
        self.client.get("/api/v1/vehicles/?limit=100", headers=self._headers(), name="/vehicles/[100]")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n🚀 Load test started")
    print(f"   Target: {environment.host}")
    print(f"   Users: {environment.runner.target_user_count}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.runner.stats
    total = stats.total
    print(f"\n📊 Results: {total.num_requests} requests, "
          f"{total.fail_ratio*100:.1f}% failures, "
          f"avg {total.avg_response_time:.0f}ms, "
          f"p95 {total.get_response_time_percentile(0.95):.0f}ms")
