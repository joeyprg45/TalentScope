"""ask_user_clarification — Main Agent からユーザーへ逆質問するための kernel_function.

呼び出されると、ClarificationCallback 経由でフロントに質問を送信し、
ユーザーの回答が返ってくるまでブロックする（asyncio.Future）。
SK 側はこの戻り値をツール結果として LLM に渡すため、
ReAct ループに透過的に組み込まれる。
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Annotated, Awaitable, Callable

from semantic_kernel.functions import kernel_function

# シグネチャ: callback(question, options) -> ユーザー回答テキスト
ClarificationCallback = Callable[[str, list[dict]], Awaitable[str]]
_clarification_callback_var: ContextVar[ClarificationCallback | None] = ContextVar(
    "_clarification_callback", default=None,
)


def set_clarification_callback(cb: ClarificationCallback | None):
    return _clarification_callback_var.set(cb)


def reset_clarification_callback(token) -> None:
    _clarification_callback_var.reset(token)


class ClarificationPlugin:
    """Main Agent のみが持つ逆質問ツール."""

    @kernel_function(
        description=(
            "不明点・前提欠如・複数解釈がありうる場合にユーザーへ逆質問する。"
            "回答が返るまで処理は停止する。明らかに回答できる質問には使わない（過剰確認しない）"
        )
    )
    async def ask_user_clarification(
        self,
        question: Annotated[str, "ユーザーに尋ねる質問文（1〜2文）"],
        options_json: Annotated[
            str,
            'JSON配列の選択肢。例: [{"id":"a","label":"PJ-A: LLM基盤","description":"..."},{"id":"b","label":"PJ-B"}]'
            ' 空配列なら自由記述のみ',
        ] = "[]",
    ) -> str:
        cb = _clarification_callback_var.get()
        if cb is None:
            return "（逆質問機能が無効のため回答不可。質問を別の手段で確認してください）"
        try:
            options = json.loads(options_json) if options_json else []
            if not isinstance(options, list):
                options = []
        except json.JSONDecodeError:
            options = []
        answer = await cb(question, options)
        return answer or "（ユーザー回答なし）"
