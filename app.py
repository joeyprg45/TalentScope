"""TalentScope Chainlit UI.

自然文からスキル分析・アサイン提案を起動できる常時チャット対応UI。
モードボタンは使い方ヒントとして機能し、入力をブロックしない。
"""
from __future__ import annotations

import unicodedata
from typing import Optional

import chainlit as cl
from semantic_kernel.contents.chat_history import ChatHistory

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.orchestrator import AgentMode, TalentScopeOrchestrator

# ---------------------------------------------------------------------------
# セッションキー
# ---------------------------------------------------------------------------
KEY_ORCHESTRATOR  = "orchestrator"
KEY_COSMOS        = "cosmos"
KEY_HISTORY       = "history"
KEY_PENDING_ID    = "pending_target_id"
KEY_PENDING_NAME  = "pending_target_name"
KEY_ACTIVE_REPORT = "active_report"   # 直近のレポート状態（修正ループで使用）

# ---------------------------------------------------------------------------
# ヘルパー: モードボタン
# ---------------------------------------------------------------------------

def _mode_actions() -> list[cl.Action]:
    return [
        cl.Action(name="mode_skill",      value="skill",      label="👤 個人スキル分析", payload={}),
        cl.Action(name="mode_assignment", value="assignment",  label="📋 アサイン提案",  payload={}),
    ]

# ---------------------------------------------------------------------------
# ヘルパー: Cosmos DB ルックアップ
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """NFKC正規化 + 空白除去 + lowercase."""
    return unicodedata.normalize("NFKC", s).replace(" ", "").replace("　", "").lower()


def _lookup_member(
    query: str,
    cosmos: CosmosContainers,
) -> Optional[tuple[str, str]]:
    """(member_id, member_name) を返す。見つからなければ None。"""
    items = list(
        cosmos.members.query_items(
            query="SELECT c.member_id, c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    q = query.strip()
    # 1. email完全一致
    for item in items:
        if item.get("member_id", "").lower() == q.lower():
            return item["member_id"], item["name"]
    # 2. 名前の正規化サブストリング一致（双方向）
    q_norm = _normalize(q)
    for item in items:
        member_norm = _normalize(item.get("name", ""))
        if q_norm in member_norm or member_norm in q_norm:
            return item["member_id"], item["name"]
    return None


def _lookup_project(
    query: str,
    cosmos: CosmosContainers,
) -> Optional[tuple[str, str]]:
    """(project_id, project_name) を返す。見つからなければ None。"""
    items = list(
        cosmos.projects.query_items(
            query="SELECT c.project_id, c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    q = query.strip().lower()
    for item in items:
        name = item.get("name", "").lower()
        if q in name or name in q:
            return item["project_id"], item["name"]
    return None


def _list_member_names(cosmos: CosmosContainers) -> list[str]:
    items = list(
        cosmos.members.query_items(
            query="SELECT c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    return [item["name"] for item in items]


def _list_project_names(cosmos: CosmosContainers) -> list[str]:
    items = list(
        cosmos.projects.query_items(
            query="SELECT c.name FROM c",
            enable_cross_partition_query=True,
        )
    )
    return [item["name"] for item in items]

# ---------------------------------------------------------------------------
# ヘルパー: インテント検出
# ---------------------------------------------------------------------------

_SKILL_KEYWORDS = [
    "スキル分析", "スキルを分析", "スキルレポート",
    "スキルを見", "の分析して", "分析レポート", "スキル見て",
]
_ASSIGN_KEYWORDS = [
    "アサイン", "チーム提案", "メンバーを決め", "担当者を決め",
    "チーム決め", "配置して", "チームを組",
]


def _is_skill_intent(text: str) -> bool:
    return any(kw in text for kw in _SKILL_KEYWORDS)


def _is_assign_intent(text: str) -> bool:
    return any(kw in text for kw in _ASSIGN_KEYWORDS)


_REFINE_KEYWORDS = [
    "修正", "変えて", "外して", "除いて", "抜いて", "替えて",
    "追加して", "入れて", "増やして", "減らして",
    "変更", "差し替え", "見直して", "調整", "もっと",
    "代わりに", "別の人", "他のメンバー",
    "更新", "アップデート",
]


def _is_refine_intent(text: str) -> bool:
    return any(kw in text for kw in _REFINE_KEYWORDS)

# ---------------------------------------------------------------------------
# ヘルパー: 軸ボタン
# ---------------------------------------------------------------------------

_AXIS_LABELS = {
    "ability": "能力重視",
    "cost":    "コスト重視",
    "growth":  "育成・チャレンジ重視",
    "synergy": "チームワーク・シナジー重視",
}


def _axis_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="axis_ability", value="ability", label="🎯 能力重視",
            description="必要スキルを最大限カバーする最強チームを提案", payload={},
        ),
        cl.Action(
            name="axis_cost", value="cost", label="💰 コスト重視",
            description="予算制約内でコスト効率の良いチームを提案", payload={},
        ),
        cl.Action(
            name="axis_growth", value="growth", label="🌱 育成・チャレンジ重視",
            description="若手にストレッチ機会を与え成長を促すチームを提案", payload={},
        ),
        cl.Action(
            name="axis_synergy", value="synergy", label="🤝 チームワーク重視",
            description="過去の協働実績をもとにシナジーが最大のチームを提案", payload={},
        ),
    ]


def _axis_choice_message(project_name: str) -> str:
    return (
        f"プロジェクト「**{project_name}**」のアサイン提案を行います。\n\n"
        "提案軸を選んでください：\n\n"
        "| 軸 | 概要 |\n|---|---|\n"
        "| 🎯 **能力重視** | 必要スキルを最大限カバーする最強チームを提案 |\n"
        "| 💰 **コスト重視** | 予算制約内でコスト効率の良いチームを提案 |\n"
        "| 🌱 **育成・チャレンジ重視** | 若手にストレッチ機会を与え、成長を促すチームを提案 |\n"
        "| 🤝 **チームワーク重視** | 過去の協働実績をもとにシナジーが最大のチームを提案 |\n"
    )

# ---------------------------------------------------------------------------
# ヘルパー: レポート生成・表示
# ---------------------------------------------------------------------------

async def _run_report(
    mode: AgentMode,
    target_id: str,
    target_name: str,
    axis: str,
) -> None:
    """レポートを生成してサイドパネル + ダウンロードボタンを表示する。"""
    orchestrator: TalentScopeOrchestrator = cl.user_session.get(KEY_ORCHESTRATOR)

    axis_label = _AXIS_LABELS.get(axis, axis)
    mode_label = "個人スキル分析" if mode == AgentMode.SKILL_ANALYSIS else f"アサイン提案（{axis_label}）"

    msg = cl.Message(content=f"⏳ **{target_name}** の{mode_label}レポートを生成中...")
    await msg.send()

    try:
        summary, full_md = await orchestrator.generate_report(
            mode=mode,
            target_id=target_id,
            target_name=target_name,
            axis=axis,
        )
    except Exception as exc:
        msg.content = f"❌ レポート生成中にエラーが発生しました: {exc}"
        await msg.update()
        return

    panel_name = f"{target_name} {mode_label}レポート"
    text_element = cl.Text(name=panel_name, content=full_md, display="side", mime="text/plain")
    text_element.updatable = True
    msg.content = f"✅ **{mode_label}レポート**を生成しました。右パネルをご覧ください。"
    msg.elements = [text_element]
    await msg.update()

    cl.user_session.set(KEY_ACTIVE_REPORT, {
        "mode":          mode,
        "target_id":     target_id,
        "target_name":   target_name,
        "axis":          axis,
        "content":       full_md,
        "panel_name":    panel_name,
        "mode_label":    mode_label,
        "panel_element": text_element,
    })

    # pending状態をリセット
    cl.user_session.set(KEY_PENDING_ID,   None)
    cl.user_session.set(KEY_PENDING_NAME, None)

    # モードボタンを再表示（修正ヒントつき）
    await cl.Message(
        content=(
            "「**田中を外して**」「**もっとコストを下げて**」など、"
            "チャットで指示するとレポートを修正できます。"
        ),
        actions=_mode_actions(),
    ).send()


async def _run_refine(user_feedback: str, report: dict) -> None:
    """既存レポートをユーザーの指示に従って修正し、サイドパネルを更新する。"""
    orchestrator: TalentScopeOrchestrator = cl.user_session.get(KEY_ORCHESTRATOR)

    msg = cl.Message(content=f"⏳ レポートを修正中...")
    await msg.send()

    try:
        summary, full_md = await orchestrator.refine_report(
            mode=report["mode"],
            target_id=report["target_id"],
            target_name=report["target_name"],
            axis=report["axis"],
            current_report_md=report["content"],
            user_feedback=user_feedback,
        )
    except Exception as exc:
        msg.content = f"❌ レポート修正中にエラーが発生しました: {exc}"
        await msg.update()
        return

    msg.content = f"✅ レポートを修正しました。\n\n**変更内容:** {summary}"
    await msg.update()

    panel_element = report.get("panel_element")
    if panel_element:
        panel_element.content = full_md
        await panel_element.send(for_id=panel_element.for_id)
    else:
        msg.elements = [cl.Text(name=report["panel_name"], content=full_md, display="side", mime="text/plain")]
        await msg.update()

    report["content"] = full_md
    cl.user_session.set(KEY_ACTIVE_REPORT, report)

    await cl.Message(
        content="さらに修正が必要な場合はチャットでお知らせください。",
        actions=_mode_actions(),
    ).send()

# ---------------------------------------------------------------------------
# Chainlit イベントハンドラ
# ---------------------------------------------------------------------------

@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        settings = AgentSettings.from_env()
        orchestrator = TalentScopeOrchestrator(settings)
        cosmos = CosmosContainers(settings)
    except Exception as exc:
        await cl.Message(content=f"❌ 初期化エラー: {exc}").send()
        return

    cl.user_session.set(KEY_ORCHESTRATOR, orchestrator)
    cl.user_session.set(KEY_COSMOS,       cosmos)
    cl.user_session.set(KEY_HISTORY,      ChatHistory())
    cl.user_session.set(KEY_PENDING_ID,    None)
    cl.user_session.set(KEY_PENDING_NAME,  None)
    cl.user_session.set(KEY_ACTIVE_REPORT, None)

    await cl.Message(
        content=(
            "**TalentScope** へようこそ。\n\n"
            "チャットで自由に質問できます。以下の操作もできます：\n"
            "- 「**佐藤健太のスキルを分析して**」→ 個人スキル分析レポートを生成\n"
            "- 「**次世代LLMのアサインを決めて**」→ アサイン提案レポートを生成"
        ),
        actions=_mode_actions(),
    ).send()


@cl.on_chat_end
async def on_chat_end() -> None:
    pass


# ---------------------------------------------------------------------------
# モードボタン（ヒント表示のみ、チャットはブロックしない）
# ---------------------------------------------------------------------------

@cl.action_callback("mode_skill")
async def on_mode_skill(action: cl.Action) -> None:
    members = _list_member_names(cl.user_session.get(KEY_COSMOS))
    sample = members[0] if members else "メンバー名"
    await cl.Message(
        content=(
            "👤 **個人スキル分析**\n"
            f"「{sample}のスキルを分析して」のようにメンバー名を含めて送ってください。\n\n"
            f"**登録メンバー:** {', '.join(members)}"
        )
    ).send()


@cl.action_callback("mode_assignment")
async def on_mode_assignment(action: cl.Action) -> None:
    projects = _list_project_names(cl.user_session.get(KEY_COSMOS))
    sample = projects[0] if projects else "プロジェクト名"
    await cl.Message(
        content=(
            "📋 **アサイン提案**\n"
            f"「{sample}のアサインを決めて」のようにプロジェクト名を含めて送ってください。\n\n"
            f"**登録プロジェクト:** {', '.join(projects)}"
        )
    ).send()


# ---------------------------------------------------------------------------
# 提案軸ボタン
# ---------------------------------------------------------------------------

@cl.action_callback("axis_ability")
async def on_axis_ability(action: cl.Action) -> None:
    target_id   = cl.user_session.get(KEY_PENDING_ID)
    target_name = cl.user_session.get(KEY_PENDING_NAME)
    await _run_report(AgentMode.ASSIGNMENT, target_id, target_name, "ability")


@cl.action_callback("axis_cost")
async def on_axis_cost(action: cl.Action) -> None:
    target_id   = cl.user_session.get(KEY_PENDING_ID)
    target_name = cl.user_session.get(KEY_PENDING_NAME)
    await _run_report(AgentMode.ASSIGNMENT, target_id, target_name, "cost")


@cl.action_callback("axis_growth")
async def on_axis_growth(action: cl.Action) -> None:
    target_id   = cl.user_session.get(KEY_PENDING_ID)
    target_name = cl.user_session.get(KEY_PENDING_NAME)
    await _run_report(AgentMode.ASSIGNMENT, target_id, target_name, "growth")


@cl.action_callback("axis_synergy")
async def on_axis_synergy(action: cl.Action) -> None:
    target_id   = cl.user_session.get(KEY_PENDING_ID)
    target_name = cl.user_session.get(KEY_PENDING_NAME)
    await _run_report(AgentMode.ASSIGNMENT, target_id, target_name, "synergy")


# ---------------------------------------------------------------------------
# メッセージ受信（常時チャット対応）
# ---------------------------------------------------------------------------

@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_text = message.content.strip()
    if not user_text:
        return

    cosmos: CosmosContainers              = cl.user_session.get(KEY_COSMOS)
    orchestrator: TalentScopeOrchestrator = cl.user_session.get(KEY_ORCHESTRATOR)
    history: ChatHistory                  = cl.user_session.get(KEY_HISTORY)

    # --- レポート修正インテント: アクティブなレポートがある場合に優先 ---
    active_report = cl.user_session.get(KEY_ACTIVE_REPORT)
    if active_report and _is_refine_intent(user_text):
        await _run_refine(user_text, active_report)
        return

    # --- スキル分析インテント: メンバー名+スキルキーワード ---
    if _is_skill_intent(user_text):
        member = _lookup_member(user_text, cosmos)
        if member:
            member_id, member_name = member
            await _run_report(AgentMode.SKILL_ANALYSIS, member_id, member_name, "ability")
            return

    # --- アサイン提案インテント: プロジェクト名+アサインキーワード ---
    if _is_assign_intent(user_text):
        project = _lookup_project(user_text, cosmos)
        if project:
            project_id, project_name = project
            cl.user_session.set(KEY_PENDING_ID,   project_id)
            cl.user_session.set(KEY_PENDING_NAME, project_name)
            await cl.Message(
                content=_axis_choice_message(project_name),
                actions=_axis_actions(),
            ).send()
        else:
            projects = _list_project_names(cosmos)
            await cl.Message(
                content=(
                    "どのプロジェクトについてアサイン提案を行いますか？\n\n"
                    f"**登録プロジェクト:** {', '.join(projects)}\n\n"
                    "プロジェクト名を含めて入力してください。"
                ),
                actions=_mode_actions(),
            ).send()
        return

    # --- 通常チャット（常にフォールスルー）---
    response_msg = cl.Message(content="")
    await response_msg.send()

    async for chunk in orchestrator.chat(
        user_message=user_text,
        mode=AgentMode.BASE_CHAT,
        history=history,
    ):
        await response_msg.stream_token(chunk)

    await response_msg.update()
    await cl.Message(content="---", actions=_mode_actions()).send()
