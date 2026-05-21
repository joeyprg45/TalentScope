"""Slack → Cosmos DB 取り込みモジュール.

公開 API:
  ingest_slack_vlogs(slack, cosmos_members, name_email_map)
  ingest_slack_channels(slack, cosmos_slack_channels, name_email_map)

チャンネル設定は TWEET_CHANNEL_MAP / SLACK_CHANNEL_MAP で管理する。
新しいチャンネルを追加する場合はここを更新する。
"""
import re
from datetime import datetime, timezone

# ================================================================
# チャンネル設定
# ================================================================

# 個人 vlog チャンネル → members.slack_vlog に格納
TWEET_CHANNEL_MAP: dict[str, dict] = {
    "C0B51HALTNV": {"name": "tweet_kobayashi", "member_email": "kobayashi@abc.com"},
    "C0B4TB12T7D": {"name": "tweet_maeda",     "member_email": "maeda@abc.com"},
    "C0B4JGP19NX": {"name": "tweet_sato",      "member_email": "sato@abc.com"},
}

# プロジェクト・全社チャンネル → slack_channels コンテナに格納
SLACK_CHANNEL_MAP: dict[str, dict] = {
    "C0B4UBF7JTE": {
        "name": "all-abctechnologies",
        "kind": "company",
        "project_id": None,
    },
    "C0B5C36EL02": {
        "name": "proj-llm-agent-infra",
        "kind": "project",
        "project_id": "366c7942-de09-8092-9a75-e59d205d94d0",
    },
}

# 除外するシステムメッセージのサブタイプ（bot_message は除外しない）
_SYSTEM_SUBTYPES = frozenset({
    "channel_join", "channel_leave", "channel_purpose",
    "channel_name", "channel_archive", "channel_unarchive",
})


# ================================================================
# ユーティリティ
# ================================================================

def _ts_to_iso(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ts


def _fetch_messages(slack, channel_id: str) -> list[dict]:
    """conversations.history を全件取得する（ページネーション対応）。"""
    messages, cursor = [], None
    while True:
        kwargs: dict = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = slack.conversations_history(**kwargs)
        if not resp["ok"]:
            print(f"  WARN: conversations.history 失敗 ({resp.get('error')}) ch={channel_id}")
            break
        messages.extend(resp.get("messages", []))
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return messages


def _extract_speaker(msg: dict) -> str:
    """メッセージから発言者名を返す。

    Bot 投稿（chat:write.customize で username オーバーライド）は
    username フィールドを優先する。
    フォールバック: 本文先頭の '[氏名] ' プレフィックスを試みる。
    """
    username = msg.get("username", "")
    if username:
        return username
    text = msg.get("text", "")
    m = re.match(r"^\[(.+?)\]\s", text)
    if m:
        return m.group(1)
    return msg.get("user", "")


def _is_system_msg(msg: dict) -> bool:
    return msg.get("subtype", "") in _SYSTEM_SUBTYPES


# ================================================================
# 公開 API
# ================================================================

def ingest_slack_vlogs(
    slack,
    cosmos_members,
    name_email_map: dict[str, str],
) -> None:
    """tweet_* チャンネルのメッセージを members コンテナの slack_vlog に格納する。"""
    print("\n--- Slack vlog 取り込み ---")

    for channel_id, config in TWEET_CHANNEL_MAP.items():
        member_email = config["member_email"]
        channel_name = config["name"]

        messages = _fetch_messages(slack, channel_id)
        posts = [
            {
                "ts": msg["ts"],
                "posted_at": _ts_to_iso(msg["ts"]),
                "text": msg.get("text", ""),
            }
            for msg in messages
            if not _is_system_msg(msg)
        ]
        posts.sort(key=lambda p: p["ts"])  # 時系列順

        try:
            member = cosmos_members.read_item(
                item=member_email, partition_key=member_email
            )
            member["slack_vlog"] = {
                "channel": channel_name,
                "channel_id": channel_id,
                "posts": posts,
            }
            cosmos_members.upsert_item(member)
            print(f"  OK: #{channel_name} → {member_email} / {len(posts)} 件")
        except Exception as e:
            print(f"  WARN: {member_email} のメンバー document が見つかりません ({e})")


def ingest_slack_channels(
    slack,
    cosmos_slack_channels,
    name_email_map: dict[str, str],
) -> None:
    """プロジェクト ch・全社 ch のメッセージを slack_channels コンテナに投入する。"""
    print("\n--- Slack チャンネル取り込み ---")

    for channel_id, config in SLACK_CHANNEL_MAP.items():
        channel_name = config["name"]
        channel_kind = config["kind"]
        project_id = config["project_id"]

        messages = _fetch_messages(slack, channel_id)
        upserted = 0

        for msg in messages:
            if _is_system_msg(msg):
                continue

            speaker = _extract_speaker(msg)
            speaker_id = name_email_map.get(speaker, speaker)

            cosmos_slack_channels.upsert_item({
                "id": f"{channel_id}::{msg['ts']}",
                "channel_id": channel_id,
                "type": "slack_message",
                "channel_name": channel_name,
                "channel_kind": channel_kind,
                "project_id": project_id,
                "speaker": speaker,
                "speaker_id": speaker_id,
                "ts": msg["ts"],
                "posted_at": _ts_to_iso(msg["ts"]),
                "text": msg.get("text", ""),
            })
            upserted += 1

        print(f"  OK: #{channel_name} / {upserted} 件投入")
