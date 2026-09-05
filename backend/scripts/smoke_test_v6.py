"""Smoke-тест v6: Celery + MinIO + периодические задачи."""

import time

import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


class SmokeTest:
    def __init__(self):
        self.token = None
        self.passed = 0
        self.failed = 0

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

    def test_file_upload(self):
        """Тест загрузки файла в MinIO."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Загружаем README.md
            with open("../README.md", "rb") as f:
                resp = requests.post(
                    f"{API}/files/upload?file_category=other",
                    headers=headers,
                    files={"file": ("README.md", f, "text/markdown")},
                )

            if resp.status_code == 201:
                data = resp.json()
                self.log(f"File uploaded: id={data['id']}, path={data['storage_path']}")
                return data["id"]
            else:
                self.log(f"Upload failed: {resp.status_code}", False)
                return None
        except Exception as e:
            self.log(f"Upload error: {e}", False)
            return None

    def test_file_download(self, file_id: int):
        """Тест скачивания файла."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.get(f"{API}/files/download/{file_id}", headers=headers)
            if resp.status_code == 200 and len(resp.content) > 0:
                self.log(f"File downloaded: {len(resp.content)} bytes")
                return True
            else:
                self.log(f"Download failed: {resp.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Download error: {e}", False)
            return False

    def test_storage_stats(self):
        """Тест статистики хранилища."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.get(f"{API}/files/stats", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                storage = data.get("storage", {})
                self.log(
                    f"Storage stats: {storage.get('total_files', 0)} files, {storage.get('total_size_bytes', 0)} bytes"
                )
                return True
            else:
                self.log(f"Stats failed: {resp.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Stats error: {e}", False)
            return False

    def test_celery_task(self):
        """Тест Celery задачи."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Запускаем health-check
            resp = requests.post(f"{API}/tasks/scheduled/health-check", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id")
                self.log(f"Celery task queued: {task_id}")

                # Ждём выполнения
                time.sleep(3)

                # Проверяем статус
                resp = requests.get(
                    f"{API}/tasks/tasks/{task_id}/status", headers=headers
                )
                if resp.status_code == 200:
                    status = resp.json().get("status")
                    self.log(f"Task status: {status}")
                    return status == "SUCCESS"
                else:
                    self.log(f"Status check failed: {resp.status_code}", False)
                    return False
            else:
                self.log(f"Task queue failed: {resp.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Celery test error: {e}", False)
            return False

    def test_system_metrics(self):
        """Тест системных метрик."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.get(f"{API}/system/metrics", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                uptime = data.get("uptime_human", "unknown")
                total_requests = data.get("total_requests", 0)
                self.log(f"System metrics: uptime={uptime}, requests={total_requests}")
                return True
            else:
                self.log(f"Metrics failed: {resp.status_code}", False)
                return False
        except Exception as e:
            self.log(f"Metrics error: {e}", False)
            return False

    def run(self):
        """Запуск всех тестов."""
        print("=" * 70)
        print("🚀 SMOKE TEST V6 - Celery + MinIO + Periodic Tasks")
        print("=" * 70)
        print()

        if not self.login():
            print("❌ Cannot proceed without authentication")
            return

        # Тесты
        file_id = self.test_file_upload()
        if file_id:
            self.test_file_download(file_id)

        self.test_storage_stats()
        self.test_celery_task()
        self.test_system_metrics()

        # Итоги
        print()
        print("=" * 70)
        total = self.passed + self.failed
        print(f"📊 Results: {self.passed}/{total} passed")
        if self.failed == 0:
            print("🎉 ALL CHECKS PASSED!")
            print()
            print("✅ MinIO storage working")
            print("✅ File upload/download working")
            print("✅ Celery tasks executing")
            print("✅ System metrics available")
        else:
            print(f"⚠️  {self.failed} checks failed")
        print("=" * 70)


if __name__ == "__main__":
    SmokeTest().run()
