from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from api.deps import get_cosmos
from api.schemas.chat_session import ChatSessionListItem

router = APIRouter()


@router.get("/sessions", response_model=list[ChatSessionListItem])
async def list_chat_sessions() -> list[ChatSessionListItem]:
    cosmos = get_cosmos()
    query = (
        "SELECT c.id, c.title, c.created_at, c.updated_at FROM c ORDER BY c.updated_at DESC"
    )
    items = list(cosmos.chat_sessions.query_items(query=query, enable_cross_partition_query=True))
    return [ChatSessionListItem(**item) for item in items]


@router.delete("/sessions/{chat_id}", status_code=204)
async def delete_chat_session(chat_id: str) -> Response:
    cosmos = get_cosmos()
    try:
        cosmos.chat_sessions.delete_item(item=chat_id, partition_key=chat_id)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@router.get("/sessions/{chat_id}/trace")
async def get_chat_trace(chat_id: str) -> list[dict]:
    cosmos = get_cosmos()
    try:
        doc = cosmos.chat_sessions.read_item(item=chat_id, partition_key=chat_id)
        return doc.get("trace_log", [])
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Session not found")
