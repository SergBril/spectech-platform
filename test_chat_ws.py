"""Простой тест WebSocket чата."""

import asyncio
import json
import os
import urllib.request

import websockets

API_BASE = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
WS_BASE = os.environ.get("WS_BASE", "ws://localhost:8000")


def _get_token() -> str:
    """Fetch a fresh JWT via login. Never hardcode tokens in the repo."""
    token = os.environ.get("TEST_TOKEN")
    if token:
        return token
    password = os.environ.get("TEST_PASSWORD")
    if not password:
        raise SystemExit(
            "Set TEST_PASSWORD (or TEST_TOKEN) env var before running this script."
        )
    email = os.environ.get("TEST_EMAIL", "admin@spectech.dev")
    req = urllib.request.Request(
        f"{API_BASE}/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


async def test_chat():
    token = _get_token()
    chat_id = 1

    uri = f"{WS_BASE}/api/v1/chat/ws/{chat_id}?token={token}"

    async with websockets.connect(uri) as ws:
        print("✅ WebSocket connected!")

        # Отправляем сообщение
        await ws.send(
            json.dumps(
                {
                    "type": "message",
                    "content": "Привет из WebSocket! Это real-time!",
                    "message_type": "text",
                }
            )
        )
        print("📤 Message sent")

        # Получаем ответ
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            print(f"📥 Received: {data['type']}")
            if data["type"] == "message":
                print(f"   Content: {data['data']['content']}")
        except asyncio.TimeoutError:
            print("⏰ No response received (timeout)")


if __name__ == "__main__":
    asyncio.run(test_chat())
