"""Shifts router package - auto-refactored from monolithic shifts.py"""

from fastapi import APIRouter

router = APIRouter(prefix="/shifts", tags=["Shifts"])

from app.api.routes.shifts.tasks import router as tasks_router
from app.api.routes.shifts.reports import router as reports_router
from app.api.routes.shifts.templates import router as templates_router
from app.api.routes.shifts.notifications import router as notifications_router
from app.api.routes.shifts.stats import router as stats_router
from app.api.routes.shifts.alerts import router as alerts_router
from app.api.routes.shifts.mobile import router as mobile_router
from app.api.routes.shifts.chat import router as chat_router
from app.api.routes.shifts.diadoc import router as diadoc_router
from app.api.routes.shifts.documents import router as documents_router
from app.api.routes.shifts.bank import router as bank_router
from app.api.routes.shifts.finance import router as finance_router
from app.api.routes.shifts.admin import router as admin_router
from app.api.routes.shifts.max_messenger import router as max_messenger_router
from app.api.routes.shifts.geofence import router as geofence_router
from app.api.routes.shifts.checklist_configs import router as checklist_configs_router

router.include_router(tasks_router)
router.include_router(reports_router)
router.include_router(templates_router)
router.include_router(notifications_router)
router.include_router(stats_router)
router.include_router(alerts_router)
router.include_router(mobile_router)
router.include_router(chat_router)
router.include_router(diadoc_router)
router.include_router(documents_router)
router.include_router(bank_router)
router.include_router(finance_router)
router.include_router(admin_router)
router.include_router(max_messenger_router)
router.include_router(geofence_router)
router.include_router(checklist_configs_router)
