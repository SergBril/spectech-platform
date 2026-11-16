"""
WebSocket Connection Manager.

Поддерживает два режима:
1. GPS/Telemetry: connect(websocket, user_id, company_id)
2. Чаты: connect_chat(websocket, chat_id)
"""

import logging

from fastapi import WebSocket

logger = logging.getLogger("spectech.ws_manager")


class ConnectionManager:
    """Менеджер WebSocket подключений (мульти-режимный)."""

    def __init__(self):
        # === GPS/Telemetry (старый режим) ===
        # user_id -> websocket
        self.user_connections: dict[int, WebSocket] = {}
        # company_id -> set of user_ids
        self.company_users: dict[int, set[int]] = {}

        # === Чаты (новый режим) ===
        # chat_id -> список websocket
        self.chat_connections: dict[int, list[WebSocket]] = {}

    # ============================================================
    # GPS/Telemetry методы (для существующего websocket.py)
    # ============================================================

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        company_id: int | list[int] = 0,
    ):
        """Подключение для GPS/телеметрии.

        company_id может быть списком: пользователь с несколькими юрлицами
        подписывается на все доступные ему компании.
        """
        await websocket.accept()
        self.user_connections[user_id] = websocket
        ids = [company_id] if isinstance(company_id, int) else list(company_id)
        for cid in ids:
            if cid:
                self.company_users.setdefault(cid, set()).add(user_id)
        logger.info("GPS WS connected: user=%s, companies=%s", user_id, ids)

    def disconnect(self, websocket: WebSocket):
        """Отключение GPS/телеметрии (старый API)."""
        # Найти user_id по websocket
        user_to_remove = None
        company_to_update = None

        for uid, ws in list(self.user_connections.items()):
            if ws == websocket:
                user_to_remove = uid
                break

        if user_to_remove:
            del self.user_connections[user_to_remove]
            # Удалить из company_users
            # Снять подписку со ВСЕХ компаний, иначе после переподключения
            # останутся висячие подписки и утечка вернётся.
            removed_from = []
            for cid, users in list(self.company_users.items()):
                if user_to_remove in users:
                    users.discard(user_to_remove)
                    removed_from.append(cid)
                    if not users:
                        del self.company_users[cid]
            company_to_update = removed_from
            logger.info(
                "GPS WS disconnected: user=%s, company=%s",
                user_to_remove,
                company_to_update,
            )

    async def send_to_user(self, user_id: int, message: dict):
        """Отправить сообщение конкретному пользователю (GPS)."""
        ws = self.user_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Failed to send to user %s: %s", user_id, e)

    async def broadcast_to_user(self, user_id: int, message: dict):
        """Отправить сообщение конкретному пользователю."""
        await self.send_to_user(user_id, message)

    async def broadcast_to_company(self, company_id: int, message: dict):
        """Отправить всем пользователям компании (GPS)."""
        user_ids = self.company_users.get(company_id, set())
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    # ============================================================
    # Chat методы (новый API для чатов)
    # ============================================================

    async def connect_chat(self, websocket: WebSocket, chat_id: int):
        """Подключение к чату."""
        await websocket.accept()
        if chat_id not in self.chat_connections:
            self.chat_connections[chat_id] = []
        self.chat_connections[chat_id].append(websocket)
        logger.info(
            "Chat WS connected: chat=%s, total=%d",
            chat_id,
            len(self.chat_connections[chat_id]),
        )

    async def broadcast_positions(self, positions: list[dict], company_id: int = 0):
        """Отправить позиции только подписчикам указанной компании.

        company_id=0 не означает "всем": без компании получателей нет.
        Координаты, скорость и топливо - операционные данные юрлица, и
        конкурирующая компания не должна их видеть.
        """
        import json

        if not company_id:
            logger.warning(
                "GPS broadcast without company_id: %d positions dropped", len(positions)
            )
            return

        message = json.dumps({"type": "gps_positions", "positions": positions})
        disconnected = []
        for uid in list(self.company_users.get(company_id, set())):
            ws = self.user_connections.get(uid)
            if ws is None:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(uid)
        for uid in disconnected:
            self.user_connections.pop(uid, None)
            for users in self.company_users.values():
                users.discard(uid)

    def disconnect_chat(self, websocket: WebSocket, chat_id: int):
        """Отключение от чата."""
        if chat_id in self.chat_connections:
            self.chat_connections[chat_id] = [
                c for c in self.chat_connections[chat_id] if c != websocket
            ]
            if not self.chat_connections[chat_id]:
                del self.chat_connections[chat_id]
            logger.info("Chat WS disconnected: chat=%s", chat_id)

    async def broadcast_to_chat(self, chat_id: int, message: dict):
        """Отправить всем участникам чата."""
        if chat_id not in self.chat_connections:
            return
        disconnected = []
        for conn in self.chat_connections[chat_id]:
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.warning("Failed to send to chat %s: %s", chat_id, e)
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect_chat(conn, chat_id)


# Глобальный экземпляр
manager = ConnectionManager()
