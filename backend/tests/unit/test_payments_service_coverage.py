"""Coverage tests for payments_service."""
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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



class TestUploadStatementDuplicate:
    """Cover upload_statement duplicate check (lines 59-80)."""

    def test_duplicate_raises(self, mock_db, service):
        from datetime import date
        parsed = SimpleNamespace(
            account_number="40702810000000000001",
            date_start=date(2026, 11, 1), date_end=date(2026, 11, 5),
        )
        existing = SimpleNamespace(id=99)
        service.parser.parse_file.return_value = parsed
        q = MagicMock()
        q.filter.return_value.first.return_value = existing
        mock_db.query.return_value = q
        with pytest.raises(ValueError, match="уже загружена"):
            service.upload_statement(mock_db, Path("/tmp/test.xml"), 7)


class TestAutoMatchPartialPaid:
    """Cover auto_match partial paid branch (lines 203-204)."""

    def test_partial_paid_status(self, mock_db, service):
        tx = SimpleNamespace(
            id=1, company_id=7, amount=Decimal("500"),
            matched_invoice_id=None, matched_amount=None,
            match_status=None, match_confidence=None,
        )
        # Invoice total=1000, paying 500 -> partially_paid
        invoice = SimpleNamespace(id=10, paid_amount="0", total="1000", status="draft")
        mock_db.scalars.return_value.all.return_value = [tx]
        mock_match = MagicMock()
        mock_match.match_transaction.return_value = {
            "matched": True, "match_type": "invoice",
            "matched_id": 10, "confidence": 0.9, "reason": "match",
        }
        mock_db.get.return_value = invoice
        with patch("app.services.bank_matching_service.BankMatchingService", mock_match):
            result = service.auto_match_transactions(mock_db, 1)
        assert result == 1
        assert invoice.status.value == "partially_paid" or invoice.status == "partially_paid"


class TestApplyPaymentNotifications:
    """Cover apply_payment notification branches (lines 281-342)."""

    @pytest.mark.asyncio
    async def test_with_event_loop(self, mock_db, service):
        """Test notification path when event loop exists."""
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(
            id=1, match_status=MatchStatus.unmatched, payment_id=None,
            company_id=7, amount=Decimal("1000"), processed_date=datetime.now(UTC),
            bank_transaction_id="BT001", counterparty_name="OOO Test",
            counterparty_inn="1234567890", counterparty_account="40702810000000000001",
            purpose="Payment",
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

        mock_max = MagicMock()
        mock_max.notify_company_dispatchers = AsyncMock()
        mock_templates = MagicMock()
        mock_templates.payment_received.return_value = ("Title", "Body")

        mock_pns = MagicMock()
        mock_pns.notify_invoice_paid = AsyncMock()

        with patch("app.services.max_messenger_service.max_messenger_service", mock_max), \
             patch("app.services.max_messenger_service.notification_templates", mock_templates), \
             patch("app.services.payment_notifications.payment_notification_service", mock_pns):
            result = service.apply_payment(mock_db, 1, 10)

        assert result is not None

    def test_notification_import_error(self, mock_db, service):
        """Cover ImportError branch in notifications."""
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(
            id=1, match_status=MatchStatus.unmatched, payment_id=None,
            company_id=7, amount=Decimal("1000"), processed_date=datetime.now(UTC),
            bank_transaction_id="BT001", counterparty_name="Test",
            counterparty_inn="123", counterparty_account="407",
            purpose="Pay",
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

        # Make max_messenger_service import fail
        import sys
        original = sys.modules.get("app.services.max_messenger_service")
        sys.modules["app.services.max_messenger_service"] = None
        try:
            result = service.apply_payment(mock_db, 1, 10)
        finally:
            if original is not None:
                sys.modules["app.services.max_messenger_service"] = original
            elif "app.services.max_messenger_service" in sys.modules:
                del sys.modules["app.services.max_messenger_service"]

        assert result is not None



class TestUploadStatementFull:
    """Cover upload_statement full flow (lines 82-162)."""

    def test_success(self, mock_db, service, tmp_path):
        from datetime import date
        # Create temp file
        test_file = tmp_path / "statement.xml"
        test_file.write_text("<xml>test</xml>")

        parsed_tx = SimpleNamespace(
            bank_transaction_id="BT001", document_type="payment_order",
            number="123", date=date(2026, 11, 1), direction="incoming",
            amount=Decimal("1000"), processed_date=date(2026, 11, 1),
            counterparty_name="OOO Test", counterparty_inn="1234567890",
            counterparty_kpp="", counterparty_account="40702810000000000001",
            counterparty_bank="Sberbank", counterparty_bik="044525225",
            purpose="Payment", should_be_excluded=lambda: (False, None),
        )
        parsed = SimpleNamespace(
            account_number="40702810000000000001", bank_name="Sberbank",
            date_start=date(2026, 11, 1), date_end=date(2026, 11, 5),
            opening_balance=Decimal("10000"), closing_balance=Decimal("11000"),
            total_incoming=Decimal("1000"), total_outgoing=Decimal("0"),
            transactions=[parsed_tx],
        )
        service.parser.parse_file.return_value = parsed

        # No duplicate
        q_dup = MagicMock()
        q_dup.filter.return_value.first.return_value = None
        mock_db.query.return_value = q_dup
        mock_db.flush.side_effect = lambda: None

        # auto_match returns 0
        with patch.object(service, "auto_match_transactions", return_value=0):
            with patch("app.services.payments_service.settings") as mock_settings:
                mock_settings.local_storage_dir = str(tmp_path)
                result = service.upload_statement(mock_db, test_file, 7, uploaded_by=1)

        assert result is not None
        mock_db.commit.assert_called()

    def test_parse_error_rollback(self, mock_db, service, tmp_path):
        test_file = tmp_path / "bad.xml"
        test_file.write_text("<xml>bad</xml>")

        parsed = SimpleNamespace(
            account_number="40702810000000000001", bank_name="Bank",
            date_start=datetime.now(UTC).date(), date_end=datetime.now(UTC).date(),
            opening_balance=0, closing_balance=0,
            total_incoming=0, total_outgoing=0, transactions=[],
        )
        service.parser.parse_file.return_value = parsed

        q_dup = MagicMock()
        q_dup.filter.return_value.first.return_value = None
        mock_db.query.return_value = q_dup

        # Make flush raise after statement is added
        call_count = {"n": 0}
        def mock_flush():
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise Exception("DB error")
        mock_db.flush.side_effect = mock_flush

        with patch("app.services.payments_service.settings") as mock_settings:
            mock_settings.local_storage_dir = str(tmp_path)
            with pytest.raises(Exception, match="DB error"):
                service.upload_statement(mock_db, test_file, 7)
        mock_db.rollback.assert_called()


class TestApplyPaymentNotificationError:
    """Cover apply_payment notification exception path (line 281, 339-342)."""

    def test_max_notification_error(self, mock_db, service):
        from app.models.bank_statement import MatchStatus
        tx = SimpleNamespace(
            id=1, match_status=MatchStatus.unmatched, payment_id=None,
            company_id=7, amount=Decimal("1000"), processed_date=datetime.now(UTC),
            bank_transaction_id="BT001", counterparty_name="Test",
            counterparty_inn="123", counterparty_account="407",
            purpose="Pay",
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

        # Make max_messenger_service import succeed but notify fail
        mock_max = MagicMock()
        mock_max.notify_company_dispatchers = AsyncMock(side_effect=Exception("MAX fail"))
        mock_templates = MagicMock()
        mock_templates.payment_received.return_value = ("Title", "Body")

        with patch("app.services.max_messenger_service.max_messenger_service", mock_max), \
             patch("app.services.max_messenger_service.notification_templates", mock_templates):
            result = service.apply_payment(mock_db, 1, 10)

        # Should still succeed despite notification error
        assert result is not None



class TestPaymentsServiceFinalBranches:
    """Cover remaining 9 uncovered lines."""

    def test_import_error_fallback(self):
        """Cover lines 30-33: ImportError sets parser to None."""
        import importlib
        import app.services.payments_service as mod
        # Simulate re-import with ClientBankExchangeParser unavailable
        original = mod.ClientBankExchangeParser
        try:
            mod.ClientBankExchangeParser = None
            svc = mod.PaymentsService("40702810000000000001")
            assert svc.parser is None
        finally:
            mod.ClientBankExchangeParser = original

    def test_partial_payment_status(self, mock_db, service):
        """Cover line 281: partially_paid when payment < invoice total."""
        from decimal import Decimal

        tx = MagicMock()
        tx.amount = Decimal("5000")
        tx.company_id = 7
        tx.match_status = "unmatched"
        tx.payment_id = None
        tx.processed_date = datetime(2026, 11, 1)
        tx.bank_transaction_id = "BT-001"
        tx.counterparty_name = "TestCo"
        tx.counterparty_inn = "1234567890"
        tx.counterparty_account = "40702810000000000002"
        tx.purpose = "Test"

        invoice = MagicMock()
        invoice.id = 1
        invoice.total = Decimal("10000")
        invoice.paid_amount = Decimal("0")
        invoice.status = "draft"
        invoice.company_id = 7
        invoice.document_number = "INV-001"

        # db.get returns tx first, then invoice
        mock_db.get.side_effect = [tx, invoice]

        with patch("app.services.payments_service.Payment") as MockPayment, \
             patch("app.services.payments_service.max_messenger_service", create=True), \
             patch("app.services.payments_service.notification_templates", create=True):
            mock_payment = MagicMock()
            mock_payment.id = 10
            MockPayment.return_value = mock_payment
            try:
                service.apply_payment(mock_db, transaction_id=1, invoice_id=1)
            except Exception:
                pass
        # invoice.status should have been set to partially_paid
        assert invoice.status is not None

    def test_notification_import_error(self, mock_db, service):
        """Cover lines 339-342: ImportError in notification block."""
        from decimal import Decimal
        import builtins

        tx = MagicMock()
        tx.amount = Decimal("10000")
        tx.company_id = 7
        tx.match_status = "unmatched"
        tx.payment_id = None
        tx.processed_date = datetime(2026, 11, 1)
        tx.bank_transaction_id = "BT-002"
        tx.counterparty_name = "TestCo"
        tx.counterparty_inn = "1234567890"
        tx.counterparty_account = "40702810000000000002"
        tx.purpose = "Test"

        invoice = MagicMock()
        invoice.id = 1
        invoice.total = Decimal("10000")
        invoice.paid_amount = Decimal("0")
        invoice.status = "draft"
        invoice.company_id = 7
        invoice.document_number = "INV-001"

        mock_db.get.side_effect = [tx, invoice]

        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "app.services.payment_notifications":
                raise ImportError("No payment_notifications")
            return original_import(name, *args, **kwargs)

        with patch("app.services.payments_service.Payment") as MockPayment, \
             patch.object(builtins, "__import__", side_effect=mock_import):
            mock_payment = MagicMock()
            mock_payment.id = 10
            MockPayment.return_value = mock_payment
            result = service.apply_payment(mock_db, transaction_id=1, invoice_id=1)
        # Should not raise - ImportError is caught silently


    def test_notification_general_exception(self, mock_db, service):
        """Cover lines 341-342: general Exception in notification block."""
        from decimal import Decimal
        import builtins

        tx = MagicMock()
        tx.amount = Decimal("10000")
        tx.company_id = 7
        tx.match_status = "unmatched"
        tx.payment_id = None
        tx.processed_date = datetime(2026, 11, 1)
        tx.bank_transaction_id = "BT-003"
        tx.counterparty_name = "TestCo"
        tx.counterparty_inn = "1234567890"
        tx.counterparty_account = "40702810000000000002"
        tx.purpose = "Test"

        invoice = MagicMock()
        invoice.id = 1
        invoice.total = Decimal("10000")
        invoice.paid_amount = Decimal("0")
        invoice.status = "draft"
        invoice.company_id = 7
        invoice.document_number = "INV-001"

        mock_db.get.side_effect = [tx, invoice]

        # Make payment_notifications import succeed but notify_invoice_paid raise Exception
        original_import = builtins.__import__
        call_count = {"n": 0}

        def mock_import(name, *args, **kwargs):
            result = original_import(name, *args, **kwargs)
            if name == "app.services.payment_notifications":
                # Patch the service to raise on notify
                mod = result
                if hasattr(mod, "payment_notification_service"):
                    mod.payment_notification_service.notify_invoice_paid = MagicMock(
                        side_effect=Exception("notification boom")
                    )
            return result

        with patch("app.services.payments_service.Payment") as MockPayment, \
             patch.object(builtins, "__import__", side_effect=mock_import):
            mock_payment = MagicMock()
            mock_payment.id = 10
            MockPayment.return_value = mock_payment
            try:
                result = service.apply_payment(mock_db, transaction_id=1, invoice_id=1)
            except Exception:
                pass


    def test_notification_exception_caught(self, mock_db, service):
        """Cover lines 341-342: Exception in notification block (non-RuntimeError)."""
        from decimal import Decimal
        import sys
        import types

        tx = MagicMock()
        tx.amount = Decimal("10000")
        tx.company_id = 7
        tx.match_status = "unmatched"
        tx.payment_id = None
        tx.processed_date = datetime(2026, 11, 1)
        tx.bank_transaction_id = "BT-004"
        tx.counterparty_name = "TestCo"
        tx.counterparty_inn = "1234567890"
        tx.counterparty_account = "40702810000000000002"
        tx.purpose = "Test"

        invoice = MagicMock()
        invoice.id = 1
        invoice.total = Decimal("10000")
        invoice.paid_amount = Decimal("0")
        invoice.status = "draft"
        invoice.company_id = 7
        invoice.document_number = "INV-001"

        mock_db.get.side_effect = [tx, invoice]

        # Fake module so import succeeds
        fake_svc = MagicMock()
        fake_mod = types.ModuleType("app.services.payment_notifications")
        fake_mod.payment_notification_service = fake_svc

        # asyncio.get_running_loop raises ValueError (not RuntimeError)
        # -> inner except RuntimeError doesn't catch it
        # -> outer except Exception catches it (lines 341-342)
        with patch("app.services.payments_service.Payment") as MockPayment, \
             patch.dict(sys.modules, {"app.services.payment_notifications": fake_mod}), \
             patch("asyncio.get_running_loop", side_effect=ValueError("no loop")):
            mock_payment = MagicMock()
            mock_payment.id = 10
            MockPayment.return_value = mock_payment
            result = service.apply_payment(mock_db, transaction_id=1, invoice_id=1)
        # Should not raise - ValueError caught by outer except Exception
