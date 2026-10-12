"""Сервис обработки банковских выписок и платежей."""

import logging
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bank_statement import (
    BankStatement,
    BankTransaction,
    MatchStatus,
    StatementStatus,
    TransactionDirection,
    TransactionType,
)
from app.models.finance import Invoice, Payment, DocumentStatus, PaymentMethod
from app.services.bank_parser import (
    ClientBankExchangeParser,
    extract_invoice_numbers_from_purpose,
)

logger = logging.getLogger("spectech.payments")


class PaymentsService:
    """Сервис для обработки банковских выписок и платежей."""

    def __init__(self, our_account_number: str):
        self.parser = ClientBankExchangeParser(our_account_number)

    def upload_statement(
        self,
        db: Session,
        file_path: Path,
        company_id: int,
        uploaded_by: int | None = None,
    ) -> BankStatement:
        """Загружает банковскую выписку, парсит и создаёт транзакции."""
        logger.info(f"Uploading bank statement: {file_path.name}")

        parsed = self.parser.parse_file(file_path)

        # Проверяем дубликаты
        existing = db.query(BankStatement).filter(
            BankStatement.company_id == company_id,
            BankStatement.account_number == parsed.account_number,
            BankStatement.date_start == parsed.date_start,
            BankStatement.date_end == parsed.date_end,
        ).first()

        if existing:
            raise ValueError(
                f"Выписка за период {parsed.date_start} - {parsed.date_end} "
                f"уже загружена (ID={existing.id}). Удалите её перед повторной загрузкой."
            )

        # Читаем и сохраняем файл
        file_size = file_path.stat().st_size
        with open(file_path, "rb") as f:
            file_content = f.read()

        storage_dir = Path(settings.local_storage_dir) / "bank_statements"
        storage_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        storage_path = storage_dir / f"{timestamp}_{file_path.name}"
        storage_path.write_bytes(file_content)

        try:
            statement = BankStatement(
                company_id=company_id,
                file_name=file_path.name,
                file_size=file_size,
                storage_path=str(storage_path),
                account_number=parsed.account_number,
                bank_name=parsed.bank_name,
                date_start=parsed.date_start,
                date_end=parsed.date_end,
                opening_balance=parsed.opening_balance,
                closing_balance=parsed.closing_balance,
                total_incoming=parsed.total_incoming,
                total_outgoing=parsed.total_outgoing,
                total_transactions=len(parsed.transactions),
                status=StatementStatus.processing,
                uploaded_by=uploaded_by,
            )
            db.add(statement)
            db.flush()

            for tx_data in parsed.transactions:
                is_excluded, exclusion_reason = tx_data.should_be_excluded()

                tx = BankTransaction(
                    statement_id=statement.id,
                    company_id=company_id,
                    bank_transaction_id=tx_data.bank_transaction_id,
                    document_type=TransactionType(tx_data.document_type),
                    document_number=tx_data.number,
                    document_date=tx_data.date,
                    direction=TransactionDirection(tx_data.direction),
                    amount=tx_data.amount,
                    processed_date=tx_data.processed_date,
                    counterparty_name=tx_data.counterparty_name,
                    counterparty_inn=tx_data.counterparty_inn,
                    counterparty_kpp=tx_data.counterparty_kpp,
                    counterparty_account=tx_data.counterparty_account,
                    counterparty_bank=tx_data.counterparty_bank,
                    counterparty_bik=tx_data.counterparty_bik,
                    purpose=tx_data.purpose,
                    is_excluded=is_excluded,
                    exclusion_reason=exclusion_reason,
                    match_status=MatchStatus.unmatched,
                )
                db.add(tx)

            db.flush()

            matched_count = self.auto_match_transactions(db, statement.id)

            statement.matched_transactions = matched_count
            statement.unmatched_transactions = statement.total_transactions - matched_count
            statement.status = StatementStatus.parsed

            db.commit()
            db.refresh(statement)

            logger.info(
                f"✅ Statement uploaded: {statement.total_transactions} transactions, "
                f"{matched_count} auto-matched"
            )
            return statement

        except Exception as e:
            logger.error(f"Failed to parse statement: {e}", exc_info=True)
            db.rollback()
            raise

    def auto_match_transactions(self, db: Session, statement_id: int) -> int:
        """Автоматически привязывает транзакции к Invoice по номеру счёта."""
        stmt = select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.direction == TransactionDirection.incoming,
            BankTransaction.match_status == MatchStatus.unmatched,
            BankTransaction.is_excluded == False,
        )

        transactions = db.scalars(stmt).all()
        matched_count = 0

        for tx in transactions:
            if not tx.purpose:
                continue

            invoice_numbers = extract_invoice_numbers_from_purpose(tx.purpose)

            for inv_num in invoice_numbers:
                invoice = self._find_invoice_by_number(db, inv_num, tx.company_id)

                if invoice:
                    if invoice.status == DocumentStatus.paid:
                        logger.warning(f"Invoice {invoice.document_number} already paid, skipping")
                        continue

                    tx.matched_invoice_id = invoice.id
                    tx.matched_amount = tx.amount
                    tx.match_status = MatchStatus.auto_matched
                    tx.match_confidence = Decimal("1.00")
                    matched_count += 1
                    logger.info(
                        f"Auto-matched transaction {tx.bank_transaction_id} "
                        f"to Invoice {invoice.document_number}"
                    )
                    break

        db.commit()
        return matched_count

    def apply_payment(
        self,
        db: Session,
        transaction_id: int,
        invoice_id: int,
        amount: Decimal | None = None,
        applied_by: int | None = None,
    ) -> Payment:
        """Применяет банковскую транзакцию к Invoice."""
        tx = db.get(BankTransaction, transaction_id)
        if not tx:
            raise ValueError(f"Transaction {transaction_id} not found")

        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if invoice.company_id != tx.company_id:
            raise ValueError("Transaction and invoice belong to different companies")

        payment_amount = amount or tx.amount

        remaining = float(invoice.total) - float(invoice.paid_amount or 0)
        if float(payment_amount) > remaining:
            logger.warning(
                f"Payment amount {payment_amount} exceeds remaining {remaining}, adjusting"
            )
            payment_amount = Decimal(str(remaining))

        payment = Payment(
            invoice_id=invoice.id,
            amount=payment_amount,
            method=PaymentMethod.bank_transfer,
            payment_date=tx.processed_date,
            external_transaction_id=tx.bank_transaction_id,
            bank_transaction_id=tx.bank_transaction_id,
            payer_name=tx.counterparty_name,
            payer_inn=tx.counterparty_inn,
            payer_account=tx.counterparty_account,
            purpose=tx.purpose,
            comment=f"Оплата по банковской выписке от {tx.processed_date}",
        )
        db.add(payment)
        db.flush()

        tx.payment_id = payment.id
        tx.matched_invoice_id = invoice.id
        tx.matched_amount = payment_amount
        tx.match_status = MatchStatus.manual_matched

        new_paid = float(invoice.paid_amount or 0) + float(payment_amount)
        invoice.paid_amount = str(new_paid)

        if new_paid >= float(invoice.total):
            invoice.status = DocumentStatus.paid
        else:
            invoice.status = DocumentStatus.partially_paid

        db.commit()
        db.refresh(payment)
        db.refresh(invoice)

        logger.info(
            f"✅ Payment applied: {payment_amount} to Invoice {invoice.document_number}, "
            f"remaining: {float(invoice.total) - new_paid}"
        )

        # Уведомления (не блокируем основную операцию)
        try:
            from app.services.payment_notifications import payment_notification_service
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    payment_notification_service.notify_invoice_paid(
                        db=db,
                        invoice=invoice,
                        payment_amount=float(payment_amount),
                        payment_date=tx.processed_date,
                        payer_name=tx.counterparty_name,
                        payer_inn=tx.counterparty_inn,
                        client_user_id=None,
                    )
                )
            except RuntimeError:
                pass
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to send payment notifications: {e}")

        return payment

    def get_unmatched_transactions(
        self, db: Session, company_id: int, limit: int = 100, offset: int = 0
    ) -> list[BankTransaction]:
        """Возвращает список непривязанных входящих транзакций."""
        stmt = (
            select(BankTransaction)
            .where(
                BankTransaction.company_id == company_id,
                BankTransaction.direction == TransactionDirection.incoming,
                BankTransaction.match_status == MatchStatus.unmatched,
                BankTransaction.is_excluded == False,
                BankTransaction.payment_id == None,
            )
            .order_by(BankTransaction.processed_date.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def _find_invoice_by_number(
        self, db: Session, number: str, company_id: int
    ) -> Invoice | None:
        """Ищет Invoice по номеру."""
        stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.document_number.ilike(f"%{number}%"),
        )
        return db.scalars(stmt).first()


# Singleton
payments_service = PaymentsService(our_account_number="40702810210001399360")