"""
Единая точка импорта всех моделей SQLAlchemy.
Гарантирует регистрацию всех классов в registry до первого запроса к БД.
Предотвращает ошибки: NameError, InvalidRequestError при настройке relationship.
"""

# === Auth & RBAC ===
from app.models.auth import (  # noqa: F401
    User,
    AuditLog,
    NotificationTemplate,
    UserNotificationPreference,
)

# === Company ===
from app.models.company import Company  # noqa: F401

# === Contractors & Drivers ===
from app.models.contractor import (  # noqa: F401
    Contractor,
    DriverProfile,
    Employee,
)

# === Catalog (Vehicles, Attributes) ===
from app.models.catalog import (  # noqa: F401
    Category,
    Vehicle,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
    EquipmentAttributeValue,
)

# === Maintenance ===
from app.models.maintenance import (  # noqa: F401
    MaintenanceOrder,
    MaintenancePart,
    MaintenanceWork,
)

# === Shifts ===
from app.models.shift import (  # noqa: F401
    ShiftTask,
    ShiftReport,
    ShiftTemplate,
    ShiftFuelEntry,
)

# === Finance ===
from app.models.finance import (  # noqa: F401
    Act,
    Invoice,
    Payout,
)

# === Bank Statements ===
from app.models.bank_statement import BankTransaction  # noqa: F401

# === Dispatch / Requests ===
from app.models.dispatch import (  # noqa: F401
    Request,
    RequestAssignment,
)

# === Chat ===
from app.models.chat import (  # noqa: F401
    ChatMessage,
    RequestChat,
    ChatParticipant,
)

# === Rental ===
from app.models.rental import Rental  # noqa: F401

# === Marketplace ===
from app.models.marketplace import MarketplaceOffer  # noqa: F401

# === UserCompany ===
from app.models.user_company import UserCompany  # noqa: F401

# === Telematics (Geofences, GPS) ===
from app.models.telematics import Geofence, GpsPoint  # noqa: F401
