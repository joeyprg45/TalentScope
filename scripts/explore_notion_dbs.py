"""Notion DB のプロパティ構造を確認するスクリプト.

次世代 LLM Agent 基盤開発 配下の各DBのスキーマとIDを表示する。
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client

# 次世代 LLM Agent 基盤開発 のページID（dump_notion_page.py で特定済み）
PROJECT_PAGE_ID = "2c7c7942de0980aabf7fd79487c2ab01"


def rich(rt: list) -> str:
    return "".join(t.get("plain_text", "") for t in (rt or []))


def list_children(client, block_id):
    blocks, cursor = [], None
    while True:
        resp = client.blocks.children.list(block_id=block_id, start_cursor=cursor, page_size=100)
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def main():
    load_dotenv()
    client = Client(auth=os.getenv("NOTION_API_KEY"))

    # ABC_technologies 配下のサブページを探す
    for block in list_children(client, PROJECT_PAGE_ID):
        if block.get("type") == "child_page":
            title = block["child_page"]["title"]
            if "次世代" in title:
                project_id = block["id"]
                print(f"プロジェクトページ: {title}")
                print(f"  ID: {project_id}\n")

                # そのプロジェクト内のDBを列挙
                for child in list_children(client, project_id):
                    if child.get("type") == "child_database":
                        db_title = child["child_database"]["title"]
                        db_id = child["id"]
                        print(f"  DB: {db_title}")
                        print(f"    ID: {db_id}")

                        # DBのプロパティ構造を取得
                        db_info = client.databases.retrieve(database_id=db_id)
                        props = db_info.get("properties", {})
                        print(f"    プロパティ ({len(props)}件):")
                        for prop_name, prop_def in props.items():
                            print(f"      - {prop_name}: {prop_def['type']}")
                        print()
                break


if __name__ == "__main__":
    main()
