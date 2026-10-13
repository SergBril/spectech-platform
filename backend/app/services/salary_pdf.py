"""Генерация PDF расчётных листков по зарплатам."""

import logging
from pathlib import Path
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger("spectech.salary_pdf")

# === Регистрация кириллических шрифтов ===
_FONTS_DIR = Path(__file__).parent / "fonts"
_REGULAR_FONT = _FONTS_DIR / "DejaVuSans.ttf"
_BOLD_FONT = _FONTS_DIR / "DejaVuSans-Bold.ttf"

_FONT_REGISTERED = False
if _REGULAR_FONT.exists() and _BOLD_FONT.exists():
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", str(_REGULAR_FONT)))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_BOLD_FONT)))
        _FONT_REGISTERED = True
        logger.info(f"✅ DejaVu fonts loaded from {_FONTS_DIR}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to register DejaVu fonts: {e}")
else:
    logger.warning(
        f"⚠️ DejaVu fonts not found in {_FONTS_DIR}. "
        f"PDF will show squares for Cyrillic. "
        f"Download from https://github.com/dejavu-fonts/dejavu-fonts/tree/master/ttf"
    )


def _get_font(bold: bool = False) -> str:
    """Возвращает имя зарегистрированного шрифта."""
    if _FONT_REGISTERED:
        return "DejaVu-Bold" if bold else "DejaVu"
    return "Helvetica-Bold" if bold else "Helvetica"


SALARY_TYPE_LABELS = {
    "fixed_shift": "Фиксированная за смену",
    "hourly": "Почасовая оплата",
    "per_km": "Оплата за пробег",
    "shift_percent": "Процент от смены",
    "combo": "Комбинированная",
}


def generate_salary_payslip(record, employee_name: str = "") -> bytes:
    """
    Генерирует PDF расчётного листка для одной записи зарплаты.

    Args:
        record: SalaryRecord объект
        employee_name: Имя сотрудника (из Contractor)

    Returns:
        bytes: PDF содержимое
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontName=_get_font(bold=True), fontSize=16, spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle', parent=styles['Normal'],
        fontName=_get_font(), fontSize=10, textColor=colors.grey, spaceAfter=20,
    )
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontName=_get_font(bold=True), fontSize=10,
    )
    value_style = ParagraphStyle(
        'Value', parent=styles['Normal'],
        fontName=_get_font(), fontSize=10,
    )
    total_style = ParagraphStyle(
        'Total', parent=styles['Normal'],
        fontName=_get_font(bold=True), fontSize=14, textColor=colors.HexColor('#16a34a'),
    )

    elements = []

    # Заголовок
    elements.append(Paragraph("РАСЧЁТНЫЙ ЛИСТОК", title_style))
    period_str = f"{record.period_start.strftime('%d.%m.%Y')} — {record.period_end.strftime('%d.%m.%Y')}"
    elements.append(Paragraph(f"Период: {period_str}", subtitle_style))

    # Информация о сотруднике
    info_data = [
        [Paragraph("Сотрудник:", label_style), Paragraph(employee_name or f"#{record.employee_contractor_id}", value_style)],
        [Paragraph("Тип оплаты:", label_style), Paragraph(SALARY_TYPE_LABELS.get(record.salary_type, record.salary_type), value_style)],
        [Paragraph("Статус:", label_style), Paragraph(record.status, value_style)],
        [Paragraph("Дата расчёта:", label_style), Paragraph(record.created_at.strftime('%d.%m.%Y %H:%M') if record.created_at else "—", value_style)],
    ]
    info_table = Table(info_data, colWidths=[50 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10 * mm))

    # Данные за период
    elements.append(Paragraph("Данные за период", label_style))
    metrics_data = [
        ["Показатель", "Значение"],
        ["Количество смен", str(record.shifts_count)],
        ["Отработано часов", f"{float(record.total_hours or 0):.1f}"],
        ["Пробег (км)", f"{float(record.total_km or 0):.1f}"],
    ]
    metrics_table = Table(metrics_data, colWidths=[80 * mm, 80 * mm])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, 0), _get_font(bold=True)),
        ('FONTNAME', (0, 1), (-1, -1), _get_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 10 * mm))

    # Расчёт
    elements.append(Paragraph("Расчёт", label_style))
    calc_data = [
        ["Статья", "Сумма (₽)"],
        ["Начислено (gross)", f"{float(record.gross_amount or 0):,.2f}".replace(",", " ")],
        ["Удержания", f"{float(record.deductions or 0):,.2f}".replace(",", " ")],
    ]
    calc_table = Table(calc_data, colWidths=[80 * mm, 80 * mm])
    calc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, 0), _get_font(bold=True)),
        ('FONTNAME', (0, 1), (-1, -1), _get_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(calc_table)
    elements.append(Spacer(1, 8 * mm))

    # Итого
    net_formatted = f"{float(record.net_amount or 0):,.2f}".replace(",", " ")
    elements.append(Paragraph(f"К ВЫПЛАТЕ: {net_formatted} ₽", total_style))

    # Детали расчёта (если есть)
    if record.calculation_details and isinstance(record.calculation_details, dict):
        formula = record.calculation_details.get("formula", "")
        if formula:
            elements.append(Spacer(1, 5 * mm))
            detail_style = ParagraphStyle(
                'Detail', parent=styles['Normal'],
                fontName=_get_font(), fontSize=8, textColor=colors.grey,
            )
            elements.append(Paragraph(f"Формула: {formula}", detail_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()


def generate_salary_register_pdf(records: list, company_name: str = "") -> bytes:
    """
    Генерирует PDF ведомости зарплат за период (все сотрудники).

    Args:
        records: список SalaryRecord
        company_name: название компании

    Returns:
        bytes: PDF содержимое
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, landscape=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'],
        fontName=_get_font(bold=True), fontSize=14, spaceAfter=10,
    )

    elements = []
    elements.append(Paragraph(f"ВЕДОМОСТЬ НАЧИСЛЕНИЯ ЗАРПЛАТЫ — {company_name}", title_style))

    if records:
        period = f"{records[0].period_start.strftime('%d.%m.%Y')} — {records[0].period_end.strftime('%d.%m.%Y')}"
        elements.append(Paragraph(f"Период: {period}", styles['Normal']))
        elements.append(Spacer(1, 5 * mm))

    header = ["№", "Сотрудник", "Тип", "Смены", "Часы", "Начислено", "Удержания", "К выплате", "Статус"]
    rows = [header]

    total_gross = 0
    total_net = 0

    for i, r in enumerate(records, 1):
        gross = float(r.gross_amount or 0)
        net = float(r.net_amount or 0)
        total_gross += gross
        total_net += net

        status_label = {"draft": "Черновик", "approved": "Утверждено", "paid": "Выплачено"}.get(r.status, r.status)
        rows.append([
            str(i),
            f"#{r.employee_contractor_id}",
            SALARY_TYPE_LABELS.get(r.salary_type, r.salary_type),
            str(r.shifts_count),
            f"{float(r.total_hours or 0):.1f}",
            f"{gross:,.2f}".replace(",", " "),
            f"{float(r.deductions or 0):,.2f}".replace(",", " "),
            f"{net:,.2f}".replace(",", " "),
            status_label,
        ])

    # Итоговая строка
    rows.append([
        "", "ИТОГО", "", "", "",
        f"{total_gross:,.2f}".replace(",", " "),
        "",
        f"{total_net:,.2f}".replace(",", " "),
        "",
    ])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), _get_font(bold=True)),
        ('FONTNAME', (0, 1), (-1, -1), _get_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0fdf4')),
        ('FONTNAME', (0, -1), (-1, -1), _get_font(bold=True)),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()