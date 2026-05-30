"""メモリ抽出パイプライン.

チャット履歴からCEOの判断基準を抽出し、
absolute_constraints / qualitative_memory を更新する。
"""
from __future__ import annotations

import json
import pathlib
import re

from agents.config import AgentSettings
from agents.cosmos_client import (
    CosmosContainers,
    get_qualitative_memory,
    get_unprocessed_sessions,
    mark_session_extracted,
    upsert_constraint,
    upsert_qualitative_memory,
)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "agents" / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / "sub_agents" / f"{name}.txt").read_text(encoding="utf-8")


def _get_user_messages(session_doc: dict) -> str:
    """display_messages から role=='user' のメッセージを改行連結して返す。"""
    messages = session_doc.get("display_messages", [])
    lines = [m["content"] for m in messages if m.get("role") == "user"]
    return "\n".join(lines)


async def _llm_text(prompt: str, settings: AgentSettings) -> str:
    """Azure OpenAI に1回問い合わせてテキストを返す。"""
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    response = await client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def _parse_extraction_result(raw: str) -> dict:
    """LLM出力JSONをパースする。失敗時は空の結果を返す。"""
    raw = raw.strip()
    # ```json ... ``` ブロックがあれば剥がす
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)
    try:
        data = json.loads(raw)
        return {
            "absolute": data.get("absolute", []),
            "qualitative_snippet": data.get("qualitative_snippet", ""),
        }
    except (json.JSONDecodeError, ValueError):
        return {"absolute": [], "qualitative_snippet": ""}


async def extract_from_session(session_doc: dict, settings: AgentSettings) -> dict:
    """セッション1件から絶対条件リストと定性スニペットを抽出して返す。

    戻り値: {"absolute": [...], "qualitative_snippet": "..."}
    """
    messages_text = _get_user_messages(session_doc)
    if not messages_text:
        return {"absolute": [], "qualitative_snippet": ""}

    template = _load_prompt("memory_extractor")
    prompt = template.replace("{messages}", messages_text)
    raw = await _llm_text(prompt, settings)
    return _parse_extraction_result(raw)


async def merge_qualitative(existing: str, snippet: str, settings: AgentSettings) -> str:
    """既存の定性テキストに新スニペットをマージして返す。

    既存が空の場合はスニペットをそのまま返す（LLM呼び出し不要）。
    """
    if not existing:
        return snippet
    if not snippet:
        return existing

    template = _load_prompt("qualitative_merger")
    prompt = template.replace("{existing}", existing).replace("{snippet}", snippet)
    result = await _llm_text(prompt, settings)
    return result or existing


async def run_extraction_pipeline(
    cosmos: CosmosContainers, settings: AgentSettings
) -> dict:
    """未処理セッションをすべて処理する。

    戻り値: {processed: int, constraints_found: int, qualitative_updated: bool}
    """
    sessions = get_unprocessed_sessions(cosmos)
    processed = 0
    constraints_found = 0
    qualitative_updated = False

    for session in sessions:
        session_id = session.get("id", "")

        messages_text = _get_user_messages(session)
        if not messages_text:
            mark_session_extracted(cosmos, session_id)
            processed += 1
            continue

        result = await extract_from_session(session, settings)

        for constraint in result.get("absolute", []):
            content = constraint.get("content", "").strip()
            if not content:
                continue
            upsert_constraint(
                cosmos,
                content=content,
                related_member_ids=constraint.get("related_member_ids", []),
                status="pending",
                source="ai",
                chat_id=session_id,
            )
            constraints_found += 1

        snippet = result.get("qualitative_snippet", "").strip()
        if snippet:
            existing = get_qualitative_memory(cosmos)
            merged = await merge_qualitative(existing, snippet, settings)
            upsert_qualitative_memory(cosmos, merged)
            qualitative_updated = True

        mark_session_extracted(cosmos, session_id)
        processed += 1

    return {
        "processed": processed,
        "constraints_found": constraints_found,
        "qualitative_updated": qualitative_updated,
    }
