from datetime import datetime, timedelta, timezone

from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request
from app.services.auth_service import hash_password
from app.services.rbac_service import init_system_data


def setup_finance_test_data(db):
    """Подготовка данных для финансовых тестов."""
    init_system_data(db)

    company = Company(
        name="API Test Co",
        legal_name='ООО "API Test"',
        inn="7712345678",
    )
    db.add(company)
    db.flush()

    user = User(
        email="finance_api@test.com",
        full_name="Finance Tester",
        password_hash=hash_password("test123"),
        company_id=company.id,
        is_superuser=True,
    )
    db.add(user)
    db.flush()

    client = Contractor(
        type="client",
        name="API Client",
        inn="7798765432",
        company_id=company.id,
    )
    db.add(client)

    owner = Contractor(
        type="owner",
        name="API Owner",
        company_id=company.id,
    )
    db.add(owner)
    db.flush()

    category = Category(
        name="API Category",
        code="api_test",
        level=1,
        company_id=company.id,
    )
    db.add(category)
    db.flush()

    vehicle = Vehicle(
        id_type="vin",
        id_value="APITEST12345678901",
        category_id=category.id,
        name="API Vehicle",
        status="free",
        company_id=company.id,
    )
    db.add(vehicle)
    db.flush()

    now = datetime.now(timezone.utc)
    request = Request(
        client_id=client.id,
        status="completed",
        request_type="one_time",
        vehicle_category_id=category.id,
        work_type="API test work",
        object_address="Test address",
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        shift_duration_hours=8,
        source_channel="phone",
        priority="normal",
        company_id=company.id,
    )
    db.add(request)
    db.commit()

    return {
        "user": user,
        "company": company,
        "client": client,
        "owner": owner,
        "vehicle": vehicle,
        "request": request,
    }


def get_auth_header(client, db):
    """Получает данные с подменой авторизации на суперпользователя."""
    from app.api.deps import get_current_user
    from app.main import app

    data = setup_finance_test_data(db)

    def override():
        return data["user"]

    app.dependency_overrides[get_current_user] = override
    return data


def clear_overrides():
    """Очищает подмены зависимостей."""
    from app.main import app
    app.dependency_overrides.clear()


# === Invoice API ===


def test_create_invoice(client, db):
    """Создание счёта через API."""
    data = get_auth_header(client, db)
    try:
        response = client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "due_date": "2026-09-15",
                "vat_rate": 20.0,
                "comment": "Test invoice",
                "items": [
                    {
                        "description": "Экскаватор - 8 часов",
                        "quantity": 8,
                        "unit": "час",
                        "unit_price": 2000,
                    }
                ],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["document_number"].startswith("INV-")
        assert body["subtotal"] == "16000.00"
        assert body["vat_amount"] == "3200.00"
        assert body["total"] == "19200.00"
        assert body["status"] == "draft"
        assert len(body["items"]) == 1
    finally:
        clear_overrides()


def test_list_invoices(client, db):
    """Список счетов."""
    data = get_auth_header(client, db)
    try:
        client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "items": [
                    {"description": "Услуга", "quantity": 1, "unit": "шт", "unit_price": 1000}
                ],
            },
        )
        response = client.get("/api/v1/invoices")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 1
    finally:
        clear_overrides()


def test_send_invoice(client, db):
    """Отправка счёта меняет статус."""
    data = get_auth_header(client, db)
    try:
        create_resp = client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "items": [
                    {"description": "Услуга", "quantity": 1, "unit": "шт", "unit_price": 1000}
                ],
            },
        )
        invoice_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "draft"

        send_resp = client.post(f"/api/v1/invoices/{invoice_id}/send")
        assert send_resp.status_code == 200
        assert send_resp.json()["status"] == "sent"

        send_resp2 = client.post(f"/api/v1/invoices/{invoice_id}/send")
        assert send_resp2.status_code == 409
    finally:
        clear_overrides()


def test_download_invoice_pdf(client, db):
    """Скачивание PDF счёта."""
    data = get_auth_header(client, db)
    try:
        create_resp = client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "items": [
                    {"description": "PDF тест", "quantity": 1, "unit": "шт", "unit_price": 500}
                ],
            },
        )
        invoice_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:4] == b"%PDF"
    finally:
        clear_overrides()


# === Act API ===


def test_create_act(client, db):
    """Создание акта."""
    data = get_auth_header(client, db)
    try:
        response = client.post(
            "/api/v1/acts",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "act_date": "2026-09-01",
                "total_amount": 15000,
                "comment": "Test act",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["document_number"].startswith("ACT-")
        assert body["status"] == "draft"
    finally:
        clear_overrides()


def test_sign_act_both_parties(client, db):
    """Подписание акта обеими сторонами."""
    data = get_auth_header(client, db)
    try:
        create_resp = client.post(
            "/api/v1/acts",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "act_date": "2026-09-01",
                "total_amount": 10000,
            },
        )
        act_id = create_resp.json()["id"]

        sign1 = client.post(
            f"/api/v1/acts/{act_id}/sign",
            json={"signed_by": "client"},
        )
        assert sign1.status_code == 200
        body1 = sign1.json()
        assert body1["signed_by_client_at"] is not None
        assert body1["signed_by_executor_at"] is None

        sign2 = client.post(
            f"/api/v1/acts/{act_id}/sign",
            json={"signed_by": "executor"},
        )
        assert sign2.status_code == 200
        body2 = sign2.json()
        assert body2["signed_by_executor_at"] is not None
        assert body2["status"] == "paid"

        sign3 = client.post(
            f"/api/v1/acts/{act_id}/sign",
            json={"signed_by": "client"},
        )
        assert sign3.status_code == 409
    finally:
        clear_overrides()


# === Payout API ===


def test_create_payout_auto_commission(client, db):
    """Выплата с автоматическим расчётом комиссии."""
    data = get_auth_header(client, db)
    try:
        response = client.post(
            "/api/v1/payouts",
            json={
                "owner_id": data["owner"].id,
                "vehicle_id": data["vehicle"].id,
                "request_id": data["request"].id,
                "gross_amount": 20000,
                "commission_rate": 15,
                "payout_date": "2026-09-01",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["document_number"].startswith("PAY-")
        assert body["gross_amount"] == "20000.00"
        assert body["platform_commission"] == "3000.00"
        assert body["net_amount"] == "17000.00"
        assert body["commission_rate"] == "15.00"
    finally:
        clear_overrides()


def test_approve_payout(client, db):
    """Одобрение выплаты."""
    data = get_auth_header(client, db)
    try:
        create_resp = client.post(
            "/api/v1/payouts",
            json={
                "owner_id": data["owner"].id,
                "vehicle_id": data["vehicle"].id,
                "gross_amount": 10000,
                "commission_rate": 10,
                "payout_date": "2026-09-01",
            },
        )
        payout_id = create_resp.json()["id"]

        approve_resp = client.post(f"/api/v1/payouts/{payout_id}/approve")
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "sent"
    finally:
        clear_overrides()


# === Payment API ===


def test_payment_updates_invoice(client, db):
    """Платёж обновляет paid_amount счёта."""
    data = get_auth_header(client, db)
    try:
        inv_resp = client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "items": [
                    {"description": "Услуга", "quantity": 1, "unit": "шт", "unit_price": 10000}
                ],
            },
        )
        invoice_id = inv_resp.json()["id"]
        assert inv_resp.json()["paid_amount"] == "0.00"

        pay_resp = client.post(
            "/api/v1/payments",
            json={
                "invoice_id": invoice_id,
                "amount": 5000,
                "method": "bank_transfer",
                "payment_date": "2026-09-05",
            },
        )
        assert pay_resp.status_code == 201

        get_resp = client.get(f"/api/v1/invoices/{invoice_id}")
        assert get_resp.json()["paid_amount"] == "5000.00"
        assert get_resp.json()["status"] == "partially_paid"
    finally:
        clear_overrides()


# === Dashboard ===


def test_finance_dashboard(client, db):
    """Финансовый дашборд возвращает корректную статистику."""
    data = get_auth_header(client, db)
    try:
        response = client.get("/api/v1/payments/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert "total_revenue" in body
        assert "total_paid" in body
        assert "total_outstanding" in body
        assert "total_commission_earned" in body
        assert "invoices_count" in body
    finally:
        clear_overrides()


# === Полный цикл ===


def test_full_finance_workflow(client, db):
    """Полный финансовый цикл: счёт → платёж → выплата → PDF."""
    data = get_auth_header(client, db)
    try:
        inv_resp = client.post(
            "/api/v1/invoices",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "invoice_date": "2026-09-01",
                "vat_rate": 20,
                "items": [
                    {"description": "Работы", "quantity": 8, "unit": "час", "unit_price": 1000}
                ],
            },
        )
        assert inv_resp.status_code == 201
        invoice_id = inv_resp.json()["id"]

        client.post(f"/api/v1/invoices/{invoice_id}/send")

        pay_resp = client.post(
            "/api/v1/payments",
            json={
                "invoice_id": invoice_id,
                "amount": 9600,
                "method": "bank_transfer",
                "payment_date": "2026-09-10",
            },
        )
        assert pay_resp.status_code == 201

        act_resp = client.post(
            "/api/v1/acts",
            json={
                "request_id": data["request"].id,
                "client_id": data["client"].id,
                "act_date": "2026-09-10",
                "total_amount": 9600,
            },
        )
        act_id = act_resp.json()["id"]

        client.post(f"/api/v1/acts/{act_id}/sign", json={"signed_by": "client"})
        client.post(f"/api/v1/acts/{act_id}/sign", json={"signed_by": "executor"})

        pay_out_resp = client.post(
            "/api/v1/payouts",
            json={
                "owner_id": data["owner"].id,
                "vehicle_id": data["vehicle"].id,
                "request_id": data["request"].id,
                "gross_amount": 8000,
                "commission_rate": 15,
                "payout_date": "2026-09-10",
            },
        )
        assert pay_out_resp.status_code == 201
        assert pay_out_resp.json()["net_amount"] == "6800.00"
        assert pay_out_resp.json()["platform_commission"] == "1200.00"

        pdf_resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"

        dash_resp = client.get("/api/v1/payments/dashboard")
        assert dash_resp.status_code == 200
        dash = dash_resp.json()
        assert float(dash["total_revenue"]) >= 9600
        assert float(dash["total_commission_earned"]) >= 1200
    finally:
        clear_overrides()