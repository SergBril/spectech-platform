"""Парсер банковской выписки формата 1CClientBankExchange."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("spectech.bank_parser")

# Regex для извлечения номера счёта из назначения платежа
INVOICE_NUMBER_PATTERNS = [
    re.compile(r'(?:счет[а-я]*|сч[.]?)\s*№\s*(\d+)', re.IGNORECASE),
    re.compile(r'по\s+счету\s+№?\s*(\d+)', re.IGNORECASE),
    re.compile(r'INV-(\d{4}-\d+)', re.IGNORECASE),
    re.compile(r'(?:и|,)\s*№\s*(\d+)', re.IGNORECASE),
    re.compile(r'счета?\s*№?\s*(\d+)', re.IGNORECASE),
]

# Регулярки для определения "служебных" операций
EXCLUSION_PATTERNS = [
    re.compile(r'Плата за обслуживание', re.IGNORECASE),
    re.compile(r'Плата за пакет', re.IGNORECASE),
    re.compile(r'Комиссия банка', re.IGNORECASE),
    re.compile(r'По решению о взыскании', re.IGNORECASE),
    re.compile(r'ФНС России', re.IGNORECASE),
    re.compile(r'РКО', re.IGNORECASE),
]


@dataclass
class ParsedTransaction:
    """Распарсенная транзакция."""
    document_type: str
    number: str
    date: date
    amount: Decimal
    processed_date: date
    direction: str

    # Плательщик
    payer_name: str
    payer_inn: str | None = None
    payer_kpp: str | None = None
    payer_account: str | None = None
    payer_bank: str | None = None
    payer_bik: str | None = None

    # Получатель
    payee_name: str = ""
    payee_inn: str | None = None
    payee_kpp: str | None = None
    payee_account: str | None = None
    payee_bank: str | None = None
    payee_bik: str | None = None

    # Назначение
    purpose: str | None = None

    # Дополнительные данные
    payment_type: str | None = None
    priority: int | None = None

    raw_data: dict = field(default_factory=dict)

    @property
    def counterparty_name(self) -> str:
        return self.payee_name if self.direction == "outgoing" else self.payer_name

    @property
    def counterparty_inn(self) -> str | None:
        return self.payee_inn if self.direction == "outgoing" else self.payer_inn

    @property
    def counterparty_kpp(self) -> str | None:
        return self.payee_kpp if self.direction == "outgoing" else self.payer_kpp

    @property
    def counterparty_account(self) -> str | None:
        return self.payee_account if self.direction == "outgoing" else self.payer_account

    @property
    def counterparty_bank(self) -> str | None:
        return self.payee_bank if self.direction == "outgoing" else self.payer_bank

    @property
    def counterparty_bik(self) -> str | None:
        return self.payee_bik if self.direction == "outgoing" else self.payer_bik

    @property
    def bank_transaction_id(self) -> str:
        amount_str = str(self.amount).replace(".", "_").replace(",", "_")
        return f"{self.document_type}_{self.number}_{self.date.isoformat()}_{amount_str}"

    def extract_invoice_number(self) -> str | None:
        if not self.purpose:
            return None
        for pattern in INVOICE_NUMBER_PATTERNS:
            match = pattern.search(self.purpose)
            if match:
                return match.group(1)
        return None

    def should_be_excluded(self) -> tuple[bool, str | None]:
        if not self.purpose:
            return False, None
        for pattern in EXCLUSION_PATTERNS:
            if pattern.search(self.purpose):
                return True, f"Matched exclusion pattern: {pattern.pattern}"
        if self.document_type in ("bank_order", "demand_order"):
            return True, f"Document type {self.document_type} is excluded by default"
        return False, None


@dataclass
class ParsedStatement:
    """Распарсенная выписка."""
    account_number: str
    bank_name: str | None
    date_start: date
    date_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_incoming: Decimal
    total_outgoing: Decimal
    transactions: list[ParsedTransaction] = field(default_factory=list)

    def validate(self) -> bool:
        calculated = self.opening_balance + self.total_incoming - self.total_outgoing
        diff = abs(calculated - self.closing_balance)
        if diff > Decimal("0.01"):
            logger.error(
                f"Balance mismatch: expected {self.closing_balance}, "
                f"got {calculated} (diff {diff})"
            )
            return False
        return True


class ClientBankExchangeParser:
    """Парсер формата 1CClientBankExchange (Т-Банк, Сбер, Альфа и др.)."""

    DOCUMENT_TYPE_MAP = {
        "Платежное поручение": "payment_order",
        "Банковский ордер": "bank_order",
        "Инкассовое поручение": "demand_order",
        "Платежное требование": "demand_order",
        "Взнос наличными": "cash_deposit",
        "Выдача наличными": "cash_withdrawal",
    }

    def __init__(self, our_account_number: str):
        self.our_account = our_account_number

    def parse_file(self, file_path: Path | str) -> ParsedStatement:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="windows-1251") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

        return self.parse_content(content)

    def parse_content(self, content: str) -> ParsedStatement:
        if not content.startswith("1CClientBankExchange"):
            raise ValueError("Invalid format: expected 1CClientBankExchange")

        lines = content.split("\n")
        header = self._parse_header(lines)

        statement_data = None
        transactions = []

        current_section = None
        current_doc_type = None
        current_data = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line == "СекцияРасчСчет":
                current_section = "account"
                current_data = {}
                continue

            if line.startswith("СекцияДокумент="):
                current_section = "document"
                current_doc_type = line.split("=", 1)[1].strip()
                current_data = {}
                continue

            if line == "КонецРасчСчет":
                if current_section == "account":
                    statement_data = self._build_statement_data(current_data)
                current_section = None
                continue

            if line == "КонецДокумента":
                if current_section == "document" and current_doc_type:
                    tx = self._build_transaction(current_doc_type, current_data)
                    if tx:
                        transactions.append(tx)
                current_section = None
                continue

            if line == "КонецФайла":
                break

            if "=" in line:
                key, _, value = line.partition("=")
                current_data[key.strip()] = value.strip()

        if not statement_data:
            raise ValueError("No account section found in statement")

        statement = ParsedStatement(
            account_number=statement_data["account_number"],
            bank_name=statement_data.get("bank_name"),
            date_start=statement_data["date_start"],
            date_end=statement_data["date_end"],
            opening_balance=statement_data["opening_balance"],
            closing_balance=statement_data["closing_balance"],
            total_incoming=statement_data["total_incoming"],
            total_outgoing=statement_data["total_outgoing"],
            transactions=transactions,
        )

        if not statement.validate():
            logger.warning("Statement balance validation failed")

        logger.info(
            f"Parsed statement: {len(transactions)} transactions, "
            f"{statement.date_start} - {statement.date_end}"
        )
        return statement

    def _parse_header(self, lines: list[str]) -> dict:
        header = {}
        for line in lines[:20]:
            if "=" in line:
                key, _, value = line.partition("=")
                header[key.strip()] = value.strip()
            if line.startswith("Секция"):
                break
        return header

    def _build_statement_data(self, data: dict) -> dict:
        return {
            "account_number": data.get("РасчСчет", ""),
            "bank_name": None,
            "date_start": self._parse_date(data.get("ДатаНачала")),
            "date_end": self._parse_date(data.get("ДатаКонца")),
            "opening_balance": Decimal(data.get("НачальныйОстаток", "0")),
            "closing_balance": Decimal(data.get("КонечныйОстаток", "0")),
            "total_incoming": Decimal(data.get("ВсегоПоступило", "0")),
            "total_outgoing": Decimal(data.get("ВсегоСписано", "0")),
        }

    def _build_transaction(self, doc_type_ru: str, data: dict) -> ParsedTransaction | None:
        doc_type = self.DOCUMENT_TYPE_MAP.get(doc_type_ru)
        if not doc_type:
            logger.warning(f"Unknown document type: {doc_type_ru}")
            return None

        payer_account = data.get("ПлательщикСчет", "")
        payee_account = data.get("ПолучательСчет", "")

        if payer_account == self.our_account:
            direction = "outgoing"
            processed_date_key = "ДатаСписано"
        elif payee_account == self.our_account:
            direction = "incoming"
            processed_date_key = "ДатаПоступило"
        else:
            logger.warning(f"Transaction not related to our account: {data.get('Номер')}")
            return None

        processed_date_str = data.get(processed_date_key) or data.get("Дата")

        return ParsedTransaction(
            document_type=doc_type,
            number=data.get("Номер", ""),
            date=self._parse_date(data.get("Дата")),
            amount=Decimal(data.get("Сумма", "0")),
            processed_date=self._parse_date(processed_date_str),
            direction=direction,
            payer_name=data.get("Плательщик", ""),
            payer_inn=data.get("ПлательщикИНН") or None,
            payer_kpp=data.get("ПлательщикКПП") or None,
            payer_account=payer_account or None,
            payer_bank=data.get("ПлательщикБанк1") or None,
            payer_bik=data.get("ПлательщикБИК") or None,
            payee_name=data.get("Получатель", ""),
            payee_inn=data.get("ПолучательИНН") or None,
            payee_kpp=data.get("ПолучательКПП") or None,
            payee_account=payee_account or None,
            payee_bank=data.get("ПолучательБанк1") or None,
            payee_bik=data.get("ПолучательБИК") or None,
            purpose=data.get("НазначениеПлатежа"),
            payment_type=data.get("ВидОплаты"),
            priority=int(data["Очередность"]) if "Очередность" in data else None,
            raw_data=data,
        )

    @staticmethod
    def _parse_date(value: str | None) -> date:
        if not value:
            raise ValueError("Empty date value")
        return datetime.strptime(value, "%d.%m.%Y").date()


def extract_invoice_numbers_from_purpose(purpose: str) -> list[str]:
    """Извлекает все номера счетов из назначения платежа."""
    if not purpose:
        return []
    numbers = []
    for pattern in INVOICE_NUMBER_PATTERNS:
        for match in pattern.finditer(purpose):
            numbers.append(match.group(1))
    return list(set(numbers))