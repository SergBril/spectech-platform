"""Тесты WebSocket endpoints."""
from fastapi.testclient import TestClient
from app.main import app
from app.models.auth import User
from app.services.auth_service import hash_password, create_access_token
from app.services.rbac_service import init_system_data
from app.models.company import Company


def setup_ws_test(db):
    """Подготовка данных для WebSocket тестов."""
    init_system_data(db)
    company = Company(name="WS Test", legal_name='ООО "WS"', inn="7700000099")
    db.add(company)
    db.flush()
    
    user = User(
        email="ws@test.com",
        full_name="WS Tester",
        password_hash=hash_password("test123"),
        company_id=company.id,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_websocket_connection(client, db):
    """Тест подключения к WebSocket."""
    user = setup_ws_test(db)
    token = create_access_token(user)
    
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        # Получаем приветственное сообщение
        data = ws.receive_json()
        assert data["type"] == "connected"
        assert data["user_id"] == user.id
        assert data["company_id"] == user.company_id


def test_websocket_ping_pong(client, db):
    """Тест ping-pong."""
    user = setup_ws_test(db)
    token = create_access_token(user)
    
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.receive_json()  # connected
        
        # Отправляем ping
        ws.send_json({"type": "ping"})
        
        # Получаем pong
        data = ws.receive_json()
        assert data["type"] == "pong"
        assert "timestamp" in data


def test_websocket_subscribe(client, db):
    """Тест подписки на канал."""
    user = setup_ws_test(db)
    token = create_access_token(user)
    
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.receive_json()  # connected
        
        # Подписываемся на GPS
        ws.send_json({"type": "subscribe", "channel": "gps"})
        data = ws.receive_json()
        assert data["type"] == "subscribed"
        assert data["channel"] == "gps"


def test_websocket_invalid_token(client):
    """Тест подключения с неверным токеном."""
    with pytest.raises(Exception):
        # WebSocket должен закрыться с кодом 4001
        with client.websocket_connect("/api/v1/ws?token=invalid") as ws:
            ws.receive_json()


def test_websocket_missing_token(client):
    """Тест подключения без токена."""
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.receive_json()


# Нужен pytest.raises
import pytest