"""Locust load tests for SpectechPlatform."""

from locust import HttpUser, task, between, tag


class SpectechUser(HttpUser):
    """Базовый пользователь SpectechPlatform."""

    wait_time = between(0.5, 2)  # Пауза между запросами 0.5-2 сек

    def on_start(self):
        """Инициализация: логин и получение токена."""
        # Для простоты используем анонимные endpoints
        # В реальности здесь был бы логин
        self.token = None

    # ═══════════════════════════════════════════════════════════════
    # System Endpoints (лёгкие)
    # ═══════════════════════════════════════════════════════════════

    @task(10)  # Вес 10 — выполняется чаще
    @tag("system", "health")
    def health_check(self):
        """Проверка health endpoint."""
        with self.client.get(
            "/api/v1/system/health", catch_response=True, name="/api/v1/system/health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")

    # ═══════════════════════════════════════════════════════════════
    # Benchmark Endpoints (средние)
    # ═══════════════════════════════════════════════════════════════

    @task(5)
    @tag("benchmark", "fast")
    def benchmark_fast(self):
        """Быстрый benchmark endpoint."""
        self.client.get("/api/v1/benchmark/fast", name="/api/v1/benchmark/fast")

    @task(3)
    @tag("benchmark", "cpu")
    def benchmark_cpu(self):
        """CPU-intensive benchmark."""
        self.client.get("/api/v1/benchmark/cpu", name="/api/v1/benchmark/cpu")

    @task(2)
    @tag("benchmark", "memory")
    def benchmark_memory(self):
        """Memory-intensive benchmark."""
        self.client.get("/api/v1/benchmark/memory", name="/api/v1/benchmark/memory")

    # ═══════════════════════════════════════════════════════════════
    # API Documentation (тяжёлые)
    # ═══════════════════════════════════════════════════════════════

    @task(1)
    @tag("docs")
    def openapi_json(self):
        """Получение OpenAPI спецификации."""
        self.client.get("/api/v1/openapi.json", name="/api/v1/openapi.json")


class HeavyLoadUser(HttpUser):
    """Пользователь для тяжёлой нагрузки."""

    wait_time = between(0.1, 0.5)  # Быстрее — 0.1-0.5 сек
    weight = 1  # Меньше пользователей этого типа

    @task
    @tag("heavy")
    def rapid_health_checks(self):
        """Быстрые health checks для стресс-теста."""
        self.client.get("/api/v1/system/health", name="/heavy/health")
