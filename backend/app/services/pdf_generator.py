"""Сервис генерации PDF-документов через WeasyPrint."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

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
