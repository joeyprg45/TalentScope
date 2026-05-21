"""Notion API 接続検証スクリプト（フェーズ1）.

段階的に Notion API を叩き、各ステップの結果を標準出力に表示する。
  1. .env から NOTION_API_KEY を読み込む
  2. users.me() でトークン有効性を確認
  3. 対象IDがページかデータベースかを判定
  4. 中身（文字起こし本文 / DB行）を取得して表示
"""

import os
import sys

# Windows のコンソール既定エンコーディング(cp932)では絵文字や記号が出力できないため UTF-8 に固定
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

# 検証対象オブジェクトID（ユーザー提供URLより）
TARGET_ID = "2c7c7942de0980aabf7fd79487c2ab01"


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def extract_rich_text(rich_text: list) -> str:
    """rich_text 配列からプレーンテキストを連結する。"""
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def block_to_text(block: dict) -> str:
    """ブロック1件をテキスト化する（対応していない型は型名のみ）。"""
    btype = block.get("type", "")
    body = block.get(btype, {})
    if isinstance(body, dict) and "rich_text" in body:
        text = extract_rich_text(body["rich_text"])
        return f"[{btype}] {text}"
    return f"[{btype}] (テキスト無し)"


def main() -> int:
    section("STEP 1: .env 読み込み")
    load_dotenv()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("NG: NOTION_API_KEY が .env に見つかりません")
        return 1
    print(f"OK: トークン取得（先頭: {token[:8]}...）")

    client = Client(auth=token)

    section("STEP 2: トークン有効性チェック users.me()")
    try:
        me = client.users.me()
        print(f"OK: トークン有効 / bot名: {me.get('name')} / id: {me.get('id')}")
    except APIResponseError as e:
        print(f"NG: トークン不正の可能性 (status={e.status}, code={e.code})")
        print(f"    {e}")
        return 1

    section("STEP 3: 対象オブジェクト判定")
    obj_kind = None
    try:
        page = client.pages.retrieve(page_id=TARGET_ID)
        obj_kind = "page"
        print(f"OK: 対象はページです / id: {page.get('id')}")
        title_prop = next(
            (v for v in page.get("properties", {}).values() if v.get("type") == "title"),
            None,
        )
        if title_prop:
            print(f"    タイトル: {extract_rich_text(title_prop['title'])}")
    except APIResponseError as e_page:
        if e_page.status == 404:
            try:
                db = client.databases.retrieve(database_id=TARGET_ID)
                obj_kind = "database"
                print(f"OK: 対象はデータベースです / id: {db.get('id')}")
                print(f"    タイトル: {extract_rich_text(db.get('title', []))}")
                print(f"    プロパティ: {list(db.get('properties', {}).keys())}")
            except APIResponseError as e_db:
                print(f"NG: ページ/DBどちらでも取得失敗 (status={e_db.status})")
                print("    → インテグレーションへのページ共有が未設定の可能性大。")
                print('      Notionで対象ページを開き右上「...」→「接続を追加」から')
                print(f'      インテグレーション「{me.get("name")}」を追加してください。')
                return 1
        else:
            print(f"NG: 想定外のエラー (status={e_page.status}, code={e_page.code})")
            print(f"    {e_page}")
            return 1

    section("STEP 4: データ取得")
    if obj_kind == "page":
        blocks = client.blocks.children.list(block_id=TARGET_ID)
        results = blocks.get("results", [])
        print(f"OK: ブロック {len(results)} 件取得（先頭10件を表示）")
        for b in results[:10]:
            print(f"  {block_to_text(b)}")
        if blocks.get("has_more"):
            print("  ... (続きあり)")
    elif obj_kind == "database":
        rows = client.databases.query(database_id=TARGET_ID)
        results = rows.get("results", [])
        print(f"OK: 行 {len(results)} 件取得（先頭5件のIDを表示）")
        for r in results[:5]:
            print(f"  row id: {r.get('id')}")
        if rows.get("has_more"):
            print("  ... (続きあり)")

    section("検証完了: Notion 接続 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
