"""Эндпоинты экспорта данных: CSV и PDF-отчёты."""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.dispatch import Request, RequestStatusLog
from app.models.finance import Act, Invoice

router = APIRouter()


def _to_str(value) -> str:
    """Безопасная конвертация в строку."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _transliterate(text: str) -> str:
    mapping = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "А": "A",
        "Б": "B",
        "В": "V",
        "Г": "G",
        "Д": "D",
        "Е": "E",
        "Ё": "Yo",
        "Ж": "Zh",
        "З": "Z",
        "И": "I",
        "Й": "Y",
        "К": "K",
        "Л": "L",
        "М": "M",
        "Н": "N",
        "О": "O",
        "П": "P",
        "Р": "R",
        "С": "S",
        "Т": "T",
        "У": "U",
        "Ф": "F",
        "Х": "Kh",
        "Ц": "Ts",
        "Ч": "Ch",
        "Ш": "Sh",
        "Щ": "Sch",
        "Ъ": "",
        "Ы": "Y",
        "Ь": "",
        "Э": "E",
        "Ю": "Yu",
        "Я": "Ya",
    }
    return "".join(mapping.get(c, c if ord(c) < 128 else "?") for c in text or "")


# ==================== CSV EXPORT ====================


@router.get("/invoices/csv")
def export_invoices_csv(
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт списка счетов в CSV с фильтрами."""
    stmt = select(Invoice).options(joinedload(Invoice.items))
    stmt = stmt.where(Invoice.company_id == current_user.company_id)

    if status:
        stmt = stmt.where(Invoice.status == status)
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)

    stmt = stmt.order_by(Invoice.created_at.desc())
    invoices = db.scalars(stmt).unique().all()

    # Формируем CSV
    output = io.StringIO()
    # BOM для корректного отображения кириллицы в Excel
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")

    # Заголовки
    writer.writerow(
        [
            "№ документа",
            "Дата",
            "Срок оплаты",
            "Клиент ID",
            "Сумма без НДС",
            "НДС",
            "Итого",
            "Оплачено",
            "Статус",
            "Комментарий",
        ]
    )

    for inv in invoices:
        writer.writerow(
            [
                inv.document_number or "",
                str(inv.invoice_date or ""),
                str(inv.due_date or ""),
                inv.client_id or "",
                _to_float(inv.subtotal),
                _to_float(inv.vat_amount),
                _to_float(inv.total),
                _to_float(inv.paid_amount),
                _to_str(inv.status),
                (inv.comment or "").replace("\n", " "),
            ]
        )

    content = output.getvalue().encode("utf-8")
    filename = f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/acts/csv")
def export_acts_csv(
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт списка актов в CSV с фильтрами."""
    stmt = select(Act).where(Act.company_id == current_user.company_id)

    if status:
        stmt = stmt.where(Act.status == status)
    if date_from:
        stmt = stmt.where(Act.act_date >= date_from)
    if date_to:
        stmt = stmt.where(Act.act_date <= date_to)

    stmt = stmt.order_by(Act.created_at.desc())
    acts = db.scalars(stmt).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")

    writer.writerow(
        [
            "№ документа",
            "Дата",
            "Клиент ID",
            "Сумма",
            "Статус",
            "Подписан клиентом",
            "Подписан исполнителем",
            "Комментарий",
        ]
    )

    for act in acts:
        writer.writerow(
            [
                act.document_number or "",
                str(act.act_date or ""),
                act.client_id or "",
                _to_float(act.total_amount),
                _to_str(act.status),
                str(act.signed_by_client_at or ""),
                str(act.signed_by_executor_at or ""),
                (act.comment or "").replace("\n", " "),
            ]
        )

    content = output.getvalue().encode("utf-8")
    filename = f"acts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ==================== PDF REPORT ====================


@router.get("/requests/{request_id}/report")
def export_request_report(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PDF-отчёт по заявке со всеми связанными документами."""
    from fpdf import FPDF

    request = db.get(Request, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Загружаем связанные данные
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.request_id == request_id)
        .order_by(Invoice.invoice_date)
    ).all()
    acts = db.scalars(
        select(Act).where(Act.request_id == request_id).order_by(Act.act_date)
    ).all()
    history = db.scalars(
        select(RequestStatusLog)
        .where(RequestStatusLog.request_id == request_id)
        .order_by(RequestStatusLog.changed_at)
    ).all()

    # Создаём PDF
    pdf = FPDF()
    pdf.add_page()
    font_family = "Helvetica"

    # === Заголовок ===
    pdf.set_font(font_family, "B", 18)
    pdf.cell(0, 12, f"REQUEST REPORT #{request.id}", 0, 1, "C")
    pdf.ln(3)

    pdf.set_font(font_family, "", 10)
    pdf.cell(0, 6, f'Generated: {datetime.now().strftime("%d.%m.%Y %H:%M")}', 0, 1, "C")
    pdf.ln(6)

    # === Основная информация ===
    pdf.set_font(font_family, "B", 13)
    pdf.cell(0, 8, "1. REQUEST INFO", 0, 1)
    pdf.set_font(font_family, "", 10)

    info_rows = [
        ("Work type", _transliterate(request.work_type or "N/A")),
        ("Address", _transliterate(request.object_address or "N/A")),
        ("Status", _to_str(request.status).upper()),
        ("Period", f"{request.planned_start} - {request.planned_end}"),
        ("Shift hours", str(request.shift_duration_hours or "N/A")),
        (
            "Client rate",
            f'{_to_float(request.client_rate):.2f} RUB ({request.rate_type or ""})',
        ),
        ("Estimated amount", f"{_to_float(request.estimated_amount):.2f} RUB"),
        ("Priority", (request.priority or "").upper()),
        ("Source", request.source_channel or "N/A"),
    ]
    for label, value in info_rows:
        pdf.cell(60, 6, f"{label}:", 0, 0)
        pdf.cell(0, 6, value, 0, 1)

    if request.comment:
        pdf.ln(2)
        pdf.set_font(font_family, "B", 10)
        pdf.cell(0, 6, "Comment:", 0, 1)
        pdf.set_font(font_family, "", 9)
        pdf.multi_cell(0, 5, _transliterate(request.comment))

    pdf.ln(4)

    # === Счета ===
    pdf.set_font(font_family, "B", 13)
    pdf.cell(0, 8, f"2. INVOICES ({len(invoices)})", 0, 1)

    if invoices:
        pdf.set_font(font_family, "B", 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(45, 7, "Number", 1, 0, "C", True)
        pdf.cell(25, 7, "Date", 1, 0, "C", True)
        pdf.cell(30, 7, "Total", 1, 0, "C", True)
        pdf.cell(30, 7, "Paid", 1, 0, "C", True)
        pdf.cell(30, 7, "Status", 1, 0, "C", True)
        pdf.cell(30, 7, "Progress", 1, 1, "C", True)

        pdf.set_font(font_family, "", 9)
        total_sum = 0.0
        total_paid = 0.0
        for inv in invoices:
            t = _to_float(getattr(inv, "total", 0))
            p = _to_float(getattr(inv, "paid_amount", 0))
            total_sum += t
            total_paid += p
            progress = (p / t * 100) if t > 0 else 0
            # ✅ ТРАНЛИТЕРИРУЕМ document_number
            doc_num = _transliterate(
                getattr(inv, "document_number", "") or f'INV-{getattr(inv, "id", "")}'
            )
            invoice_date = str(getattr(inv, "invoice_date", "") or "")
            status_str = _to_str(getattr(inv, "status", "")).upper()

            pdf.cell(45, 6, doc_num, 1, 0, "L")
            pdf.cell(25, 6, invoice_date, 1, 0, "C")
            pdf.cell(30, 6, f"{t:.2f}", 1, 0, "R")
            pdf.cell(30, 6, f"{p:.2f}", 1, 0, "R")
            pdf.cell(30, 6, status_str, 1, 0, "C")
            pdf.cell(30, 6, f"{progress:.0f}%", 1, 1, "C")

        pdf.set_font(font_family, "B", 9)
        pdf.cell(70, 7, "TOTAL:", 1, 0, "R")
        pdf.cell(30, 7, f"{total_sum:.2f}", 1, 0, "R")
        pdf.cell(30, 7, f"{total_paid:.2f}", 1, 0, "R")
        progress_total = (total_paid / total_sum * 100) if total_sum > 0 else 0
        pdf.cell(30, 7, f"{progress_total:.0f}%", 1, 0, "C")
        pdf.cell(30, 7, "", 1, 1)
    else:
        pdf.set_font(font_family, "I", 10)
        pdf.cell(0, 6, "No invoices linked", 0, 1)

    pdf.ln(4)

    # === Акты ===
    pdf.set_font(font_family, "B", 13)
    pdf.cell(0, 8, f"3. ACTS ({len(acts)})", 0, 1)

    if acts:
        pdf.set_font(font_family, "B", 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(50, 7, "Number", 1, 0, "C", True)
        pdf.cell(30, 7, "Date", 1, 0, "C", True)
        pdf.cell(35, 7, "Amount", 1, 0, "C", True)
        pdf.cell(35, 7, "Status", 1, 0, "C", True)
        pdf.cell(40, 7, "Signed", 1, 1, "C", True)

        pdf.set_font(font_family, "", 9)
        for act in acts:
            signed_client = getattr(act, "signed_by_client_at", None)
            signed_exec = getattr(act, "signed_by_executor_at", None)
            signed = (
                "Both"
                if signed_client and signed_exec
                else (
                    "Client" if signed_client else ("Executor" if signed_exec else "No")
                )
            )
            # ✅ ТРАНЛИТЕРИРУЕМ document_number
            act_num = _transliterate(
                getattr(act, "document_number", "") or f'ACT-{getattr(act, "id", "")}'
            )
            act_date = str(getattr(act, "act_date", "") or "")
            amount = _to_float(getattr(act, "total_amount", 0))
            status_str = _to_str(getattr(act, "status", "")).upper()

            pdf.cell(50, 6, act_num, 1, 0, "L")
            pdf.cell(30, 6, act_date, 1, 0, "C")
            pdf.cell(35, 6, f"{amount:.2f}", 1, 0, "R")
            pdf.cell(35, 6, status_str, 1, 0, "C")
            pdf.cell(40, 6, signed, 1, 1, "C")
    else:
        pdf.set_font(font_family, "I", 10)
        pdf.cell(0, 6, "No acts linked", 0, 1)

    pdf.ln(4)

    # === История статусов ===
    pdf.add_page()
    pdf.set_font(font_family, "B", 13)
    pdf.cell(0, 8, f"4. STATUS HISTORY ({len(history)})", 0, 1)

    if history:
        pdf.set_font(font_family, "B", 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(40, 7, "Date", 1, 0, "C", True)
        pdf.cell(35, 7, "From", 1, 0, "C", True)
        pdf.cell(35, 7, "To", 1, 0, "C", True)
        pdf.cell(80, 7, "Comment", 1, 1, "C", True)

        pdf.set_font(font_family, "", 8)
        for log in history:
            date_str = (
                log.changed_at.strftime("%d.%m.%Y %H:%M") if log.changed_at else ""
            )
            pdf.cell(40, 6, date_str, 1, 0, "C")
            pdf.cell(35, 6, _to_str(log.from_status or "").upper(), 1, 0, "C")
            pdf.cell(35, 6, _to_str(log.to_status).upper(), 1, 0, "C")
            comment = _transliterate(log.comment or "")[:50]
            pdf.cell(80, 6, comment, 1, 1, "L")
    else:
        pdf.set_font(font_family, "I", 10)
        pdf.cell(0, 6, "No history records", 0, 1)

    # === Футер ===
    pdf.ln(8)
    pdf.set_font(font_family, "I", 8)
    pdf.cell(0, 5, "SpecTech Pro System - Request Report", 0, 1, "C")

    pdf_bytes = bytes(pdf.output())
    filename = f"request_{request.id}_report.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
