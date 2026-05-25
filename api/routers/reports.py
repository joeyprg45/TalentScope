from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents.orchestrator import AgentMode
from api.deps import get_orchestrator
from api.schemas.reports import (
    AssignmentRequest,
    RefineRequest,
    RefineResponse,
    ReportResponse,
    SkillAnalysisRequest,
)

router = APIRouter()


@router.post("/skill-analysis", response_model=ReportResponse)
async def skill_analysis(req: SkillAnalysisRequest, orch=Depends(get_orchestrator)) -> ReportResponse:
    summary, full_md = await orch.generate_report(
        mode=AgentMode.SKILL_ANALYSIS,
        target_id=req.member_id,
        target_name=req.member_name,
        axis="ability",
    )
    return ReportResponse(summary=summary, markdown=full_md)


@router.post("/assignment", response_model=ReportResponse)
async def assignment(req: AssignmentRequest, orch=Depends(get_orchestrator)) -> ReportResponse:
    summary, full_md = await orch.generate_report(
        mode=AgentMode.ASSIGNMENT,
        target_id=req.project_id,
        target_name=req.project_name,
        axis=req.axis,
    )
    return ReportResponse(summary=summary, markdown=full_md)


@router.post("/refine", response_model=RefineResponse)
async def refine(req: RefineRequest, orch=Depends(get_orchestrator)) -> RefineResponse:
    try:
        mode = AgentMode(req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}") from exc

    summary, full_md = await orch.refine_report(
        mode=mode,
        target_id=req.target_id,
        target_name=req.target_name,
        axis=req.axis,
        current_report_md=req.current_report_md,
        user_feedback=req.user_feedback,
    )
    return RefineResponse(change_summary=summary, markdown=full_md)
