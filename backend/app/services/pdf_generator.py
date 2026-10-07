"""Сервис генерации PDF-документов через WeasyPrint."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
# Lazy import — WeasyPrint загружается только при генерации PDF,
# чтобы не блокировать запуск приложения на Windows без GTK
_weasyprint = None

def _get_weasyprint():
    """Ленивая загрузка WeasyPrint с понятным сообщением об ошибке."""
    global _weasyprint
    if _weasyprint is None:
        try:
            from weasyprint import HTML
            _weasyprint = HTML
        except (OSError, ImportError) as e:
            raise RuntimeError(
                "WeasyPrint не может загрузиться. На Windows нужны GTK runtime.\n"
                "Установите GTK3: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases\n"
                f"Оригинальная ошибка: {e}"
            ) from e
    return _weasyprint

from app.services.pdf_form_filler import fill_torg12_pdf, fill_upd_pdf
from app.services.translations import translate_unit

logger = logging.getLogger("spectech.pdf")

TEMPLATES_DIR = Path(__file__).parent / "email_templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# 🆕 РЕГИСТРАЦИЯ ФИЛЬТРА ДЛЯ JINJA2
env.filters["translate_unit"] = translate_unit


def generate_act_pdf(act, request, contractor=None) -> bytes:
    """
    Генерирует PDF-акт из HTML-шаблона.
    """
    try:
        template = env.get_template("act_pdf.html")
        html_content = template.render(
            act=act,
            request=request,
            contractor=contractor,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def _money_to_words_ru(amount: float) -> str:
    """Сумма прописью на русском (для ТОРГ-12)."""
    ones = [
        "",
        "один",
        "два",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
        "десять",
        "одиннадцать",
        "двенадцать",
        "тринадцать",
        "четырнадцать",
        "пятнадцать",
        "шестнадцать",
        "семнадцать",
        "восемнадцать",
        "девятнадцать",
    ]
    fem = [
        "",
        "одна",
        "две",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ]
    tens = [
        "",
        "",
        "двадцать",
        "тридцать",
        "сорок",
        "пятьдесят",
        "шестьдесят",
        "семьдесят",
        "восемьдесят",
        "девяносто",
    ]
    hund = [
        "",
        "сто",
        "двести",
        "триста",
        "четыреста",
        "пятьсот",
        "шестьсот",
        "семьсот",
        "восемьсот",
        "девятьсот",
    ]

    def three(n: int, feminine=False) -> str:
        out = []
        if n // 100:
            out.append(hund[n // 100])
        t = n % 100
        if t < 20:
            if t:
                out.append(fem[t] if (feminine and t < 10) else ones[t])
        else:
            out.append(tens[t // 10])
            if t % 10:
                out.append(fem[t % 10] if (feminine and t % 10 < 10) else ones[t % 10])
        return " ".join(out)

    def plural(n: int, forms: list) -> str:
        n = abs(n) % 100
        d = n % 10
        if 10 < n < 20:
            return forms[2]
        if 1 < d < 5:
            return forms[1]
        if d == 1:
            return forms[0]
        return forms[2]

    rub = int(amount)
    kop = int(round((amount - rub) * 100))
    parts = []
    mil, thou, rest = rub // 1_000_000, (rub % 1_000_000) // 1000, rub % 1000
    if mil:
        parts += [three(mil), plural(mil, ["миллион", "миллиона", "миллионов"])]
    if thou:
        parts += [
            three(thou, feminine=True),
            plural(thou, ["тысяча", "тысячи", "тысяч"]),
        ]
    if rest:
        parts.append(three(rest))
    if not parts:
        parts.append("ноль")
    parts.append(plural(rub, ["рубль", "рубля", "рублей"]))
    parts.append(f"{kop:02d} копеек")
    return " ".join(parts)


def generate_upd_pdf(act, company, client, request=None) -> bytes:
    """Генерирует PDF УПД через заполнение официального бланка."""
    return fill_upd_pdf(act, company, client, request)


def generate_torg12_pdf(
    act, company, client, request=None, driver_name=None, vehicle_plate=None
) -> bytes:
    """Генерирует PDF ТОРГ-12 через заполнение официального бланка."""
    return fill_torg12_pdf(act, company, client, request, driver_name, vehicle_plate)


def generate_invoice_pdf(invoice, contractor=None) -> bytes:
    """
    Генерирует PDF-счёт из HTML-шаблона.
    """
    try:
        template = env.get_template("invoice_pdf.html")
        html_content = template.render(
            invoice=invoice,
            contractor=contractor,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ Invoice PDF generated: {invoice.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Invoice PDF generation failed for {invoice.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def generate_invoice_facture_pdf(act, request, contractor=None) -> bytes:
    """
    Генерирует PDF счёт-фактуры на основании акта.
    Вызывается только для ОСНО с НДС.
    """
    try:
        from datetime import date
        from decimal import Decimal

        template = env.get_template("invoice_facture_pdf.html")

        # Расчёт суммы без НДС
        total_amount = Decimal(str(act.total_amount or 0))
        vat_amount = Decimal(str(act.vat_amount or 0))
        vat_rate = Decimal(str(act.vat_rate or 22))
        total_without_vat = total_amount - vat_amount

        # Номер счёт-фактуры (на основе акта)
        facture_number = act.document_number.replace("ACT", "SF")
        facture_date = act.act_date or date.today()

        html_content = template.render(
            act=act,
            request=request,
            contractor=contractor,
            facture_number=facture_number,
            facture_date=facture_date,
            vat_rate=vat_rate,
            total_without_vat=total_without_vat,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ Invoice facture PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Invoice facture PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise
