"""Сервис генерации PDF-документов через WeasyPrint."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger("spectech.pdf")

TEMPLATES_DIR = Path(__file__).parent / "email_templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def generate_act_pdf(act, request, contractor=None) -> bytes:
    """
    Генерирует PDF-акт из HTML-шаблона.

    Args:
        act: ORM-объект акта
        request: ORM-объект заявки
        contractor: ORM-объект контрагента (опционально)

    Returns:
        bytes: содержимое PDF-файла
    """
    try:
        template = env.get_template("act_pdf.html")
        html_content = template.render(
            act=act,
            request=request,
            contractor=contractor,
        )

        # Генерируем PDF в память
        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ PDF generation failed for act {act.id}: {e}")
        raise


def generate_invoice_pdf(invoice, contractor=None) -> bytes:
    """
    Генерирует PDF-счет из HTML-шаблона.

    Args:
        invoice: ORM-объект счета (с items)
        contractor: ORM-объект контрагента (опционально)

    Returns:
        bytes: содержимое PDF-файла
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
        raise
