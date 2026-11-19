"""Модуль diadoc для shifts router."""

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.finance import Act
from app.models.shift import ShiftTask

router = APIRouter()


@router.post("/diadoc/send-act", summary="📨 Отправить акт через Diadoc")
async def send_act_via_diadoc(
    act_id: int = Body(...),
    counterparty_box_id: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить акт выполненных работ контрагенту через Diadoc ЭДО."""
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.diadoc_service import diadoc_service
    from app.services.edoxml.upd_xml_generator import generate_upd_xml, validate_upd_xml

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    company = db.get(Company, act.company_id) if act.company_id else None
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    client = db.get(Contractor, act.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    request = db.get(Request, act.request_id) if act.request_id else None

    xml_bytes = generate_upd_xml(act, company, client, request)

    # Невалидный по формату ФНС документ контрагенту не отправляем.
    xsd_ok, xsd_errors = validate_upd_xml(xml_bytes)
    if not xsd_ok:
        raise HTTPException(
            status_code=400,
            detail=f"УПД не проходит формат ФНС: {'; '.join(xsd_errors[:2])}",
        )

    token = await diadoc_service.authenticate(company=company)
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    result = await diadoc_service.send_act(
        xml_bytes, counterparty_box_id, token, company=company
    )

    # Update act status
    if result.get("status") == "sent" or result.get("status") == "sent_stub":
        act.status = "sent_to_edo"
        act.edo_message_id = result.get("message_id")
        db.commit()

    return {"message": "Акт отправлен через Diadoc", **result}


@router.get("/diadoc/counterparties", summary="👥 Контрагенты Diadoc")
async def list_diadoc_counterparties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Контрагенты Diadoc только своей компании (фильтр по ИНН контрагентов)."""
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.services.diadoc_service import diadoc_service

    company = db.get(Company, company_id)

    # ИНН контрагентов компании; пустые/NULL исключаем, чтобы не матчить лишнее
    company_inns = {
        inn
        for inn in db.scalars(
            select(Contractor.inn).where(Contractor.company_id == company_id)
        ).all()
        if inn
    }
    if not company_inns:
        return []

    token = await diadoc_service.authenticate(company=company)
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    counterparties = await diadoc_service.get_counterparties(token, company=company)
    return [cp for cp in counterparties if cp.get("inn") and cp["inn"] in company_inns]


@router.get("/diadoc/status/{message_id}", summary="📊 Статус документа")
async def get_diadoc_document_status(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статус документа Diadoc только по актам своей компании."""
    from app.models.company import Company
    from app.services.diadoc_service import diadoc_service

    # Документ должен быть привязан к акту текущей компании
    act = db.scalar(
        select(Act).where(
            Act.edo_message_id == message_id,
            Act.company_id == company_id,
        )
    )
    if not act:
        raise HTTPException(status_code=404, detail="Document not found")

    company = db.get(Company, company_id)
    token = await diadoc_service.authenticate(company=company)
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    result = await diadoc_service.get_document_status(
        message_id, token, company=company
    )
    return result


@router.post("/diadoc/refresh-statuses", summary="🔄 Обновить все статусы")
async def refresh_all_diadoc_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массово обновить статусы всех актов, отправленных через Diadoc."""
    from app.models.company import Company
    from app.services.diadoc_service import diadoc_service

    acts = (
        db.execute(
            select(Act).where(
                Act.company_id == company_id,
                Act.status.in_(["sent_to_edo"]),
            )
        )
        .scalars()
        .all()
    )

    if not acts:
        return {"updated": 0, "message": "Нет актов для обновления"}

    company = db.get(Company, company_id)
    token = await diadoc_service.authenticate(company=company)
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    updated = 0
    for act in acts:
        edo_msg_id = getattr(act, "edo_message_id", None)
        if not edo_msg_id:
            continue
        result = await diadoc_service.get_document_status(
            edo_msg_id, token, company=company
        )
        new_status = result.get("status", "")
        if new_status in ("signed", "rejected") and act.status != new_status:
            act.status = new_status
            updated += 1

    db.commit()
    return {"updated": updated, "total_checked": len(acts)}


@router.post("/diadoc/bulk-send", summary="📨 Массовая отправка актов")
async def bulk_send_acts_via_diadoc(
    act_ids: list[int] = Body(...),
    counterparty_box_id: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Массово отправить несколько актов одному контрагенту через Diadoc."""
    from app.models.company import Company
    from app.models.contractor import Contractor
    from app.models.dispatch import Request
    from app.services.diadoc_service import diadoc_service
    from app.services.edoxml.upd_xml_generator import generate_upd_xml, validate_upd_xml

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    token = await diadoc_service.authenticate(company=company)
    if not token:
        raise HTTPException(status_code=503, detail="Diadoc authentication failed")

    sent = 0
    errors = 0

    for act_id in act_ids:
        act = db.get(Act, act_id)
        if not act or act.company_id != company_id:
            errors += 1
            continue
        if act.status != "draft":
            errors += 1
            continue

        client = db.get(Contractor, act.client_id)
        if not client:
            errors += 1
            continue
        request = db.get(Request, act.request_id) if act.request_id else None

        xml_bytes = generate_upd_xml(act, company, client, request)

        # Один невалидный акт не должен ронять весь батч.
        xsd_ok, _xsd_errors = validate_upd_xml(xml_bytes)
        if not xsd_ok:
            errors += 1
            continue

        result = await diadoc_service.send_act(
            xml_bytes, counterparty_box_id, token, company=company
        )
        if result.get("status") in ("sent", "sent_stub"):
            act.status = "sent_to_edo"
            act.edo_message_id = result.get("message_id")
            sent += 1
        else:
            errors += 1

    db.commit()
    return {"sent": sent, "errors": errors, "total": len(act_ids)}


@router.get("/acts/registry", summary="📋 Реестр актов")
def get_acts_registry(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    status: str | None = Query(default=None),
    min_amount: float | None = Query(default=None),
    max_amount: float | None = Query(default=None),
    search: str | None = Query(
        default=None, description="Поиск по номеру акта или технике"
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Реестр актов с фильтрацией, поиском и пагинацией."""
    from datetime import date as date_type

    from sqlalchemy import func, or_

    stmt = select(Act).where(Act.company_id == company_id)

    if date_from:
        stmt = stmt.where(Act.act_date >= date_type.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Act.act_date <= date_type.fromisoformat(date_to))
    if status:
        stmt = stmt.where(Act.status == status)
    if min_amount is not None:
        stmt = stmt.where(Act.total_amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Act.total_amount <= max_amount)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.outerjoin(Vehicle, Act.vehicle_id == Vehicle.id).where(
            or_(
                getattr(Act, "document_number", Act.id).ilike(search_pattern),
                Vehicle.name.ilike(search_pattern),
            )
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginated results
    stmt = stmt.order_by(Act.act_date.desc(), Act.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    acts = db.execute(stmt).scalars().all()

    items = []
    for a in acts:
        vehicle = (
            db.get(Vehicle, getattr(a, "vehicle_id", None))
            if getattr(a, "vehicle_id", None)
            else None
        )
        items.append(
            {
                "id": a.id,
                "act_number": getattr(a, "document_number", None),
                "act_date": str(a.act_date),
                "vehicle_name": vehicle.name if vehicle else "",
                "driver_name": getattr(a, "driver_name", None) or "",
                "hours_worked": getattr(a, "hours_worked", None),
                "total_amount": a.total_amount,
                "vat_amount": a.vat_amount,
                "status": a.status,
                "edo_message_id": getattr(a, "edo_message_id", None),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


# === Digital Signature (КЭП) ===


@router.post("/acts/{act_id}/sign", summary="✍️ Подписать акт КЭП")
async def sign_act_with_kep(
    act_id: int,
    certificate_thumbprint: str = Body(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подписать акт квалифицированной электронной подписью."""
    from xml.etree.ElementTree import Element, SubElement, tostring

    from app.services.digital_signature_service import digital_signature_service

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    # Generate XML for signing
    root = Element("UniversalTransferDocument")
    root.set("Function", "СЧФДОП")
    root.set("Date", str(act.act_date))
    root.set("Number", getattr(act, "document_number", None) or f"ACT-{act.id}")

    item = SubElement(root, "Item")
    SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
    SubElement(item, "Quantity").text = str(act.hours_worked or 0)
    SubElement(item, "Total").text = str(act.total_amount or 0)

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    result = await digital_signature_service.sign_document(
        xml_bytes, certificate_thumbprint
    )

    if result.get("status") in ("signed", "signed_stub"):
        act.signature = result.get("signature", "")
        act.signed_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        act.signed_by = current_user.id
        if act.status == "draft":
            act.status = "signed"
        db.commit()
        return {
            "message": "Акт подписан КЭП",
            "signature_length": len(result.get("signature", "")),
            **result,
        }
    else:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Signing failed")
        )


@router.get("/acts/{act_id}/verify-signature", summary="🔍 Проверить подпись")
async def verify_act_signature(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Проверить КЭП акта."""
    from xml.etree.ElementTree import Element, SubElement, tostring

    from app.services.digital_signature_service import digital_signature_service

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    if not act.signature:
        return {"valid": False, "message": "Акт не подписан"}

    # Reconstruct XML for verification
    root = Element("UniversalTransferDocument")
    root.set("Function", "СЧФДОП")
    root.set("Date", str(act.act_date))
    root.set("Number", getattr(act, "document_number", None) or f"ACT-{act.id}")
    item = SubElement(root, "Item")
    SubElement(item, "Name").text = f"Услуги спецтехники ({act.act_date})"
    SubElement(item, "Quantity").text = str(act.hours_worked or 0)
    SubElement(item, "Total").text = str(act.total_amount or 0)
    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    result = await digital_signature_service.verify_signature(xml_bytes, act.signature)
    return {
        "valid": result.get("valid", False),
        "provider": result.get("provider", ""),
        "signed_at": act.signed_at.isoformat() if act.signed_at else None,
    }


# === Document Archive ===


@router.get("/acts/export/1c", summary="📥 Экспорт для 1С")
def export_acts_for_1c(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Выгрузка завершённых смен в формате XML для импорта в 1С:Бухгалтерия."""
    from datetime import date as date_type
    from xml.etree.ElementTree import Element, SubElement, tostring

    from fastapi.responses import Response

    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    tasks = (
        db.execute(
            select(ShiftTask)
            .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
            .where(Vehicle.company_id == company_id)
            .where(ShiftTask.shift_date >= d_from)
            .where(ShiftTask.shift_date <= d_to)
            .where(ShiftTask.status == "completed")
            .order_by(ShiftTask.shift_date)
        )
        .scalars()
        .all()
    )

    root = Element("ActsExport")
    root.set("company_id", str(company_id))
    root.set("date_from", str(d_from))
    root.set("date_to", str(d_to))
    root.set("generated_at", __import__("datetime").datetime.now().isoformat())

    for t in tasks:
        act = SubElement(root, "Act")
        SubElement(act, "ActId").text = str(t.id)
        SubElement(act, "Date").text = str(t.shift_date)

        vehicle = db.get(Vehicle, t.vehicle_id)
        SubElement(act, "VehicleName").text = vehicle.name if vehicle else ""
        SubElement(act, "VehicleRegNumber").text = (
            getattr(vehicle, "plate_number", "") or ""
        )

        driver_name = ""
        if t.operator_id:
            profile = db.get(DriverProfile, t.operator_id)
            if profile:
                emp = db.get(Employee, profile.employee_contractor_id)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""
        SubElement(act, "DriverName").text = driver_name

        SubElement(act, "PlannedStart").text = (
            getattr(t, "planned_start", None).isoformat()
            if getattr(t, "planned_start", None)
            else ""
        )
        SubElement(act, "PlannedEnd").text = (
            getattr(t, "planned_end", None).isoformat()
            if getattr(t, "planned_end", None)
            else ""
        )

        hours = 0
        if getattr(t, "planned_start", None) and getattr(t, "planned_end", None):
            hours = round(
                (
                    getattr(t, "planned_end", None) - getattr(t, "planned_start", None)
                ).total_seconds()
                / 3600,
                2,
            )
        SubElement(act, "HoursWorked").text = str(hours)

        distance = getattr(t, "odometer_distance", None)
        SubElement(act, "DistanceKm").text = str(distance) if distance else "0"

        # Financial fields (placeholder for integration)
        SubElement(act, "HourlyRate").text = "0"
        SubElement(act, "TotalAmount").text = "0"
        SubElement(act, "VATRate").text = "20"

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")
    filename = f"acts_1c_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xml"

    return Response(
        content=xml_bytes,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/acts/auto-generate", summary="🤖 Автогенерация актов за период")
def auto_generate_acts(
    date_from: str = Body(..., description="Начальная дата в формате YYYY-MM-DD"),
    date_to: str = Body(..., description="Конечная дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически создать акты выполненных работ из завершённых смен за период.

    Создание отдано act_service - тому же, что использует ежемесячная задача.
    Здесь был второй, расходящийся путь: часы из несуществующих planned_start
    через getattr (всегда 0), ставка 1500 и НДС 20% константами, поля driver_name
    и distance_km, которых у Act нет (TypeError), и отсутствие обязательного
    client_id. Акты либо не создавались, либо были бы нулевыми.

    skipped теперь означает «пропущено с причиной» (нет выработки, заказчика или
    ставки), а не «акт уже существует»: причины возвращаются явно.
    """
    from datetime import date as date_type

    from app.services.act_service import generate_acts_for_shifts

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    result = generate_acts_for_shifts(
        db, company_id, d_from, d_to, created_by=current_user.id
    )
    db.commit()
    return {
        "message": "Акты успешно сгенерированы",
        "created": result["created"],
        "skipped": len(result["skipped"]),
        "skipped_reasons": result["skipped"],
        "period": f"{d_from} / {d_to}",
    }
