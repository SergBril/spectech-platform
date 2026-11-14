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
    """PDF счёта. Not-found и company_mismatch — без retry (не транзиентные)."""
    from app.models.finance import Invoice
    from app.services.pdf_service import generate_invoice_pdf

    db = _get_db()
    try:
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            logger.error(
                "PDF task: invoice #%s not found (task company_id=%s) — no retry",
                invoice_id,
                company_id,
            )
            return {"status": "error", "reason": "not_found", "invoice_id": invoice_id}
        if invoice.company_id != company_id:
            logger.error(
                "PDF task: invoice #%s company mismatch: task company_id=%s, "
                "object company_id=%s — cross-tenant attempt, no retry",
                invoice_id,
                company_id,
                invoice.company_id,
            )
            return {
                "status": "error",
                "reason": "company_mismatch",
                "invoice_id": invoice_id,
            }

        local_path = os.path.join(PDF_DIR, f"invoice_{invoice_id}.pdf")
        pdf_bytes = generate_invoice_pdf(invoice)
        if not pdf_bytes:
            raise ValueError(f"Empty PDF generated for invoice #{invoice_id}")
        with open(local_path, "wb") as f:
            f.write(pdf_bytes)

        from app.services import storage_service

        with open(local_path, "rb") as f:
            upload_result = storage_service.upload_file(
                file_obj=f,
                filename=f"invoice_{invoice.document_number}.pdf",
                folder="finance/invoices",
                content_type="application/pdf",
            )

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
    except Exception as exc:
        logger.error(f"PDF task failed for invoice #{invoice_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.pdf_tasks.generate_act_pdf_async"
)
def generate_act_pdf_async(self, act_id: int, company_id: int):
    """PDF акта. Not-found и company_mismatch — без retry (не транзиентные)."""
    from app.models.finance import Act
    from app.services.pdf_service import generate_act_pdf

    db = _get_db()
    try:
        act = db.get(Act, act_id)
        if not act:
            logger.error(
                "PDF task: act #%s not found (task company_id=%s) — no retry",
                act_id,
                company_id,
            )
            return {"status": "error", "reason": "not_found", "act_id": act_id}
        if act.company_id != company_id:
            logger.error(
                "PDF task: act #%s company mismatch: task company_id=%s, "
                "object company_id=%s — cross-tenant attempt, no retry",
                act_id,
                company_id,
                act.company_id,
            )
            return {"status": "error", "reason": "company_mismatch", "act_id": act_id}

        local_path = os.path.join(PDF_DIR, f"act_{act_id}.pdf")
        pdf_bytes = generate_act_pdf(act)
        if not pdf_bytes:
            raise ValueError(f"Empty PDF generated for act #{act_id}")
        with open(local_path, "wb") as f:
            f.write(pdf_bytes)

        from app.services import storage_service

        with open(local_path, "rb") as f:
            upload_result = storage_service.upload_file(
                file_obj=f,
                filename=f"act_{act.document_number}.pdf",
                folder="finance/acts",
                content_type="application/pdf",
            )

        from app.models.telematics import UploadedFile

        uploaded_file = UploadedFile(
            original_filename=f"act_{act.document_number}.pdf",
            storage_path=upload_result["path"],
            content_type="application/pdf",
            size_bytes=upload_result["size"],
            file_category="act_pdf",
            act_id=act_id,
            company_id=company_id,
        )
        db.add(uploaded_file)
        db.commit()

        logger.info(f"PDF uploaded to storage: {upload_result['path']}")

        return {
            "status": "success",
            "act_id": act_id,
            "document_number": act.document_number,
            "local_path": local_path,
            "storage_path": upload_result["path"],
            "url": upload_result["url"],
            "size_bytes": upload_result["size"],
            "generated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        logger.error(f"PDF task failed for act #{act_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True, max_retries=3, name="app.tasks.pdf_tasks.generate_payout_pdf_async"
)
def generate_payout_pdf_async(self, payout_id: int, company_id: int):
    """PDF ведомости выплаты. Not-found и company_mismatch — без retry.

    В UploadedFile нет колонки payout_id: связь восстановима через
    folder finance/payouts/{payout_id} в storage_path и имя файла.
    """
    from app.models.catalog import Vehicle
    from app.models.contractor import Contractor
    from app.models.finance import Payout
    from app.services.pdf_service import generate_payout_pdf

    db = _get_db()
    try:
        payout = db.get(Payout, payout_id)
        if not payout:
            logger.error(
                "PDF task: payout #%s not found (task company_id=%s) — no retry",
                payout_id,
                company_id,
            )
            return {"status": "error", "reason": "not_found", "payout_id": payout_id}
        if payout.company_id != company_id:
            logger.error(
                "PDF task: payout #%s company mismatch: task company_id=%s, "
                "object company_id=%s — cross-tenant attempt, no retry",
                payout_id,
                company_id,
                payout.company_id,
            )
            return {
                "status": "error",
                "reason": "company_mismatch",
                "payout_id": payout_id,
            }

        owner = db.get(Contractor, payout.owner_id)
        vehicle = db.get(Vehicle, payout.vehicle_id) if payout.vehicle_id else None

        local_path = os.path.join(PDF_DIR, f"payout_{payout_id}.pdf")
        pdf_bytes = generate_payout_pdf(
            payout,
            owner_name=owner.name if owner else "",
            vehicle_name=vehicle.name if vehicle else "",
        )
        if not pdf_bytes:
            raise ValueError(f"Empty PDF generated for payout #{payout_id}")
        with open(local_path, "wb") as f:
            f.write(pdf_bytes)

        from app.services import storage_service

        with open(local_path, "rb") as f:
            upload_result = storage_service.upload_file(
                file_obj=f,
                filename=f"payout_{payout.document_number}.pdf",
                folder=f"finance/payouts/{payout_id}",
                content_type="application/pdf",
            )

        from app.models.telematics import UploadedFile

        uploaded_file = UploadedFile(
            original_filename=f"payout_{payout.document_number}.pdf",
            storage_path=upload_result["path"],
            content_type="application/pdf",
            size_bytes=upload_result["size"],
            file_category="payout_pdf",
            invoice_id=None,
            company_id=company_id,
            payout_id=payout_id,
        )
        db.add(uploaded_file)
        db.commit()

        logger.info(f"PDF uploaded to storage: {upload_result['path']}")

        return {
            "status": "success",
            "payout_id": payout_id,
            "document_number": payout.document_number,
            "local_path": local_path,
            "storage_path": upload_result["path"],
            "url": upload_result["url"],
            "size_bytes": upload_result["size"],
            "generated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        logger.error(f"PDF task failed for payout #{payout_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


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
