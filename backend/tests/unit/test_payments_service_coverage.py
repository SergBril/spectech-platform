"""Coverage tests for payments_service."""
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service():
    from app.services.payments_service import PaymentsService
    with patch("app.services.payments_service.ClientBankExchangeParser"):
        svc = PaymentsService("40702810000000000001")
    return svc


class TestPaymentsServiceInit:
    """Cover __init__ (lines 39-45)."""

    def test_with_parser(self):
        from app.services.payments_service import PaymentsService
        with patch("app.services.payments_service.ClientBankExchangeParser") as MockParser:
            svc = PaymentsService("40702810000000000001")
            MockParser.assert_called_once_with("40702810000000000001")
            assert svc.parser is not None

    def test_without_parser(self):
        from app.services.payments_service import PaymentsService
        with patch("app.services.payments_service.ClientBankExchangeParser", None):
            svc = PaymentsService("40702810000000000001")
            assert svc.parser is None


class TestUploadStatement:
    """Cover upload_statement (lines 46-162)."""

    def test_no_parser_raises(self, mock_db):
        from app.services.payments_service import PaymentsService
        with patch("app.services.payments_service.ClientBankExchangeParser", None):
            svc = PaymentsService("40702810000000000001")
        with pytest.raises(ValueError, match="parser is not available"):
            svc.upload_statement(mock_db, Path("/tmp/test.xml"), 7)


class TestAutoMatchTransactions:
    """Cover auto_match_transactions (lines 164-219)."""

    def test_no_unmatched(self, mock_db, service):
        mock_db.scalars.return_value.all.return_value = []
        result = service.auto_match_transactions(mock_db, 1)
        assert result == 0

    def test_matched_to_invoice(self, mock_db, service):
        tx = SimpleNamespace(
            id=1, company_id=7, amount=Decimal("1000"),
            matched_invoice_id=None, matched_amount=None,
            match_status=None, match_confidence=None,
        )
        invoice = SimpleNamespace(id=10, paid_amount="0", total="1000", status="draft")
        mock_db.scalars.return_value.all.return_value = [tx]
        mock_match = MagicMock()
        mock_match.match_transaction.return_value = {
            "matched": True, "match_type": "invoice",
            "matched_id": 10, "confidence": 0.95, "reason": "amount match",
        }
        mock_db.get.return_value = invoice
        with patch("app.services.bank_matching_service.BankMatchingService", mock_match):
            result = service.auto_match_transactions(mock_db, 1)
        assert result == 1
        mock_db.commit.assert_called()

    def test_unmatched_transaction(self, mock_db, service):
        tx = SimpleNamespace(id=1, company_id=7, amount=Decimal("1000"))
        mock_db.scalars.return_value.all.return_value = [tx]
        mock_match = MagicMock()
        mock_match.match_transaction.return_value = {
            "matched": False, "reason": "no match found",
        }
        with patch("app.services.bank_matching_service.BankMatchingService", mock_match):
            result = service.auto_match_transactions(mock_db, 1)
        assert result == 0

    def test_match_error_continues(self, mock_db, service):
        tx = SimpleNamespace(id=1, company_id=7, amount=Decimal("1000"))
        mock_db.scalars.return_value.all.return_value = [tx]
        mock_match = MagicMock()
        mock_match.match_transaction.side_effect = Exception("DB error")
        with patch("app.services.bank_matching_service.BankMatchingService", mock_match):
            result = service.auto_match_transactions(mock_db, 1)
        assert result == 0


class TestApplyPayment:
    """Cover apply_payment (lines 221-344)."""

    def test_transaction_not_found(self, mock_db, service):
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Transaction.*not found"):
            service.apply_payment(mock_db, 999, 1)

    def test_already_applied(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(match_status=MatchStatus.manual_matched, payment_id=5)
        mock_db.get.return_value = tx
        with pytest.raises(ValueError, match="already applied"):
            service.apply_payment(mock_db, 1, 1)

    def test_invoice_not_found(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(match_status=MatchStatus.unmatched, payment_id=None)
        call_count = {"n": 0}
        def mock_get(model, obj_id):
            call_count["n"] += 1
            return tx if call_count["n"] == 1 else None
        mock_db.get.side_effect = mock_get
        with pytest.raises(ValueError, match="Invoice.*not found"):
            service.apply_payment(mock_db, 1, 999)

    def test_different_companies(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(match_status=MatchStatus.unmatched, payment_id=None, company_id=7)
        invoice = SimpleNamespace(company_id=99)
        call_count = {"n": 0}
        def mock_get(model, obj_id):
            call_count["n"] += 1
            return tx if call_count["n"] == 1 else invoice
        mock_db.get.side_effect = mock_get
        with pytest.raises(ValueError, match="different companies"):
            service.apply_payment(mock_db, 1, 1)

    def test_success_full_payment(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(
            id=1, match_status=MatchStatus.unmatched, payment_id=None,
            company_id=7, amount=Decimal("1000"), processed_date=datetime.now(UTC),
            bank_transaction_id="BT001", counterparty_name="OOO Test",
            counterparty_inn="1234567890", counterparty_account="40702810000000000001",
            purpose="Payment for services",
        )
        invoice = SimpleNamespace(
            id=10, company_id=7, total="1000", paid_amount="0",
            status="draft", document_number="INV-001",
        )
        call_count = {"n": 0}
        def mock_get(model, obj_id):
            call_count["n"] += 1
            return tx if call_count["n"] == 1 else invoice
        mock_db.get.side_effect = mock_get
        mock_db.flush.side_effect = lambda: None
        mock_db.refresh.side_effect = lambda r: None

        with patch("app.services.payments_service.max_messenger_service", create=True), \
             patch("app.services.payments_service.notification_templates", create=True):
            result = service.apply_payment(mock_db, 1, 10)

        assert result is not None
        mock_db.commit.assert_called()

    def test_amount_exceeds_remaining(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(
            id=1, match_status=MatchStatus.unmatched, payment_id=None,
            company_id=7, amount=Decimal("2000"), processed_date=datetime.now(UTC),
            bank_transaction_id="BT001", counterparty_name="Test",
            counterparty_inn="123", counterparty_account="407",
            purpose="Pay",
        )
        invoice = SimpleNamespace(
            id=10, company_id=7, total="1000", paid_amount="500",
            status="draft", document_number="INV-001",
        )
        call_count = {"n": 0}
        def mock_get(model, obj_id):
            call_count["n"] += 1
            return tx if call_count["n"] == 1 else invoice
        mock_db.get.side_effect = mock_get
        mock_db.flush.side_effect = lambda: None
        mock_db.refresh.side_effect = lambda r: None

        with patch("app.services.payments_service.max_messenger_service", create=True), \
             patch("app.services.payments_service.notification_templates", create=True):
            result = service.apply_payment(mock_db, 1, 10)

        assert result is not None


class TestGetUnmatchedTransactions:
    """Cover get_unmatched_transactions (lines 346-363)."""

    def test_returns_list(self, mock_db, service):
        mock_db.scalars.return_value.all.return_value = []
        result = service.get_unmatched_transactions(mock_db, 1)
        assert isinstance(result, list)


class TestFindInvoiceByNumber:
    """Cover _find_invoice_by_number (lines 365-end)."""

    def test_found(self, mock_db, service):
        invoice = SimpleNamespace(id=1)
        # Method may use db.scalar or db.scalars().first()
        mock_db.scalar.return_value = invoice
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = invoice
        mock_db.scalars.return_value = scalars_mock
        result = service._find_invoice_by_number(mock_db, "INV-001", 7)
        assert result is not None

    def test_not_found(self, mock_db, service):
        mock_db.scalar.return_value = None
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        mock_db.scalars.return_value = scalars_mock
        result = service._find_invoice_by_number(mock_db, "INV-999", 7)
        assert result is None
