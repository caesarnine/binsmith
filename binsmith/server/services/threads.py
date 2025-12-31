from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pydantic_ai.messages import ModelMessage

from binsmith.core.session import SessionStore


def list_threads(store: SessionStore, session_id: str) -> list[str]:
    return store.list_threads(session_id)


def create_thread(
    store: SessionStore,
    *,
    session_id: str,
    thread_id: str,
    workspace: Path,
) -> None:
    if thread_id in store.list_threads(session_id):
        raise ValueError("Thread already exists.")
    store.load_thread(session_id, thread_id, workspace=workspace)


def delete_thread(store: SessionStore, *, session_id: str, thread_id: str) -> None:
    store.delete_thread(session_id, thread_id)


def load_thread_messages(
    store: SessionStore,
    *,
    session_id: str,
    thread_id: str,
    workspace: Path,
) -> Sequence[ModelMessage]:
    thread_state = store.load_thread(session_id, thread_id, workspace=workspace)
    return thread_state.messages
