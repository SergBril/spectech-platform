"""Coverage tests for background_service."""
from unittest.mock import patch


class TestLogTask:
    """Cover log_task (lines 12-24)."""

    def test_appends_to_log(self):
        from app.services.background_service import log_task, get_task_log, _task_log
        _task_log.clear()
        log_task("test_task", "completed", "details")
        logs = get_task_log()
        assert len(logs) == 1
        assert logs[0]["task"] == "test_task"
        assert logs[0]["status"] == "completed"

    def test_trims_to_100(self):
        from app.services.background_service import log_task, _task_log
        _task_log.clear()
        for i in range(105):
            log_task(f"task_{i}", "ok")
        assert len(_task_log) == 100
        assert _task_log[0]["task"] == "task_5"


class TestGetTaskLog:
    """Cover get_task_log (lines 27-29)."""

    def test_returns_reversed(self):
        from app.services.background_service import log_task, get_task_log, _task_log
        _task_log.clear()
        log_task("first", "ok")
        log_task("second", "ok")
        logs = get_task_log()
        assert logs[0]["task"] == "second"
        assert logs[1]["task"] == "first"


class TestBackgroundGeneratePdf:
    """Cover background_generate_pdf (lines 34-43)."""

    def test_success(self):
        from app.services.background_service import background_generate_pdf, _task_log
        _task_log.clear()
        background_generate_pdf("act", 42, "/tmp/act.pdf")
        assert any(t["task"] == "generate_pdf_act" and t["status"] == "completed" for t in _task_log)

    def test_error_logged(self):
        from app.services.background_service import background_generate_pdf, _task_log
        _task_log.clear()
        with patch("app.services.background_service.log_task", side_effect=[None, None]):
            # First call succeeds, simulate error in the function body
            pass
        # Direct test: make logger.error path
        with patch("app.services.background_service.logger") as mock_logger:
            mock_logger.info.side_effect = Exception("fail")
            background_generate_pdf("act", 1, "/tmp/x.pdf")
        assert any(t["status"] == "failed" for t in _task_log)


class TestBackgroundSendEmail:
    """Cover background_send_email (lines 46-55)."""

    def test_success(self):
        from app.services.background_service import background_send_email, _task_log
        _task_log.clear()
        background_send_email("test@example.com", "Subject", "Body")
        assert any(t["task"] == "send_email" and t["status"] == "completed" for t in _task_log)

    def test_error_logged(self):
        from app.services.background_service import background_send_email, _task_log
        _task_log.clear()
        with patch("app.services.background_service.logger") as mock_logger:
            mock_logger.info.side_effect = Exception("SMTP fail")
            background_send_email("test@example.com", "Subj", "Body")
        assert any(t["task"] == "send_email" and t["status"] == "failed" for t in _task_log)


class TestBackgroundProcessGpsBatch:
    """Cover background_process_gps_batch (lines 58-73)."""

    def test_success(self):
        from app.services.background_service import background_process_gps_batch, _task_log
        _task_log.clear()
        background_process_gps_batch(7, 150)
        entry = next(t for t in _task_log if t["task"] == "process_gps_batch")
        assert entry["status"] == "completed"
        assert "vehicle=7" in entry["details"]

    def test_error_logged(self):
        from app.services.background_service import background_process_gps_batch, _task_log
        _task_log.clear()
        with patch("app.services.background_service.logger") as mock_logger:
            mock_logger.info.side_effect = Exception("GPS fail")
            background_process_gps_batch(7, 150)
        assert any(t["task"] == "process_gps_batch" and t["status"] == "failed" for t in _task_log)
