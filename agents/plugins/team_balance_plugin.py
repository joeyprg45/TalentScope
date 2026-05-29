"""チームバランス評価プラグイン.

提案チームの構成を評価するためにLLMを内部で直接呼び出す。
Kernelの再帰呼び出しを避けるため、AzureOpenAIクライアントを直接使用する。
"""
from __future__ import annotations

import json
from typing import Annotated

from azure.cosmos import ContainerProxy
from openai import AzureOpenAI
from semantic_kernel.functions import kernel_function

from agents.config import AgentSettings
from agents.plugins._resolve import resolve_project_id

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

    def __init__(
        self,
        settings: AgentSettings,
        members_container: ContainerProxy | None = None,
        projects_container: ContainerProxy | None = None,
    ) -> None:
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self._deployment = settings.azure_openai_chat_deployment
        self._members = members_container
        self._projects = projects_container

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

    @kernel_function(
        description=(
            "プロジェクト必要スキルと提案チームの保有スキルを照合し、不足スキル一覧と"
            "カバー率を返す（DB集計・LLM不要）"
        )
    )
    def find_skill_gaps(
        self,
        project_id: Annotated[str, "プロジェクト名またはID"],
        proposed_member_ids_json: Annotated[
            str,
            'メンバーIDのJSON配列。例: ["a@x.com","b@x.com"]。空配列なら現在のアサインを使う',
        ] = "[]",
    ) -> str:
        if self._projects is None or self._members is None:
            return json.dumps({"error": "containers が未注入"}, ensure_ascii=False)

        project_id = resolve_project_id(project_id, self._projects)
        project = self._projects.read_item(item=project_id, partition_key=project_id)
        required = list(project.get("required_skills", []) or [])

        try:
            member_ids: list[str] = json.loads(proposed_member_ids_json) if proposed_member_ids_json else []
        except json.JSONDecodeError:
            member_ids = []
        if not member_ids:
            member_ids = list(project.get("member_ids", []) or [])

        covered_skills: set[str] = set()
        member_skills: list[dict] = []
        for mid in member_ids:
            try:
                m = self._members.read_item(item=mid, partition_key=mid)
                skills = list(m.get("skills", []) or [])
                covered_skills.update(s.lower() for s in skills)
                member_skills.append({
                    "member_id": mid,
                    "name":      m.get("name", mid),
                    "skills":    skills,
                })
            except Exception:
                member_skills.append({"member_id": mid, "error": "not found"})

        required_lower = {r.lower(): r for r in required}
        missing = [orig for low, orig in required_lower.items() if low not in covered_skills]
        covered = [orig for low, orig in required_lower.items() if low in covered_skills]
        coverage = round(len(covered) / len(required), 2) if required else 1.0

        return json.dumps({
            "project_id":      project_id,
            "project_name":    project.get("name"),
            "required_skills": required,
            "covered_skills":  covered,
            "missing_skills":  missing,
            "coverage_rate":   coverage,
            "team":            member_skills,
        }, ensure_ascii=False)

    @kernel_function(
        description=(
            "複数メンバーを指定軸で横並び比較する。aspect は 'skill' / 'experience' / 'cost' / 'all'"
        )
    )
    def compare_members(
        self,
        member_ids_json: Annotated[str, 'メンバーIDのJSON配列。例: ["a@x.com","b@x.com"]'],
        aspect: Annotated[str, "比較軸: skill | experience | cost | all"] = "all",
    ) -> str:
        if self._members is None:
            return json.dumps({"error": "members container が未注入"}, ensure_ascii=False)
        try:
            ids: list[str] = json.loads(member_ids_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "member_ids_json のパースに失敗"}, ensure_ascii=False)

        rows: list[dict] = []
        for mid in ids:
            try:
                m = self._members.read_item(item=mid, partition_key=mid)
                row: dict = {
                    "member_id": mid,
                    "name":      m.get("name", mid),
                    "role":      m.get("role"),
                }
                if aspect in ("skill", "all"):
                    row["skills"] = m.get("skills", [])
                if aspect in ("experience", "all"):
                    row["years_experience"] = m.get("years_experience")
                if aspect in ("cost", "all"):
                    row["monthly_cost"] = m.get("monthly_cost")
                rows.append(row)
            except Exception as e:
                rows.append({"member_id": mid, "error": str(e)})

        return json.dumps({"aspect": aspect, "rows": rows}, ensure_ascii=False)
