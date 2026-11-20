"""PR-3: MAX-бот считает свободной технику со статусом 'free'.

Vehicle.status - строка без enum, default 'free' (catalog.py:107); telegram_bot
использует 'free' для свободной техники. Литерал 'available' не совпадал ни с
одним статусом -> бот показывал 0 свободной техники. send_message мокается
(внешняя отправка запрещена).
"""

import pytest


@pytest.fixture
def max_user(db_session, company, sample_user):
    sample_user.max_chat_id = "chat-123"
    db_session.commit()
    return sample_user


@pytest.fixture
def vehicles(db_session, company):
    from app.models.catalog import Vehicle

    free = Vehicle(
        name="Экскаватор Free",
        company_id=company.id,
        status="free",
        id_type="internal",
        id_value="MAX-FREE-1",
    )
    busy = Vehicle(
        name="Самосвал Busy",
        company_id=company.id,
        status="in_work",
        id_type="internal",
        id_value="MAX-BUSY-1",
    )
    db_session.add_all([free, busy])
    db_session.commit()
    return {"free": free, "busy": busy}


def _webhook(auth_client, text, secret="test-secret"):
    return auth_client.post(
        "/api/v1/shifts/max/webhook",
        headers={"X-Max-Bot-Api-Secret": secret},
        json={"type": "message", "payload": {"text": text, "chatId": "chat-123"}},
    )


@pytest.fixture
def capture_send(monkeypatch):
    from app.core.config import settings
    from app.services.max_messenger_service import max_messenger_service

    monkeypatch.setattr(settings, "MAX_WEBHOOK_SECRET", "test-secret")
    sent = []

    async def fake_send(chat_id, text, *args, **kwargs):
        sent.append(text)
        return True

    monkeypatch.setattr(max_messenger_service, "send_message", fake_send)
    return sent


def test_vehicles_command_lists_free_not_busy(
    auth_client, db_session, max_user, vehicles, capture_send
):
    r = _webhook(auth_client, "/vehicles")
    assert r.status_code == 200, r.text
    assert capture_send, "сообщение не отправлено"
    text = capture_send[-1]
    assert "Экскаватор Free" in text
    assert "Самосвал Busy" not in text


def test_status_command_counts_free(
    auth_client, db_session, max_user, vehicles, capture_send
):
    r = _webhook(auth_client, "/status")
    assert r.status_code == 200, r.text
    assert capture_send
    assert "Свободной техники: 1" in capture_send[-1]
