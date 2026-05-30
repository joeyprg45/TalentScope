"""メンバー情報取得プラグイン."""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve_member import resolve_member_id


class MemberPlugin:
    """メンバーDBとプロジェクトDBを横断してメンバー情報を取得する."""

    def __init__(
        self,
        members_container: ContainerProxy,
        projects_container: ContainerProxy,
    ) -> None:
        self._members = members_container
        self._projects = projects_container

    def _resolve(self, name_or_email: str) -> str:
        return resolve_member_id(name_or_email, self._members)

    @kernel_function(description="全メンバーの概要一覧（id/name/role/skills/経験年数/月次コスト/github_username）を返す")
    def list_all_members(self) -> str:
        query = (
            "SELECT c.member_id, c.name, c.role, c.skills, "
            "c.years_experience, c.monthly_cost, c.github_username "
            "FROM c"
        )
        items = list(
            self._members.query_items(query=query, enable_cross_partition_query=True)
        )
        return json.dumps(items, ensure_ascii=False)

    @kernel_function(description="指定メンバーの詳細（スキル/役職/コスト/Slack活動）を返す")
    def get_member_detail(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
    ) -> str:
        email = self._resolve(member_id)
        doc = self._members.read_item(item=email, partition_key=email)
        # Slack vlog は最新20件のみ渡してコンテキストを節約する
        vlog = doc.get("slack_vlog")
        if vlog and isinstance(vlog.get("posts"), list):
            vlog = {**vlog, "posts": vlog["posts"][-20:]}
            doc = {**doc, "slack_vlog": vlog}
        doc.pop("source", None)
        return json.dumps(doc, ensure_ascii=False)

    @kernel_function(description="指定スキルを持つメンバー一覧を返す（部分一致・大文字小文字無視）")
    def find_members_by_skill(
        self,
        skill_name: Annotated[str, "検索するスキル名（例: Python, Azure, RAG）"],
    ) -> str:
        query = (
            "SELECT c.member_id, c.name, c.role, c.skills, "
            "c.years_experience, c.monthly_cost "
            "FROM c"
        )
        all_members = list(
            self._members.query_items(query=query, enable_cross_partition_query=True)
        )
        skill_lower = skill_name.lower()
        matched = [
            m for m in all_members
            if any(skill_lower in s.lower() for s in m.get("skills", []))
        ]
        return json.dumps(matched, ensure_ascii=False)

    @kernel_function(
        description="メンバーが参加している全プロジェクトの在籍期間（役割/開始日/終了日）を返す"
    )
    def get_member_schedule(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
    ) -> str:
        email = self._resolve(member_id)
        query = (
            "SELECT c.project_id, c.name, c.period, c.status, c.assignments "
            "FROM c "
            "WHERE ARRAY_CONTAINS(c.member_ids, @mid)"
        )
        projects = list(
            self._projects.query_items(
                query=query,
                parameters=[{"name": "@mid", "value": email}],
                enable_cross_partition_query=True,
            )
        )
        schedule = []
        for proj in projects:
            member_assignments = [
                a for a in proj.get("assignments", [])
                if a.get("member_id") == email
            ]
            schedule.append({
                "project_id":   proj["project_id"],
                "project_name": proj["name"],
                "period":       proj.get("period", {}),
                "status":       proj.get("status", ""),
                "assignments":  member_assignments,
            })
        return json.dumps(schedule, ensure_ascii=False)
