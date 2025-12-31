from __future__ import annotations

from collections.abc import Iterable

from ag_ui.core import RunAgentInput
from pydantic_ai.ui.ag_ui import AGUIAdapter


def resolve_session_id(adapter: AGUIAdapter, *, default_session_id: str) -> str:
    state = adapter.state
    if isinstance(state, dict):
        session_id = state.get("session_id") or state.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
    forwarded = getattr(adapter.run_input, "forwarded_props", None)
    if isinstance(forwarded, dict):
        session_id = forwarded.get("session_id") or forwarded.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
    return default_session_id


def resolve_session_id_from_run_input(run_input: RunAgentInput, *, default_session_id: str) -> str:
    state = run_input.state
    if isinstance(state, dict):
        session_id = state.get("session_id") or state.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
    forwarded = getattr(run_input, "forwarded_props", None)
    if isinstance(forwarded, dict):
        session_id = forwarded.get("session_id") or forwarded.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
    return default_session_id


def incoming_has_history(adapter: AGUIAdapter) -> bool:
    roles = {getattr(msg, "role", None) for msg in adapter.run_input.messages}
    return bool(roles.intersection({"assistant", "tool"}))


def select_message_history(adapter: AGUIAdapter, stored_messages: Iterable) -> list:
    if incoming_has_history(adapter):
        return []
    return list(stored_messages)
