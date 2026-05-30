"""GitHubAnalyzerAgent: GitHub MCP を使ってエンジニアの GitHub 活動を分析するサブエージェント."""
from __future__ import annotations

import pathlib

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.filters.filter_types import FilterTypes
from semantic_kernel.functions.kernel_arguments import KernelArguments

from agents.config import AgentSettings
from agents.plugins.github_mcp_plugin import GitHubMCPPlugin
from agents.tool_filter import _tool_filter

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class GitHubAnalyzerAgent:
    """GitHub MCP を使って個人・PJ リポジトリの実装活動を分析する専門サブエージェント."""

    def __init__(self, settings: AgentSettings) -> None:
        self._kernel = Kernel()
        self._kernel.add_service(
            AzureChatCompletion(
                service_id="chat",
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment_name=settings.azure_openai_chat_deployment,
                api_version=settings.azure_openai_api_version,
            )
        )
        self._kernel.add_plugin(GitHubMCPPlugin(), plugin_name="GitHubMCPPlugin")
        self._kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        instructions = (_PROMPTS_DIR / "sub_agents" / "github_analyzer.txt").read_text(encoding="utf-8")
        self._agent = ChatCompletionAgent(
            kernel=self._kernel,
            name="GitHubAnalyzerAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )
        self._invoke_args = KernelArguments(
            settings=AzureChatPromptExecutionSettings(parallel_tool_calls=False)
        )

    async def run(
        self,
        github_username: str,
        github_repo: str = "",
        context: str = "",
    ) -> str:
        """GitHub プロファイルを分析して ~300tokens の構造化テキストを返す.

        Args:
            github_username: GitHub ユーザー名（例: alice-dev）
            github_repo:     PJ リポジトリ名（owner/repo 形式、省略時は個人分析のみ）
            context:         分析文脈（プロジェクト要件など）
        """
        history = ChatHistory()
        ctx_lines = [f"対象GitHubユーザー: {github_username}"]
        if github_repo:
            ctx_lines.append(f"対象PJリポジトリ: {github_repo}（owner/repo形式）")
        if context:
            ctx_lines.append(f"分析文脈: {context}")
        history.add_user_message("\n".join(ctx_lines))

        body = ""
        async for resp in self._agent.invoke(messages=history, arguments=self._invoke_args):
            text = str(resp.message) if resp.message else ""
            if text:
                body += text
        return body or "（GitHub分析失敗）"
