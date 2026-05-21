"""Notion v3 API 挙動診断スクリプト."""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client

HUB_PAGE_ID = "2c7c7942de0980aabf7fd79487c2ab01"


def t(content: str) -> list:
    return [{"text": {"content": content}}]


def main():
    load_dotenv()
    client = Client(auth=os.getenv("NOTION_API_KEY"))

    # ---- STEP 1: DB作成 (initial_data_source でプロパティ指定) ----
    print("STEP 1: databases.create (initial_data_source でプロパティ指定)")
    try:
        db = client.databases.create(
            parent={"type": "page_id", "page_id": HUB_PAGE_ID},
            title=t("診断テストDB2"),
            initial_data_source={
                "properties": {
                    "名前":   {"title": {}},
                    "email":  {"rich_text": {}},
                    "経験年数": {"number": {"format": "number"}},
                }
            },
        )
        db_id = db["id"]
        ds_id = db.get("data_sources", [{}])[0].get("id")
        print(f"  db_id={db_id}")
        print(f"  ds_id={ds_id}")
        print(f"  data_sources={json.dumps(db.get('data_sources'), ensure_ascii=False)}")
    except Exception as e:
        print(f"  NG: {e}")
        return

    # ---- STEP 2: data_sources.retrieve で確認 ----
    print("\nSTEP 2: data_sources.retrieve でプロパティ確認")
    try:
        ds_info = client.data_sources.retrieve(data_source_id=ds_id)
        props = ds_info.get("properties", {})
        print(f"  ds response keys: {list(ds_info.keys())}")
        print(f"  properties ({len(props)} 件):")
        for name, prop in props.items():
            print(f"    [{prop.get('type')}] {name!r}")
    except Exception as e:
        print(f"  NG: {e}")
        return

    # ---- STEP 3: data_sources.update でプロパティ更新 ----
    print("\nSTEP 3: data_sources.update でプロパティ追加テスト")
    try:
        upd = client.data_sources.update(
            ds_id,
            properties={
                "役職": {"select": {"options": [{"name": "エンジニア", "color": "blue"}]}},
            },
        )
        props2 = upd.get("properties", {})
        print(f"  update後 properties ({len(props2)} 件):")
        for name, prop in props2.items():
            print(f"    [{prop.get('type')}] {name!r}")
    except Exception as e:
        print(f"  NG: {e}")

    # ---- STEP 4: pages.create で行追加 (parent=db_id) ----
    print("\nSTEP 4a: pages.create (parent=database_id=db_id)")
    try:
        page = client.pages.create(
            parent={"database_id": db_id},
            properties={
                "名前":   {"title": t("テスト太郎")},
                "email":  {"rich_text": t("test@test.com")},
                "経験年数": {"number": 3},
            },
        )
        print(f"  OK: page_id={page['id']}")
    except Exception as e:
        print(f"  NG (db_id): {e}")

    # ---- STEP 5: pages.create で行追加 (parent=ds_id) ----
    print("\nSTEP 4b: pages.create (parent=database_id=ds_id)")
    try:
        page2 = client.pages.create(
            parent={"database_id": ds_id},
            properties={
                "名前":   {"title": t("テスト花子")},
                "email":  {"rich_text": t("test2@test.com")},
                "経験年数": {"number": 5},
            },
        )
        print(f"  OK: page_id={page2['id']}")
    except Exception as e:
        print(f"  NG (ds_id): {e}")

    print("\n診断完了")


if __name__ == "__main__":
    main()
