from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ThreadCreateRequest(BaseModel):
    thread_id: str | None = None


class ThreadCreateResponse(BaseModel):
    thread_id: str


class ThreadDeleteResponse(BaseModel):
    deleted: str


class ThreadClearResponse(BaseModel):
    cleared: str


class ThreadListResponse(BaseModel):
    threads: list[str]


class TranscriptMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str


class ThreadMessagesResponse(BaseModel):
    messages: list[TranscriptMessage]


class ModelListResponse(BaseModel):
    default_model: str
    models: list[str]


class SessionModelRequest(BaseModel):
    model: str | None = None


class SessionModelResponse(BaseModel):
    model: str
    default_model: str
    is_default: bool
