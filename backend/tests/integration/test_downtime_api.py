"""Интеграционные тесты API учёта простоев."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import Client
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.downtime import DowntimeCause, DowntimeStatus, FaultParty
from app.models.shift import ShiftTask
from app.models.dispatch import Request


class TestDowntimeAPI:
    """Тесты CRUD и бизнес-логики простоев."""

    @pytest.fixture
    def shift_task(self, db_session: Session, company, sample_vehicle):
        """Создаёт сменное задание для тестов."""
        from app.models.dispatch import Request
    
        now = datetime.now(timezone.utc)
        # Создаём заявку с обязательными полями planned_start/planned_end
        request = Request(
            company_id=company.id,
            client_id=None,
            status="new",
            planned_start=now,
            planned_end=now + timedelta(hours=8),
            work_type="rent",
        )
        db_session.add(request)
        db_session.commit()
        db_session.refresh(request)
    
        task = ShiftTask(
            request_id=request.id,
            vehicle_id=sample_vehicle.id,
            operator_id=None,
            company_id=company.id,
            shift_date=now.date(),
            status="draft",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    @pytest.fixture
    def vehicle_with_rate(
        self, db_session: Session, company, sample_vehicle: Vehicle
    ):
        """Добавляет downtime_hourly_rate к технике."""
        sample_vehicle.downtime_hourly_rate = Decimal("2000.00")
        db_session.commit()
        db_session.refresh(sample_vehicle)
        return sample_vehicle

    def test_create_downtime_client_fault_billable(
        self, auth_client: Client, shift_task: ShiftTask, vehicle_with_rate
    ):
        """Простой по вине клиента: billable=True, рассчитывается сумма."""
        now = datetime.now(timezone.utc)
        response = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=2)).isoformat(),
                "cause_category": "waiting_client",
                "description": "Клиент не обеспечил фронт работ",
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Автоопределение: waiting_client -> client -> billable
        assert data["fault_party"] == "client"
        assert data["billable"] is True
        assert data["duration_minutes"] == 120
        # 2 часа × 2000 руб/час = 4000 руб
        assert float(data["total_amount"]) == 4000.0
        assert data["status"] == "pending"

    def test_create_downtime_operator_fault_not_billable(
        self, auth_client: Client, shift_task: ShiftTask, vehicle_with_rate
    ):
        """Простой по вине оператора: billable=False, сумма 0."""
        now = datetime.now(timezone.utc)
        response = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "operator_fault",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["fault_party"] == "operator"
        assert data["billable"] is False
        assert float(data["total_amount"]) == 0.0

    def test_create_downtime_auto_fault_by_cause(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Причина → виновная сторона определяется автоматически."""
        test_cases = [
            ("waiting_site", "client"),
            ("technical", "owner"),
            ("weather", "none"),
            ("force_majeure", "none"),
        ]

        for cause, expected_fault in test_cases:
            now = datetime.now(timezone.utc)
            response = auth_client.post(
                "/api/v1/downtime",
                json={
                    "shift_task_id": shift_task.id,
                    "started_at": now.isoformat(),
                    "ended_at": (now + timedelta(minutes=30)).isoformat(),
                    "cause_category": cause,
                },
            )
            assert response.status_code == 201, f"Failed for cause={cause}"
            data = response.json()
            assert (
                data["fault_party"] == expected_fault
            ), f"Cause {cause} should map to {expected_fault}, got {data['fault_party']}"

    def test_create_downtime_override_fault_party(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Можно вручную переопределить виновную сторону."""
        now = datetime.now(timezone.utc)
        response = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "waiting_client",
                "fault_party": "owner",  # Переопределяем
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["fault_party"] == "owner"
        assert data["billable"] is False  # owner != client

    def test_end_downtime_recalculates_amount(
        self, auth_client: Client, shift_task: ShiftTask, vehicle_with_rate
    ):
        """Завершение открытого простоя пересчитывает сумму."""
        now = datetime.now(timezone.utc)

        # Создаём открытый простой (без ended_at)
        create_resp = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "cause_category": "waiting_client",
            },
        )
        assert create_resp.status_code == 201
        downtime_id = create_resp.json()["id"]
        assert create_resp.json()["duration_minutes"] == 0

        # Завершаем через 90 минут
        end_resp = auth_client.post(
            f"/api/v1/downtime/{downtime_id}/end",
            json={"ended_at": (now + timedelta(minutes=90)).isoformat()},
        )

        assert end_resp.status_code == 200
        data = end_resp.json()
        assert data["duration_minutes"] == 90
        # 1.5 часа × 2000 = 3000
        assert float(data["total_amount"]) == 3000.0

    def test_approve_downtime(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Подтверждение простоя: pending → approved."""
        now = datetime.now(timezone.utc)
        create_resp = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "waiting_client",
            },
        )
        downtime_id = create_resp.json()["id"]

        approve_resp = auth_client.post(f"/api/v1/downtime/{downtime_id}/approve")

        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] is not None
        assert data["approved_at"] is not None

    def test_reject_downtime(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Отклонение простоя: pending → rejected."""
        now = datetime.now(timezone.utc)
        create_resp = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "waiting_client",
            },
        )
        downtime_id = create_resp.json()["id"]

        reject_resp = auth_client.post(
            f"/api/v1/downtime/{downtime_id}/reject",
            json={"reason": "Не подтверждено клиентом"},
        )

        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data["status"] == "rejected"
        assert data["rejection_reason"] == "Не подтверждено клиентом"

    def test_cannot_approve_non_pending(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Нельзя подтвердить уже подтверждённый простой."""
        now = datetime.now(timezone.utc)
        create_resp = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "waiting_client",
            },
        )
        downtime_id = create_resp.json()["id"]

        # Первый approve — OK
        auth_client.post(f"/api/v1/downtime/{downtime_id}/approve")

        # Второй approve — 400
        resp = auth_client.post(f"/api/v1/downtime/{downtime_id}/approve")
        assert resp.status_code == 400

    def test_list_downtimes_by_shift_task(
        self, auth_client: Client, shift_task: ShiftTask
    ):
        """Фильтрация простоев по shift_task_id."""
        now = datetime.now(timezone.utc)
        # Создаём 3 простоя
        for cause in ["waiting_client", "technical", "weather"]:
            auth_client.post(
                "/api/v1/downtime",
                json={
                    "shift_task_id": shift_task.id,
                    "started_at": now.isoformat(),
                    "ended_at": (now + timedelta(hours=1)).isoformat(),
                    "cause_category": cause,
                },
            )

        response = auth_client.get(
            f"/api/v1/downtime?shift_task_id={shift_task.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_downtime_stats(
        self, auth_client: Client, shift_task: ShiftTask, vehicle_with_rate
    ):
        """Статистика по простоям."""
        now = datetime.now(timezone.utc)

        # 2 простоя по вине клиента (billable)
        for _ in range(2):
            auth_client.post(
                "/api/v1/downtime",
                json={
                    "shift_task_id": shift_task.id,
                    "started_at": now.isoformat(),
                    "ended_at": (now + timedelta(hours=1)).isoformat(),
                    "cause_category": "waiting_client",
                },
            )

        # 1 простой по вине оператора (не billable)
        auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=1)).isoformat(),
                "cause_category": "operator_fault",
            },
        )

        response = auth_client.get("/api/v1/downtime/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_events"] == 3
        assert data["total_minutes"] == 180
        assert data["total_hours"] == 3.0
        # 2 × (1ч × 2000) = 4000
        assert data["total_billable_amount"] == 4000.0
        assert "client" in data["by_fault_party"]
        assert "operator" in data["by_fault_party"]

    def test_downtime_fallback_to_hourly_rate(
        self, auth_client: Client, shift_task: ShiftTask, sample_vehicle
    ):
        """Если downtime_hourly_rate не указан — используется 50% от hourly_rate."""
        # Устанавливаем только hourly_rate
        sample_vehicle.hourly_rate = Decimal("1000.00")
        sample_vehicle.downtime_hourly_rate = None

        now = datetime.now(timezone.utc)
        response = auth_client.post(
            "/api/v1/downtime",
            json={
                "shift_task_id": shift_task.id,
                "started_at": now.isoformat(),
                "ended_at": (now + timedelta(hours=2)).isoformat(),
                "cause_category": "waiting_client",
            },
        )

        assert response.status_code == 201
        data = response.json()
        # 50% от 1000 = 500 руб/час
        assert float(data["hourly_rate"]) == 500.0
        # 2ч × 500 = 1000
        assert float(data["total_amount"]) == 1000.0