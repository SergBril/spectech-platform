"""
Сервис для автоматической генерации счетов из сверки данных.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.dispatch import Request
from app.models.finance import Invoice, InvoiceItem
from app.models.shift import ShiftTask
from app.models.telematics import ShiftDataReconciliation

logger = logging.getLogger("spectech.invoice_service")


class InvoiceService:
    """Сервис для генерации счетов из сверки данных."""

    def generate_invoice_from_reconciliation(
        self,
        db: Session,
        reconciliation_id: int,
        invoice_date: date | None = None,
        due_date: date | None = None,
        include_fuel_compensation: bool = True,
        company_id: int | None = None,
        created_by: int | None = None,
    ) -> Invoice:
        """
        Генерирует счёт из сверки данных.

        Логика:
        1. Получает финальные данные из сверки (моточасы, топливо)
        2. Определяет ставку клиента из заявки
        3. Создаёт Invoice + InvoiceItems
        4. Рассчитывает итоговую сумму

        Returns:
            Созданный Invoice
        """
        # 1. Получаем сверку
        reconciliation = db.get(ShiftDataReconciliation, reconciliation_id)
        if not reconciliation:
            raise ValueError(f"Reconciliation {reconciliation_id} not found")

        if reconciliation.reconciliation_status not in (
            "auto_approved",
            "resolved",
        ):
            raise ValueError(
                f"Cannot generate invoice from reconciliation with status "
                f"'{reconciliation.reconciliation_status}'. "
                f"Must be 'auto_approved' or 'resolved'."
            )

        # 2. Получаем ShiftTask и Request
        shift_task = db.get(ShiftTask, reconciliation.shift_task_id)
        if not shift_task:
            raise ValueError(f"ShiftTask {reconciliation.shift_task_id} not found")

        request = db.get(Request, shift_task.request_id)
        if not request:
            raise ValueError(f"Request {shift_task.request_id} not found")

        client_id = request.client_id
        request_id = request.id

        # 3. Определяем ставку клиента
        client_rate = request.client_rate or Decimal("0")
        if not client_rate:
            logger.warning(
                f"Request {request_id} has no client_rate. Using default 5000 RUB/hour."
            )
            client_rate = Decimal("5000")

        # 4. Рассчитываем суммы
        moto_hours = Decimal(str(reconciliation.final_moto_hours or 0))
        fuel_used = Decimal(str(reconciliation.final_fuel_used or 0))

        # Стоимость моточасов
        moto_hours_cost = moto_hours * client_rate

        # Компенсация топлива (опционально)
        fuel_cost = Decimal("0")
        if include_fuel_compensation and fuel_used > 0:
            # Средняя цена дизеля (можно вынести в настройки)
            fuel_price = Decimal("65")  # руб/литр
            fuel_cost = fuel_used * fuel_price

        subtotal = moto_hours_cost + fuel_cost

        # НДС (20% для ОСНО)
        vat_rate = Decimal("20")
        vat_amount = (subtotal * vat_rate / 100).quantize(Decimal("0.01"))
        total = subtotal + vat_amount

        # 5. Генерируем номер документа
        document_number = self._generate_document_number(db, invoice_date)

        # 6. Создаём Invoice
        invoice = Invoice(
            document_number=document_number,
            request_id=request_id,
            client_id=client_id,
            company_id=company_id,
            subtotal=subtotal,
            vat_amount=vat_amount,
            vat_rate=vat_rate,
            total=total,
            tax_system="OSNO",
            is_vat_included=False,
            invoice_date=invoice_date or date.today(),
            due_date=due_date,
            status="draft",
            comment=f"Автоматически создан из сверки #{reconciliation_id}",
            created_by=created_by,
        )
        db.add(invoice)
        db.flush()

        # 7. Создаём позиции счёта
        # Позиция 1: Моточасы
        moto_hours_item = InvoiceItem(
            invoice_id=invoice.id,
            description=f"Аренда спецтехники: {moto_hours} моточасов",
            quantity=moto_hours,
            unit="мото-час",
            unit_price=client_rate,
            amount=moto_hours_cost,
            shift_report_id=reconciliation.shift_task_id,
        )
        db.add(moto_hours_item)

        # Позиция 2: Топливо (опционально)
        if include_fuel_compensation and fuel_used > 0:
            fuel_item = InvoiceItem(
                invoice_id=invoice.id,
                description=f"Компенсация топлива: {fuel_used} литров",
                quantity=fuel_used,
                unit="литр",
                unit_price=Decimal("65"),
                amount=fuel_cost,
            )
            db.add(fuel_item)

        db.commit()
        db.refresh(invoice)

        logger.info(
            f"✅ Invoice #{invoice.id} generated from reconciliation "
            f"#{reconciliation_id}: total={total} RUB"
        )

        return invoice

    def _generate_document_number(self, db: Session, invoice_date: date | None) -> str:
        """
        Генерирует уникальный номер счёта.

        Формат: СЧ-2026-0001
        """
        invoice_date = invoice_date or date.today()
        year = invoice_date.year
        prefix = f"СЧ-{year}-"

        # Находим максимальный номер для этого года
        max_number = (
            db.query(func.max(Invoice.document_number))
            .filter(Invoice.document_number.like(f"{prefix}%"))
            .scalar()
        )

        if max_number:
            # Извлекаем число из последнего номера
            last_number = int(max_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"{prefix}{new_number:04d}"


# Singleton instance
invoice_service = InvoiceService()
