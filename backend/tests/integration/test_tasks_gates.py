"""Гейты tasks.py: tenant-изоляция PDF-задач, superuser /emails/send, auth статуса.

Две реальные компании, реальные счета/акты. Celery/SMTP мокаются (внешние сервисы).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act, Invoice
from app.services.auth_service import create_access_token

pytestmark = [pytest.mark.integration]

INVOICE_DELAY = "app.api.routes.tasks.generate_invoice_pdf_async.delay"
ACT_DELAY = "app.api.routes.tasks.generate_act_pdf_async.delay"
EMAIL_DELAY = "app.tasks.email_tasks.send_email_async.delay"
ASYNC_RESULT = "app.core.celery_app.celery_app.AsyncResult"


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Tasks Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999992",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def regular_headers(sample_user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user=sample_user)}"}


def _contractor(name: str, inn: str, company_id: int) -> Contractor:
    return Contractor(name=name, inn=inn, type="client", company_id=company_id)


def _invoice(number: str, client_id: int, company_id: int) -> Invoice:
    return Invoice(
        document_number=number,
        client_id=client_id,
        company_id=company_id,
        subtotal=Decimal("1000.00"),
        vat_amount=Decimal("200.00"),
        vat_rate=Decimal("20.00"),
        total=Decimal("1200.00"),
        invoice_date=date.today(),
        status="draft",
    )


def _act(number: str, client_id: int, company_id: int) -> Act:
    return Act(
        document_number=number,
        client_id=client_id,
        company_id=company_id,
        total_amount=Decimal("1000.00"),
        act_date=date.today(),
    )


@pytest.fixture
def task_docs(db_session: Session, company: Company, second_company: Company):
    ca = _contractor("Tasks Client A", "7707777771", company.id)
    cb = _contractor("Tasks Client B", "7707777772", second_company.id)
    db_session.add_all([ca, cb])
    db_session.flush()
    inv_a = _invoice("INV-TASK-A", ca.id, company.id)
    inv_b = _invoice("INV-TASK-B", cb.id, second_company.id)
    act_a = _act("ACT-TASK-A", ca.id, company.id)
    act_b = _act("ACT-TASK-B", cb.id, second_company.id)
    db_session.add_all([inv_a, inv_b, act_a, act_b])
    db_session.commit()
    for obj in (inv_a, inv_b, act_a, act_b):
        db_session.refresh(obj)
    return {"inv_a": inv_a, "inv_b": inv_b, "act_a": act_a, "act_b": act_b}


class TestPdfTaskIsolation:
    def test_invoice_foreign_404_no_task(
        self, client: TestClient, auth_headers: dict, task_docs: dict
    ):
        with patch(INVOICE_DELAY) as delay:
            resp = client.post(
                f"/api/v1/tasks/invoices/{task_docs['inv_b'].id}/generate-pdf-async",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        delay.assert_not_called()

    def test_invoice_own_200_task_queued(
        self,
        client: TestClient,
        auth_headers: dict,
        task_docs: dict,
        company: Company,
    ):
        with patch(INVOICE_DELAY, return_value=MagicMock(id="task-a")) as delay:
            resp = client.post(
                f"/api/v1/tasks/invoices/{task_docs['inv_a'].id}/generate-pdf-async",
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        delay.assert_called_once()
        assert delay.call_args.kwargs["company_id"] == company.id

    def test_act_foreign_404_no_task(
        self, client: TestClient, auth_headers: dict, task_docs: dict
    ):
        with patch(ACT_DELAY) as delay:
            resp = client.post(
                f"/api/v1/tasks/acts/{task_docs['act_b'].id}/generate-pdf-async",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        delay.assert_not_called()

    def test_act_own_200_task_queued(
        self,
        client: TestClient,
        auth_headers: dict,
        task_docs: dict,
        company: Company,
    ):
        with patch(ACT_DELAY, return_value=MagicMock(id="task-b")) as delay:
            resp = client.post(
                f"/api/v1/tasks/acts/{task_docs['act_a'].id}/generate-pdf-async",
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        delay.assert_called_once()
        assert delay.call_args.kwargs["company_id"] == company.id


class TestEmailSendGate:
    PARAMS = {"to_email": "x@test.com", "subject": "s", "body": "b"}

    def test_anonymous_401(self, client: TestClient):
        resp = client.post("/api/v1/tasks/emails/send", params=self.PARAMS)
        assert resp.status_code == 401

    def test_regular_user_403(self, client: TestClient, regular_headers: dict):
        resp = client.post(
            "/api/v1/tasks/emails/send", params=self.PARAMS, headers=regular_headers
        )
        assert resp.status_code == 403

    def test_superuser_200(self, client: TestClient, auth_headers: dict):
        with patch(EMAIL_DELAY, return_value=MagicMock(id="task-e")) as delay:
            resp = client.post(
                "/api/v1/tasks/emails/send",
                params=self.PARAMS,
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        delay.assert_called_once()


class TestTaskStatusAuth:
    def test_anonymous_401(self, client: TestClient):
        resp = client.get("/api/v1/tasks/tasks/some-task-id/status")
        assert resp.status_code == 401

    def test_authenticated_200(self, client: TestClient, auth_headers: dict):
        result = MagicMock()
        result.status = "PENDING"
        result.ready.return_value = False
        result.failed.return_value = False
        with patch(ASYNC_RESULT, return_value=result):
            resp = client.get(
                "/api/v1/tasks/tasks/some-task-id/status", headers=auth_headers
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"
