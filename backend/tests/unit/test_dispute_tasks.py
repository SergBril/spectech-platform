"""Unit tests for dispute Celery tasks."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from unittest.mock import Mock, patch

from app.models.dispute import Dispute, DisputeStatus, DisputeType
from app.models.shift import ShiftReport, ShiftTask, ShiftReportStatus
from app.models.dispatch import Request
from app.models.contractor import Contractor, Employee
from app.tasks.dispute_tasks import (
    auto_escalate_overdue_disputes,
    check_sla_breaches,
    generate_dispute_metrics,
)


@pytest.fixture
def dispute_test_data(db_session, company):
    """Создаёт тестовые данные для споров."""
    # Создаём клиента
    client = Contractor(
        name="Test Client for Disputes",
        inn="7701111111",
        kpp="770101001",
        type="client",
        company_id=company.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)

    # Создаём оператора
    operator_contractor = Contractor(
        name="Test Operator for Disputes",
        inn="770222222222",
        type="employee",
        company_id=company.id,
    )
    db_session.add(operator_contractor)
    db_session.commit()
    db_session.refresh(operator_contractor)

    employee = Employee(
        contractor_id=operator_contractor.id,
        position="Оператор",
        role_in_system="operator",
    )
    db_session.add(employee)
    db_session.commit()

    # Создаём технику
    from app.models.catalog import Vehicle

    vehicle = Vehicle(
        name="Test Vehicle for Disputes",
        id_type="internal",
        id_value="DISP-TASK-001",
        status="free",
        company_id=company.id,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    # Создаём заявку
    now = datetime.utcnow()
    request = Request(
        client_id=client.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)

    # Создаём сменное задание
    shift_task = ShiftTask(
        request_id=request.id,
        operator_id=operator_contractor.id,
        vehicle_id=vehicle.id,
        shift_date=datetime.utcnow().date(),
        shift_number=1,
        status="completed",
        company_id=company.id,
    )
    db_session.add(shift_task)
    db_session.commit()
    db_session.refresh(shift_task)

    # Создаём сменный отчёт
    shift_report = ShiftReport(
        shift_task_id=shift_task.id,
        operator_id=operator_contractor.id,
        operator_moto_hours=Decimal("8.0"),
        operator_odometer=150,
        status=ShiftReportStatus.client_review,
        company_id=company.id,
    )
    db_session.add(shift_report)
    db_session.commit()
    db_session.refresh(shift_report)

    return {
        "company": company,
        "client": client,
        "operator_contractor": operator_contractor,
        "employee": employee,
        "vehicle": vehicle,
        "request": request,
        "shift_task": shift_task,
        "shift_report": shift_report,
    }


class TestAutoEscalateOverdueDisputes:
    """Тесты задачи автоэскалации просроченных споров."""

    def test_no_overdue_disputes(self, db_session):
        """Тест: нет просроченных споров."""
        result = auto_escalate_overdue_disputes()

        assert result["escalated"] == 0
        assert result["total_checked"] == 0

    def test_escalate_dispatcher_to_manager(self, db_session, dispute_test_data):
        """Тест: эскалация с dispatcher_review на manager."""
        shift_report = dispute_test_data["shift_report"]

        # Создаём просроченный спор на уровне dispatcher
        now = datetime.utcnow()
        dispute = Dispute(
            shift_report_id=shift_report.id,
            request_id=dispute_test_data["request"].id,
            company_id=dispute_test_data["company"].id,
            status=DisputeStatus.dispatcher_review,
            dispute_type=DisputeType.hours,
            opened_at=now - timedelta(hours=4),  # Открыт 4 часа назад
            sla_deadline=now - timedelta(hours=1),  # SLA истёк 1 час назад
            initiator_id=1,
            initiator_role="client",
        )
        db_session.add(dispute)
        db_session.commit()

        # Запускаем задачу
        result = auto_escalate_overdue_disputes()

        # Проверяем результат
        assert result["escalated"] == 1
        assert result["breakdown"]["dispatcher_to_manager"] == 1

        # Проверяем, что спор эскалирован
        db_session.refresh(dispute)
        assert dispute.status == DisputeStatus.escalated_to_manager
        assert dispute.escalated_at is not None
        assert dispute.assigned_role == "manager"

    def test_escalate_manager_to_ceo(self, db_session, dispute_test_data):
        """Тест: эскалация с manager на CEO."""
        shift_report = dispute_test_data["shift_report"]

        # Создаём просроченный спор на уровне manager
        now = datetime.utcnow()
        dispute = Dispute(
            shift_report_id=shift_report.id,
            request_id=dispute_test_data["request"].id,
            company_id=dispute_test_data["company"].id,
            status=DisputeStatus.escalated_to_manager,
            dispute_type=DisputeType.mileage,
            opened_at=now - timedelta(days=2),
            sla_deadline=now - timedelta(hours=12),
            escalated_at=now - timedelta(days=1),
            escalation_deadline=now - timedelta(hours=1),  # Просрочен
            initiator_id=1,
            initiator_role="operator",
            assigned_role="manager",
        )
        db_session.add(dispute)
        db_session.commit()

        # Запускаем задачу
        result = auto_escalate_overdue_disputes()

        # Проверяем результат
        assert result["escalated"] == 1
        assert result["breakdown"]["manager_to_ceo"] == 1

        # Проверяем, что спор эскалирован
        db_session.refresh(dispute)
        assert dispute.status == DisputeStatus.escalated_to_ceo
        assert dispute.assigned_role == "ceo"

    def test_do_not_escalate_resolved_dispute(self, db_session, dispute_test_data):
        """Тест: не эскалировать уже разрешённые споры."""
        shift_report = dispute_test_data["shift_report"]

        # Создаём разрешённый спор с просроченным SLA
        now = datetime.utcnow()
        dispute = Dispute(
            shift_report_id=shift_report.id,
            request_id=dispute_test_data["request"].id,
            company_id=dispute_test_data["company"].id,
            status=DisputeStatus.resolved,
            dispute_type=DisputeType.hours,
            opened_at=now - timedelta(hours=5),
            sla_deadline=now - timedelta(hours=2),  # Просрочен
            resolved_at=now - timedelta(hours=1),
            resolved_by=1,
            initiator_id=1,
            initiator_role="client",
        )
        db_session.add(dispute)
        db_session.commit()

        # Запускаем задачу
        result = auto_escalate_overdue_disputes()

        # Проверяем, что спор не был обработан
        assert result["escalated"] == 0
        assert result["total_checked"] == 0


class TestCheckSLABreaches:
    """Тесты задачи проверки нарушений SLA."""

    def test_no_sla_breaches(self, db_session):
        """Тест: нет нарушений SLA."""
        result = check_sla_breaches()

        assert result["breached"] == 0

    def test_mark_sla_breached(self, db_session, dispute_test_data):
        """Тест: пометка спора как нарушившего SLA."""
        shift_report = dispute_test_data["shift_report"]

        # Создаём спор с нарушенным SLA
        now = datetime.utcnow()
        dispute = Dispute(
            shift_report_id=shift_report.id,
            request_id=dispute_test_data["request"].id,
            company_id=dispute_test_data["company"].id,
            status=DisputeStatus.dispatcher_review,
            dispute_type=DisputeType.hours,
            opened_at=now - timedelta(hours=4),
            sla_deadline=now - timedelta(hours=1),  # Просрочен
            initiator_id=1,
            initiator_role="client",
            sla_breached=False,  # Ещё не помечен
        )
        db_session.add(dispute)
        db_session.commit()

        # Запускаем задачу
        result = check_sla_breaches()

        # Проверяем результат
        assert result["breached"] == 1

        # Проверяем, что спор помечен как нарушивший SLA
        db_session.refresh(dispute)
        assert dispute.sla_breached is True


class TestGenerateDisputeMetrics:
    """Тесты задачи генерации метрик по спорам."""

    def test_generate_metrics_empty(self, db_session):
        """Тест: генерация метрик при отсутствии споров."""
        result = generate_dispute_metrics()

        assert result["total_disputes_30d"] == 0
        assert result["breached_sla_count"] == 0
        assert result["breach_rate_percent"] == 0
        assert result["avg_resolution_time_minutes"] == 0
        assert result["active_disputes"] == 0

    def test_generate_metrics_with_data(self, db_session, dispute_test_data):
        """Тест: генерация метрик с данными."""
        shift_report = dispute_test_data["shift_report"]
        now = datetime.utcnow()

        # Создаём несколько споров
        for i in range(3):
            dispute = Dispute(
                shift_report_id=shift_report.id,
                request_id=dispute_test_data["request"].id,
                company_id=dispute_test_data["company"].id,
                status=DisputeStatus.resolved if i < 2 else DisputeStatus.dispatcher_review,
                dispute_type=DisputeType.hours if i < 2 else DisputeType.mileage,
                opened_at=now - timedelta(days=10 - i),
                sla_deadline=now - timedelta(days=10 - i, hours=-3),
                resolved_at=now - timedelta(days=5 - i) if i < 2 else None,
                resolved_by=1 if i < 2 else None,
                resolution_time_minutes=120 + i * 30 if i < 2 else None,
                sla_breached=i == 1,  # Один спор с нарушенным SLA
                initiator_id=1,
                initiator_role="client",
            )
            db_session.add(dispute)

        db_session.commit()

        # Запускаем задачу
        result = generate_dispute_metrics()

        # Проверяем метрики
        assert result["total_disputes_30d"] == 3
        assert result["breached_sla_count"] == 1
        assert result["breach_rate_percent"] == 33.33
        assert result["avg_resolution_time_minutes"] == 135.0  # (120 + 150) / 2
        assert result["active_disputes"] == 1
        assert result["disputes_by_type"]["hours"] == 2
        assert result["disputes_by_type"]["mileage"] == 1