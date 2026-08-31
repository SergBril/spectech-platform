def get_token(client, email="contractor@test.com"):
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "password123",
        "full_name": "Contractor Test",
    })
    response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "password123",
    })
    return response.json()["access_token"]


def test_list_contractors(client):
    """Обычный пользователь может видеть список контрагентов (проверка прав временно отключена)."""
    token = get_token(client)
    
    response = client.get(
        "/api/v1/contractors",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Сейчас проверка прав отключена, поэтому 200
    assert response.status_code == 200
    # Ответ должен быть списком
    assert isinstance(response.json(), list)


def test_create_contractor_invalid_type(client):
    """Создание контрагента с невалидным типом должно возвращать 422."""
    token = get_token(client, "contractor2@test.com")
    
    response = client.post(
        "/api/v1/contractors",
        json={
            "type": "invalid_type",
            "name": "Test Contractor",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # Должен вернуть 422 - невалидный тип
    assert response.status_code == 422


def test_create_contractor_valid(client):
    """Создание контрагента с валидными данными."""
    token = get_token(client, "contractor3@test.com")
    
    response = client.post(
        "/api/v1/contractors",
        json={
            "type": "client",
            "name": "Тестовый клиент",
            "inn": "9999999999",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "client"
    assert data["name"] == "Тестовый клиент"