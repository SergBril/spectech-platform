"""Кросс-тенант изоляция диспутов: create / escalate / resolve.

Две реальные компании, реальная цепочка Vehicle -> Request -> ShiftTask ->
ShiftReport и реальный Dispute компании B. Пользователь A не может открыть спор
по чужому отчёту, эскалировать и резолвить чужой спор (влияние на биллинг).
Positive-control: пользователь B выполняет все три действия со своими объектами.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.dispute import Dispute, DisputeStatus, DisputeType, InitiatorRole
from app.models.shift import ShiftReport, ShiftReportStatus, ShiftTask
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Dispute Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999997",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    user = User(
        email="dispute-other@test.com",
        full_name="Dispute Other User",
        password_hash="hashed_password",
        company_id=second_company.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_auth_headers(other_user: User) -> dict:
    token = create_access_token(user=other_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def chain_b(db_session: Session, second_company: Company, other_user: User) -> dict:
    """Реальная цепочка объектов компании B."""
    contractor = Contractor(
        name="Dispute Client B",
        inn="7703333333",
        type="client",
        company_id=second_company.id,
    )
    db_session.add(contractor)
    db_session.flush()

    vehicle = Vehicle(
        name="Экскаватор B",
        company_id=second_company.id,
        status="free",
        id_type="internal",
        id_value="DISP-B-001",
    )
    db_session.add(vehicle)
    db_session.flush()

    request = Request(
        client_id=contractor.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(days=1),
        company_id=second_company.id,
    )
    db_session.add(request)
    db_session.flush()

    task = ShiftTask(
        request_id=request.id,
        operator_id=contractor.id,
        vehicle_id=vehicle.id,
        shift_date=date.today(),
        shift_number=1,
        status="completed",
        company_id=second_company.id,
    )
    db_session.add(task)
    db_session.flush()

    report = ShiftReport(
        shift_task_id=task.id,
        operator_moto_hours=Decimal("8.0"),
        status=ShiftReportStatus.client_review,
        company_id=second_company.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return {"report": report, "request": request}


@pytest.fixture
def dispute_b(
    db_session: Session, chain_b: dict, second_company: Company, other_user: User
) -> Dispute:
    now = datetime.now(UTC)
    dispute = Dispute(
        shift_report_id=chain_b["report"].id,
        request_id=chain_b["request"].id,
        company_id=second_company.id,
        status=DisputeStatus.dispatcher_review,
        dispute_type=DisputeType.hours,
        opened_at=now,
        sla_deadline=now + timedelta(hours=3),
        initiator_id=other_user.id,
        initiator_role=InitiatorRole.operator,
        operator_version={"moto_hours": 10.0},
        client_version={"moto_hours": 8.0},
    )
    db_session.add(dispute)
    db_session.commit()
    db_session.refresh(dispute)
    return dispute


def _create_payload(shift_report_id: int) -> dict:
    return {
        "shift_report_id": shift_report_id,
        "dispute_type": "hours",
        "initiator_role": "operator",
        "operator_version": {"moto_hours": 10.0},
        "client_version": {"moto_hours": 8.0},
    }


class TestDisputeTenantIsolation:
    def test_create_foreign_report_404_and_status_unchanged(
        self,
        client: TestClient,
        auth_headers: dict,
        chain_b: dict,
        db_session: Session,
    ):
        resp = client.post(
            "/api/v1/disputes",
            json=_create_payload(chain_b["report"].id),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        # Факт из БД: чужой отчёт НЕ перешёл в disputed
        db_session.expire_all()
        report = db_session.get(ShiftReport, chain_b["report"].id)
        assert report.status != ShiftReportStatus.disputed

    def test_escalate_foreign_404_and_status_unchanged(
        self,
        client: TestClient,
        auth_headers: dict,
        dispute_b: Dispute,
        db_session: Session,
    ):
        resp = client.post(
            f"/api/v1/disputes/{dispute_b.id}/escalate", headers=auth_headers
        )
        assert resp.status_code == 404
        db_session.expire_all()
        dispute = db_session.get(Dispute, dispute_b.id)
        assert dispute.status == DisputeStatus.dispatcher_review

    def test_resolve_foreign_404_and_billing_unchanged(
        self,
        client: TestClient,
        auth_headers: dict,
        dispute_b: Dispute,
        chain_b: dict,
        db_session: Session,
    ):
        resp = client.post(
            f"/api/v1/disputes/{dispute_b.id}/resolve",
            json={"resolution": {"note": "foreign"}, "final_moto_hours": 999},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        db_session.expire_all()
        dispute = db_session.get(Dispute, dispute_b.id)
        assert dispute.status != DisputeStatus.resolved
        report = db_session.get(ShiftReport, chain_b["report"].id)
        assert report.final_moto_hours is None


class TestDisputeOwnAccess:
    def test_create_own_report_201(
        self,
        client: TestClient,
        other_auth_headers: dict,
        chain_b: dict,
        db_session: Session,
    ):
        resp = client.post(
            "/api/v1/disputes",
            json=_create_payload(chain_b["report"].id),
            headers=other_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        db_session.expire_all()
        report = db_session.get(ShiftReport, chain_b["report"].id)
        assert report.status == ShiftReportStatus.disputed

    def test_escalate_own_200(
        self,
        client: TestClient,
        other_auth_headers: dict,
        dispute_b: Dispute,
        db_session: Session,
    ):
        resp = client.post(
            f"/api/v1/disputes/{dispute_b.id}/escalate", headers=other_auth_headers
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        dispute = db_session.get(Dispute, dispute_b.id)
        assert dispute.status == DisputeStatus.escalated_to_manager

    def test_resolve_own_200_persists_final_hours(
        self,
        client: TestClient,
        other_auth_headers: dict,
        dispute_b: Dispute,
        chain_b: dict,
        db_session: Session,
    ):
        resp = client.post(
            f"/api/v1/disputes/{dispute_b.id}/resolve",
            json={"resolution": {"note": "ok"}, "final_moto_hours": 12.5},
            headers=other_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        report = db_session.get(ShiftReport, chain_b["report"].id)
        assert report.final_moto_hours == Decimal("12.5")
