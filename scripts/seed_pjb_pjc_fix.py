"""PJ-B / PJ-C Notion データ修正スクリプト.

対応内容:
  PJ-B:
    - メンバーDBに田中 誠を追加（現在2名 → 3名）
    - ページ概要の担当者記述を更新
  PJ-C:
    - 既存ボードビューDBにスキーマ設定＋タスク5件投入
    - メンバーDB・議事録DBにスキーマ設定（データなし・計画段階）
    - ページ概要更新

実行:
  uv run python scripts/seed_pjb_pjc_fix.py
"""

import os
import pathlib
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from notion_client import Client

# ============================================================
# IDs（確認済み）
# ============================================================

# PJ-B
PJ_B_PAGE_ID   = "36ac7942-de09-811f-8814-ca6c340896be"
PJ_B_MBR_DB_ID = "36ac7942-de09-8009-99fb-fc447aff1964"
PJ_B_MBR_DS_ID = "36ac7942-de09-8102-b584-000b27810cdd"

# PJ-C
PJ_C_PAGE_ID    = "36ac7942-de09-8176-88d2-de8abcd9251b"
PJ_C_TASK_DB_ID = "36ac7942-de09-8046-aa03-e642be9c030e"
PJ_C_TASK_DS_ID = "36ac7942-de09-8000-b2fe-000bc26d30f9"
PJ_C_MBR_DB_ID  = "36ac7942-de09-8028-b530-fa72cc507c04"
PJ_C_MBR_DS_ID  = "36ac7942-de09-8088-bd7d-000b0f14edca"
PJ_C_MTG_DB_ID  = "36ac7942-de09-80a8-89f5-e289a0004d89"
PJ_C_MTG_DS_ID  = "36ac7942-de09-8183-8d69-000b52e47420"

# ============================================================
# データ定義
# ============================================================

# PJ-B: 追加するメンバー（田中 誠）
PJ_B_NEW_MEMBER = {
    "名前":     "田中 誠",
    "email":    "tanaka@abc.com",
    "役職":     "テックリード",
    "スキル":   "Python, アーキテクチャ設計, PM, Azure, Semantic Kernel",
    "経験年数": 7,
    "一言メモ": "PJ全体のマネジメント・技術判断。1on1でメンバー育成に注力。",
}

# PJ-B ページ概要（田中誠を追加した版）
PJ_B_INFO_UPDATED = "\n".join([
    "概要: 大手ECサイト向けに協調フィルタリング＋機械学習を用いたレコメンドエンジンの開発。",
    "期間: 2026-02-01 〜 2026-07-25",
    "ステータス: 進行中",
    "必要スキル: Python, 協調フィルタリング, LightGBM, Azure ML, MLOps",
    "メンバー: 田中 誠,テックリード兼PM,2026-02-01,2026-07-25",
    "メンバー: 中村 大樹,MLリード,2026-02-01,2026-07-25",
    "メンバー: 山田 花奈,MLOps,2026-02-01,2026-07-25",
])

# PJ-C ページ概要
PJ_C_INFO = "\n".join([
    "概要: 胸部X線・MRI画像からの異常検出AIシステムの開発。医療機関向けSaaS。",
    "期間: 2026-08-01 〜 2026-11-30",
    "ステータス: 計画中",
    "必要スキル: Python, 画像認識, CNN, Vision Transformer, PyTorch, Azure, DICOM処理",
    "メンバー: 未定（エージェントによるアサイン提案待ち）",
])

# PJ-C タスク（5件・全て未着手・担当者未定）
PJ_C_TASKS = [
    {
        "タスク名":         "医療画像データセット調査・整備",
        "担当者":           "未定",
        "ステータス":       "未着手",
        "ストーリーポイント": 5,
        "使用スキル":       "Python, DICOM処理, データ整備",
        "実行結果・学び":   "",
    },
    {
        "タスク名":         "画像前処理パイプライン（DICOM対応）",
        "担当者":           "未定",
        "ステータス":       "未着手",
        "ストーリーポイント": 8,
        "使用スキル":       "Python, DICOM, 画像前処理, pydicom",
        "実行結果・学び":   "",
    },
    {
        "タスク名":         "ベースラインモデル実装（EfficientNet）",
        "担当者":           "未定",
        "ステータス":       "未着手",
        "ストーリーポイント": 8,
        "使用スキル":       "Python, PyTorch, EfficientNet, 画像分類",
        "実行結果・学び":   "",
    },
    {
        "タスク名":         "Vision Transformer Fine-tuning",
        "担当者":           "未定",
        "ステータス":       "未着手",
        "ストーリーポイント": 13,
        "使用スキル":       "Python, PyTorch, Vision Transformer, Swin Transformer",
        "実行結果・学び":   "",
    },
    {
        "タスク名":         "推論APIサーバー構築・Azureデプロイ",
        "担当者":           "未定",
        "ステータス":       "未着手",
        "ストーリーポイント": 5,
        "使用スキル":       "Python, FastAPI, Azure Container Apps, Docker",
        "実行結果・学び":   "",
    },
]


# ============================================================
# ユーティリティ
# ============================================================

def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def t(content: str) -> list:
    return [{"text": {"content": content}}] if content else []


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def find_first_paragraph(client: Client, page_id: str) -> str | None:
    resp = client.blocks.children.list(block_id=page_id, page_size=100)
    for b in resp["results"]:
        if b["type"] == "paragraph":
            return b["id"]
    return None


# ============================================================
# STEP 1: PJ-B メンバー追加（田中誠）
# ============================================================

def add_tanaka_to_pjb(client: Client) -> None:
    section("STEP 1: PJ-B メンバーDBに田中 誠を追加")
    m = PJ_B_NEW_MEMBER

    # 役職 selectにテックリードが未登録の場合に備えてoptionを事前追加
    try:
        client.data_sources.update(
            PJ_B_MBR_DS_ID,
            properties={
                "役職": {"select": {"options": [
                    {"name": "データサイエンティスト",  "color": "purple"},
                    {"name": "MLOps/DevOpsエンジニア", "color": "orange"},
                    {"name": "テックリード",            "color": "blue"},
                ]}},
            },
        )
        print("OK: 役職 selectオプション更新")
    except Exception as e:
        print(f"WARN: 役職 select更新スキップ: {e}")

    client.pages.create(
        parent={"database_id": PJ_B_MBR_DB_ID},
        properties={
            "名前":     {"title": t(m["名前"])},
            "email":    {"rich_text": t(m["email"])},
            "役職":     {"select": {"name": m["役職"]}},
            "スキル":   {"rich_text": t(m["スキル"])},
            "経験年数": {"number": m["経験年数"]},
            "一言メモ": {"rich_text": t(m["一言メモ"])},
        },
    )
    print(f"OK: {m['名前']} ({m['役職']}) 追加完了")


def update_pjb_page(client: Client) -> None:
    block_id = find_first_paragraph(client, PJ_B_PAGE_ID)
    if block_id:
        client.blocks.update(
            block_id=block_id,
            paragraph={"rich_text": t(PJ_B_INFO_UPDATED)},
        )
        print("OK: PJ-B ページ概要（担当者3名）更新完了")
    else:
        print("WARN: PJ-B ページのparagraphが見つかりません")


# ============================================================
# STEP 2: PJ-C タスク管理DB スキーマ設定 + データ投入
# ============================================================

def setup_pjc_task_schema(client: Client) -> None:
    """PJ-C タスク管理: 名前→タスク名, people担当者→rich_text, 他プロパティ追加."""

    # 1. タイトルプロパティをリネーム
    client.data_sources.update(
        PJ_C_TASK_DS_ID,
        properties={"名前": {"name": "タスク名"}},
    )
    print("OK: 名前 → タスク名 リネーム")

    # 2. people型 担当者を削除
    try:
        client.data_sources.update(
            PJ_C_TASK_DS_ID,
            properties={"担当者": None},
        )
        print("OK: 担当者(people) 削除")
    except Exception as e:
        print(f"WARN: 担当者削除スキップ: {e}")

    # 3. rich_text 担当者 + 追加プロパティ
    client.data_sources.update(
        PJ_C_TASK_DS_ID,
        properties={
            "担当者":             {"rich_text": {}},
            "ストーリーポイント": {"number": {"format": "number"}},
            "使用スキル":         {"rich_text": {}},
            "実行結果・学び":     {"rich_text": {}},
        },
    )
    print("OK: タスクDBプロパティ定義完了")


def insert_pjc_tasks(client: Client) -> None:
    """PJ-C タスク5件を status 型で投入."""
    for task in PJ_C_TASKS:
        client.pages.create(
            parent={"database_id": PJ_C_TASK_DB_ID},
            properties={
                "タスク名":           {"title": t(task["タスク名"])},
                "担当者":             {"rich_text": t(task["担当者"])},
                "ステータス":         {"status": {"name": task["ステータス"]}},
                "ストーリーポイント": {"number": task["ストーリーポイント"]},
                "使用スキル":         {"rich_text": t(task["使用スキル"])},
                "実行結果・学び":     {"rich_text": t(task["実行結果・学び"])},
            },
        )
        print(f"  + [{task['ステータス']}] {task['タスク名'][:40]} ({task['ストーリーポイント']}pt)")
        time.sleep(0.3)


# ============================================================
# STEP 3: PJ-C メンバーDB スキーマ整備（データなし）
# ============================================================

def setup_pjc_member_schema(client: Client) -> None:
    client.data_sources.update(
        PJ_C_MBR_DS_ID,
        properties={
            "email":    {"rich_text": {}},
            "役職":     {"select": {"options": [
                {"name": "テックリード",            "color": "blue"},
                {"name": "データサイエンティスト",  "color": "purple"},
                {"name": "MLOps/DevOpsエンジニア", "color": "orange"},
                {"name": "バックエンドエンジニア",  "color": "green"},
                {"name": "AIエンジニア",            "color": "red"},
            ]}},
            "スキル":   {"rich_text": {}},
            "経験年数": {"number": {"format": "number"}},
            "一言メモ": {"rich_text": {}},
        },
    )
    print("OK: PJ-C メンバーDBスキーマ定義完了（データ未登録・計画段階）")


# ============================================================
# STEP 4: PJ-C 議事録DB スキーマ整備（データなし）
# ============================================================

def setup_pjc_meeting_schema(client: Client) -> None:
    client.data_sources.update(
        PJ_C_MTG_DS_ID,
        properties={"名前": {"name": "タイトル"}},
    )
    client.data_sources.update(
        PJ_C_MTG_DS_ID,
        properties={
            "日付":   {"date": {}},
            "種別":   {"select": {"options": [
                {"name": "チームMTG",          "color": "blue"},
                {"name": "1on1",               "color": "green"},
                {"name": "スプリントレビュー",  "color": "orange"},
            ]}},
            "参加者": {"rich_text": {}},
            "本文":   {"rich_text": {}},
        },
    )
    print("OK: PJ-C 議事録DBスキーマ定義完了（データ未登録・計画段階）")


# ============================================================
# STEP 5: PJ-C ページ概要更新
# ============================================================

def update_pjc_page(client: Client) -> None:
    block_id = find_first_paragraph(client, PJ_C_PAGE_ID)
    if block_id:
        client.blocks.update(
            block_id=block_id,
            paragraph={"rich_text": t(PJ_C_INFO)},
        )
        print("OK: PJ-C ページ概要更新完了")
    else:
        # 先頭にparagraphを追加
        client.blocks.children.append(
            block_id=PJ_C_PAGE_ID,
            children=[{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": t(PJ_C_INFO)},
            }],
        )
        print("OK: PJ-C ページ概要を新規追加")


# ============================================================
# main
# ============================================================

def main() -> int:
    load_env()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("ERROR: NOTION_API_KEY が .env に見つかりません")
        return 1
    client = Client(auth=token)

    # PJ-B: 田中誠追加 + ページ更新
    add_tanaka_to_pjb(client)
    update_pjb_page(client)

    # PJ-C: 既存ボードビューDBにスキーマ+データ投入
    section("STEP 2: PJ-C タスク管理DB スキーマ設定")
    setup_pjc_task_schema(client)

    section("STEP 3: PJ-C タスク投入（5件・全て未着手）")
    insert_pjc_tasks(client)
    print(f"OK: タスク {len(PJ_C_TASKS)} 件投入")

    section("STEP 4: PJ-C メンバーDB スキーマ整備")
    setup_pjc_member_schema(client)

    section("STEP 5: PJ-C 議事録DB スキーマ整備")
    setup_pjc_meeting_schema(client)

    section("STEP 6: PJ-C ページ概要更新")
    update_pjc_page(client)

    section("完了")
    print("  [PJ-B] メンバーDB: 田中 誠が追加され 3名になりました")
    print("  [PJ-B] ページ概要: 担当者3名に更新")
    print("  [PJ-C] タスク管理（ボードビュー）: 5件投入（全て未着手・担当者未定）")
    print("  [PJ-C] メンバーDB・議事録: スキーマ整備完了（計画段階のため空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
