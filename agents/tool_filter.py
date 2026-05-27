"""共有ツールコールフィルタ.

orchestrator の Main Agent と各サブエージェントカーネルの両方に登録することで、
ツール呼び出しを WebSocket コールバックへ転送する。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable

ToolCallCallback = Callable[[str, str, dict[str, str], "str | None"], Awaitable[None]]
_tool_callback_var: ContextVar[ToolCallCallback | None] = ContextVar("_tool_callback", default=None)


async def _tool_filter(context: Any, next: Callable) -> None:
    fn = getattr(context, "function", None)
    fn_name = (
        getattr(fn, "fully_qualified_name", None)
        or f"{getattr(fn, 'plugin_name', '')}-{getattr(fn, 'name', 'unknown')}"
        if fn else "unknown"
    )
    args_dict: dict[str, str] = {}
    raw_args = getattr(context, "arguments", None)
    if raw_args:
        try:
            for k, v in raw_args.items():
                if not k.startswith("_") and v is not None:
                    args_dict[k] = str(v)
        except Exception:
            pass
    cb = _tool_callback_var.get()
    if cb:
        await cb(fn_name, "start", args_dict, None)
    await next(context)
    result_str: str | None = None
    try:
        if hasattr(context, "function_result") and context.function_result is not None:
            result_str = str(context.function_result)
    except Exception:  # noqa: BLE001
        pass
    if cb:
        await cb(fn_name, "done", args_dict, result_str)
