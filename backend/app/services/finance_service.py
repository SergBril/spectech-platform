from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finance import (
    Act,
    DocumentStatus,
    Invoice,
    InvoiceItem,
    Payment,
    Payout,
)


def generate_document_number(db: Session, prefix: str) -> str:
    """
    Генерирует уникальный номер документа.
    Формат: PREFIX-YYYY-NNNN (например, INV-2026-0001)
    """
    current_year = datetime.now().year

    # Определяем модель по префиксу
    model_map = {
        "INV": Invoice,
        "ACT": Act,
        "PAY": Payout,
    }
    model = model_map.get(prefix)

    if not model:
        raise ValueError(f"Unknown document prefix: {prefix}")

    # Получаем максимальный номер для текущего года
    pattern = f"{prefix}-{current_year}-%"
    stmt = (
        select(model.document_number)
        .where(model.document_number.like(pattern))
        .order_by(model.document_number.desc())
        .limit(1)
    )

    last_number = db.scalar(stmt)

    if last_number:
        # Извлекаем номер из последней записи
        try:
            last_seq = int(last_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}-{current_year}-{next_seq:04d}"


def calculate_invoice_totals(invoice: Invoice) -> None:
    """Пересчитывает итоговые суммы счёта."""
    subtotal = Decimal("0")

    for item in invoice.items:
        item.amount = item.quantity * item.unit_price
        subtotal += item.amount

    invoice.subtotal = subtotal

    if invoice.vat_rate is not None:
        invoice.vat_amount = (subtotal * invoice.vat_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )
    else:
        invoice.vat_amount = Decimal("0")

    invoice.total = subtotal + invoice.vat_amount


def create_invoice(db: Session, payload, user_id: int, company_id: int) -> Invoice:
    """Создаёт счёт с позициями."""
    invoice = Invoice(
        document_number=generate_document_number(db, "INV"),
        request_id=payload.request_id,
        client_id=payload.client_id,
        company_id=company_id,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        vat_rate=payload.vat_rate,
        comment=payload.comment,
        status=DocumentStatus.draft,
        created_by=user_id,
    )
    db.add(invoice)
    db.flush()

    # Создаём позиции
    for item_data in payload.items:
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            shift_report_id=item_data.shift_report_id,
        )
        db.add(item)

    db.flush()

    # Пересчитываем итоги
    calculate_invoice_totals(invoice)

    db.commit()
    db.refresh(invoice)
    return invoice


def register_payment(db: Session, payment: Payment) -> None:
    """
    Регистрирует платёж и обновляет paid_amount у связанных документов.
    """
    if payment.invoice_id:
        invoice = db.get(Invoice, payment.invoice_id)
        if invoice:
            invoice.paid_amount += payment.amount

            # Обновляем статус счёта
            if invoice.paid_amount >= invoice.total:
                invoice.status = DocumentStatus.paid
            elif invoice.paid_amount > 0:
                invoice.status = DocumentStatus.partially_paid

    if payment.payout_id:
        payout = db.get(Payout, payment.payout_id)
        if payout:
            payout.status = DocumentStatus.paid

    db.commit()


def calculate_payout(gross_amount: Decimal, commission_rate: Decimal) -> dict:
    """Рассчитывает выплату с учётом комиссии."""
    commission = (gross_amount * commission_rate / Decimal("100")).quantize(
        Decimal("0.01")
    )
    net_amount = gross_amount - commission

    return {
        "gross_amount": gross_amount,
        "platform_commission": commission,
        "net_amount": net_amount,
        "commission_rate": commission_rate,
    }


def get_finance_dashboard(db: Session, company_id: int | None) -> dict:
    """
    Собирает статистику для финансового дашборда.
    Если company_id = None, показывает все данные (без фильтрации).
    """
    # Базовые фильтры (пустые, если company_id = None)
    invoice_filter = (
        Invoice.company_id == company_id if company_id is not None else True
    )
    act_filter = Act.company_id == company_id if company_id is not None else True
    payout_filter = Payout.company_id == company_id if company_id is not None else True

    # Сумма всех счетов
    total_revenue = db.scalar(
        select(func.coalesce(func.sum(Invoice.total), 0)).where(invoice_filter)
    ) or Decimal("0")

    # Сумма оплаченных счетов
    total_paid = db.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(invoice_filter)
    ) or Decimal("0")

    # Задолженность
    total_outstanding = total_revenue - total_paid

    # Комиссия, заработанная платформой
    total_commission = db.scalar(
        select(func.coalesce(func.sum(Payout.platform_commission), 0)).where(
            payout_filter
        )
    ) or Decimal("0")

    # Количество документов
    invoices_count = (
        db.scalar(select(func.count(Invoice.id)).where(invoice_filter)) or 0
    )

    acts_count = db.scalar(select(func.count(Act.id)).where(act_filter)) or 0

    payouts_count = db.scalar(select(func.count(Payout.id)).where(payout_filter)) or 0

    return {
        "total_revenue": total_revenue,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "total_commission_earned": total_commission,
        "invoices_count": invoices_count,
        "acts_count": acts_count,
        "payouts_count": payouts_count,
    }
