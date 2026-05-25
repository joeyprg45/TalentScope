"""TalentScope エージェントオーケストレータ.

ChatCompletionAgent + FunctionChoiceBehavior.Auto() でReActパターンを実現する。
モード切替はシステムプロンプトの差し替えで行う。
"""
from __future__ import annotations

import pathlib
from contextvars import ContextVar
from enum import Enum
from typing import Any, AsyncGenerator, Awaitable, Callable

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.filters.filter_types import FilterTypes

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.plugins.member_plugin import MemberPlugin
from agents.plugins.project_plugin import ProjectPlugin
from agents.plugins.contribution_plugin import ContributionPlugin
from agents.plugins.meeting_plugin import MeetingPlugin
from agents.plugins.team_balance_plugin import TeamBalancePlugin
from agents.plugins.synergy_plugin import SynergyPlugin
from agents.report import build_skill_report_md, build_assignment_report_md

ToolCallCallback = Callable[[str, str, dict[str, str]], Awaitable[None]]
_tool_callback_var: ContextVar[ToolCallCallback | None] = ContextVar("_tool_callback", default=None)

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"

_INTENT_PROMPT = """\
ユーザーの発言を以下のカテゴリに分類し、分類名だけを1単語で出力してください。

- assignment: アサイン提案・チーム編成を「実行してほしい」明確なリクエスト
  例: 「アサイン提案をして」「プロジェクトAのチームを組んで」「誰をアサインすべきか提案して」
- skill: 特定メンバーのスキル分析レポートを「生成してほしい」リクエスト
  例: 「田中のスキル分析をして」「鈴木のスキルレポートを出して」
- refine: 既存レポートへの修正・変更指示（current_report=ありの場合のみ選択可）
  例: 「田中を外して別の人に」「コストを下げて」「リーダーを佐藤に」
- chat: 上記以外の質問・情報収集・雑談
  例: 「現在のプロジェクトを教えて」「アサイン提案について教えて」「誰が空いてる？」
  ※「〜について教えて」「〜はどうすれば？」「〜できる？」などの質問は必ず chat にする\
"""


class AgentMode(str, Enum):
    BASE_CHAT       = "base_chat"
    SKILL_ANALYSIS  = "skill_analysis"
    ASSIGNMENT      = "assignment"


_AXIS_PROMPT_MAP = {
    "ability": "assignment.txt",
    "cost":    "assignment_cost.txt",
    "growth":  "assignment_growth.txt",
    "synergy": "assignment_synergy.txt",
}

_AXIS_LABEL_MAP = {
    "ability": "能力重視",
    "cost":    "コスト重視",
    "growth":  "育成・チャレンジ重視",
    "synergy": "チームワーク・シナジー重視",
}


def _load_prompt(mode: AgentMode, axis: str = "ability") -> str:
    if mode == AgentMode.ASSIGNMENT:
        filename = _AXIS_PROMPT_MAP.get(axis, "assignment.txt")
    else:
        filename = {
            AgentMode.BASE_CHAT:      "base_chat.txt",
            AgentMode.SKILL_ANALYSIS: "skill_analysis.txt",
        }[mode]
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


async def _tool_filter(context: Any, next: Callable) -> None:
    fn = getattr(context, "function", None)
    fn_name = (
        getattr(fn, "fully_qualified_name", None)
        or f"{getattr(fn, 'plugin_name', '')}-{getattr(fn, 'name', 'unknown')}"
        if fn else "unknown"
    )
    args_dict: dict[str, str] = {}
    raw_args = getattr(context, "arguments", None)
    if raw_args:
        try:
            for k, v in raw_args.items():
                if not k.startswith("_") and v is not None:
                    args_dict[k] = str(v)
        except Exception:
            pass
    cb = _tool_callback_var.get()
    if cb:
        await cb(fn_name, "start", args_dict)
    await next(context)
    if cb:
        await cb(fn_name, "done", args_dict)


class TalentScopeOrchestrator:
    """全モードのエージェント呼び出しを担当するオーケストレータ."""

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self._kernel = self._build_kernel(settings)

    def _build_kernel(self, settings: AgentSettings) -> Kernel:
        kernel = Kernel()
        kernel.add_service(
            AzureChatCompletion(
                service_id="chat",
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment_name=settings.azure_openai_chat_deployment,
                api_version=settings.azure_openai_api_version,
            )
        )
        containers = CosmosContainers(settings)
        kernel.add_plugin(
            MemberPlugin(containers.members, containers.projects),
            plugin_name="MemberPlugin",
        )
        kernel.add_plugin(
            ProjectPlugin(containers.projects),
            plugin_name="ProjectPlugin",
        )
        kernel.add_plugin(
            ContributionPlugin(containers.members, containers.projects),
            plugin_name="ContributionPlugin",
        )
        kernel.add_plugin(
            MeetingPlugin(containers.meetings),
            plugin_name="MeetingPlugin",
        )
        kernel.add_plugin(
            TeamBalancePlugin(settings),
            plugin_name="TeamBalancePlugin",
        )
        kernel.add_plugin(
            SynergyPlugin(containers.projects, containers.meetings),
            plugin_name="SynergyPlugin",
        )
        kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        return kernel

    def _build_agent(self, mode: AgentMode, axis: str = "ability") -> ChatCompletionAgent:
        return ChatCompletionAgent(
            kernel=self._kernel,
            name="TalentScopeAgent",
            instructions=_load_prompt(mode, axis),
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )

    async def classify_intent(
        self,
        user_message: str,
        has_current_report: bool = False,
    ) -> str:
        """ユーザーメッセージの意図を分類する。"assignment" | "skill" | "refine" | "chat" を返す。"""
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            api_key=self._settings.azure_openai_api_key,
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_version=self._settings.azure_openai_api_version,
        )
        context = f"current_report={'あり' if has_current_report else 'なし'}\n\nユーザー発言: {user_message}"
        response = await client.chat.completions.create(
            model=self._settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": _INTENT_PROMPT},
                {"role": "user", "content": context},
            ],
            max_tokens=10,
            temperature=0,
        )
        result = (response.choices[0].message.content or "").strip().lower()
        if result.startswith("assignment"):
            return "assignment"
        if result.startswith("skill"):
            return "skill"
        if result.startswith("refine") and has_current_report:
            return "refine"
        return "chat"

    async def chat(
        self,
        user_message: str,
        mode: AgentMode = AgentMode.BASE_CHAT,
        history: ChatHistory | None = None,
        axis: str = "ability",
        on_tool_call: ToolCallCallback | None = None,
    ) -> AsyncGenerator[str, None]:
        """ユーザーメッセージを受け取り、エージェントの応答をストリーミングで返す."""
        if history is None:
            history = ChatHistory()
        history.add_user_message(user_message)

        agent = self._build_agent(mode, axis)
        full_response: list[str] = []

        token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        try:
            async for chunk in agent.invoke_stream(messages=history):
                text = str(chunk.message) if chunk.message else ""
                if text:
                    full_response.append(text)
                    yield text
        finally:
            if token is not None:
                _tool_callback_var.reset(token)

        # 会話履歴にアシスタントの返答を追加
        history.add_message(
            ChatMessageContent(role=AuthorRole.ASSISTANT, content="".join(full_response))
        )

    async def chat_batch(
        self,
        user_message: str,
        mode: AgentMode,
        history: ChatHistory | None = None,
        axis: str = "ability",
        on_tool_call: ToolCallCallback | None = None,
    ) -> str:
        """invoke() を使うバッチ版チャット。invoke_stream はツール呼び出しが多いと
        最終テキストが空になるため、ASSIGNMENT のような重いモードではこちらを使う。"""
        if history is None:
            history = ChatHistory()
        history.add_user_message(user_message)

        agent = self._build_agent(mode, axis)
        full_response = ""

        token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        try:
            async for response in agent.invoke(messages=history):
                text = str(response.message) if response.message else ""
                if text:
                    full_response += text
        finally:
            if token is not None:
                _tool_callback_var.reset(token)

        history.add_message(
            ChatMessageContent(role=AuthorRole.ASSISTANT, content=full_response)
        )
        return full_response

    async def generate_report(
        self,
        mode: AgentMode,
        target_id: str,
        target_name: str = "",
        axis: str = "ability",
        on_tool_call: ToolCallCallback | None = None,
    ) -> tuple[str, str]:
        """レポート用のエージェント呼び出し。(summary, full_markdown) を返す.

        Args:
            mode:        SKILL_ANALYSIS または ASSIGNMENT
            target_id:   skill時はmember_id(email)、assignment時はproject_id
            target_name: レポートヘッダ用の表示名（省略可）
            axis:        "ability" | "cost"（assignmentモードのみ有効）

        Returns:
            (summary, full_markdown): summaryはチャット表示用1〜2文、full_markdownはサイドパネル/ダウンロード用
        """
        if mode == AgentMode.BASE_CHAT:
            raise ValueError("generate_report は SKILL_ANALYSIS / ASSIGNMENT モードのみ対応")

        history = ChatHistory()
        if mode == AgentMode.SKILL_ANALYSIS:
            history.add_user_message(
                f"メンバー {target_id} の個人スキル分析レポートを作成してください。"
            )
        else:
            axis_label = _AXIS_LABEL_MAP.get(axis, axis)
            history.add_user_message(
                f"プロジェクト {target_id} のアサイン提案レポートを作成してください。"
                f"提案軸は「{axis_label}」です。"
            )

        agent = self._build_agent(mode, axis)
        agent_body = ""

        token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        try:
            # invoke_stream はツール呼び出しが多いと最終テキストが空になるため
            # レポート生成は invoke() （非ストリーミング）を使用する
            async for response in agent.invoke(messages=history):
                text = str(response.message) if response.message else ""
                if text:
                    agent_body += text
        finally:
            if token is not None:
                _tool_callback_var.reset(token)

        # レポートヘッダを付与
        if mode == AgentMode.SKILL_ANALYSIS:
            full_md = build_skill_report_md(
                member_name=target_name or target_id,
                agent_body=agent_body,
            )
        else:
            full_md = build_assignment_report_md(
                project_name=target_name or target_id,
                axis=axis,
                agent_body=agent_body,
            )

        # サマリー: 最初の2文をチャット表示用に返す
        sentences = [s.strip() for s in agent_body.split("。") if s.strip()]
        summary = "。".join(sentences[:2]) + ("。" if sentences else "")

        return summary, full_md

    async def refine_report(
        self,
        mode: AgentMode,
        target_id: str,
        target_name: str,
        axis: str,
        current_report_md: str,
        user_feedback: str,
        on_tool_call: ToolCallCallback | None = None,
    ) -> tuple[str, str]:
        """既存レポートをユーザーの修正指示に従って更新する。

        Args:
            current_report_md: 修正前のレポート全文（Markdown）
            user_feedback:     ユーザーの修正指示テキスト
        """
        history = ChatHistory()
        history.add_user_message(
            f"以下は現在のレポートです:\n\n{current_report_md}\n\n"
            f"---\n\n"
            f"ユーザーからの修正指示: {user_feedback}\n\n"
            f"上記のレポートを修正指示に従って更新してください。"
            f"必要に応じてツールで追加情報を取得してもかまいません。"
            f"修正対象以外の項目は元のレポートの内容をそのまま維持してください。\n"
            f"【変更箇所のマーキング】\n"
            f"- 変更・追加した箇所は <mark>テキスト</mark> で囲んでください（テーブルのセル単位、文単位など適切な粒度で）\n"
            f"- 削除した内容は ~~削除したテキスト~~ で示してください\n"
            f"- 変更していない箇所にはマーキング不要です\n"
            f"【出力形式】\n"
            f"1行目: 「変更点: （変更内容の1〜2文サマリー）」\n"
            f"2行目以降: 修正済みレポートのMarkdown本文のみ（変更説明・前置き文は含めないこと）"
        )

        agent = self._build_agent(mode, axis)
        agent_body = ""

        token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        try:
            async for response in agent.invoke(messages=history):
                text = str(response.message) if response.message else ""
                if text:
                    agent_body += text
        finally:
            if token is not None:
                _tool_callback_var.reset(token)

        lines = agent_body.strip().split("\n", 1)
        if lines[0].startswith("変更点:"):
            summary = lines[0][len("変更点:"):].strip()
            report_body = lines[1].strip() if len(lines) > 1 else agent_body
        else:
            sentences = [s.strip() for s in agent_body.split("。") if s.strip()]
            summary = "。".join(sentences[:2]) + ("。" if sentences else "")
            report_body = agent_body

        if mode == AgentMode.SKILL_ANALYSIS:
            full_md = build_skill_report_md(
                member_name=target_name or target_id,
                agent_body=report_body,
            )
        else:
            full_md = build_assignment_report_md(
                project_name=target_name or target_id,
                axis=axis,
                agent_body=report_body,
            )

        return summary, full_md
