"""Tests for payments_service coverage improvement."""

import pytest
from decimal import Decimal
from datetime import date


class TestPaymentsServiceInit:
    """Cover __init__ (lines 43-50)."""

    def test_init(self):
        from app.services.payments_service import PaymentsService
        svc = PaymentsService("40702810000000000001")
        assert svc is not None
        # parser may be None if ClientBankExchangeParser not available
        assert hasattr(svc, "parser")


def _create_statement_and_tx(db_session, company):
    """Helper to create BankStatement + BankTransaction for tests."""
    from app.models.bank_statement import (
        BankStatement, BankTransaction, TransactionDirection, MatchStatus, StatementStatus, TransactionType,
    )

    stmt_obj = BankStatement(
        company_id=company.id,
        file_name="test.xml",
        file_size=1024,
        storage_path="/tmp/test.xml",
        account_number="40702810000000000001",
        date_start=date(2025, 1, 1),
        date_end=date(2025, 1, 31),
        status=StatementStatus.processing,
    )
    db_session.add(stmt_obj)
    db_session.flush()

    tx = BankTransaction(
        statement_id=stmt_obj.id,
        company_id=company.id,
        bank_transaction_id="TX-TEST-001",
        document_type=TransactionType.payment_order,
        document_number="PP-001",
        document_date=date(2025, 1, 15),
        direction=TransactionDirection.incoming,
        amount=Decimal("50000"),
        processed_date=date(2025, 1, 15),
        counterparty_name="Test Client LLC",
        counterparty_inn="7700000001",
        counterparty_account="40702810000000000002",
        purpose="РћРїР»Р°С‚Р° РїРѕ СЃС‡С‘С‚Сѓ TEST-2026-0001",
        match_status=MatchStatus.unmatched,
        is_excluded=False,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


class TestApplyPayment:
    """Cover apply_payment method (lines 219-310)."""

    def test_apply_payment_not_found_tx(self, db_session):
        from app.services.payments_service import PaymentsService
        svc = PaymentsService("40702810000000000001")
        with pytest.raises(ValueError, match="Transaction.*not found"):
            svc.apply_payment(db_session, 99999, 1)

    def test_apply_payment_not_found_invoice(self, db_session, company):
        from app.services.payments_service import PaymentsService
        tx = _create_statement_and_tx(db_session, company)
        svc = PaymentsService("40702810000000000001")
        with pytest.raises(ValueError, match="Invoice.*not found"):
            svc.apply_payment(db_session, tx.id, 99999)

    def test_apply_payment_different_company(
        self, db_session, sample_invoice, company
    ):
        from app.services.payments_service import PaymentsService
        tx = _create_statement_and_tx(db_session, company)
        svc = PaymentsService("40702810000000000001")
        sample_invoice.company_id = 99999
        db_session.commit()
        with pytest.raises(ValueError, match="different companies"):
            svc.apply_payment(db_session, tx.id, sample_invoice.id)

    def test_apply_payment_success(
        self, db_session, sample_invoice, company
    ):
        from app.services.payments_service import PaymentsService
        from app.models.finance import DocumentStatus

        tx = _create_statement_and_tx(db_session, company)
        svc = PaymentsService("40702810000000000001")
        payment = svc.apply_payment(db_session, tx.id, sample_invoice.id)
        assert payment.amount > 0
        assert payment.invoice_id == sample_invoice.id
        db_session.refresh(sample_invoice)
        assert sample_invoice.status in (
            DocumentStatus.paid, DocumentStatus.partially_paid
        )

    def test_apply_payment_exceeds_remaining(
        self, db_session, sample_invoice, company
    ):
        from app.services.payments_service import PaymentsService

        tx = _create_statement_and_tx(db_session, company)
        tx.amount = Decimal("999999")
        db_session.commit()
        svc = PaymentsService("40702810000000000001")
        payment = svc.apply_payment(db_session, tx.id, sample_invoice.id)
        assert float(payment.amount) <= float(sample_invoice.total)


class TestGetUnmatchedTransactions:
    """Cover get_unmatched_transactions (lines 314+)."""

    def test_returns_list(self, db_session, company):
        from app.services.payments_service import PaymentsService
        svc = PaymentsService("40702810000000000001")
        result = svc.get_unmatched_transactions(db_session, company.id)
        assert isinstance(result, list)

    def test_with_limit_offset(self, db_session, company):
        from app.services.payments_service import PaymentsService
        svc = PaymentsService("40702810000000000001")
        result = svc.get_unmatched_transactions(
            db_session, company.id, limit=5, offset=0
        )
        assert isinstance(result, list)
        assert len(result) <= 5


class TestAutoMatchTransactions:
    """Cover auto_match_transactions (lines 171-217)."""

    def test_auto_match_no_parser(self, db_session, company):
        from app.services.payments_service import PaymentsService
        import app.services.payments_service as ps_mod

        original = ps_mod.extract_invoice_numbers_from_purpose
        ps_mod.extract_invoice_numbers_from_purpose = None
        try:
            svc = PaymentsService("40702810000000000001")
            result = svc.auto_match_transactions(db_session, 99999)
            assert result == 0
        finally:
            ps_mod.extract_invoice_numbers_from_purpose = original

    def test_auto_match_no_transactions(self, db_session, company):
        from app.services.payments_service import PaymentsService
        svc = PaymentsService("40702810000000000001")
        result = svc.auto_match_transactions(db_session, 99999)
        assert result == 0

