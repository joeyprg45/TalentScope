"""WebSocket セッションごとの ChatHistory と レポート状態を in-memory で保持."""
from __future__ import annotations

from dataclasses import dataclass, field

from semantic_kernel.contents.chat_history import ChatHistory


@dataclass
class SessionData:
    history: ChatHistory = field(default_factory=ChatHistory)
    current_report: str | None = None     # 最新のアサイン提案レポート Markdown
    current_report_id: str | None = None  # CosmosDB の reports コンテナ ID
    ceo_layer: str = ""                   # 直前メッセージで判別されたモードの判断基準


_sessions: dict[str, SessionData] = {}


def get_session(session_id: str) -> SessionData:
    if session_id not in _sessions:
        _sessions[session_id] = SessionData()
    return _sessions[session_id]


def get_history(session_id: str) -> ChatHistory:
    """後方互換: ChatHistory を直接返す."""
    return get_session(session_id).history


def reset_history(session_id: str) -> None:
    _sessions.pop(session_id, None)
