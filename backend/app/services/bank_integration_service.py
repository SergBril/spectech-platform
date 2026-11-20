"""Интеграция с банк-клиентом / 1С для выгрузки платёжных поручений."""

import logging
from xml.etree.ElementTree import fromstring

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BankIntegrationService:
    """Сервис импорта платёжных документов из банк-клиента / 1С.

    Поддерживает форматы:
    - 1C ClientBankExchange (XML)
    - Стандартный формат ЦБ РФ (txt/xml)
    - Ручной CSV импорт
    """

    def parse_1c_xml(self, xml_content: str) -> list[dict]:
        """Парсинг XML выгрузки из 1С (ClientBankExchange)."""
        payments = []
        try:
            root = fromstring(xml_content)
            for doc in root.iter("Документ"):
                if doc.get("Тип", "") != "ПлатежноеПоручение":
                    continue

                payment = {
                    "doc_number": self._get_text(doc, "Номер"),
                    "doc_date": self._get_text(doc, "Дата"),
                    "payer_inn": self._get_text(doc, "ИННПлательщика"),
                    "payer_name": self._get_text(doc, "НаименованиеПлательщика"),
                    "payer_account": self._get_text(doc, "СчетПлательщика"),
                    "payee_inn": self._get_text(doc, "ИННПолучателя"),
                    "payee_name": self._get_text(doc, "НаименованиеПолучателя"),
                    "payee_account": self._get_text(doc, "СчетПолучателя"),
                    "amount": float(self._get_text(doc, "Сумма") or "0"),
                    "purpose": self._get_text(doc, "НазначениеПлатежа"),
                    "status": self._get_text(doc, "Статус") or "processed",
                }
                payments.append(payment)

            logger.info(f"Parsed {len(payments)} payments from 1C XML")
        except Exception as e:
            logger.error(f"Failed to parse 1C XML: {e}")
        return payments

    def parse_csv(self, csv_content: str) -> list[dict]:
        """Парсинг CSV выгрузки из банк-клиента."""
        import csv
        import io

        payments = []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                payment = {
                    "doc_number": row.get("Номер", row.get("number", "")),
                    "doc_date": row.get("Дата", row.get("date", "")),
                    "payer_inn": row.get("ИННПлательщика", row.get("payer_inn", "")),
                    "payer_name": row.get("Плательщик", row.get("payer_name", "")),
                    "payer_account": row.get(
                        "СчетПлательщика", row.get("payer_account", "")
                    ),
                    "payee_inn": row.get("ИННПолучателя", row.get("payee_inn", "")),
                    "payee_name": row.get("Получатель", row.get("payee_name", "")),
                    "payee_account": row.get(
                        "СчетПолучателя", row.get("payee_account", "")
                    ),
                    "amount": float(row.get("Сумма", row.get("amount", "0"))),
                    "purpose": row.get("Назначение", row.get("purpose", "")),
                    "status": "processed",
                }
                payments.append(payment)

            logger.info(f"Parsed {len(payments)} payments from CSV")
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
        return payments

    def sync_payments_to_db(
        self,
        db: Session,
        company_id: int,
        payments: list[dict],
        file_name: str = "",
        file_content: bytes = b"",
    ) -> dict:
        """Сохранить платежи в БД как строки банковской выписки.

        BankTransaction живёт в app.models.bank_statement и требует выписку
        (statement_id) и поля document_number/direction/counterparty_*. direction
        определяется по совпадению счёта плательщика/получателя с нашим счётом
        (конвенция ClientBankExchangeParser); платёж, не относящийся к нашему
        счёту, пропускается. Выписка пакета импорта создаётся реально, а не
        подставляется выдуманный statement_id.
        """
        from datetime import UTC, datetime
        from decimal import Decimal
        from pathlib import Path

        from app.core.config import settings
        from app.models.bank_statement import (
            BankStatement,
            BankTransaction,
            MatchStatus,
            StatementStatus,
            TransactionDirection,
            TransactionType,
        )

        our_account = getattr(settings, "BANK_ACCOUNT_NUMBER", "40702810210001399360")

        created = 0
        skipped = 0
        seen: set[str] = set()
        prepared: list[tuple] = []

        for p in payments:
            doc_date = self._parse_date(p.get("doc_date"))
            if doc_date is None:
                skipped += 1
                continue

            payer_account = p.get("payer_account") or ""
            payee_account = p.get("payee_account") or ""
            if payer_account == our_account:
                direction = TransactionDirection.outgoing
            elif payee_account == our_account:
                direction = TransactionDirection.incoming
            else:
                # Не относится к нашему счёту - пропускаем (конвенция парсера).
                skipped += 1
                continue

            amount = Decimal(str(p.get("amount") or 0))
            number = p.get("doc_number") or ""
            amount_str = str(amount).replace(".", "_")
            bank_transaction_id = (
                f"{TransactionType.payment_order.value}_{number}_"
                f"{doc_date.isoformat()}_{amount_str}"
            )
            if bank_transaction_id in seen:
                skipped += 1
                continue
            existing = db.execute(
                select(BankTransaction).where(
                    BankTransaction.company_id == company_id,
                    BankTransaction.bank_transaction_id == bank_transaction_id,
                )
            ).scalar_one_or_none()
            if existing:
                skipped += 1
                continue
            seen.add(bank_transaction_id)
            prepared.append((p, doc_date, direction, bank_transaction_id, amount))

        if not prepared:
            return {"created": 0, "skipped": skipped}

        dates = [d for _, d, _, _, _ in prepared]
        storage_dir = Path(settings.local_storage_dir) / "bank_statements"
        storage_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        safe_name = file_name or "import.csv"
        storage_path = storage_dir / f"{timestamp}_{safe_name}"
        storage_path.write_bytes(file_content or b"")

        statement = BankStatement(
            company_id=company_id,
            file_name=safe_name,
            file_size=len(file_content or b""),
            storage_path=str(storage_path),
            account_number=our_account,
            date_start=min(dates),
            date_end=max(dates),
            total_transactions=len(prepared),
            status=StatementStatus.parsed,
        )
        db.add(statement)
        db.flush()

        for p, doc_date, direction, bank_transaction_id, amount in prepared:
            outgoing = direction == TransactionDirection.outgoing
            txn = BankTransaction(
                statement_id=statement.id,
                company_id=company_id,
                bank_transaction_id=bank_transaction_id,
                document_type=TransactionType.payment_order,
                document_number=p.get("doc_number") or "",
                document_date=doc_date,
                direction=direction,
                amount=amount,
                processed_date=doc_date,
                counterparty_name=(
                    p.get("payee_name") if outgoing else p.get("payer_name")
                )
                or "",
                counterparty_inn=(
                    p.get("payee_inn") if outgoing else p.get("payer_inn")
                )
                or None,
                counterparty_account=(
                    p.get("payee_account") if outgoing else p.get("payer_account")
                )
                or None,
                purpose=p.get("purpose") or None,
                match_status=MatchStatus.unmatched,
                source="import",
            )
            db.add(txn)
            created += 1

        statement.total_transactions = created
        db.commit()
        logger.info(f"Bank sync: {created} created, {skipped} skipped")
        return {"created": created, "skipped": skipped}

    @staticmethod
    def _parse_date(value: str | None):
        """Дата платежа из парсера приходит строкой dd.mm.yyyy."""
        from datetime import datetime

        if not value:
            return None
        try:
            return datetime.strptime(str(value).strip(), "%d.%m.%Y").date()
        except ValueError:
            return None

    def _get_text(self, parent, tag: str) -> str:
        el = parent.find(tag)
        return el.text.strip() if el is not None and el.text else ""


bank_integration_service = BankIntegrationService()
