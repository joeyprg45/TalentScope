"""メンバー名→email 解決ユーティリティ."""
from __future__ import annotations

from azure.cosmos import ContainerProxy


def resolve_member_id(name_or_email: str, members_container: ContainerProxy) -> str:
    """名前またはemailを受け取りemailを返す。

    - '@' を含む場合はemailとみなしそのまま返す
    - それ以外は members コンテナを部分一致で検索してemailを返す
    - 見つからない場合は元の値を返す
    """
    v = (name_or_email or "").strip()
    if not v or "@" in v:
        return v
    items = list(
        members_container.query_items(
            query="SELECT c.member_id, c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    name_lower = v.lower()
    for item in items:
        if name_lower in item.get("name", "").lower():
            return item["member_id"]
    return v
