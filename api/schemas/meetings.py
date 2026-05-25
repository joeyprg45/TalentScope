from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Meeting(BaseModel):
    model_config = ConfigDict(extra="allow")

    meeting_id: str | None = None
    title: str | None = None
    date: str | None = None
    meeting_type: str | None = None
    project_id: str | None = None
    participants: list[str] = []
    overall_summary: str | None = None
