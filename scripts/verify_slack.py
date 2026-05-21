"""Slack API 接続検証スクリプト（フェーズ1）.

段階的に Slack API を叩き、各ステップの結果を標準出力に表示する。
  1. .env から SLACK_API_KEY を読み込む
  2. auth.test() でトークン有効性を確認
  3. conversations.list で対象チャンネルの ID を解決
  4. users.list で ユーザーID -> 表示名 の辞書を作る
  5. conversations.history で各チャンネルのメッセージを取得し「発信者名 + 本文」を表示
"""

import os
import sys

# Windows のコンソール既定エンコーディング(cp932)対策
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 検証対象チャンネル（ユーザー指定）
TARGET_CHANNELS = [
    "all-abctechnologies",
    "tweet_kobayashi",
    "tweet_maeda",
    "tweet_sato",
]


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def list_all_channels(client: WebClient) -> dict:
    """全チャンネル(public/private)を取得し、name -> channel dict を返す。"""
    channels = {}
    cursor = None
    while True:
        resp = client.conversations_list(
            types="public_channel,private_channel",
            limit=200,
            cursor=cursor,
        )
        for ch in resp.get("channels", []):
            channels[ch["name"]] = ch
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return channels


def build_user_map(client: WebClient) -> dict:
    """users.list を一度だけ叩いて ユーザーID -> 表示名 の辞書を作る。"""
    user_map = {}
    cursor = None
    while True:
        resp = client.users_list(limit=200, cursor=cursor)
        for u in resp.get("members", []):
            profile = u.get("profile", {})
            name = (
                profile.get("real_name")
                or profile.get("display_name")
                or u.get("name")
                or u["id"]
            )
            user_map[u["id"]] = name
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return user_map


def main() -> int:
    section("STEP 1: .env 読み込み")
    load_dotenv()
    token = os.getenv("SLACK_BOT_OAUTH_TOKEN")
    if not token:
        print("NG: SLACK_BOT_OAUTH_TOKEN が .env に見つかりません")
        return 1
    print(f"OK: トークン取得（先頭: {token[:9]}...）")

    client = WebClient(token=token)

    section("STEP 2: トークン有効性チェック auth.test()")
    try:
        auth = client.auth_test()
        print(f"OK: トークン有効 / team: {auth.get('team')} / bot: {auth.get('user')}")
    except SlackApiError as e:
        print(f"NG: トークン不正の可能性 (error={e.response.get('error')})")
        return 1

    section("STEP 3: チャンネル一覧取得・対象IDの解決")
    try:
        channels = list_all_channels(client)
    except SlackApiError as e:
        err = e.response.get("error")
        print(f"NG: conversations.list 失敗 (error={err})")
        if err == "missing_scope":
            print("    → スコープ channels:read / groups:read を追加して再インストール")
        return 1
    print(f"OK: ワークスペースのチャンネル {len(channels)} 件を取得")

    targets = {}
    for name in TARGET_CHANNELS:
        ch = channels.get(name)
        if ch:
            mark = "" if ch.get("is_member") else "  ⚠ Bot未参加"
            print(f"  - #{name} / id={ch['id']}{mark}")
            targets[name] = ch
        else:
            print(f"  - #{name} / ✗ 見つからない（名前違い or Bot未参加で非表示）")

    section("STEP 4: ユーザー辞書の作成 users.list")
    try:
        user_map = build_user_map(client)
        print(f"OK: ユーザー {len(user_map)} 件を ID→名前 で辞書化")
    except SlackApiError as e:
        print(f"NG: users.list 失敗 (error={e.response.get('error')})")
        print("    → スコープ users:read を追加して再インストール")
        return 1

    section("STEP 5: メッセージ取得（発信者名 + 本文）")
    for name, ch in targets.items():
        print(f"\n--- #{name} ---")
        try:
            resp = client.conversations_history(channel=ch["id"], limit=10)
        except SlackApiError as e:
            err = e.response.get("error")
            print(f"  NG: conversations.history 失敗 (error={err})")
            if err == "not_in_channel":
                print(f"     → Slackで #{name} を開き /invite でBotを招待してください")
            continue
        msgs = resp.get("messages", [])
        if not msgs:
            print("  (メッセージ無し)")
            continue
        for m in msgs:
            uid = m.get("user") or m.get("bot_id", "")
            who = user_map.get(uid, uid or "(不明)")
            text = (m.get("text", "") or "").replace("\n", " ")[:80]
            print(f"  [{who}] {text}")

    section("検証完了: Slack 接続 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
