from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from agents.orchestrator import AgentMode, ToolCallCallback
from api.deps import get_orchestrator
from api.services.session_store import get_session

router = APIRouter()


def _make_tool_callback(ws: WebSocket) -> ToolCallCallback:
    async def on_tool_call(tool_name: str, status: str, args: dict[str, str] | None = None) -> None:
        await ws.send_json({"type": "tool_call", "tool_name": tool_name, "status": status, "args": args or {}})
    return on_tool_call


@router.websocket("/ws")
async def chat_ws(ws: WebSocket, session_id: str = Query(..., min_length=1)) -> None:
    await ws.accept()
    orch = get_orchestrator()
    session = get_session(session_id)
    tool_cb = _make_tool_callback(ws)

    try:
        while True:
            data = await ws.receive_json()

            # 軸確定メッセージ: フロントエンドが axis_prompt 後に送る
            if data.get("type") == "axis_confirm":
                axis = (data.get("axis") or "ability").strip()
                content = (data.get("original_content") or "").strip()
                if not content:
                    continue
                session.current_axis = axis
                try:
                    full_report = await orch.chat_batch(
                        user_message=content,
                        mode=AgentMode.ASSIGNMENT,
                        history=session.history,
                        axis=axis,
                        on_tool_call=tool_cb,
                    )
                    session.current_report = full_report
                    await ws.send_json({"type": "report_chunk", "text": full_report})
                    await ws.send_json({"type": "report_done", "report_type": "assignment"})
                except Exception as exc:  # noqa: BLE001
                    await ws.send_json({"type": "error", "message": str(exc)})
                continue

            if data.get("type") != "user_message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue

            try:
                intent = await orch.classify_intent(
                    user_message=content,
                    has_current_report=bool(session.current_report),
                )

                if intent == "assignment":
                    await ws.send_json({"type": "axis_prompt", "original_content": content})

                elif intent == "skill":
                    full_report = await orch.chat_batch(
                        user_message=content,
                        mode=AgentMode.SKILL_ANALYSIS,
                        history=session.history,
                        axis="ability",
                        on_tool_call=tool_cb,
                    )
                    await ws.send_json({"type": "report_chunk", "text": full_report})
                    await ws.send_json({"type": "report_done", "report_type": "skill"})

                elif intent == "refine":
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
                        history=None,
                        axis=session.current_axis,
                        on_tool_call=tool_cb,
                    )
                    lines = full_response.strip().split("\n", 1)
                    if lines[0].startswith("変更点"):
                        summary = lines[0].split(":", 1)[-1].strip()
                        report_body = lines[1].strip() if len(lines) > 1 else full_response
                    else:
                        summary = lines[0].strip()
                        report_body = full_response
                    await ws.send_json({"type": "chunk", "text": summary})
                    await ws.send_json({"type": "done"})
                    session.current_report = report_body
                    await ws.send_json({"type": "report_chunk", "text": report_body})
                    await ws.send_json({"type": "report_done", "report_type": "assignment"})

                else:  # chat
                    async for chunk in orch.chat(
                        user_message=content,
                        mode=AgentMode.BASE_CHAT,
                        history=session.history,
                        on_tool_call=tool_cb,
                    ):
                        await ws.send_json({"type": "chunk", "text": chunk})
                    await ws.send_json({"type": "done"})

            except Exception as exc:  # noqa: BLE001
                await ws.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        return
