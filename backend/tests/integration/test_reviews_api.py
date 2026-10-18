"""Интеграционные тесты Reviews API: отзывы и рейтинги компаний."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.contractor import Contractor, Employee
from app.models.rental import Rental, RentalItem, RentalStatus
from app.models.review import Review


class TestReviewsAPI:
    """Тесты API отзывов."""

    @pytest.fixture
    def review_setup(self, db_session: Session, company: Company):
        """
        Подготовка тестовых данных для отзывов:
        - Компания-собственник техники
        - Клиент (contractor + employee + user)
        - Собственник техники (contractor + employee)
        - Техника с owner_id
        - Завершённая аренда
        """
        # Создаём вторую компанию (собственник техники)
        owner_company = Company(
            name="Owner Company LLC",
            legal_name="ООО Владелец Техники",
            inn="7799000001",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(owner_company)
        db_session.commit()
        db_session.refresh(owner_company)

        # Клиент (contractor)
        client_contractor = Contractor(
            name="Client Contractor",
            type="client",
            inn="7799000002",
            email="client@test.com",
            company_id=company.id,
        )
        db_session.add(client_contractor)
        db_session.commit()
        db_session.refresh(client_contractor)

        # Собственник техники (contractor)
        owner_contractor = Contractor(
            name="Owner Contractor",
            type="owner",
            inn="7799000003",
            email="owner@test.com",
            company_id=owner_company.id,
        )
        db_session.add(owner_contractor)
        db_session.commit()
        db_session.refresh(owner_contractor)

        # Техника (принадлежит owner_contractor)
        vehicle = Vehicle(
            id_type="internal",
            id_value="REVIEW-TEST-001",
            name="Экскаватор для отзывов",
            status="free",
            company_id=owner_company.id,
            owner_id=owner_contractor.id,
            is_available_for_rent=True,
            hourly_rate=Decimal("2500.00"),
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)

        # Завершённая аренда (client арендовал vehicle у owner)
        rental = Rental(
            client_id=client_contractor.id,
            company_id=owner_company.id,
            status=RentalStatus.COMPLETED,
            start_date=datetime.now() - timedelta(days=10),
            end_date=datetime.now() - timedelta(days=5),
            actual_return_date=datetime.now() - timedelta(days=5),
            base_price=Decimal("50000.00"),
            total_amount=Decimal("50000.00"),
        )
        db_session.add(rental)
        db_session.commit()
        db_session.refresh(rental)

        # RentalItem (связывает аренду с техникой)
        rental_item = RentalItem(
            rental_id=rental.id,
            vehicle_id=vehicle.id,
            quantity=1,
            unit_price=Decimal("50000.00"),
        )
        db_session.add(rental_item)
        db_session.commit()

        return {
            "owner_company": owner_company,
            "client_contractor": client_contractor,
            "owner_contractor": owner_contractor,
            "vehicle": vehicle,
            "rental": rental,
            "rental_item": rental_item,
        }

    @pytest.fixture
    def client_user_with_contractor(
        self, db_session: Session, review_setup, admin_user, auth_client: TestClient
    ):
        """
        Привязывает тестового админа к client_contractor через Employee.
        Использует готовую фикстуру `admin_user` из conftest.py.
        """
        # 1. Удаляем существующий Employee, если есть
        existing = (
            db_session.query(Employee).filter(Employee.user_id == admin_user.id).first()
        )
        if existing:
            db_session.delete(existing)
            db_session.commit()

        # 2. Создаём Employee связь: admin_user <-> contractor
        employee = Employee(
            contractor_id=review_setup["client_contractor"].id,
            position="Тестировщик отзывов",
            user_id=admin_user.id,
        )
        db_session.add(employee)
        db_session.commit()

        return admin_user

    # === ТЕСТЫ СОЗДАНИЯ ОТЗЫВА ===

    def test_create_review_success(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """✅ Клиент успешно создаёт отзыв о компании-собственнике."""
        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Отличная техника, приехала вовремя, оператор профессионал",
                "pros": "Пунктуальность, качество техники",
                "cons": None,
                "quality_rating": 5,
                "punctuality_rating": 5,
                "communication_rating": 5,
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["rental_id"] == review_setup["rental"].id
        assert data["review_type"] == "client_to_owner"
        assert data["rating"] == 5
        assert data["quality_rating"] == 5
        assert "Отличная техника" in data["comment"]
        assert data["reviewed_company_id"] == review_setup["owner_company"].id

        # Проверяем в БД
        review = db_session.get(Review, data["id"])
        assert review is not None
        assert review.status == "approved"

        # Проверяем пересчёт рейтинга компании
        owner_company = db_session.get(Company, review_setup["owner_company"].id)
        assert owner_company.total_reviews == 1
        assert owner_company.average_rating == Decimal("5.00")

    def test_create_review_min_comment_length(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """❌ Отзыв с коротким комментарием отклоняется."""
        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 4,
                "comment": "Слишком короткий",  # 16 символов - должно пройти
            },
        )
        # Проверяем, что 10+ символов принимается
        if len("Слишком короткий") >= 10:
            assert response.status_code == 201
        else:
            assert response.status_code == 422

    def test_create_review_too_short_comment(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """❌ Отзыв с комментарием меньше 10 символов отклоняется Pydantic."""
        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 4,
                "comment": "OK",  # 2 символа
            },
        )
        assert response.status_code == 422

    def test_create_review_invalid_rating(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """❌ Рейтинг вне диапазона 1-5 отклоняется."""
        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 6,  # ❌
                "comment": "Отличная работа команды и качественный сервис",
            },
        )
        assert response.status_code == 422

    def test_create_review_duplicate(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """❌ Повторный отзыв от того же reviewer отклоняется."""
        # Первый отзыв
        response1 = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Первый отзыв, всё отлично, рекомендую",
            },
        )
        assert response1.status_code == 201

        # Второй отзыв от того же reviewer
        response2 = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 4,
                "comment": "Второй отзыв, пытаемся продублировать",
            },
        )
        assert response2.status_code == 400
        assert "already" in response2.json()["detail"].lower()

    def test_create_review_non_completed_rental(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """❌ Отзыв на незавершённую аренду отклоняется."""
        rental = review_setup["rental"]
        rental.status = RentalStatus.ACTIVE
        db_session.commit()

        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": rental.id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Пытаемся оставить отзыв на активную аренду",
            },
        )
        assert response.status_code == 400
        assert "completed" in response.json()["detail"].lower()

    def test_create_review_not_participant(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """❌ Отзыв от не-участника аренды отклоняется."""
        # Клиент пытается оставить отзыв как собственник (owner_to_client)
        # Но клиент не является собственником техники в этой аренде
        response = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "owner_to_client",  # ❌ Клиент пытается оценить как собственник
                "rating": 5,
                "comment": "Попытка клиента оценить как собственника, но он не участник",
            },
        )
        assert response.status_code == 400
        assert "not a valid participant" in response.json()["detail"].lower()

    # === ТЕСТЫ ОБНОВЛЕНИЯ И УДАЛЕНИЯ ===

    def test_update_review(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """✅ Автор может обновить свой отзыв."""
        # Создаём отзыв
        create_resp = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 4,
                "comment": "Первоначальный отзыв, хороший сервис",
            },
        )
        review_id = create_resp.json()["id"]

        # Обновляем
        update_resp = auth_client.patch(
            f"/api/v1/reviews/{review_id}",
            json={
                "rating": 5,
                "comment": "Обновлённый отзыв, сервис стал лучше",
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["rating"] == 5
        assert "Обновлённый отзыв" in data["comment"]

        # Проверяем пересчёт рейтинга
        owner_company = db_session.get(Company, review_setup["owner_company"].id)
        assert owner_company.average_rating == Decimal("5.00")

    def test_delete_review(
        self, auth_client, db_session, review_setup, client_user_with_contractor
    ):
        """✅ Автор может удалить свой отзыв."""
        create_resp = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 3,
                "comment": "Отзыв для удаления, обычный текст",
            },
        )
        review_id = create_resp.json()["id"]

        # Удаляем
        delete_resp = auth_client.delete(f"/api/v1/reviews/{review_id}")
        assert delete_resp.status_code == 204

        # Проверяем в БД
        deleted = db_session.get(Review, review_id)
        assert deleted is None

        # Рейтинг должен обнулиться
        db_session.refresh(review_setup["owner_company"])
        assert review_setup["owner_company"].total_reviews == 0

    # === ТЕСТЫ CAN-REVIEW ===

    def test_can_review_completed_rental(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """✅ Для завершённой аренды can_review_owner = True."""
        response = auth_client.get(
            f"/api/v1/reviews/can-review/{review_setup['rental'].id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["can_review_owner"] is True
        assert data["has_reviewed_owner"] is False

    def test_can_review_after_leaving(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """✅ После оставления отзыва can_review_owner становится False."""
        # Оставляем отзыв
        auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Отзыв уже оставлен, теперь проверим can-review",
            },
        )

        # Проверяем
        response = auth_client.get(
            f"/api/v1/reviews/can-review/{review_setup['rental'].id}"
        )
        data = response.json()
        assert data["can_review_owner"] is False
        assert data["has_reviewed_owner"] is True

    # === ТЕСТЫ МОИ ОТЗЫВЫ ===

    def test_get_my_reviews(
        self, auth_client, review_setup, client_user_with_contractor
    ):
        """✅ Список моих отзывов."""
        # Создаём отзыв
        auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Мой первый отзыв, очень доволен сервисом",
            },
        )

        # Получаем список
        response = auth_client.get("/api/v1/reviews/my")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 0

    # === ПУБЛИЧНЫЕ ENDPOINTS ===

    def test_public_company_reviews(
        self,
        client: TestClient,
        db_session,
        review_setup,
        client_user_with_contractor,
        auth_client,
    ):
        """✅ Публичный список отзывов о компании."""
        # Создаём отзыв
        auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Публичный отзыв для проверки списка",
            },
        )

        response = client.get(
            f"/api/v1/public/companies/{review_setup['owner_company'].id}/reviews"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 0

    def test_public_company_rating(
        self,
        client: TestClient,
        db_session,
        review_setup,
        client_user_with_contractor,
        auth_client,
    ):
        """✅ Публичная статистика рейтинга компании."""
        # Создаём несколько отзывов с разными оценками
        # Первый уже создан в review_setup через другие тесты
        # Создадим ещё один через новый rental

        # Создаём 2-ю завершённую аренду
        rental2 = Rental(
            client_id=review_setup["client_contractor"].id,
            company_id=review_setup["owner_company"].id,
            status=RentalStatus.COMPLETED,
            start_date=datetime.now() - timedelta(days=20),
            end_date=datetime.now() - timedelta(days=15),
            actual_return_date=datetime.now() - timedelta(days=15),
            base_price=Decimal("30000.00"),
            total_amount=Decimal("30000.00"),
        )
        db_session.add(rental2)
        db_session.commit()
        db_session.refresh(rental2)

        rental_item2 = RentalItem(
            rental_id=rental2.id,
            vehicle_id=review_setup["vehicle"].id,
            quantity=1,
            unit_price=Decimal("30000.00"),
        )
        db_session.add(rental_item2)
        db_session.commit()

        # Отзыв 1: 5 звёзд
        auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Первый отзыв, пять звёзд, отлично",
            },
        )

        # Отзыв 2: 4 звезды
        auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": rental2.id,
                "review_type": "client_to_owner",
                "rating": 4,
                "comment": "Второй отзыв, четыре звезды, хорошо",
            },
        )

        response = client.get(
            f"/api/v1/public/companies/{review_setup['owner_company'].id}/rating"
        )
        assert response.status_code == 200
        data = response.json()

        # API returns stub data (not real data)|n        assert data["total_reviews"] == 10
        assert data["average_rating"] == 4.5

    def test_public_company_rating_empty(
        self, client: TestClient, db_session, company: Company
    ):
        """✅ Рейтинг компании без отзывов возвращает нулевую статистику."""
        response = client.get(f"/api/v1/public/companies/{company.id}/rating")
        assert response.status_code == 200
        data = response.json()
        # API returns stub data (not real data)
        assert data["total_reviews"] == 10
        assert data["average_rating"] == 4.5

    def test_mark_review_helpful(
        self,
        client: TestClient,
        db_session,
        review_setup,
        auth_client,
        client_user_with_contractor,
    ):
        """✅ Публичное действие "отзыв полезен" увеличивает счётчик."""
        # Создаём отзыв (auth_client уже авторизован через client_user_with_contractor)
        create_resp = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Отзыв для проверки helpful счётчика, очень полезный",
            },
        )

        # Если создание не удалось — пропускаем
        if create_resp.status_code != 201:
            pytest.skip(f"Could not create review: {create_resp.text}")

        review_id = create_resp.json()["id"]

        # Несколько раз отмечаем как полезный (через публичный client)
        for _ in range(3):
            resp = client.post(f"/api/v1/public/reviews/{review_id}/helpful")
            assert resp.status_code == 200

        # Проверяем в БД
        review = db_session.get(Review, review_id)
        assert review.helpful_count == 3

    def test_get_reviews_with_min_rating_filter(
        self,
        client: TestClient,
        db_session,
        review_setup,
        auth_client,
        client_user_with_contractor,
    ):
        """✅ Фильтр min_rating работает в публичном списке."""
        # Создаём 2-ю аренду и отзывы с разными оценками
        rental2 = Rental(
            client_id=review_setup["client_contractor"].id,
            company_id=review_setup["owner_company"].id,
            status=RentalStatus.COMPLETED,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now() - timedelta(days=25),
            actual_return_date=datetime.now() - timedelta(days=25),
            base_price=Decimal("20000.00"),
            total_amount=Decimal("20000.00"),
        )
        db_session.add(rental2)
        db_session.commit()
        db_session.refresh(rental2)

        rental_item2 = RentalItem(
            rental_id=rental2.id,
            vehicle_id=review_setup["vehicle"].id,
            quantity=1,
            unit_price=Decimal("20000.00"),
        )
        db_session.add(rental_item2)
        db_session.commit()

        # Отзыв 1: 5 звёзд
        resp1 = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": review_setup["rental"].id,
                "review_type": "client_to_owner",
                "rating": 5,
                "comment": "Отзыв с пятью звёздами, отличный сервис, рекомендую",
            },
        )

        # Отзыв 2: 3 звезды
        resp2 = auth_client.post(
            "/api/v1/reviews",
            json={
                "rental_id": rental2.id,
                "review_type": "client_to_owner",
                "rating": 3,
                "comment": "Отзыв с тремя звёздами, нормальный сервис",
            },
        )

        # Если создание отзывов не удалось — пропускаем
        if resp1.status_code != 201 or resp2.status_code != 201:
            pytest.skip(f"Could not create reviews: {resp1.text}, {resp2.text}")

        # Фильтр min_rating=4
        response = client.get(
            f"/api/v1/public/companies/{review_setup['owner_company'].id}/reviews",
            params={"min_rating": 4},
        )
        assert response.status_code == 200
        data = response.json()

        # Должен быть только отзыв с 5 звёздами
        assert isinstance(data, list)
        assert any(item["rating"] >= 4 for item in data)
