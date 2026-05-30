"""TeamEvaluatorAgent: アサイン提案ドラフトのレビュアー.

Main Agent がドラフトを組み立てた後、1 回だけ呼ばれる。
コスト・バランス・スキルカバレッジ・シナジーを検証し、
✅承認 or ⚠️要修正 を構造化 Markdown で返す。
"""
from __future__ import annotations

import json
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
from agents.plugins.contribution_plugin import ContributionPlugin
from agents.plugins.synergy_plugin import SynergyPlugin
from agents.plugins.team_balance_plugin import TeamBalancePlugin
from agents.tool_filter import _tool_filter

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


class TeamEvaluatorAgent:
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
        self._kernel.add_plugin(
            SynergyPlugin(containers.projects, containers.meetings),
            plugin_name="SynergyPlugin",
        )
        self._kernel.add_plugin(
            TeamBalancePlugin(settings, containers.members, containers.projects),
            plugin_name="TeamBalancePlugin",
        )
        self._kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, _tool_filter)
        instructions = (_PROMPTS_DIR / "sub_agents" / "team_evaluator.txt").read_text(encoding="utf-8")
        self._agent = ChatCompletionAgent(
            kernel=self._kernel,
            name="TeamEvaluatorAgent",
            instructions=instructions,
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )
        self._invoke_args = KernelArguments(
            settings=AzureChatPromptExecutionSettings(parallel_tool_calls=False)
        )

    async def run(self, draft_json: str) -> str:
        """draft_json は {project_id, period:{start,end}, proposed_team:[{member_id,role},...]}。"""
        try:
            parsed = json.loads(draft_json)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pretty = draft_json

        history = ChatHistory()
        history.add_user_message(
            "以下のアサイン提案ドラフトをレビューしてください。\n\n"
            f"```json\n{pretty}\n```"
        )
        body = ""
        async for resp in self._agent.invoke(messages=history, arguments=self._invoke_args):
            text = str(resp.message) if resp.message else ""
            if text:
                body += text
        return body or "（評価結果なし）"
