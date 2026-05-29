"""議事録分析取得プラグイン.

Ingest時にLLMで生成済みの overall_summary / member_analyses[] をフィルター取得する。
このプラグイン内ではLLM呼び出しを行わない。
"""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve import resolve_project_id
from agents.plugins._resolve_member import resolve_member_id


class MeetingPlugin:
    """議事録DBから分析結果を取得する."""

    def __init__(
        self,
        meetings_container: ContainerProxy,
        projects_container: ContainerProxy | None = None,
        members_container: ContainerProxy | None = None,
    ) -> None:
        self._meetings = meetings_container
        self._projects = projects_container
        self._members = members_container

    def _resolve(self, name_or_id: str) -> str:
        if not name_or_id or not self._projects:
            return name_or_id or ""
        return resolve_project_id(name_or_id, self._projects)

    def _resolve_member(self, name_or_email: str) -> str:
        if not name_or_email or not self._members:
            return name_or_email or ""
        return resolve_member_id(name_or_email, self._members)

    @kernel_function(
        description=(
            "メンバーが参加した全MTGの能力分析（施策提案力/論理思考/ファシリテーション/"
            "技術深度/性格傾向）を返す"
        )
    )
    def get_member_meeting_analyses(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
        project_id: Annotated[str, "絞り込むプロジェクト名またはID（空文字なら全PJ）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付（空文字なら制限なし）"] = "",
    ) -> str:
        member_name = (member_id or "").strip()
        member_email = self._resolve_member(member_name)
        clauses = ["ARRAY_CONTAINS(c.participant_names, @name)"]
        params: list[dict] = [{"name": "@name", "value": member_name}]
        if project_id.strip():
            pid = self._resolve(project_id.strip())
            clauses.append("c.project_id = @pid")
            params.append({"name": "@pid", "value": pid})
        if date_from.strip():
            clauses.append("c.date >= @df")
            params.append({"name": "@df", "value": date_from.strip()})
        query = (
            "SELECT c.meeting_id, c.title, c.date, c.meeting_type, "
            "c.overall_summary, c.member_analyses "
            "FROM c WHERE " + " AND ".join(clauses)
        )
        meetings = list(
            self._meetings.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        results = []
        for mtg in meetings:
            member_entry = next(
                (a for a in mtg.get("member_analyses", []) if a.get("member_id") == member_email),
                None,
            )
            results.append({
                "meeting_id":      mtg["meeting_id"],
                "title":           mtg.get("title"),
                "date":            mtg.get("date"),
                "meeting_type":    mtg.get("meeting_type"),
                "overall_summary": mtg.get("overall_summary"),
                "member_analysis": member_entry,
            })
        return json.dumps(results, ensure_ascii=False)

    @kernel_function(
        description="プロジェクトの全MTG要約一覧（タイトル/日付/種別/全体要約）を返す"
    )
    def get_project_meeting_summaries(
        self,
        project_id: Annotated[str, "プロジェクト名またはID"],
    ) -> str:
        project_id = self._resolve(project_id)
        query = (
            "SELECT c.meeting_id, c.title, c.date, c.meeting_type, "
            "c.overall_summary, c.participant_names "
            "FROM c WHERE c.project_id = @pid"
        )
        meetings = list(
            self._meetings.query_items(
                query=query,
                parameters=[{"name": "@pid", "value": project_id}],
                enable_cross_partition_query=True,
            )
        )
        return json.dumps(meetings, ensure_ascii=False)

    @kernel_function(
        description=(
            "プロジェクトの議事録 full_text を直近順に最大 limit 件返す（会話分析用）。"
            "limit 未指定時は10件、date_from で期間下限を指定可能"
        )
    )
    def get_project_meetings(
        self,
        project_id: Annotated[str, "プロジェクト名またはID"],
        date_from: Annotated[str, "期間下限 ISO日付。空文字なら制限なし"] = "",
        date_to: Annotated[str, "期間上限 ISO日付。空文字なら現在"] = "",
        limit: Annotated[int, "取得件数上限（デフォルト10）"] = 10,
    ) -> str:
        if not limit or limit <= 0:
            limit = 10
        project_id = self._resolve(project_id)
        clauses = ["c.project_id = @pid"]
        params: list[dict] = [{"name": "@pid", "value": project_id}]
        if date_from.strip():
            clauses.append("c.date >= @df")
            params.append({"name": "@df", "value": date_from.strip()})
        if date_to.strip():
            clauses.append("c.date <= @dt")
            params.append({"name": "@dt", "value": date_to.strip()})
        query = (
            "SELECT TOP @lim c.meeting_id, c.title, c.date, c.meeting_type, c.full_text "
            "FROM c WHERE " + " AND ".join(clauses) + " ORDER BY c.date DESC"
        )
        params.append({"name": "@lim", "value": limit})
        meetings = list(
            self._meetings.query_items(
                query=query, parameters=params, enable_cross_partition_query=True,
            )
        )
        return json.dumps(meetings, ensure_ascii=False)

    @kernel_function(
        description=(
            "メンバーが参加した議事録 full_text を直近順に最大 limit 件返す（会話分析用）。"
            "limit 未指定時は10件"
        )
    )
    def get_member_meetings(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
        project_id: Annotated[str, "絞り込むプロジェクト名またはID（空文字なら全PJ）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付（空文字なら制限なし）"] = "",
        date_to: Annotated[str, "期間上限 ISO日付（空文字なら現在）"] = "",
        limit: Annotated[int, "取得件数上限（デフォルト10）"] = 10,
    ) -> str:
        if not limit or limit <= 0:
            limit = 10
        member_name = (member_id or "").strip()
        clauses = ["ARRAY_CONTAINS(c.participant_names, @name)"]
        params: list[dict] = [{"name": "@name", "value": member_name}]
        if project_id.strip():
            pid = self._resolve(project_id.strip())
            clauses.append("c.project_id = @pid")
            params.append({"name": "@pid", "value": pid})
        if date_from.strip():
            clauses.append("c.date >= @df")
            params.append({"name": "@df", "value": date_from.strip()})
        if date_to.strip():
            clauses.append("c.date <= @dt")
            params.append({"name": "@dt", "value": date_to.strip()})
        params.append({"name": "@lim", "value": limit})
        query = (
            "SELECT TOP @lim c.meeting_id, c.title, c.date, c.meeting_type, "
            "c.project_id, c.full_text "
            "FROM c WHERE " + " AND ".join(clauses) + " ORDER BY c.date DESC"
        )
        meetings = list(
            self._meetings.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        return json.dumps(meetings, ensure_ascii=False)
