"""Роутер для актов выполненных работ (PDF, УПД, ТОРГ-12, счёт-фактура)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.finance import Act

logger = logging.getLogger("spectech.acts")
router = APIRouter(tags=["acts"])


@router.get("/{act_id}/pdf")
def download_act_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать PDF акта (только своей компании)."""
    import io

    from fastapi.responses import StreamingResponse

    from app.services.pdf_service import generate_act_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    try:
        pdf_bytes = generate_act_pdf(act)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=act_{act.document_number}.pdf"
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate act PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/{act_id}/invoice-facture")
def download_invoice_facture_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать PDF счёта-фактуры (только своей компании)."""
    import io

    from fastapi.responses import StreamingResponse

    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.pdf_generator import generate_invoice_facture_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    request = db.get(Request, act.request_id) if act.request_id else None
    contractor = db.get(Contractor, act.client_id)

    try:
        pdf_bytes = generate_invoice_facture_pdf(act, request, contractor)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=sf_{act.document_number}.pdf"
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate invoice facture PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/{act_id}/upd")
def download_upd_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать PDF УПД (только своей компании)."""
    import io

    from fastapi.responses import StreamingResponse

    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.pdf_generator import generate_upd_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    company = db.get(Company, act.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        pdf_bytes = generate_upd_pdf(act, company, client, request)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=upd_{act.document_number}.pdf"
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate UPD PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/{act_id}/torg12")
def download_torg12_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать PDF ТОРГ-12 (только своей компании)."""
    import io

    from fastapi.responses import StreamingResponse

    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.pdf_generator import generate_torg12_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    company = db.get(Company, act.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        pdf_bytes = generate_torg12_pdf(act, company, client, request)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=torg12_{act.document_number}.pdf"
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate TORG-12 PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
