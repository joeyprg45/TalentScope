"""会話分析サブエージェント.

Slack チャンネルメッセージと会議 full_text を横断して、
発言傾向・リーダーシップ・特定テーマへの貢献を分析する ReAct エージェント。
"""
from __future__ import annotations

import pathlib

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.filters.filter_types import FilterTypes

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.plugins.slack_plugin import SlackPlugin
from agents.plugins.meeting_plugin import MeetingPlugin
from agents.tool_filter import _tool_filter

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class ConversationAnalysisAgent:
    def __init__(self, settings: AgentSettings, containers: CosmosContainers) -> None:
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
        self._kernel.add_plugin(
            SlackPlugin(containers.slack_channels, containers.members), plugin_name="SlackPlugin",
        )
        self._kernel.add_plugin(
            MeetingPlugin(containers.meetings, containers.projects, containers.members),
            plugin_name="MeetingPlugin",
        )
        self._kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        instructions = (_PROMPTS_DIR / "conversation_analysis.txt").read_text(encoding="utf-8")
        self._agent = ChatCompletionAgent(
            kernel=self._kernel,
            name="ConversationAnalysisAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )
        self._invoke_args = KernelArguments(
            settings=AzureChatPromptExecutionSettings(parallel_tool_calls=False)
        )

    async def run(
        self,
        target_id: str,
        question: str,
        date_from: str | None = None,
        date_to: str | None = None,
        project_id: str | None = None,
    ) -> str:
        history = ChatHistory()
        ctx_lines = [f"対象ID: {target_id}", f"質問: {question}"]
        if project_id:
            ctx_lines.append(f"対象プロジェクトID: {project_id}（このPJのデータのみ取得すること）")
        if date_from:
            ctx_lines.append(f"期間下限: {date_from}")
        if date_to:
            ctx_lines.append(f"期間上限: {date_to}")
        history.add_user_message("\n".join(ctx_lines))
        body = ""
        async for resp in self._agent.invoke(messages=history, arguments=self._invoke_args):
            text = str(resp.message) if resp.message else ""
            if text:
                body += text
        return body or "（会話分析の結果なし）"
