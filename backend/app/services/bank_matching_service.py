"""Сервис автоматического сопоставления банковских транзакций со счетами."""

import logging
import re
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.bank_statement import BankTransaction, MatchStatus, TransactionType
from app.models.finance import Invoice, Payout, DocumentStatus

logger = logging.getLogger("spectech.bank_matching")

# Паттерны для извлечения номера счёта из назначения платежа
INVOICE_PATTERNS = [
    re.compile(r'(?:счет[а-я]*|сч[.]?)\s*№?\s*(\S+)', re.IGNORECASE),
    re.compile(r'INV-(\d{4}-\d+)', re.IGNORECASE),
    re.compile(r'СЧ-(\d{4}-\d+)', re.IGNORECASE),
    re.compile(r'по\s+счету\s*№?\s*(\S+)', re.IGNORECASE),
]


class BankMatchingService:
    """Сервис авто-матчинга банковских транзакций."""

    @staticmethod
    def extract_invoice_number(purpose: str | None) -> str | None:
        """Извлекает номер счёта из назначения платежа."""
        if not purpose:
            return None
        for pattern in INVOICE_PATTERNS:
            match = pattern.search(purpose)
            if match:
                return match.group(1).strip()
        return None

    @classmethod
    def match_transaction(cls, db: Session, tx: BankTransaction, company_id: int) -> dict:
        """
        Пытается сопоставить транзакцию со счётом или выплатой.

        Returns:
            dict с результатами матчинга:
            - matched: bool
            - match_type: 'invoice' | 'payout' | None
            - matched_id: int | None
            - confidence: float (0.0 - 1.0)
            - reason: str
        """
        result = {
            "matched": False,
            "match_type": None,
            "matched_id": None,
            "confidence": 0.0,
            "reason": "",
        }

        # Пропускаем служебные операции
        exclusion_keywords = [
            "комиссия банка", "плата за обслуживание", "РКО",
            "ФНС", "взыскание", "налог", "пени", "штраф",
        ]
        purpose_lower = (tx.purpose or "").lower()
        if any(kw in purpose_lower for kw in exclusion_keywords):
            result["reason"] = "Служебная операция банка"
            return result

        amount = float(tx.amount)

        # === Стратегия 1: Поиск по номеру счёта в назначении ===
        invoice_number = cls.extract_invoice_number(tx.purpose)
        if invoice_number:
            invoice = db.query(Invoice).filter(
                Invoice.company_id == company_id,
                Invoice.document_number == invoice_number,
            ).first()

            if invoice:
                result["matched"] = True
                result["match_type"] = "invoice"
                result["matched_id"] = invoice.id
                result["confidence"] = 0.95
                result["reason"] = f"Найден по номеру {invoice_number} в назначении"
                logger.info(f"✅ Matched TX#{tx.id} → Invoice#{invoice.id} by document_number")
                return result

        # === Стратегия 2: Поиск по сумме + ИНН контрагента ===
        if tx.counterparty_inn:
            # Ищем инвойсы с matching суммой и клиентом с таким ИНН
            from app.models.contractor import Contractor

            contractor = db.query(Contractor).filter(
                Contractor.company_id == company_id,
                Contractor.inn == tx.counterparty_inn,
            ).first()

            if contractor:
                # Для входящих — ищем инвойсы этого клиента
                if tx.operation_type == TransactionType.income:
                    invoice = db.query(Invoice).filter(
                        Invoice.company_id == company_id,
                        Invoice.client_id == contractor.id,
                        Invoice.total == str(amount),
                        Invoice.status.in_([DocumentStatus.sent, DocumentStatus.overdue, DocumentStatus.partially_paid]),
                    ).first()

                    if invoice:
                        result["matched"] = True
                        result["match_type"] = "invoice"
                        result["matched_id"] = invoice.id
                        result["confidence"] = 0.85
                        result["reason"] = f"Найден по сумме {amount}₽ и ИНН {tx.counterparty_inn}"
                        logger.info(f"✅ Matched TX#{tx.id} → Invoice#{invoice.id} by amount+INN")
                        return result

                # Для исходящих — ищем выплаты этому контрагенту
                elif tx.operation_type == TransactionType.expense:
                    payout = db.query(Payout).filter(
                        Payout.company_id == company_id,
                        Payout.owner_id == contractor.id,
                        Payout.net_amount == str(amount),
                        Payout.status.in_([DocumentStatus.sent, DocumentStatus.paid]),
                    ).first()

                    if payout:
                        result["matched"] = True
                        result["match_type"] = "payout"
                        result["matched_id"] = payout.id
                        result["confidence"] = 0.85
                        result["reason"] = f"Найден по сумме {amount}₽ и ИНН {tx.counterparty_inn}"
                        logger.info(f"✅ Matched TX#{tx.id} → Payout#{payout.id} by amount+INN")
                        return result

        # === Стратегия 3: Поиск только по сумме (низкая уверенность) ===
        if tx.operation_type == TransactionType.income:
            invoices = db.query(Invoice).filter(
                Invoice.company_id == company_id,
                Invoice.total == str(amount),
                Invoice.status.in_([DocumentStatus.sent, DocumentStatus.overdue, DocumentStatus.partially_paid]),
            ).all()

            if len(invoices) == 1:
                result["matched"] = True
                result["match_type"] = "invoice"
                result["matched_id"] = invoices[0].id
                result["confidence"] = 0.6
                result["reason"] = f"Единственный неоплаченный счёт на сумму {amount}₽"
                logger.info(f"⚠️ Weak match TX#{tx.id} → Invoice#{invoices[0].id} by amount only")
                return result
            elif len(invoices) > 1:
                result["reason"] = f"Найдено {len(invoices)} счетов на сумму {amount}₽ — требуется ручной выбор"
                return result

        result["reason"] = "Не найден подходящий счёт/выплата"
        return result

    @classmethod
    def apply_match(cls, db: Session, tx: BankTransaction, match_result: dict) -> None:
        """Применяет результат матчинга к транзакции."""
        if match_result["matched"]:
            tx.match_status = MatchStatus.matched_auto
            tx.match_confidence = match_result["confidence"]

            if match_result["match_type"] == "invoice":
                tx.matched_invoice_id = match_result["matched_id"]
                # Обновляем оплаченную сумму в инвойсе
                invoice = db.get(Invoice, match_result["matched_id"])
                if invoice:
                    current_paid = float(invoice.paid_amount or 0)
                    new_paid = current_paid + float(tx.amount)
                    total = float(invoice.total or 0)
                    invoice.paid_amount = str(min(new_paid, total))
                    if new_paid >= total:
                        invoice.status = DocumentStatus.paid
                    elif new_paid > 0:
                        invoice.status = DocumentStatus.partially_paid
                    logger.info(f"💰 Updated Invoice#{invoice.id}: paid={invoice.paid_amount}/{invoice.total}")

            elif match_result["match_type"] == "payout":
                tx.matched_payout_id = match_result["matched_id"]
        else:
            tx.match_status = MatchStatus.unmatched

        db.commit()


bank_matching_service = BankMatchingService()