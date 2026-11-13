"""Кросс-тенант изоляция чтения документов: acts / files / export.

Объекты компании B запрашиваются пользователем компании A -> 404.
Две реальные компании и реальные объекты в БД, без моков данных.
Positive-control: свой акт -> 200 (проверка владельца реальная;
weasyprint уже замокан в conftest, рендер возвращает тестовый PDF).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.finance import Act
from app.models.telematics import UploadedFile

pytestmark = [pytest.mark.integration]


# ─── Фикстуры: компания B и её реальные объекты ──────────────────────────────


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Documents Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999998",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def contractor_b(db_session: Session, second_company: Company) -> Contractor:
    contractor = Contractor(
        name="Client B LLC",
        inn="7701111112",
        type="client",
        company_id=second_company.id,
    )
    db_session.add(contractor)
    db_session.commit()
    db_session.refresh(contractor)
    return contractor


@pytest.fixture
def act_b(
    db_session: Session, second_company: Company, contractor_b: Contractor
) -> Act:
    act = Act(
        document_number="ACT-ISOLATION-B-0001",
        client_id=contractor_b.id,
        company_id=second_company.id,
        total_amount=Decimal("1000.00"),
        act_date=date.today(),
    )
    db_session.add(act)
    db_session.commit()
    db_session.refresh(act)
    return act


@pytest.fixture
def file_b(db_session: Session, second_company: Company) -> UploadedFile:
    uploaded = UploadedFile(
        original_filename="secret_b.pdf",
        storage_path="isolation-test/secret_b.pdf",
        content_type="application/pdf",
        size_bytes=123,
        file_category="other",
        company_id=second_company.id,
    )
    db_session.add(uploaded)
    db_session.commit()
    db_session.refresh(uploaded)
    return uploaded


@pytest.fixture
def request_b(
    db_session: Session, second_company: Company, contractor_b: Contractor
) -> Request:
    request = Request(
        client_id=contractor_b.id,
        company_id=second_company.id,
        status="new",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(days=1),
    )
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)
    return request


# ─── Кросс-тенант: пользователь A запрашивает объекты B -> 404 ───────────────


class TestDocumentTenantIsolation:
    def test_act_pdf_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, act_b: Act
    ):
        resp = client.get(f"/api/v1/acts/{act_b.id}/pdf", headers=auth_headers)
        assert resp.status_code == 404

    def test_act_invoice_facture_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, act_b: Act
    ):
        resp = client.get(
            f"/api/v1/acts/{act_b.id}/invoice-facture", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_act_upd_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, act_b: Act
    ):
        resp = client.get(f"/api/v1/acts/{act_b.id}/upd", headers=auth_headers)
        assert resp.status_code == 404

    def test_act_torg12_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, act_b: Act
    ):
        resp = client.get(f"/api/v1/acts/{act_b.id}/torg12", headers=auth_headers)
        assert resp.status_code == 404

    def test_file_download_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, file_b: UploadedFile
    ):
        resp = client.get(f"/api/v1/files/download/{file_b.id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_file_presigned_url_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, file_b: UploadedFile
    ):
        resp = client.get(
            f"/api/v1/files/presigned-url/{file_b.id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_file_delete_foreign_returns_404_and_file_survives(
        self,
        client: TestClient,
        auth_headers: dict,
        file_b: UploadedFile,
        db_session: Session,
    ):
        resp = client.delete(f"/api/v1/files/{file_b.id}", headers=auth_headers)
        assert resp.status_code == 404
        # Факт из БД: чужой файл НЕ удалён
        db_session.expire_all()
        assert db_session.get(UploadedFile, file_b.id) is not None

    def test_export_request_report_foreign_returns_404(
        self, client: TestClient, auth_headers: dict, request_b: Request
    ):
        resp = client.get(
            f"/api/v1/export/requests/{request_b.id}/report", headers=auth_headers
        )
        assert resp.status_code == 404


# ─── Positive-control: свой объект доступен (проверка владельца реальная) ───


class TestOwnDocumentAccess:
    def test_own_act_pdf_returns_200(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        company: Company,
    ):
        contractor = Contractor(
            name="Client A LLC",
            inn="7701111113",
            type="client",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.flush()

        act = Act(
            document_number="ACT-ISOLATION-A-0001",
            client_id=contractor.id,
            company_id=company.id,
            total_amount=Decimal("2000.00"),
            act_date=date.today(),
        )
        db_session.add(act)
        db_session.commit()
        db_session.refresh(act)

        resp = client.get(f"/api/v1/acts/{act.id}/pdf", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.content.startswith(b"%PDF")
