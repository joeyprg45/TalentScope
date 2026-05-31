"""TalentScope エージェントオーケストレータ.

ChatCompletionAgent + FunctionChoiceBehavior.Auto() でReActパターンを実現する。
モード切替はシステムプロンプトの差し替えで行う。
"""
from __future__ import annotations

import pathlib
from enum import Enum
from typing import Annotated, AsyncGenerator

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.functions.kernel_arguments import KernelArguments

_INVOKE_ARGS = KernelArguments(
    settings=AzureChatPromptExecutionSettings(parallel_tool_calls=False)
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.filters.filter_types import FilterTypes
from semantic_kernel.functions import kernel_function

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.plugins.member_plugin import MemberPlugin
from agents.plugins.project_plugin import ProjectPlugin
from agents.plugins.contribution_plugin import ContributionPlugin
from agents.plugins.team_balance_plugin import TeamBalancePlugin
from agents.plugins.sub_agent_plugin import (
    SubAgentPlugin,
    SubAgentCallback,
    set_subagent_callback,
    reset_subagent_callback,
)
from agents.plugins.clarification_plugin import (
    ClarificationPlugin,
    ClarificationCallback,
    set_clarification_callback,
    reset_clarification_callback,
)
from agents.sub_agents import (
    ConversationAnalysisAgent,
    GitHubAnalyzerAgent,
    MemberProfilerAgent,
    TaskAnalysisAgent,
    TeamEvaluatorAgent,
)
from agents.report import build_skill_report_md, build_assignment_report_md
from agents.tool_filter import ToolCallCallback, _tool_callback_var, _tool_filter  # noqa: F401 (re-exported for chat.py)

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


def _load_prompt(mode: AgentMode) -> str:
    filename = {
        AgentMode.BASE_CHAT:      "orchestrator/base_chat.txt",
        AgentMode.SKILL_ANALYSIS: "sub_agents/skill_analysis.txt",
        AgentMode.ASSIGNMENT:     "assignment/ability.txt",
    }[mode]
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestrator専用 Plugin ラッパー
# SKはプラグイン全体を登録する仕様のため、薄いラッパーで公開ツールを制限する。
# サブエージェントは独立した Kernel インスタンスを持つので影響しない。
# ---------------------------------------------------------------------------

class _MemberLookupPlugin:
    """list_all_members + get_member_schedule のみ公開（分析ツールはサブエージェントへ）."""

    def __init__(self, base: MemberPlugin) -> None:
        self._base = base

    @kernel_function(description="全メンバーの概要一覧（id/name/role/skills/経験年数/月次コスト/github_username）を返す")
    def list_all_members(self) -> str:
        return self._base.list_all_members()

    @kernel_function(description="メンバーが参加している全プロジェクトの在籍期間（役割/開始日/終了日）を返す")
    def get_member_schedule(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
    ) -> str:
        return self._base.get_member_schedule(member_id)


class _CostPlugin:
    """calc_project_cost のみ公開（アサイン提案時のコスト試算専用）."""

    def __init__(self, base: ContributionPlugin) -> None:
        self._base = base

    @kernel_function(description="提案チームの月次コスト合計×プロジェクト期間＝総コストを試算する")
    def calc_project_cost(
        self,
        member_ids_json: Annotated[str, 'メンバーIDのJSON配列 例: ["kobayashi@abc.com", "maeda@abc.com"]'],
        project_id: Annotated[str, "プロジェクト名またはID"],
    ) -> str:
        return self._base.calc_project_cost(member_ids_json, project_id)


class _TeamCheckPlugin:
    """evaluate_team_balance + find_skill_gaps のみ公開（compare_members はサブエージェントへ）."""

    def __init__(self, base: TeamBalancePlugin) -> None:
        self._base = base

    @kernel_function(description="提案チームのスキルカバレッジ・経験バランス・リーダー適性を評価してMarkdownで返す")
    def evaluate_team_balance(
        self,
        proposed_team_json: Annotated[str, "提案チームのJSON配列。各要素に member_id/name/role/skills/years_experience/monthly_cost を含む"],
        project_requirements_json: Annotated[str, "プロジェクト要件のJSON。required_skills/period/overview を含む"],
    ) -> str:
        return self._base.evaluate_team_balance(proposed_team_json, project_requirements_json)

    @kernel_function(description="プロジェクト必要スキルと提案チームの保有スキルを照合し、不足スキル一覧とカバー率を返す（DB集計・LLM不要）")
    def find_skill_gaps(
        self,
        project_id: Annotated[str, "プロジェクト名またはID"],
        proposed_member_ids_json: Annotated[str, 'メンバーIDのJSON配列。例: ["a@x.com","b@x.com"]。空配列なら現在のアサインを使う'] = "[]",
    ) -> str:
        return self._base.find_skill_gaps(project_id, proposed_member_ids_json)


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
        # ルーティング情報取得用の最小限ツールのみ公開（ラッパーで制限）
        kernel.add_plugin(
            _MemberLookupPlugin(MemberPlugin(containers.members, containers.projects)),
            plugin_name="MemberPlugin",
        )
        kernel.add_plugin(
            ProjectPlugin(containers.projects, containers.members),
            plugin_name="ProjectPlugin",
        )
        # アサイン提案時のコスト試算のみ
        kernel.add_plugin(
            _CostPlugin(ContributionPlugin(containers.members, containers.projects)),
            plugin_name="ContributionPlugin",
        )
        # アサイン提案時のチェックのみ（compare_members は除外）
        kernel.add_plugin(
            _TeamCheckPlugin(TeamBalancePlugin(settings, containers.members, containers.projects)),
            plugin_name="TeamBalancePlugin",
        )
        # MeetingPlugin: 削除（ConversationAnalysisAgent / MemberProfilerAgent が保有）
        # SynergyPlugin: 削除（TeamEvaluatorAgent が保有）

        # サブエージェント 5 つを構築して SubAgentPlugin に注入
        conversation_sa = ConversationAnalysisAgent(settings, containers)
        task_sa = TaskAnalysisAgent(settings, containers)
        profiler_sa = MemberProfilerAgent(settings, containers)
        evaluator_sa = TeamEvaluatorAgent(settings, containers)
        github_sa = GitHubAnalyzerAgent(settings)
        kernel.add_plugin(
            SubAgentPlugin(conversation_sa, task_sa, profiler_sa, evaluator_sa, github_sa, containers.projects, containers.members),
            plugin_name="SubAgentPlugin",
        )
        kernel.add_plugin(ClarificationPlugin(), plugin_name="ClarificationPlugin")

        kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        return kernel

    def _build_agent(
        self,
        mode: AgentMode,
        ceo_layer: str = "",
        constraints: list[str] | None = None,
        qualitative: str = "",
    ) -> ChatCompletionAgent:
        if mode == AgentMode.ASSIGNMENT and ceo_layer:
            instructions = ceo_layer
        else:
            instructions = _load_prompt(mode)
            if ceo_layer:
                instructions += f"\n\n## 追加指示\n{ceo_layer}"
        if constraints:
            lines = "\n".join(f"- {c}" for c in constraints)
            instructions += f"\n\n## 絶対条件（違反禁止）\n{lines}"
        if qualitative:
            instructions += f"\n\n## 方針・判断基準\n{qualitative}"
        return ChatCompletionAgent(
            kernel=self._kernel,
            name="TalentScopeAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )

    async def classify_intent(
        self,
        user_message: str,
        has_current_report: bool = False,
        mode_candidates: list[dict] | None = None,
    ) -> str:
        """ユーザーメッセージの意図を分類する。

        動的モード: mode_candidates が渡された場合、Cosmos の発火条件を使って分類する。
        戻り値: "assignment" | "skill_analysis" | "refine" | mode_id | "none"
        """
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            api_key=self._settings.azure_openai_api_key,
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_version=self._settings.azure_openai_api_version,
        )

        if mode_candidates:
            # 動的分類: Cosmos のモード一覧（trigger_conditions）を使用
            effective = list(mode_candidates)
            if has_current_report:
                effective.insert(0, {
                    "id": "refine",
                    "trigger_conditions": (
                        "既存レポートへの修正・変更指示。"
                        "例: 「田中を外して別の人に」「コストを下げて」「リーダーを佐藤に変更して」"
                    ),
                })
            mode_lines = "\n".join(
                f"- {m['id']}: {m['trigger_conditions']}"
                for m in effective if m.get("trigger_conditions")
            )
            prompt = (
                "以下のモード一覧を参照し、ユーザー発言がどのモードの発火条件に当てはまるかを判定してください。\n"
                "どのモードにも当てはまらない場合は \"none\" を返してください。\n"
                "モードIDのみを1単語で返してください（他の文字は含めない）。\n\n"
                f"利用可能なモード:\n{mode_lines}\n\n"
                f"ユーザー発言: {user_message}"
            )
            response = await client.chat.completions.create(
                model=self._settings.azure_openai_chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0,
            )
            result = (response.choices[0].message.content or "").strip().lower().split()[0]
            known_ids = {m["id"] for m in effective}
            return result if result in known_ids else "none"

        # フォールバック: 固定分類（mode_candidates なし）
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
            return "skill_analysis"
        if result.startswith("refine") and has_current_report:
            return "refine"
        return "none"

    async def plan_query(
        self,
        user_message: str,
        history: ChatHistory | None = None,
    ) -> str:
        """質問をサブクエスチョンに分解した実行プランを返す."""
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            api_key=self._settings.azure_openai_api_key,
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_version=self._settings.azure_openai_api_version,
        )
        planner_prompt = (_PROMPTS_DIR / "orchestrator" / "planner.txt").read_text(encoding="utf-8")
        messages: list[dict] = [{"role": "system", "content": planner_prompt}]
        if history:
            for msg in list(history.messages)[-4:]:
                role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
                content = str(msg.content) if msg.content else ""
                if content.strip():
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        response = await client.chat.completions.create(
            model=self._settings.azure_openai_chat_deployment,
            messages=messages,
            temperature=0.1,
            max_tokens=400,
        )
        return (response.choices[0].message.content or "").strip()

    async def chat(
        self,
        user_message: str,
        mode: AgentMode = AgentMode.BASE_CHAT,
        history: ChatHistory | None = None,
        plan_hint: str | None = None,
        constraints: list[str] | None = None,
        qualitative: str = "",
        ceo_layer: str = "",
        on_tool_call: ToolCallCallback | None = None,
        on_subagent_call: SubAgentCallback | None = None,
        on_clarification: ClarificationCallback | None = None,
    ) -> AsyncGenerator[str, None]:
        """ユーザーメッセージを受け取り、エージェントの応答をストリーミングで返す."""
        if history is None:
            history = ChatHistory()
        history.add_user_message(user_message)

        # plan_hint がある場合は実行用に拡張したメッセージを別 history で渡す
        if plan_hint:
            exec_history = ChatHistory()
            for msg in list(history.messages[:-1]):
                exec_history.add_message(msg)
            exec_history.add_user_message(
                f"{user_message}\n\n---\n"
                f"[以下のプランを参考にデータを取得すること。"
                f"ただし、あるステップで情報が取得できない・データが不足している・別の手段の方が適切と判断した場合は、"
                f"代替ツールやサブエージェントを自律的に選択して補完してよい。"
                f"プランは出発点であり、硬直した手順書ではない。状況に応じて柔軟に判断すること。]\n\n{plan_hint}"
            )
        else:
            exec_history = history

        agent = self._build_agent(mode, ceo_layer, constraints, qualitative)
        full_response: list[str] = []

        tool_token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        sub_token = set_subagent_callback(on_subagent_call) if on_subagent_call is not None else None
        clr_token = set_clarification_callback(on_clarification) if on_clarification is not None else None
        try:
            async for response in agent.invoke(messages=exec_history, arguments=_INVOKE_ARGS):
                text = str(response.message) if response.message else ""
                if text:
                    full_response.append(text)
            combined = "".join(full_response)
            if combined:
                yield combined
        finally:
            if tool_token is not None:
                _tool_callback_var.reset(tool_token)
            if sub_token is not None:
                reset_subagent_callback(sub_token)
            if clr_token is not None:
                reset_clarification_callback(clr_token)

        # 会話履歴にアシスタントの返答を追加（元の history に保存）
        history.add_message(
            ChatMessageContent(role=AuthorRole.ASSISTANT, content="".join(full_response))
        )

    async def chat_batch(
        self,
        user_message: str,
        mode: AgentMode,
        history: ChatHistory | None = None,
        constraints: list[str] | None = None,
        qualitative: str = "",
        ceo_layer: str = "",
        on_tool_call: ToolCallCallback | None = None,
        on_subagent_call: SubAgentCallback | None = None,
        on_clarification: ClarificationCallback | None = None,
    ) -> str:
        """invoke() を使うバッチ版チャット。invoke_stream はツール呼び出しが多いと
        最終テキストが空になるため、ASSIGNMENT のような重いモードではこちらを使う。"""
        if history is None:
            history = ChatHistory()
        history.add_user_message(user_message)

        agent = self._build_agent(mode, ceo_layer, constraints, qualitative)
        full_response = ""

        tool_token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        sub_token = set_subagent_callback(on_subagent_call) if on_subagent_call is not None else None
        clr_token = set_clarification_callback(on_clarification) if on_clarification is not None else None
        _ASSIGNMENT_REQUIRED = [
            "## 推奨チーム構成",
            "## コスト試算",
            "## スキルギャップ分析",
        ]
        try:
            async for response in agent.invoke(messages=history, arguments=_INVOKE_ARGS):
                text = str(response.message) if response.message else ""
                if text:
                    full_response += text

            # ASSIGNMENT モード専用: 必須セクション未達なら最大2回続行を強制
            if mode == AgentMode.ASSIGNMENT:
                for _ in range(2):
                    if all(s in full_response for s in _ASSIGNMENT_REQUIRED):
                        break
                    history.add_message(
                        ChatMessageContent(role=AuthorRole.ASSISTANT, content=full_response)
                    )
                    history.add_user_message(
                        "レポートが未完成です。残りのステップ（ドラフト組成・スキルギャップ確認・"
                        "チームレビュー・コスト試算）を続行し、出力形式に従って最終レポートを全文出力してください。"
                    )
                    full_response = ""
                    async for response in agent.invoke(messages=history, arguments=_INVOKE_ARGS):
                        text = str(response.message) if response.message else ""
                        if text:
                            full_response += text

        finally:
            if tool_token is not None:
                _tool_callback_var.reset(tool_token)
            if sub_token is not None:
                reset_subagent_callback(sub_token)
            if clr_token is not None:
                reset_clarification_callback(clr_token)

        history.add_message(
            ChatMessageContent(role=AuthorRole.ASSISTANT, content=full_response)
        )
        return full_response

    async def generate_report(
        self,
        mode: AgentMode,
        target_id: str,
        target_name: str = "",
        constraints: list[str] | None = None,
        qualitative: str = "",
        ceo_layer: str = "",
        on_tool_call: ToolCallCallback | None = None,
        on_subagent_call: SubAgentCallback | None = None,
        on_clarification: ClarificationCallback | None = None,
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
            history.add_user_message(
                f"プロジェクト {target_id} のアサイン提案レポートを作成してください。"
            )

        agent = self._build_agent(mode, ceo_layer, constraints, qualitative)
        agent_body = ""

        tool_token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        sub_token = set_subagent_callback(on_subagent_call) if on_subagent_call is not None else None
        clr_token = set_clarification_callback(on_clarification) if on_clarification is not None else None
        try:
            # invoke_stream はツール呼び出しが多いと最終テキストが空になるため
            # レポート生成は invoke() （非ストリーミング）を使用する
            async for response in agent.invoke(messages=history, arguments=_INVOKE_ARGS):
                text = str(response.message) if response.message else ""
                if text:
                    agent_body += text
        finally:
            if tool_token is not None:
                _tool_callback_var.reset(tool_token)
            if sub_token is not None:
                reset_subagent_callback(sub_token)
            if clr_token is not None:
                reset_clarification_callback(clr_token)

        # レポートヘッダを付与
        if mode == AgentMode.SKILL_ANALYSIS:
            full_md = build_skill_report_md(
                member_name=target_name or target_id,
                agent_body=agent_body,
            )
        else:
            full_md = build_assignment_report_md(
                project_name=target_name or target_id,
                axis="",
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
        current_report_md: str,
        user_feedback: str,
        constraints: list[str] | None = None,
        qualitative: str = "",
        ceo_layer: str = "",
        on_tool_call: ToolCallCallback | None = None,
        on_subagent_call: SubAgentCallback | None = None,
        on_clarification: ClarificationCallback | None = None,
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

        agent = self._build_agent(mode, ceo_layer, constraints, qualitative)
        agent_body = ""

        tool_token = _tool_callback_var.set(on_tool_call) if on_tool_call is not None else None
        sub_token = set_subagent_callback(on_subagent_call) if on_subagent_call is not None else None
        clr_token = set_clarification_callback(on_clarification) if on_clarification is not None else None
        try:
            async for response in agent.invoke(messages=history, arguments=_INVOKE_ARGS):
                text = str(response.message) if response.message else ""
                if text:
                    agent_body += text
        finally:
            if tool_token is not None:
                _tool_callback_var.reset(tool_token)
            if sub_token is not None:
                reset_subagent_callback(sub_token)
            if clr_token is not None:
                reset_clarification_callback(clr_token)

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
                axis="",
                agent_body=report_body,
            )

        return summary, full_md
