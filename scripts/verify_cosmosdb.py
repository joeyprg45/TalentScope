"""Cosmos DB 接続検証スクリプト（フェーズ1）.

段階的に Cosmos DB を叩き、各ステップの結果を標準出力に表示する。
  1. .env から COSMOS_CONNECTION_STRING を読み込む
  2. CosmosClient で接続確認
  3. データベース 'talentscope' を作成（既存なら取得）
  4. 3つのコンテナを作成（members / projects / meetings）
  5. テスト用ドキュメントを write → read → delete して CRUD 確認
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey, exceptions

DATABASE_NAME = "talentscope"
CONTAINERS = [
    {"id": "members",  "partition_key": "/member_id"},
    {"id": "projects", "partition_key": "/project_id"},
    {"id": "meetings", "partition_key": "/meeting_id"},
]


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def main() -> int:
    section("STEP 1: .env 読み込み")
    load_dotenv()
    conn_str = os.getenv("COSMOS_CONNECTION_STRING")
    if not conn_str:
        print("NG: COSMOS_CONNECTION_STRING が .env に見つかりません")
        print("    → Azureポータル > Cosmos DBアカウント > キー > プライマリ接続文字列")
        return 1
    print(f"OK: 接続文字列取得（先頭: {conn_str[:40]}...）")

    section("STEP 2: CosmosClient 接続確認")
    try:
        client = CosmosClient.from_connection_string(conn_str)
        # アカウント情報を取得して疎通確認
        props = client.get_database_account()
        print(f"OK: 接続成功 / WritableLocations: {[r['name'] for r in props.WritableLocations]}")
    except Exception as e:
        print(f"NG: 接続失敗 ({e})")
        return 1

    section(f"STEP 3: データベース '{DATABASE_NAME}' 作成/取得")
    try:
        db = client.create_database_if_not_exists(id=DATABASE_NAME)
        print(f"OK: データベース '{db.id}' 準備完了")
    except Exception as e:
        print(f"NG: データベース作成失敗 ({e})")
        return 1

    section("STEP 4: コンテナ作成/取得")
    containers = {}
    for spec in CONTAINERS:
        try:
            container = db.create_container_if_not_exists(
                id=spec["id"],
                partition_key=PartitionKey(path=spec["partition_key"]),
            )
            print(f"OK: コンテナ '{container.id}' 準備完了（partition: {spec['partition_key']}）")
            containers[spec["id"]] = container
        except Exception as e:
            print(f"NG: コンテナ '{spec['id']}' 作成失敗 ({e})")
            return 1

    section("STEP 5: CRUD 確認（members コンテナ）")
    test_doc = {
        "id": "test-verify-001",
        "member_id": "test-verify-001",
        "name": "テスト太郎",
        "note": "verify_cosmosdb.py による疎通確認用ドキュメント",
    }
    container = containers["members"]
    try:
        # Write
        container.upsert_item(test_doc)
        print(f"OK: Write — id={test_doc['id']}")

        # Read
        item = container.read_item(item=test_doc["id"], partition_key=test_doc["member_id"])
        print(f"OK: Read  — name={item['name']}")

        # Delete
        container.delete_item(item=test_doc["id"], partition_key=test_doc["member_id"])
        print(f"OK: Delete — id={test_doc['id']}")
    except Exception as e:
        print(f"NG: CRUD 失敗 ({e})")
        return 1

    section("検証完了: Cosmos DB 接続 OK")
    print(f"  データベース : {DATABASE_NAME}")
    print(f"  コンテナ     : {[c['id'] for c in CONTAINERS]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
