"""TalentScope FastAPI エントリーポイント.

起動: uv run uvicorn api.main:app --reload --port 8000
Swagger: http://localhost:8000/docs
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, chat_sessions, health, meetings, members, projects, reports

app = FastAPI(title="TalentScope API", version="0.1.0")

_cors_env = os.getenv("CORS_ORIGINS", "")
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_extra_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
_allow_origins = _default_origins + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,   prefix="/api")
app.include_router(members.router,  prefix="/api/members",  tags=["members"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(meetings.router, prefix="/api/meetings", tags=["meetings"])
app.include_router(reports.router,  prefix="/api/reports",  tags=["reports"])
app.include_router(chat.router,          prefix="/api/chat",          tags=["chat"])
app.include_router(chat_sessions.router, prefix="/api/chat",          tags=["chat-sessions"])
