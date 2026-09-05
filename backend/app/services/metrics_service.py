"""Простой сервис метрик в памяти (для разработки).
В продакшене заменить на Prometheus/Grafana."""

import time
from collections import defaultdict
from datetime import UTC, datetime

# Глобальное состояние метрик
_start_time = time.time()
_request_count = 0
_error_count = 0
_request_times = []
_endpoint_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0.0})


def record_request(endpoint: str, method: str, status_code: int, duration_ms: float):
    """Записывает метрику запроса."""
    global _request_count, _error_count
    _request_count += 1
    if status_code >= 500:
        _error_count += 1
    _request_times.append(duration_ms)
    # Храним только последние 1000 значений
    if len(_request_times) > 1000:
        _request_times.pop(0)

    key = f"{method} {endpoint}"
    _endpoint_stats[key]["count"] += 1
    if status_code >= 500:
        _endpoint_stats[key]["errors"] += 1
    _endpoint_stats[key]["total_time"] += duration_ms


def get_metrics() -> dict:
    """Возвращает сводку метрик."""
    uptime = time.time() - _start_time
    avg_time = sum(_request_times) / len(_request_times) if _request_times else 0

    # Топ-5 медленных эндпоинтов
    top_slow = sorted(
        _endpoint_stats.items(),
        key=lambda x: x[1]["total_time"] / x[1]["count"] if x[1]["count"] > 0 else 0,
        reverse=True,
    )[:5]

    return {
        "uptime_seconds": round(uptime, 2),
        "uptime_human": _format_uptime(uptime),
        "total_requests": _request_count,
        "error_count": _error_count,
        "error_rate_percent": (
            round(_error_count / _request_count * 100, 2) if _request_count > 0 else 0
        ),
        "avg_response_time_ms": round(avg_time, 2),
        "requests_last_1000_avg_ms": round(avg_time, 2),
        "top_slow_endpoints": [
            {
                "endpoint": k,
                "count": v["count"],
                "avg_ms": (
                    round(v["total_time"] / v["count"], 2) if v["count"] > 0 else 0
                ),
            }
            for k, v in top_slow
        ],
        "collected_at": datetime.now(UTC).isoformat(),
    }


def _format_uptime(seconds: float) -> str:
    """Форматирует аптайм в человекочитаемый вид."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    elif hours > 0:
        return f"{hours}ч {minutes}м {secs}с"
    else:
        return f"{minutes}м {secs}с"


def reset_metrics():
    """Сбрасывает метрики (для тестов)."""
    global _request_count, _error_count, _request_times, _endpoint_stats
    _request_count = 0
    _error_count = 0
    _request_times = []
    _endpoint_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0.0})
