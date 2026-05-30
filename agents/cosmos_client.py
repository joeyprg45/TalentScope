"""Cosmos DB コンテナクライアントのファクトリ."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from azure.cosmos import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from agents.config import AgentSettings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CosmosContainers:
    """9つのコンテナクライアントをまとめて保持する."""

    members:              ContainerProxy
    projects:             ContainerProxy
    meetings:             ContainerProxy
    slack_channels:       ContainerProxy
    reports:              ContainerProxy
    chat_sessions:        ContainerProxy
    prompts:              ContainerProxy
    absolute_constraints: ContainerProxy
    qualitative_memory:   ContainerProxy

    def __init__(self, settings: AgentSettings) -> None:
        client = CosmosClient.from_connection_string(settings.cosmos_connection_string)
        db = client.get_database_client(settings.cosmos_database)
        self.members       = db.get_container_client("members")
        self.projects      = db.get_container_client("projects")
        self.meetings      = db.get_container_client("meetings")
        self.slack_channels = db.get_container_client("slack_channels")
        self.reports       = db.create_container_if_not_exists(
            id="reports", partition_key={"paths": ["/id"], "kind": "Hash"}
        )
        self.chat_sessions = db.create_container_if_not_exists(
            id="chat_sessions", partition_key={"paths": ["/id"], "kind": "Hash"}
        )
        self.prompts = db.create_container_if_not_exists(
            id="prompts", partition_key={"paths": ["/id"], "kind": "Hash"}
        )
        self.absolute_constraints = db.create_container_if_not_exists(
            id="absolute_constraints", partition_key={"paths": ["/id"], "kind": "Hash"}
        )
        self.qualitative_memory = db.create_container_if_not_exists(
            id="qualitative_memory", partition_key={"paths": ["/id"], "kind": "Hash"}
        )


# ---------------------------------------------------------------------------
# absolute_constraints CRUD
# ---------------------------------------------------------------------------

def get_active_constraints(cosmos: CosmosContainers) -> list[str]:
    """status=active の制約テキスト一覧を返す。"""
    items = list(cosmos.absolute_constraints.query_items(
        query="SELECT c.content FROM c WHERE c.status = 'active'",
        enable_cross_partition_query=True,
    ))
    return [item["content"] for item in items]


def get_all_constraints(cosmos: CosmosContainers) -> list[dict]:
    """UI表示用: 全ステータスの制約ドキュメント一覧（作成日昇順）。"""
    return list(cosmos.absolute_constraints.query_items(
        query="SELECT * FROM c ORDER BY c.created_at ASC",
        enable_cross_partition_query=True,
    ))


def upsert_constraint(
    cosmos: CosmosContainers,
    content: str,
    related_member_ids: list[str],
    status: str,
    source: str,
    chat_id: str | None = None,
) -> dict:
    """絶対条件を新規作成する。id は uuid4 で自動採番。"""
    doc = {
        "id": str(uuid4()),
        "content": content,
        "status": status,
        "source": source,
        "related_member_ids": related_member_ids,
        "created_at": _now(),
        "created_from_chat_id": chat_id,
    }
    cosmos.absolute_constraints.upsert_item(doc)
    return doc


def update_constraint_status(cosmos: CosmosContainers, constraint_id: str, status: str) -> bool:
    """絶対条件のステータスを更新する。"""
    try:
        doc = cosmos.absolute_constraints.read_item(item=constraint_id, partition_key=constraint_id)
        doc["status"] = status
        cosmos.absolute_constraints.upsert_item(doc)
        return True
    except CosmosResourceNotFoundError:
        return False


def delete_constraint(cosmos: CosmosContainers, constraint_id: str) -> bool:
    """絶対条件を削除する。"""
    try:
        cosmos.absolute_constraints.delete_item(item=constraint_id, partition_key=constraint_id)
        return True
    except CosmosResourceNotFoundError:
        return False


# ---------------------------------------------------------------------------
# qualitative_memory CRUD
# ---------------------------------------------------------------------------

QUALITATIVE_SINGLETON_ID = "singleton"


def get_qualitative_memory(cosmos: CosmosContainers) -> str:
    """定性条件テキストを返す。未存在なら空文字。"""
    try:
        doc = cosmos.qualitative_memory.read_item(
            item=QUALITATIVE_SINGLETON_ID,
            partition_key=QUALITATIVE_SINGLETON_ID,
        )
        return doc.get("content", "")
    except CosmosResourceNotFoundError:
        return ""


def upsert_qualitative_memory(cosmos: CosmosContainers, content: str) -> dict:
    """定性条件を上書き保存する（常に id=singleton の1件のみ）。"""
    try:
        existing = cosmos.qualitative_memory.read_item(
            item=QUALITATIVE_SINGLETON_ID,
            partition_key=QUALITATIVE_SINGLETON_ID,
        )
        version = existing.get("version", 0) + 1
    except CosmosResourceNotFoundError:
        version = 1
    doc = {
        "id": QUALITATIVE_SINGLETON_ID,
        "content": content,
        "updated_at": _now(),
        "version": version,
    }
    cosmos.qualitative_memory.upsert_item(doc)
    return doc


# ---------------------------------------------------------------------------
# chat_sessions: 抽出パイプライン用ヘルパー
# ---------------------------------------------------------------------------

def get_unprocessed_sessions(cosmos: CosmosContainers) -> list[dict]:
    """memory_extracted_at が未設定のセッションを created_at 昇順で返す。"""
    return list(cosmos.chat_sessions.query_items(
        query=(
            "SELECT * FROM c"
            " WHERE NOT IS_DEFINED(c.memory_extracted_at)"
            "    OR c.memory_extracted_at = null"
            " ORDER BY c.created_at ASC"
        ),
        enable_cross_partition_query=True,
    ))


def mark_session_extracted(cosmos: CosmosContainers, session_id: str) -> None:
    """セッションの memory_extracted_at を現在時刻にセットする。"""
    doc = cosmos.chat_sessions.read_item(item=session_id, partition_key=session_id)
    doc["memory_extracted_at"] = _now()
    cosmos.chat_sessions.upsert_item(doc)


def get_unprocessed_sessions_count(cosmos: CosmosContainers) -> int:
    """memory_extracted_at が未設定のセッション件数を返す（COUNT クエリ）。"""
    result = list(cosmos.chat_sessions.query_items(
        query=(
            "SELECT VALUE COUNT(1) FROM c"
            " WHERE NOT IS_DEFINED(c.memory_extracted_at)"
            "    OR c.memory_extracted_at = null"
        ),
        enable_cross_partition_query=True,
    ))
    return result[0] if result else 0
