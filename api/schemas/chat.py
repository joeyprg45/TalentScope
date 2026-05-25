from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class UserMessage(BaseModel):
    type: Literal["user_message"]
    content: str


class Chunk(BaseModel):
    type: Literal["chunk"] = "chunk"
    text: str


class Done(BaseModel):
    type: Literal["done"] = "done"


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
