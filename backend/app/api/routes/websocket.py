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
    from app.core.db import SessionLocal

    logger.info("🔌 WebSocket connection attempt, token present: %s", bool(token))

    # Создаём сессию БД для проверки токена
    db = SessionLocal()
    try:
        # ⚠️ ВАЖНО: verify_ws_token — СИНХРОННАЯ функция (def, не async def)
        # УБИРАЕМ await!
        user = verify_ws_token(token, db)
    finally:
        db.close()

    if not user:
        logger.warning("❌ WebSocket: invalid token")
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user.id
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
