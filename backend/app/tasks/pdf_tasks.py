"""Задачи генерации PDF через Celery."""

import logging
import os
from datetime import UTC, datetime

from app.core.celery_app import celery_app

logger = logging.getLogger("spectech.tasks.pdf")

# Папка для хранения PDF
PDF_DIR = "storage/pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


def _get_db():
    """Создаёт сессию БД для использования в Celery worker."""
    from app.core.db import SessionLocal

    return SessionLocal()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.pdf_tasks.generate_invoice_pdf_async",
)
def generate_invoice_pdf_async(self, invoice_id: int, company_id: int):
    # Генерируем PDF локально
    local_path = os.path.join(PDF_DIR, f"invoice_{invoice_id}.pdf")
    generate_invoice_pdf(db, invoice, local_path)

    # Загружаем в MinIO
    from app.services import storage_service

    with open(local_path, "rb") as f:
        upload_result = storage_service.upload_file(
            file_obj=f,
            filename=f"invoice_{invoice.document_number}.pdf",
            folder="finance/invoices",
            content_type="application/pdf",
        )

    # Сохраняем метаданные
    from app.models.telematics import UploadedFile

    uploaded_file = UploadedFile(
        original_filename=f"invoice_{invoice.document_number}.pdf",
        storage_path=upload_result["path"],
        content_type="application/pdf",
        size_bytes=upload_result["size"],
        file_category="invoice_pdf",
        invoice_id=invoice_id,
        company_id=company_id,
    )
    db.add(uploaded_file)
    db.commit()

    logger.info(f"PDF uploaded to storage: {upload_result['path']}")

    return {
        "status": "success",
        "invoice_id": invoice_id,
        "document_number": invoice.document_number,
        "local_path": local_path,
        "storage_path": upload_result["path"],
        "url": upload_result["url"],
        "size_bytes": upload_result["size"],
        "generated_at": datetime.now(UTC).isoformat(),
    }


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.pdf_tasks.generate_act_pdf_async"
)
def generate_act_pdf_async(self, act_id: int, company_id: int):
    # Генерируем PDF локально
    local_path = os.path.join(PDF_DIR, f"invoice_{invoice_id}.pdf")
    generate_invoice_pdf(db, invoice, local_path)

    # Загружаем в MinIO
    from app.services import storage_service

    with open(local_path, "rb") as f:
        upload_result = storage_service.upload_file(
            file_obj=f,
            filename=f"invoice_{invoice.document_number}.pdf",
            folder="finance/invoices",
            content_type="application/pdf",
        )

    # Сохраняем метаданные
    from app.models.telematics import UploadedFile

    uploaded_file = UploadedFile(
        original_filename=f"invoice_{invoice.document_number}.pdf",
        storage_path=upload_result["path"],
        content_type="application/pdf",
        size_bytes=upload_result["size"],
        file_category="invoice_pdf",
        invoice_id=invoice_id,
        company_id=company_id,
    )
    db.add(uploaded_file)
    db.commit()

    logger.info(f"PDF uploaded to storage: {upload_result['path']}")

    return {
        "status": "success",
        "invoice_id": invoice_id,
        "document_number": invoice.document_number,
        "local_path": local_path,
        "storage_path": upload_result["path"],
        "url": upload_result["url"],
        "size_bytes": upload_result["size"],
        "generated_at": datetime.now(UTC).isoformat(),
    }


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.pdf_tasks.generate_payout_pdf_async"
)
def generate_payout_pdf_async(self, payout_id: int, company_id: int):
    # Генерируем PDF локально
    local_path = os.path.join(PDF_DIR, f"invoice_{invoice_id}.pdf")
    generate_invoice_pdf(db, invoice, local_path)

    # Загружаем в MinIO
    from app.services import storage_service

    with open(local_path, "rb") as f:
        upload_result = storage_service.upload_file(
            file_obj=f,
            filename=f"invoice_{invoice.document_number}.pdf",
            folder="finance/invoices",
            content_type="application/pdf",
        )

    # Сохраняем метаданные
    from app.models.telematics import UploadedFile

    uploaded_file = UploadedFile(
        original_filename=f"invoice_{invoice.document_number}.pdf",
        storage_path=upload_result["path"],
        content_type="application/pdf",
        size_bytes=upload_result["size"],
        file_category="invoice_pdf",
        invoice_id=invoice_id,
        company_id=company_id,
    )
    db.add(uploaded_file)
    db.commit()

    logger.info(f"PDF uploaded to storage: {upload_result['path']}")

    return {
        "status": "success",
        "invoice_id": invoice_id,
        "document_number": invoice.document_number,
        "local_path": local_path,
        "storage_path": upload_result["path"],
        "url": upload_result["url"],
        "size_bytes": upload_result["size"],
        "generated_at": datetime.now(UTC).isoformat(),
    }


@celery_app.task(name="app.tasks.pdf_tasks.cleanup_old_pdfs")
def cleanup_old_pdfs(days_old: int = 30):
    """Удаляет старые PDF файлы."""
    logger.info(f"Cleaning up PDFs older than {days_old} days")
    cutoff = datetime.now(UTC).timestamp() - (days_old * 86400)
    deleted = 0

    if not os.path.exists(PDF_DIR):
        return {
            "status": "success",
            "deleted_count": 0,
            "message": "PDF directory not found",
        }

    for filename in os.listdir(PDF_DIR):
        filepath = os.path.join(PDF_DIR, filename)
        if os.path.isfile(filepath):
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff:
                try:
                    os.remove(filepath)
                    deleted += 1
                    logger.info(f"Deleted old PDF: {filename}")
                except Exception as e:
                    logger.error(f"Failed to delete {filename}: {e}")

    return {"status": "success", "deleted_count": deleted, "days_old": days_old}
