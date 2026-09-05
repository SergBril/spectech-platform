import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from app.models.finance import Act, Invoice, Payout

# Путь к папке хранения
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "documents"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Пути к системным шрифтам с поддержкой кириллицы
FONT_PATHS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    # macOS
    "/System/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_PATH = None
for path in FONT_PATHS:
    if os.path.exists(path):
        FONT_PATH = path
        break

if not FONT_PATH:
    raise RuntimeError("Не найден шрифт с поддержкой кириллицы")


class DocumentPDF(FPDF):
    """Базовый класс для финансовых документов."""

    def __init__(self):
        super().__init__()
        self.add_font("Main", "", FONT_PATH)
        self.add_font("Main", "B", FONT_PATH)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Main", "B", 16)
        self.cell(0, 10, "СпецТехника Про", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Main", "", 10)
        self.set_text_color(100)
        self.cell(
            0,
            5,
            'ООО "СпецТехника Про", ИНН 7700000000',
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
        )
        self.ln(5)
        self.set_text_color(0)
        self.set_draw_color(200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Main", "", 8)
        self.set_text_color(100)
        self.cell(0, 10, f"Страница {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.set_font("Main", "B", 12)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def info_row(self, label: str, value: str):
        self.set_font("Main", "", 10)
        self.cell(50, 6, label + ":", align="L")
        self.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT", align="L")

    def amount_row(self, label: str, amount: Decimal, bold: bool = False):
        self.set_font("Main", "B" if bold else "", 10)
        self.cell(120, 6, label, align="L")
        self.cell(0, 6, f"{amount:,.2f} руб.", new_x="LMARGIN", new_y="NEXT", align="R")


def format_date(d: date) -> str:
    """Форматирует дату для документа."""
    return d.strftime("%d.%m.%Y")


def generate_invoice_pdf(invoice: Invoice, client_name: str = "") -> str:
    """
    Генерирует PDF для счёта.
    Возвращает путь к файлу.
    """
    pdf = DocumentPDF()
    pdf.add_page()

    # Заголовок документа
    pdf.set_font("Main", "B", 14)
    pdf.cell(
        0,
        10,
        f"СЧЁТ № {invoice.document_number}",
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.ln(5)

    # Информация о документе
    pdf.section_title("Информация о документе")
    pdf.info_row("Дата счёта", format_date(invoice.invoice_date))
    if invoice.due_date:
        pdf.info_row("Срок оплаты", format_date(invoice.due_date))
    pdf.info_row("Заказчик", client_name or "—")
    pdf.ln(5)

    # Таблица позиций
    pdf.section_title("Позиции счёта")

    # Заголовок таблицы
    pdf.set_font("Main", "B", 9)
    pdf.set_fill_color(240)
    pdf.cell(10, 8, "№", border=1, fill=True, align="C")
    pdf.cell(80, 8, "Наименование", border=1, fill=True, align="C")
    pdf.cell(20, 8, "Кол-во", border=1, fill=True, align="C")
    pdf.cell(20, 8, "Ед.", border=1, fill=True, align="C")
    pdf.cell(30, 8, "Цена", border=1, fill=True, align="C")
    pdf.cell(30, 8, "Сумма", border=1, fill=True, align="C")
    pdf.ln()

    # Позиции
    pdf.set_font("Main", "", 9)
    for idx, item in enumerate(invoice.items, 1):
        pdf.cell(10, 7, str(idx), border=1, align="C")
        pdf.cell(80, 7, item.description[:60], border=1, align="L")
        pdf.cell(20, 7, f"{item.quantity:g}", border=1, align="C")
        pdf.cell(20, 7, item.unit, border=1, align="C")
        pdf.cell(30, 7, f"{item.unit_price:,.2f}", border=1, align="R")
        pdf.cell(30, 7, f"{item.amount:,.2f}", border=1, align="R")
        pdf.ln()

    pdf.ln(5)

    # Итоги
    pdf.section_title("Итого")
    pdf.amount_row("Подытог", invoice.subtotal)
    if invoice.vat_rate and invoice.vat_rate > 0:
        pdf.amount_row(f"НДС ({invoice.vat_rate}%)", invoice.vat_amount)
    pdf.amount_row("ИТОГО К ОПЛАТЕ", invoice.total, bold=True)

    if invoice.comment:
        pdf.ln(5)
        pdf.section_title("Комментарий")
        pdf.set_font("Main", "", 10)
        pdf.multi_cell(0, 5, invoice.comment)

    # Сохраняем
    filename = f"invoice_{invoice.document_number.replace('/', '-')}.pdf"
    filepath = STORAGE_DIR / filename
    pdf.output(str(filepath))

    return str(filepath)


def generate_act_pdf(act: Act, client_name: str = "", executor_name: str = "") -> str:
    """
    Генерирует PDF для акта выполненных работ.
    """
    pdf = DocumentPDF()
    pdf.add_page()

    # Заголовок
    pdf.set_font("Main", "B", 14)
    pdf.cell(
        0,
        10,
        f"АКТ ВЫПОЛНЕННЫХ РАБОТ № {act.document_number}",
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.ln(5)

    # Информация
    pdf.section_title("Информация")
    pdf.info_row("Дата акта", format_date(act.act_date))
    pdf.info_row("Заказчик", client_name or "—")
    pdf.info_row("Исполнитель", executor_name or 'ООО "СпецТехника Про"')
    pdf.info_row("Сумма работ", f"{act.total_amount:,.2f} руб.")
    pdf.ln(5)

    # Статус подписания
    pdf.section_title("Статус подписания")
    client_signed = "✅ Подписан" if act.signed_by_client_at else "⏳ Не подписан"
    executor_signed = "✅ Подписан" if act.signed_by_executor_at else "⏳ Не подписан"
    pdf.info_row("Со стороны заказчика", client_signed)
    pdf.info_row("Со стороны исполнителя", executor_signed)

    if act.comment:
        pdf.ln(5)
        pdf.section_title("Комментарий")
        pdf.set_font("Main", "", 10)
        pdf.multi_cell(0, 5, act.comment)

    # Место для подписей
    pdf.ln(15)
    pdf.set_font("Main", "", 10)
    pdf.cell(90, 10, "Заказчик: ___________________", align="L")
    pdf.cell(0, 10, "Исполнитель: ___________________", align="R")
    pdf.ln(20)
    pdf.cell(90, 10, "М.П.", align="L")
    pdf.cell(0, 10, "М.П.", align="R")

    # Сохраняем
    filename = f"act_{act.document_number.replace('/', '-')}.pdf"
    filepath = STORAGE_DIR / filename
    pdf.output(str(filepath))

    return str(filepath)


def generate_payout_pdf(
    payout: Payout, owner_name: str = "", vehicle_name: str = ""
) -> str:
    """
    Генерирует PDF для ведомости выплаты собственнику.
    """
    pdf = DocumentPDF()
    pdf.add_page()

    pdf.set_font("Main", "B", 14)
    pdf.cell(
        0,
        10,
        f"ВЕДОМОСТЬ ВЫПЛАТЫ № {payout.document_number}",
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.ln(5)

    pdf.section_title("Информация о выплате")
    pdf.info_row("Дата", format_date(payout.payout_date))
    pdf.info_row("Собственник", owner_name or "—")
    pdf.info_row("Техника", vehicle_name or "—")
    pdf.ln(5)

    pdf.section_title("Расчёт")
    pdf.amount_row("Общая сумма работ", payout.gross_amount)
    pdf.amount_row(
        f"Комиссия платформы ({payout.commission_rate}%)", -payout.platform_commission
    )
    pdf.ln(2)
    pdf.amount_row("К ВЫПЛАТЕ", payout.net_amount, bold=True)

    filename = f"payout_{payout.document_number.replace('/', '-')}.pdf"
    filepath = STORAGE_DIR / filename
    pdf.output(str(filepath))

    return str(filepath)
