"""Утилиты экспорта заявок в PDF и Excel."""
import io
from datetime import datetime
from typing import Any

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


FONT_REGULAR = "app/services/fonts/DejaVuSans.ttf"
FONT_BOLD = "app/services/fonts/DejaVuSans-Bold.ttf"

STATUS_LABELS = {
    "new": "Новая", "processing": "В обработке", "assigned": "Назначена",
    "confirmed": "Подтверждена", "released": "Выпущена", "in_progress": "В работе",
    "completed": "Завершена", "signed": "Подписана", "closed": "Закрыта",
    "cancelled": "Отменена", "disputed": "Спорная",
}

PRIORITY_LABELS = {
    "low": "Низкий", "normal": "Обычный", "high": "Высокий", "urgent": "Срочный",
}

COLUMNS = [
    ("№", "id", 12),
    ("Тип работы", "work_type", 35),
    ("Адрес", "object_address", 40),
    ("Период", "period", 28),
    ("Категория", "vehicle_category_name", 30),
    ("Клиент", "client_name", 30),
    ("Статус", "status_label", 22),
    ("Приоритет", "priority_label", 18),
    ("Сумма", "amount", 20),
]


def _prepare_rows(requests: list[Any]) -> list[dict]:
    rows = []
    for r in requests:
        data = r if isinstance(r, dict) else r.__dict__
        period = ""
        ps = getattr(r, "planned_start", None) or (r.get("planned_start") if isinstance(r, dict) else None)
        pe = getattr(r, "planned_end", None) or (r.get("planned_end") if isinstance(r, dict) else None)
        if ps:
            start = ps[:10] if isinstance(ps, str) else ps.strftime("%d.%m.%Y")
            end = pe[:10] if isinstance(pe, str) and pe else ""
            if not end and pe:
                end = pe.strftime("%d.%m.%Y") if hasattr(pe, "strftime") else ""
            period = f"{start} — {end}" if end else start

        status = getattr(r, "status", None) or (r.get("status") if isinstance(r, dict) else "")
        priority = getattr(r, "priority", None) or (r.get("priority") if isinstance(r, dict) else "")
        amount = getattr(r, "estimated_amount", None) or getattr(r, "final_amount", None) or (r.get("estimated_amount") or r.get("final_amount") if isinstance(r, dict) else None)

        rows.append({
            "id": getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else ""),
            "work_type": getattr(r, "work_type", "") or (r.get("work_type", "") if isinstance(r, dict) else ""),
            "object_address": getattr(r, "object_address", "") or (r.get("object_address", "") if isinstance(r, dict) else ""),
            "period": period,
            "vehicle_category_name": getattr(r, "vehicle_category_name", "") or (r.get("vehicle_category_name", "") if isinstance(r, dict) else ""),
            "client_name": getattr(r, "client_name", "") or (r.get("client_name", "") if isinstance(r, dict) else ""),
            "status_label": STATUS_LABELS.get(status, status),
            "priority_label": PRIORITY_LABELS.get(priority, priority),
            "amount": f"{float(amount):,.0f} ₽" if amount else "—",
        })
    return rows


def export_requests_pdf(requests: list[Any], title: str = "Заявки") -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", FONT_REGULAR)
    pdf.add_font("DejaVu", "B", FONT_BOLD)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.set_font("DejaVu", "", 8)
    pdf.cell(0, 6, f"Дата выгрузки: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    # Header
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_fill_color(240, 240, 240)
    for label, _, width in COLUMNS:
        pdf.cell(width, 7, label, border=1, fill=True, align="C")
    pdf.ln()

    # Rows
    pdf.set_font("DejaVu", "", 6)
    rows = _prepare_rows(requests)
    for row in rows:
        for _, key, width in COLUMNS:
            val = str(row.get(key, ""))[:50]
            pdf.cell(width, 6, val, border=1, align="L" if key != "amount" else "R")
        pdf.ln()

    return pdf.output()


def export_requests_excel(requests: list[Any], title: str = "Заявки") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]

    header_font = Font(bold=True, size=10)
    header_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLUMNS))
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = Font(bold=True, size=14)
    cell.alignment = Alignment(horizontal="center")

    ws.cell(row=2, column=1, value=f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}").font = Font(size=9)

    # Headers
    for col_idx, (label, _, _) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=4, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")

    # Data
    rows = _prepare_rows(requests)
    for row_idx, row in enumerate(rows, 5):
        for col_idx, (_, key, _) in enumerate(COLUMNS, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row.get(key, ""))
            cell.border = thin_border

    # Auto-width
    for col_idx, (_, _, width) in enumerate(COLUMNS, 1):
        ws.column_dimensions[chr(64 + col_idx) if col_idx <= 26 else "A"].width = width / 2.5

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()