"""Сервис генерации PDF документов."""

from datetime import datetime


def _to_str(value) -> str:
    """Безопасная конвертация enum/Decimal/str в строку."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _to_float(value) -> float:
    """Безопасная конвертация Decimal/str/int в float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _transliterate(text: str) -> str:
    """Простая транслитерация кириллицы в латиницу."""
    if not text:
        return ""
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
    result = []
    for char in text:
        if char in mapping:
            result.append(mapping[char])
        elif ord(char) < 128:
            result.append(char)
        else:
            result.append("?")
    return "".join(result)


def generate_invoice_pdf(
    invoice, client_name: str = "", local_path: str = None
) -> bytes:
    """Генерирует PDF для счёта."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    font_family = "Helvetica"

    # === Заголовок (с пробелом между INVOICE и #) ===
    pdf.set_font(font_family, "B", 16)
    pdf.cell(0, 10, f"INVOICE  #{invoice.document_number}", 0, 1, "C")
    pdf.ln(5)

    # === Информация (статус через .value) ===
    pdf.set_font(font_family, "", 10)
    pdf.cell(95, 7, f"Date: {invoice.invoice_date}", 0, 0)
    pdf.cell(95, 7, f"Due: {invoice.due_date}", 0, 1)
    pdf.cell(0, 7, f"Status: {_to_str(invoice.status).upper()}", 0, 1)
    pdf.ln(3)

    # === Клиент ===
    pdf.set_font(font_family, "B", 11)
    pdf.cell(0, 7, "Client:", 0, 1)
    pdf.set_font(font_family, "", 10)
    safe_client = _transliterate(client_name or "Not specified")
    pdf.cell(0, 7, safe_client, 0, 1)
    pdf.ln(5)

    # === Таблица позиций ===
    pdf.set_font(font_family, "B", 11)
    pdf.cell(0, 7, "Items:", 0, 1)
    pdf.ln(2)

    pdf.set_font(font_family, "B", 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 8, "#", 1, 0, "C", True)
    pdf.cell(90, 8, "Description", 1, 0, "C", True)
    pdf.cell(25, 8, "Qty", 1, 0, "C", True)
    pdf.cell(30, 8, "Price", 1, 0, "C", True)
    pdf.cell(35, 8, "Amount", 1, 1, "C", True)

    pdf.set_font(font_family, "", 9)
    for idx, item in enumerate(invoice.items, 1):
        amount = _to_float(item.amount)
        desc = _transliterate(str(item.description or ""))[:50]

        pdf.cell(10, 7, str(idx), 1, 0, "C")
        pdf.cell(90, 7, desc, 1, 0, "L")
        pdf.cell(25, 7, str(item.quantity), 1, 0, "C")
        pdf.cell(30, 7, f"{_to_float(item.unit_price):.2f}", 1, 0, "R")
        pdf.cell(35, 7, f"{amount:.2f}", 1, 1, "R")

    pdf.ln(5)

    # === Итоги ===
    subtotal = _to_float(invoice.subtotal)
    vat_amount = _to_float(invoice.vat_amount)
    total = _to_float(invoice.total)
    vat_rate = _to_float(invoice.vat_rate)

    pdf.set_font(font_family, "", 10)
    pdf.cell(130, 7, "Subtotal:", 0, 0, "R")
    pdf.cell(60, 7, f"{subtotal:.2f} RUB", 0, 1, "R")

    pdf.cell(130, 7, f"VAT ({vat_rate:.2f}%):", 0, 0, "R")
    pdf.cell(60, 7, f"{vat_amount:.2f} RUB", 0, 1, "R")

    pdf.set_font(font_family, "B", 12)
    pdf.cell(130, 8, "TOTAL:", 0, 0, "R")
    pdf.cell(60, 8, f"{total:.2f} RUB", 0, 1, "R")

    # === Комментарий ===
    if invoice.comment:
        pdf.ln(5)
        pdf.set_font(font_family, "B", 10)
        pdf.cell(0, 7, "Comment:", 0, 1)
        pdf.set_font(font_family, "", 9)
        pdf.multi_cell(0, 6, _transliterate(str(invoice.comment)))

    # === Футер ===
    pdf.ln(10)
    pdf.set_font(font_family, "I", 8)
    pdf.cell(0, 5, f'Generated: {datetime.now().strftime("%d.%m.%Y %H:%M")}', 0, 1, "C")
    pdf.cell(0, 5, "SpecTech Pro System", 0, 1, "C")

    return bytes(pdf.output())


def generate_act_pdf(*args, **kwargs):
    return b""


def generate_payout_pdf(*args, **kwargs):
    return b""
