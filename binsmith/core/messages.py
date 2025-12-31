from __future__ import annotations

from typing import Iterable, Sequence

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter


def dump_messages(messages: Sequence[ModelMessage]) -> bytes:
    return ModelMessagesTypeAdapter.dump_json(list(messages))


def load_messages(data: bytes | None) -> list[ModelMessage]:
    if not data:
        return []
    return ModelMessagesTypeAdapter.validate_json(data)


def merge_messages(*chunks: Iterable[ModelMessage]) -> list[ModelMessage]:
    merged: list[ModelMessage] = []
    for chunk in chunks:
        merged.extend(chunk)
    return merged
