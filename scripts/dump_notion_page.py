"""Notion ページを再帰的にクロールして全内容をツリー表示するスクリプト（フェーズ1 構造調査用）.

ハブページ ABC_technologies 配下を、トグル / ネスト箇条書き / サブページ / 表まで
すべて潜って書き出す。取り込み設計の検討材料にする。
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

TARGET_ID = "2c7c7942de0980aabf7fd79487c2ab01"


def rich(rt: list) -> str:
    return "".join(t.get("plain_text", "") for t in (rt or []))


def block_label(block: dict) -> str:
    """ブロック1件を1行のラベルにする。"""
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


def list_children(client: Client, block_id: str):
    """ページネーションを処理して全子ブロックを返す。"""
    blocks, cursor = [], None
    while True:
        resp = client.blocks.children.list(
            block_id=block_id, start_cursor=cursor, page_size=100
        )
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def walk(client: Client, block_id: str, depth: int = 0, into_subpages: bool = True):
    """ブロックを再帰的にたどって表示する。"""
    for block in list_children(client, block_id):
        indent = "  " * depth
        print(f"{indent}- {block_label(block)}")
        btype = block.get("type")
        # child_page は別ページ扱い。深追いするかは into_subpages で制御
        if btype == "child_page":
            if into_subpages:
                walk(client, block["id"], depth + 1, into_subpages)
        elif block.get("has_children"):
            walk(client, block["id"], depth + 1, into_subpages)


def main() -> int:
    load_dotenv()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("NG: NOTION_API_KEY が見つかりません")
        return 1
    client = Client(auth=token)
    try:
        page = client.pages.retrieve(page_id=TARGET_ID)
    except APIResponseError as e:
        print(f"NG: ページ取得失敗 (status={e.status})")
        return 1

    title_prop = next(
        (v for v in page.get("properties", {}).values() if v.get("type") == "title"),
        None,
    )
    title = rich(title_prop["title"]) if title_prop else "(無題)"
    print(f"===== ページ: {title} =====\n")
    walk(client, TARGET_ID, depth=0, into_subpages=True)
    print("\n===== 完了 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
