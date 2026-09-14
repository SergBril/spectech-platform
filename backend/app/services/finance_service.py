import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.contractor import Contractor
from app.models.finance import (
    Act,
    DocumentStatus,
    Invoice,
    InvoiceItem,
    Payment,
    Payout,
)
from app.services.email_service import email_service

logger = logging.getLogger("spectech.finance")


def generate_document_number(db: Session, prefix: str) -> str:
    current_year = datetime.now().year
    model_map = {"INV": Invoice, "ACT": Act, "PAY": Payout}
    model = model_map.get(prefix)
    if not model:
        raise ValueError(f"Unknown document prefix: {prefix}")

    pattern = f"{prefix}-{current_year}-%"
    stmt = (
        select(model.document_number)
        .where(model.document_number.like(pattern))
        .order_by(model.document_number.desc())
        .limit(1)
    )
    last_number = db.scalar(stmt)

    if last_number:
        try:
            last_seq = int(last_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}-{current_year}-{next_seq:04d}"


def calculate_invoice_totals(invoice: Invoice) -> None:
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


def _get_field(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def create_invoice(db: Session, payload, current_user: User) -> Invoice:
    import traceback

    logger.info(f"🔄 Creating invoice, payload type: {type(payload).__name__}")

    try:
        company_id = getattr(current_user, "company_id", None)

        invoice = Invoice(
            document_number=generate_document_number(db, "INV"),
            request_id=_get_field(payload, "request_id"),
            client_id=_get_field(payload, "client_id"),
            company_id=company_id,
            invoice_date=_get_field(payload, "invoice_date") or datetime.now(),
            due_date=_get_field(payload, "due_date"),
            vat_rate=_get_field(payload, "vat_rate"),
            comment=_get_field(payload, "comment", ""),
            status=DocumentStatus.draft,
            created_by=current_user.id,
        )
        db.add(invoice)
        db.flush()
        logger.info(f"✅ Invoice #{invoice.id} created")

        items = _get_field(payload, "items", []) or []
        logger.info(f"📦 Adding {len(items)} items")

        for item_data in items:
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=str(_get_field(item_data, "description", "")),
                quantity=_get_field(item_data, "quantity", 1),
                unit=str(_get_field(item_data, "unit", "шт")),
                unit_price=_get_field(item_data, "unit_price", 0),
                shift_report_id=_get_field(item_data, "shift_report_id"),
            )
            db.add(item)

        db.flush()
        calculate_invoice_totals(invoice)
        db.commit()
        db.refresh(invoice)
        logger.info(
            f"✅ Invoice {invoice.document_number} saved, total={invoice.total}"
        )

        # 📧 ОТПРАВЛЯЕМ EMAIL
        try:
            client = (
                db.get(Contractor, invoice.client_id) if invoice.client_id else None
            )
            logger.info(
                f"👥 Client lookup: id={invoice.client_id}, found={client is not None}"
            )

            if client and hasattr(client, "contact_email") and client.contact_email:
                client_name = getattr(client, "name", "") or "Клиент"
                logger.info(f"📧 Sending email to {client.contact_email}")
                success = email_service.send_invoice_created(
                    invoice=invoice,
                    client_email=client.contact_email,
                    client_name=client_name,
                )
                logger.info(f"📧 Email send result: {success}")
            else:
                logger.warning(
                    f"⚠️ Client contact_email not found for invoice #{invoice.document_number}"
                )
        except Exception as email_err:
            logger.error(f"❌ Email sending failed: {email_err}")
            logger.error(traceback.format_exc())

        return invoice

    except Exception as e:
        logger.error(f"❌ create_invoice FAILED: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise


def register_payment(db: Session, payment: Payment) -> None:
    if payment.invoice_id:
        invoice = db.get(Invoice, payment.invoice_id)
        if invoice:
            invoice.paid_amount += payment.amount
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
    invoice_query = select(func.coalesce(func.sum(Invoice.total), 0))
    invoice_paid_query = select(func.coalesce(func.sum(Invoice.paid_amount), 0))
    invoice_count_query = select(func.count(Invoice.id))

    if company_id is not None:
        invoice_query = invoice_query.where(Invoice.company_id == company_id)
        invoice_paid_query = invoice_paid_query.where(Invoice.company_id == company_id)
        invoice_count_query = invoice_count_query.where(
            Invoice.company_id == company_id
        )

    total_revenue = db.scalar(invoice_query) or Decimal("0")
    total_paid = db.scalar(invoice_paid_query) or Decimal("0")
    invoices_count = db.scalar(invoice_count_query) or 0
    total_outstanding = total_revenue - total_paid

    acts_query = select(func.count(Act.id))
    if company_id is not None:
        acts_query = acts_query.where(Act.company_id == company_id)
    acts_count = db.scalar(acts_query) or 0

    payout_query = select(func.count(Payout.id))
    commission_query = select(func.coalesce(func.sum(Payout.platform_commission), 0))
    if company_id is not None:
        payout_query = payout_query.where(Payout.company_id == company_id)
        commission_query = commission_query.where(Payout.company_id == company_id)

    payouts_count = db.scalar(payout_query) or 0
    total_commission = db.scalar(commission_query) or Decimal("0")

    return {
        "total_revenue": total_revenue,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "total_commission_earned": total_commission,
        "invoices_count": invoices_count,
        "acts_count": acts_count,
        "payouts_count": payouts_count,
    }
