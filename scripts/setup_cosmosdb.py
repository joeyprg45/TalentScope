"""Cosmos DB セットアップスクリプト.

talentscope DB に必要な4コンテナをすべて作成する（既存はスキップ）。

  members       /member_id
  projects      /project_id
  meetings      /meeting_id   ← 全文 + LLM要約 + member_analyses[] を格納
  slack_channels /channel_id

実行:
  python scripts/setup_cosmosdb.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey

DATABASE_NAME = "talentscope"

CONTAINERS = [
    {"id": "members",        "partition_key": "/member_id"},
    {"id": "projects",       "partition_key": "/project_id"},
    {"id": "meetings",       "partition_key": "/meeting_id"},
    {"id": "slack_channels", "partition_key": "/channel_id"},
]


def main() -> int:
    load_dotenv()
    conn_str = os.getenv("COSMOS_CONNECTION_STRING")
    if not conn_str:
        print("NG: COSMOS_CONNECTION_STRING が .env に見つかりません")
        return 1

    client = CosmosClient.from_connection_string(conn_str)
    db = client.create_database_if_not_exists(id=DATABASE_NAME)
    print(f"OK: DB '{DATABASE_NAME}' 接続\n")

    for c in CONTAINERS:
        db.create_container_if_not_exists(
            id=c["id"],
            partition_key=PartitionKey(path=c["partition_key"]),
        )
        print(f"OK: {c['id']} ({c['partition_key']})")

    print("\n完了。次: python -m ingest.run_ingest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
