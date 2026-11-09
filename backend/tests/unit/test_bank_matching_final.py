"""Comprehensive tests for bank_matching_service -> 95%+."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.bank_matching_service import BankMatchingService


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    return db


def _tx(**kw):
    d = dict(id=1, amount="10000.00", purpose="Оплата по счету INV-2024-001",
             counterparty_inn=None, document_type="incoming",
             match_status=None, match_confidence=None,
             matched_invoice_id=None, matched_payout_id=None)
    d.update(kw)
    return SimpleNamespace(**d)


class TestExtractInvoiceNumber:
    def test_none_purpose(self):
        assert BankMatchingService.extract_invoice_number(None) is None

    def test_empty_purpose(self):
        assert BankMatchingService.extract_invoice_number("") is None

    def test_inv_pattern(self):
        assert BankMatchingService.extract_invoice_number("Оплата INV-2024-001") == "2024-001"

    def test_sch_pattern(self):
        r = BankMatchingService.extract_invoice_number("Оплата по счету № 42")
        assert r == "42"

    def test_po_schetu_pattern(self):
        r = BankMatchingService.extract_invoice_number("по счету № ABC-123")
        assert r == "ABC-123"

    def test_no_match(self):
        assert BankMatchingService.extract_invoice_number("Перевод средств") is None


class TestMatchTransactionExclusions:
    def test_bank_commission(self, mock_db):
        tx = _tx(purpose="Комиссия банка за обслуживание")
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]
        assert "Служебная" in r["reason"]

    def test_fns(self, mock_db):
        tx = _tx(purpose="Уплата в ФНС")
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]

    def test_penalty(self, mock_db):
        tx = _tx(purpose="Пени по налогу")
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]


class TestMatchByInvoiceNumber:
    """Strategy 1: match by invoice number in purpose."""

    def test_found_by_number(self, mock_db):
        tx = _tx(purpose="Оплата по счету INV-2024-001")
        invoice = SimpleNamespace(id=42)
        mock_db.query.return_value.filter.return_value.first.return_value = invoice
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert r["matched"]
        assert r["match_type"] == "invoice"
        assert r["matched_id"] == 42
        assert r["confidence"] == 0.95

    def test_not_found_by_number(self, mock_db):
        tx = _tx(purpose="Оплата по счету INV-9999-999", counterparty_inn=None)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        # Also no invoices by amount
        mock_db.query.return_value.filter.return_value.all.return_value = []
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]


class TestMatchByAmountAndINN:
    """Strategy 2: match by amount + counterparty INN."""

    def test_incoming_invoice_match(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Оплата товаров", counterparty_inn="7701234567",
                 document_type=TransactionDirection.incoming)
        contractor = SimpleNamespace(id=10)
        invoice = SimpleNamespace(id=55)
        # First query: contractor found; second query: invoice found
        mock_db.query.return_value.filter.return_value.first.side_effect = [contractor, invoice]
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert r["matched"]
        assert r["match_type"] == "invoice"
        assert r["confidence"] == 0.85

    def test_outgoing_payout_match(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Выплата владельцу", counterparty_inn="7701234567",
                 document_type=TransactionDirection.outgoing)
        contractor = SimpleNamespace(id=10)
        payout = SimpleNamespace(id=77)
        mock_db.query.return_value.filter.return_value.first.side_effect = [contractor, payout]
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert r["matched"]
        assert r["match_type"] == "payout"
        assert r["confidence"] == 0.85

    def test_contractor_not_found(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Оплата", counterparty_inn="9999999999",
                 document_type=TransactionDirection.incoming)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]


class TestMatchByAmountOnly:
    """Strategy 3: match by amount only (low confidence)."""

    def test_single_invoice_match(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Перевод", counterparty_inn=None,
                 document_type=TransactionDirection.incoming)
        invoice = SimpleNamespace(id=99)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = [invoice]
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert r["matched"]
        assert r["confidence"] == 0.6

    def test_multiple_invoices_no_match(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Перевод", counterparty_inn=None,
                 document_type=TransactionDirection.incoming)
        inv1 = SimpleNamespace(id=1)
        inv2 = SimpleNamespace(id=2)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = [inv1, inv2]
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]
        assert "ручной выбор" in r["reason"]

    def test_outgoing_no_amount_match(self, mock_db):
        from app.models.bank_statement import TransactionDirection
        tx = _tx(purpose="Перевод", counterparty_inn=None,
                 document_type=TransactionDirection.outgoing)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        r = BankMatchingService.match_transaction(mock_db, tx, 1)
        assert not r["matched"]


class TestApplyMatch:
    def test_apply_invoice_match(self, mock_db):
        tx = _tx()
        invoice = SimpleNamespace(id=42, paid_amount="0", total="10000.00", status="sent")
        mock_db.get.return_value = invoice
        match_result = {"matched": True, "match_type": "invoice",
                       "matched_id": 42, "confidence": 0.95}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert tx.match_status.value == "auto_matched"
        assert tx.matched_invoice_id == 42
        mock_db.commit.assert_called()

    def test_apply_invoice_partial_payment(self, mock_db):
        tx = _tx(amount="5000.00")
        invoice = SimpleNamespace(id=42, paid_amount="3000.00", total="10000.00", status="sent")
        mock_db.get.return_value = invoice
        match_result = {"matched": True, "match_type": "invoice",
                       "matched_id": 42, "confidence": 0.95}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert invoice.status.value == "partially_paid"

    def test_apply_invoice_full_payment(self, mock_db):
        tx = _tx(amount="10000.00")
        invoice = SimpleNamespace(id=42, paid_amount="0", total="10000.00", status="sent")
        mock_db.get.return_value = invoice
        match_result = {"matched": True, "match_type": "invoice",
                       "matched_id": 42, "confidence": 0.95}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert invoice.status.value == "paid"

    def test_apply_payout_match(self, mock_db):
        tx = _tx()
        match_result = {"matched": True, "match_type": "payout",
                       "matched_id": 77, "confidence": 0.85}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert tx.matched_payout_id == 77
        mock_db.commit.assert_called()

    def test_apply_unmatched(self, mock_db):
        tx = _tx()
        match_result = {"matched": False, "match_type": None,
                       "matched_id": None, "confidence": 0.0}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert tx.match_status.value == "unmatched"
        mock_db.commit.assert_called()

    def test_apply_invoice_not_found(self, mock_db):
        tx = _tx()
        mock_db.get.return_value = None
        match_result = {"matched": True, "match_type": "invoice",
                       "matched_id": 999, "confidence": 0.95}
        BankMatchingService.apply_match(mock_db, tx, match_result)
        assert tx.matched_invoice_id == 999
