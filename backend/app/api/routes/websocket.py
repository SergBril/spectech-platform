"""WebSocket endpoints для real-time коммуникации."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.websocket_auth import verify_ws_token
from app.services.websocket_manager import manager

logger = logging.getLogger("spectech.ws.routes")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint с аутентификацией."""
    logger.info("🔌 WebSocket connection attempt, token present: %s", bool(token))

    # Аутентификация
    user_data = await verify_ws_token(token)
    if not user_data:
        logger.warning("❌ WebSocket: invalid token")
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user_data.get("user_id")
    company_id = user_data.get("company_id", 0)
    logger.info("✅ WebSocket auth OK: user_id=%s, company_id=%s", user_id, company_id)

    await manager.connect(websocket, user_id, company_id)

    try:
        # Отправляем приветственное сообщение
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

            # Обработка ping
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
