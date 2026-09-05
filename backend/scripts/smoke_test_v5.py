"""Smoke-тест v5: полный workflow с обработкой ошибок."""

from datetime import UTC

import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


class SmokeTest:
    def __init__(self):
        self.token: str | None = None
        self.passed = 0
        self.failed = 0
        self.request_id = None

    def log(self, message: str, success: bool = True):
        prefix = "✅" if success else "❌"
        print(f"{prefix} {message}")
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def login(self):
        """Авторизация."""
        try:
            resp = requests.post(
                f"{API}/auth/login",
                json={"email": "admin@spectech.dev", "password": "admin123"},
            )
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
                self.log("Login successful")
                return True
            else:
                self.log(f"Login failed: {resp.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Login error: {e}", False)
            return False

    def test_validation_error(self):
        """Проверка красивых ошибок валидации."""
        try:
            resp = requests.post(
                f"{API}/auth/register",
                json={"email": "not-an-email", "password": "123", "full_name": "Test"},
            )
            if resp.status_code == 422:
                data = resp.json()
                if "error" in data and "details" in data:
                    self.log(
                        f"Validation error: {data['error']}, {len(data['details'])} field errors"
                    )
                    return
            self.log("Validation error format incorrect", False)
        except Exception as e:
            self.log(f"Validation error test failed: {e}", False)

    def test_system_metrics(self):
        """Проверка системных метрик."""
        try:
            resp = requests.get(f"{API}/system/metrics")
            if resp.status_code == 200:
                data = resp.json()
                if "uptime_seconds" in data and "total_requests" in data:
                    self.log(
                        f"Metrics: {data['total_requests']} requests, uptime {data['uptime_human']}"
                    )
                    return
            self.log("Metrics endpoint failed", False)
        except Exception as e:
            self.log(f"Metrics test failed: {e}", False)

    def test_telematics_workflow(self):
        """Полный цикл телематики."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # 1. Создаём правило
            resp = requests.post(
                f"{API}/telematics/rules/seed-defaults", headers=headers
            )
            if resp.status_code == 201:
                self.log("Default rules created")
            else:
                self.log(f"Seed rules failed: {resp.status_code}", False)
                return

            # 2. Создаём геозону
            resp = requests.post(
                f"{API}/telematics/geofences",
                headers=headers,
                json={
                    "name": "Test Zone",
                    "type": "circle",
                    "center_latitude": 55.7558,
                    "center_longitude": 37.6173,
                    "radius_meters": 500,
                },
            )
            if resp.status_code == 201:
                self.log("Geofence created")
            else:
                self.log(f"Geofence creation failed: {resp.status_code}", False)

            # 3. Отправляем GPS точку
            from datetime import datetime

            resp = requests.post(
                f"{API}/telematics/gps",
                headers=headers,
                json={
                    "points": [
                        {
                            "vehicle_id": 1,
                            "latitude": 55.7558,
                            "longitude": 37.6173,
                            "speed": 45.0,
                            "engine_on": True,
                            "fuel_level": 85.5,
                            "recorded_at": datetime.now(UTC).isoformat(),
                        }
                    ]
                },
            )
            if resp.status_code == 201:
                self.log("GPS point received")
            else:
                self.log(f"GPS point failed: {resp.status_code}", False)

            # 4. Проверяем дашборд
            resp = requests.get(f"{API}/telematics/dashboard", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                self.log(f"Dashboard: {data.get('vehicles_online', 0)} vehicles online")
            else:
                self.log(f"Dashboard failed: {resp.status_code}", False)

        except Exception as e:
            self.log(f"Telematics workflow failed: {e}", False)

    def run(self):
        """Запуск всех тестов."""
        print("=" * 60)
        print("🚀 SMOKE TEST V5 - Full Workflow with Error Handling")
        print("=" * 60)
        print()

        self.login()
        self.test_validation_error()
        self.test_system_metrics()
        self.test_telematics_workflow()

        print()
        print("=" * 60)
        total = self.passed + self.failed
        print(f"📊 Results: {self.passed}/{total} passed")
        if self.failed == 0:
            print("🎉 ALL CHECKS PASSED!")
        else:
            print(f"⚠️  {self.failed} checks failed")
        print("=" * 60)


if __name__ == "__main__":
    SmokeTest().run()
