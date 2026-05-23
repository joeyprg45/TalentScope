"""TalentScope Streamlit UI.

Azure Portal 風の3ペインレイアウト:
  左: ナビゲーションサイドバー
  中央: コンテンツ（メンバーDB / プロジェクト / カレンダー / レポート）
  右: 常時チャットパネル
"""
from __future__ import annotations

import asyncio
import queue
import threading
import unicodedata
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from openai import AsyncAzureOpenAI
from semantic_kernel.contents.chat_history import ChatHistory
from streamlit_calendar import calendar

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.orchestrator import AgentMode, TalentScopeOrchestrator

# ─────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TalentScope",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background-color: #1b2430; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label { color: #c8d0e0 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: transparent; border: none; text-align: left;
    font-size: 0.92rem; padding: 0.45rem 0.8rem;
    color: #c8d0e0; border-radius: 6px; width: 100%;
}
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,0.1); }
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(0,120,212,0.75); color: #fff;
}

/* ── Chat panel column ── */
div[data-testid="column"]:last-child {
    background-color: #f7f9fc;
    border-left: 1px solid #dde3ef;
    padding: 0 1rem !important;
}

/* ── Chat header ── */
.chat-header {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.75rem 0 0.6rem 0;
    border-bottom: 1px solid #e0e6ef; margin-bottom: 0.5rem;
}
.online-dot {
    width: 9px; height: 9px; background: #22c55e;
    border-radius: 50%; flex-shrink: 0;
    animation: pulse-green 2s infinite;
}
@keyframes pulse-green {
    0%,100% { box-shadow: 0 0 0 2px rgba(34,197,94,.25); }
    50%      { box-shadow: 0 0 0 5px rgba(34,197,94,.08); }
}

/* ── Message bubbles (Chrome 105+) ── */
[data-testid="stChatMessage"] {
    padding: 0.5rem 0.7rem !important;
    margin-bottom: 0.15rem;
    border-radius: 12px;
    gap: 0.5rem !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse;
    background-color: #e8f0fe !important;
    border-radius: 12px 2px 12px 12px;
    margin-left: 1.2rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #ffffff !important;
    border-radius: 2px 12px 12px 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,.07);
    margin-right: 1.2rem;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
    border-radius: 24px !important;
    border: 1.5px solid #c8d4e8 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,.06);
    margin-top: 0.4rem;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #0078d4 !important;
    box-shadow: 0 0 0 3px rgba(0,120,212,.15) !important;
}

/* ── Scrollable message container ── */
div[data-testid="stVerticalBlockBorderWrapper"][style*="height"] {
    overflow-y: auto;
    scroll-behavior: smooth;
}

/* ── Axis selection bar ── */
.axis-info-bar {
    background: #fff8e1; border: 1px solid #ffd54f;
    border-radius: 8px; padding: 0.4rem 0.75rem;
    font-size: 0.82rem; color: #b45309; margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# Constants (reused from app.py)
# ─────────────────────────────────────────────────────────
_AXIS_LABELS = {
    "ability": "能力重視",
    "cost":    "コスト重視",
    "growth":  "育成・チャレンジ重視",
    "synergy": "チームワーク・シナジー重視",
}

# ─────────────────────────────────────────────────────────
# Helper functions (same logic as app.py, no Chainlit deps)
# ─────────────────────────────────────────────────────────
def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace(" ", "").replace("　", "").lower()


def _lookup_member(query: str, cosmos: CosmosContainers) -> Optional[tuple[str, str]]:
    items = list(cosmos.members.query_items(
        query="SELECT c.member_id, c.name FROM c",
        enable_cross_partition_query=True,
    ))
    q = query.strip()
    for item in items:
        if item.get("member_id", "").lower() == q.lower():
            return item["member_id"], item["name"]
    q_norm = _normalize(q)
    for item in items:
        mn = _normalize(item.get("name", ""))
        if mn and (q_norm in mn or mn in q_norm):
            return item["member_id"], item["name"]
    return None


def _lookup_project(query: str, cosmos: CosmosContainers) -> Optional[tuple[str, str]]:
    items = list(cosmos.projects.query_items(
        query="SELECT c.project_id, c.name FROM c",
        enable_cross_partition_query=True,
    ))
    q = query.strip().lower()
    for item in items:
        name = item.get("name", "").lower()
        if q in name or name in q:
            return item["project_id"], item["name"]
    return None


def _list_member_names(cosmos: CosmosContainers) -> list[str]:
    return [i["name"] for i in cosmos.members.query_items(
        query="SELECT c.name FROM c", enable_cross_partition_query=True,
    )]


def _list_project_names(cosmos: CosmosContainers) -> list[str]:
    return [i["name"] for i in cosmos.projects.query_items(
        query="SELECT c.name FROM c", enable_cross_partition_query=True,
    )]


async def _classify_intent_async(
    text: str, has_active_report: bool, last_msgs: list
) -> str:
    settings = AgentSettings.from_env()
    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    history_text = "\n".join(
        f"{m['role']}: {m['content'][:120]}" for m in last_msgs[-4:]
    )
    prompt = f"""あなたはタレントマネジメントアプリのルーティング分類器です。

コンテキスト:
- active_report: {has_active_report}  # レポートが表示中かどうか
- 直近の会話:
{history_text}

ユーザーメッセージ: "{text}"

ユーザーの意図を以下の4つから1つ選び、ラベルのみを返してください（説明不要）:
- skill_analysis : 特定メンバーのスキル分析を新規に依頼している
- assign_request : プロジェクトへの新規アサイン提案を依頼している
- refine         : 現在表示中のレポートの修正・変更を依頼している
- chat           : 上記以外（質問・会話・感想など）

回答:"""
    try:
        resp = await client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        label = resp.choices[0].message.content.strip().lower()
        if label in ("skill_analysis", "assign_request", "refine", "chat"):
            return label
    except Exception:
        pass
    return "chat"


def _classify_intent(text: str, has_active_report: bool, last_msgs: list) -> str:
    return asyncio.run(_classify_intent_async(text, has_active_report, last_msgs))


# ─────────────────────────────────────────────────────────
# Session initialisation
# ─────────────────────────────────────────────────────────
def _init_session() -> None:
    if "initialized" in st.session_state:
        return
    try:
        settings = AgentSettings.from_env()
        st.session_state.orchestrator = TalentScopeOrchestrator(settings)
        st.session_state.cosmos       = CosmosContainers(settings)
    except Exception as exc:
        st.error(f"❌ 初期化エラー: {exc}")
        st.stop()
    st.session_state.chat_history  = ChatHistory()
    st.session_state.messages      = []
    st.session_state.view          = "home"
    st.session_state.pending_id    = None
    st.session_state.pending_name  = None
    st.session_state.active_report = None
    st.session_state.chat_open     = True
    st.session_state.initialized   = True

# ─────────────────────────────────────────────────────────
# Async → sync streaming bridge
# ─────────────────────────────────────────────────────────
def _sync_stream(user_text: str):
    """Convert async SK generator to sync generator for st.write_stream."""
    q: queue.Queue[str | None] = queue.Queue()
    orch: TalentScopeOrchestrator = st.session_state.orchestrator
    hist: ChatHistory             = st.session_state.chat_history

    async def _producer() -> None:
        try:
            async for chunk in orch.chat(
                user_message=user_text,
                mode=AgentMode.BASE_CHAT,
                history=hist,
            ):
                q.put(chunk)
        except Exception as exc:
            q.put(f"\n\n❌ エラーが発生しました: {exc}")
        finally:
            q.put(None)

    threading.Thread(target=lambda: asyncio.run(_producer()), daemon=True).start()

    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield chunk

# ─────────────────────────────────────────────────────────
# Report helpers
# ─────────────────────────────────────────────────────────
def _run_report(mode: AgentMode, target_id: str, target_name: str, axis: str) -> None:
    with st.spinner(f"⏳ {target_name} のレポートを生成中..."):
        try:
            _summary, full_md = asyncio.run(
                st.session_state.orchestrator.generate_report(
                    mode=mode,
                    target_id=target_id,
                    target_name=target_name,
                    axis=axis,
                )
            )
        except Exception as exc:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ レポート生成エラー: {exc}",
            })
            return

    axis_label = _AXIS_LABELS.get(axis, axis)
    mode_label = "個人スキル分析" if mode == AgentMode.SKILL_ANALYSIS else f"アサイン提案（{axis_label}）"
    panel_name = f"{target_name} {mode_label}レポート"

    st.session_state.active_report = {
        "mode":        mode,
        "target_id":   target_id,
        "target_name": target_name,
        "axis":        axis,
        "content":     full_md,
        "panel_name":  panel_name,
        "mode_label":  mode_label,
    }
    st.session_state.pending_id   = None
    st.session_state.pending_name = None
    st.session_state.view         = "home"
    st.session_state.messages.append({
        "role":    "assistant",
        "content": f"✅ **{mode_label}レポート**を生成しました。中央パネルでご確認ください。",
    })

    # Push report into chat_history so follow-up chat has context
    hist: ChatHistory = st.session_state.chat_history
    hist.add_user_message(f"「{target_name}」の{mode_label}レポートを作成してください。")
    hist.add_assistant_message(
        f"以下の{mode_label}レポートを生成しました（対象: {target_name}）:\n\n{full_md}"
    )


def _run_refine(user_feedback: str) -> None:
    report = st.session_state.active_report
    with st.spinner("⏳ レポートを修正中..."):
        try:
            summary, full_md = asyncio.run(
                st.session_state.orchestrator.refine_report(
                    mode=report["mode"],
                    target_id=report["target_id"],
                    target_name=report["target_name"],
                    axis=report["axis"],
                    current_report_md=report["content"],
                    user_feedback=user_feedback,
                )
            )
        except Exception as exc:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ レポート修正エラー: {exc}",
            })
            return

    report["content"] = full_md
    st.session_state.active_report = report
    st.session_state.messages.append({
        "role":    "assistant",
        "content": f"✅ レポートを修正しました。\n\n**変更内容:** {summary}",
    })

    # Push refined report into chat_history so follow-up chat has updated context
    hist: ChatHistory = st.session_state.chat_history
    hist.add_user_message(f"先ほどのレポートを次のとおり修正してください: {user_feedback}")
    hist.add_assistant_message(
        f"レポートを修正しました（変更内容: {summary}）。最新版:\n\n{full_md}"
    )

# ─────────────────────────────────────────────────────────
# Input intent handler
# ─────────────────────────────────────────────────────────
def _handle_input(user_text: str) -> bool:
    """Route user input via LLM classification. Returns True when streaming needed."""
    cosmos = st.session_state.cosmos
    active_report = st.session_state.active_report

    intent = _classify_intent(
        user_text,
        has_active_report=bool(active_report),
        last_msgs=st.session_state.messages[-6:],
    )

    if intent == "refine" and active_report:
        _run_refine(user_text)
        return False

    if intent == "skill_analysis":
        member = _lookup_member(user_text, cosmos)
        if member:
            _run_report(AgentMode.SKILL_ANALYSIS, member[0], member[1], "ability")
        else:
            names = _list_member_names(cosmos)
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"メンバーが見つかりませんでした。\n\n**登録メンバー:** {', '.join(names)}",
            })
        return False

    if intent == "assign_request":
        project = _lookup_project(user_text, cosmos)
        if project:
            st.session_state.pending_id   = project[0]
            st.session_state.pending_name = project[1]
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"プロジェクト「**{project[1]}**」のアサイン提案を行います。提案軸を選んでください。",
            })
        else:
            names = _list_project_names(cosmos)
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"プロジェクトが見つかりませんでした。\n\n**登録プロジェクト:** {', '.join(names)}",
            })
        return False

    return True  # intent == "chat" → caller handles streaming

# ─────────────────────────────────────────────────────────
# Content views
# ─────────────────────────────────────────────────────────
def render_home() -> None:
    if st.session_state.active_report:
        report = st.session_state.active_report
        st.markdown(f"### {report['panel_name']}")
        st.divider()
        st.markdown(report["content"])
    else:
        st.markdown("## 🎯 TalentScope")
        st.markdown("**人事を動かすための AI HR アシスタント**")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("#### 👤 個人スキル分析")
                st.markdown("メンバーのスキル・経験・貢献履歴を分析")
                st.caption('例: 「佐藤健太のスキルを分析して」')
        with col2:
            with st.container(border=True):
                st.markdown("#### 📋 アサイン提案")
                st.markdown("プロジェクトに最適なチーム構成を AI が提案")
                st.caption('例: 「次世代LLMのアサインを決めて」')
        st.info("右のチャットパネルから質問できます。サイドバーのメニューからメンバー・プロジェクト一覧も確認できます。")


def render_members() -> None:
    cosmos = st.session_state.cosmos
    st.markdown("### 👥 メンバーDB")

    with st.spinner("データを読み込み中..."):
        items = list(cosmos.members.query_items(
            query="SELECT * FROM c WHERE c.type = 'member'",
            enable_cross_partition_query=True,
        ))

    col_search, col_skill = st.columns([2, 3])
    with col_search:
        search = st.text_input("名前で検索", placeholder="名前で検索...", label_visibility="collapsed")
    with col_skill:
        all_skills = sorted({s for m in items for s in m.get("skills", [])})
        selected_skills = st.multiselect("スキルで絞り込み", all_skills, label_visibility="collapsed")

    filtered = [
        m for m in items
        if (not search or search in m.get("name", ""))
        and (not selected_skills or all(s in m.get("skills", []) for s in selected_skills))
    ]

    if filtered:
        df = pd.DataFrame([{
            "名前":       m["name"],
            "役割":       m.get("role", ""),
            "スキル":     ", ".join(m.get("skills", [])),
            "経験年数":   m.get("years_experience", ""),
            "月次コスト": f"¥{m.get('monthly_cost', 0):,}",
        } for m in filtered])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    for m in filtered:
        with st.container(border=True):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"**{m['name']}** · {m.get('role', '')} · "
                    f"経験 {m.get('years_experience', '?')}年 · ¥{m.get('monthly_cost', 0):,}/月"
                )
                skills_md = "　".join(f"`{s}`" for s in m.get("skills", []))
                st.markdown(skills_md)
                if m.get("note"):
                    st.caption(m["note"])
            with col_btn:
                if st.button("👤 分析", key=f"skill_{m['member_id']}", use_container_width=True, type="primary"):
                    st.session_state.trigger = {
                        "type":        "skill",
                        "member_id":   m["member_id"],
                        "member_name": m["name"],
                    }
                    st.session_state.view = "home"
                    st.rerun()


def render_projects() -> None:
    cosmos = st.session_state.cosmos
    st.markdown("### 📋 プロジェクト一覧")

    with st.spinner("データを読み込み中..."):
        items = list(cosmos.projects.query_items(
            query="SELECT * FROM c WHERE c.type = 'project'",
            enable_cross_partition_query=True,
        ))

    status_icons = {"進行中": "🟢", "未着手": "🟡", "完了": "⚫"}

    for p in items:
        with st.container(border=True):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                icon = status_icons.get(p.get("status", ""), "⚪")
                period = p.get("period", {})
                st.markdown(f"**{icon} {p['name']}**")
                st.caption(
                    f"期間: {period.get('start', '?')} 〜 {period.get('end', '?')}　"
                    f"メンバー {len(p.get('member_ids', []))}名　状態: {p.get('status', '?')}"
                )
                skills_md = "　".join(f"`{s}`" for s in p.get("required_skills", []))
                st.markdown(f"必要スキル: {skills_md}")
                tasks = p.get("tasks", [])
                if tasks:
                    done = sum(1 for t in tasks if t.get("status") == "完了")
                    st.progress(done / len(tasks), text=f"タスク {done}/{len(tasks)} 完了")
            with col_btn:
                if st.button("📋 提案", key=f"assign_{p['project_id']}", use_container_width=True, type="primary"):
                    st.session_state.trigger = {
                        "type":         "assign_pending",
                        "project_id":   p["project_id"],
                        "project_name": p["name"],
                    }
                    st.session_state.view = "home"
                    st.rerun()


def render_calendar() -> None:
    cosmos = st.session_state.cosmos
    st.markdown("### 📅 カレンダー")

    with st.spinner("データを読み込み中..."):
        projects = list(cosmos.projects.query_items(
            query="SELECT c.project_id, c.name, c.period, c.status FROM c WHERE c.type = 'project'",
            enable_cross_partition_query=True,
        ))

    color_map = {
        "進行中": "#0078d4",
        "未着手": "#ffb900",
        "完了":   "#8a8886",
    }
    events = []
    for p in projects:
        period = p.get("period") or {}
        start, end = period.get("start"), period.get("end")
        if not (start and end):
            continue
        color = color_map.get(p.get("status", ""), "#c8c6c4")
        events.append({
            "id":              p["project_id"],
            "title":           p["name"],
            "start":           start,
            "end":             end,
            "backgroundColor": color,
            "borderColor":     color,
            "allDay":          True,
        })

    calendar_options = {
        "headerToolbar": {
            "left":   "prev,next today",
            "center": "title",
            "right":  "dayGridMonth,timeGridWeek,timeGridDay",
        },
        "initialView":  "dayGridMonth",
        "locale":       "ja",
        "firstDay":     0,
        "height":       700,
        "navLinks":     True,
        "editable":     False,
        "selectable":   True,
        "dayMaxEvents": 3,
        "buttonText": {
            "today": "今日",
            "month": "月",
            "week":  "週",
            "day":   "日",
        },
    }

    custom_css = """
    .fc-event-title { font-weight: 500; }
    .fc-toolbar-title { font-size: 1.2rem !important; }
    .fc-button { background-color: #0078d4 !important; border-color: #0078d4 !important; }
    .fc-button:hover { background-color: #106ebe !important; }
    .fc-day-today { background-color: #fff8e1 !important; }
    """

    state = calendar(
        events=events,
        options=calendar_options,
        custom_css=custom_css,
        key="main_calendar",
    )

    if state and state.get("eventClick"):
        ev = state["eventClick"]["event"]
        start_s = (ev.get("start") or "")[:10]
        end_s   = (ev.get("end")   or "")[:10]
        st.info(f"🔗 **{ev.get('title', '')}**  期間: {start_s} 〜 {end_s}")


def render_main() -> None:
    dispatch = {
        "home":     render_home,
        "members":  render_members,
        "projects": render_projects,
        "calendar": render_calendar,
    }
    dispatch.get(st.session_state.get("view", "home"), render_home)()

# ─────────────────────────────────────────────────────────
# Chat panel
# ─────────────────────────────────────────────────────────
def render_chat() -> None:
    # Handle trigger from member / project page buttons
    trigger = st.session_state.pop("trigger", None)
    if trigger:
        t = trigger["type"]
        if t == "skill":
            auto_msg = f"{trigger['member_name']}のスキルを分析して"
            st.session_state.messages.append({"role": "user", "content": auto_msg})
            _run_report(AgentMode.SKILL_ANALYSIS, trigger["member_id"], trigger["member_name"], "ability")
        elif t == "assign_pending":
            auto_msg = f"{trigger['project_name']}のアサインを決めて"
            st.session_state.messages.append({"role": "user", "content": auto_msg})
            st.session_state.pending_id   = trigger["project_id"]
            st.session_state.pending_name = trigger["project_name"]
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"プロジェクト「**{trigger['project_name']}**」のアサイン提案を行います。提案軸を選んでください。",
            })
        st.rerun()

    # ─ Polished header ─
    st.markdown("""
<div class="chat-header">
  <span class="online-dot"></span>
  <span style="font-weight:700;font-size:1rem;color:#1a2436;flex-grow:1">AIアシスタント</span>
  <span style="font-size:.72rem;color:#22c55e;font-weight:500">オンライン</span>
</div>""", unsafe_allow_html=True)

    # ─ Toolbar: close button only (width is adjusted via draggable splitter) ─
    _, tb_close = st.columns([10, 1])
    with tb_close:
        if st.button("✕", key="chat_close", use_container_width=True, help="チャットを閉じる"):
            st.session_state.chat_open = False
            st.rerun()

    # ─ Scrollable container: messages + axis buttons + pending stream ─
    with st.container(height=550, border=False):
        if not st.session_state.messages:
            st.markdown(
                '<div style="text-align:center;color:#94a3b8;padding:3rem 0;font-size:.9rem">'
                '💬 質問してみましょう<br>'
                '<span style="font-size:.8rem">例: 「田中さんのスキルを分析して」</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ─ Axis selection (inline after messages) ─
        if st.session_state.pending_id:
            st.markdown(
                f'<div class="axis-info-bar">📋 <b>{st.session_state.pending_name}</b> の提案軸を選択してください</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            for axis_key, label, col in [
                ("ability", "🎯 能力重視",    c1),
                ("cost",    "💰 コスト重視",  c2),
                ("growth",  "🌱 育成重視",    c1),
                ("synergy", "🤝 チームワーク", c2),
            ]:
                with col:
                    if st.button(label, key=f"axis_{axis_key}", use_container_width=True):
                        pid, pname = st.session_state.pending_id, st.session_state.pending_name
                        st.session_state.pending_id = None
                        st.session_state.messages.append({"role": "user", "content": label})
                        _run_report(AgentMode.ASSIGNMENT, pid, pname, axis_key)
                        st.rerun()

        # ─ Pending stream consumption (renders INSIDE container) ─
        pending = st.session_state.pop("pending_stream", None)
        if pending:
            with st.chat_message("assistant"):
                response = st.write_stream(_sync_stream(pending))
            st.session_state.messages.append({"role": "assistant", "content": response})

    # ─ Chat input (visually below container) ─
    if user_input := st.chat_input("メンバーやプロジェクトについて質問..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        needs_streaming = _handle_input(user_input)
        if needs_streaming:
            st.session_state.pending_stream = user_input
        st.rerun()

# ─────────────────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────────────────
def sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🎯 TalentScope")
        st.caption("AI HR アシスタント")
        st.divider()

        current_view = st.session_state.get("view", "home")
        for icon, label, view_key in [
            ("🏠", "ホーム / レポート", "home"),
            ("👥", "メンバーDB",        "members"),
            ("📋", "プロジェクト",       "projects"),
            ("📅", "スケジュール",       "calendar"),
        ]:
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{view_key}",
                use_container_width=True,
                type="primary" if current_view == view_key else "secondary",
            ):
                st.session_state.view = view_key
                st.rerun()

        st.divider()
        if st.session_state.get("active_report"):
            report = st.session_state.active_report
            st.success(f"📄 {report['panel_name']}", icon=None)
            if st.button("🗑️ レポートをクリア", use_container_width=True):
                st.session_state.active_report = None
                st.rerun()

# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────
_SPLITTER_JS = """
<script>
(function() {
    const doc = window.parent.document;

    function setupSplitter() {
        const blocks = doc.querySelectorAll('[data-testid="stHorizontalBlock"]');
        let target = null;
        for (const b of blocks) {
            if (b.querySelector('.chat-header')) { target = b; break; }
        }
        if (!target) return false;
        if (target.dataset.splitterReady === '1') return true;

        const columns = target.querySelectorAll(':scope > [data-testid="stColumn"], :scope > div > [data-testid="stColumn"], :scope > [data-testid="column"]');
        if (columns.length < 2) return false;
        const c1 = columns[0], c2 = columns[columns.length - 1];

        const splitter = doc.createElement('div');
        splitter.className = 'col-splitter';
        Object.assign(splitter.style, {
            width: '6px',
            cursor: 'col-resize',
            background: '#dde3ef',
            flexShrink: '0',
            margin: '0 4px',
            borderRadius: '3px',
            transition: 'background 0.15s',
        });

        let dragging = false, startX = 0, w1Start = 0, w2Start = 0;
        splitter.addEventListener('mouseenter', () => splitter.style.background = '#0078d4');
        splitter.addEventListener('mouseleave', () => { if (!dragging) splitter.style.background = '#dde3ef'; });
        splitter.addEventListener('mousedown', (e) => {
            dragging = true;
            startX = e.clientX;
            w1Start = c1.offsetWidth;
            w2Start = c2.offsetWidth;
            doc.body.style.cursor = 'col-resize';
            doc.body.style.userSelect = 'none';
            e.preventDefault();
        });
        doc.addEventListener('mousemove', (e) => {
            if (!dragging) return;
            const dx = e.clientX - startX;
            const newW1 = w1Start + dx;
            const newW2 = w2Start - dx;
            if (newW1 < 240 || newW2 < 240) return;
            c1.style.flex = `0 0 ${newW1}px`;
            c2.style.flex = `0 0 ${newW2}px`;
            localStorage.setItem('tsChatRatio', `${newW1}:${newW2}`);
        });
        doc.addEventListener('mouseup', () => {
            if (dragging) {
                dragging = false;
                doc.body.style.cursor = '';
                doc.body.style.userSelect = '';
                splitter.style.background = '#dde3ef';
            }
        });

        target.insertBefore(splitter, c2);
        target.dataset.splitterReady = '1';

        const saved = localStorage.getItem('tsChatRatio');
        if (saved) {
            const [w1, w2] = saved.split(':').map(Number);
            if (w1 > 200 && w2 > 200) {
                c1.style.flex = `0 0 ${w1}px`;
                c2.style.flex = `0 0 ${w2}px`;
            }
        }
        return true;
    }

    let tries = 0;
    const iv = setInterval(() => {
        if (setupSplitter() || ++tries > 40) clearInterval(iv);
    }, 100);
})();
</script>
"""


def _inject_splitter() -> None:
    components.html(_SPLITTER_JS, height=0)


def main() -> None:
    _init_session()
    sidebar()

    if not st.session_state.chat_open:
        col_main, col_open = st.columns([10, 1])
        with col_open:
            if st.button("💬", key="open_chat", help="チャットを開く", use_container_width=True):
                st.session_state.chat_open = True
                st.rerun()
        with col_main:
            render_main()
    else:
        col_main, col_chat = st.columns([3, 2], gap="small")
        with col_main:
            render_main()
        with col_chat:
            render_chat()
        _inject_splitter()


main()
