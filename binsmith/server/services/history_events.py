from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import uuid4

from ag_ui.core import (
    TextMessageStartEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    ThinkingStartEvent,
    ThinkingTextMessageStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingEndEvent,
    ToolCallStartEvent,
    ToolCallArgsEvent,
    ToolCallResultEvent,
)
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

BUILTIN_TOOL_CALL_ID_PREFIX = "pyd_ai_builtin"


def iter_history_events(messages: Iterable[ModelMessage]) -> Iterator[object]:
    for message in messages:
        if isinstance(message, ModelRequest):
            yield from _events_from_request(message)
        elif isinstance(message, ModelResponse):
            yield from _events_from_response(message)


def _events_from_request(message: ModelRequest) -> Iterator[object]:
    for part in message.parts:
        if isinstance(part, UserPromptPart):
            content = _stringify_user_content(part.content)
            if not content:
                continue
            message_id = uuid4().hex
            yield TextMessageStartEvent(message_id=message_id, role="user")
            yield TextMessageContentEvent(message_id=message_id, delta=content)
            yield TextMessageEndEvent(message_id=message_id)
        elif isinstance(part, ToolReturnPart):
            tool_call_id = _tool_call_id(part)
            yield ToolCallResultEvent(
                message_id=uuid4().hex,
                tool_call_id=tool_call_id,
                content=part.model_response_str(),
                role="tool",
            )


def _events_from_response(message: ModelResponse) -> Iterator[object]:
    text_open = False
    text_message_id: str | None = None
    current_parent_id = uuid4().hex

    def close_text() -> Iterator[object]:
        nonlocal text_open, text_message_id
        if text_open and text_message_id:
            yield TextMessageEndEvent(message_id=text_message_id)
        text_open = False
        text_message_id = None

    for part in message.parts:
        if isinstance(part, ThinkingPart):
            yield from close_text()
            if part.content:
                yield ThinkingStartEvent()
                yield ThinkingTextMessageStartEvent()
                yield ThinkingTextMessageContentEvent(delta=part.content)
                yield ThinkingTextMessageEndEvent()
                yield ThinkingEndEvent()
            continue

        if isinstance(part, (ToolCallPart, BuiltinToolCallPart)):
            yield from close_text()
            tool_call_id = _tool_call_id(part)
            yield ToolCallStartEvent(
                tool_call_id=tool_call_id,
                tool_call_name=part.tool_name,
                parent_message_id=current_parent_id,
            )
            if part.args:
                yield ToolCallArgsEvent(tool_call_id=tool_call_id, delta=_tool_args(part))
            continue

        if isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
            yield from close_text()
            tool_call_id = _tool_call_id(part)
            yield ToolCallResultEvent(
                message_id=uuid4().hex,
                tool_call_id=tool_call_id,
                content=part.model_response_str(),
                role="tool",
            )
            continue

        if hasattr(part, "content"):
            content = getattr(part, "content")
            if isinstance(content, str) and content:
                if not text_open:
                    text_message_id = uuid4().hex
                    current_parent_id = text_message_id
                    yield TextMessageStartEvent(message_id=text_message_id, role="assistant")
                    text_open = True
                yield TextMessageContentEvent(message_id=text_message_id, delta=content)

    if text_open and text_message_id:
        yield TextMessageEndEvent(message_id=text_message_id)


def _tool_call_id(part: Any) -> str:
    tool_call_id = getattr(part, "tool_call_id", uuid4().hex)
    if isinstance(part, (BuiltinToolCallPart, BuiltinToolReturnPart)):
        provider_name = getattr(part, "provider_name", "") or ""
        return "|".join([BUILTIN_TOOL_CALL_ID_PREFIX, provider_name, tool_call_id])
    return tool_call_id


def _tool_args(part: Any) -> str:
    if hasattr(part, "args_as_json_str"):
        return part.args_as_json_str()
    args = getattr(part, "args", None)
    if args is None:
        return "{}"
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, ensure_ascii=True)
    except TypeError:
        return str(args)


def _stringify_user_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        rendered: list[str] = []
        for item in content:
            if isinstance(item, str):
                rendered.append(item)
            else:
                media_type = getattr(item, "media_type", "binary")
                rendered.append(f"[{media_type} content]")
        return "\n".join(rendered)
    if content is None:
        return ""
    return str(content)
