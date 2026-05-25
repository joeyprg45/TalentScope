from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_cosmos
from api.schemas.projects import Project, ProjectDetail

router = APIRouter()


@router.get("", response_model=list[Project])
def list_projects(status: str | None = None, cosmos=Depends(get_cosmos)) -> list[dict]:
    query = "SELECT c.project_id, c.name, c.status, c.period, c.assignments, c.required_skills FROM c WHERE c.type = 'project'"
    items = list(cosmos.projects.query_items(query=query, enable_cross_partition_query=True))
    if status:
        items = [p for p in items if p.get("status") == status]
    return items


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, cosmos=Depends(get_cosmos)) -> dict:
    items = list(cosmos.projects.query_items(
        query="SELECT * FROM c WHERE c.project_id = @id",
        parameters=[{"name": "@id", "value": project_id}],
        enable_cross_partition_query=True,
    ))
    if not items:
        raise HTTPException(status_code=404, detail="Project not found")
    return items[0]
