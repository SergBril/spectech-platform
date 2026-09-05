"""WebSocket endpoints для real-time коммуникации."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.websocket_auth import verify_ws_token
from app.core.db import SessionLocal
from app.services.websocket_manager import manager

logger = logging.getLogger("spectech.ws.routes")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
):
    """
    Основной WebSocket endpoint.

    Клиент подключается: ws://localhost:8000/api/v1/ws?token=<JWT>
    """
    logger.info("🔌 WebSocket connection attempt, token present: %s", bool(token))

    # Аутентификация через query параметр
    if not token:
        logger.warning("❌ WebSocket: missing token")
        await websocket.close(code=4001, reason="Missing token")
        return

    db = SessionLocal()
    user = None
    connected = False

    try:
        logger.info("🔐 Verifying token...")
        user = verify_ws_token(token, db)
        if not user:
            logger.warning("❌ WebSocket: invalid token")
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_id = user.id
        company_id = user.company_id or 0
        logger.info(
            "✅ WebSocket auth OK: user_id=%s, company_id=%s", user_id, company_id
        )

        # Подключаем пользователя
        await manager.connect(
            websocket,
            user_id=user_id,
            company_id=company_id,
        )
        connected = True
        logger.info("✅ WebSocket connected and registered")

        # Отправляем приветственное сообщение
        await websocket.send_json(
            {
                "type": "connected",
                "user_id": user_id,
                "email": user.email,
                "company_id": company_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "Welcome to SpectechPlatform WebSocket!",
            }
        )
        logger.info("✅ Welcome message sent")

        # Основной цикл обработки сообщений
        while True:
            data = await websocket.receive_json()
            await _handle_message(websocket, user, data, db)

    except WebSocketDisconnect:
        username = user.id if user else "unknown"
        logger.info("👋 Client disconnected: user=%s", username)
    except Exception as e:
        logger.error("❌ WebSocket error: %s: %s", type(e).__name__, e, exc_info=True)
        # Пытаемся отправить ошибку клиенту, если соединение ещё открыто
        if connected and user:
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
            except Exception:
                pass
    finally:
        # Безопасная очистка
        try:
            if connected:
                manager.disconnect(websocket)
        except Exception as cleanup_error:
            logger.warning("Cleanup error: %s", cleanup_error)
        finally:
            db.close()


async def _handle_message(websocket: WebSocket, user, data: dict, db: Session):
    """Обрабатывает входящие сообщения от клиента."""
    msg_type = data.get("type")

    if msg_type == "ping":
        # Простой ping-pong для проверки связи
        await websocket.send_json(
            {
                "type": "pong",
                "timestamp": datetime.now(UTC).isoformat(),
                "server_time": datetime.now(UTC).isoformat(),
            }
        )

    elif msg_type == "subscribe":
        # Подписка на канал (gps, alerts, requests)
        channel = data.get("channel")
        if channel in ("gps", "alerts", "requests", "all"):
            await websocket.send_json(
                {
                    "type": "subscribed",
                    "channel": channel,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Unknown channel: {channel}",
                }
            )

    elif msg_type == "unsubscribe":
        channel = data.get("channel")
        await websocket.send_json(
            {
                "type": "unsubscribed",
                "channel": channel,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    elif msg_type == "stats":
        # Запрос статистики подключений (только для админов)
        if user.is_superuser:
            stats = manager.get_stats()
            await websocket.send_json(
                {
                    "type": "stats",
                    "data": stats,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Admin access required",
                }
            )

    else:
        await websocket.send_json(
            {
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            }
        )


@router.get("/ws/stats")
def websocket_stats(current_user=Depends()):
    """
    HTTP endpoint для получения статистики WebSocket подключений.
    Временно без авторизации для простоты.
    """
    return manager.get_stats()
