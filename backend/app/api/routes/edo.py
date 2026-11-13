"""API для ЭДО (Diadoc): отправка документов, статусы, контрагенты."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User

logger = logging.getLogger("spectech.edo")

router = APIRouter(prefix="/edo", tags=["edo"])


@router.post("/send-act/{act_id}")
async def send_act_via_diadoc(
    act_id: int,
    counterparty_box_id: str = Query(..., description="Box ID контрагента в Diadoc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить акт через Diadoc."""
    from app.models.finance import Act
    from app.services.diadoc_service import diadoc_service
    from app.services.digital_signature_service import digital_signature_service

    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    if act.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Authenticate with Diadoc
    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    # Generate UPD XML if not already generated
    act_xml = None
    if hasattr(act, "xml_content") and act.xml_content:
        act_xml = (
            act.xml_content.encode("utf-8")
            if isinstance(act.xml_content, str)
            else act.xml_content
        )
    else:
        # Try to generate XML from edoxml service
        try:
            from app.services.edoxml.upd_generator import generate_upd_xml

            act_xml = generate_upd_xml(db, act)
        except Exception as e:
            logger.warning(f"UPD XML generation failed: {e}")
            raise HTTPException(status_code=400, detail=f"Cannot generate UPD XML: {e}")

    if not act_xml:
        raise HTTPException(status_code=400, detail="No XML content for act")

    # Sign document
    sign_result = await digital_signature_service.sign_document(act_xml)
    if sign_result.get("status") == "error":
        raise HTTPException(
            status_code=500, detail=f"Signing failed: {sign_result.get('error')}"
        )

    # Send via Diadoc
    result = await diadoc_service.send_act(act_xml, counterparty_box_id, token)

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500, detail=f"Diadoc send failed: {result.get('error')}"
        )

    # Update act status
    if hasattr(act, "edo_message_id"):
        act.edo_message_id = result.get("message_id")
    if hasattr(act, "status"):
        act.status = "sent_to_edo"
    db.commit()

    logger.info(f"Act #{act_id} sent to Diadoc: {result.get('message_id')}")
    return {
        "act_id": act_id,
        "message_id": result.get("message_id"),
        "status": result.get("status"),
        "signature_provider": sign_result.get("provider"),
    }


@router.get("/document-status/{message_id}")
async def get_edo_document_status(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить статус документа в Diadoc."""
    from app.services.diadoc_service import diadoc_service

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    result = await diadoc_service.get_document_status(message_id, token)
    return result


@router.get("/counterparties")
async def list_diadoc_counterparties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список контрагентов из Diadoc."""
    from app.services.diadoc_service import diadoc_service

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    counterparties = await diadoc_service.get_counterparties(token)
    return {"counterparties": counterparties, "total": len(counterparties)}


@router.post("/refresh-statuses")
async def refresh_all_diadoc_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить статусы всех отправленных через Diadoc актов."""
    from app.models.finance import Act
    from app.services.diadoc_service import diadoc_service

    token = await diadoc_service.authenticate()
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    acts = (
        db.query(Act)
        .filter(
            Act.company_id == company_id,
            Act.edo_message_id.isnot(None),
            Act.status == "sent_to_edo",
        )
        .all()
    )

    updated = 0
    for act in acts:
        try:
            result = await diadoc_service.get_document_status(act.edo_message_id, token)
            new_status = result.get("status")
            if new_status and new_status != "stub" and new_status != "unknown":
                act.status = new_status
                updated += 1
        except Exception as e:
            logger.warning(f"Failed to refresh status for act #{act.id}: {e}")

    db.commit()
    return {"checked": len(acts), "updated": updated}


@router.post("/webhook/diadoc", summary="🔔 Diadoc webhook callback")
async def diadoc_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Callback от Diadoc: payload — только hint, статус НЕ применяется напрямую.

    Перед применением статус перепроверяется через API (GetMessage).
    API недоступен / нет токена → 503; верификация не дала статуса → 202;
    verified-статус применяется, расхождение с payload логируется.
    """
    from app.models.finance import Act
    from app.services.diadoc_service import diadoc_service

    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid json"}

    message_id = body.get("MessageId", "")
    if not message_id:
        return {"status": "ignored", "reason": "no MessageId"}

    # Привязка: обновляем только акт, отправленный через ЭДО (edo_message_id)
    act = db.query(Act).filter(Act.edo_message_id == message_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Document not found")

    payload_status = body.get("DocflowStatus", {}).get("PrimaryStatus", "")

    token = await diadoc_service.authenticate()
    if not token:
        logger.error(
            "Diadoc webhook: authentication failed, status NOT applied (msg=%s)",
            message_id,
        )
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    verified = await diadoc_service.get_document_status(message_id, token)
    api_status = verified.get("status")
    if api_status in (None, "stub", "error", "unknown"):
        logger.warning(
            "Diadoc webhook: verification unavailable (%s), hint NOT applied (msg=%s)",
            api_status,
            message_id,
        )
        return JSONResponse(
            status_code=202,
            content={"status": "pending_verification", "message_id": message_id},
        )

    # Расхождение payload и API — индикатор попытки подделки
    status_map = {
        "WaitingForSenderSignature": "draft",
        "WaitingForRecipientSignature": "sent_to_edo",
        "WithRecipientSignature": "signed",
        "RecipientSignatureRequestRejected": "rejected",
        "InvalidDocument": "rejected",
    }
    payload_mapped = status_map.get(payload_status, payload_status)
    if payload_mapped and api_status != payload_mapped:
        logger.warning(
            "Diadoc webhook: STATUS MISMATCH payload=%s api=%s (msg=%s) — "
            "applying API status (possible forgery)",
            payload_status,
            api_status,
            message_id,
        )

    old_status = act.status
    act.status = api_status
    if api_status == "signed":
        # Подпись получателя (клиента); колонки signed_at в модели Act нет
        act.signed_by_client_at = datetime.now(UTC)
    db.commit()
    logger.info(
        "📬 Diadoc webhook verified: Act #%s status %s → %s (msg: %s)",
        act.id,
        old_status,
        api_status,
        message_id,
    )
    return {"status": "updated", "act_id": act.id, "new_status": api_status}
