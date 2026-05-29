"""プロジェクト名またはUUIDをCosmosDBのproject_id（UUID）に解決するユーティリティ."""
from __future__ import annotations

import re

from azure.cosmos import ContainerProxy

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def resolve_project_id(name_or_id: str, projects_container: ContainerProxy) -> str:
    """プロジェクト名またはUUIDを受け取り、CosmosDBのproject_id（UUID）を返す。

    - UUIDが渡された場合はそのまま返す
    - 名前が渡された場合は部分一致で検索してUUIDを返す
    - 解決できない場合は元の値をそのまま返す（DBクエリ側でハンドリング）
    """
    v = (name_or_id or "").strip()
    if not v:
        return ""
    if _UUID_RE.match(v):
        return v
    items = list(
        projects_container.query_items(
            query="SELECT c.project_id, c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    name_lower = v.lower()
    for item in items:
        if name_lower in item.get("name", "").lower():
            return item["project_id"]
    return v
