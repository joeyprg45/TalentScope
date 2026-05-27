from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from api.schemas.saved_report import ChatEntry, ReportListItem, StoredReport


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_report(
    container: ContainerProxy,
    *,
    type_: str,
    title: str,
    markdown: str,
    axis: str | None,
    member_id: str | None,
    project_id: str | None,
    chat_history: list[ChatEntry] | None = None,
) -> StoredReport:
    now = _now()
    doc = {
        "id": str(uuid4()),
        "type": type_,
        "title": title,
        "markdown": markdown,
        "axis": axis,
        "member_id": member_id,
        "project_id": project_id,
        "created_at": now,
        "updated_at": now,
        "chat_history": [e.model_dump() for e in (chat_history or [])],
    }
    container.upsert_item(doc)
    return StoredReport(**doc)


async def update_report(
    container: ContainerProxy,
    report_id: str,
    *,
    title: str,
    markdown: str,
    extra_entry: ChatEntry | None = None,
) -> StoredReport | None:
    try:
        doc = container.read_item(item=report_id, partition_key=report_id)
    except CosmosResourceNotFoundError:
        return None

    doc["title"] = title
    doc["markdown"] = markdown
    doc["updated_at"] = _now()
    if extra_entry:
        doc.setdefault("chat_history", []).append(extra_entry.model_dump())

    container.upsert_item(doc)
    return StoredReport(**doc)


async def get_report(container: ContainerProxy, report_id: str) -> StoredReport | None:
    try:
        doc = container.read_item(item=report_id, partition_key=report_id)
        return StoredReport(**doc)
    except CosmosResourceNotFoundError:
        return None


async def list_reports(container: ContainerProxy) -> list[ReportListItem]:
    query = (
        "SELECT c.id, c.type, c.title, c.markdown, c.axis, c.member_id, c.project_id, "
        "c.created_at, c.updated_at FROM c ORDER BY c.created_at DESC"
    )
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return [ReportListItem(**item) for item in items]


async def delete_report(container: ContainerProxy, report_id: str) -> bool:
    try:
        container.delete_item(item=report_id, partition_key=report_id)
        return True
    except CosmosResourceNotFoundError:
        return False


async def tag_report(
    container: ContainerProxy,
    report_id: str,
    *,
    member_id: str | None,
    project_id: str | None,
) -> StoredReport | None:
    try:
        doc = container.read_item(item=report_id, partition_key=report_id)
    except CosmosResourceNotFoundError:
        return None

    doc["member_id"] = member_id
    doc["project_id"] = project_id
    doc["updated_at"] = _now()
    container.upsert_item(doc)
    return StoredReport(**doc)
