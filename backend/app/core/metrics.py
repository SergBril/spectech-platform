"""Prometheus metrics for SpectechPlatform."""

import os

# При 4 воркерах uvicorn у каждого процесса свой реестр: планировщик живёт в
# одном (advisory lock в Postgres), а скрейп /metrics попадает в случайный.
# Из-за этого гейджи показывали 0 при 15 машинах, а http_requests_total -
# трафик одного воркера. Multiprocess-режим собирает метрики всех процессов.
#
# Режимы live (livemax/livesum) учитывают только живые PID, поэтому файлы
# умерших воркеров не искажают значения и чистка каталога не требуется.
_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "")
if _MULTIPROC_DIR:
    os.makedirs(_MULTIPROC_DIR, exist_ok=True)

from prometheus_client import REGISTRY, Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# ═══════════════════════════════════════════════════════════════
# Custom Business Metrics
# ═══════════════════════════════════════════════════════════════

# Authentication metrics
auth_attempts_total = Counter(
    "spectech_auth_attempts_total",
    "Total authentication attempts",
    ["status", "endpoint"],
)

auth_failures_total = Counter(
    "spectech_auth_failures_total",
    "Total authentication failures by reason",
    ["reason"],
)

# Business metrics
vehicles_active = Gauge(
    "spectech_vehicles_active",
    "Number of active vehicles",
    multiprocess_mode="livemax",
)

requests_pending = Gauge(
    "spectech_requests_pending",
    "Number of pending requests",
    multiprocess_mode="livemax",
)

alerts_active = Gauge(
    "spectech_alerts_active",
    "Number of active alerts",
    ["severity"],
    multiprocess_mode="livemax",
)

telematics_events_total = Counter(
    "spectech_telematics_events_total",
    "Total telematics events processed",
    ["event_type"],
)

# Database metrics
db_connections_active = Gauge(
    "spectech_db_connections_active",
    "Number of active database connections",
    multiprocess_mode="livesum",
)

# Cache metrics
cache_hits_total = Counter(
    "spectech_cache_hits_total",
    "Total cache hits",
    ["cache_name"],
)

cache_misses_total = Counter(
    "spectech_cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)


# ═══════════════════════════════════════════════════════════════
# Prometheus Instrumentator Setup
# ═══════════════════════════════════════════════════════════════


scheduler_job_failures_total = Counter(
    "scheduler_job_failures_total",
    "Провалы задач планировщика по job_id",
    ["job_id"],
)

scheduler_job_missed_total = Counter(
    "scheduler_job_missed_total",
    "Задачи планировщика, пропустившие своё время запуска",
    ["job_id"],
)


def setup_metrics(app):
    """Configure Prometheus metrics for FastAPI application."""
    registry = REGISTRY
    if _MULTIPROC_DIR:
        from prometheus_client import CollectorRegistry, ProcessCollector
        from prometheus_client.multiprocess import MultiProcessCollector

        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        # Процессные метрики не входят в multiprocess-сборку. Регистрируем
        # отдельно, иначе панели памяти и CPU опустеют. Значения отражают
        # тот воркер, который обслужил скрейп.
        ProcessCollector(registry=registry)

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/health", "/ready"],
        env_var_name="ENABLE_METRICS",
        registry=registry,
    )

    instrumentator.instrument(app)

    if _MULTIPROC_DIR:
        # expose() в instrumentator 7.0 при наличии PROMETHEUS_MULTIPROC_DIR
        # строит СВОЙ реестр только с MultiProcessCollector, игнорируя
        # переданный. Процессные метрики при этом теряются: панели памяти и
        # CPU пустели. Поэтому эндпоинт отдаём сами из своего реестра.
        from fastapi import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @app.get("/metrics", include_in_schema=False)
        def _metrics_endpoint() -> Response:
            return Response(
                content=generate_latest(registry),
                media_type=CONTENT_TYPE_LATEST,
            )

    else:
        instrumentator.expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
            should_gzip=True,
        )

    return instrumentator


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════


def record_auth_attempt(status: str, endpoint: str = "unknown"):
    """Record an authentication attempt."""
    auth_attempts_total.labels(status=status, endpoint=endpoint).inc()


def record_auth_failure(reason: str):
    """Record an authentication failure."""
    auth_failures_total.labels(reason=reason).inc()


def record_telematics_event(event_type: str):
    """Record a telematics event."""
    telematics_events_total.labels(event_type=event_type).inc()


def record_cache_hit(cache_name: str = "default"):
    """Record a cache hit."""
    cache_hits_total.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str = "default"):
    """Record a cache miss."""
    cache_misses_total.labels(cache_name=cache_name).inc()


def set_active_vehicles(count: int):
    """Set the number of active vehicles."""
    vehicles_active.set(count)


def set_pending_requests(count: int):
    """Set the number of pending requests."""
    requests_pending.set(count)


def set_active_alerts(severity: str, count: int):
    """Set the number of active alerts by severity."""
    alerts_active.labels(severity=severity).set(count)
