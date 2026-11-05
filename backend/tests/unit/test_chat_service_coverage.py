"""Coverage tests for chat_service."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestSendChatMessage:
    """Cover send_chat_message (lines 12-end)."""

    def test_existing_room(self, mock_db):
        from app.services.chat_service import send_chat_message

        room = SimpleNamespace(id=10)
        SimpleNamespace(id=42, created_at=datetime.now(UTC))

        # scalar_one_or_none returns existing room
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = room
        mock_db.execute.return_value = exec_result

        # refresh sets id on message
        mock_db.refresh.side_effect = lambda m: setattr(m, "id", 42)

        # Capture added objects
        added = []
        mock_db.add.side_effect = lambda obj: added.append(obj)

        result = send_chat_message(mock_db, sender_id=1, recipient_id=2, text="Hello")

        assert result["message_id"] == 42
        assert result["room_id"] == 10
        assert result["message_type"] == "text"
        # Only message added (room already exists)
        assert len(added) == 1
        mock_db.commit.assert_called_once()

    def test_new_room_created(self, mock_db):
        from app.services.chat_service import send_chat_message

        SimpleNamespace(id=99, created_at=datetime.now(UTC))

        # scalar_one_or_none returns None -> new room created
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = exec_result

        # After flush, room gets id=5
        new_room = None

        def capture_add(obj):
            nonlocal new_room
            if hasattr(obj, "request_id"):
                new_room = obj
                obj.id = 5
            elif hasattr(obj, "chat_id"):
                obj.id = 99

        mock_db.add.side_effect = capture_add
        mock_db.refresh.side_effect = lambda m: setattr(m, "id", 99)

        result = send_chat_message(
            mock_db,
            sender_id=1,
            recipient_id=2,
            text="Hi",
            shift_task_id=7,
        )

        assert result["room_id"] == 5
        assert result["message_id"] == 99
        # Both room and message added
        assert mock_db.add.call_count == 2
        mock_db.flush.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_with_file_and_attachments(self, mock_db):
        from app.services.chat_service import send_chat_message

        room = SimpleNamespace(id=10)
        SimpleNamespace(id=50, created_at=datetime.now(UTC))

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = room
        mock_db.execute.return_value = exec_result
        mock_db.refresh.side_effect = lambda m: None
        mock_db.add.side_effect = lambda obj: None

        result = send_chat_message(
            mock_db,
            sender_id=1,
            recipient_id=2,
            text="Photo",
            message_type="image",
            file_url="https://example.com/photo.jpg",
            attachments={"filename": "photo.jpg"},
        )

        assert result["message_type"] == "image"
        assert result["file_url"] == "https://example.com/photo.jpg"

    def test_shift_task_id_zero_fallback(self, mock_db):
        from app.services.chat_service import send_chat_message

        room = SimpleNamespace(id=1)
        SimpleNamespace(id=1, created_at=datetime.now(UTC))

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = room
        mock_db.execute.return_value = exec_result
        mock_db.refresh.side_effect = lambda m: setattr(m, "id", 1)
        mock_db.add.side_effect = lambda obj: None

        result = send_chat_message(
            mock_db,
            sender_id=1,
            recipient_id=2,
            text="Test",
            shift_task_id=None,
        )

        assert result["message_id"] == 1
