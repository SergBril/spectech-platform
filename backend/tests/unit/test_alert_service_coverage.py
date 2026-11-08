"""Coverage tests for alert_service."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    exec_result.all.return_value = []
    db.execute.return_value = exec_result
    return db


class TestCheckAndNotifyIdleVehicles:
    """Cover check_and_notify_idle_vehicles (lines 12-49)."""

    @pytest.mark.asyncio
    async def test_no_idle(self, mock_db):
        from app.services.alert_service import check_and_notify_idle_vehicles

        v1 = SimpleNamespace(id=1, name="KAMAZ")
        call_count = {"n": 0}

        def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [v1]
            else:
                result.scalars.return_value.all.return_value = [1]
            return result

        mock_db.execute.side_effect = mock_execute

        with (
            patch(
                "app.services.alert_service.send_alert_email", new_callable=AsyncMock
            ),
            patch(
                "app.services.alert_service.send_telegram_alert", new_callable=AsyncMock
            ),
        ):
            result = await check_and_notify_idle_vehicles(mock_db, 7, date(2026, 11, 6))
        assert result["idle_count"] == 0
        assert result["notified"] is False

    @pytest.mark.asyncio
    async def test_has_idle(self, mock_db):
        from app.services.alert_service import check_and_notify_idle_vehicles

        v1 = SimpleNamespace(id=1, name="KAMAZ")
        v2 = SimpleNamespace(id=2, name="MAN")
        call_count = {"n": 0}

        def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [v1, v2]
            else:
                result.scalars.return_value.all.return_value = [1]
            return result

        mock_db.execute.side_effect = mock_execute

        with (
            patch(
                "app.services.alert_service.send_alert_email", new_callable=AsyncMock
            ) as mock_email,
            patch(
                "app.services.alert_service.send_telegram_alert", new_callable=AsyncMock
            ) as mock_tg,
        ):
            result = await check_and_notify_idle_vehicles(mock_db, 7, date(2026, 11, 6))
        assert result["idle_count"] == 1
        assert result["notified"] is True
        mock_email.assert_called_once()
        mock_tg.assert_called_once()


class TestCheckAndNotifyConflicts:
    """Cover check_and_notify_conflicts (lines 51-79)."""

    @pytest.mark.asyncio
    async def test_no_conflicts(self, mock_db):
        from app.services.alert_service import check_and_notify_conflicts

        mock_db.execute.return_value.all.return_value = []
        with (
            patch(
                "app.services.alert_service.send_alert_email", new_callable=AsyncMock
            ),
            patch(
                "app.services.alert_service.send_telegram_alert", new_callable=AsyncMock
            ),
        ):
            result = await check_and_notify_conflicts(mock_db, 7, date(2026, 11, 6))
        assert result["conflict_count"] == 0
        assert result["notified"] is False

    @pytest.mark.asyncio
    async def test_has_conflicts(self, mock_db):
        from app.services.alert_service import check_and_notify_conflicts

        mock_db.execute.return_value.all.return_value = [(1, 2), (3, 3)]
        with (
            patch(
                "app.services.alert_service.send_alert_email", new_callable=AsyncMock
            ) as mock_email,
            patch(
                "app.services.alert_service.send_telegram_alert", new_callable=AsyncMock
            ) as mock_tg,
        ):
            result = await check_and_notify_conflicts(mock_db, 7, date(2026, 11, 6))
        assert result["conflict_count"] == 2
        assert result["notified"] is True
        mock_email.assert_called_once()
        mock_tg.assert_called_once()


class TestSendAlertEmail:
    """Cover send_alert_email (lines 81-104)."""

    @pytest.mark.asyncio
    async def test_success_with_fcm(self, mock_db):
        from app.services.alert_service import send_alert_email

        mock_fcm = MagicMock()
        mock_fcm.send_to_user = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [1, 2]
        with patch("app.services.fcm_service.fcm_service", mock_fcm):
            await send_alert_email(7, "Subject", "Body", mock_db)
        assert mock_fcm.send_to_user.call_count == 2

    @pytest.mark.asyncio
    async def test_fcm_error_logged(self, mock_db):
        from app.services.alert_service import send_alert_email

        mock_db.execute.side_effect = Exception("DB fail")
        await send_alert_email(7, "Test", "Body", mock_db)

    @pytest.mark.asyncio
    async def test_no_dispatchers(self, mock_db):
        from app.services.alert_service import send_alert_email

        mock_fcm = MagicMock()
        mock_fcm.send_to_user = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        with patch("app.services.fcm_service.fcm_service", mock_fcm):
            await send_alert_email(7, "Test", "Body", mock_db)
        mock_fcm.send_to_user.assert_not_called()


class TestSendTelegramAlert:
    """Cover send_telegram_alert (lines 106-end)."""

    @pytest.mark.asyncio
    async def test_logs_message(self):
        from app.services.alert_service import send_telegram_alert

        await send_telegram_alert(7, "Test message")
