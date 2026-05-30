from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents.cosmos_client import get_active_constraints, get_qualitative_memory
from agents.orchestrator import AgentMode
from api.deps import get_cosmos, get_orchestrator
from api.schemas.reports import (
    AssignmentRequest,
    RefineRequest,
    RefineResponse,
    ReportResponse,
    SkillAnalysisRequest,
)
from api.schemas.saved_report import ReportListItem, StoredReport, TagReportRequest
from api.services.report_store import (
    delete_report,
    get_report,
    list_reports,
    tag_report,
)

router = APIRouter()


# ── 既存: レポート生成 (チャット経由とは別の直接API) ──────────────────────────

@router.post("/skill-analysis", response_model=ReportResponse)
async def skill_analysis(
    req: SkillAnalysisRequest,
    orch=Depends(get_orchestrator),
    cosmos=Depends(get_cosmos),
) -> ReportResponse:
    summary, full_md = await orch.generate_report(
        mode=AgentMode.SKILL_ANALYSIS,
        target_id=req.member_id,
        target_name=req.member_name,
        constraints=get_active_constraints(cosmos),
        qualitative=get_qualitative_memory(cosmos),
    )
    return ReportResponse(summary=summary, markdown=full_md)


@router.post("/assignment", response_model=ReportResponse)
async def assignment(
    req: AssignmentRequest,
    orch=Depends(get_orchestrator),
    cosmos=Depends(get_cosmos),
) -> ReportResponse:
    summary, full_md = await orch.generate_report(
        mode=AgentMode.ASSIGNMENT,
        target_id=req.project_id,
        target_name=req.project_name,
        constraints=get_active_constraints(cosmos),
        qualitative=get_qualitative_memory(cosmos),
    )
    return ReportResponse(summary=summary, markdown=full_md)


@router.post("/refine", response_model=RefineResponse)
async def refine(
    req: RefineRequest,
    orch=Depends(get_orchestrator),
    cosmos=Depends(get_cosmos),
) -> RefineResponse:
    try:
        mode = AgentMode(req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}") from exc

    summary, full_md = await orch.refine_report(
        mode=mode,
        target_id=req.target_id,
        target_name=req.target_name,
        current_report_md=req.current_report_md,
        user_feedback=req.user_feedback,
        constraints=get_active_constraints(cosmos),
        qualitative=get_qualitative_memory(cosmos),
    )
    return RefineResponse(change_summary=summary, markdown=full_md)


# ── 新規: CosmosDB 永続化 CRUD ──────────────────────────────────────────────

@router.get("", response_model=list[ReportListItem])
async def get_reports(cosmos=Depends(get_cosmos)) -> list[ReportListItem]:
    return await list_reports(cosmos.reports)


@router.get("/{report_id}", response_model=StoredReport)
async def get_report_by_id(report_id: str, cosmos=Depends(get_cosmos)) -> StoredReport:
    doc = await get_report(cosmos.reports, report_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return doc


@router.patch("/{report_id}/tag", response_model=StoredReport)
async def tag_report_endpoint(
    report_id: str, req: TagReportRequest, cosmos=Depends(get_cosmos)
) -> StoredReport:
    doc = await tag_report(cosmos.reports, report_id, member_id=req.member_id, project_id=req.project_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return doc


@router.delete("/{report_id}", status_code=204)
async def delete_report_endpoint(report_id: str, cosmos=Depends(get_cosmos)) -> None:
    deleted = await delete_report(cosmos.reports, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
