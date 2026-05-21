"""Ingest 実行スクリプト.

Notion / Slack のデータを Cosmos DB に取り込む。

実行順序（deps あり）:
  1. Notion → members     （氏名→emailマップを構築）
  2. Notion → projects    （タスクネスト）
  3. Notion → meetings    （全文 + LLM要約 + member_analyses[]）
  4. Slack  → members.slack_vlog
  5. Slack  → slack_channels

実行:
  python -m ingest.run_ingest

事前条件:
  - scripts/setup_cosmosdb.py を実行済み
  - .env に全キーが設定済み
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client as NotionClient
from slack_sdk import WebClient as SlackClient
from openai import AzureOpenAI
from azure.cosmos import CosmosClient

from ingest.notion_ingest import ingest_members, ingest_project, ingest_meetings
from ingest.slack_ingest import ingest_slack_vlogs, ingest_slack_channels

# ================================================================
# Notion ID 設定（取り込み対象）
# ================================================================

MEMBER_DS_ID = "367c7942-de09-8026-af72-000b072dfb23"

PROJECTS = [
    {
        "page_id":    "366c7942-de09-8092-9a75-e59d205d94d0",  # 次世代 LLM Agent 基盤開発
        "task_ds_id": "367c7942-de09-80f0-a785-000b74ddc0fd",
        "mtg_ds_id":  "367c7942-de09-8037-8cf9-000b49c08892",
    },
]

DATABASE_NAME = "talentscope"


def main() -> int:
    load_dotenv()

    conn_str   = os.getenv("COSMOS_CONNECTION_STRING")
    notion_tk  = os.getenv("NOTION_API_KEY")
    slack_tk   = os.getenv("SLACK_BOT_OAUTH_TOKEN")
    aoai_key   = os.getenv("AZURE_OPENAI_API_KEY")
    aoai_ep    = os.getenv("AZURE_OPENAI_ENDPOINT")
    chat_dep   = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o")

    missing = [k for k, v in {
        "COSMOS_CONNECTION_STRING":  conn_str,
        "NOTION_API_KEY":            notion_tk,
        "SLACK_BOT_OAUTH_TOKEN":     slack_tk,
        "AZURE_OPENAI_API_KEY":      aoai_key,
        "AZURE_OPENAI_ENDPOINT":     aoai_ep,
    }.items() if not v]
    if missing:
        for k in missing:
            print(f"NG: {k} が .env に見つかりません")
        return 1

    # クライアント初期化
    cosmos = CosmosClient.from_connection_string(conn_str)
    db = cosmos.get_database_client(DATABASE_NAME)
    c_members  = db.get_container_client("members")
    c_projects = db.get_container_client("projects")
    c_meetings = db.get_container_client("meetings")
    c_slack    = db.get_container_client("slack_channels")

    notion = NotionClient(auth=notion_tk)
    slack  = SlackClient(token=slack_tk)
    openai = AzureOpenAI(
        api_key=aoai_key,
        azure_endpoint=aoai_ep,
        api_version="2024-12-01-preview",
    )

    print("=" * 55)
    print("TalentScope Ingest 開始")
    print(f"  chat deployment: {chat_dep}")
    print("=" * 55)

    # 1. メンバー（氏名→emailマップを構築）
    name_email_map = ingest_members(notion, c_members, MEMBER_DS_ID)

    # 2. プロジェクト + 3. 議事録
    for proj in PROJECTS:
        ingest_project(
            notion, c_projects,
            proj["page_id"], proj["task_ds_id"],
            name_email_map,
        )
        ingest_meetings(
            notion, c_meetings,
            proj["mtg_ds_id"], proj["page_id"],
            name_email_map, openai, chat_dep,
        )

    # 4. Slack vlog → members 更新
    ingest_slack_vlogs(slack, c_members, name_email_map)

    # 5. Slack チャンネル
    ingest_slack_channels(slack, c_slack, name_email_map)

    print("\n" + "=" * 55)
    print("Ingest 完了")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    sys.exit(main())
