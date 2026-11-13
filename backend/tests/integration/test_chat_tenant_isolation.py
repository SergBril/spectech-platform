"""Кросс-тенант изоляция чата заявки: REST (5 эндпоинтов) + WebSocket.

Две реальные компании, реальные заявки и чат компании B с участником B.
Пользователь A не может читать/писать чужой чат и не добавляется в участники.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models.auth import User
from app.models.chat import ChatMessage, ChatParticipant, RequestChat
from app.models.company import Company
from app.models.dispatch import Request

pytestmark = [pytest.mark.integration]


@pytest.fixture
def second_company(db_session: Session) -> Company:
    company = Company(
        name="Chat Other Company",
        legal_name="ООО Другая Компания",
        inn="9999999993",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def other_user(db_session: Session, second_company: Company) -> User:
    user = User(
        email="chat-other@test.com",
        full_name="Chat Other User",
        password_hash="hashed_password",
        company_id=second_company.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _request(company_id: int) -> Request:
    return Request(
        company_id=company_id,
        status="new",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(days=1),
    )


@pytest.fixture
def request_a(db_session: Session, company: Company) -> Request:
    req = _request(company.id)
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)
    return req


@pytest.fixture
def request_b(db_session: Session, second_company: Company) -> Request:
    req = _request(second_company.id)
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)
    return req


@pytest.fixture
def chat_b(db_session: Session, request_b: Request, other_user: User) -> RequestChat:
    chat = RequestChat(request_id=request_b.id, created_at=datetime.now(UTC))
    db_session.add(chat)
    db_session.flush()
    db_session.add(
        ChatParticipant(
            chat_id=chat.id,
            user_id=other_user.id,
            role="client",
            joined_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    db_session.refresh(chat)
    return chat


class TestChatTenantIsolation:
    def test_get_chat_foreign_404_and_no_join(
        self,
        client: TestClient,
        auth_headers: dict,
        request_b: Request,
        chat_b: RequestChat,
        admin_user: User,
        db_session: Session,
    ):
        resp = client.get(f"/api/v1/chat/requests/{request_b.id}", headers=auth_headers)
        assert resp.status_code == 404
        # DB-факт: пользователь A НЕ добавлен в участники чужого чата
        db_session.expire_all()
        joined = (
            db_session.query(ChatParticipant)
            .filter(
                ChatParticipant.chat_id == chat_b.id,
                ChatParticipant.user_id == admin_user.id,
            )
            .count()
        )
        assert joined == 0

    def test_messages_foreign_404(
        self, client: TestClient, auth_headers: dict, request_b: Request
    ):
        resp = client.get(
            f"/api/v1/chat/requests/{request_b.id}/messages", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_send_message_foreign_404_and_no_message(
        self,
        client: TestClient,
        auth_headers: dict,
        request_b: Request,
        chat_b: RequestChat,
        db_session: Session,
    ):
        resp = client.post(
            f"/api/v1/chat/requests/{request_b.id}/messages",
            json={"content": "foreign write"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        db_session.expire_all()
        assert (
            db_session.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_b.id)
            .count()
            == 0
        )

    def test_upload_foreign_404(
        self, client: TestClient, auth_headers: dict, request_b: Request
    ):
        resp = client.post(
            f"/api/v1/chat/requests/{request_b.id}/upload",
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_ws_foreign_closes_4003(
        self,
        client: TestClient,
        auth_token: str,
        chat_b: RequestChat,
    ):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/api/v1/chat/ws/{chat_b.id}?token={auth_token}"
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4003


class TestChatOwnAccess:
    def test_get_own_chat_200_and_join(
        self,
        client: TestClient,
        auth_headers: dict,
        request_a: Request,
        admin_user: User,
        db_session: Session,
    ):
        resp = client.get(f"/api/v1/chat/requests/{request_a.id}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["id"]
        # DB-факт: авто-join в чат СВОЕЙ компании работает
        db_session.expire_all()
        joined = (
            db_session.query(ChatParticipant)
            .filter(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id == admin_user.id,
            )
            .count()
        )
        assert joined == 1

    def test_ws_own_connects(
        self,
        client: TestClient,
        auth_headers: dict,
        auth_token: str,
        request_a: Request,
    ):
        resp = client.get(f"/api/v1/chat/requests/{request_a.id}", headers=auth_headers)
        assert resp.status_code == 200
        chat_id = resp.json()["id"]
        with client.websocket_connect(
            f"/api/v1/chat/ws/{chat_id}?token={auth_token}"
        ) as websocket:
            data = websocket.receive_json()
            assert data["type"] == "message"
            assert data["data"]["message_type"] == "system_event"
