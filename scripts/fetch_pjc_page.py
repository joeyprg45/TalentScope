"""PJ-C（医療画像AI診断支援システム）ページをNotionから取得して構造を表示するスクリプト。

使い方:
  python scripts/fetch_pjc_page.py           # .env の NOTION_API_KEY を使用
  python scripts/fetch_pjc_page.py --page PAGE_ID

出力: ページタイトルと階層化されたブロック一覧を標準出力へ表示する。
"""

import os
import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

# デフォルトは既存スクリプトのPJ_C_PAGE_ID
DEFAULT_PAGE_ID = "36ac7942-de09-8176-88d2-de8abcd9251b"


def rich(rt: list) -> str:
    return "".join(t.get("plain_text", "") for t in (rt or []))


def block_label(block: dict) -> str:
    btype = block.get("type", "")
    body = block.get(btype, {})
    if isinstance(body, dict) and "rich_text" in body:
        return f"{btype}: {rich(body['rich_text'])}"
    if btype == "child_page":
        return f"child_page: {body.get('title', '')}  <<サブページ>>"
    if btype == "child_database":
        return f"child_database: {body.get('title', '')}  <<DB>>"
    if btype == "table":
        return f"table (width={body.get('table_width')})"
    if btype == "table_row":
        cells = body.get("cells", [])
        return "table_row: | " + " | ".join(rich(c) for c in cells) + " |"
    return f"{btype}"


def list_children(client: Client, block_id: str) -> list[dict]:
    results, cursor = [], None
    while True:
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def walk(client: Client, block_id: str, depth: int = 0, into_subpages: bool = True):
    for block in list_children(client, block_id):
        indent = "  " * depth
        print(f"{indent}- {block_label(block)}")
        btype = block.get("type")
        if btype == "child_page":
            if into_subpages:
                walk(client, block["id"], depth + 1, into_subpages)
        elif block.get("has_children"):
            walk(client, block["id"], depth + 1, into_subpages)


def get_page_title(page: dict) -> str:
    for _k, prop in page.get("properties", {}).items():
        if prop.get("type") == "title":
            return rich(prop.get("title", []))
    return "(無題)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", "-p", help="page id to fetch", default=DEFAULT_PAGE_ID)
    parser.add_argument("--no-subpages", action="store_true", help="do not recurse into child_page")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("ERROR: NOTION_API_KEY が .env に見つかりません")
        return 2

    client = Client(auth=token)

    try:
        page = client.pages.retrieve(page_id=args.page)
    except APIResponseError as e:
        print(f"ERROR: ページ取得失敗 (status={e.status})")
        return 3

    title = get_page_title(page)
    print(f"===== ページ: {title} (id={args.page}) =====\n")
    walk(client, args.page, depth=0, into_subpages=not args.no_subpages)
    print("\n===== 完了 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
