"""プロジェクト情報取得プラグイン."""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function


class ProjectPlugin:
    """プロジェクトDBからプロジェクト情報を取得する."""

    def __init__(self, projects_container: ContainerProxy) -> None:
        self._projects = projects_container

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
        project_id: Annotated[str, "プロジェクトID（Notion page ID）"],
    ) -> str:
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
