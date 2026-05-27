"""MemberProfilerAgent: 特定メンバーを横断分析して 300tokens 級プロファイルを返す."""
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
from agents.plugins.member_plugin import MemberPlugin
from agents.plugins.meeting_plugin import MeetingPlugin
from agents.plugins.contribution_plugin import ContributionPlugin
from agents.plugins.slack_plugin import SlackPlugin
from agents.tool_filter import _tool_filter

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class MemberProfilerAgent:
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
            MemberPlugin(containers.members, containers.projects),
            plugin_name="MemberPlugin",
        )
        self._kernel.add_plugin(
            MeetingPlugin(containers.meetings), plugin_name="MeetingPlugin",
        )
        self._kernel.add_plugin(
            ContributionPlugin(containers.members, containers.projects),
            plugin_name="ContributionPlugin",
        )
        self._kernel.add_plugin(
            SlackPlugin(containers.slack_channels),
            plugin_name="SlackPlugin",
        )
        self._kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        instructions = (_PROMPTS_DIR / "member_profiler.txt").read_text(encoding="utf-8")
        self._agent = ChatCompletionAgent(
            kernel=self._kernel,
            name="MemberProfilerAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )

    async def run(self, member_id: str, project_context: str = "") -> str:
        history = ChatHistory()
        ctx = f"対象メンバー: {member_id}"
        if project_context:
            ctx += f"\nプロジェクト文脈: {project_context}"
        history.add_user_message(ctx)
        body = ""
        async for resp in self._agent.invoke(messages=history):
            text = str(resp.message) if resp.message else ""
            if text:
                body += text
        return body or "（プロファイル生成失敗）"
