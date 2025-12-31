from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid
from typing import Callable, Protocol, Sequence

from pydantic_ai.messages import ModelMessage


@dataclass
class ThreadState:
    session_id: str
    thread_id: str
    workspace: Path
    messages: list[ModelMessage]


class SessionStore(Protocol):
    def load_thread(
        self,
        session_id: str,
        thread_id: str,
        *,
        workspace: Path,
    ) -> ThreadState:
        ...

    def save_thread(
        self,
        session_id: str,
        thread_id: str,
        *,
        workspace: Path,
        messages: Sequence[ModelMessage],
    ) -> None:
        ...

    def list_threads(self, session_id: str) -> list[str]:
        ...

    def list_sessions(self) -> list[str]:
        ...

    def delete_thread(self, session_id: str, thread_id: str) -> None:
        ...

    def get_session_model(self, session_id: str) -> str | None:
        ...

    def set_session_model(self, session_id: str, model: str | None) -> None:
        ...


def generate_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
