"""Coverage tests for metrics_service."""

import pytest


@pytest.fixture(autouse=True)
def reset():
    from app.services.metrics_service import reset_metrics

    reset_metrics()
    yield
    reset_metrics()


class TestRecordRequest:
    """Cover record_request (lines 16-32)."""

    def test_normal_request(self):
        from app.services.metrics_service import get_metrics, record_request

        record_request("/api/vehicles", "GET", 200, 50.0)
        m = get_metrics()
        assert m["total_requests"] == 1
        assert m["error_count"] == 0

    def test_error_request(self):
        from app.services.metrics_service import get_metrics, record_request

        record_request("/api/vehicles", "GET", 500, 100.0)
        m = get_metrics()
        assert m["error_count"] == 1
        assert m["error_rate_percent"] == 100.0

    def test_trims_to_1000(self):
        from app.services import metrics_service
        from app.services.metrics_service import record_request

        for i in range(1005):
            record_request("/api/test", "GET", 200, 10.0)
        assert len(metrics_service._request_times) == 1000

    def test_endpoint_stats(self):
        from app.services.metrics_service import get_metrics, record_request

        record_request("/api/a", "GET", 200, 10.0)
        record_request("/api/b", "POST", 200, 200.0)
        m = get_metrics()
        assert len(m["top_slow_endpoints"]) == 2
        assert m["top_slow_endpoints"][0]["endpoint"] == "POST /api/b"


class TestGetMetrics:
    """Cover get_metrics (lines 34-68)."""

    def test_empty_metrics(self):
        from app.services.metrics_service import get_metrics

        m = get_metrics()
        assert m["total_requests"] == 0
        assert m["avg_response_time_ms"] == 0
        assert m["error_rate_percent"] == 0
        assert "uptime_seconds" in m
        assert "collected_at" in m

    def test_with_data(self):
        from app.services.metrics_service import get_metrics, record_request

        record_request("/api/x", "GET", 200, 50.0)
        record_request("/api/x", "GET", 200, 150.0)
        m = get_metrics()
        assert m["total_requests"] == 2
        assert m["avg_response_time_ms"] == 100.0


class TestFormatUptime:
    """Cover _format_uptime (lines 70-82)."""

    def test_minutes_only(self):
        from app.services.metrics_service import _format_uptime

        result = _format_uptime(125)
        assert "2м" in result
        assert "5с" in result

    def test_hours(self):
        from app.services.metrics_service import _format_uptime

        result = _format_uptime(3661)
        assert "1ч" in result

    def test_days(self):
        from app.services.metrics_service import _format_uptime

        result = _format_uptime(90061)
        assert "1д" in result


class TestResetMetrics:
    """Cover reset_metrics (lines 84-end)."""

    def test_resets_all(self):
        from app.services.metrics_service import (
            get_metrics,
            record_request,
            reset_metrics,
        )

        record_request("/api/x", "GET", 500, 100.0)
        reset_metrics()
        m = get_metrics()
        assert m["total_requests"] == 0
        assert m["error_count"] == 0
