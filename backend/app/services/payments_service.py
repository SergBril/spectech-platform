"""Сервис обработки банковских выписок и платежей."""

import logging
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path
from typing import Optional

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
from app.services.bank_statement_parser import (
    ClientBankExchangeParser,
    ParsedTransaction,
)

logger = logging.getLogger("spectech.payments")


class PaymentsService:
    """Сервис для обработки банковских выписок и платежей."""

    def __init__(self, our_account_number: str):
        """
        Args:
            our_account_number: Наш расчётный счёт (для парсера)
        """
        self.parser = ClientBankExchangeParser(our_account_number)

    def upload_statement(
        self,
        db: Session,
        file_path: Path,
        company_id: int,
        uploaded_by: int | None = None,
    ) -> BankStatement:
        """
        Загружает банковскую выписку, парсит и создаёт транзакции.
        
        Args:
            db: Database session
            file_path: Путь к файлу выписки (TXT)
            company_id: ID компании
            uploaded_by: ID пользователя, загрузившего файл
            
        Returns:
            Созданный BankStatement с транзакциями
        """
        logger.info(f"Uploading bank statement: {file_path.name}")
        
        # Читаем файл для сохранения
        file_size = file_path.stat().st_size
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Сохраняем файл в локальное хранилище
        storage_dir = Path(settings.local_storage_dir) / "bank_statements"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        storage_path = storage_dir / f"{timestamp}_{file_path.name}"
        storage_path.write_bytes(file_content)
        
        # Создаём запись о выписке
        statement = BankStatement(
            company_id=company_id,
            file_name=file_path.name,
            file_size=file_size,
            storage_path=str(storage_path),
            status=StatementStatus.processing,
            uploaded_by=uploaded_by,
        )
        db.add(statement)
        db.flush()
        
        try:
            # Парсим выписку
            parsed = self.parser.parse_file(file_path)
            
            # Заполняем метаданные
            statement.account_number = parsed.account_number
            statement.bank_name = parsed.bank_name
            statement.date_start = parsed.date_start
            statement.date_end = parsed.date_end
            statement.opening_balance = parsed.opening_balance
            statement.closing_balance = parsed.closing_balance
            statement.total_incoming = parsed.total_incoming
            statement.total_outgoing = parsed.total_outgoing
            statement.total_transactions = len(parsed.transactions)
            
            # Создаём транзакции
            matched_count = 0
            for tx_data in parsed.transactions:
                # Проверяем, нужно ли исключить (комиссии банка, ФНС)
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
            
            # Авто-матчинг
            matched_count = self.auto_match_transactions(db, statement.id)
            
            statement.matched_transactions = matched_count
            statement.unmatched_transactions = (
                statement.total_transactions - matched_count
            )
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
            statement.status = StatementStatus.failed
            statement.error_message = str(e)
            db.commit()
            raise

    def auto_match_transactions(
        self, db: Session, statement_id: int
    ) -> int:
        """
        Автоматически привязывает транзакции к Invoice по номеру счёта.
        
        Args:
            db: Database session
            statement_id: ID выписки
            
        Returns:
            Количество привязанных транзакций
        """
        # Получаем все непривязанные входящие транзакции
        stmt = select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.direction == TransactionDirection.incoming,
            BankTransaction.match_status == MatchStatus.unmatched,
            BankTransaction.is_excluded == False,
        )
        
        transactions = db.scalars(stmt).all()
        matched_count = 0
        
        for tx in transactions:
            # Извлекаем номер счёта из назначения платежа
            invoice_number = tx.purpose if tx.purpose else None
            
            if not invoice_number:
                continue
            
            # Ищем Invoice по номеру документа
            # Парсер уже извлёк номер, теперь ищем в БД
            invoice_numbers = self._extract_invoice_numbers(tx.purpose)
            
            for inv_num in invoice_numbers:
                # Ищем Invoice с таким document_number
                # Формат: INV-2026-0001 или просто номер
                invoice = self._find_invoice_by_number(db, inv_num, tx.company_id)
                
                if invoice:
                    # Проверяем, не оплачен ли уже счёт
                    if invoice.status == DocumentStatus.paid:
                        logger.warning(
                            f"Invoice {invoice.document_number} already paid, skipping"
                        )
                        continue
                    
                    # Привязываем транзакцию
                    tx.matched_invoice_id = invoice.id
                    tx.matched_amount = tx.amount
                    tx.match_status = MatchStatus.auto_matched
                    tx.match_confidence = Decimal("1.00")  # 100% уверенность
                    
                    matched_count += 1
                    logger.info(
                        f"Auto-matched transaction {tx.bank_transaction_id} "
                        f"to Invoice {invoice.document_number}"
                    )
                    break  # Нашли совпадение, переходим к следующей транзакции
        
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
        """
        Применяет банковскую транзакцию к Invoice (создаёт Payment).
        
        Args:
            db: Database session
            transaction_id: ID транзакции
            invoice_id: ID счёта
            amount: Сумма (если None — берётся из транзакции)
            applied_by: ID пользователя
            
        Returns:
            Созданный Payment
        """
        # Получаем транзакцию и Invoice
        tx = db.get(BankTransaction, transaction_id)
        if not tx:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        if invoice.company_id != tx.company_id:
            raise ValueError("Transaction and invoice belong to different companies")
        
        # Определяем сумму
        payment_amount = amount or tx.amount
        
        # Проверяем, не превышает ли сумма остаток счёта
        remaining = invoice.total - invoice.paid_amount
        if payment_amount > remaining:
            logger.warning(
                f"Payment amount {payment_amount} exceeds remaining {remaining}, "
                f"adjusting to {remaining}"
            )
            payment_amount = remaining
        
        # Создаём Payment
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
        
        # Обновляем транзакцию
        tx.payment_id = payment.id
        tx.matched_invoice_id = invoice.id
        tx.matched_amount = payment_amount
        tx.match_status = MatchStatus.manual_matched
        
        # Обновляем Invoice
        invoice.paid_amount += payment_amount
        
        # Меняем статус Invoice
        if invoice.paid_amount >= invoice.total:
            invoice.status = DocumentStatus.paid
        else:
            invoice.status = DocumentStatus.partially_paid
        
        db.commit()
        db.refresh(payment)
        
        logger.info(
            f"✅ Payment applied: {payment_amount} to Invoice {invoice.document_number}, "
            f"remaining: {invoice.total - invoice.paid_amount}"
        )
        
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

    def _extract_invoice_numbers(self, purpose: str | None) -> list[str]:
        """Извлекает номера счетов из назначения платежа."""
        if not purpose:
            return []
        
        from app.services.bank_statement_parser import extract_invoice_numbers_from_purpose
        return extract_invoice_numbers_from_purpose(purpose)

    def _find_invoice_by_number(
        self, db: Session, number: str, company_id: int
    ) -> Invoice | None:
        """Ищет Invoice по номеру (полному или части)."""
        # Пробуем точное совпадение (INV-2026-0001)
        stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.document_number.ilike(f"%{number}%"),
        )
        invoice = db.scalars(stmt).first()
        
        if invoice:
            return invoice
        
        # Пробуем поиск по числовой части
        stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.document_number.ilike(f"%{number}"),
        )
        return db.scalars(stmt).first()


# Singleton (используем счёт из выписки)
payments_service = PaymentsService(our_account_number="40702810210001399360")