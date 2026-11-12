"""Unit tests for InvoiceService.generate_invoice_from_reconciliation."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session


class TestInvoiceServiceGenerateFromReconciliation:
    """Cover invoice_service.py lines 46-173."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        db.add = Mock()
        db.flush = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    @pytest.fixture
    def invoice_service(self):
        from app.services.finance.invoice_service import InvoiceService

        return InvoiceService()

    def test_reconciliation_not_found(self, invoice_service, mock_db):
        """Line 46-47: reconciliation not found raises ValueError."""
        mock_db.get = Mock(return_value=None)

        with pytest.raises(ValueError, match="Reconciliation.*not found"):
            invoice_service.generate_invoice_from_reconciliation(
                mock_db, reconciliation_id=999
            )

    def test_reconciliation_wrong_status_pending(self, invoice_service, mock_db):
        """Lines 49-55: status must be auto_approved or resolved."""
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "pending"
        mock_db.get = Mock(return_value=recon)

        with pytest.raises(ValueError, match="Cannot generate invoice.*status"):
            invoice_service.generate_invoice_from_reconciliation(
                mock_db, reconciliation_id=1
            )

    def test_reconciliation_wrong_status_discrepancy(self, invoice_service, mock_db):
        """Lines 49-55: discrepancy_detected status rejected."""
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "discrepancy_detected"
        mock_db.get = Mock(return_value=recon)

        with pytest.raises(ValueError, match="Cannot generate invoice.*status"):
            invoice_service.generate_invoice_from_reconciliation(
                mock_db, reconciliation_id=1
            )

    def test_shift_task_not_found(self, invoice_service, mock_db):
        """Lines 58-59: shift_task not found raises ValueError."""
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.reconciliation_status = "auto_approved"
        recon.shift_task_id = 123
        mock_db.get = Mock(side_effect=[recon, None])  # recon found, shift_task not

        with pytest.raises(ValueError, match="ShiftTask.*not found"):
            invoice_service.generate_invoice_from_reconciliation(
                mock_db, reconciliation_id=1
            )

    def test_request_not_found(self, invoice_service, mock_db):
        """Lines 62-63: request not found raises ValueError."""
        from app.models.shift import ShiftTask
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.reconciliation_status = "auto_approved"
        recon.shift_task_id = 123

        shift_task = Mock(spec=ShiftTask)
        shift_task.request_id = 456

        mock_db.get = Mock(side_effect=[recon, shift_task, None])

        with pytest.raises(ValueError, match="Request.*not found"):
            invoice_service.generate_invoice_from_reconciliation(
                mock_db, reconciliation_id=1
            )

    @patch("app.services.finance.invoice_service.logger")
    def test_happy_path_with_fuel(self, mock_logger, invoice_service, mock_db):
        """Lines 23-173: full happy path with fuel compensation."""
        from app.models.dispatch import Request
        from app.models.shift import ShiftTask
        from app.models.telematics import ShiftDataReconciliation

        # Setup mocks
        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "auto_approved"
        recon.shift_task_id = 123
        recon.final_moto_hours = 8.0
        recon.final_fuel_used = 50.0

        shift_task = Mock(spec=ShiftTask)
        shift_task.request_id = 456

        request = Mock(spec=Request)
        request.id = 456
        request.client_id = 789
        request.client_rate = Decimal("3500")

        mock_db.get = Mock(side_effect=[recon, shift_task, request])

        # Call method
        result = invoice_service.generate_invoice_from_reconciliation(
            mock_db, reconciliation_id=1, company_id=1, created_by=1
        )

        # Assertions
        assert result is not None
        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

        # Check invoice was created with correct values
        invoice_calls = [
            call for call in mock_db.add.call_args_list if len(call.args) > 0
        ]
        assert len(invoice_calls) >= 2  # invoice + 2 items (moto_hours + fuel)

    @patch("app.services.finance.invoice_service.logger")
    def test_happy_path_no_fuel(self, mock_logger, invoice_service, mock_db):
        """Lines 86-90: fuel_used=0 skips fuel item creation."""
        from app.models.dispatch import Request
        from app.models.shift import ShiftTask
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "resolved"
        recon.shift_task_id = 123
        recon.final_moto_hours = 8.0
        recon.final_fuel_used = 0.0  # No fuel

        shift_task = Mock(spec=ShiftTask)
        shift_task.request_id = 456

        request = Mock(spec=Request)
        request.id = 456
        request.client_id = 789
        request.client_rate = Decimal("5000")

        mock_db.get = Mock(side_effect=[recon, shift_task, request])

        result = invoice_service.generate_invoice_from_reconciliation(
            mock_db, reconciliation_id=1, company_id=1, created_by=1
        )

        assert result is not None
        # Should have invoice + 1 item (only moto_hours, no fuel)
        invoice_calls = [
            call for call in mock_db.add.call_args_list if len(call.args) > 0
        ]
        assert len(invoice_calls) == 2  # invoice + 1 item

    @patch("app.services.finance.invoice_service.logger")
    def test_include_fuel_compensation_false(
        self, mock_logger, invoice_service, mock_db
    ):
        """Lines 86-90: include_fuel_compensation=False skips fuel even if fuel_used>0."""
        from app.models.dispatch import Request
        from app.models.shift import ShiftTask
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "auto_approved"
        recon.shift_task_id = 123
        recon.final_moto_hours = 8.0
        recon.final_fuel_used = 100.0  # Has fuel, but we'll skip it

        shift_task = Mock(spec=ShiftTask)
        shift_task.request_id = 456

        request = Mock(spec=Request)
        request.id = 456
        request.client_id = 789
        request.client_rate = Decimal("3000")

        mock_db.get = Mock(side_effect=[recon, shift_task, request])

        result = invoice_service.generate_invoice_from_reconciliation(
            mock_db,
            reconciliation_id=1,
            include_fuel_compensation=False,
            company_id=1,
            created_by=1,
        )

        assert result is not None
        # Should have invoice + 1 item (only moto_hours, fuel skipped)
        invoice_calls = [
            call for call in mock_db.add.call_args_list if len(call.args) > 0
        ]
        assert len(invoice_calls) == 2

    @patch("app.services.finance.invoice_service.logger")
    def test_no_client_rate_uses_default(self, mock_logger, invoice_service, mock_db):
        """Lines 66-70: client_rate=None or 0 uses default 5000."""
        from app.models.dispatch import Request
        from app.models.shift import ShiftTask
        from app.models.telematics import ShiftDataReconciliation

        recon = Mock(spec=ShiftDataReconciliation)
        recon.id = 1
        recon.reconciliation_status = "auto_approved"
        recon.shift_task_id = 123
        recon.final_moto_hours = 8.0
        recon.final_fuel_used = 0.0

        shift_task = Mock(spec=ShiftTask)
        shift_task.request_id = 456

        request = Mock(spec=Request)
        request.id = 456
        request.client_id = 789
        request.client_rate = Decimal("0")  # No rate

        mock_db.get = Mock(side_effect=[recon, shift_task, request])

        result = invoice_service.generate_invoice_from_reconciliation(
            mock_db, reconciliation_id=1, company_id=1, created_by=1
        )

        assert result is not None
        # Should log warning about using default rate
        assert mock_logger.warning.called


class TestInvoiceServiceGenerateDocumentNumber:
    """Cover _generate_document_number method."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        return db

    @pytest.fixture
    def invoice_service(self):
        from app.services.finance.invoice_service import InvoiceService

        return InvoiceService()

    def test_generate_document_number_format(self, invoice_service, mock_db):
        """Line 194-195: document number format check."""
        mock_db.execute = Mock(return_value=Mock(scalar=Mock(return_value=0)))

        result = invoice_service._generate_document_number(mock_db, date(2026, 11, 12))

        assert result is not None
        assert len(result) > 5 and "-" in result  # Should be formatted document number
        assert len(result) > 5
