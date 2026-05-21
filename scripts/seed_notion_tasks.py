"""次世代 LLM Agent 基盤開発 / タスク管理DB にスキーマ定義＋ダミーデータを投入するスクリプト."""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client

TASK_DB_ID = "366c7942-de09-80be-a460-d13274ae1114"

DUMMY_TASKS = [
    {
        "タスク名": "Azure Cosmos DB の接続設計・実装",
        "担当者": "小林",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, Azure, NoSQL",
        "実行結果・学び": "CosmosDB SDK でCRUDを実装。パーティションキーの設計で詰まったが、member_id をキーにすることで解決。",
    },
    {
        "タスク名": "Semantic Kernel によるエージェント基盤の構築",
        "担当者": "前田",
        "ステータス": "進行中",
        "ストーリーポイント": 8,
        "使用スキル": "Python, Semantic Kernel, Azure OpenAI",
        "実行結果・学び": "",
    },
    {
        "タスク名": "Notion APIを用いたデータ取り込みパイプライン実装",
        "担当者": "小林",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, Notion API, REST",
        "実行結果・学び": "再帰クロールで全ブロックを取得できた。has_children フラグを使った実装が鍵。",
    },
    {
        "タスク名": "チャットUIのフロントエンド実装",
        "担当者": "佐藤",
        "ステータス": "未着手",
        "ストーリーポイント": 8,
        "使用スキル": "React, TypeScript",
        "実行結果・学び": "",
    },
    {
        "タスク名": "RAGパイプラインの設計・検証",
        "担当者": "前田",
        "ステータス": "完了",
        "ストーリーポイント": 13,
        "使用スキル": "Python, Azure OpenAI, Vector Search",
        "実行結果・学び": "CosmosDBのベクトル検索機能を使いRAGを実装。埋め込みモデルはtext-embedding-3-smallを採用。精度は十分。",
    },
    {
        "タスク名": "Slack APIを用いたメッセージ取り込み実装",
        "担当者": "佐藤",
        "ステータス": "完了",
        "ストーリーポイント": 3,
        "使用スキル": "Python, Slack API",
        "実行結果・学び": "users.listで名前解決を一度にまとめることでレート制限を回避できた。",
    },
    {
        "タスク名": "Azureへのデプロイ・CI/CD構築",
        "担当者": "佐藤",
        "ステータス": "未着手",
        "ストーリーポイント": 5,
        "使用スキル": "Azure Container Apps, GitHub Actions",
        "実行結果・学び": "",
    },
]


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def main():
    load_dotenv()
    client = Client(auth=os.getenv("NOTION_API_KEY"))

    section("STEP 1: タスク管理DB にプロパティを定義")
    client.databases.update(
        database_id=TASK_DB_ID,
        properties={
            "タスク名": {"title": {}},
            "担当者": {"rich_text": {}},
            "ステータス": {
                "select": {
                    "options": [
                        {"name": "未着手", "color": "gray"},
                        {"name": "進行中", "color": "blue"},
                        {"name": "完了",   "color": "green"},
                    ]
                }
            },
            "ストーリーポイント": {"number": {"format": "number"}},
            "使用スキル": {"rich_text": {}},
            "実行結果・学び": {"rich_text": {}},
        },
    )
    print("OK: プロパティ定義完了")

    section(f"STEP 2: ダミータスク {len(DUMMY_TASKS)} 件を投入")
    for task in DUMMY_TASKS:
        client.pages.create(
            parent={"database_id": TASK_DB_ID},
            properties={
                "タスク名": {
                    "title": [{"text": {"content": task["タスク名"]}}]
                },
                "担当者": {
                    "rich_text": [{"text": {"content": task["担当者"]}}]
                },
                "ステータス": {
                    "select": {"name": task["ステータス"]}
                },
                "ストーリーポイント": {
                    "number": task["ストーリーポイント"]
                },
                "使用スキル": {
                    "rich_text": [{"text": {"content": task["使用スキル"]}}]
                },
                "実行結果・学び": {
                    "rich_text": [{"text": {"content": task["実行結果・学び"]}}]
                },
            },
        )
        print(f"  OK: [{task['ステータス']}] {task['タスク名'][:35]} — {task['担当者']} / {task['ストーリーポイント']}pt")

    section("完了: Notionのタスク管理DBを確認してください")


if __name__ == "__main__":
    main()
