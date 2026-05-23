"""チームバランス評価プラグイン.

提案チームの構成を評価するためにLLMを内部で直接呼び出す。
Kernelの再帰呼び出しを避けるため、AzureOpenAIクライアントを直接使用する。
"""
from __future__ import annotations

from typing import Annotated

from openai import AzureOpenAI
from semantic_kernel.functions import kernel_function

from agents.config import AgentSettings

_SYSTEM_PROMPT = """\
あなたはチーム構成の評価専門AIです。
提案チームを以下の観点で評価し、構造化されたMarkdownで回答してください。

評価観点:
1. **スキルカバレッジ**: 必要スキルのうち何%がカバーされているか（具体的なスキル名で）
2. **不足スキルと補完案**: 不足しているスキルと対応策（採用/育成/外部委託など）
3. **経験年数バランス**: シニア（5年以上）/ミドル（2〜5年）/ジュニア（2年未満）の比率
4. **リーダーシップ適性**: MTG能力分析からリーダー候補を評価
5. **総合バランス評価**: A（優秀）/B（良好）/C（要注意）/D（再検討推奨）の4段階＋コメント

JSONではなく読みやすいMarkdownで回答すること。
"""


class TeamBalancePlugin:
    """LLMを用いてチームバランスを評価する."""

    def __init__(self, settings: AgentSettings) -> None:
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self._deployment = settings.azure_openai_chat_deployment

    @kernel_function(
        description=(
            "提案チームのスキルカバレッジ・経験バランス・リーダー適性を評価してMarkdownで返す"
        )
    )
    def evaluate_team_balance(
        self,
        proposed_team_json: Annotated[
            str,
            "提案チームのJSON配列。各要素に member_id/name/role/skills/years_experience/monthly_cost を含む",
        ],
        project_requirements_json: Annotated[
            str,
            "プロジェクト要件のJSON。required_skills/period/overview を含む",
        ],
    ) -> str:
        user_msg = (
            f"## プロジェクト要件\n```json\n{project_requirements_json}\n```\n\n"
            f"## 提案チーム\n```json\n{proposed_team_json}\n```"
        )
        resp = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content or "（評価結果なし）"
