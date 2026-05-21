"""Jira API 接続検証スクリプト（フェーズ1）.

段階的に Jira API を叩き、各ステップの結果を標準出力に表示する。
  1. .env から JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_KEY を読み込む
  2. /rest/api/3/myself でトークン有効性を確認
  3. /rest/api/3/project でプロジェクト一覧を取得
  4. 最初のプロジェクトの Issue を取得（JQL）
  5. Issue ごとのベロシティ情報（ストーリーポイント）を表示
"""

import os
import sys
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def get_base_url(raw: str) -> str:
    """URLからスキーム+ホストだけ取り出す（/jira/for-you 等のパスを除去）。"""
    parsed = urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}"


def main() -> int:
    section("STEP 1: .env 読み込み")
    load_dotenv()
    raw_url   = os.getenv("JIRA_BASE_URL")
    email     = os.getenv("JIRA_EMAIL")
    api_key   = os.getenv("JIRA_API_KEY")

    missing = [k for k, v in {
        "JIRA_BASE_URL": raw_url,
        "JIRA_EMAIL": email,
        "JIRA_API_KEY": api_key,
    }.items() if not v]
    if missing:
        print(f"NG: 以下のキーが .env に見つかりません: {missing}")
        return 1

    base_url = get_base_url(raw_url)
    print(f"OK: 設定取得")
    print(f"    base_url : {base_url}  (元の値: {raw_url})")
    print(f"    email    : {email}")
    print(f"    api_key  : {api_key[:20]}...")

    auth = HTTPBasicAuth(email, api_key)
    headers = {"Accept": "application/json"}

    section("STEP 2: 認証確認 GET /rest/api/3/myself")
    resp = requests.get(f"{base_url}/rest/api/3/myself", auth=auth, headers=headers)
    if resp.status_code != 200:
        print(f"NG: 認証失敗 (status={resp.status_code})")
        print(f"    → メールアドレスとAPIトークンを確認してください")
        print(f"    レスポンス: {resp.text[:200]}")
        return 1
    me = resp.json()
    print(f"OK: 認証成功")
    print(f"    displayName  : {me.get('displayName')}")
    print(f"    emailAddress : {me.get('emailAddress')}")
    print(f"    accountId    : {me.get('accountId')}")

    section("STEP 3: プロジェクト一覧 GET /rest/api/3/project")
    resp = requests.get(f"{base_url}/rest/api/3/project", auth=auth, headers=headers)
    if resp.status_code != 200:
        print(f"NG: プロジェクト取得失敗 (status={resp.status_code})")
        print(f"    レスポンス: {resp.text[:200]}")
        return 1
    projects = resp.json()
    if not projects:
        print("OK: プロジェクトが0件（Jiraにプロジェクトが存在しない）")
        section("検証完了: Jira 接続 OK（プロジェクト未作成）")
        return 0
    print(f"OK: プロジェクト {len(projects)} 件取得")
    for p in projects[:5]:
        print(f"    - [{p['key']}] {p['name']}")

    section("STEP 4: Issue 取得（JQL: 最初のプロジェクトの最新10件）")
    first_key = projects[0]["key"]
    jql = f"project = {first_key} ORDER BY created DESC"
    resp = requests.get(
        f"{base_url}/rest/api/3/search/jql",
        auth=auth,
        headers=headers,
        params={"jql": jql, "maxResults": 10, "fields": "summary,assignee,status,story_points,customfield_10016"},
    )
    if resp.status_code != 200:
        print(f"NG: Issue 取得失敗 (status={resp.status_code})")
        print(f"    レスポンス: {resp.text[:200]}")
        return 1
    data = resp.json()
    issues = data.get("issues", [])
    print(f"OK: Issue {data.get('total', 0)} 件中 {len(issues)} 件取得")

    section("STEP 5: Issue 詳細（ベロシティ情報）")
    if not issues:
        print("（Issueが0件）")
    for issue in issues:
        fields = issue["fields"]
        summary  = fields.get("summary", "(タイトルなし)")
        assignee = (fields.get("assignee") or {}).get("displayName", "未アサイン")
        status   = (fields.get("status") or {}).get("name", "不明")
        points   = fields.get("customfield_10016")  # ストーリーポイント
        sp_str   = f"{points}pt" if points is not None else "ポイントなし"
        print(f"  [{issue['key']}] {summary[:40]}")
        print(f"    担当: {assignee} / ステータス: {status} / ベロシティ: {sp_str}")

    section("検証完了: Jira 接続 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
