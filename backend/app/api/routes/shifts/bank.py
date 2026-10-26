"""Модуль bank для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.bank_statement import BankTransaction
from app.models.finance import Act
from app.models.catalog import Vehicle
from app.services.bank_integration_service import bank_integration_service
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.bank_statement import BankTransaction
from app.models.finance import Act
from app.models.catalog import Vehicle
from app.services.bank_integration_service import bank_integration_service

router = APIRouter()

async def import_bank_payments(
    file: UploadFile = File(...),
    format: str = Body(default="auto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Импортировать платёжные поручения из файла 1С или банк-клиента."""
    from app.services.bank_integration_service import bank_integration_service

    content = await file.read()
    filename = file.filename or ""

    # Auto-detect format
    if format == "auto":
        if filename.endswith(".xml") or content[:5] == b"<?xml" or b"<FileExchange" in content or "<ФайлОбмен" in content.decode("utf-8-sig", errors="ignore"):
            format = "1c_xml"
        elif filename.endswith(".csv") or filename.endswith(".txt"):
            format = "csv"
        else:
            format = "1c_xml"  # Default

    if format == "1c_xml":
        payments = bank_integration_service.parse_1c_xml(content.decode("utf-8-sig"))
    elif format == "csv":
        payments = bank_integration_service.parse_csv(content.decode("utf-8-sig"))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    result = bank_integration_service.sync_payments_to_db(db, company_id, payments)
    return {"message": f"Импортировано {result['created']} платежей", **result}



def auto_match_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически сопоставить входящие платежи с неоплаченными актами по ИНН + сумме."""
    # from app.models.finance import BankTransaction  # TODO: find correct module

    # Get unmatched incoming payments for this company
    payments = db.execute(
        select(BankTransaction).where(
            BankTransaction.company_id == company_id,
            BankTransaction.matched_invoice_id.is_(None),
            BankTransaction.status == "processed",
        )
    ).scalars().all()

    # Get unpaid acts
    unpaid_acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
            Act.paid_amount < Act.total_amount,
        )
    ).scalars().all()

    matched = 0
    partial = 0

    for payment in payments:
        best_act = None
        for act in unpaid_acts:
            remaining = (act.total_amount or 0) - (act.paid_amount or 0)
            if remaining <= 0:
                continue

            # Match by amount (exact or within 1%)
            amount_match = abs(payment.amount - remaining) < max(remaining * 0.01, 1)

            # Match by payer INN (if available)
            inn_match = False
            if payment.payer_inn and act.counterparty_inn:
                inn_match = payment.payer_inn == act.counterparty_inn

            # Match by purpose containing act number
            purpose_match = False
            if payment.purpose and getattr(act, 'document_number', None) or f'ACT-{act.id}':
                purpose_match = getattr(act, 'document_number', None) or f'ACT-{act.id}'.replace("-", "") in payment.purpose.replace("-", "").replace(" ", "")

            if amount_match and (inn_match or purpose_match or not act.counterparty_inn):
                best_act = act
                break

        if best_act:
            payment.matched_act_id = best_act.id
            best_act.paid_amount = (best_act.paid_amount or 0) + payment.amount
            if best_act.paid_amount >= best_act.total_amount:
                best_act.payment_status = "paid"
            else:
                best_act.payment_status = "partial"
                partial += 1
            matched += 1

    db.commit()
    return {"matched": matched, "partial": partial, "total_payments": len(payments)}



def get_receivables_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд дебиторской задолженности: просроченные акты, ageing buckets."""
    from datetime import date as date_type, timedelta

    today = date_type.today()

    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
        )
    ).scalars().all()

    total_outstanding = 0
    overdue_amount = 0
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    overdue_acts = []

    for act in acts:
        outstanding = (act.total_amount or 0) - (act.paid_amount or 0)
        if outstanding <= 0:
            continue

        total_outstanding += outstanding
        days_since = (today - act.act_date).days if act.act_date else 0

        if days_since > 30:
            overdue_amount += outstanding
            vehicle = db.get(Vehicle, act.vehicle_id) if act.vehicle_id else None
            overdue_acts.append({
                "id": act.id,
                "act_number": getattr(act, 'document_number', None) or f'ACT-{act.id}',
                "act_date": str(act.act_date),
                "vehicle_name": vehicle.name if vehicle else "",
                "counterparty": act.counterparty_name or act.driver_name or "",
                "outstanding": round(outstanding, 2),
                "days_overdue": days_since - 30,
                "status": act.status,
            })

        if days_since <= 30:
            buckets["current"] += outstanding
        elif days_since <= 60:
            buckets["1_30"] += outstanding
        elif days_since <= 90:
            buckets["31_60"] += outstanding
        elif days_since <= 120:
            buckets["61_90"] += outstanding
        else:
            buckets["90_plus"] += outstanding

    overdue_acts.sort(key=lambda x: x["days_overdue"], reverse=True)

    return {
        "summary": {
            "total_outstanding": round(total_outstanding, 2),
            "overdue_amount": round(overdue_amount, 2),
            "overdue_count": len(overdue_acts),
            "on_time_amount": round(total_outstanding - overdue_amount, 2),
        },
        "ageing_buckets": {k: round(v, 2) for k, v in buckets.items()},
        "overdue_acts": overdue_acts[:50],
    }


# === Bank Transactions Management ===


def list_bank_transactions(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    matched: str | None = Query(default=None, description="matched/unmatched/all"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список банковских транзакций с фильтрами."""
    from datetime import date as date_type
    from sqlalchemy import func
    # from app.models.finance import BankTransaction  # TODO: find correct module

    stmt = select(BankTransaction).where(BankTransaction.company_id == company_id)

    if date_from:
        stmt = stmt.where(BankTransaction.document_date >= date_from)
    if date_to:
        stmt = stmt.where(BankTransaction.document_date <= date_to)
    if matched == "matched":
        stmt = stmt.where(BankTransaction.matched_invoice_id.isnot(None))
    elif matched == "unmatched":
        stmt = stmt.where(BankTransaction.matched_invoice_id.is_(None))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(BankTransaction.document_date.desc(), BankTransaction.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    txns = db.execute(stmt).scalars().all()

    items = []
    for t in txns:
        act = db.get(Act, t.matched_act_id) if t.matched_act_id else None
        items.append({
            "id": t.id, "doc_number": t.document_number, "doc_date": t.document_date,
            "payer_name": t.payer_name, "payer_inn": t.payer_inn,
            "payee_name": t.payee_name, "amount": t.amount,
            "purpose": t.purpose, "status": t.status,
            "matched_act_id": t.matched_act_id,
            "matched_act_number": getattr(act, 'document_number', None) or f'ACT-{act.id}' if act else None,
            "source": t.source,
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page if per_page > 0 else 0}



def manual_match_transaction(
    txn_id: int,
    act_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Вручную привязать банковскую транзакцию к акту."""
    # from app.models.finance import BankTransaction  # TODO: find correct module

    txn = db.get(BankTransaction, txn_id)
    if not txn or txn.company_id != company_id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    act = db.get(Act, act_id)
    if not act or act.company_id != company_id:
        raise HTTPException(status_code=404, detail="Act not found")

    txn.matched_act_id = act_id
    act.paid_amount = (act.paid_amount or 0) + txn.amount
    if act.paid_amount >= (act.total_amount or 0):
        act.payment_status = "paid"
    else:
        act.payment_status = "partial"

    db.commit()
    return {"message": f"Транзакция {txn.doc_number} привязана к акту {getattr(act, 'document_number', None) or f'ACT-{act.id}'}"}



def list_unpaid_acts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Список неоплаченных/частично оплаченных актов для ручного разнесения."""
    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.status.in_(["draft", "sent_to_edo", "signed"]),
        )
    ).scalars().all()

    result = []
    for a in acts:
        outstanding = (a.total_amount or 0) - (a.paid_amount or 0)
        if outstanding > 0:
            vehicle = db.get(Vehicle, a.vehicle_id) if a.vehicle_id else None
            result.append({
                "id": a.id, "act_number": getattr(a, 'document_number', None), "act_date": str(a.act_date),
                "vehicle_name": vehicle.name if vehicle else "",
                "total_amount": a.total_amount, "paid_amount": a.paid_amount or 0,
                "outstanding": round(outstanding, 2),
            })

    result.sort(key=lambda x: x["outstanding"], reverse=True)
    return result



def export_transactions_excel(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    matched: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт банковских транзакций в Excel."""
    import io
    from fastapi.responses import StreamingResponse
    # from app.models.finance import BankTransaction  # TODO: find correct module

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    stmt = select(BankTransaction).where(BankTransaction.company_id == company_id)
    if date_from:
        stmt = stmt.where(BankTransaction.document_date >= date_from)
    if date_to:
        stmt = stmt.where(BankTransaction.document_date <= date_to)
    if matched == "matched":
        stmt = stmt.where(BankTransaction.matched_invoice_id.isnot(None))
    elif matched == "unmatched":
        stmt = stmt.where(BankTransaction.matched_invoice_id.is_(None))
    stmt = stmt.order_by(BankTransaction.document_date.desc())

    txns = db.execute(stmt).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Банковские операции"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Дата", "Номер", "Плательщик", "ИНН", "Сумма", "Назначение", "Акт", "Статус"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    total_amount = 0
    for row_idx, t in enumerate(txns, 2):
        act = db.get(Act, t.matched_act_id) if t.matched_act_id else None
        ws.cell(row=row_idx, column=1, value=t.document_date)
        ws.cell(row=row_idx, column=2, value=t.document_number)
        ws.cell(row=row_idx, column=3, value=t.payer_name or "")
        ws.cell(row=row_idx, column=4, value=t.payer_inn or "")
        ws.cell(row=row_idx, column=5, value=t.amount).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=t.purpose or "")
        ws.cell(row=row_idx, column=7, value=getattr(act, 'document_number', None) or f'ACT-{act.id}' if act else "")
        ws.cell(row=row_idx, column=8, value="Разнесено" if act else "Не разнесено")
        total_amount += t.amount

    last_row = len(txns) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=5, value=round(total_amount, 2)).number_format = '#,##0'
    ws.cell(row=last_row, column=5).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = "bank_transactions.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})



