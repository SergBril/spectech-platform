"""Модели для чата по заявке."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class RequestChat(Base):
    """Чат по заявке — один чат на одну заявку."""

    __tablename__ = "request_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships (только к своим детям, БЕЗ связи с Request)
    messages = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    participants = relationship(
        "ChatParticipant",
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    """Сообщение в чате."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("request_chats.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    sender_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )
    message_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text"
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id"), nullable=True
    )
    mentions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_read_by: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chat = relationship("RequestChat", back_populates="messages")


class ChatParticipant(Base):
    """Участник чата."""

    __tablename__ = "chat_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("request_chats.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    chat = relationship("RequestChat", back_populates="participants")