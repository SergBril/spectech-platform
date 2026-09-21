"""Простой тест WebSocket чата."""
import asyncio
import json
import websockets


async def test_chat():
    # Получите актуальный токен через /api/v1/auth/login
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBzcGVjdGVjaC5kZXYiLCJleHAiOjE3OTAwNzA2NDcsImlhdCI6MTc4OTk4NDI0N30._QUyTr6yjcb4KHdju_XJNX95UvbTT97iBRvBw1WHoLA"
    chat_id = 1

    uri = f"ws://localhost:8000/api/v1/chat/ws/{chat_id}?token={token}"

    async with websockets.connect(uri) as ws:
        print("✅ WebSocket connected!")

        # Отправляем сообщение
        await ws.send(json.dumps({
            "type": "message",
            "content": "Привет из WebSocket! Это real-time!",
            "message_type": "text",
        }))
        print("📤 Message sent")

        # Получаем ответ
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            print(f"📥 Received: {data['type']}")
            if data['type'] == 'message':
                print(f"   Content: {data['data']['content']}")
        except asyncio.TimeoutError:
            print("⏰ No response received (timeout)")


if __name__ == "__main__":
    asyncio.run(test_chat())