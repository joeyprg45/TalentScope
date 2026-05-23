"""Markdownレポートフォーマッタ.

エージェントが出力したMarkdown本文にヘッダ・フッタを付与する。
LLM呼び出しは行わない。
"""
from __future__ import annotations

from datetime import date


def build_skill_report_md(member_name: str, agent_body: str) -> str:
    """個人スキル分析レポートのMarkdown全文を返す."""
    today = date.today().isoformat()
    header = (
        f"# 個人スキル分析レポート：{member_name}\n\n"
        f"**生成日:** {today}　｜　**生成エンジン:** TalentScope (Azure OpenAI)\n\n"
        "---\n\n"
    )
    footer = "\n\n---\n\n*このレポートはTalentScopeエージェントが自動生成しました。*\n"
    return header + agent_body.strip() + footer


def build_assignment_report_md(
    project_name: str,
    axis: str,
    agent_body: str,
) -> str:
    """アサイン提案レポートのMarkdown全文を返す."""
    _labels = {
        "ability": "能力重視",
        "cost":    "コスト重視",
        "growth":  "育成・チャレンジ重視",
        "synergy": "チームワーク・シナジー重視",
    }
    today = date.today().isoformat()
    axis_label = _labels.get(axis, axis)
    header = (
        f"# アサイン提案レポート：{project_name}\n\n"
        f"**生成日:** {today}　｜　**提案軸:** {axis_label}　｜　**生成エンジン:** TalentScope (Azure OpenAI)\n\n"
        "---\n\n"
    )
    footer = "\n\n---\n\n*このレポートはTalentScopeエージェントが自動生成しました。*\n"
    return header + agent_body.strip() + footer
