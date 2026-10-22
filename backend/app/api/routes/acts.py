import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.constants import TaxSystem
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.finance import Act, DocumentStatus
from app.schemas.finance import ActCreate, ActRead, ActSign
from app.services.email_service import email_service
from app.services.finance_service import (
    generate_and_save_act_pdf,
    generate_document_number,
)
from app.services.pdf_generator import generate_act_pdf

logger = logging.getLogger("spectech.acts")

router = APIRouter()


@router.get("", response_model=list[ActRead])
def list_acts(
    status_filter: str | None = Query(default=None, alias="status"),
    contractor_id: int | None = Query(
        default=None, description="Фильтр по контрагенту (client_id)"
    ),  # 🆕
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список актов (только своей компании)."""
    stmt = select(Act).where(Act.company_id == company_id)

    if status_filter:
        stmt = stmt.where(Act.status == status_filter)

    # 🆕 Фильтр по контрагенту
    if contractor_id is not None:
        stmt = stmt.where(Act.client_id == contractor_id)

    stmt = stmt.order_by(Act.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=ActRead, status_code=201)
def create_act(
    payload: ActCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать акт выполненных работ (для своей компании)."""
    import traceback
    from decimal import ROUND_HALF_UP, Decimal

    # 💰 Расчёт НДС
    vat_rate = payload.vat_rate or Decimal("0")
    is_vat_included = payload.is_vat_included
    tax_system = payload.tax_system

    # Для УСН/Патент/НПД НДС = 0
    if tax_system != TaxSystem.OSNO.value:
        vat_rate = Decimal("0")

    total_amount = payload.total_amount
    vat_amount = Decimal("0")

    if vat_rate > 0:
        if is_vat_included:
            # НДС уже включён в сумму: vat = total * rate / (100 + rate)
            vat_amount = (
                total_amount * vat_rate / (Decimal("100") + vat_rate)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            # НДС начисляется сверху: vat = total * rate / 100
            vat_amount = (total_amount * vat_rate / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total_amount = total_amount + vat_amount

    act = Act(
        document_number=generate_document_number(db, "ACT"),
        request_id=payload.request_id,
        client_id=payload.client_id,
        company_id=company_id,
        act_date=payload.act_date,
        total_amount=total_amount,
        vat_amount=vat_amount,
        vat_rate=vat_rate,
        is_vat_included=is_vat_included,
        tax_system=tax_system,
        status=DocumentStatus.draft,
        comment=payload.comment,
        created_by=current_user.id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    logger.info(
        f"✅ Act {act.document_number} created by user {current_user.email} "
        f"(total={total_amount}, vat={vat_amount}, rate={vat_rate}%)"
    )

    # 🎨 Автогенерация PDF
    try:
        generate_and_save_act_pdf(act.id, db)
    except Exception as pdf_err:
        logger.error(
            f"⚠️ PDF auto-generation failed for {act.document_number}: {pdf_err}"
        )

    # 📧 Уведомляем исполнителя (создателя заявки)
    try:
        if act.request_id:
            request = db.get(Request, act.request_id)
            if request and request.created_by:
                executor = db.get(User, request.created_by)
                client = db.get(Contractor, act.client_id) if act.client_id else None

                if executor and executor.email:
                    executor_name = executor.full_name or "Исполнитель"
                    client_name = client.name if client else "Клиент"

                    logger.info(f"📧 Sending act_created email to {executor.email}")
                    success = email_service.send_act_created(
                        act=act,
                        executor_email=executor.email,
                        executor_name=executor_name,
                        client_name=client_name,
                    )
                    logger.info(f"📧 Act created email sent: {success}")
    except Exception as email_err:
        logger.error(f"❌ Failed to send act_created email: {email_err}")
        logger.error(traceback.format_exc())

    return act


@router.get("/{act_id}", response_model=ActRead)
def get_act(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить акт по ID (только своей компании)."""
    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")
    return act


@router.patch("/{act_id}", response_model=ActRead)
def update_act(
    act_id: int,
    payload: ActCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить акт (только своей компании, только draft)."""
    from decimal import ROUND_HALF_UP, Decimal

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    if act.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft acts can be edited. Current status: {act.status}",
        )

    # 💰 Пересчёт НДС
    vat_rate = payload.vat_rate or Decimal("0")
    tax_system = payload.tax_system
    if tax_system != TaxSystem.OSNO.value:
        vat_rate = Decimal("0")

    total_amount = payload.total_amount
    vat_amount = Decimal("0")

    if vat_rate > 0:
        if payload.is_vat_included:
            vat_amount = (
                total_amount * vat_rate / (Decimal("100") + vat_rate)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            vat_amount = (total_amount * vat_rate / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total_amount = total_amount + vat_amount

    act.request_id = payload.request_id
    act.client_id = payload.client_id
    act.act_date = payload.act_date
    act.total_amount = total_amount
    act.vat_amount = vat_amount
    act.vat_rate = vat_rate
    act.is_vat_included = payload.is_vat_included
    act.tax_system = tax_system
    act.comment = payload.comment

    db.commit()
    db.refresh(act)
    return act


@router.post("/{act_id}/sign", response_model=ActRead)
async def sign_act(
    act_id: int,
    payload: ActSign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подписать акт (только своей компании)."""
    import traceback

    logger.info(
        f"📝 Sign act request: act_id={act_id}, signed_by={payload.signed_by}, user={current_user.email}"
    )

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    now = datetime.now(UTC)

    try:
        if payload.signed_by == "client":
            if act.signed_by_client_at:
                raise HTTPException(
                    status_code=409, detail="Act already signed by client"
                )
            act.signed_by_client_at = now
            logger.info(f"✅ Act signed by client at {now}")

            # Уведомляем создателя заявки
            if act.request_id:
                try:
                    request = db.get(Request, act.request_id)
                    if (
                        request
                        and hasattr(request, "created_by")
                        and request.created_by
                        and request.created_by != current_user.id
                    ):
                        from app.services.notification_service import (
                            create_notification,
                        )

                        await create_notification(
                            db=db,
                            user_id=request.created_by,
                            title=f"Акт {act.document_number} подписан клиентом",
                            body=f"Клиент подписал акт {act.document_number} на сумму {float(act.total_amount):.2f} ₽",
                            channel="in_app",
                        )
                except Exception as notif_err:
                    logger.error(f"❌ Notification failed: {notif_err}")

            # Email клиенту
            try:
                client = db.get(Contractor, act.client_id) if act.client_id else None
                if client and hasattr(client, "contact_email") and client.contact_email:
                    success = email_service.send_act_signed(
                        act=act,
                        user_email=client.contact_email,
                        user_name=client.name or "Клиент",
                    )

                # Template-based notifications with user prefs
                try:
                    from app.services.notification_prefs_helper import should_notify
                    from app.services.notification_template_service import render_template
                    from app.services.max_messenger_service import max_messenger_service
                    act_num = act.document_number or str(act.id)
                    if current_user and should_notify(db, current_user.id, "act_signed", "max"):
                        tmpl = render_template(db, "act_signed", "max", act_number=act_num)
                        if tmpl:
                            import asyncio
                            loop = asyncio.new_event_loop()
                            loop.run_until_complete(max_messenger_service.notify_user(db, current_user.id, tmpl["subject"], tmpl["body"]))
                            loop.close()
                    if current_user and should_notify(db, current_user.id, "act_signed", "email") and current_user.email:
                        tmpl = render_template(db, "act_signed", "email", act_number=act_num)
                        if tmpl:
                            from app.services.email_service import send_email
                            send_email(current_user.email, tmpl["subject"], tmpl["body"])
                except Exception:
                    pass
                    logger.info(f"📧 Client email sent: {success}")
            except Exception as email_err:
                logger.error(f"❌ Client email failed: {email_err}")

        elif payload.signed_by == "executor":
            if act.signed_by_executor_at:
                raise HTTPException(
                    status_code=409, detail="Act already signed by executor"
                )
            act.signed_by_executor_at = now
            logger.info(f"✅ Act signed by executor at {now}")

            try:
                if current_user.email:
                    success = email_service.send_act_signed(
                        act=act,
                        user_email=current_user.email,
                        user_name=current_user.full_name or "Исполнитель",
                    )
                    logger.info(f"📧 Executor email sent: {success}")
            except Exception as email_err:
                logger.error(f"❌ Executor email failed: {email_err}")

        if act.signed_by_client_at and act.signed_by_executor_at:
            act.status = DocumentStatus.paid
            logger.info(f"✅ Act {act.document_number} fully signed, status=paid")

        db.commit()
        db.refresh(act)

        logger.info(
            f"✅ Act {act.document_number} signed by {payload.signed_by} — SUCCESS"
        )
        return act

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ sign_act FAILED: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")




@router.post("/{act_id}/reject", summary="Reject act", tags=["Finance"])
def reject_act(
    act_id: int,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отклонить акт с указанием причины."""
    from app.models.finance import Act, DocumentStatus
    from app.services.audit_service import log_action

    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")

    if act.status == DocumentStatus.rejected:
        raise HTTPException(status_code=409, detail="Act already rejected")

    act.status = DocumentStatus.rejected
    db.commit()

    log_action(db, current_user.id, "reject", "act", act_id,
               details=f"Act {act.document_number} rejected: {reason}")

    # Send rejection notifications
    try:
        from app.services.notification_prefs_helper import should_notify
        from app.services.notification_template_service import render_template
        from app.services.max_messenger_service import max_messenger_service
        act_num = act.document_number or str(act.id)

        # Notify executor via MAX
        if current_user and should_notify(db, current_user.id, "act_rejected", "max"):
            tmpl = render_template(db, "act_rejected", "max", act_number=act_num)
            if tmpl:
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(max_messenger_service.notify_user(db, current_user.id, tmpl["subject"], tmpl["body"]))
                loop.close()

        # Notify executor via email
        if current_user and should_notify(db, current_user.id, "act_rejected", "email") and current_user.email:
            tmpl = render_template(db, "act_rejected", "email", act_number=act_num)
            if tmpl:
                from app.services.email_service import send_email
                send_email(current_user.email, tmpl["subject"], tmpl["body"])
    except Exception:
        pass

    return {"message": f"Act {act.document_number} rejected", "reason": reason}

@router.delete("/{act_id}", status_code=204)
def delete_act(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить акт (только своей компании, только draft)."""
    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    if act.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft acts can be deleted. Current status: {act.status}",
        )

    db.delete(act)
    db.commit()


@router.get("/{act_id}/pdf")
def download_act_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать акт в формате PDF (только своей компании)."""
    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    request = db.get(Request, act.request_id) if act.request_id else None
    contractor = db.get(Contractor, act.client_id) if act.client_id else None

    if (
        not contractor
        and request
        and hasattr(request, "client_id")
        and request.client_id
    ):
        contractor = db.get(Contractor, request.client_id)

    try:
        pdf_bytes = generate_act_pdf(
            act=act,
            request=request,
            contractor=contractor,
        )
    except Exception as e:
        logger.error(f"PDF generation error for act {act_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

    from urllib.parse import quote

    safe_name = f"act-{act_id}.pdf"
    quote(filename, safe="")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
            '{utf8_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/{act_id}/regenerate-pdf", status_code=201)
def regenerate_act_pdf_endpoint(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Ручная перегенерация PDF (только своей компании)."""
    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    from app.services.finance_service import generate_and_save_act_pdf

    result = generate_and_save_act_pdf(act_id, db)
    if result is None:
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать PDF")

    logger.info(f"📄 PDF regenerated for act #{act_id}: {result['path']}")
    return {
        "status": "success",
        "message": "PDF успешно перегенерирован",
        "data": result,
    }


@router.post("/{act_id}/resend-email", response_model=ActRead)
def resend_act_email(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить акт клиенту повторно (только своей компании)."""
    from app.services.email_service import email_service

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    contractor = db.get(Contractor, act.client_id) if act.client_id else None
    if not contractor:
        raise HTTPException(status_code=400, detail="Act has no client attached")

    if not hasattr(contractor, "contact_email") or not contractor.contact_email:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{contractor.name}' has no contact email",
        )

    client_name = contractor.name or "Клиент"
    success = email_service.send_act_signed(
        act=act,
        user_email=contractor.contact_email,
        user_name=client_name,
    )

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to send email. Check SMTP settings."
        )

    logger.info(f"📧 Act {act.document_number} resent to {contractor.contact_email}")
    return act


@router.get("/{act_id}/invoice-facture")
def download_invoice_facture_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Скачать счёт-фактуру (только для ОСНО с НДС)."""
    from app.core.constants import TaxSystem
    from app.services.pdf_generator import generate_invoice_facture_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    # Счёт-фактура только для ОСНО с НДС > 0
    if act.tax_system != TaxSystem.OSNO.value:
        raise HTTPException(
            status_code=400,
            detail="Счёт-фактура доступна только для ОСНО",
        )

    vat_rate = float(act.vat_rate or 0)
    if vat_rate <= 0:
        raise HTTPException(
            status_code=400,
            detail="Счёт-фактура не генерируется для документов без НДС",
        )

    request = db.get(Request, act.request_id) if act.request_id else None
    contractor = db.get(Contractor, act.client_id) if act.client_id else None

    if not contractor and request and request.client_id:
        contractor = db.get(Contractor, request.client_id)

    try:
        pdf_bytes = generate_invoice_facture_pdf(
            act=act,
            request=request,
            contractor=contractor,
        )
    except Exception as e:
        logger.error(f"PDF generation error for invoice facture {act_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
            '{utf8_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{act_id}/upd")
def download_upd_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать УПД (Универсальный передаточный документ) для акта.

    УПД = Акт + Счёт-фактура в одном документе (для ОСНО с НДС).
    Статус "1" = СЧФДОП (счёт-фактура + передаточный документ).
    Статус "2" = только передаточный документ (для УСН).
    """
    from fastapi.responses import Response

    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.pdf_generator import generate_upd_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Получаем связанную заявку (для описания работ)
    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        pdf_bytes = generate_upd_pdf(act, company, client, request)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
                '{utf8_name}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate UPD PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate UPD: {str(e)}")


@router.get("/{act_id}/torg12")
def download_torg12_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать ТОРГ-12 (Расходная накладная) на основании акта.

    Используется для отгрузки товаров (песок, бетон, щебень, стройматериалы).
    Форма утверждена Постановлением Госкомстата РФ от 25.12.1998 № 132.
    """
    from fastapi.responses import Response

    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.pdf_generator import generate_torg12_pdf

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Получаем связанную заявку
    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        pdf_bytes = generate_torg12_pdf(act, company, client, request)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
                '{utf8_name}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate TORG-12 PDF: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate TORG-12: {str(e)}"
        )


@router.get("/{act_id}/xml")
def download_upd_xml(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать XML УПД для электронного документооборота (формат ФНС 5.03).

    Формат: КНД 1115133 (ФайлОбмИнФХЖ4)
    Кодировка: windows-1251
    XSD: упрощённая схема для валидации структуры
    """
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.edoxml.upd_xml_generator import (
        generate_upd_xml,
        validate_upd_xml,
    )

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        xml_bytes = generate_upd_xml(act, company, client, request)

        is_valid, errors = validate_upd_xml(xml_bytes)
        if is_valid:
            logger.info(f"✅ UPD XML for act {act_id} passed XSD validation")
        else:
            logger.warning(f"⚠️ UPD XML for act {act_id} warnings: {errors}")

        return Response(
            content=xml_bytes,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
                '{utf8_name}"',
                "Content-Length": str(len(xml_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate UPD XML: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate XML: {str(e)}")


@router.get("/{act_id}/signed-xml")
def download_signed_upd_xml(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать XML УПД + отсоединённую подпись (.sig) в одном ZIP-архиве.

    Возвращает архив с двумя файлами:
    - UPD-ACT-2026-XXXX.xml (документ в windows-1251)
    - UPD-ACT-2026-XXXX.xml.sig (отсоединённая подпись CMS/PKCS#7 DER)

    Такой формат используется для загрузки в Диадок/СБИС/Контур.Экстерн.
    """
    import io
    import zipfile

    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.edoxml.signature_service import create_detached_signature
    from app.services.edoxml.upd_xml_generator import generate_upd_xml

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        # Генерация XML
        xml_bytes = generate_upd_xml(act, company, client, request)

        # Создание отсоединённой подписи
        signature_bytes = create_detached_signature(xml_bytes)

        # Упаковка в ZIP (формат для ЭДО)
        base_name = f"UPD-{act.document_number}"
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{base_name}.xml", xml_bytes)
            zf.writestr(f"{base_name}.xml.sig", signature_bytes)
        zip_bytes = zip_buffer.getvalue()

        logger.info(
            f"✅ Signed UPD package created for act {act_id}: "
            f"XML={len(xml_bytes)} bytes, SIG={len(signature_bytes)} bytes"
        )

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{base_name}-signed.zip"',
                "Content-Length": str(len(zip_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to create signed package: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create signed package: {str(e)}"
        )


@router.get("/{act_id}/signature")
def download_upd_signature(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Скачать только отсоединённую подпись (.sig) для XML УПД.

    Формат: CMS/PKCS#7 detached в DER кодировке.
    Используется если XML уже есть и нужна только подпись.
    """
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.edoxml.signature_service import create_detached_signature
    from app.services.edoxml.upd_xml_generator import generate_upd_xml

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    company = db.get(Company, company_id)
    request = db.get(Request, act.request_id) if act.request_id else None

    if not client or not company:
        raise HTTPException(status_code=404, detail="Client or company not found")

    try:
        xml_bytes = generate_upd_xml(act, company, client, request)
        signature_bytes = create_detached_signature(xml_bytes)

        return Response(
            content=signature_bytes,
            media_type="application/pkcs7-signature",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}; filename*=UTF-8'
                '{utf8_name}"',
                "Content-Length": str(len(signature_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Failed to create signature: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create signature: {str(e)}"
        )


@router.get("/{act_id}/signature/verify")
def verify_upd_signature(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Проверить валидность подписи XML УПД (генерирует XML+подпись и проверяет).

    Возвращает JSON с результатом проверки.
    """
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.edoxml.signature_service import (
        create_detached_signature,
        verify_detached_signature,
    )
    from app.services.edoxml.upd_xml_generator import generate_upd_xml

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    company = db.get(Company, company_id)
    request = db.get(Request, act.request_id) if act.request_id else None

    if not client or not company:
        raise HTTPException(status_code=404, detail="Client or company not found")

    try:
        xml_bytes = generate_upd_xml(act, company, client, request)
        signature_bytes = create_detached_signature(xml_bytes)
        is_valid = verify_detached_signature(xml_bytes, signature_bytes)

        return {
            "act_id": act_id,
            "document_number": act.document_number,
            "xml_size": len(xml_bytes),
            "signature_size": len(signature_bytes),
            "signature_valid": is_valid,
            "algorithm": "RSA-SHA256 (development mode)",
            "note": "Для боевого ЭДО используйте ГОСТ Р 34.10-2012 через КриптоПро",
        }
    except Exception as e:
        logger.error(f"Signature verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Signature verification failed: {str(e)}"
        )


@router.post("/{act_id}/send-to-diadoc")
def send_act_to_diadoc(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Отправить подписанный УПД в Диадок (электронный документооборот).

    Процесс:
    1. Генерация XML УПД
    2. Создание отсоединённой подписи (.sig)
    3. Отправка пакета в Диадок API

    Требует настройки переменных окружения:
    - DIADOC_API_KEY
    - DIADOC_BOX_ID
    - DIADOC_USE_SANDBOX (true/false)
    """
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.diadoc_service import diadoc_service
    from app.services.edoxml.signature_service import create_detached_signature
    from app.services.edoxml.upd_xml_generator import generate_upd_xml

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    request = db.get(Request, act.request_id) if act.request_id else None

    try:
        # Генерация XML
        xml_bytes = generate_upd_xml(act, company, client, request)

        # Создание подписи
        signature_bytes = create_detached_signature(xml_bytes)

        # Отправка в Диадок
        result = diadoc_service.send_signed_package(
            xml_bytes=xml_bytes,
            sig_bytes=signature_bytes,
            document_number=act.document_number,
        )

        if result.get("status") == "success":
            logger.info(
                f"✅ Act {act.document_number} sent to Diadoc: "
                f"message_id={result.get('message_id')}"
            )
        else:
            logger.error(
                f"❌ Failed to send act {act.document_number} to Diadoc: "
                f"{result.get('error')}"
            )

        return result

    except Exception as e:
        logger.error(f"Failed to send to Diadoc: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to send to Diadoc: {str(e)}"
        )


@router.get("/{act_id}/mock-files")
def list_mock_diadoc_files(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Список mock-файлов (XML/SIG), сохранённых при эмуляции отправки в Диадок.
    Полезно для проверки корректности генерации ЭДО-пакета без реального ключа.
    """
    from pathlib import Path

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    mock_dir = Path("/tmp/diadoc_mock")
    if not mock_dir.exists():
        return {
            "act_id": act_id,
            "document_number": act.document_number,
            "files": [],
            "total_files": 0,
            "note": "No mock files yet. Use POST /acts/{id}/send-to-diadoc first.",
        }

    doc_base = act.document_number.replace("/", "_").replace(" ", "-")
    files = []
    for f in mock_dir.glob(f"*{doc_base}*"):
        stat = f.stat()
        files.append(
            {
                "filename": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    return {
        "act_id": act_id,
        "document_number": act.document_number,
        "mock_directory": str(mock_dir),
        "files": files,
        "total_files": len(files),
    }
