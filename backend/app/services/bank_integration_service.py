"""Интеграция с банк-клиентом / 1С для выгрузки платёжных поручений."""
import logging
from sqlalchemy.orm import Session
from typing import Optional
from xml.etree.ElementTree import fromstring

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
        import csv, io
        payments = []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                payment = {
                    "doc_number": row.get("Номер", row.get("number", "")),
                    "doc_date": row.get("Дата", row.get("date", "")),
                    "payer_inn": row.get("ИННПлательщика", row.get("payer_inn", "")),
                    "payer_name": row.get("Плательщик", row.get("payer_name", "")),
                    "payer_account": row.get("СчетПлательщика", row.get("payer_account", "")),
                    "payee_inn": row.get("ИННПолучателя", row.get("payee_inn", "")),
                    "payee_name": row.get("Получатель", row.get("payee_name", "")),
                    "payee_account": row.get("СчетПолучателя", row.get("payee_account", "")),
                    "amount": float(row.get("Сумма", row.get("amount", "0"))),
                    "purpose": row.get("Назначение", row.get("purpose", "")),
                    "status": "processed",
                }
                payments.append(payment)

            logger.info(f"Parsed {len(payments)} payments from CSV")
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
        return payments

    def sync_payments_to_db(self, db: Session, company_id: int, payments: list[dict]) -> dict:
        """Сохранить платежи в БД (bank_transactions)."""
        from app.models.bank import BankTransaction
        from datetime import datetime

        created = 0
        skipped = 0

        for p in payments:
            # Check duplicate by doc_number + doc_date + amount
            existing = db.execute(
                select(BankTransaction).where(
                    BankTransaction.company_id == company_id,
                    BankTransaction.doc_number == p["doc_number"],
                    BankTransaction.amount == p["amount"],
                )
            ).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            txn = BankTransaction(
                company_id=company_id,
                doc_number=p["doc_number"],
                doc_date=p["doc_date"],
                payer_inn=p["payer_inn"],
                payer_name=p["payer_name"],
                payer_account=p["payer_account"],
                payee_inn=p["payee_inn"],
                payee_name=p["payee_name"],
                payee_account=p["payee_account"],
                amount=p["amount"],
                purpose=p["purpose"],
                status=p["status"],
                source="import",
            )
            db.add(txn)
            created += 1

        db.commit()
        logger.info(f"Bank sync: {created} created, {skipped} skipped")
        return {"created": created, "skipped": skipped}

    def _get_text(self, parent, tag: str) -> str:
        el = parent.find(tag)
        return el.text.strip() if el is not None and el.text else ""


bank_integration_service = BankIntegrationService()
