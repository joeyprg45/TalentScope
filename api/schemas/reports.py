from __future__ import annotations

from pydantic import BaseModel


class SkillAnalysisRequest(BaseModel):
    member_id: str
    member_name: str


class AssignmentRequest(BaseModel):
    project_id: str
    project_name: str
    axis: str = "ability"  # ability | cost | growth | synergy


class RefineRequest(BaseModel):
    mode: str  # "SKILL_ANALYSIS" | "ASSIGNMENT"
    target_id: str
    target_name: str
    axis: str
    current_report_md: str
    user_feedback: str


class ReportResponse(BaseModel):
    summary: str
    markdown: str


class RefineResponse(BaseModel):
    change_summary: str
    markdown: str
