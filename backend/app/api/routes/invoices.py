import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_company_id, get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor
from app.models.finance import DocumentStatus, Invoice
from app.schemas.finance import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
)
from app.services.finance_service import create_invoice, generate_and_save_invoice_pdf
from app.services.pdf_generator import generate_invoice_pdf

logger = logging.getLogger("spectech.invoices")

router = APIRouter()


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список счетов (только своей компании)."""
    stmt = (
        select(Invoice)
        .where(Invoice.company_id == company_id)  # 🆕
        .options(joinedload(Invoice.items))
    )

    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)

    stmt = stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).unique().all()


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice_endpoint(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("invoices", "create")),
):
    """Создать новый счёт (для своей компании)."""
    invoice = create_invoice(
        db=db,
        payload=payload,
        current_user=current_user,
    )
    # 🎨 Автогенерация PDF
    try:
        generate_and_save_invoice_pdf(invoice.id, db)
    except Exception as pdf_err:
        logger.error(
            f"⚠️ PDF auto-generation failed for {invoice.document_number}: {pdf_err}"
        )
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить счёт по ID (только своей компании)."""
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = db.scalar(stmt)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("invoices", "update")),
):
    """Обновить счёт (только своей компании)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.company_id != company_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/send", response_model=InvoiceRead)
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("invoices", "update")),
):
    """Отправить счёт клиенту (только своей компании)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.company_id != company_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft invoices can be sent. Current status: {invoice.status}",
        )

    invoice.status = DocumentStatus.sent
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}", status_code=204)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("invoices", "delete")),
):
    """Отменить счёт (только своей компании)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.company_id != company_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == DocumentStatus.paid:
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel paid invoice",
        )

    invoice.status = DocumentStatus.cancelled
    db.commit()


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать счёт в формате PDF (только своей компании)."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = db.scalar(stmt)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    contractor = db.get(Contractor, invoice.client_id) if invoice.client_id else None

    try:
        pdf_bytes = generate_invoice_pdf(
            invoice=invoice,
            contractor=contractor,
        )
    except Exception as e:
        logger.error(f"PDF generation error for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

    filename = f"{invoice.document_number or f'invoice-{invoice_id}'}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/{invoice_id}/resend-email", response_model=InvoiceRead)
def resend_invoice_email(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить счёт клиенту повторно (только своей компании)."""
    from app.services.email_service import email_service

    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.company_id != company_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    contractor = db.get(Contractor, invoice.client_id) if invoice.client_id else None
    if not contractor:
        raise HTTPException(status_code=400, detail="Invoice has no client attached")

    if not hasattr(contractor, "contact_email") or not contractor.contact_email:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{contractor.name}' has no contact email",
        )

    client_name = contractor.name or "Клиент"
    success = email_service.send_invoice_created(
        invoice=invoice,
        client_email=contractor.contact_email,
        client_name=client_name,
    )

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to send email. Check SMTP settings."
        )

    logger.info(
        f"📧 Invoice {invoice.document_number} resent to {contractor.contact_email}"
    )
    return invoice


@router.post("/{invoice_id}/regenerate-pdf", status_code=201)
def regenerate_invoice_pdf_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Ручная перегенерация PDF (только своей компании)."""
    # Проверка принадлежности
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.company_id != company_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    from app.services.finance_service import generate_and_save_invoice_pdf

    result = generate_and_save_invoice_pdf(invoice_id, db)
    if result is None:
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать PDF")

    logger.info(f"📄 PDF regenerated for invoice #{invoice_id}: {result['path']}")
    return {
        "status": "success",
        "message": "PDF счёта успешно перегенерирован",
        "data": result,
    }
