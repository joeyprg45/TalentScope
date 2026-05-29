"""プロジェクト情報取得プラグイン."""
from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve import resolve_project_id


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()) if s else None
    except ValueError:
        return None


def _ranges_overlap(a_start: date | None, a_end: date | None,
                    b_start: date | None, b_end: date | None) -> bool:
    """[a_start, a_end] と [b_start, b_end] が重なるか。端不明は最大限重なる想定で扱う。"""
    if a_start and b_end and a_start > b_end:
        return False
    if a_end and b_start and a_end < b_start:
        return False
    return True


class ProjectPlugin:
    """プロジェクトDBからプロジェクト情報を取得する."""

    def __init__(
        self,
        projects_container: ContainerProxy,
        members_container: ContainerProxy | None = None,
    ) -> None:
        self._projects = projects_container
        self._members = members_container

    @kernel_function(description="全プロジェクト一覧（名前/ステータス/必要スキル/期間）を返す")
    def list_all_projects(
        self,
        status_filter: Annotated[str, "ステータスでフィルタ（空文字なら全件）"] = "",
    ) -> str:
        if status_filter:
            query = (
                "SELECT c.project_id, c.name, c.status, c.required_skills, "
                "c.period, c.member_ids, c.overview "
                "FROM c WHERE c.status = @status"
            )
            params = [{"name": "@status", "value": status_filter}]
        else:
            query = (
                "SELECT c.project_id, c.name, c.status, c.required_skills, "
                "c.period, c.member_ids, c.overview "
                "FROM c"
            )
            params = []

        items = list(
            self._projects.query_items(
                query=query,
                parameters=params or None,
                enable_cross_partition_query=True,
            )
        )
        return json.dumps(items, ensure_ascii=False)

    @kernel_function(
        description="指定プロジェクトの詳細（必要スキル/期間/アサイン/タスク一覧）を返す"
    )
    def get_project_detail(
        self,
        project_id: Annotated[str, "プロジェクト名またはID（例: EC推薦エンジン）"],
    ) -> str:
        project_id = resolve_project_id(project_id, self._projects)
        doc = self._projects.read_item(item=project_id, partition_key=project_id)
        doc.pop("source", None)
        return json.dumps(doc, ensure_ascii=False)

    @kernel_function(
        description="プロジェクト名（部分一致）でプロジェクトを検索し、詳細を返す。project_idが不明なときに使う"
    )
    def find_project_by_name(
        self,
        name: Annotated[str, "検索するプロジェクト名（部分一致・大文字小文字無視）"],
    ) -> str:
        query = "SELECT * FROM c"
        items = list(
            self._projects.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        )
        name_lower = name.lower()
        matched = [
            {k: v for k, v in item.items() if k != "source"}
            for item in items
            if name_lower in item.get("name", "").lower()
        ]
        if not matched:
            return json.dumps({"error": f"プロジェクト名 '{name}' に一致するプロジェクトが見つかりません"}, ensure_ascii=False)
        return json.dumps(matched, ensure_ascii=False)

    @kernel_function(
        description=(
            "指定期間に稼働アサインがないメンバー一覧を返す。"
            "アサイン提案モードで最初に呼び、候補プールを得るためのツール"
        )
    )
    def find_available_members(
        self,
        date_from: Annotated[str, "対象期間の開始日 ISO形式（例: 2026-08-01）"],
        date_to: Annotated[str, "対象期間の終了日 ISO形式。空文字なら開始日のみで判定"] = "",
    ) -> str:
        target_start = _parse_date(date_from)
        target_end = _parse_date(date_to) or target_start
        if not target_start:
            return json.dumps(
                {"error": "date_from を ISO日付（YYYY-MM-DD）で指定してください"},
                ensure_ascii=False,
            )

        all_projects = list(
            self._projects.query_items(
                query=(
                    "SELECT c.project_id, c.name, c.status, c.assignments, c.period "
                    "FROM c"
                ),
                enable_cross_partition_query=True,
            )
        )

        busy_members: dict[str, list[dict]] = {}
        for proj in all_projects:
            for a in proj.get("assignments", []) or []:
                mid = a.get("member_id")
                if not mid:
                    continue
                a_start = _parse_date(a.get("start_date", "") or a.get("start", ""))
                a_end = _parse_date(a.get("end_date", "") or a.get("end", ""))
                if _ranges_overlap(target_start, target_end, a_start, a_end):
                    busy_members.setdefault(mid, []).append({
                        "project_id":   proj["project_id"],
                        "project_name": proj.get("name", ""),
                        "role":         a.get("role"),
                        "start":        a.get("start_date") or a.get("start"),
                        "end":          a.get("end_date")   or a.get("end"),
                    })

        if self._members is None:
            return json.dumps(
                {"error": "members container が未注入のため候補抽出ができません"},
                ensure_ascii=False,
            )
        all_members = list(
            self._members.query_items(
                query=(
                    "SELECT c.member_id, c.name, c.role, c.skills, "
                    "c.years_experience, c.monthly_cost "
                    "FROM c"
                ),
                enable_cross_partition_query=True,
            )
        )
        available = [m for m in all_members if m["member_id"] not in busy_members]
        return json.dumps(
            {
                "date_from": date_from,
                "date_to":   date_to or date_from,
                "available_count": len(available),
                "available_members": available,
                "busy_members": [
                    {"member_id": mid, "assignments": busy_members[mid]}
                    for mid in busy_members
                ],
            },
            ensure_ascii=False,
        )
