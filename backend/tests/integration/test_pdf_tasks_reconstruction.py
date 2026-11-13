"""Реконструкция pdf_tasks: свои генераторы, tenant-проверки, retry-политика.

Реальные Invoice/Act/Payout двух компаний в БД; моки только внешних сервисов
(PDF-генератор, S3 upload). Задачи вызываются напрямую через task.run().
self.retry мокается: вне worker-контекста Celery re-raise'ит исходное исключение,
поэтому факт retry проверяем по вызову self.retry(exc=...).
"""

import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Act, DocumentStatus, Invoice, Payout
from app.models.telematics import UploadedFile
from app.tasks.pdf_tasks import (
    generate_act_pdf_async,
    generate_invoice_pdf_async,
    generate_payout_pdf_async,
)

pytestmark = [pytest.mark.integration]

PDF_BYTES = b"%PDF-1.4 mock content for reconstruction tests"
UPLOAD_RESULT = {
    "path": "finance/test/2026/01/01/uuid.pdf",
    "url": "http://localhost:9000/bucket/finance/test/uuid.pdf",
    "size": len(PDF_BYTES),
}

GEN_INVOICE = "app.services.pdf_service.generate_invoice_pdf"
GEN_ACT = "app.services.pdf_service.generate_act_pdf"
GEN_PAYOUT = "app.services.pdf_service.generate_payout_pdf"
UPLOAD = "app.services.storage_service.upload_file"


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="PDF Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999989",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def pdf_docs(db_session: Session, company: Company, second_company: Company):
    """Реальные документы двух компаний: по одному каждого типа на компанию."""
    ca = Contractor(
        name="PDF Client A", inn="7709999991", type="client", company_id=company.id
    )
    cb = Contractor(
        name="PDF Client B",
        inn="7709999992",
        type="client",
        company_id=second_company.id,
    )
    va = Vehicle(
        name="Техника PDF A",
        company_id=company.id,
        status="free",
        id_type="internal",
        id_value="PDF-A-1",
    )
    vb = Vehicle(
        name="Техника PDF B",
        company_id=second_company.id,
        status="free",
        id_type="internal",
        id_value="PDF-B-1",
    )
    db_session.add_all([ca, cb, va, vb])
    db_session.flush()

    docs = {}
    for key, comp, contr, veh in (
        ("a", company, ca, va),
        ("b", second_company, cb, vb),
    ):
        inv = Invoice(
            document_number=f"INV-PDF-{key.upper()}",
            client_id=contr.id,
            company_id=comp.id,
            subtotal=Decimal("1000.00"),
            vat_amount=Decimal("200.00"),
            vat_rate=Decimal("20.00"),
            total=Decimal("1200.00"),
            invoice_date=date.today(),
            status="draft",
        )
        act = Act(
            document_number=f"ACT-PDF-{key.upper()}",
            client_id=contr.id,
            company_id=comp.id,
            total_amount=Decimal("1000.00"),
            act_date=date.today(),
        )
        payout = Payout(
            document_number=f"PAY-PDF-{key.upper()}",
            owner_id=contr.id,
            vehicle_id=veh.id,
            company_id=comp.id,
            gross_amount=Decimal("100000.00"),
            platform_commission=Decimal("15000.00"),
            net_amount=Decimal("85000.00"),
            commission_rate=Decimal("15.00"),
            payout_date=date.today(),
            status=DocumentStatus.draft,
            calculation_details={"test": True},
        )
        db_session.add_all([inv, act, payout])
        docs[f"inv_{key}"], docs[f"act_{key}"], docs[f"pay_{key}"] = inv, act, payout
    db_session.commit()
    for obj in docs.values():
        db_session.refresh(obj)
    return docs


def _cleanup_local(result: dict):
    path = result.get("local_path")
    if path and os.path.exists(path):
        os.remove(path)


class TestInvoicePdfTask:
    def test_own_success_generator_file_and_db(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()  # освобождаем SQLite-лок перед сессией задачи
        inv = pdf_docs["inv_a"]
        with (
            patch(GEN_INVOICE, return_value=PDF_BYTES) as gen,
            patch(UPLOAD, return_value=UPLOAD_RESULT) as up,
        ):
            result = generate_invoice_pdf_async.run(inv.id, company.id)
        try:
            assert result["status"] == "success"
            gen.assert_called_once()
            assert gen.call_args[0][0].id == inv.id
            # Файл на диске НЕ пустой
            assert os.path.getsize(result["local_path"]) > 0
            assert (
                up.call_args.kwargs["filename"] == f"invoice_{inv.document_number}.pdf"
            )
            # DB-факт: метаданные с правильной категорией и связью
            db_session.expire_all()
            row = (
                db_session.query(UploadedFile)
                .filter(UploadedFile.invoice_id == inv.id)
                .one()
            )
            assert row.file_category == "invoice_pdf"
            assert row.company_id == company.id
        finally:
            _cleanup_local(result)

    def test_foreign_company_mismatch_no_generator_no_retry(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        inv_b = pdf_docs["inv_b"]
        with (
            patch(GEN_INVOICE) as gen,
            patch(UPLOAD) as up,
            patch.object(generate_invoice_pdf_async, "retry") as mock_retry,
        ):
            result = generate_invoice_pdf_async.run(inv_b.id, company.id)
        assert result["status"] == "error"
        assert result["reason"] == "company_mismatch"
        gen.assert_not_called()
        up.assert_not_called()
        mock_retry.assert_not_called()
        db_session.expire_all()
        assert (
            db_session.query(UploadedFile)
            .filter(UploadedFile.invoice_id == inv_b.id)
            .count()
            == 0
        )

    def test_not_found_no_retry(self, db_session: Session, company: Company):
        db_session.commit()
        with (
            patch(GEN_INVOICE) as gen,
            patch.object(generate_invoice_pdf_async, "retry") as mock_retry,
        ):
            result = generate_invoice_pdf_async.run(999999, company.id)
        assert result["status"] == "error"
        assert result["reason"] == "not_found"
        gen.assert_not_called()
        mock_retry.assert_not_called()

    def test_transient_failure_retries(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        inv = pdf_docs["inv_a"]
        with (
            patch(GEN_INVOICE, side_effect=RuntimeError("boom")),
            patch.object(
                generate_invoice_pdf_async, "retry", side_effect=Retry("scheduled")
            ) as mock_retry,
        ):
            with pytest.raises(Retry):
                generate_invoice_pdf_async.run(inv.id, company.id)
        mock_retry.assert_called_once()
        assert isinstance(mock_retry.call_args.kwargs["exc"], RuntimeError)


class TestActPdfTask:
    def test_own_success_generator_file_and_db(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        act = pdf_docs["act_a"]
        with (
            patch(GEN_ACT, return_value=PDF_BYTES) as gen,
            patch(UPLOAD, return_value=UPLOAD_RESULT) as up,
        ):
            result = generate_act_pdf_async.run(act.id, company.id)
        try:
            assert result["status"] == "success"
            gen.assert_called_once()
            assert gen.call_args[0][0].id == act.id
            assert os.path.getsize(result["local_path"]) > 0
            assert up.call_args.kwargs["filename"] == f"act_{act.document_number}.pdf"
            db_session.expire_all()
            row = (
                db_session.query(UploadedFile)
                .filter(UploadedFile.act_id == act.id)
                .one()
            )
            assert row.file_category == "act_pdf"
            assert row.company_id == company.id
        finally:
            _cleanup_local(result)

    def test_foreign_company_mismatch_no_generator_no_retry(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        act_b = pdf_docs["act_b"]
        with (
            patch(GEN_ACT) as gen,
            patch(UPLOAD) as up,
            patch.object(generate_act_pdf_async, "retry") as mock_retry,
        ):
            result = generate_act_pdf_async.run(act_b.id, company.id)
        assert result["reason"] == "company_mismatch"
        gen.assert_not_called()
        up.assert_not_called()
        mock_retry.assert_not_called()

    def test_not_found_no_retry(self, db_session: Session, company: Company):
        db_session.commit()
        with (
            patch(GEN_ACT) as gen,
            patch.object(generate_act_pdf_async, "retry") as mock_retry,
        ):
            result = generate_act_pdf_async.run(999999, company.id)
        assert result["reason"] == "not_found"
        gen.assert_not_called()
        mock_retry.assert_not_called()

    def test_transient_failure_retries(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        with (
            patch(GEN_ACT, side_effect=RuntimeError("boom")),
            patch.object(
                generate_act_pdf_async, "retry", side_effect=Retry("scheduled")
            ) as mock_retry,
        ):
            with pytest.raises(Retry):
                generate_act_pdf_async.run(pdf_docs["act_a"].id, company.id)
        mock_retry.assert_called_once()
        assert isinstance(mock_retry.call_args.kwargs["exc"], RuntimeError)


class TestPayoutPdfTask:
    def test_own_success_generator_file_and_db(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        pay = pdf_docs["pay_a"]
        with (
            patch(GEN_PAYOUT, return_value=PDF_BYTES) as gen,
            patch(UPLOAD, return_value=UPLOAD_RESULT) as up,
        ):
            result = generate_payout_pdf_async.run(pay.id, company.id)
        try:
            assert result["status"] == "success"
            gen.assert_called_once()
            assert gen.call_args[0][0].id == pay.id
            assert os.path.getsize(result["local_path"]) > 0
            # payout_id восстановим из folder в storage_path
            assert up.call_args.kwargs["folder"] == f"finance/payouts/{pay.id}"
            assert (
                up.call_args.kwargs["filename"] == f"payout_{pay.document_number}.pdf"
            )
            db_session.expire_all()
            row = (
                db_session.query(UploadedFile)
                .filter(UploadedFile.storage_path == UPLOAD_RESULT["path"])
                .one()
            )
            assert row.file_category == "payout_pdf"
            assert row.company_id == company.id
            assert row.invoice_id is None
        finally:
            _cleanup_local(result)

    def test_foreign_company_mismatch_no_generator_no_retry(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        pay_b = pdf_docs["pay_b"]
        with (
            patch(GEN_PAYOUT) as gen,
            patch(UPLOAD) as up,
            patch.object(generate_payout_pdf_async, "retry") as mock_retry,
        ):
            result = generate_payout_pdf_async.run(pay_b.id, company.id)
        assert result["reason"] == "company_mismatch"
        gen.assert_not_called()
        up.assert_not_called()
        mock_retry.assert_not_called()

    def test_not_found_no_retry(self, db_session: Session, company: Company):
        db_session.commit()
        with (
            patch(GEN_PAYOUT) as gen,
            patch.object(generate_payout_pdf_async, "retry") as mock_retry,
        ):
            result = generate_payout_pdf_async.run(999999, company.id)
        assert result["reason"] == "not_found"
        gen.assert_not_called()
        mock_retry.assert_not_called()

    def test_transient_failure_retries(
        self, db_session: Session, company: Company, pdf_docs: dict
    ):
        db_session.commit()
        with (
            patch(GEN_PAYOUT, side_effect=RuntimeError("boom")),
            patch.object(
                generate_payout_pdf_async, "retry", side_effect=Retry("scheduled")
            ) as mock_retry,
        ):
            with pytest.raises(Retry):
                generate_payout_pdf_async.run(pdf_docs["pay_a"].id, company.id)
        mock_retry.assert_called_once()
        assert isinstance(mock_retry.call_args.kwargs["exc"], RuntimeError)
