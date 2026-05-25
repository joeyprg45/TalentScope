from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Member(BaseModel):
    model_config = ConfigDict(extra="allow")

    member_id: str
    name: str
    role: str | None = None
    skills: list[str] = []
    years_experience: int | None = None
    monthly_cost: int | None = None


class MemberDetail(Member):
    """すべての追加フィールド (slack_vlog 等) は extra で吸収."""
