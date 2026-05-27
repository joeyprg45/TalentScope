"""TalentScope サブエージェント群.

すべてのサブは ReAct パターン（ChatCompletionAgent + FunctionChoiceBehavior.Auto()）。
Main Agent からは SubAgentPlugin の invoke_* 経由で呼ばれる。
"""
from agents.sub_agents.conversation_analysis import ConversationAnalysisAgent
from agents.sub_agents.task_analysis import TaskAnalysisAgent
from agents.sub_agents.member_profiler import MemberProfilerAgent
from agents.sub_agents.team_evaluator import TeamEvaluatorAgent

__all__ = [
    "ConversationAnalysisAgent",
    "TaskAnalysisAgent",
    "MemberProfilerAgent",
    "TeamEvaluatorAgent",
]
