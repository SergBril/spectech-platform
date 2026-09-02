"""Единый скрипт для исправления Pydantic enum + тестов + API телематики."""
from pathlib import Path

BASE = Path(__file__).parent.parent
ROUTES = BASE / "app" / "api" / "routes" / "telematics.py"
TESTS = BASE / "tests"

# === 1. Полная версия telematics.py (роуты) ===
TELEMATICS_ROUTES = '''from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.telematics import (
    GpsPoint, Geofence, GeofenceEvent, FuelTransaction,
    Alert, Notification, AlertRule, AlertStatus,
)
from app.schemas.telematics import (
    GpsPointCreate, GpsPointBatch, GpsPointRead,
    GeofenceCreate, GeofenceRead,
    FuelTransactionCreate, FuelTransactionRead,
    AlertAck, NotificationRead, TelematicsDashboard,
)
from app.services.telematics_service import (
    save_gps_points, get_telematics_dashboard,
)
from app.services.alert_engine import seed_default_rules

router = APIRouter()


# =========================================
# === GPS ===
# =========================================


@router.post("/gps", response_model=List[GpsPointRead], status_code=201)
def receive_gps_points(
    payload: GpsPointBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Приём пачки GPS-точек с устройства."""
    if not payload.points:
        raise HTTPException(status_code=400, detail="No points provided")
    return save_gps_points(db, payload.points, current_user.company_id or 0)


@router.post("/gps/single", response_model=GpsPointRead, status_code=201)
def receive_single_gps_point(
    payload: GpsPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Приём одной GPS-точки."""
    return save_gps_points(db, [payload], current_user.company_id or 0)[0]


@router.get("/gps/{vehicle_id}", response_model=List[GpsPointRead])
def get_vehicle_track(
    vehicle_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История GPS-точек по технике."""
    stmt = (
        select(GpsPoint)
        .where(GpsPoint.vehicle_id == vehicle_id)
        .order_by(GpsPoint.recorded_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


# =========================================
# === Geofences ===
# =========================================


@router.get("/geofences", response_model=List[GeofenceRead])
def list_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Geofence).order_by(Geofence.name)
    return db.scalars(stmt).all()


@router.post("/geofences", response_model=GeofenceRead, status_code=201)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = Geofence(**payload.model_dump(), company_id=current_user.company_id)
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return gf


@router.delete("/geofences/{geofence_id}", status_code=204)
def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = db.get(Geofence, geofence_id)
    if not gf:
        raise HTTPException(status_code=404, detail="Geofence not found")
    gf.is_active = False
    db.commit()


# =========================================
# === Fuel ===
# =========================================


@router.get("/fuel", response_model=List[FuelTransactionRead])
def list_fuel_transactions(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(FuelTransaction).order_by(FuelTransaction.occurred_at.desc())
    if vehicle_id:
        stmt = stmt.where(FuelTransaction.vehicle_id == vehicle_id)
    return db.scalars(stmt.limit(100)).all()


@router.post("/fuel", response_model=FuelTransactionRead, status_code=201)
def create_fuel_transaction(
    payload: FuelTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_cost = None
    if payload.price_per_liter:
        total_cost = payload.volume * payload.price_per_liter
    ft = FuelTransaction(
        **payload.model_dump(),
        total_cost=total_cost,
        company_id=current_user.company_id,
    )
    db.add(ft)
    db.commit()
    db.refresh(ft)
    return ft


# =========================================
# === Alerts ===
# =========================================


class AlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    status: str
    vehicle_id: int | None = None
    title: str
    description: str | None = None
    details: dict | None = None
    occurred_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("severity", "status", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/alerts", response_model=List[AlertRead])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Alert).order_by(Alert.occurred_at.desc())
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != AlertStatus.active:
        raise HTTPException(status_code=409, detail="Alert not active")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_by = current_user.id
    from datetime import datetime, timezone
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


# =========================================
# === Notifications ===
# =========================================


@router.get("/notifications", response_model=List[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.sent_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    from datetime import datetime, timezone
    notif.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notif)
    return notif


@router.get("/notifications/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    return {"unread_count": count or 0}


# =========================================
# === Dashboard ===
# =========================================


@router.get("/dashboard", response_model=TelematicsDashboard)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = get_telematics_dashboard(db, current_user.company_id or 0)
    return TelematicsDashboard(**stats)


# =========================================
# === Alert Rules ===
# =========================================


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str = "warning"
    notify_email: bool = False
    notify_in_app: bool = True


class AlertRuleRead(BaseModel):
    id: int
    name: str
    rule_type: str
    threshold: float | None = None
    severity: str
    is_active: bool
    notify_email: bool
    notify_in_app: bool

    model_config = ConfigDict(from_attributes=True)

    @field_validator("severity", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


@router.get("/rules", response_model=List[AlertRuleRead])
def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список правил алертов компании."""
    stmt = select(AlertRule).where(
        AlertRule.company_id == (current_user.company_id or 0)
    )
    return db.scalars(stmt).all()


@router.post("/rules", response_model=AlertRuleRead, status_code=201)
def create_alert_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать правило алерта."""
    rule = AlertRule(
        company_id=current_user.company_id or 0,
        **payload.model_dump(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/rules/seed-defaults", status_code=201)
def seed_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать правила по умолчанию для компании."""
    seed_default_rules(db, current_user.company_id or 0)
    return {"detail": "Default rules created"}


@router.delete("/rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    db.commit()
'''

ROUTES.write_text(TELEMATICS_ROUTES, encoding="utf-8")
print("✅ app/api/routes/telematics.py rewritten")

# === 2. conftest.py ===
CONFTEST = '''from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models import *  # noqa: F401, F403
from app.models.dispatch import Request

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_test_request(db, client_id, category_id, company_id, **overrides):
    """Фабрика тестовых заявок со всеми обязательными полями."""
    now = datetime.now(timezone.utc)
    defaults = {
        "client_id": client_id,
        "status": "completed",
        "request_type": "one_time",
        "vehicle_category_id": category_id,
        "work_type": "Тестовая работа",
        "object_address": "Москва",
        "planned_start": now,
        "planned_end": now + timedelta(hours=8),
        "shift_duration_hours": 8,
        "client_rate": Decimal("15000"),
        "rate_type": "per_shift",
        "estimated_amount": Decimal("15000"),
        "source_channel": "phone",
        "priority": "normal",
        "company_id": company_id,
    }
    defaults.update(overrides)
    return Request(**defaults)
'''
(TESTS / "conftest.py").write_text(CONFTEST, encoding="utf-8")
print("✅ tests/conftest.py rewritten")

# === 3. test_finance_service.py (использует make_test_request!) ===
FIN_SVC = '''from datetime import date
from decimal import Decimal
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import (
    Invoice, InvoiceItem, Act, Payout, Payment, DocumentStatus,
)
from app.services.finance_service import (
    generate_document_number, calculate_invoice_totals,
    register_payment, calculate_payout, get_finance_dashboard,
)
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request


def create_test_entities(db):
    init_system_data(db)
    company = Company(name="T", legal_name='OOO "T"', inn="7799999999")
    db.add(company); db.flush()
    client = Contractor(type="client", name="C", inn="7788888888", company_id=company.id)
    owner = Contractor(type="owner", name="O", company_id=company.id)
    db.add(client); db.add(owner); db.flush()
    category = Category(name="K", code="test", level=1, company_id=company.id)
    db.add(category); db.flush()
    vehicle = Vehicle(id_type="vin", id_value="TEST12345678901234",
                      category_id=category.id, name="V", status="free", company_id=company.id)
    db.add(vehicle); db.flush()
    request = make_test_request(db, client.id, category.id, company.id)
    db.add(request); db.flush()
    return {"company": company, "client": client, "owner": owner, "vehicle": vehicle, "request": request}


def test_generate_document_number_first(db):
    create_test_entities(db)
    n = generate_document_number(db, "INV")
    assert n.startswith("INV-") and n.endswith("-0001")


def test_generate_document_number_sequence(db):
    create_test_entities(db)
    n1 = generate_document_number(db, "INV")
    db.add(Invoice(document_number=n1, request_id=1, client_id=1, company_id=1,
                   invoice_date=date(2026, 9, 1), status=DocumentStatus.draft))
    db.commit()
    n2 = generate_document_number(db, "INV")
    assert n1 != n2 and n2.endswith("-0002")


def test_generate_document_number_different_prefixes(db):
    create_test_entities(db)
    assert generate_document_number(db, "INV").startswith("INV-")
    assert generate_document_number(db, "ACT").startswith("ACT-")
    assert generate_document_number(db, "PAY").startswith("PAY-")


def test_calculate_invoice_totals_no_vat(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="X", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    i1 = InvoiceItem(invoice_id=inv.id, description="U1", quantity=Decimal("8"), unit="h", unit_price=Decimal("2000"))
    i2 = InvoiceItem(invoice_id=inv.id, description="U2", quantity=Decimal("1"), unit="pc", unit_price=Decimal("3000"))
    db.add_all([i1, i2]); inv.items = [i1, i2]
    calculate_invoice_totals(inv)
    assert inv.subtotal == Decimal("19000")
    assert inv.total == Decimal("19000")


def test_calculate_invoice_totals_with_vat(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="X", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  vat_rate=Decimal("20"), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    item = InvoiceItem(invoice_id=inv.id, description="U", quantity=Decimal("1"), unit="pc", unit_price=Decimal("10000"))
    db.add(item); inv.items = [item]
    calculate_invoice_totals(inv)
    assert inv.vat_amount == Decimal("2000")
    assert inv.total == Decimal("12000")


def test_calculate_payout_basic():
    r = calculate_payout(Decimal("10000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("1500")
    assert r["net_amount"] == Decimal("8500")


def test_calculate_payout_zero_commission():
    r = calculate_payout(Decimal("5000"), Decimal("0"))
    assert r["platform_commission"] == Decimal("0")


def test_calculate_payout_fractional():
    r = calculate_payout(Decimal("1000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("150.00")


def test_register_payment_updates_invoice(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="X", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("5000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p)
    db.refresh(inv)
    assert inv.paid_amount == Decimal("5000")
    assert inv.status == DocumentStatus.partially_paid


def test_register_payment_full_paid(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="X", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("10000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p)
    db.refresh(inv)
    assert inv.status == DocumentStatus.paid


def test_register_payment_updates_payout(db):
    e = create_test_entities(db)
    po = Payout(document_number="X", owner_id=e["owner"].id, vehicle_id=e["vehicle"].id,
                company_id=e["company"].id, gross_amount=Decimal("10000"),
                platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.sent)
    db.add(po); db.flush()
    p = Payment(payout_id=po.id, amount=Decimal("8500"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p)
    db.refresh(po)
    assert po.status == DocumentStatus.paid


def test_get_finance_dashboard_empty(db):
    e = create_test_entities(db)
    r = get_finance_dashboard(db, e["company"].id)
    assert r["total_revenue"] == Decimal("0")


def test_get_finance_dashboard_with_data(db):
    e = create_test_entities(db)
    db.add(Invoice(document_number="X", request_id=e["request"].id, client_id=e["client"].id,
                   company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                   total=Decimal("12000"), paid_amount=Decimal("5000"), status=DocumentStatus.partially_paid))
    db.add(Payout(document_number="Y", owner_id=e["owner"].id, vehicle_id=e["vehicle"].id,
                  company_id=e["company"].id, gross_amount=Decimal("10000"),
                  platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                  commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.draft))
    db.add(Act(document_number="Z", request_id=e["request"].id, client_id=e["client"].id,
               company_id=e["company"].id, act_date=date(2026, 9, 1),
               total_amount=Decimal("12000"), status=DocumentStatus.draft))
    db.commit()
    r = get_finance_dashboard(db, e["company"].id)
    assert r["total_revenue"] == Decimal("12000")
    assert r["total_paid"] == Decimal("5000")
    assert r["total_commission_earned"] == Decimal("1500")
'''
(TESTS / "test_finance_service.py").write_text(FIN_SVC, encoding="utf-8")
print("✅ tests/test_finance_service.py rewritten (uses make_test_request)")

# === 4. test_finance_api.py (использует make_test_request!) ===
FIN_API = '''from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.services.auth_service import hash_password
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request


def setup_finance_test_data(db):
    init_system_data(db)
    company = Company(name="API", legal_name='OOO "API"', inn="7712345678")
    db.add(company); db.flush()
    user = User(email="f@t.com", full_name="T", password_hash=hash_password("x"),
                company_id=company.id, is_superuser=True)
    db.add(user); db.flush()
    client = Contractor(type="client", name="C", inn="7798765432", company_id=company.id)
    owner = Contractor(type="owner", name="O", company_id=company.id)
    db.add(client); db.add(owner); db.flush()
    category = Category(name="K", code="api", level=1, company_id=company.id)
    db.add(category); db.flush()
    vehicle = Vehicle(id_type="vin", id_value="API12345678901234", category_id=category.id,
                      name="V", status="free", company_id=company.id)
    db.add(vehicle); db.flush()
    request = make_test_request(db, client.id, category.id, company.id)
    db.add(request); db.commit()
    return {"user": user, "company": company, "client": client, "owner": owner, "vehicle": vehicle, "request": request}


def _setup(client, db):
    from app.api.deps import get_current_user
    from app.main import app
    data = setup_finance_test_data(db)
    app.dependency_overrides[get_current_user] = lambda: data["user"]
    return data


def _clear():
    from app.main import app
    app.dependency_overrides.clear()


def test_create_invoice(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01", "vat_rate": 20.0,
            "items": [{"description": "E", "quantity": 8, "unit": "h", "unit_price": 2000}],
        })
        assert r.status_code == 201
        assert r.json()["subtotal"] == "16000.00"
        assert r.json()["total"] == "19200.00"
    finally:
        _clear()


def test_list_invoices(client, db):
    d = _setup(client, db)
    try:
        client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "pc", "unit_price": 1000}],
        })
        r = client.get("/api/v1/invoices")
        assert r.status_code == 200 and len(r.json()) >= 1
    finally:
        _clear()


def test_send_invoice(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "pc", "unit_price": 1000}],
        })
        iid = cr.json()["id"]
        sr = client.post(f"/api/v1/invoices/{iid}/send")
        assert sr.status_code == 200 and sr.json()["status"] == "sent"
        assert client.post(f"/api/v1/invoices/{iid}/send").status_code == 409
    finally:
        _clear()


def test_download_invoice_pdf(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "P", "quantity": 1, "unit": "pc", "unit_price": 500}],
        })
        r = client.get(f"/api/v1/invoices/{cr.json()['id']}/pdf")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
    finally:
        _clear()


def test_create_act(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-01", "total_amount": 15000,
        })
        assert r.status_code == 201
        assert r.json()["document_number"].startswith("ACT-")
    finally:
        _clear()


def test_sign_act_both_parties(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-01", "total_amount": 10000,
        })
        aid = cr.json()["id"]
        s1 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"})
        assert s1.status_code == 200 and s1.json()["signed_by_client_at"] is not None
        s2 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "executor"})
        assert s2.status_code == 200 and s2.json()["status"] == "paid"
        assert client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"}).status_code == 409
    finally:
        _clear()


def test_create_payout_auto_commission(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id, "request_id": d["request"].id,
            "gross_amount": 20000, "commission_rate": 15, "payout_date": "2026-09-01",
        })
        assert r.status_code == 201
        b = r.json()
        assert b["gross_amount"] == "20000.00"
        assert b["platform_commission"] == "3000.00"
        assert b["net_amount"] == "17000.00"
    finally:
        _clear()


def test_approve_payout(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id,
            "gross_amount": 10000, "commission_rate": 10, "payout_date": "2026-09-01",
        })
        r = client.post(f"/api/v1/payouts/{cr.json()['id']}/approve")
        assert r.status_code == 200 and r.json()["status"] == "sent"
    finally:
        _clear()


def test_payment_updates_invoice(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "pc", "unit_price": 10000}],
        })
        iid = cr.json()["id"]
        pr = client.post("/api/v1/payments", json={
            "invoice_id": iid, "amount": 5000, "method": "bank_transfer", "payment_date": "2026-09-05",
        })
        assert pr.status_code == 201
        gr = client.get(f"/api/v1/invoices/{iid}")
        assert gr.json()["paid_amount"] == "5000.00"
        assert gr.json()["status"] == "partially_paid"
    finally:
        _clear()


def test_finance_dashboard(client, db):
    d = _setup(client, db)
    try:
        r = client.get("/api/v1/payments/dashboard")
        assert r.status_code == 200
        for k in ("total_revenue", "total_paid", "total_commission_earned", "invoices_count"):
            assert k in r.json()
    finally:
        _clear()


def test_full_finance_workflow(client, db):
    d = _setup(client, db)
    try:
        inv = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id, "invoice_date": "2026-09-01", "vat_rate": 20,
            "items": [{"description": "W", "quantity": 8, "unit": "h", "unit_price": 1000}],
        }).json()
        client.post(f"/api/v1/invoices/{inv['id']}/send")
        client.post("/api/v1/payments", json={
            "invoice_id": inv["id"], "amount": 9600, "method": "bank_transfer", "payment_date": "2026-09-10",
        })
        act = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-10", "total_amount": 9600,
        }).json()
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "client"})
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "executor"})
        po = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id, "request_id": d["request"].id,
            "gross_amount": 8000, "commission_rate": 15, "payout_date": "2026-09-10",
        }).json()
        assert po["net_amount"] == "6800.00"
        pdf = client.get(f"/api/v1/invoices/{inv['id']}/pdf")
        assert pdf.status_code == 200
    finally:
        _clear()
'''
(TESTS / "test_finance_api.py").write_text(FIN_API, encoding="utf-8")
print("✅ tests/test_finance_api.py rewritten (uses make_test_request)")

print("\n🎉 Все 4 файла исправлены!")
print("\nСледующие шаги:")
print("   1. uvicorn app.main:app --reload --port 8000  (если не запущен)")
print("   2. del test.db  (в backend/)")
print("   3. pytest tests/ -v")