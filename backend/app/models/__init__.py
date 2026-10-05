# Auth
from app.models.auth import User, UserSession
from app.models.dispute import Dispute, DisputeStatus, DisputeType, InitiatorRole, AssignedRole

# Catalog
from app.models.catalog import (
    Category,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
    EquipmentAttributeValue,
    Vehicle,
)
from app.models.chat import ChatMessage, ChatParticipant, RequestChat  # noqa: F401

# Company
from app.models.company import Company

# Contractor
from app.models.contractor import Contractor, Employee, EmployeeCertificate

# Dispatch
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog
from app.models.email import EmailLog, EmailStatus, EmailTemplate, EmailTemplateType

# Finance
from app.models.finance import (
    Act,
    DocumentStatus,
    Invoice,
    InvoiceItem,
    Payment,
    Payout,
)
from app.models.marketplace import MarketplaceOffer  # noqa: F401

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
    "EquipmentAttributeDefinition",
    "EquipmentAttributeOption",
    "EquipmentAttributeValue",
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
    # Maintenance
    "MaintenanceOrder",
    "MaintenanceOrderType",
    "MaintenanceOrderStatus",
    "MaintenancePriority",
    "MaintenancePart",
    "MaintenanceWork",
]

# Maintenance (ТО и Ремонты)
from app.models.maintenance import (
    MaintenanceOrder,
    MaintenanceOrderStatus,
    MaintenanceOrderType,
    MaintenancePart,
    MaintenancePriority,
    MaintenanceWork,
)  # noqa: F401

from app.models.downtime import (
    DowntimeEvent,
    DowntimeCause,
    DowntimeStatus,
    FaultParty,
)
