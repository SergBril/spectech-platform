"""Integration tests for disputes API."""

from datetime import datetime, timedelta, date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shift import ShiftReport, ShiftTask, ShiftReportStatus
from app.models.dispatch import Request
from app.models.contractor import Contractor, Employee


@pytest.fixture
def dispute_test_data(db_session: Session, company):
    """Создаёт полный набор тестовых данных для тестов диспутов."""
    # Создаём клиента
    client_contractor = Contractor(
        name="Test Client for Dispute",
        inn="7701111111",
        kpp="770101001",
        type="client",
        company_id=company.id,
    )
    db_session.add(client_contractor)
    db_session.commit()
    db_session.refresh(client_contractor)

    # Создаём оператора (контрагент + сотрудник)
    operator_contractor = Contractor(
        name="Test Operator for Dispute",
        inn="770222222222",
        type="employee",
        company_id=company.id,
    )
    db_session.add(operator_contractor)
    db_session.commit()
    db_session.refresh(operator_contractor)

    employee = Employee(
        contractor_id=operator_contractor.id,
        position="Оператор экскаватора",
        role_in_system="operator",
    )
    db_session.add(employee)
    db_session.commit()

    # Создаём технику
    from app.models.catalog import Vehicle
    vehicle = Vehicle(
        name="Test Excavator for Dispute",
        id_type="internal",
        id_value="DISP-TEST-001",
        status="free",
        company_id=company.id,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    # Создаём заявку
    now = datetime.now()
    request = Request(
        client_id=client_contractor.id,
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
        shift_date=date.today(),
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
        "client": client_contractor,
        "operator_contractor": operator_contractor,
        "employee": employee,
        "vehicle": vehicle,
        "request": request,
        "shift_task": shift_task,
        "shift_report": shift_report,
    }


class TestDisputesAPI:
    """Test dispute management endpoints."""

    def test_create_dispute_success(
        self, auth_client: TestClient, dispute_test_data
    ):
        """Test successful dispute creation."""
        shift_report = dispute_test_data["shift_report"]

        response = auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "hours",
                "initiator_role": "client",
                "operator_version": {"moto_hours": 8.0},
                "client_version": {"moto_hours": 6.5},
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "dispatcher_review"
        assert data["dispute_type"] == "hours"
        assert "sla_deadline" in data

    def test_create_dispute_invalid_shift_report(
        self, auth_client: TestClient
    ):
        """Test dispute creation with invalid shift report."""
        response = auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": 99999,
                "dispute_type": "hours",
                "initiator_role": "client",
            },
        )
        assert response.status_code == 404

    def test_list_disputes(self, auth_client: TestClient, dispute_test_data):
        """Test listing disputes."""
        shift_report = dispute_test_data["shift_report"]

        # Create a dispute first
        auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "mileage",
                "initiator_role": "operator",
            },
        )

        response = auth_client.get("/api/v1/disputes")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_dispute(self, auth_client: TestClient, dispute_test_data):
        """Test getting a specific dispute."""
        shift_report = dispute_test_data["shift_report"]

        # Create dispute
        create_response = auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "fuel",
                "initiator_role": "client",
            },
        )
        assert create_response.status_code == 201, create_response.text
        dispute_id = create_response.json()["id"]

        # Get dispute
        response = auth_client.get(f"/api/v1/disputes/{dispute_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dispute_id
        assert data["dispute_type"] == "fuel"

    def test_escalate_dispute(self, auth_client: TestClient, dispute_test_data):
        """Test escalating a dispute."""
        shift_report = dispute_test_data["shift_report"]

        # Create dispute
        create_response = auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "hours",
                "initiator_role": "client",
            },
        )
        dispute_id = create_response.json()["id"]

        # Escalate
        response = auth_client.post(
            f"/api/v1/disputes/{dispute_id}/escalate",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "escalated_to_manager"
        assert data["assigned_role"] == "manager"

    def test_resolve_dispute(self, auth_client: TestClient, dispute_test_data):
        """Test resolving a dispute."""
        shift_report = dispute_test_data["shift_report"]

        # Create dispute
        create_response = auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "hours",
                "initiator_role": "client",
            },
        )
        dispute_id = create_response.json()["id"]

        # Resolve
        response = auth_client.post(
            f"/api/v1/disputes/{dispute_id}/resolve",
            json={
                "resolution": {
                    "comment": "Agreed on 7.5 hours",
                    "decision": "compromise",
                },
                "final_moto_hours": 7.5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_by"] is not None
        assert data["resolution_time_minutes"] is not None

    def test_filter_disputes_by_status(
        self, auth_client: TestClient, dispute_test_data
    ):
        """Test filtering disputes by status."""
        shift_report = dispute_test_data["shift_report"]

        # Create two disputes
        auth_client.post(
            "/api/v1/disputes",
            json={
                "shift_report_id": shift_report.id,
                "dispute_type": "hours",
                "initiator_role": "client",
            },
        )

        # Filter by dispatcher_review
        response = auth_client.get(
            "/api/v1/disputes?status=dispatcher_review"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(
            item["status"] == "dispatcher_review" for item in data["items"]
        )