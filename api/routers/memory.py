from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.cosmos_client import (
    delete_constraint,
    get_all_constraints,
    get_qualitative_memory,
    get_unprocessed_sessions_count,
    upsert_constraint,
    upsert_qualitative_memory,
    update_constraint_status,
)
from api.deps import get_cosmos, get_settings
from api.services.memory_extraction import run_extraction_pipeline

router = APIRouter()


# ── スキーマ ──────────────────────────────────────────────────────────────────

class ExtractionResult(BaseModel):
    processed: int
    constraints_found: int
    qualitative_updated: bool


class ConstraintCreate(BaseModel):
    content: str
    related_member_ids: list[str] = []


class ConstraintStatusUpdate(BaseModel):
    status: str  # "active" | "pending" | "dismissed"


class QualitativeUpdate(BaseModel):
    content: str


# ── 未処理件数 ─────────────────────────────────────────────────────────────────

@router.get("/unprocessed_count")
async def get_unprocessed_count(cosmos=Depends(get_cosmos)) -> dict:
    count = get_unprocessed_sessions_count(cosmos)
    return {"count": count}


# ── 抽出実行 ───────────────────────────────────────────────────────────────────

@router.post("/extract", response_model=ExtractionResult)
async def extract_memory(
    cosmos=Depends(get_cosmos),
    settings=Depends(get_settings),
) -> ExtractionResult:
    result = await run_extraction_pipeline(cosmos, settings)
    return ExtractionResult(**result)


# ── 絶対条件 CRUD ──────────────────────────────────────────────────────────────

@router.get("/constraints")
async def list_constraints(cosmos=Depends(get_cosmos)) -> list[dict]:
    return get_all_constraints(cosmos)


@router.post("/constraints", status_code=201)
async def create_constraint(
    req: ConstraintCreate,
    cosmos=Depends(get_cosmos),
) -> dict:
    return upsert_constraint(
        cosmos,
        content=req.content,
        related_member_ids=req.related_member_ids,
        status="active",
        source="manual",
    )


@router.patch("/constraints/{constraint_id}")
async def update_constraint(
    constraint_id: str,
    req: ConstraintStatusUpdate,
    cosmos=Depends(get_cosmos),
) -> dict:
    ok = update_constraint_status(cosmos, constraint_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Constraint not found")
    return {"id": constraint_id, "status": req.status}


@router.delete("/constraints/{constraint_id}", status_code=204)
async def remove_constraint(
    constraint_id: str,
    cosmos=Depends(get_cosmos),
) -> None:
    ok = delete_constraint(cosmos, constraint_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Constraint not found")


# ── 定性テキスト ───────────────────────────────────────────────────────────────

@router.get("/qualitative")
async def get_qualitative(cosmos=Depends(get_cosmos)) -> dict:
    content = get_qualitative_memory(cosmos)
    return {"content": content}


@router.put("/qualitative")
async def update_qualitative(
    req: QualitativeUpdate,
    cosmos=Depends(get_cosmos),
) -> dict:
    doc = upsert_qualitative_memory(cosmos, req.content)
    return doc
