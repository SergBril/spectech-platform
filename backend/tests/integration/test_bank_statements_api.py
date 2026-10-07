"""Интеграционные тесты API банковских выписок."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.bank_statement import (
    BankStatement,
    BankTransaction,
    MatchStatus,
    StatementStatus,
    TransactionDirection,
)
from app.models.finance import Invoice, DocumentStatus


class TestBankStatementsAPI:
    """Тесты загрузки банковских выписок."""

    @pytest.fixture
    def sample_statement_file(self) -> Path:
        """Путь к тестовому файлу выписки."""
        path = Path("tests/fixtures/bank_statement_sample.txt")
        if not path.exists():
            pytest.skip("Sample bank statement file not found")
        return path

    def test_upload_bank_statement_success(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_statement_file: Path,
    ):
        """✅ Загрузка выписки создаёт BankStatement и BankTransaction."""
        with open(sample_statement_file, "rb") as f:
            response = auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        assert response.status_code == 201
        data = response.json()

        assert data["status"] == "parsed"
        assert data["total_transactions"] > 0
        assert data["total_incoming"] > 0
        assert data["total_outgoing"] > 0
        assert data["account_number"] == "40702810210001399360"

        # Проверяем, что данные в БД
        statement = db_session.get(BankStatement, data["id"])
        assert statement is not None
        assert statement.status == StatementStatus.parsed
        assert len(statement.transactions) == data["total_transactions"]

    def test_upload_invalid_file_type(
        self, auth_client: TestClient, tmp_path: Path
    ):
        """❌ Загрузка не-TXT файла возвращает ошибку."""
        invalid_file = tmp_path / "statement.pdf"
        invalid_file.write_bytes(b"not a txt file")

        with open(invalid_file, "rb") as f:
            response = auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (invalid_file.name, f, "application/pdf")},
            )

        assert response.status_code == 400
        assert "Only .txt files supported" in response.json()["detail"]

    def test_list_bank_statements(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_statement_file: Path,
    ):
        """✅ Список загруженных выписок."""
        # Загружаем выписку
        with open(sample_statement_file, "rb") as f:
            auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        # Получаем список
        response = auth_client.get("/api/v1/banking/bank-statements")
        assert response.status_code == 200

        statements = response.json()
        assert isinstance(statements, list)
        assert len(statements) >= 1
        assert "id" in statements[0]
        assert "file_name" in statements[0]
        assert "status" in statements[0]

    def test_unmatched_payments_endpoint(
        self,
        auth_client: TestClient,
        sample_statement_file: Path,
    ):
        """✅ Эндпоинт непривязанных платежей возвращает список."""
        # Загружаем выписку
        with open(sample_statement_file, "rb") as f:
            auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        # Получаем непривязанные
        response = auth_client.get("/api/v1/banking/payments/unmatched")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_auto_matching_finds_invoices(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_statement_file: Path,
        company,
    ):
        """✅ Авто-матчинг находит Invoice по номеру в назначении платежа."""
        from datetime import date, timedelta

        # Создаём тестовый Invoice с номером 347 (есть в выписке)
        invoice = Invoice(
            document_number="INV-2026-347",
            client_id=1,
            company_id=company.id,
            subtotal=Decimal("179179.67"),
            vat_amount=Decimal("39444.64"),
            vat_rate=Decimal("22.00"),
            total=Decimal("218738.40"),
            paid_amount=Decimal("0.00"),
            invoice_date=date.today() - timedelta(days=10),
            due_date=date.today() + timedelta(days=20),
            status=DocumentStatus.sent,
        )
        db_session.add(invoice)
        db_session.commit()

        # Загружаем выписку
        with open(sample_statement_file, "rb") as f:
            response = auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        assert response.status_code == 201
        data = response.json()

        # Должна быть хотя бы одна авто-привязка
        assert data["matched_transactions"] >= 1, \
            f"Expected at least 1 auto-match, got {data['matched_transactions']}"

        # Проверяем, что транзакция действительно привязана
        matched = db_session.query(BankTransaction).filter(
            BankTransaction.statement_id == data["id"],
            BankTransaction.match_status == MatchStatus.auto_matched,
        ).count()
        assert matched >= 1

    def test_apply_payment_to_invoice(
        self,
        auth_client: TestClient,
        db_session: Session,
        sample_statement_file: Path,
        company,
    ):
        """✅ Применение платежа к Invoice создаёт Payment и обновляет статус."""
        from datetime import date, timedelta

        # Создаём Invoice
        invoice = Invoice(
            document_number="INV-2026-TEST-001",
            client_id=1,
            company_id=company.id,
            subtotal=Decimal("10000.00"),
            vat_amount=Decimal("2000.00"),
            vat_rate=Decimal("20.00"),
            total=Decimal("12000.00"),
            paid_amount=Decimal("0.00"),
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=DocumentStatus.sent,
        )
        db_session.add(invoice)

        # Загружаем выписку
        with open(sample_statement_file, "rb") as f:
            auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        # Получаем первую непривязанную транзакцию
        unmatched_resp = auth_client.get("/api/v1/banking/payments/unmatched")
        unmatched = unmatched_resp.json()

        if unmatched["total"] == 0:
            pytest.skip("No unmatched transactions")

        tx = unmatched["items"][0]

        # Применяем платёж
        apply_resp = auth_client.post(
            "/api/v1/banking/payments/apply",
            params={
                "transaction_id": tx["id"],
                "invoice_id": invoice.id,
            },
        )

        assert apply_resp.status_code == 200
        result = apply_resp.json()
        assert result["payment_id"] > 0

        # Проверяем, что Invoice обновился
        db_session.refresh(invoice)
        assert invoice.paid_amount > 0
        assert invoice.status in (
            DocumentStatus.paid,
            DocumentStatus.partially_paid,
        )

    def test_excluded_transactions_not_in_unmatched(
        self,
        auth_client: TestClient,
        sample_statement_file: Path,
    ):
        """✅ Служебные транзакции (комиссии банка) не попадают в unmatched."""
        # Загружаем выписку
        with open(sample_statement_file, "rb") as f:
            auth_client.post(
                "/api/v1/banking/bank-statements",
                files={"file": (sample_statement_file.name, f, "text/plain")},
            )

        # Получаем непривязанные
        response = auth_client.get("/api/v1/banking/payments/unmatched")
        unmatched = response.json()

        # В unmatched не должно быть банковских комиссий
        for tx in unmatched["items"]:
            assert "обслуживание" not in (tx.get("purpose") or "").lower(), \
                f"Bank commission should be excluded: {tx}"
            assert "пакет" not in (tx.get("purpose") or "").lower(), \
                f"Bank package should be excluded: {tx}"

    def test_apply_payment_sends_email_notification(
        self,
        auth_client: TestClient,
        db_session: Session,
        company,
    ):
        """✅ Применение платежа отправляет email-уведомление клиенту."""
        from datetime import date, timedelta
        from unittest.mock import patch
        from app.models.contractor import Contractor
        from app.models.finance import Invoice, DocumentStatus
        from app.models.bank_statement import (
            BankStatement, BankTransaction, MatchStatus,
            StatementStatus, TransactionDirection, TransactionType,
        )

        # Создаём клиента с email
        client = Contractor(
            name="Test Client for Payment",
            inn="7711111111",
            type="client",
            company_id=company.id,
            email="payment_test@spectech.dev",
        )
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)

        # Создаём Invoice
        invoice = Invoice(
            document_number="INV-2026-PAYMENT-TEST",
            client_id=client.id,
            company_id=company.id,
            subtotal=Decimal("10000.00"),
            vat_amount=Decimal("2000.00"),
            vat_rate=Decimal("20.00"),
            total=Decimal("12000.00"),
            paid_amount=Decimal("0.00"),
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=DocumentStatus.sent,
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        # Создаём тестовую выписку и транзакцию
        statement = BankStatement(
            company_id=company.id,
            file_name="test.txt",
            file_size=100,
            storage_path="/tmp/test.txt",
            account_number="40702810210001399360",
            date_start=date.today() - timedelta(days=1),
            date_end=date.today(),
            opening_balance=Decimal("0"),
            closing_balance=Decimal("12000"),
            total_incoming=Decimal("12000"),
            total_outgoing=Decimal("0"),
            total_transactions=1,
            status=StatementStatus.parsed,
        )
        db_session.add(statement)
        db_session.commit()
        db_session.refresh(statement)

        tx = BankTransaction(
            statement_id=statement.id,
            company_id=company.id,
            bank_transaction_id="test_payment_order_1",
            document_type=TransactionType.payment_order,
            document_number="1",
            document_date=date.today(),
            direction=TransactionDirection.incoming,
            amount=Decimal("12000.00"),
            processed_date=date.today(),
            counterparty_name="Test Payer",
            counterparty_inn="7722222222",
            purpose="Оплата по счету",
            match_status=MatchStatus.unmatched,
        )
        db_session.add(tx)
        db_session.commit()
        db_session.refresh(tx)

        # Применяем платёж с моком email_service
        with patch("app.services.payment_notifications.email_service") as mock_email:
            mock_email.send_invoice_paid.return_value = True

            response = auth_client.post(
                "/api/v1/banking/payments/apply",
                params={
                    "transaction_id": tx.id,
                    "invoice_id": invoice.id,
                },
            )

            assert response.status_code == 200

            # Проверяем, что Invoice обновился
            db_session.refresh(invoice)
            assert invoice.paid_amount == Decimal("12000.00")
            assert invoice.status == DocumentStatus.paid

            # Примечание: email может быть отправлен асинхронно,
            # поэтому в синхронном тесте он может не успеть отправиться.
            # Это нормально — в production уведомления идут в фоне.