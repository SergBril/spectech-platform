"""Интеграционные тесты для Rental API (Аренда техники)."""

from datetime import datetime, UTC, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.rental import RateType, RentalStatus, PrepaymentStatus


@pytest.mark.integration
class TestRentalCreate:
    """Тесты создания аренды."""

    def test_create_rental_hourly(
        self, auth_client: TestClient, sample_rental_client, sample_rental_vehicle
    ):
        """✅ Создание аренды с почасовой тарификацией."""
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)

        response = auth_client.post(
            "/api/v1/rentals",
            json={
                "client_id": sample_rental_client.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rate_type": RateType.HOURLY.value,
                "items": [
                    {
                        "vehicle_id": sample_rental_vehicle.id,
                        "quantity": 1,
                        "unit_price": "2500.00",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == RentalStatus.DRAFT.value
        assert data["rate_type"] == RateType.HOURLY.value
        # 8 часов × 2500 = 20000
        assert Decimal(data["total_amount"]) == Decimal("20000.00")
        assert len(data["items"]) == 1

    def test_create_rental_shift(
        self, auth_client: TestClient, sample_rental_client, sample_rental_vehicle
    ):
        """✅ Создание аренды с посменной тарификацией."""
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        # ИСПРАВЛЕНО: 16 часов = 2 смены (по 8 часов каждая)
        end = start + timedelta(hours=16)

        response = auth_client.post(
            "/api/v1/rentals",
            json={
                "client_id": sample_rental_client.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rate_type": RateType.SHIFT.value,
                "items": [
                    {
                        "vehicle_id": sample_rental_vehicle.id,
                        "quantity": 1,
                        "unit_price": "15000.00",  # 15000 за смену
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rate_type"] == RateType.SHIFT.value
        # 2 смены × 15000 = 30000
        assert Decimal(data["total_amount"]) == Decimal("30000.00")

    def test_create_rental_with_discount(
        self, auth_client: TestClient, sample_rental_client, sample_rental_vehicle
    ):
        """✅ Скидка уменьшает итоговую сумму."""
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=4)

        response = auth_client.post(
            "/api/v1/rentals",
            json={
                "client_id": sample_rental_client.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rate_type": RateType.HOURLY.value,
                "discount": "2000.00",
                "items": [
                    {
                        "vehicle_id": sample_rental_vehicle.id,
                        "quantity": 1,
                        "unit_price": "2500.00",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        # 4 часа × 2500 = 10000, минус скидка 2000 = 8000
        assert Decimal(data["base_price"]) == Decimal("10000.00")
        assert Decimal(data["discount"]) == Decimal("2000.00")
        assert Decimal(data["total_amount"]) == Decimal("8000.00")

    def test_create_rental_invalid_dates(
        self, auth_client: TestClient, sample_rental_client, sample_rental_vehicle
    ):
        """❌ Дата начала позже даты окончания — 400."""
        start = datetime.now(UTC)
        end = start - timedelta(hours=1)

        response = auth_client.post(
            "/api/v1/rentals",
            json={
                "client_id": sample_rental_client.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rate_type": RateType.HOURLY.value,
                "items": [
                    {
                        "vehicle_id": sample_rental_vehicle.id,
                        "quantity": 1,
                        "unit_price": "2500.00",
                    }
                ],
            },
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestRentalWorkflow:
    """Тесты жизненного цикла аренды."""

    def test_activate_rental(self, auth_client: TestClient, sample_rental):
        """✅ Активация аренды (DRAFT → ACTIVE)."""
        response = auth_client.post(f"/api/v1/rentals/{sample_rental.id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RentalStatus.ACTIVE.value

    def test_activate_empty_rental_fails(
        self, auth_client: TestClient, db_session, company, sample_rental_client
    ):
        """❌ Нельзя активировать аренду без позиций."""
        from app.models.rental import Rental, RentalStatus, RateType
        
        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(hours=8),
            rate_type=RateType.HOURLY,
            status=RentalStatus.DRAFT,
            base_price=Decimal("0"),
            total_amount=Decimal("0"),
        )
        db_session.add(rental)
        db_session.commit()
        db_session.refresh(rental)

        response = auth_client.post(f"/api/v1/rentals/{rental.id}/activate")
        assert response.status_code == 400
        assert "позиц" in response.json()["detail"].lower() or "items" in response.json()["detail"].lower()

    def test_cancel_rental(self, auth_client: TestClient, sample_rental):
        """✅ Отмена аренды (DRAFT → CANCELLED)."""
        response = auth_client.post(f"/api/v1/rentals/{sample_rental.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RentalStatus.CANCELLED.value

    def test_close_rental_with_actuals(
        self, auth_client: TestClient, db_session, sample_rental
    ):
        """✅ Завершение аренды с фактическими данными."""
        # Сначала активируем
        auth_client.post(f"/api/v1/rentals/{sample_rental.id}/activate")

        # Получаем ID позиции
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        item_id = rental_data["items"][0]["id"]

        # Закрываем с фактическими 10 моточасами (вместо плановых 8)
        response = auth_client.post(
            f"/api/v1/rentals/{sample_rental.id}/close",
            json={
                "items_actuals": [
                    {
                        "rental_item_id": item_id,
                        "actual_moto_hours": "10.00",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RentalStatus.COMPLETED.value
        # 10 часов × 2500 = 25000 (больше плана)
        assert Decimal(data["total_amount"]) >= Decimal("25000.00")
        # Дополнительно проверяем структуру
        assert "penalty_amount" in data or data["total_amount"] > data["base_price"]

    def test_close_rental_with_overdue_penalty(
        self, auth_client: TestClient, db_session, company, sample_rental_client, sample_rental_vehicle
    ):
        """✅ Штраф за просрочку (150% ставки за каждый час)."""
        from app.models.rental import Rental, RentalItem, RentalStatus, RateType
        
        # Создаём аренду с end_date в прошлом
        start = datetime.now(UTC) - timedelta(hours=10)
        end = datetime.now(UTC) - timedelta(hours=2)  # Должна была вернуться 2 часа назад

        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=start,
            end_date=end,
            rate_type=RateType.HOURLY,
            status=RentalStatus.ACTIVE,  # Уже активна
            base_price=Decimal("20000.00"),
            total_amount=Decimal("20000.00"),
        )
        db_session.add(rental)
        db_session.flush()

        item = RentalItem(
            rental_id=rental.id,
            vehicle_id=sample_rental_vehicle.id,
            quantity=1,
            unit_price=Decimal("2500.00"),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(rental)
        db_session.refresh(item)

        # Закрываем с фактическими 10 часами работы
        response = auth_client.post(
            f"/api/v1/rentals/{rental.id}/close",
            json={
                "items_actuals": [
                    {
                        "rental_item_id": item.id,
                        "actual_moto_hours": "10.00",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RentalStatus.COMPLETED.value
        # Факт (10ч × 2500 = 25000) + штраф за 2 часа просрочки
        # (2ч × 2500 × 1.5 = 7500) = 32500
        total = Decimal(data["total_amount"])
        assert total > Decimal("25000.00")  # Больше факта из-за штрафа
        assert total >= Decimal("32000.00")  # Примерно 32500


@pytest.mark.integration
class TestRentalItems:
    """Тесты управления позициями аренды."""

    def test_add_rental_item(
        self, auth_client: TestClient, db_session, sample_rental, sample_rental_vehicle
    ):
        """✅ Добавление второй техники в аренду."""
        # Создаём вторую машину
        from app.models.catalog import Vehicle
        v2 = Vehicle(
            name="Экскаватор JCB 3CX",
            company_id=sample_rental.company_id,
            status="free",
            id_type="internal",
            id_value="JCB-3CX-RENT-002",
        )
        db_session.add(v2)
        db_session.commit()
        db_session.refresh(v2)

        response = auth_client.post(
            f"/api/v1/rentals/{sample_rental.id}/items",
            json={
                "vehicle_id": v2.id,
                "quantity": 1,
                "unit_price": "3000.00",
            },
        )
        assert response.status_code == 201
        
        # Проверяем, что позиций стало 2
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        assert len(rental_data["items"]) == 2

    def test_remove_rental_item(
        self, auth_client: TestClient, sample_rental
    ):
        """✅ Удаление позиции из аренды."""
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        item_id = rental_data["items"][0]["id"]

        response = auth_client.delete(
            f"/api/v1/rentals/{sample_rental.id}/items/{item_id}"
        )
        assert response.status_code == 204

        # Позиций больше нет
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        assert len(rental_data["items"]) == 0

    def test_cannot_add_item_to_active_rental(
        self, auth_client: TestClient, sample_rental, sample_rental_vehicle
    ):
        """❌ Нельзя добавить позицию в активную аренду."""
        # Активируем
        auth_client.post(f"/api/v1/rentals/{sample_rental.id}/activate")

        response = auth_client.post(
            f"/api/v1/rentals/{sample_rental.id}/items",
            json={
                "vehicle_id": sample_rental_vehicle.id,
                "quantity": 1,
                "unit_price": "1000.00",
            },
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestRentalList:
    """Тесты списка аренд."""

    def test_list_rentals(
        self, auth_client: TestClient, sample_rental
    ):
        """✅ Список аренд компании."""
        response = auth_client.get("/api/v1/rentals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["id"] == sample_rental.id

    def test_filter_rentals_by_status(
        self, auth_client: TestClient, sample_rental
    ):
        """✅ Фильтрация по статусу DRAFT."""
        response = auth_client.get(
            f"/api/v1/rentals?status={RentalStatus.DRAFT.value}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == RentalStatus.DRAFT.value for r in data)

    def test_get_rental_details(
        self, auth_client: TestClient, sample_rental
    ):
        """✅ Получение деталей аренды."""
        response = auth_client.get(f"/api/v1/rentals/{sample_rental.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_rental.id
        assert "items" in data
        assert len(data["items"]) == 1

    def test_get_nonexistent_rental(
        self, auth_client: TestClient
    ):
        """❌ 404 для несуществующей аренды."""
        response = auth_client.get("/api/v1/rentals/999999")
        assert response.status_code == 404

class TestRentalFinanceIntegration:
    """Тесты интеграции Rental → Finance (автосоздание Invoice)."""

    def test_close_rental_creates_invoice(
        self, auth_client: TestClient, db_session, sample_rental
    ):
        """✅ При завершении аренды автоматически создаётся Invoice."""
        from app.models.finance import Invoice, InvoiceItem

        # 1. Активируем аренду
        auth_client.post(f"/api/v1/rentals/{sample_rental.id}/activate")

        # 2. Получаем ID позиции
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        item_id = rental_data["items"][0]["id"]

        # 3. Закрываем аренду с фактическими 8 моточасами
        response = auth_client.post(
            f"/api/v1/rentals/{sample_rental.id}/close",
            json={
                "items_actuals": [
                    {
                        "rental_item_id": item_id,
                        "actual_moto_hours": "8.00",
                    }
                ],
            },
        )
        assert response.status_code == 200
        rental_data = response.json()
        assert rental_data["status"] == RentalStatus.COMPLETED.value

        # 4. Проверяем, что создался Invoice
        invoices = db_session.query(Invoice).filter(
            Invoice.rental_id == sample_rental.id
        ).all()
        assert len(invoices) == 1

        invoice = invoices[0]
        assert invoice.client_id == sample_rental.client_id
        assert invoice.company_id == sample_rental.company_id
        assert invoice.rental_id == sample_rental.id
        assert invoice.status.value == "draft"
        
        # Проверяем суммы (8 часов × 2500 = 20000, + 20% VAT = 24000)
        assert invoice.subtotal >= Decimal("20000.00")
        assert invoice.vat_amount >= Decimal("4000.00")
        assert invoice.vat_amount == (invoice.subtotal * Decimal("0.20")).quantize(Decimal("0.01"))
        assert invoice.total >= Decimal("24000.00")

        # 5. Проверяем, что создалась позиция счёта
        items = db_session.query(InvoiceItem).filter(
            InvoiceItem.invoice_id == invoice.id
        ).all()
        assert len(items) == 1
        assert "Аренда техники" in items[0].description
        assert items[0].amount >= Decimal("20000.00")

    def test_close_rental_invoice_includes_overdue_penalty(
        self, auth_client: TestClient, db_session, company, sample_rental_client, sample_rental_vehicle
    ):
        """✅ Invoice включает штраф за просрочку."""
        from app.models.rental import Rental, RentalItem, RentalStatus, RateType
        from app.models.finance import Invoice

        # Создаём аренду с end_date в прошлом
        start = datetime.now(UTC) - timedelta(hours=10)
        end = datetime.now(UTC) - timedelta(hours=2)

        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=start,
            end_date=end,
            rate_type=RateType.HOURLY,
            status=RentalStatus.ACTIVE,
            base_price=Decimal("20000.00"),
            total_amount=Decimal("20000.00"),
        )
        db_session.add(rental)
        db_session.flush()

        item = RentalItem(
            rental_id=rental.id,
            vehicle_id=sample_rental_vehicle.id,
            quantity=1,
            unit_price=Decimal("2500.00"),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(rental)
        db_session.refresh(item)

        # Закрываем с фактическими 10 часами
        response = auth_client.post(
            f"/api/v1/rentals/{rental.id}/close",
            json={
                "items_actuals": [
                    {
                        "rental_item_id": item.id,
                        "actual_moto_hours": "10.00",
                    }
                ],
            },
        )
        assert response.status_code == 200

        # Проверяем Invoice
        invoices = db_session.query(Invoice).filter(
            Invoice.rental_id == rental.id
        ).all()
        assert len(invoices) == 1

        invoice = invoices[0]
        # Факт (10ч × 2500 = 25000) + штраф (2ч × 2500 × 1.5 = 7500) = 32500
        assert invoice.subtotal > Decimal("32000.00")
        assert invoice.total > Decimal("38000.00")  # + 20% VAT

    def test_cancel_rental_does_not_create_invoice(
        self, auth_client: TestClient, db_session, sample_rental
    ):
        """✅ При отмене аренды Invoice НЕ создаётся."""
        from app.models.finance import Invoice

        # Отменяем аренду
        response = auth_client.post(f"/api/v1/rentals/{sample_rental.id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == RentalStatus.CANCELLED.value

        # Проверяем, что Invoice не создался
        invoices = db_session.query(Invoice).filter(
            Invoice.rental_id == sample_rental.id
        ).all()
        assert len(invoices) == 0

    def test_close_rental_creates_payout(
        self, auth_client: TestClient, db_session, sample_rental
    ):
        """✅ При завершении аренды создаётся Payout собственнику техники."""
        from app.models.finance import Payout

        # 1. Активируем аренду
        auth_client.post(f"/api/v1/rentals/{sample_rental.id}/activate")

        # 2. Получаем ID позиции
        rental_data = auth_client.get(
            f"/api/v1/rentals/{sample_rental.id}"
        ).json()
        item_id = rental_data["items"][0]["id"]

        # 3. Закрываем аренду с фактическими 8 моточасами
        response = auth_client.post(
            f"/api/v1/rentals/{sample_rental.id}/close",
            json={
                "items_actuals": [
                    {"rental_item_id": item_id, "actual_moto_hours": "8.00"}
                ],
            },
        )
        assert response.status_code == 200

        # 4. Проверяем, что создался Payout
        payouts = db_session.query(Payout).filter(
            Payout.rental_id == sample_rental.id
        ).all()
        assert len(payouts) == 1

        payout = payouts[0]
        # gross = 20000 (10 часов × 2500), commission 10% = 2000, net = 18000
        assert payout.gross_amount >= Decimal("20000.00")
        assert payout.platform_commission == (payout.gross_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        assert payout.net_amount == payout.gross_amount - payout.platform_commission
        assert payout.commission_rate == Decimal("10.00")
        assert payout.status.value == "draft"
        assert payout.calculation_details["source"] == "auto_from_rental"

    def test_close_rental_multiple_owners_creates_multiple_payouts(
        self, auth_client: TestClient, db_session, company, sample_rental_client
    ):
        """✅ Для машин разных собственников создаются разные Payouts."""
        from app.models.catalog import Vehicle
        from app.models.contractor import Contractor
        from app.models.rental import Rental, RentalItem, RentalStatus, RateType
        from app.models.finance import Payout
        
        # Создаём двух собственников
        owner1 = Contractor(name="Owner 1", inn="7700000001", type="owner", company_id=company.id)
        owner2 = Contractor(name="Owner 2", inn="7700000002", type="owner", company_id=company.id)
        db_session.add_all([owner1, owner2])
        db_session.flush()
        
        # Создаём 2 машины от разных собственников
        v1 = Vehicle(name="CAT 320", company_id=company.id, owner_id=owner1.id,
                    status="free", id_type="internal", id_value="TEST-V1")
        v2 = Vehicle(name="JCB 3CX", company_id=company.id, owner_id=owner2.id,
                    status="free", id_type="internal", id_value="TEST-V2")
        db_session.add_all([v1, v2])
        db_session.flush()
        
        # Создаём аренду с 2 машинами
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)
        
        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=start, end_date=end,
            rate_type=RateType.HOURLY,
            status=RentalStatus.ACTIVE,
            commission_rate=Decimal("10.00"),
            base_price=Decimal("0"),
            total_amount=Decimal("0"),
        )
        db_session.add(rental)
        db_session.flush()
        
        # Машина 1: 2500/ч × 8ч = 20000
        # Машина 2: 3000/ч × 8ч = 24000
        # Итого: 44000
        item1 = RentalItem(rental_id=rental.id, vehicle_id=v1.id, quantity=1, unit_price=Decimal("2500.00"))
        item2 = RentalItem(rental_id=rental.id, vehicle_id=v2.id, quantity=1, unit_price=Decimal("3000.00"))
        db_session.add_all([item1, item2])
        
        # Устанавливаем total_amount вручную (имитация работы close_rental)
        rental.base_price = Decimal("44000.00")
        rental.total_amount = Decimal("44000.00")
        db_session.commit()
        db_session.refresh(rental)
        
        # Закрываем аренду
        response = auth_client.post(
            f"/api/v1/rentals/{rental.id}/close",
            json={
                "items_actuals": [
                    {"rental_item_id": item1.id, "actual_moto_hours": "8.00"},
                    {"rental_item_id": item2.id, "actual_moto_hours": "8.00"},
                ],
            },
        )
        assert response.status_code == 200
        
        # Проверяем, что создано 2 Payout
        payouts = db_session.query(Payout).filter(
            Payout.rental_id == rental.id
        ).order_by(Payout.owner_id).all()
        assert len(payouts) == 2
        
        # Owner 1: 20000 gross, 2000 commission, 18000 net
        assert payouts[0].owner_id == owner1.id
        assert payouts[0].gross_amount >= Decimal("20000.00")
        assert payouts[0].platform_commission == (payouts[0].gross_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        assert payouts[0].net_amount == payouts[0].gross_amount - payouts[0].platform_commission
        
        # Owner 2: 24000 gross, 2400 commission, 21600 net
        assert payouts[1].owner_id == owner2.id
        assert payouts[1].gross_amount >= Decimal("24000.00")
        assert payouts[1].platform_commission == (payouts[1].gross_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        assert payouts[1].net_amount == payouts[1].gross_amount - payouts[1].platform_commission

    def test_close_rental_same_owner_groups_payouts(
        self, auth_client: TestClient, db_session, company, sample_rental_client
    ):
        """✅ Если у одного собственника 2 машины — создаётся ОДИН Payout с суммой."""
        from app.models.catalog import Vehicle
        from app.models.contractor import Contractor
        from app.models.rental import Rental, RentalItem, RentalStatus, RateType
        from app.models.finance import Payout
        
        # Один собственник
        owner = Contractor(name="Single Owner", inn="7700000003", type="owner", company_id=company.id)
        db_session.add(owner)
        db_session.flush()
        
        # 2 машины от одного собственника
        v1 = Vehicle(name="CAT 320", company_id=company.id, owner_id=owner.id,
                    status="free", id_type="internal", id_value="TEST-V3")
        v2 = Vehicle(name="JCB 3CX", company_id=company.id, owner_id=owner.id,
                    status="free", id_type="internal", id_value="TEST-V4")
        db_session.add_all([v1, v2])
        db_session.flush()
        
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)
        
        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=start, end_date=end,
            rate_type=RateType.HOURLY,
            status=RentalStatus.ACTIVE,
            commission_rate=Decimal("10.00"),
            base_price=Decimal("44000.00"),
            total_amount=Decimal("44000.00"),
        )
        db_session.add(rental)
        db_session.flush()
        
        item1 = RentalItem(rental_id=rental.id, vehicle_id=v1.id, quantity=1, unit_price=Decimal("2500.00"))
        item2 = RentalItem(rental_id=rental.id, vehicle_id=v2.id, quantity=1, unit_price=Decimal("3000.00"))
        db_session.add_all([item1, item2])
        db_session.commit()
        db_session.refresh(rental)
        
        response = auth_client.post(
            f"/api/v1/rentals/{rental.id}/close",
            json={
                "items_actuals": [
                    {"rental_item_id": item1.id, "actual_moto_hours": "8.00"},
                    {"rental_item_id": item2.id, "actual_moto_hours": "8.00"},
                ],
            },
        )
        assert response.status_code == 200
        
        # Проверяем — создан ОДИН Payout
        payouts = db_session.query(Payout).filter(
            Payout.rental_id == rental.id
        ).all()
        assert len(payouts) == 1
        
        payout = payouts[0]
        assert payout.owner_id == owner.id
        # Сумма обеих машин: 44000, комиссия 10% = 4400, net = 39600
        assert payout.gross_amount >= Decimal("44000.00")
        assert payout.platform_commission == (payout.gross_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        assert payout.net_amount == payout.gross_amount - payout.platform_commission
        
        # В details должны быть обе машины
        assert len(payout.calculation_details["vehicle_ids"]) == 2

    def test_close_rental_vehicle_without_owner_skipped(
        self, auth_client: TestClient, db_session, company, sample_rental_client
    ):
        """✅ Если у техники нет собственника, Payout не создаётся (но аренда завершается)."""
        from app.models.catalog import Vehicle
        from app.models.rental import Rental, RentalItem, RentalStatus, RateType
        from app.models.finance import Payout
        
        # Машина БЕЗ собственника (owner_id = None)
        v = Vehicle(
            name="Orphan Vehicle", company_id=company.id,
            owner_id=None,  # ← Нет собственника
            status="free", id_type="internal", id_value="ORPHAN-001"
        )
        db_session.add(v)
        db_session.flush()
        
        start = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)
        
        rental = Rental(
            client_id=sample_rental_client.id,
            company_id=company.id,
            start_date=start, end_date=end,
            rate_type=RateType.HOURLY,
            status=RentalStatus.ACTIVE,
            commission_rate=Decimal("10.00"),
            base_price=Decimal("20000.00"),
            total_amount=Decimal("20000.00"),
        )
        db_session.add(rental)
        db_session.flush()
        
        item = RentalItem(rental_id=rental.id, vehicle_id=v.id, quantity=1, unit_price=Decimal("2500.00"))
        db_session.add(item)
        db_session.commit()
        db_session.refresh(rental)
        
        response = auth_client.post(
            f"/api/v1/rentals/{rental.id}/close",
            json={
                "items_actuals": [
                    {"rental_item_id": item.id, "actual_moto_hours": "8.00"}
                ],
            },
        )
        # Аренда всё равно завершилась успешно
        assert response.status_code == 200
        
        # Но Payout не создан
        payouts = db_session.query(Payout).filter(
            Payout.rental_id == rental.id
        ).all()
        assert len(payouts) == 0