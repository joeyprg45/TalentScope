"""タスク貢献度・コスト計算プラグイン."""
from __future__ import annotations

import json
import math
from datetime import date
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve import resolve_project_id
from agents.plugins._resolve_member import resolve_member_id


class ContributionPlugin:
    """タスク集計と月次コスト試算を担当する."""

    def __init__(
        self,
        members_container: ContainerProxy,
        projects_container: ContainerProxy,
    ) -> None:
        self._members = members_container
        self._projects = projects_container

    @kernel_function(description="メンバーのプロジェクト別タスク貢献度（SP合計/完了率/得意スキル）を返す")
    def get_member_task_stats(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
        project_id: Annotated[str, "絞り込むプロジェクトID（空文字なら全PJ）"] = "",
    ) -> str:
        member_id = resolve_member_id(member_id, self._members)
        clauses = ["ARRAY_CONTAINS(c.member_ids, @mid)"]
        params: list[dict] = [{"name": "@mid", "value": member_id}]
        if project_id.strip():
            clauses.append("c.project_id = @pid")
            params.append({"name": "@pid", "value": project_id.strip()})
        query = (
            "SELECT c.project_id, c.name, c.period, c.tasks "
            "FROM c WHERE " + " AND ".join(clauses)
        )
        projects = list(
            self._projects.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        stats = []
        for proj in projects:
            member_tasks = [
                t for t in proj.get("tasks", [])
                if t.get("assignee") == member_id
            ]
            if not member_tasks:
                continue
            total_sp = sum(t.get("story_points", 0) for t in member_tasks)
            done_sp = sum(
                t.get("story_points", 0)
                for t in member_tasks
                if t.get("status") in ("完了", "Done", "Closed")
            )
            skills_used: list[str] = []
            for t in member_tasks:
                skills_used.extend(t.get("skills_used", []))
            result_notes = [
                t.get("result_note", "") for t in member_tasks if t.get("result_note")
            ]
            task_descriptions = [
                {"name": t.get("name", ""), "description": t["description"][:500]}
                for t in member_tasks
                if t.get("description")
            ]
            stats.append({
                "project_id":        proj["project_id"],
                "project_name":      proj["name"],
                "period":            proj.get("period", {}),
                "task_count":        len(member_tasks),
                "total_sp":          total_sp,
                "done_sp":           done_sp,
                "completion_rate":   round(done_sp / total_sp, 2) if total_sp else 0,
                "skills_used":       list(dict.fromkeys(skills_used)),  # 重複除去・順序保持
                "result_notes":      result_notes,
                "task_descriptions": task_descriptions,
            })
        return json.dumps(stats, ensure_ascii=False)

    @kernel_function(description="プロジェクトのタスク一覧（担当者/ステータス/SP/実行結果）を返す")
    def get_project_tasks(
        self,
        project_id: Annotated[str, "プロジェクト名またはID"],
    ) -> str:
        project_id = resolve_project_id(project_id, self._projects)
        doc = self._projects.read_item(item=project_id, partition_key=project_id)
        return json.dumps(
            {"project_name": doc.get("name"), "tasks": doc.get("tasks", [])},
            ensure_ascii=False,
        )

    @kernel_function(
        description="提案チームの月次コスト合計×プロジェクト期間＝総コストを試算する"
    )
    def calc_project_cost(
        self,
        member_ids_json: Annotated[
            str,
            'メンバーIDのJSON配列 例: ["kobayashi@abc.com", "maeda@abc.com"]',
        ],
        project_id: Annotated[str, "プロジェクト名またはID"],
    ) -> str:
        member_ids: list[str] = json.loads(member_ids_json)

        project_id = resolve_project_id(project_id, self._projects)
        project = self._projects.read_item(item=project_id, partition_key=project_id)
        period = project.get("period", {})
        start_str = period.get("start", "")
        end_str = period.get("end", "")

        months: float | None = None
        if start_str and end_str:
            try:
                start_d = date.fromisoformat(start_str)
                end_d = date.fromisoformat(end_str)
                months = math.ceil((end_d - start_d).days / 30)
            except ValueError:
                months = None

        per_member: list[dict] = []
        total_monthly = 0
        for mid in member_ids:
            try:
                m = self._members.read_item(item=mid, partition_key=mid)
                cost = m.get("monthly_cost", 0) or 0
                per_member.append({"member_id": mid, "name": m.get("name", mid), "monthly_cost": cost})
                total_monthly += cost
            except Exception:
                per_member.append({"member_id": mid, "name": mid, "monthly_cost": 0, "error": "not found"})

        result = {
            "project_name":   project.get("name"),
            "period":         period,
            "months":         months,
            "per_member":     per_member,
            "total_monthly":  total_monthly,
            "total_cost":     total_monthly * months if months is not None else None,
        }
        return json.dumps(result, ensure_ascii=False)
