"""SynergyPlugin — メンバー間の協働実績マトリクスを計算する."""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function


class SynergyPlugin:
    def __init__(
        self,
        projects_container: ContainerProxy,
        meetings_container: ContainerProxy,
    ) -> None:
        self._projects = projects_container
        self._meetings = meetings_container

    @kernel_function(
        name="get_collaboration_matrix",
        description=(
            "指定したメンバーIDリストについて、全ペアの過去共同プロジェクト数・"
            "共同会議参加数・シナジースコアを集計したマトリクスを返す。"
            "シナジー重視のアサイン提案で候補者を絞り込んだ後に1回だけ呼ぶ。"
        ),
    )
    async def get_collaboration_matrix(
        self,
        member_ids_json: Annotated[
            str,
            'メンバーIDのJSON配列。例: ["tanaka@abc.com", "maeda@abc.com"]',
        ],
    ) -> str:
        member_ids: list[str] = json.loads(member_ids_json)
        member_set = set(member_ids)

        # 共同プロジェクト数を集計
        shared_projects: dict[tuple[str, str], int] = {}
        for proj in self._projects.query_items(
            query="SELECT c.project_id, c.member_ids FROM c",
            enable_cross_partition_query=True,
        ):
            overlap = [m for m in proj.get("member_ids", []) if m in member_set]
            for i in range(len(overlap)):
                for j in range(i + 1, len(overlap)):
                    pair = tuple(sorted([overlap[i], overlap[j]]))
                    shared_projects[pair] = shared_projects.get(pair, 0) + 1

        # 共同会議数を集計
        shared_meetings: dict[tuple[str, str], int] = {}
        for mtg in self._meetings.query_items(
            query="SELECT c.meeting_id, c.participants FROM c",
            enable_cross_partition_query=True,
        ):
            overlap = [m for m in mtg.get("participants", []) if m in member_set]
            for i in range(len(overlap)):
                for j in range(i + 1, len(overlap)):
                    pair = tuple(sorted([overlap[i], overlap[j]]))
                    shared_meetings[pair] = shared_meetings.get(pair, 0) + 1

        # ペアリスト構築（シナジースコア降順）
        pairs = []
        for i in range(len(member_ids)):
            for j in range(i + 1, len(member_ids)):
                a, b = member_ids[i], member_ids[j]
                pair = tuple(sorted([a, b]))
                pj = shared_projects.get(pair, 0)
                mt = shared_meetings.get(pair, 0)
                pairs.append({
                    "member_a": a,
                    "member_b": b,
                    "shared_projects": pj,
                    "shared_meetings": mt,
                    "synergy_score": pj * 2 + mt,
                })
        pairs.sort(key=lambda x: x["synergy_score"], reverse=True)

        return json.dumps(
            {"member_count": len(member_ids), "pairs": pairs},
            ensure_ascii=False,
        )
