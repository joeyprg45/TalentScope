from __future__ import annotations

from pydantic import BaseModel


class ChatSessionMessage(BaseModel):
    role: str
    content: str


class ChatSession(BaseModel):
    id: str
    title: str
    display_messages: list[ChatSessionMessage]
    sk_history: list[ChatSessionMessage]
    current_report_id: str | None = None
    current_axis: str = "ability"
    trace_log: list[dict] = []
    created_at: str
    updated_at: str


class ChatSessionListItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
