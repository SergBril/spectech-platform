"""Менеджер WebSocket подключений."""
import logging
from datetime import datetime, timezone
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("spectech.websocket")


class ConnectionManager:
    """
    Управляет WebSocket подключениями с группировкой по компании.
    
    Структура:
    - self.company_connections: dict[company_id -> set[websocket]]
    - self.user_connections: dict[user_id -> websocket]
    """

    def __init__(self):
        # company_id -> множество активных подключений
        self.company_connections: Dict[int, Set[WebSocket]] = {}
        # user_id -> websocket (последнее подключение пользователя)
        self.user_connections: Dict[int, WebSocket] = {}
        # websocket -> метаинформация
        self.connection_meta: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, user_id: int, company_id: int):
        """Принимает подключение и регистрирует пользователя."""
        await websocket.accept()
        
        # Регистрируем в company группу
        if company_id not in self.company_connections:
            self.company_connections[company_id] = set()
        self.company_connections[company_id].add(websocket)
        
        # Сохраняем последнее подключение пользователя (не закрывая старые)
        self.user_connections[user_id] = websocket
        
        # Сохраняем метаданные
        self.connection_meta[websocket] = {
            "user_id": user_id,
            "company_id": company_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.info(
            "WebSocket connected: user=%s, company=%s, total_company=%s",
            user_id, company_id, len(self.company_connections.get(company_id, set()))
        )

    def disconnect(self, websocket: WebSocket):
        """Удаляет подключение."""
        meta = self.connection_meta.pop(websocket, {})
        user_id = meta.get("user_id")
        company_id = meta.get("company_id")
        
        # Удаляем из company группы
        if company_id and company_id in self.company_connections:
            self.company_connections[company_id].discard(websocket)
            if not self.company_connections[company_id]:
                del self.company_connections[company_id]
        
        # Удаляем из user connections
        if user_id and self.user_connections.get(user_id) == websocket:
            del self.user_connections[user_id]
        
        logger.info("WebSocket disconnected: user=%s, company=%s", user_id, company_id)

    async def send_personal(self, user_id: int, message: dict):
        """Отправляет сообщение конкретному пользователю."""
        websocket = self.user_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error("Failed to send to user %s: %s", user_id, e)
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
        
        # Удаляем нерабочие подключения
        for ws in failed:
            self.disconnect(ws)
        
        logger.info(
            "Broadcast to company %s: sent=%s, failed=%s",
            company_id, sent_count, len(failed)
        )
        return sent_count

    async def broadcast_gps_to_company(self, company_id: int, gps_data: dict) -> int:
        """
        Отправляет GPS точку всем подписчикам компании на канал 'gps'.
        
        Args:
            company_id: ID компании
            gps_data: Данные GPS точки (vehicle_id, lat, lon, speed, ...)
        
        Returns:
            Количество получателей
        """
        message = {
            "type": "gps_point",
            "data": gps_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.broadcast_to_company(company_id, message)

    async def broadcast_all(self, message: dict):
        """Отправляет сообщение всем подключённым пользователям."""
        total = 0
        for company_id in list(self.company_connections.keys()):
            total += await self.broadcast_to_company(company_id, message)
        return total

    def get_stats(self) -> dict:
        """Статистика подключений."""
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
        }


# Глобальный singleton менеджер
manager = ConnectionManager()