def test_register(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "newuser@test.com",
        "password": "password123",
        "full_name": "Новый Пользователь",
    })
    assert response.status_code == 201
    assert response.json()["email"] == "newuser@test.com"


def test_login(client):
    client.post("/api/v1/auth/register", json={
        "email": "logintest@test.com",
        "password": "password123",
        "full_name": "Тест Логин",
    })

    response = client.post("/api/v1/auth/login", json={
        "email": "logintest@test.com",
        "password": "password123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={
        "email": "wrongpass@test.com",
        "password": "password123",
        "full_name": "Тест",
    })

    response = client.post("/api/v1/auth/login", json={
        "email": "wrongpass@test.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401