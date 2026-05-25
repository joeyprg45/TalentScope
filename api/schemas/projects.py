from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Period(BaseModel):
    start: str
    end: str


class Assignment(BaseModel):
    model_config = ConfigDict(extra="allow")

    member_id: str
    role: str | None = None
    start: str | None = None
    end: str | None = None


class Project(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_id: str
    name: str
    status: str | None = None
    period: Period | None = None
    assignments: list[Assignment] = []
    required_skills: list[str] = []


class ProjectDetail(Project):
    required_skills: list[str] = []
    member_ids: list[str] = []
    overview: str | None = None
    assignments: list[Assignment] = []
    tasks: list[dict] = []
