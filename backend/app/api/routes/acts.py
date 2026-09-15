import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.models.finance import Act, DocumentStatus
from app.schemas.finance import ActCreate, ActRead, ActSign
from app.services.email_service import email_service
from app.services.finance_service import generate_document_number
from app.services.pdf_service import generate_act_pdf

logger = logging.getLogger("spectech.acts")

router = APIRouter()


@router.get("", response_model=list[ActRead])
def list_acts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список актов."""
    stmt = select(Act)

    if status_filter:
        stmt = stmt.where(Act.status == status_filter)

    stmt = stmt.order_by(Act.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=ActRead, status_code=201)
def create_act(
    payload: ActCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать акт выполненных работ."""
    import traceback

    act = Act(
        document_number=generate_document_number(db, "ACT"),
        request_id=payload.request_id,
        client_id=payload.client_id,
        company_id=current_user.company_id,
        act_date=payload.act_date,
        total_amount=payload.total_amount,
        status=DocumentStatus.draft,
        comment=payload.comment,
        created_by=current_user.id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    logger.info(f"✅ Act {act.document_number} created by user {current_user.email}")

    # 📧 Уведомляем исполнителя (создателя заявки) о создании акта
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
        # Не прерываем — email не критичен

    return act


@router.get("/{act_id}", response_model=ActRead)
def get_act(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить акт по ID."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    return act


@router.patch("/{act_id}", response_model=ActRead)
def update_act(
    act_id: int,
    payload: ActCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить акт (только если статус draft)."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")

    if act.status != DocumentStatus.draft:
        raise HTTPException(
            status_code=409,
            detail=f"Only draft acts can be edited. Current status: {act.status}",
        )

    act.request_id = payload.request_id
    act.client_id = payload.client_id
    act.act_date = payload.act_date
    act.total_amount = payload.total_amount
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
):
    """Подписать акт (со стороны клиента или исполнителя)."""
    import traceback

    logger.info(
        f"📝 Sign act request: act_id={act_id}, signed_by={payload.signed_by}, user={current_user.email}"
    )

    act = db.get(Act, act_id)
    if not act:
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

            # Уведомляем создателя заявки (исполнителя) через in-app notification
            if act.request_id:
                try:
                    request = db.get(Request, act.request_id)
                    logger.info(
                        f"📋 Request found: id={request.id if request else None}"
                    )

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
                        logger.info(
                            f"🔔 Notification sent to user {request.created_by}"
                        )
                except Exception as notif_err:
                    logger.error(f"❌ Notification failed: {notif_err}")
                    logger.error(traceback.format_exc())
                    # Не прерываем — уведомление не критично

            # 📧 Email клиенту
            try:
                client = db.get(Contractor, act.client_id) if act.client_id else None
                logger.info(
                    f"👥 Client for email: {client.name if client else None}, contact_email={client.contact_email if client else None}"
                )

                # ✅ ИСПРАВЛЕНО: поле называется contact_email, а не email
                if client and hasattr(client, "contact_email") and client.contact_email:
                    success = email_service.send_act_signed(
                        act=act,
                        user_email=client.contact_email,
                        user_name=client.name or "Клиент",
                    )
                    logger.info(f"📧 Client email sent: {success}")
            except Exception as email_err:
                logger.error(f"❌ Client email failed: {email_err}")
                logger.error(traceback.format_exc())

        elif payload.signed_by == "executor":
            if act.signed_by_executor_at:
                raise HTTPException(
                    status_code=409, detail="Act already signed by executor"
                )
            act.signed_by_executor_at = now
            logger.info(f"✅ Act signed by executor at {now}")

            # 📧 Email исполнителю (текущему пользователю)
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
                logger.error(traceback.format_exc())

        # Если обе стороны подписали — акт завершён
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


@router.delete("/{act_id}", status_code=204)
def delete_act(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить акт (только если статус draft)."""
    act = db.get(Act, act_id)
    if not act:
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
):
    """Скачать акт в формате PDF."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")

    client = db.get(Contractor, act.client_id) if act.client_id else None
    client_name = client.name if client else "Клиент"

    try:
        pdf_bytes = generate_act_pdf(act, client_name=client_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

    filename = f"{act.document_number or f'act-{act_id}'}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
