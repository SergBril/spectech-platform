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
        assert Decimal(data["total_amount"]) == Decimal("25000.00")

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
        assert invoice.subtotal == Decimal("20000.00")
        assert invoice.vat_amount == Decimal("4000.00")
        assert invoice.total == Decimal("24000.00")

        # 5. Проверяем, что создалась позиция счёта
        items = db_session.query(InvoiceItem).filter(
            InvoiceItem.invoice_id == invoice.id
        ).all()
        assert len(items) == 1
        assert "Аренда техники" in items[0].description
        assert items[0].amount == Decimal("20000.00")

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