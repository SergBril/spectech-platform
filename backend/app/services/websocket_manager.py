# backend/app/services/websocket_manager.py
"""Менеджер WebSocket подключений с heartbeat и метриками."""

import logging
from datetime import UTC, datetime

from fastapi import WebSocket

logger = logging.getLogger("spectech.websocket")


class ConnectionManager:
    """
    Управляет WebSocket подключениями с группировкой по компании.
    """

    def __init__(self):
        self.company_connections: dict[int, set[WebSocket]] = {}
        self.user_connections: dict[int, WebSocket] = {}
        self.connection_meta: dict[WebSocket, dict] = {}
        # Метрики
        self._stats = {
            "total_connections_made": 0,
            "total_disconnections": 0,
            "total_messages_sent": 0,
            "total_broadcasts": 0,
        }

    async def connect(self, websocket: WebSocket, user_id: int, company_id: int):
        """Принимает подключение и регистрирует пользователя."""
        await websocket.accept()

        if company_id not in self.company_connections:
            self.company_connections[company_id] = set()
        self.company_connections[company_id].add(websocket)

        self.user_connections[user_id] = websocket

        self.connection_meta[websocket] = {
            "user_id": user_id,
            "company_id": company_id,
            "connected_at": datetime.now(UTC).isoformat(),
            "last_pong": datetime.now(UTC).isoformat(),
        }

        self._stats["total_connections_made"] += 1

        logger.info(
            "✅ WebSocket connected: user=%s, company=%s, total=%s",
            user_id,
            company_id,
            self.get_stats()["total_connections"],
        )

    def disconnect(self, websocket: WebSocket):
        """Удаляет подключение."""
        meta = self.connection_meta.pop(websocket, {})
        user_id = meta.get("user_id")
        company_id = meta.get("company_id")

        if company_id and company_id in self.company_connections:
            self.company_connections[company_id].discard(websocket)
            if not self.company_connections[company_id]:
                del self.company_connections[company_id]

        if user_id and self.user_connections.get(user_id) == websocket:
            del self.user_connections[user_id]

        self._stats["total_disconnections"] += 1

        logger.info(
            "❌ WebSocket disconnected: user=%s, company=%s", user_id, company_id
        )

    async def handle_ping(self, websocket: WebSocket):
        """Обработка ping от клиента — отправляем pong."""
        try:
            await websocket.send_json(
                {
                    "type": "pong",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            # Обновляем время последнего pong
            if websocket in self.connection_meta:
                self.connection_meta[websocket]["last_pong"] = datetime.now(
                    UTC
                ).isoformat()
            return True
        except Exception as e:
            logger.error("Failed to send pong: %s", e)
            return False

    async def send_personal(self, user_id: int, message: dict):
        """Отправляет сообщение конкретному пользователю."""
        websocket = self.user_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                self._stats["total_messages_sent"] += 1
                return True
            except Exception as e:
                logger.error("Failed to send to user %s: %s", user_id, e)
                self.disconnect(websocket)
                return False
        return False

    async def broadcast_to_company(self, company_id: int, message: dict):
        """Отправляет сообщение всем пользователям компании."""
        connections = self.company_connections.get(company_id, set()).copy()
        sent_count = 0
        failed = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                failed.append(websocket)
                logger.error("Failed to broadcast: %s", e)

        for ws in failed:
            self.disconnect(ws)

        self._stats["total_messages_sent"] += sent_count
        self._stats["total_broadcasts"] += 1

        logger.info(
            "📡 Broadcast to company %s: sent=%s, failed=%s",
            company_id,
            sent_count,
            len(failed),
        )
        return sent_count

    async def broadcast_gps_to_company(self, company_id: int, gps_data: dict) -> int:
        message = {
            "type": "gps_point",
            "data": gps_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return await self.broadcast_to_company(company_id, message)

    async def broadcast_alert_to_company(
        self, company_id: int, alert_data: dict
    ) -> int:
        message = {
            "type": "alert",
            "data": alert_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.info(
            "🚨 Broadcasting alert to company %s: %s",
            company_id,
            alert_data.get("title"),
        )
        return await self.broadcast_to_company(company_id, message)


async def broadcast_to_user(self, user_id: int, message: dict):
    """Отправляет сообщение конкретному пользователю через все его соединения."""
    user_connections = self.active_connections.get(user_id, [])
    for connection in user_connections:
        try:
            await connection.send_json(message)
            logger.info(f"📨 WebSocket message sent to user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send WebSocket to user {user_id}: {e}")

    async def broadcast_all(self, message: dict):
        total = 0
        for company_id in list(self.company_connections.keys()):
            total += await self.broadcast_to_company(company_id, message)
        return total

    def get_stats(self) -> dict:
        return {
            "total_connections": sum(
                len(conns) for conns in self.company_connections.values()
            ),
            "total_users": len(self.user_connections),
            "companies_online": len(self.company_connections),
            "connections_by_company": {
                company_id: len(conns)
                for company_id, conns in self.company_connections.items()
            },
            **self._stats,
        }


# Singleton
manager = ConnectionManager()
