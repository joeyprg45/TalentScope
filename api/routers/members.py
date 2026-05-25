from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_cosmos
from api.schemas.members import Member, MemberDetail

router = APIRouter()


@router.get("", response_model=list[Member])
def list_members(skill: str | None = None, cosmos=Depends(get_cosmos)) -> list[dict]:
    items = list(cosmos.members.query_items(
        query=(
            "SELECT c.member_id, c.name, c.role, c.skills, "
            "c.years_experience, c.monthly_cost FROM c"
        ),
        enable_cross_partition_query=True,
    ))
    if skill:
        s = skill.lower()
        items = [m for m in items if any(s in x.lower() for x in m.get("skills", []))]
    return items


@router.get("/{member_id}", response_model=MemberDetail)
def get_member(member_id: str, cosmos=Depends(get_cosmos)) -> dict:
    items = list(cosmos.members.query_items(
        query="SELECT * FROM c WHERE c.member_id = @id",
        parameters=[{"name": "@id", "value": member_id}],
        enable_cross_partition_query=True,
    ))
    if not items:
        raise HTTPException(status_code=404, detail="Member not found")
    return items[0]
