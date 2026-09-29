"""
Генератор PDF отчёта о сверке данных через WeasyPrint.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger("spectech.reconciliation_pdf")

TEMPLATES_DIR = Path(__file__).parent.parent / "email_templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def _translate_status(status: str) -> tuple[str, str]:
    """Возвращает (текст_статуса, CSS_класс)."""
    translations = {
        "pending": ("Ожидает", "info"),
        "auto_approved": ("Автоматически подтверждено", "ok"),
        "discrepancy_detected": ("Обнаружено расхождение", "warn"),
        "manual_review": ("Требует ручной проверки", "warn"),
        "resolved": ("Разрешено", "ok"),
    }
    return translations.get(status, (status, "info"))


def _get_decision_text(reconciliation) -> str:
    """Формирует HTML текст решения."""
    status = reconciliation.reconciliation_status

    if status == "auto_approved":
        return (
            "<b style='color:#27ae60'>✓ Сверка автоматически подтверждена.</b><br>"
            "Расхождение не превышает порог 5%. "
            "Финальные значения взяты из телеметрии."
        )
    elif status == "resolved":
        source = reconciliation.decision_source or "не указан"
        return (
            "<b style='color:#27ae60'>✓ Сверка разрешена вручную.</b><br>"
            f"Источник решения: <b>{source}</b>. "
            "Финальные значения утверждены диспетчером."
        )
    elif status == "manual_review":
        return (
            "<b style='color:#e67e22'>⚠ Сверка требует ручной проверки.</b><br>"
            "Обнаружено значительное расхождение (&gt;15%). "
            "Необходимо решение диспетчера."
        )
    elif status == "discrepancy_detected":
        return (
            "<b style='color:#e67e22'>⚠ Обнаружено расхождение.</b><br>"
            "Между данными оператора и телеметрии есть различия. "
            "Рекомендуется проверка."
        )
    else:
        return f"Статус: {status}"


def generate_reconciliation_pdf(
    reconciliation, shift_task, request, vehicle, operator, client
) -> bytes:
    """
    Генерирует PDF отчёт о сверке данных через WeasyPrint.

    Returns:
        bytes: PDF файл
    """
    try:
        template = env.get_template("reconciliation_pdf.html")

        status_text, status_class = _translate_status(
            reconciliation.reconciliation_status
        )
        decision_text = _get_decision_text(reconciliation)

        html_content = template.render(
            reconciliation=reconciliation,
            shift_task=shift_task,
            request=request,
            vehicle=vehicle,
            operator=operator,
            client=client,
            now=datetime.now(UTC),
            status_text=status_text,
            status_class=status_class,
            decision_text=decision_text,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(f"✅ Reconciliation PDF generated: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Reconciliation PDF generation failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise
