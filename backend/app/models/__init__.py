# Auth
from app.models.auth import User, UserSession

# Company
from app.models.company import Company

# Catalog
from app.models.catalog import Category, Vehicle

# Contractor
from app.models.contractor import Contractor, Employee, EmployeeCertificate

# Dispatch
from app.models.dispatch import Request, RequestStatusLog, RequestAssignment

# Shift
from app.models.shift import ShiftTask, ShiftReport

# RBAC
from app.models.rbac import Role, Permission, RolePermission, UserRole

# Finance
from app.models.finance import (
    Invoice, InvoiceItem, Act, Payout, Payment,
    DocumentStatus,
)

# Telematics (models + enums)
from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    EngineHoursLog, Alert, Notification, AlertRule, UploadedFile,
    GeofenceType, AlertSeverity, AlertStatus,
)

__all__ = [
    # Auth
    "User", "UserSession",
    # Company
    "Company",
    # Catalog
    "Category", "Vehicle",
    # Contractor
    "Contractor", "Employee", "EmployeeCertificate",
    # Dispatch
    "Request", "RequestStatusLog", "RequestAssignment",
    # Shift
    "ShiftTask", "ShiftReport",
    # RBAC
    "Role", "Permission", "RolePermission", "UserRole",
    # Finance
    "Invoice", "InvoiceItem", "Act", "Payout", "Payment",
    "DocumentStatus",
    # Telematics
    "GpsPoint", "Geofence", "GeofenceEvent", "FuelTransaction",
    "EngineHoursLog", "Alert", "Notification", "AlertRule", "UploadedFile",
    "GeofenceType", "AlertSeverity", "AlertStatus",
]