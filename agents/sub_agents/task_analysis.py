"""タスク分析サブエージェント."""
from __future__ import annotations

import pathlib

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.filters.filter_types import FilterTypes

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.plugins.contribution_plugin import ContributionPlugin
from agents.tool_filter import _tool_filter

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class TaskAnalysisAgent:
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
            ContributionPlugin(containers.members, containers.projects),
            plugin_name="ContributionPlugin",
        )
        self._kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        instructions = (_PROMPTS_DIR / "task_analysis.txt").read_text(encoding="utf-8")
        self._agent = ChatCompletionAgent(
            kernel=self._kernel,
            name="TaskAnalysisAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )

    async def run(self, target_id: str, question: str) -> str:
        history = ChatHistory()
        history.add_user_message(f"対象ID: {target_id}\n質問: {question}")
        body = ""
        async for resp in self._agent.invoke(messages=history):
            text = str(resp.message) if resp.message else ""
            if text:
                body += text
        return body or "（タスク分析の結果なし）"
