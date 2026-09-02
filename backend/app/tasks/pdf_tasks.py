"""Задачи генерации PDF через Celery."""
import logging
import os
from datetime import datetime, timezone

from app.core.celery_app import celery_app

logger = logging.getLogger("spectech.tasks.pdf")

# Папка для хранения PDF
PDF_DIR = "storage/pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


def _get_db():
    """Создаёт сессию БД для использования в Celery worker."""
    from app.core.db import SessionLocal
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60,
                 name="app.tasks.pdf_tasks.generate_invoice_pdf_async")
def generate_invoice_pdf_async(self, invoice_id: int, company_id: int):
    """Реальная асинхронная генерация PDF счёта."""
    db = None
    try:
        logger.info(f"Starting PDF generation for invoice {invoice_id}")
        
        db = _get_db()
        
        from app.models.finance import Invoice
        from app.services.pdf_service import generate_invoice_pdf
        
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error(f"Invoice {invoice_id} not found")
            return {"status": "error", "message": f"Invoice {invoice_id} not found"}
        
        # Генерируем PDF через существующий сервис
        pdf_path = os.path.join(PDF_DIR, f"invoice_{invoice_id}.pdf")
        generate_invoice_pdf(db, invoice, pdf_path)
        
        logger.info(f"PDF generated successfully: {pdf_path}")
        
        return {
            "status": "success",
            "invoice_id": invoice_id,
            "document_number": invoice.document_number,
            "path": pdf_path,
            "size_bytes": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error(f"PDF generation failed for invoice {invoice_id}: {exc}")
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3,
                 name="app.tasks.pdf_tasks.generate_act_pdf_async")
def generate_act_pdf_async(self, act_id: int, company_id: int):
    """Реальная асинхронная генерация PDF акта."""
    db = None
    try:
        logger.info(f"Starting PDF generation for act {act_id}")
        
        db = _get_db()
        
        from app.models.finance import Act
        from app.services.pdf_service import generate_act_pdf
        
        act = db.query(Act).filter(Act.id == act_id).first()
        if not act:
            logger.error(f"Act {act_id} not found")
            return {"status": "error", "message": f"Act {act_id} not found"}
        
        pdf_path = os.path.join(PDF_DIR, f"act_{act_id}.pdf")
        generate_act_pdf(db, act, pdf_path)
        
        logger.info(f"PDF generated successfully: {pdf_path}")
        
        return {
            "status": "success",
            "act_id": act_id,
            "document_number": act.document_number,
            "path": pdf_path,
            "size_bytes": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
        }
    except Exception as exc:
        logger.error(f"Act PDF generation failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3,
                 name="app.tasks.pdf_tasks.generate_payout_pdf_async")
def generate_payout_pdf_async(self, payout_id: int, company_id: int):
    """Реальная асинхронная генерация PDF выплаты."""
    db = None
    try:
        logger.info(f"Starting PDF generation for payout {payout_id}")
        
        db = _get_db()
        
        from app.models.finance import Payout
        from app.services.pdf_service import generate_payout_pdf
        
        payout = db.query(Payout).filter(Payout.id == payout_id).first()
        if not payout:
            return {"status": "error", "message": f"Payout {payout_id} not found"}
        
        pdf_path = os.path.join(PDF_DIR, f"payout_{payout_id}.pdf")
        generate_payout_pdf(db, payout, pdf_path)
        
        return {
            "status": "success",
            "payout_id": payout_id,
            "document_number": payout.document_number,
            "path": pdf_path,
        }
    except Exception as exc:
        logger.error(f"Payout PDF generation failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        if db:
            db.close()


@celery_app.task(name="app.tasks.pdf_tasks.cleanup_old_pdfs")
def cleanup_old_pdfs(days_old: int = 30):
    """Удаляет старые PDF файлы."""
    logger.info(f"Cleaning up PDFs older than {days_old} days")
    cutoff = datetime.now(timezone.utc).timestamp() - (days_old * 86400)
    deleted = 0
    
    if not os.path.exists(PDF_DIR):
        return {"status": "success", "deleted_count": 0, "message": "PDF directory not found"}
    
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