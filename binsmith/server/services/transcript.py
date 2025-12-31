from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic_ai.messages import (
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)

from binsmith.protocol.models import TranscriptMessage


def build_transcript(messages: Iterable[ModelMessage]) -> list[TranscriptMessage]:
    transcript: list[TranscriptMessage] = []
    for message in messages:
        if isinstance(message, ModelRequest):
            transcript.extend(_transcript_from_request(message))
        elif isinstance(message, ModelResponse):
            transcript.extend(_transcript_from_response(message))
    return transcript


def _transcript_from_request(message: ModelRequest) -> list[TranscriptMessage]:
    items: list[TranscriptMessage] = []
    for part in message.parts:
        if isinstance(part, SystemPromptPart):
            items.append(TranscriptMessage(role="system", content=part.content))
        elif isinstance(part, UserPromptPart):
            items.append(
                TranscriptMessage(role="user", content=_stringify_user_content(part.content))
            )
    return items


def _transcript_from_response(message: ModelResponse) -> list[TranscriptMessage]:
    items: list[TranscriptMessage] = []
    if message.text:
        items.append(TranscriptMessage(role="assistant", content=message.text))
    for part in message.parts:
        if isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
            items.append(
                TranscriptMessage(role="tool", content=_stringify_value(part.content))
            )
    return items


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
    return _stringify_value(content)


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except TypeError:
        return str(value)
