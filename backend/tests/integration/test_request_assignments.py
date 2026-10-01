"""Integration tests for request assignments and overbooking protection."""

from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.testclient import Response


class TestRequestAssignmentOverbooking:
    """Тесты защиты от овербукинга при назначении техники."""

    def _create_request(
        self,
        auth_client: TestClient,
        contractor_id: int,
        start_offset_days: int = 1,
        duration_hours: int = 8,
    ) -> dict:
        """Вспомогательный метод: создаёт заявку."""
        start = datetime.now() + timedelta(days=start_offset_days)
        end = start + timedelta(hours=duration_hours)

        payload = {
            "client_id": contractor_id,
            "request_type": "one_time",
            "work_type": "Earthworks",
            "object_address": "Test site",
            "planned_start": start.isoformat(),
            "planned_end": end.isoformat(),
            "source_channel": "phone",
            "priority": "normal",
        }
        response = auth_client.post("/api/v1/requests", json=payload)
        assert response.status_code == 201, response.text
        return response.json()


def _assign_vehicle(
    self,
    auth_client: TestClient,
    request_id: int,
    vehicle_id: int,
    planned_start: str | None = None,
    planned_end: str | None = None,
) -> Response:
    """Вспомогательный метод: назначает технику на заявку."""
    payload: dict[str, Any] = {"vehicle_id": vehicle_id}
    if planned_start:
        payload["planned_start"] = planned_start
    if planned_end:
        payload["planned_end"] = planned_end

    response = auth_client.post(f"/api/v1/requests/{request_id}/assign", json=payload)
    return response

    def test_assign_vehicle_success(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Успешное назначение техники на заявку."""
        request_data = self._create_request(auth_client, sample_contractor.id)

        response = self._assign_vehicle(
            auth_client, request_data["id"], sample_vehicle.id
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "assigned"
        assert data["assigned_vehicle_id"] == sample_vehicle.id

    def test_assign_vehicle_overlap_rejected(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Овербукинг: вторая заявка на ту же технику в тот же период отклоняется."""
        # Создаём первую заявку и назначаем технику
        request1 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=1
        )
        resp1 = self._assign_vehicle(auth_client, request1["id"], sample_vehicle.id)
        assert resp1.status_code == 200

        # Создаём вторую заявку на ТОТ ЖЕ период
        request2 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=1
        )

        # Пытаемся назначить ту же технику — должно быть отклонено
        resp2 = self._assign_vehicle(auth_client, request2["id"], sample_vehicle.id)
        assert resp2.status_code == 409
        detail = resp2.json()["detail"]
        # detail - это строка, а не словарь
        assert "already assigned" in detail.lower()

    def test_assign_vehicle_partial_overlap_rejected(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Частичное пересечение периодов тоже отклоняется."""
        # Первая заявка: завтра 08:00 — 17:00
        request1 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=1
        )
        resp1 = self._assign_vehicle(auth_client, request1["id"], sample_vehicle.id)
        assert resp1.status_code == 200

        # Вторая заявка: завтра 14:00 — 20:00 (пересечение с 14:00 до 17:00)
        request2 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=1
        )
        start2 = datetime.now() + timedelta(days=1, hours=6)
        end2 = start2 + timedelta(hours=6)

        resp2 = self._assign_vehicle(
            auth_client,
            request2["id"],
            sample_vehicle.id,
            planned_start=start2.isoformat(),
            planned_end=end2.isoformat(),
        )
        assert resp2.status_code == 409

    def test_assign_vehicle_no_overlap_different_days(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Разные дни — нет пересечения, назначение успешно."""
        # Первая заявка: завтра
        request1 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=1
        )
        resp1 = self._assign_vehicle(auth_client, request1["id"], sample_vehicle.id)
        assert resp1.status_code == 200

        # Вторая заявка: послезавтра
        request2 = self._create_request(
            auth_client, sample_contractor.id, start_offset_days=2
        )
        resp2 = self._assign_vehicle(auth_client, request2["id"], sample_vehicle.id)
        assert resp2.status_code == 200

    def test_assign_vehicle_idempotency(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Повторный запрос на назначение возвращает существующее (idempotency)."""
        request_data = self._create_request(auth_client, sample_contractor.id)

        # Первое назначение
        resp1 = self._assign_vehicle(auth_client, request_data["id"], sample_vehicle.id)
        assert resp1.status_code == 200

        # Повторное назначение той же техники на ту же заявку
        resp2 = self._assign_vehicle(auth_client, request_data["id"], sample_vehicle.id)
        assert resp2.status_code == 200

    def test_assign_to_closed_request_rejected(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Нельзя назначить технику на закрытую/отменённую заявку (409 Conflict)."""
        request_data = self._create_request(auth_client, sample_contractor.id)

        # Закрываем заявку
        auth_client.patch(
            f"/api/v1/requests/{request_data['id']}",
            json={"status": "cancelled"},
        )

        # Пытаемся назначить — должно быть отклонено (409)
        resp = self._assign_vehicle(auth_client, request_data["id"], sample_vehicle.id)
        assert resp.status_code == 409, resp.text
        assert "cancelled" in resp.json()["detail"].lower()

    def test_assign_nonexistent_vehicle(
        self,
        auth_client: TestClient,
        sample_contractor,
        db_session: Session,
    ):
        """Назначение несуществующей техники — 404 Not Found."""
        request_data = self._create_request(auth_client, sample_contractor.id)

        resp = self._assign_vehicle(auth_client, request_data["id"], 99999)
        # Техника не найдена — это 404, а не 409
        assert resp.status_code == 404, resp.text
        assert "not found" in resp.json()["detail"].lower()

    def test_assign_vehicle_with_operator_creates_shift_task(
        self,
        auth_client: TestClient,
        sample_contractor,
        sample_vehicle,
        db_session: Session,
    ):
        """Назначение с оператором автоматически создаёт ShiftTask."""
        from app.models.contractor import Contractor, Employee
        from app.models.shift import ShiftTask

        # Создаём контрагента-сотрудника (оператора)
        operator_contractor = Contractor(
            name="Test Operator",
            inn="7709999999",
            type="employee",
            company_id=sample_contractor.company_id,
        )
        db_session.add(operator_contractor)
        db_session.commit()
        db_session.refresh(operator_contractor)

        # Создаём Employee запись
        employee = Employee(
            contractor_id=operator_contractor.id,
            position="Оператор",
            role_in_system="operator",
        )
        db_session.add(employee)
        db_session.commit()

        request_data = self._create_request(auth_client, sample_contractor.id)

        # Назначаем с оператором
        payload = {
            "vehicle_id": sample_vehicle.id,
            "operator_id": operator_contractor.id,
        }
        response = auth_client.post(
            f"/api/v1/requests/{request_data['id']}/assign", json=payload
        )
        assert response.status_code == 200, response.text

        # Проверяем, что ShiftTask создан
        shift_tasks = (
            db_session.query(ShiftTask)
            .filter(ShiftTask.request_id == request_data["id"])
            .all()
        )
        assert len(shift_tasks) == 1
        assert shift_tasks[0].operator_id == operator_contractor.id
        assert shift_tasks[0].vehicle_id == sample_vehicle.id

    def test_check_availability_endpoint(
        self,
        auth_client: TestClient,
        sample_vehicle,
        db_session: Session,
    ):
        """Проверка эндпоинта /vehicles/{id}/availability."""
        start = datetime.now() + timedelta(days=5)
        end = start + timedelta(hours=8)

        response = auth_client.get(
            f"/api/v1/vehicles/{sample_vehicle.id}/availability",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert data["vehicle_id"] == sample_vehicle.id
