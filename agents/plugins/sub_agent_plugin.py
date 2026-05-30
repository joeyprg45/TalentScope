"""Main Agent から 4 つのサブエージェントを呼び出すための kernel_function 群.

各 invoke_* は対応するサブエージェントの run() をラップする。
呼び出し前後に SubAgentCallback を発火させてフロントの「生成過程ログ」に出る。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated, Awaitable, Callable

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

from agents.plugins._resolve import resolve_project_id
from agents.sub_agents import (
    ConversationAnalysisAgent,
    GitHubAnalyzerAgent,
    MemberProfilerAgent,
    TaskAnalysisAgent,
    TeamEvaluatorAgent,
)

SubAgentCallback = Callable[
    [str, str, dict[str, str], "str | None"], Awaitable[None]
]
_subagent_callback_var: ContextVar[SubAgentCallback | None] = ContextVar(
    "_subagent_callback", default=None,
)


def set_subagent_callback(cb: SubAgentCallback | None):
    """ContextVar に Subagent コールバックを設定する。token を返す。"""
    return _subagent_callback_var.set(cb)


def reset_subagent_callback(token) -> None:
    _subagent_callback_var.reset(token)


async def _emit(name: str, status: str, args: dict[str, str], result: str | None = None) -> None:
    cb = _subagent_callback_var.get()
    if cb:
        await cb(name, status, args, result)


class SubAgentPlugin:
    """5 つの invoke_* を提供する Main Agent 専用 plugin."""

    def __init__(
        self,
        conversation: ConversationAnalysisAgent,
        task: TaskAnalysisAgent,
        profiler: MemberProfilerAgent,
        evaluator: TeamEvaluatorAgent,
        github: GitHubAnalyzerAgent,
        projects_container: ContainerProxy | None = None,
        members_container: ContainerProxy | None = None,
    ) -> None:
        self._conv = conversation
        self._task = task
        self._profiler = profiler
        self._evaluator = evaluator
        self._github = github
        self._projects = projects_container
        self._members = members_container

    def _resolve(self, name_or_id: str) -> str:
        """プロジェクト名またはUUIDをUUIDに解決する。projects_container未注入時は元の値を返す。"""
        if not name_or_id or not self._projects:
            return name_or_id or ""
        return resolve_project_id(name_or_id, self._projects)

    def _resolve_github_username(self, name_or_email: str) -> str:
        """メンバー名・メールアドレス（prefix含む）から CosmosDB の github_username を引く。
        見つからない・未設定の場合は元の値をそのまま返す。"""
        if not self._members or not name_or_email:
            return name_or_email
        # 完全一致（メールアドレス or 氏名）で検索
        query = "SELECT c.github_username FROM c WHERE c.member_id = @val OR c.name = @val"
        items = list(self._members.query_items(
            query=query,
            parameters=[{"name": "@val", "value": name_or_email}],
            enable_cross_partition_query=True,
        ))
        if items and items[0].get("github_username"):
            return items[0]["github_username"]
        # 部分一致（メールprefixや名前の一部）で再検索
        all_items = list(self._members.query_items(
            query="SELECT c.github_username, c.name, c.member_id FROM c",
            enable_cross_partition_query=True,
        ))
        lower = name_or_email.lower()
        for item in all_items:
            name = item.get("name", "").lower()
            email_prefix = item.get("member_id", "").split("@")[0].lower()
            if lower in name or lower in email_prefix:
                gh = item.get("github_username")
                if gh:
                    return gh
        return name_or_email

    @kernel_function(
        description=(
            "会話分析サブエージェントに委譲する（Slack + 会議 full_text を横断分析）。"
            "発言傾向・リーダーシップ・特定テーマへの貢献などを質問する用途"
        )
    )
    async def invoke_conversation_agent(
        self,
        target_id: Annotated[str, "project_id または member_id"],
        question: Annotated[str, "分析の観点・質問文"],
        project_id: Annotated[str, "絞り込むプロジェクト名またはID（不明な場合は空文字を渡す）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付（任意）"] = "",
        date_to: Annotated[str, "期間上限 ISO日付（任意）"] = "",
    ) -> str:
        project_id = self._resolve(project_id)
        args = {"target_id": target_id, "question": question[:120]}
        if project_id: args["project_id"] = project_id
        if date_from:  args["date_from"]  = date_from
        if date_to:    args["date_to"]    = date_to
        await _emit("invoke_conversation_agent", "start", args)
        result = await self._conv.run(
            target_id, question,
            date_from=date_from or None,
            date_to=date_to or None,
            project_id=project_id or None,
        )
        await _emit("invoke_conversation_agent", "done", args, result)
        return result

    @kernel_function(
        description=(
            "タスク分析サブエージェントに委譲する。タスク実績に基づく貢献度・スキル深度・"
            "問題解決力の評価などに使う"
        )
    )
    async def invoke_task_agent(
        self,
        target_id: Annotated[str, "project_id または member_id"],
        question: Annotated[str, "分析の観点・質問文"],
        project_id: Annotated[str, "絞り込むプロジェクト名またはID（不明な場合は空文字を渡す）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付（任意）"] = "",
        date_to: Annotated[str, "期間上限 ISO日付（任意）"] = "",
    ) -> str:
        project_id = self._resolve(project_id)
        args = {"target_id": target_id, "question": question[:120]}
        if project_id: args["project_id"] = project_id
        if date_from:  args["date_from"]  = date_from
        if date_to:    args["date_to"]    = date_to
        await _emit("invoke_task_agent", "start", args)
        result = await self._task.run(
            target_id, question,
            project_id=project_id or None,
            date_from=date_from or None,
            date_to=date_to or None,
        )
        await _emit("invoke_task_agent", "done", args, result)
        return result

    @kernel_function(
        description=(
            "MemberProfilerAgent に委譲し、特定メンバーを Slack + 会議 + タスクで横断分析した "
            "300tokens 級の構造化プロファイルを取得する"
        )
    )
    async def invoke_member_profiler(
        self,
        member_id: Annotated[str, "メンバーの名前またはemail（例: 中村 大樹）"],
        project_context: Annotated[str, "プロジェクト要件などの文脈（任意）"] = "",
        project_id: Annotated[str, "絞り込むプロジェクト名またはID（不明な場合は空文字を渡す）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付（任意）"] = "",
        date_to: Annotated[str, "期間上限 ISO日付（任意）"] = "",
    ) -> str:
        project_id = self._resolve(project_id)
        args = {"member_id": member_id}
        if project_context: args["project_context"] = project_context[:120]
        if project_id:      args["project_id"]      = project_id
        if date_from:       args["date_from"]        = date_from
        if date_to:         args["date_to"]          = date_to
        await _emit("invoke_member_profiler", "start", args)
        result = await self._profiler.run(
            member_id,
            project_context=project_context,
            project_id=project_id or None,
            date_from=date_from or None,
            date_to=date_to or None,
        )
        await _emit("invoke_member_profiler", "done", args, result)
        return result

    @kernel_function(
        description=(
            "TeamEvaluatorAgent にアサイン提案ドラフトを渡してレビューを受ける。"
            "アサイン提案モードでドラフト完成後に 1 回だけ呼ぶこと"
        )
    )
    async def invoke_team_evaluator(
        self,
        draft_json: Annotated[
            str,
            '提案ドラフトJSON。例: {"project_id":"...","period":{"start":"2026-08-01","end":"2026-10-31"},'
            '"proposed_team":[{"member_id":"...","role":"..."}]}',
        ],
    ) -> str:
        await _emit("invoke_team_evaluator", "start", {"draft_json": draft_json[:200]})
        result = await self._evaluator.run(draft_json)
        await _emit("invoke_team_evaluator", "done", {"draft_json": draft_json[:200]}, result)
        return result

    @kernel_function(
        description=(
            "GitHubAnalyzerAgent に委譲し、GitHub の実装履歴・PR・技術スタックを分析した "
            "GitHub 技術プロファイル（~300tokens）を取得する。"
            "メンバーデータに github_username がある場合に呼ぶ。"
            "PJ リポジトリ（owner/repo 形式）も渡すと PJ 内の貢献量も分析する"
        )
    )
    async def invoke_github_analyzer(
        self,
        github_username: Annotated[str, "対象メンバーの GitHub ユーザー名（例: alice-dev）"],
        github_repo: Annotated[str, "PJ リポジトリ名（owner/repo 形式、任意）"] = "",
        context: Annotated[str, "分析文脈（プロジェクト要件など、任意）"] = "",
    ) -> str:
        github_username = self._resolve_github_username(github_username)
        args: dict[str, str] = {"github_username": github_username}
        if github_repo:
            args["github_repo"] = github_repo
        await _emit("invoke_github_analyzer", "start", args)
        result = await self._github.run(github_username, github_repo=github_repo, context=context)
        await _emit("invoke_github_analyzer", "done", args, result)
        return result
