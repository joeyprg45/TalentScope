from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_cosmos
from api.schemas.meetings import Meeting

router = APIRouter()


@router.get("", response_model=list[Meeting])
def list_meetings(
    member_id: str | None = None,
    project_id: str | None = None,
    cosmos=Depends(get_cosmos),
) -> list[dict]:
    items = list(cosmos.meetings.query_items(
        query=(
            "SELECT c.meeting_id, c.title, c.date, c.meeting_type, "
            "c.project_id, c.participants, c.overall_summary "
            "FROM c WHERE c.type = 'meeting_chunk' AND c.chunk_index = 0"
        ),
        enable_cross_partition_query=True,
    ))
    if project_id:
        items = [m for m in items if m.get("project_id") == project_id]
    if member_id:
        items = [m for m in items if member_id in (m.get("participants") or [])]
    return items
