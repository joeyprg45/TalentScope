"""月次コスト + アサインカレンダーを Notion に追加するパッチスクリプト.

既存データを壊さずに以下を追加する:
  1. メンバーDB に 月次コスト（数値/円）プロパティを追加し、各メンバーに値をセット
  2. プロジェクトページの基本情報ブロックに メンバー: 行を追加
     形式: メンバー: 氏名,役割,開始日,終了日

実行:
  uv run python scripts/seed_assignments_cost.py
"""
import os
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from notion_client import Client

# ============================================================
# 対象ページ / DB（seed_llm_agent_test.py と同じID）
# ============================================================
PROJECT_PAGE_ID = "366c7942-de09-8092-9a75-e59d205d94d0"
MEMBER_DB_ID    = "367c7942-de09-80e2-b2c9-c70f94d2aa72"
MEMBER_DS_ID    = "367c7942-de09-8026-af72-000b072dfb23"

# ============================================================
# 月次コスト（円）
# ============================================================
MEMBER_COSTS: dict[str, int] = {
    "小林 拓海": 600_000,
    "前田 彩":   750_000,
    "佐藤 健太": 500_000,
    "田中 誠":   900_000,
    "山田 花奈": 650_000,
}

# ============================================================
# アサインカレンダー（氏名, 役割, 開始, 終了）
# ============================================================
ASSIGNMENTS = [
    ("田中 誠",   "テックリード",   "2026-05-01", "2026-06-30"),
    ("前田 彩",   "AIコアリード",   "2026-05-01", "2026-06-30"),
    ("小林 拓海", "バックエンド",   "2026-05-01", "2026-06-30"),
    ("佐藤 健太", "フロントエンド", "2026-05-15", "2026-06-30"),
    ("山田 花奈", "MLOps",          "2026-05-07", "2026-06-30"),
]

# プロジェクトページ基本情報の全文（メンバー行を含む完成形）
PROJECT_INFO_LINES = [
    "概要: 人事エージェントの基盤となるLLM Agentプラットフォームの開発。",
    "期間: 2026-05-01 〜 2026-06-30",
    "ステータス: 進行中",
    "必要スキル: Python, Semantic Kernel, Azure OpenAI, RAG, CosmosDB",
] + [f"メンバー: {name},{role},{start},{end}" for name, role, start, end in ASSIGNMENTS]


# ============================================================
# ユーティリティ
# ============================================================
def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def rt(content: str) -> list:
    return [{"text": {"content": content}}] if content else []


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def query_all_members(client: Client) -> list[dict]:
    rows, cursor = [], None
    while True:
        kwargs: dict = {"data_source_id": MEMBER_DS_ID, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.data_sources.query(**kwargs)
        rows.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return rows


def get_page_title_from_row(row: dict) -> str:
    for prop in row["properties"].values():
        if prop.get("type") == "title":
            return "".join(t.get("text", {}).get("content", "") for t in prop.get("title", []))
    return ""


# ============================================================
# STEP 1: メンバーDB に月次コストを追加
# ============================================================
def seed_member_costs(client: Client) -> None:
    section("STEP 1: メンバーDB に 月次コスト プロパティを追加")

    client.data_sources.update(
        MEMBER_DS_ID,
        properties={"月次コスト": {"number": {"format": "yen"}}},
    )
    print("OK: 月次コスト プロパティ追加")

    rows = query_all_members(client)
    for row in rows:
        name = get_page_title_from_row(row)
        cost = MEMBER_COSTS.get(name)
        if cost is None:
            print(f"  WARN: {name!r} のコストが未定義（スキップ）")
            continue
        client.pages.update(
            page_id=row["id"],
            properties={"月次コスト": {"number": cost}},
        )
        print(f"  + {name}: {cost:,}円/月")

    print(f"OK: {len(MEMBER_COSTS)} 名のコストを設定")


# ============================================================
# STEP 2: プロジェクトページ基本情報にメンバー行を追加
# ============================================================
def seed_project_assignments(client: Client) -> None:
    section("STEP 2: プロジェクトページにアサインカレンダーを追加")

    # 「概要:」を含む段落ブロックを探す
    blocks, cursor = [], None
    while True:
        resp = client.blocks.children.list(
            block_id=PROJECT_PAGE_ID, start_cursor=cursor, page_size=100
        )
        blocks.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

    target_block_id = None
    for b in blocks:
        if b.get("type") == "paragraph":
            content = "".join(
                t.get("text", {}).get("content", "")
                for t in b["paragraph"]["rich_text"]
            )
            if "概要:" in content:
                target_block_id = b["id"]
                break

    new_text = "\n".join(PROJECT_INFO_LINES)

    if target_block_id:
        client.blocks.update(
            block_id=target_block_id,
            paragraph={"rich_text": rt(new_text)},
        )
        print(f"OK: 既存ブロックを更新 (block={target_block_id})")
    else:
        client.blocks.children.append(
            block_id=PROJECT_PAGE_ID,
            children=[{
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": rt(new_text)},
            }],
        )
        print("OK: 新規ブロックを追加")

    for name, role, start, end in ASSIGNMENTS:
        print(f"  + {name}: {role} ({start}〜{end})")

    print(f"OK: アサイン {len(ASSIGNMENTS)} 名分を追加")


# ============================================================
# main
# ============================================================
def main() -> int:
    load_env()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("NG: NOTION_API_KEY が .env に見つかりません")
        return 1
    client = Client(auth=token)

    seed_member_costs(client)
    seed_project_assignments(client)

    section("完了: Notion でメンバーDB・プロジェクトページを確認してください")
    return 0


if __name__ == "__main__":
    sys.exit(main())
