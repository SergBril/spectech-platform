"""WebSocket endpoints для real-time коммуникации."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_user
from app.core.ws_tickets import TICKET_TTL_SECONDS, consume_ticket, issue_ticket
from app.models.auth import User, UserStatus
from app.services.websocket_manager import manager

logger = logging.getLogger("spectech.ws.routes")

router = APIRouter()


@router.post("/ws/ticket")
async def create_ws_ticket(current_user: User = Depends(get_current_user)):
    """Одноразовый ticket (60 с) для WS-подключения вместо сессионного JWT в URL.

    Браузерный WebSocket не умеет заголовки, но долгоживущий JWT в query
    утекает в логи nginx, историю браузера и Referer. Redis обязателен:
    недоступен — 503, без in-memory fallback (одноразовость между воркерами).
    """
    try:
        ticket = await issue_ticket(current_user.id)
    except Exception as e:
        logger.error("WS ticket: Redis недоступен: %s", e)
        raise HTTPException(status_code=503, detail="Ticket service unavailable")
    return {"ticket": ticket, "expires_in": TICKET_TTL_SECONDS}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, ticket: str | None = None, token: str | None = None
):
    """WebSocket endpoint с аутентификацией по одноразовому ticket."""
    from app.core.db import SessionLocal

    # Сессионный JWT в URL больше не принимается (намеренный breaking change):
    # клиент один, вечный токен в query оставлять нельзя
    if token is not None:
        logger.warning("❌ WebSocket: ?token= больше не поддерживается")
        await websocket.close(code=4003, reason="Use /ws/ticket instead of ?token=")
        return

    if not ticket:
        await websocket.close(code=4001, reason="Ticket required")
        return

    try:
        user_id = await consume_ticket(ticket)
    except Exception as e:
        logger.error("WS ticket: Redis недоступен: %s", e)
        await websocket.close(code=4002, reason="Ticket service unavailable")
        return

    if user_id is None:
        logger.warning("❌ WebSocket: невалидный/просроченный/повторный ticket")
        await websocket.close(code=4001, reason="Invalid or expired ticket")
        return

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
    finally:
        db.close()

    if not user or user.status != UserStatus.active:
        logger.warning("❌ WebSocket: пользователь не найден/неактивен")
        await websocket.close(code=4001, reason="User not found or inactive")
        return

    company_id = getattr(user, "company_id", 0) or 0
    logger.info("✅ WebSocket auth OK: user_id=%s, company_id=%s", user_id, company_id)

    await manager.connect(websocket, user_id, company_id)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "user_id": user_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "Welcome to SpectechPlatform WebSocket!",
            }
        )

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

    except WebSocketDisconnect as e:
        logger.info(f"WebSocket disconnect: code={e.code}, reason={e.reason}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            manager.disconnect(websocket)
        except Exception:
            pass
