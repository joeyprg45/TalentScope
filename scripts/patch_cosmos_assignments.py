"""Cosmos DB の projects コンテナにアサインデータを直接パッチする.

seed_demo_full.py / seed_pjb_pjc_fix.py が Notion に書いたデータと同じ内容を
Cosmos DB に直接 upsert する。ingest を再実行せずにカレンダー表示を修正できる。

実行:
  uv run python scripts/patch_cosmos_assignments.py
"""
import os
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from azure.cosmos import CosmosClient

PJ_A_ID = "366c7942-de09-8092-9a75-e59d205d94d0"
PJ_B_ID = "36ac7942-de09-811f-8814-ca6c340896be"

PJ_A_ASSIGNMENTS = [
    {"member_id": "tanaka@abc.com",    "role": "テックリード",   "start": "2026-04-01", "end": "2026-07-31"},
    {"member_id": "maeda@abc.com",     "role": "AIコアリード",   "start": "2026-04-01", "end": "2026-07-31"},
    {"member_id": "kobayashi@abc.com", "role": "バックエンド",   "start": "2026-04-01", "end": "2026-07-31"},
    {"member_id": "sato@abc.com",      "role": "フロントエンド", "start": "2026-04-01", "end": "2026-07-31"},
    {"member_id": "yamada@abc.com",    "role": "MLOps",          "start": "2026-04-01", "end": "2026-07-31"},
]

PJ_B_ASSIGNMENTS = [
    {"member_id": "tanaka@abc.com",   "role": "テックリード兼PM", "start": "2026-02-01", "end": "2026-07-25"},
    {"member_id": "nakamura@abc.com", "role": "MLリード",         "start": "2026-02-01", "end": "2026-07-25"},
    {"member_id": "yamada@abc.com",   "role": "MLOps",            "start": "2026-02-01", "end": "2026-07-25"},
]


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def patch_project(container, project_id: str, assignments: list[dict]) -> None:
    doc = container.read_item(item=project_id, partition_key=project_id)
    doc["assignments"] = assignments
    doc["member_ids"] = [a["member_id"] for a in assignments]
    container.upsert_item(doc)
    print(f"OK: {project_id} — {len(assignments)} 名のアサインを設定")
    for a in assignments:
        print(f"  {a['member_id']} / {a['role']} ({a['start']}〜{a['end']})")


def main() -> int:
    load_env()
    conn_str = os.getenv("COSMOS_CONNECTION_STRING")
    if not conn_str:
        print("NG: COSMOS_CONNECTION_STRING が .env に見つかりません")
        return 1

    cosmos = CosmosClient.from_connection_string(conn_str)
    container = cosmos.get_database_client("talentscope").get_container_client("projects")

    print("=== Cosmos DB アサインパッチ ===")
    patch_project(container, PJ_A_ID, PJ_A_ASSIGNMENTS)
    patch_project(container, PJ_B_ID, PJ_B_ASSIGNMENTS)
    print("\n完了: フロントエンドをリロードして確認してください")
    return 0


if __name__ == "__main__":
    sys.exit(main())
