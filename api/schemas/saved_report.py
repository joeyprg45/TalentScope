from __future__ import annotations

from pydantic import BaseModel


class ChatEntry(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class StoredReport(BaseModel):
    id: str
    type: str   # "assignment" | "skill"
    title: str
    markdown: str
    axis: str | None = None
    member_id: str | None = None
    project_id: str | None = None
    created_at: str
    updated_at: str
    chat_history: list[ChatEntry] = []


class ReportListItem(BaseModel):
    id: str
    type: str
    title: str
    markdown: str
    axis: str | None
    member_id: str | None
    project_id: str | None
    created_at: str
    updated_at: str


class TagReportRequest(BaseModel):
    member_id: str | None = None
    project_id: str | None = None
