from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from semantic_kernel.contents.chat_history import ChatHistory

from agents.cosmos_client import get_active_constraints, get_qualitative_memory
from agents.orchestrator import AgentMode, ToolCallCallback, _load_prompt
from agents.plugins.sub_agent_plugin import SubAgentCallback
from agents.plugins.clarification_plugin import ClarificationCallback
from api.deps import get_cosmos, get_orchestrator, get_settings
from api.schemas.saved_report import ChatEntry
from api.services.report_evaluator import evaluate_report
from api.services.report_store import get_report, save_report, update_report
from api.services.session_store import SessionData, get_session

router = APIRouter()

# モード候補キャッシュ（TTL=60秒）
_mode_cache: dict = {"data": [], "ts": 0.0}


def _get_mode_candidates(cosmos) -> list[dict]:
    now = time.time()
    if now - _mode_cache["ts"] < 60 and _mode_cache["data"]:
        return _mode_cache["data"]
    try:
        items = list(cosmos.prompts.query_items(
            query="SELECT c.id, c.name, c.trigger_conditions FROM c WHERE c.is_selectable=true",
            enable_cross_partition_query=True,
        ))
        _mode_cache["data"] = [i for i in items if i.get("trigger_conditions")]
        _mode_cache["ts"] = now
    except Exception:  # noqa: BLE001
        pass
    return _mode_cache["data"]


def _fetch_constraints(cosmos) -> list[str]:
    try:
        return get_active_constraints(cosmos)
    except Exception:  # noqa: BLE001
        return []


def _fetch_qualitative(cosmos) -> str:
    try:
        return get_qualitative_memory(cosmos)
    except Exception:  # noqa: BLE001
        return ""


def _fetch_ceo_layer(cosmos, mode_id: str) -> str:
    if not mode_id:
        return ""
    try:
        item = cosmos.prompts.read_item(item=mode_id, partition_key=mode_id)
        return item.get("ceo_layer", "")
    except Exception:  # noqa: BLE001
        return ""


def _detect_project_id(projects_container, text: str) -> str | None:
    try:
        items = list(projects_container.query_items(
            "SELECT c.project_id, c.name FROM c",
            enable_cross_partition_query=True,
        ))
        text_lower = text.lower()
        for item in items:
            name = item.get("name", "")
            if name and name.lower() in text_lower:
                return item.get("project_id")
    except Exception:  # noqa: BLE001
        pass
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _t(trace_log: list[dict], **kwargs: object) -> None:
    trace_log.append({"timestamp": _now(), **kwargs})


def _make_tool_callback(ws: WebSocket, trace_log: list[dict]) -> ToolCallCallback:
    async def on_tool_call(tool_name: str, status: str, args: dict[str, str] | None = None, result: str | None = None) -> None:
        await ws.send_json({"type": "tool_call", "tool_name": tool_name, "status": status, "args": args or {}})
        entry: dict = {"timestamp": _now(), "type": "tool_call", "status": status, "tool_name": tool_name, "args": args or {}}
        if result is not None:
            entry["result"] = result[:2000] if len(result) > 2000 else result
        trace_log.append(entry)
    return on_tool_call


def _make_subagent_callback(ws: WebSocket, trace_log: list[dict]) -> SubAgentCallback:
    async def on_subagent_call(
        agent_name: str,
        status: str,
        args: dict[str, str] | None = None,
        result: str | None = None,
    ) -> None:
        await ws.send_json({
            "type": "subagent_event",
            "agent_name": agent_name,
            "status": status,
            "args": args or {},
        })
        entry: dict = {
            "timestamp": _now(),
            "type": "subagent_event",
            "status": status,
            "agent_name": agent_name,
            "args": args or {},
        }
        if result is not None:
            entry["result"] = result[:2000] if len(result) > 2000 else result
        trace_log.append(entry)
    return on_subagent_call


def _make_clarification_callback(
    ws: WebSocket,
    trace_log: list[dict],
    pending: dict[str, asyncio.Future[str]],
) -> ClarificationCallback:
    async def on_clarification(question: str, options: list[dict]) -> str:
        cid = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        pending[cid] = fut
        await ws.send_json({
            "type": "clarification_prompt",
            "id": cid,
            "question": question,
            "options": options or [],
        })
        trace_log.append({
            "timestamp": _now(),
            "type": "clarification_prompt",
            "id": cid,
            "question": question,
            "options": options or [],
        })
        try:
            answer = await fut
        finally:
            pending.pop(cid, None)
        trace_log.append({
            "timestamp": _now(),
            "type": "clarification_response",
            "id": cid,
            "answer": answer,
        })
        return answer
    return on_clarification


def _serialize_sk_history(history: ChatHistory) -> list[dict]:
    result = []
    for msg in history.messages:
        try:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = str(msg.content) if msg.content else ""
            if content.strip():
                result.append({"role": role, "content": content})
        except Exception:  # noqa: BLE001
            pass
    return result


def _persist_chat(
    cosmos,
    chat_id: str,
    display_msgs: list[dict],
    session: SessionData,
    created_at: str,
    trace_log: list[dict] | None = None,
) -> None:
    if not display_msgs:
        return
    sk_history = _serialize_sk_history(session.history)
    title = display_msgs[0]["content"][:40]

    # memory_extracted_at を既存ドキュメントから引き継ぐ（upsertで上書きされるため）
    memory_extracted_at = None
    try:
        existing = cosmos.chat_sessions.read_item(item=chat_id, partition_key=chat_id)
        memory_extracted_at = existing.get("memory_extracted_at")
    except Exception:  # noqa: BLE001
        pass

    doc: dict = {
        "id": chat_id,
        "title": title,
        "display_messages": display_msgs,
        "sk_history": sk_history,
        "current_report_id": session.current_report_id,
        "memory_extracted_at": memory_extracted_at,
        "created_at": created_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if trace_log is not None:
        doc["trace_log"] = trace_log
    cosmos.chat_sessions.upsert_item(doc)


@router.websocket("/ws")
async def chat_ws(ws: WebSocket, session_id: str = Query(..., min_length=1)) -> None:
    await ws.accept()
    orch = get_orchestrator()
    cosmos = get_cosmos()
    settings = get_settings()
    session = get_session(session_id)

    trace_log: list[dict] = []
    pending_clarifications: dict[str, asyncio.Future[str]] = {}
    tool_cb = _make_tool_callback(ws, trace_log)
    subagent_cb = _make_subagent_callback(ws, trace_log)
    clarification_cb = _make_clarification_callback(ws, trace_log, pending_clarifications)

    chat_id: str | None = None
    chat_display_msgs: list[dict] = []
    chat_created_at: str = datetime.now(timezone.utc).isoformat()

    try:
        while True:
            data = await ws.receive_json()

            # --- 逆質問への回答 ---
            if data.get("type") == "clarification_response":
                cid = data.get("id")
                answer_id = (data.get("answer_id") or "").strip()
                answer_text = (data.get("answer_text") or "").strip()
                answer = answer_text or answer_id or "（回答なし）"
                if cid and cid in pending_clarifications:
                    fut = pending_clarifications.get(cid)
                    if fut and not fut.done():
                        fut.set_result(answer)
                continue

            # --- 新規チャット ---
            if data.get("type") == "new_chat":
                chat_id = data.get("chat_id") or chat_id
                chat_display_msgs = []
                chat_created_at = datetime.now(timezone.utc).isoformat()
                trace_log.clear()
                session.history = ChatHistory()
                session.current_report = None
                session.current_report_id = None
                session.ceo_layer = ""
                continue

            # --- チャット読み込み ---
            if data.get("type") == "load_chat":
                req_chat_id = data.get("chat_id")
                if req_chat_id:
                    chat_id = req_chat_id
                    try:
                        doc = cosmos.chat_sessions.read_item(item=chat_id, partition_key=chat_id)
                        chat_display_msgs = list(doc.get("display_messages", []))
                        chat_created_at = doc.get("created_at", chat_created_at)
                        trace_log.clear()
                        trace_log.extend(doc.get("trace_log", []))
                        session.current_report_id = doc.get("current_report_id")
                        if session.current_report_id:
                            report_doc = await get_report(cosmos.reports, session.current_report_id)
                            if report_doc:
                                session.current_report = report_doc.markdown
                        new_history = ChatHistory()
                        for msg in doc.get("sk_history", []):
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if role == "user":
                                new_history.add_user_message(content)
                            elif role in ("assistant", "model"):
                                new_history.add_assistant_message(content)
                        session.history = new_history
                        await ws.send_json({
                            "type": "chat_loaded",
                            "messages": chat_display_msgs,
                        })
                    except Exception:  # noqa: BLE001
                        chat_display_msgs = []
                continue

            # --- 編集対象レポート設定 ---
            if data.get("type") == "set_active_report":
                report_id = data.get("report_id")
                if report_id:
                    doc = await get_report(cosmos.reports, report_id)
                    if doc:
                        session.current_report = doc.markdown
                        session.current_report_id = doc.id
                else:
                    session.current_report = None
                    session.current_report_id = None
                continue

            if data.get("type") != "user_message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue

            _t(trace_log, type="user_message", content=content)
            try:
                # 毎メッセージ: Cosmos モード候補を使って動的判別
                mode_candidates = _get_mode_candidates(cosmos)
                intent = await orch.classify_intent(
                    user_message=content,
                    has_current_report=bool(session.current_report),
                    mode_candidates=mode_candidates,
                )
                _t(trace_log, type="intent_classification",
                   user_message=content,
                   has_current_report=bool(session.current_report),
                   result=intent)

                # 検出モードをフロントに通知
                if intent not in ("none",):
                    if intent == "refine":
                        _mode_display = "レポート修正"
                    else:
                        _mode_display = next(
                            (m.get("name", intent) for m in mode_candidates if m.get("id") == intent),
                            intent,
                        )
                    await ws.send_json({"type": "mode_detected", "mode_id": intent, "mode_name": _mode_display})

                # CEO layer を毎メッセージ更新
                if intent not in ("refine", "none"):
                    session.ceo_layer = _fetch_ceo_layer(cosmos, intent)
                else:
                    session.ceo_layer = ""

                constraints = _fetch_constraints(cosmos)
                qualitative = _fetch_qualitative(cosmos)

                if intent == "assignment":
                    _t(trace_log, type="agent_invocation",
                       mode=AgentMode.ASSIGNMENT.value,
                       system_prompt=session.ceo_layer if session.ceo_layer else _load_prompt(AgentMode.ASSIGNMENT))
                    try:
                        full_report = await orch.chat_batch(
                            user_message=content,
                            mode=AgentMode.ASSIGNMENT,
                            history=session.history,
                            constraints=constraints,
                            qualitative=qualitative,
                            ceo_layer=session.ceo_layer,
                            on_tool_call=tool_cb,
                            on_subagent_call=subagent_cb,
                            on_clarification=clarification_cb,
                        )

                        # 評価ループ（最大2回 = 初回生成 + 再生成2回で合計3回まで）
                        for _attempt in range(2):
                            _eval_result = await evaluate_report(full_report, constraints, qualitative, settings)
                            _t(trace_log, type="eval_result", attempt=_attempt,
                               passed=_eval_result["pass"],
                               violations=_eval_result["absolute"]["violations"],
                               advice=_eval_result["qualitative"]["advice"])
                            if _eval_result["pass"]:
                                break
                            _feedback_parts: list[str] = []
                            if not _eval_result["absolute"]["ok"]:
                                _violations = "\n".join(f"- {v}" for v in _eval_result["absolute"]["violations"])
                                _feedback_parts.append(f"【絶対条件違反】以下を必ず修正すること:\n{_violations}")
                            if not _eval_result["qualitative"]["ok"] and _eval_result["qualitative"]["advice"]:
                                _feedback_parts.append(f"【定性方針への改善指摘】\n{_eval_result['qualitative']['advice']}")
                            if not _feedback_parts:
                                break
                            _feedback_msg = (
                                "【評価エージェントのフィードバック】\n\n"
                                + "\n\n".join(_feedback_parts)
                                + "\n\n上記の問題を反映して、前回のレポートを修正してください。"
                                "データの再取得は不要です。レポートを修正して全文を出力してください。"
                            )
                            full_report = await orch.chat_batch(
                                user_message=_feedback_msg,
                                mode=AgentMode.ASSIGNMENT,
                                history=session.history,
                                constraints=constraints,
                                qualitative=qualitative,
                                ceo_layer=session.ceo_layer,
                                on_tool_call=tool_cb,
                                on_subagent_call=subagent_cb,
                                on_clarification=clarification_cb,
                            )

                        first_heading = next((l for l in full_report.split("\n") if l.startswith("#")), None)
                        title = first_heading.replace("#", "").strip() if first_heading else "アサイン提案レポート"
                        project_id = _detect_project_id(cosmos.projects, content)
                        stored = await save_report(
                            cosmos.reports,
                            type_="assignment",
                            title=title,
                            markdown=full_report,
                            axis=None,
                            member_id=None,
                            project_id=project_id,
                        )
                        session.current_report = full_report
                        session.current_report_id = stored.id
                        assistant_note = f"アサイン提案「{title}」を作成しました。レポートタブで確認できます。"
                        _t(trace_log, type="assistant_response", content=assistant_note)
                        await ws.send_json({"type": "report_chunk", "text": full_report})
                        await ws.send_json({"type": "report_done", "report_type": "assignment", "report_id": stored.id})
                        if chat_id:
                            chat_display_msgs.append({"role": "user", "content": content})
                            chat_display_msgs.append({"role": "assistant", "content": assistant_note})
                            _persist_chat(cosmos, chat_id, chat_display_msgs, session, chat_created_at, trace_log)
                    except Exception as exc:  # noqa: BLE001
                        await ws.send_json({"type": "error", "message": str(exc)})

                elif intent == "skill_analysis":
                    _t(trace_log, type="agent_invocation",
                       mode=AgentMode.SKILL_ANALYSIS.value,
                       system_prompt=session.ceo_layer if session.ceo_layer else _load_prompt(AgentMode.SKILL_ANALYSIS))
                    full_report = await orch.chat_batch(
                        user_message=content,
                        mode=AgentMode.SKILL_ANALYSIS,
                        history=session.history,
                        constraints=constraints,
                        qualitative=qualitative,
                        ceo_layer=session.ceo_layer,
                        on_tool_call=tool_cb,
                        on_subagent_call=subagent_cb,
                        on_clarification=clarification_cb,
                    )
                    _heading_count = full_report.count("\n##") + full_report.count("\n#")
                    _is_complete = len(full_report.strip()) >= 300 and _heading_count >= 2
                    if not _is_complete:
                        _t(trace_log, type="assistant_response", content=full_report)
                        await ws.send_json({"type": "chunk", "text": full_report})
                        await ws.send_json({"type": "done"})
                        if chat_id:
                            chat_display_msgs.append({"role": "user", "content": content})
                            chat_display_msgs.append({"role": "assistant", "content": full_report})
                            _persist_chat(cosmos, chat_id, chat_display_msgs, session, chat_created_at, trace_log)
                    else:
                        first_heading = next((l for l in full_report.split("\n") if l.startswith("#")), None)
                        title = first_heading.replace("#", "").strip() if first_heading else "スキル分析レポート"
                        stored = await save_report(
                            cosmos.reports,
                            type_="skill",
                            title=title,
                            markdown=full_report,
                            axis=None,
                            member_id=None,
                            project_id=None,
                        )
                        skill_note = f"スキル分析「{title}」を作成しました。レポートタブで確認できます。"
                        _t(trace_log, type="assistant_response", content=skill_note)
                        await ws.send_json({"type": "report_chunk", "text": full_report})
                        await ws.send_json({"type": "report_done", "report_type": "skill", "report_id": stored.id})
                        if chat_id:
                            chat_display_msgs.append({"role": "user", "content": content})
                            chat_display_msgs.append({"role": "assistant", "content": skill_note})
                            _persist_chat(cosmos, chat_id, chat_display_msgs, session, chat_created_at, trace_log)

                elif intent == "refine":
                    _t(trace_log, type="agent_invocation", mode="assignment_refine",
                       system_prompt=session.ceo_layer if session.ceo_layer else _load_prompt(AgentMode.ASSIGNMENT))
                    refine_msg = (
                        f"現在のアサイン提案レポート:\n\n{session.current_report}\n\n"
                        "---\n\n"
                        f"修正指示: {content}\n\n"
                        "上記レポートを修正指示に従って更新してください。"
                        "最初の1行に「変更点: （変更内容の1〜2文サマリー）」を記載し、"
                        "2行目以降に完全な修正済みレポートのMarkdownを出力してください。"
                        "修正対象以外の項目は元のレポートの内容をそのまま維持してください。"
                    )
                    full_response = await orch.chat_batch(
                        user_message=refine_msg,
                        mode=AgentMode.ASSIGNMENT,
                        history=session.history,
                        constraints=constraints,
                        qualitative=qualitative,
                        ceo_layer=session.ceo_layer,
                        on_tool_call=tool_cb,
                        on_subagent_call=subagent_cb,
                        on_clarification=clarification_cb,
                    )
                    lines = full_response.strip().split("\n", 1)
                    if lines[0].startswith("変更点"):
                        summary = lines[0].split(":", 1)[-1].strip()
                        report_body = lines[1].strip() if len(lines) > 1 else full_response
                    else:
                        summary = lines[0].strip()
                        report_body = full_response

                    first_heading = next((l for l in report_body.split("\n") if l.startswith("#")), None)
                    title = first_heading.replace("#", "").strip() if first_heading else "アサイン提案レポート"

                    _t(trace_log, type="assistant_response", content=summary)
                    await ws.send_json({"type": "chunk", "text": summary})
                    await ws.send_json({"type": "done"})
                    session.current_report = report_body

                    if session.current_report_id:
                        await update_report(
                            cosmos.reports,
                            session.current_report_id,
                            title=title,
                            markdown=report_body,
                            extra_entry=ChatEntry(role="user", content=content),
                        )
                        await ws.send_json({"type": "report_chunk", "text": report_body})
                        await ws.send_json({
                            "type": "report_done",
                            "report_type": "assignment_refine",
                            "report_id": session.current_report_id,
                        })
                    else:
                        await ws.send_json({"type": "report_chunk", "text": report_body})
                        await ws.send_json({"type": "report_done", "report_type": "assignment_refine"})

                    if chat_id:
                        chat_display_msgs.append({"role": "user", "content": content})
                        chat_display_msgs.append({"role": "assistant", "content": summary})
                        _persist_chat(cosmos, chat_id, chat_display_msgs, session, chat_created_at, trace_log)

                else:  # base_chat / custom mode / none
                    _t(trace_log, type="agent_invocation",
                       mode=AgentMode.BASE_CHAT.value,
                       system_prompt=_load_prompt(AgentMode.BASE_CHAT))

                    # Phase 1: Planner
                    full_plan = await orch.plan_query(
                        user_message=content,
                        history=session.history,
                    )
                    _t(trace_log, type="planner_output", plan=full_plan[:200])
                    if full_plan:
                        await ws.send_json({"type": "plan_chunk", "text": full_plan})
                    await ws.send_json({"type": "plan_done"})

                    # Phase 2: Executor
                    response_chunks: list[str] = []
                    async for chunk in orch.chat(
                        user_message=content,
                        mode=AgentMode.BASE_CHAT,
                        history=session.history,
                        plan_hint=full_plan,
                        constraints=constraints,
                        qualitative=qualitative,
                        ceo_layer=session.ceo_layer,
                        on_tool_call=tool_cb,
                        on_subagent_call=subagent_cb,
                        on_clarification=clarification_cb,
                    ):
                        await ws.send_json({"type": "chunk", "text": chunk})
                        response_chunks.append(chunk)
                    full_response_text = "".join(response_chunks)
                    _t(trace_log, type="assistant_response", content=full_response_text)
                    await ws.send_json({"type": "done"})
                    if chat_id:
                        chat_display_msgs.append({"role": "user", "content": content})
                        chat_display_msgs.append({"role": "assistant", "content": full_response_text})
                        _persist_chat(cosmos, chat_id, chat_display_msgs, session, chat_created_at, trace_log)

            except Exception as exc:  # noqa: BLE001
                await ws.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        return
