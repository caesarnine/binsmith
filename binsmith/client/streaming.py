from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import TypeAdapter
from ag_ui.core import Event


async def iter_ag_ui_events(lines: AsyncIterator[str]) -> AsyncIterator[Event]:
    adapter = TypeAdapter(Event)
    async for line in lines:
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].lstrip()
        if not payload or payload == "[DONE]":
            continue
        yield adapter.validate_json(payload)
