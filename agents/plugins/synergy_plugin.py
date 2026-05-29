"""SynergyPlugin — メンバー間の協働実績マトリクスを計算する."""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve_member import resolve_member_id


class SynergyPlugin:
    def __init__(
        self,
        projects_container: ContainerProxy,
        meetings_container: ContainerProxy,
        members_container: ContainerProxy | None = None,
    ) -> None:
        self._projects = projects_container
        self._meetings = meetings_container
        self._members = members_container

    @kernel_function(
        name="get_collaboration_matrix",
        description=(
            "指定したメンバーの名前またはemailリストについて、全ペアの過去共同プロジェクト数・"
            "共同会議参加数・シナジースコアを集計したマトリクスを返す。"
            "シナジー重視のアサイン提案で候補者を絞り込んだ後に1回だけ呼ぶ。"
        ),
    )
    async def get_collaboration_matrix(
        self,
        member_ids_json: Annotated[
            str,
            '名前またはemailのJSON配列。例: ["中村 大樹", "山田 花奈"]',
        ],
    ) -> str:
        member_names: list[str] = json.loads(member_ids_json)

        # プロジェクトのmember_ids（email）との照合用
        email_set: set[str] = set()
        name_to_email: dict[str, str] = {}
        for name in member_names:
            if self._members:
                email = resolve_member_id(name, self._members)
            else:
                email = name
            email_set.add(email)
            name_to_email[name] = email

        # 会議のparticipant_names（名前）との照合用
        name_set = set(member_names)

        # 共同プロジェクト数を集計（email_setで照合）
        shared_projects: dict[tuple[str, str], int] = {}
        for proj in self._projects.query_items(
            query="SELECT c.project_id, c.member_ids FROM c",
            enable_cross_partition_query=True,
        ):
            # member_ids はemail → email_setで照合
            overlap_emails = [m for m in proj.get("member_ids", []) if m in email_set]
            # emailを名前に逆変換してペアを構築
            email_to_name = {v: k for k, v in name_to_email.items()}
            overlap = [email_to_name.get(e, e) for e in overlap_emails]
            for i in range(len(overlap)):
                for j in range(i + 1, len(overlap)):
                    pair = tuple(sorted([overlap[i], overlap[j]]))
                    shared_projects[pair] = shared_projects.get(pair, 0) + 1

        # 共同会議数を集計（name_setでparticipant_namesを照合）
        shared_meetings: dict[tuple[str, str], int] = {}
        for mtg in self._meetings.query_items(
            query="SELECT c.meeting_id, c.participant_names FROM c",
            enable_cross_partition_query=True,
        ):
            overlap = [m for m in mtg.get("participant_names", []) if m in name_set]
            for i in range(len(overlap)):
                for j in range(i + 1, len(overlap)):
                    pair = tuple(sorted([overlap[i], overlap[j]]))
                    shared_meetings[pair] = shared_meetings.get(pair, 0) + 1

        # ペアリスト構築（シナジースコア降順）
        pairs = []
        for i in range(len(member_names)):
            for j in range(i + 1, len(member_names)):
                a, b = member_names[i], member_names[j]
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
            {"member_count": len(member_names), "pairs": pairs},
            ensure_ascii=False,
        )
