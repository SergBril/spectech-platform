# Auth
from app.models.auth import User, UserSession

# Catalog
from app.models.catalog import Category, Vehicle

# Company
from app.models.company import Company

# Contractor
from app.models.contractor import Contractor, Employee, EmployeeCertificate

# Dispatch
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog

# Finance
from app.models.finance import (
    Act,
    DocumentStatus,
    Invoice,
    InvoiceItem,
    Payment,
    Payout,
)

# RBAC
from app.models.rbac import Permission, Role, RolePermission, UserRole

# Shift
from app.models.shift import ShiftReport, ShiftTask

# Telematics (models + enums)
from app.models.telematics import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    EngineHoursLog,
    FuelTransaction,
    Geofence,
    GeofenceEvent,
    GeofenceType,
    GpsPoint,
    Notification,
    UploadedFile,
)

__all__ = [
    # Auth
    "User",
    "UserSession",
    # Company
    "Company",
    # Catalog
    "Category",
    "Vehicle",
    # Contractor
    "Contractor",
    "Employee",
    "EmployeeCertificate",
    # Dispatch
    "Request",
    "RequestStatusLog",
    "RequestAssignment",
    # Shift
    "ShiftTask",
    "ShiftReport",
    # RBAC
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    # Finance
    "Invoice",
    "InvoiceItem",
    "Act",
    "Payout",
    "Payment",
    "DocumentStatus",
    # Telematics
    "GpsPoint",
    "Geofence",
    "GeofenceEvent",
    "FuelTransaction",
    "EngineHoursLog",
    "Alert",
    "Notification",
    "AlertRule",
    "UploadedFile",
    "GeofenceType",
    "AlertSeverity",
    "AlertStatus",
]
