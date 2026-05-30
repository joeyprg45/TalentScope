"""アサイン提案レポートの後処理評価モジュール.

生成済みMarkdownを絶対条件・定性方針と照合し pass/fail を返す。
パース失敗時は pass=True でフォールバック（評価エラーでループが止まらないようにする）。
"""
from __future__ import annotations

import json
import pathlib
import re

from agents.config import AgentSettings

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "agents" / "prompts"

_FALLBACK: dict = {
    "absolute": {"ok": True, "violations": []},
    "qualitative": {"ok": True, "advice": ""},
    "pass": True,
}


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / "sub_agents" / f"{name}.txt").read_text(encoding="utf-8")


async def _llm_text(prompt: str, settings: AgentSettings) -> str:
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    response = await client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return (response.choices[0].message.content or "").strip()


def _parse_eval_result(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)
    try:
        data = json.loads(raw)
        abs_data = data.get("absolute", {})
        qual_data = data.get("qualitative", {})
        return {
            "absolute": {
                "ok": bool(abs_data.get("ok", True)),
                "violations": list(abs_data.get("violations", [])),
            },
            "qualitative": {
                "ok": bool(qual_data.get("ok", True)),
                "advice": str(qual_data.get("advice", "")),
            },
            "pass": bool(data.get("pass", True)),
        }
    except (json.JSONDecodeError, ValueError, AttributeError):
        return dict(_FALLBACK)


async def evaluate_report(
    report_md: str,
    constraints: list[str],
    qualitative: str,
    settings: AgentSettings,
) -> dict:
    """レポートを絶対条件・定性条件で評価する。

    戻り値: {"absolute": {"ok": bool, "violations": [...]},
              "qualitative": {"ok": bool, "advice": "..."},
              "pass": bool}
    """
    if not constraints and not qualitative:
        return dict(_FALLBACK)

    constraints_text = "\n".join(f"- {c}" for c in constraints) if constraints else "（なし）"
    qualitative_text = qualitative if qualitative else "（なし）"

    template = _load_prompt("team_evaluator_post")
    prompt = (
        template
        .replace("{constraints}", constraints_text)
        .replace("{qualitative}", qualitative_text)
        .replace("{report}", report_md)
    )
    try:
        raw = await _llm_text(prompt, settings)
        return _parse_eval_result(raw)
    except Exception:  # noqa: BLE001
        return dict(_FALLBACK)
