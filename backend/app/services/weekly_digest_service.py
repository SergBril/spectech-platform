"""Сервис еженедельного дайджеста для бухгалтеров."""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.auth import User
from app.models.contractor import Employee, Contractor
from app.models.finance import Invoice, DocumentStatus, Payout
from app.models.rental import Rental, RentalStatus
from app.services.email_service import email_service

logger = logging.getLogger("spectech.weekly_digest")


class WeeklyDigestService:
    """Сервис генерации и отправки еженедельных дайджестов."""

    # === СБОР ДАННЫХ (устойчиво к отсутствию методов) ===

    @staticmethod
    def _get_dashboard_metrics(db: Session, company_id: int, from_date: date, to_date: date) -> dict:
        """Собирает ключевые метрики напрямую из БД."""
        try:
            # Выручка
            revenue_query = db.query(
                func.coalesce(func.sum(Invoice.total), 0),
                func.coalesce(func.sum(Invoice.paid_amount), 0),
            ).filter(
                Invoice.company_id == company_id,
                Invoice.invoice_date.between(from_date, to_date),
            )
            total_revenue, total_paid = revenue_query.one()

            # Комиссия
            commission = db.query(
                func.coalesce(func.sum(Payout.platform_commission), 0)
            ).filter(
                Payout.company_id == company_id,
                Payout.payout_date.between(from_date, to_date),
            ).scalar()

            # Активные аренды
            active_rentals = db.query(func.count(Rental.id)).filter(
                Rental.company_id == company_id,
                Rental.status.in_([RentalStatus.ACTIVE, RentalStatus.OVERDUE]),
            ).scalar()

            # Просроченные счета
            today = date.today()
            overdue_query = db.query(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.total - Invoice.paid_amount), 0),
            ).filter(
                Invoice.company_id == company_id,
                Invoice.status.in_([DocumentStatus.sent, DocumentStatus.overdue]),
                Invoice.due_date < today,
            )
            overdue_count, overdue_amount = overdue_query.one()

            return {
                "total_revenue": float(total_revenue or 0),
                "total_paid": float(total_paid or 0),
                "total_unpaid": float((total_revenue or 0) - (total_paid or 0)),
                "total_commission": float(commission or 0),
                "active_rentals": active_rentals,
                "overdue_invoices_count": overdue_count,
                "overdue_invoices_amount": float(overdue_amount or 0),
                "unmatched_transactions": 0,
            }
        except Exception as e:
            logger.error(f"Failed to get dashboard metrics: {e}")
            return {
                "total_revenue": 0, "total_paid": 0, "total_unpaid": 0,
                "total_commission": 0, "active_rentals": 0,
                "overdue_invoices_count": 0, "overdue_invoices_amount": 0,
                "unmatched_transactions": 0,
            }

    @staticmethod
    def _get_top_clients(db: Session, company_id: int, from_date: date, to_date: date, limit: int = 5) -> list:
        """Топ клиентов по выручке."""
        try:
            results = (
                db.query(
                    Contractor.id.label("client_id"),
                    Contractor.name.label("client_name"),
                    func.coalesce(func.sum(Invoice.total), 0).label("total_revenue"),
                    func.count(Invoice.id).label("invoices_count"),
                )
                .join(Contractor, Invoice.client_id == Contractor.id)
                .filter(
                    Invoice.company_id == company_id,
                    Invoice.invoice_date.between(from_date, to_date),
                )
                .group_by(Contractor.id, Contractor.name)
                .order_by(func.sum(Invoice.total).desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "client_id": row.client_id,
                    "client_name": row.client_name,
                    "total_revenue": float(row.total_revenue or 0),
                    "invoices_count": row.invoices_count,
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to get top clients: {e}")
            return []

    @staticmethod
    def _get_top_vehicles(db: Session, company_id: int, from_date: date, to_date: date, limit: int = 5) -> list:
        """Топ техники по выручке."""
        try:
            from app.models.catalog import Vehicle
            from app.models.rental import RentalItem

            results = (
                db.query(
                    Vehicle.id.label("vehicle_id"),
                    Vehicle.name.label("vehicle_name"),
                    func.coalesce(func.sum(RentalItem.unit_price * RentalItem.quantity), 0).label("total_revenue"),
                    func.count(func.distinct(Rental.id)).label("rentals_count"),
                )
                .join(RentalItem, Vehicle.id == RentalItem.vehicle_id)
                .join(Rental, RentalItem.rental_id == Rental.id)
                .filter(
                    Rental.company_id == company_id,
                    Rental.start_date.between(
                        datetime.combine(from_date, datetime.min.time()),
                        datetime.combine(to_date, datetime.max.time()),
                    ),
                )
                .group_by(Vehicle.id, Vehicle.name)
                .order_by(func.sum(RentalItem.unit_price * RentalItem.quantity).desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "vehicle_id": row.vehicle_id,
                    "vehicle_name": row.vehicle_name,
                    "total_revenue": float(row.total_revenue or 0),
                    "rentals_count": row.rentals_count,
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to get top vehicles: {e}")
            return []

    @staticmethod
    def _get_overdue_invoices(db: Session, company_id: int, limit: int = 10) -> list:
        """Просроченные счета."""
        try:
            today = date.today()
            results = (
                db.query(
                    Invoice.id.label("invoice_id"),
                    Invoice.document_number,
                    Contractor.name.label("client_name"),
                    Invoice.total,
                    Invoice.paid_amount,
                    Invoice.due_date,
                )
                .join(Contractor, Invoice.client_id == Contractor.id)
                .filter(
                    Invoice.company_id == company_id,
                    Invoice.status.in_([DocumentStatus.sent, DocumentStatus.overdue]),
                    Invoice.due_date < today,
                )
                .order_by(Invoice.due_date.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "invoice_id": row.invoice_id,
                    "document_number": row.document_number,
                    "client_name": row.client_name,
                    "total": float(row.total),
                    "paid_amount": float(row.paid_amount),
                    "remaining": float(row.total - row.paid_amount),
                    "due_date": row.due_date.isoformat(),
                    "days_overdue": (today - row.due_date).days,
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to get overdue invoices: {e}")
            return []

    # === ОТПРАВКА ДАЙДЖЕСТА ===

    @staticmethod
    def send_weekly_digest(db: Session, company_id: int) -> dict:
        """
        Генерирует и отправляет еженедельный дайджест бухгалтерам компании.
        """
        company = db.get(Company, company_id)
        if not company:
            logger.warning(f"Company {company_id} not found, skipping digest")
            return {"success": False, "recipients_count": 0}

        to_date = date.today()
        from_date = to_date - timedelta(days=7)

        logger.info(
            f"Generating weekly digest for company {company.name} "
            f"({from_date} - {to_date})"
        )

        try:
            # Собираем данные (устойчиво к ошибкам)
            metrics = WeeklyDigestService._get_dashboard_metrics(db, company_id, from_date, to_date)
            top_clients = WeeklyDigestService._get_top_clients(db, company_id, from_date, to_date, limit=5)
            top_vehicles = WeeklyDigestService._get_top_vehicles(db, company_id, from_date, to_date, limit=5)
            overdue_invoices = WeeklyDigestService._get_overdue_invoices(db, company_id, limit=10)
        except Exception as e:
            logger.error(f"Failed to gather digest data: {e}", exc_info=True)
            return {"success": False, "recipients_count": 0, "error": str(e)}

        # Ищем бухгалтеров
        recipients = WeeklyDigestService._find_accountants(db, company_id)

        if not recipients:
            logger.info(f"No accountants found for company {company.name}")
            return {
                "success": True,
                "recipients_count": 0,
                "period": {"from": from_date, "to": to_date},
            }

        # Контекст шаблона
        context = {
            "company_name": company.name,
            "period_start": from_date.strftime("%d.%m.%Y"),
            "period_end": to_date.strftime("%d.%m.%Y"),
            "metrics": metrics,
            "top_clients": top_clients,
            "top_vehicles": top_vehicles,
            "overdue_invoices": overdue_invoices,
        }

        # Отправляем каждому
        sent_count = 0
        for user in recipients:
            try:
                subject = f"📊 Еженедельный отчёт {company.name} ({from_date.strftime('%d.%m')} - {to_date.strftime('%d.%m')})"
                
                success = email_service.send_email(
                    to_email=user.email,
                    subject=subject,
                    template_name="email/weekly_digest.html",
                    context=context,
                )
                
                if success:
                    sent_count += 1
                    logger.info(f"Weekly digest sent to {user.email}")
                else:
                    logger.warning(f"Failed to send digest to {user.email}")
            except Exception as e:
                logger.error(f"Error sending digest to {user.email}: {e}")

        logger.info(
            f"Weekly digest completed for {company.name}: "
            f"{sent_count}/{len(recipients)} recipients"
        )

        return {
            "success": True,
            "recipients_count": sent_count,
            "period": {"from": from_date, "to": to_date},
        }

    @staticmethod
    def send_digests_for_all_companies(db: Session) -> dict:
        """Отправляет дайджест всем активным компаниям."""
        companies = db.query(Company).filter(Company.is_active == True).all()
        
        logger.info(f"Starting weekly digest for {len(companies)} companies")
        
        total_sent = 0
        total_recipients = 0
        errors = []
        
        for company in companies:
            try:
                result = WeeklyDigestService.send_weekly_digest(db, company.id)
                if result["success"]:
                    total_sent += 1
                    total_recipients += result["recipients_count"]
                else:
                    errors.append({
                        "company_id": company.id,
                        "company_name": company.name,
                        "error": result.get("error", "Unknown"),
                    })
            except Exception as e:
                logger.error(f"Failed to send digest to company {company.id}: {e}")
                errors.append({
                    "company_id": company.id,
                    "company_name": company.name,
                    "error": str(e),
                })
        
        logger.info(
            f"Weekly digest completed: {total_sent}/{len(companies)} companies, "
            f"{total_recipients} recipients, {len(errors)} errors"
        )
        
        return {
            "total_companies": len(companies),
            "successful": total_sent,
            "total_recipients": total_recipients,
            "errors": errors,
        }

    @staticmethod
    def _find_accountants(db: Session, company_id: int) -> list[User]:
        """Находит пользователей-бухгалтеров компании."""
        employees = (
            db.query(Employee)
            .filter(
                Employee.role_in_system.in_(["accountant", "admin", "manager", "owner"]),
                Employee.user_id.isnot(None),
            )
            .all()
        )
        
        if not employees:
            return []
        
        user_ids = [emp.user_id for emp in employees if emp.user_id]
        if not user_ids:
            return []
        
        users = (
            db.query(User)
            .filter(
                User.id.in_(user_ids),
                User.email.isnot(None),
            )
            .all()
        )
        
        # Фильтруем по company_id, если User имеет это поле
        if hasattr(User, "company_id"):
            users = [u for u in users if getattr(u, "company_id", None) == company_id or getattr(u, "is_superuser", False)]
        
        return users


weekly_digest_service = WeeklyDigestService()