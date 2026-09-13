"""Сервис генерации PDF документов."""

from datetime import datetime


def generate_invoice_pdf(
    invoice, client_name: str = "", local_path: str = None
) -> bytes:
    """
    Генерирует PDF для счёта.
    Использует только встроенные шрифты fpdf2 для максимальной надёжности.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()

    # Используем только встроенные шрифты (Helvetica)
    # Кириллица не поддерживается встроенными шрифтами, но зато 100% работает

    # === Заголовок ===
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"INVOICE #{invoice.document_number}", 0, 1, "C")
    pdf.ln(5)

    # === Информация ===
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 7, f"Date: {invoice.invoice_date}", 0, 0)
    pdf.cell(95, 7, f"Due: {invoice.due_date}", 0, 1)
    pdf.cell(0, 7, f"Status: {invoice.status}", 0, 1)
    pdf.ln(3)

    # === Клиент ===
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Client:", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    # Транслитерируем кириллицу в латиницу для отображения
    safe_client = _transliterate(client_name or "Not specified")
    pdf.cell(0, 7, safe_client, 0, 1)
    pdf.ln(5)

    # === Таблица позиций ===
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Items:", 0, 1)
    pdf.ln(2)

    # Заголовки таблицы
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 8, "#", 1, 0, "C", True)
    pdf.cell(90, 8, "Description", 1, 0, "C", True)
    pdf.cell(25, 8, "Qty", 1, 0, "C", True)
    pdf.cell(30, 8, "Price", 1, 0, "C", True)
    pdf.cell(35, 8, "Amount", 1, 1, "C", True)

    # Строки таблицы
    pdf.set_font("Helvetica", "", 9)
    for idx, item in enumerate(invoice.items, 1):
        amount = float(item.amount) if item.amount else 0
        desc = _transliterate(str(item.description or ""))[:50]

        pdf.cell(10, 7, str(idx), 1, 0, "C")
        pdf.cell(90, 7, desc, 1, 0, "L")
        pdf.cell(25, 7, str(item.quantity), 1, 0, "C")
        pdf.cell(30, 7, f"{float(item.unit_price):.2f}", 1, 0, "R")
        pdf.cell(35, 7, f"{amount:.2f}", 1, 1, "R")

    pdf.ln(5)

    # === Итоги ===
    subtotal = float(invoice.subtotal) if invoice.subtotal else 0
    vat_amount = float(invoice.vat_amount) if invoice.vat_amount else 0
    total = float(invoice.total) if invoice.total else 0

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(130, 7, "Subtotal:", 0, 0, "R")
    pdf.cell(60, 7, f"{subtotal:.2f} RUB", 0, 1, "R")

    pdf.cell(130, 7, f"VAT ({invoice.vat_rate}%):", 0, 0, "R")
    pdf.cell(60, 7, f"{vat_amount:.2f} RUB", 0, 1, "R")

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(130, 8, "TOTAL:", 0, 0, "R")
    pdf.cell(60, 8, f"{total:.2f} RUB", 0, 1, "R")

    # === Комментарий ===
    if invoice.comment:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "Comment:", 0, 1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _transliterate(str(invoice.comment)))

    # === Футер ===
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f'Generated: {datetime.now().strftime("%d.%m.%Y %H:%M")}', 0, 1, "C")
    pdf.cell(0, 5, "SpecTech Pro System", 0, 1, "C")

    return pdf.output()


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


def generate_act_pdf(*args, **kwargs):
    """Заглушка."""
    return b""


def generate_payout_pdf(*args, **kwargs):
    """Заглушка."""
    return b""
