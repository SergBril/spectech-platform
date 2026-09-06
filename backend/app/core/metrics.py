"""Prometheus metrics for SpectechPlatform."""

from prometheus_client import Counter, Gauge
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
)

requests_pending = Gauge(
    "spectech_requests_pending",
    "Number of pending requests",
)

alerts_active = Gauge(
    "spectech_alerts_active",
    "Number of active alerts",
    ["severity"],
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


def setup_metrics(app):
    """Configure Prometheus metrics for FastAPI application."""
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/health", "/ready"],
        env_var_name="ENABLE_METRICS",
    )

    # Add default metrics (request count, latency, etc)
    instrumentator.instrument(app).expose(
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
