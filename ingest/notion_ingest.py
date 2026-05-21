"""Notion → Cosmos DB 取り込みモジュール.

公開 API:
  ingest_members(notion, cosmos_members, member_ds_id) -> name_email_map
  ingest_project(notion, cosmos_projects, page_id, task_ds_id, name_email_map)
  ingest_meetings(notion, cosmos_meetings, mtg_ds_id, project_page_id,
                  name_email_map, openai_client)

Notion の取り込みは必ず members → projects → meetings の順で実行する。
（氏名→emailマップが後続の前提になるため）
"""
import json
import re
from datetime import datetime, timezone
from typing import Any


# ================================================================
# テキスト抽出ヘルパー
# ================================================================

def _join_rich_text(items: list) -> str:
    return "".join(t.get("text", {}).get("content", "") for t in items)


def get_rich_text(props: dict, key: str) -> str:
    return _join_rich_text(props.get(key, {}).get("rich_text", []))


def get_title(props: dict, key: str) -> str:
    return _join_rich_text(props.get(key, {}).get("title", []))


def get_select(props: dict, key: str) -> str:
    """select 型と status 型の両方に対応する。"""
    prop = props.get(key, {})
    for field in ("select", "status"):
        val = prop.get(field)
        if val and isinstance(val, dict):
            return val.get("name", "")
    return ""


def split_skills(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,、，]", s) if x.strip()]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ================================================================
# Notion ページネーション
# ================================================================

def query_all(notion, ds_id: str) -> list[dict]:
    """data_sources.query を全件取得する（ページネーション対応）。"""
    results, cursor = [], None
    while True:
        kwargs: dict[str, Any] = {"data_source_id": ds_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def list_blocks(notion, page_id: str) -> list[dict]:
    """blocks.children.list を全件取得する（ページネーション対応）。"""
    results, cursor = [], None
    while True:
        kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.blocks.children.list(**kwargs)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def get_page_title(page: dict) -> str:
    """ページオブジェクトからタイトルを取得する（プロパティ名不問）。"""
    for _key, prop in page.get("properties", {}).items():
        if prop.get("type") == "title":
            return _join_rich_text(prop.get("title", []))
    return ""


# ================================================================
# プロジェクト基本情報パーサ（ページ冒頭の「ラベル: 値」形式）
# ================================================================

def parse_project_info(notion, page_id: str) -> dict:
    """プロジェクトページ冒頭の規約フォーマットを解析して dict を返す。

    規約フォーマット（段落ブロック）:
      概要: ...
      期間: 2026-05-01 〜 2026-06-30
      ステータス: 進行中
      必要スキル: Python, Azure, RAG
      メンバー: 田中 誠,テックリード,2026-05-01,2026-06-30
      メンバー: 前田 彩,AIコアリード,2026-05-01,2026-06-30
    """
    blocks = list_blocks(notion, page_id)
    info: dict[str, Any] = {}

    for block in blocks:
        btype = block.get("type", "")
        rich_texts = block.get(btype, {}).get("rich_text", [])
        text = _join_rich_text(rich_texts).strip()
        if not text:
            continue
        for line in text.splitlines():
            if ":" not in line:
                continue
            label, _, value = line.partition(":")
            label, value = label.strip(), value.strip()
            if label == "概要":
                info["overview"] = value
            elif label == "期間":
                info["period"] = _parse_period(value)
            elif label == "ステータス":
                info["status"] = value
            elif label == "必要スキル":
                info["required_skills"] = split_skills(value)
            elif label == "メンバー":
                parts = [p.strip() for p in value.split(",")]
                if parts:
                    info.setdefault("assignments_raw", []).append({
                        "name":       parts[0],
                        "role":       parts[1] if len(parts) > 1 else "",
                        "start_date": parts[2] if len(parts) > 2 else "",
                        "end_date":   parts[3] if len(parts) > 3 else "",
                    })

    return info


def _parse_period(s: str) -> dict:
    for sep in (" 〜 ", "〜", " ~ ", "~", " - "):
        if sep in s:
            parts = s.split(sep, 1)
            return {"start": parts[0].strip(), "end": parts[1].strip()}
    return {"start": s.strip(), "end": None}


# ================================================================
# 議事録 LLM 分析
# ================================================================

_ANALYSIS_SYSTEM = """\
あなたは会議の議事録を分析する人事分析AIです。
与えられた議事録から、参加者ごとの能力・性格傾向と会議全体の要約を抽出します。
必ず指定のJSON形式のみで回答してください。
"""

_ANALYSIS_USER_TMPL = """\
## 会議情報
タイトル: {title}
種別: {mtg_type}
参加者: {participants}

## 議事録本文
{body}

## 出力形式（JSONのみ）
{{
  "overall_summary": "会議全体の要約（2〜3文。決定事項・主な議論を含める）",
  "member_analyses": [
    {{
      "member_name": "氏名（参加者リストに含まれる名前のみ）",
      "proposal_ability": "施策・アイデアの提案力（発言が確認できた内容を具体的に）",
      "logical_thinking": "論理的思考力・議論の組み立て方の観察",
      "facilitation": "まとめ・ファシリテーション・議論整理の観察",
      "technical_depth": "技術的な深さ・専門性の観察",
      "personality_notes": "性格傾向・コミュニケーションスタイルの観察"
    }}
  ]
}}

注意: 発言が確認できたメンバーのみ member_analyses に含めること。発言なしは省略。
"""


def _analyze_meeting(
    openai_client,
    chat_deployment: str,
    title: str,
    mtg_type: str,
    participant_names: list[str],
    body: str,
) -> dict:
    """LLMで議事録を分析し、overall_summary と member_analyses[] を返す。"""
    user_msg = _ANALYSIS_USER_TMPL.format(
        title=title,
        mtg_type=mtg_type,
        participants="、".join(participant_names) if participant_names else "（不明）",
        body=body if body.strip() else "（本文なし）",
    )

    resp = openai_client.chat.completions.create(
        model=chat_deployment,
        messages=[
            {"role": "system", "content": _ANALYSIS_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"overall_summary": raw, "member_analyses": []}


# ================================================================
# 公開 API
# ================================================================

def ingest_members(
    notion,
    cosmos_members,
    member_ds_id: str,
) -> dict[str, str]:
    """メンバーDB を members コンテナに取り込む。

    Returns:
        name_email_map: {氏名: email} の辞書（後続処理で名寄せに使う）
    """
    print("\n--- [1/3] メンバー取り込み ---")
    rows = query_all(notion, member_ds_id)
    name_email_map: dict[str, str] = {}

    for row in rows:
        props = row["properties"]
        name = get_title(props, "名前")
        email = get_rich_text(props, "email")
        if not email:
            print(f"  WARN: email なしのメンバーをスキップ: {name!r}")
            continue

        doc = {
            "id": email,
            "member_id": email,
            "type": "member",
            "name": name,
            "email": email,
            "role": get_select(props, "役職"),
            "skills": split_skills(get_rich_text(props, "スキル")),
            "years_experience": props.get("経験年数", {}).get("number") or 0,
            "monthly_cost": props.get("月次コスト", {}).get("number") or 0,
            "note": get_rich_text(props, "一言メモ"),
            "source": {"notion_page_id": row["id"], "synced_at": now_iso()},
        }
        cosmos_members.upsert_item(doc)
        name_email_map[name] = email
        print(f"  + {name} ({email})")

    print(f"OK: メンバー {len(name_email_map)} 名を取り込み")
    return name_email_map


def ingest_project(
    notion,
    cosmos_projects,
    project_page_id: str,
    task_ds_id: str,
    name_email_map: dict[str, str],
) -> None:
    """プロジェクトページ + タスクDB を projects コンテナに取り込む。"""
    page = notion.pages.retrieve(page_id=project_page_id)
    project_name = get_page_title(page)
    print(f"\n--- [2/3] プロジェクト取り込み: {project_name} ---")

    project_info = parse_project_info(notion, project_page_id)

    # assignments_raw（氏名ベース）を member_id（email）に解決
    assignments: list[dict] = []
    for raw in project_info.get("assignments_raw", []):
        member_id = name_email_map.get(raw["name"], raw["name"])
        if member_id == raw["name"]:
            print(f"  WARN: メンバー '{raw['name']}' のemail が未解決")
        assignments.append({
            "member_id":  member_id,
            "role":       raw["role"],
            "start_date": raw["start_date"],
            "end_date":   raw["end_date"],
        })
        print(f"  assign: {raw['name']} ({raw['role']}) {raw['start_date']}〜{raw['end_date']}")

    tasks_raw = query_all(notion, task_ds_id)
    task_docs: list[dict] = []
    member_ids: set[str] = set()

    for task in tasks_raw:
        props = task["properties"]
        assignee_name = get_rich_text(props, "担当者")
        assignee_email = name_email_map.get(assignee_name)
        if assignee_email:
            member_ids.add(assignee_email)

        task_doc = {
            "task_id": task["id"],
            "name": get_title(props, "タスク名"),
            "assignee": assignee_email or assignee_name,
            "status": get_select(props, "ステータス"),
            "story_points": props.get("ストーリーポイント", {}).get("number") or 0,
            "skills_used": split_skills(get_rich_text(props, "使用スキル")),
            "result_note": get_rich_text(props, "実行結果・学び"),
        }
        if not assignee_email:
            print(f"  WARN: 担当者 '{assignee_name}' のemail が未解決 (task: {task_doc['name'][:30]})")
        task_docs.append(task_doc)
        print(f"  task: [{task_doc['status']}] {task_doc['name'][:40]} / {assignee_name}")

    project_doc = {
        "id": project_page_id,
        "project_id": project_page_id,
        "type": "project",
        "name": project_name,
        "overview": project_info.get("overview", ""),
        "required_skills": project_info.get("required_skills", []),
        "period": project_info.get("period", {}),
        "status": project_info.get("status", ""),
        "assignments": assignments,
        "member_ids": [a["member_id"] for a in assignments] or list(member_ids),
        "tasks": task_docs,
        "source": {"project_page_id": project_page_id, "synced_at": now_iso()},
    }
    cosmos_projects.upsert_item(project_doc)
    print(f"OK: プロジェクト '{project_name}' / タスク {len(task_docs)} 件を取り込み")


def ingest_meetings(
    notion,
    cosmos_meetings,
    mtg_ds_id: str,
    project_page_id: str,
    name_email_map: dict[str, str],
    openai_client,
    chat_deployment: str,
) -> None:
    """議事録DB を meetings コンテナに取り込む。

    1会議 = 1ドキュメント。全文 + LLM生成の overall_summary + member_analyses[] を保存する。
    チャンク分割・ベクトル埋め込みは行わない。
    """
    print("\n--- [3/3] 議事録取り込み ---")
    meetings = query_all(notion, mtg_ds_id)

    for mtg in meetings:
        meeting_id = mtg["id"]
        props = mtg["properties"]
        title = get_title(props, "タイトル")
        date = (props.get("日付", {}).get("date") or {}).get("start", "")
        mtg_type = get_select(props, "種別")
        body = get_rich_text(props, "本文")

        participant_names = [
            p.strip()
            for p in re.split(r"[,、，]", get_rich_text(props, "参加者"))
            if p.strip()
        ]
        participant_ids = [
            name_email_map.get(name, name) for name in participant_names
        ]

        print(f"  [{mtg_type}] {title} → LLM分析中...")
        analysis = _analyze_meeting(
            openai_client, chat_deployment,
            title, mtg_type, participant_names, body,
        )

        # member_analyses に member_id を付加
        for entry in analysis.get("member_analyses", []):
            name = entry.get("member_name", "")
            entry["member_id"] = name_email_map.get(name, name)

        doc = {
            "id": meeting_id,
            "meeting_id": meeting_id,
            "project_id": project_page_id,
            "type": "meeting",
            "title": title,
            "date": date,
            "meeting_type": mtg_type,
            "participants": participant_ids,
            "participant_names": participant_names,
            "full_text": body,
            "overall_summary": analysis.get("overall_summary", ""),
            "member_analyses": analysis.get("member_analyses", []),
            "source": {"notion_page_id": meeting_id, "synced_at": now_iso()},
        }
        cosmos_meetings.upsert_item(doc)
        n = len(analysis.get("member_analyses", []))
        print(f"  OK: {title} / member_analyses {n} 名分")

    print(f"OK: 議事録 {len(meetings)} 件を取り込み")
