"""Схемы для маркетплейса."""

from pydantic import BaseModel


class PublishRequestResponse(BaseModel):
    """Ответ при публикации заявки."""

    request_id: int
    is_published: bool
    published_at: str | None
    message: str
