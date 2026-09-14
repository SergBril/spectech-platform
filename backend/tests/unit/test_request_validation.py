"""Unit тесты для валидации заявок."""

from datetime import datetime, timedelta

from app.schemas.request import RequestCreate


class TestRequestCreateValidation:
    """Тесты валидации схемы RequestCreate."""

    def test_valid_request_data(self):
        """Валидные данные должны проходить валидацию."""
        now = datetime.now()
        data = {
            "client_id": 1,
            "work_type": "Земляные работы",
            "object_address": "Москва",
            "planned_start": now,
            "planned_end": now + timedelta(days=1),
            "request_type": "one_time",
            "source_channel": "phone",
            "priority": "normal",
        }

        request = RequestCreate(**data)
        assert request.client_id == 1
        assert request.work_type == "Земляные работы"

    def test_planned_end_must_be_after_start(self):
        """planned_end должен быть позже planned_start (проверка в route)."""
        now = datetime.now()
        data = {
            "client_id": 1,
            "work_type": "Test",
            "object_address": "Test",
            "planned_start": now + timedelta(days=1),
            "planned_end": now,  # ❌ Раньше начала
            "request_type": "one_time",
            "source_channel": "phone",
            "priority": "normal",
        }

        # Pydantic пропустит, но route должен отклонить
        request = RequestCreate(**data)
        assert request.planned_end < request.planned_start

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        now = datetime.now()
        data = {
            "client_id": 1,
            "planned_start": now,
            "planned_end": now + timedelta(days=1),
        }

        request = RequestCreate(**data)
        assert request.request_type == "one_time"
        assert request.source_channel == "phone"
        assert request.priority == "normal"
