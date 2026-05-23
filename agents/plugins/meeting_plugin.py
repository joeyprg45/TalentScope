"""議事録分析取得プラグイン.

Ingest時にLLMで生成済みの overall_summary / member_analyses[] をフィルター取得する。
このプラグイン内ではLLM呼び出しを行わない。
"""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function


class MeetingPlugin:
    """議事録DBから分析結果を取得する."""

    def __init__(self, meetings_container: ContainerProxy) -> None:
        self._meetings = meetings_container

    @kernel_function(
        description=(
            "メンバーが参加した全MTGの能力分析（施策提案力/論理思考/ファシリテーション/"
            "技術深度/性格傾向）を返す"
        )
    )
    def get_member_meeting_analyses(
        self,
        member_id: Annotated[str, "メンバーのemail"],
    ) -> str:
        query = (
            "SELECT c.meeting_id, c.title, c.date, c.meeting_type, "
            "c.overall_summary, c.member_analyses "
            "FROM c WHERE ARRAY_CONTAINS(c.participants, @mid)"
        )
        meetings = list(
            self._meetings.query_items(
                query=query,
                parameters=[{"name": "@mid", "value": member_id}],
                enable_cross_partition_query=True,
            )
        )
        results = []
        for mtg in meetings:
            member_entry = next(
                (a for a in mtg.get("member_analyses", []) if a.get("member_id") == member_id),
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
        project_id: Annotated[str, "プロジェクトID"],
    ) -> str:
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
