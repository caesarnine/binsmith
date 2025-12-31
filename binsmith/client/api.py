from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from ag_ui.core import Event, RunAgentInput

from binsmith.client.streaming import iter_ag_ui_events
from binsmith.protocol.models import (
    ModelListResponse,
    SessionModelRequest,
    SessionModelResponse,
    ThreadClearResponse,
    ThreadCreateRequest,
    ThreadCreateResponse,
    ThreadDeleteResponse,
    ThreadListResponse,
    ThreadMessagesResponse,
)


class BinsmithClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    def _raise_for_status(self, response: httpx.Response, fallback: str) -> None:
        try:
            response.raise_for_status()
            return
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                data = response.json()
                if isinstance(data, dict) and data.get("detail"):
                    detail = str(data["detail"])
            except Exception:
                detail = ""
            if not detail:
                try:
                    text = response.text
                    if text:
                        detail = text.strip()
                except Exception:
                    detail = ""
            message = fallback
            if detail:
                message = f"{fallback}. {detail}"
            raise RuntimeError(message) from exc

    async def _raise_for_status_async(self, response: httpx.Response, fallback: str) -> None:
        if response.status_code < 400:
            return
        detail = ""
        try:
            body = await response.aread()
            if body:
                try:
                    data = response.json()
                    if isinstance(data, dict) and data.get("detail"):
                        detail = str(data["detail"])
                except Exception:
                    try:
                        detail = body.decode("utf-8", errors="ignore").strip()
                    except Exception:
                        detail = ""
        except Exception:
            detail = ""
        message = fallback
        if detail:
            message = f"{fallback}. {detail}"
        raise RuntimeError(message)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_session_id(self) -> str:
        response = await self._client.get("/session")
        self._raise_for_status(response, "Failed to load session")
        data = response.json()
        session_id = data.get("session_id") or data.get("sessionId")
        if not session_id:
            raise ValueError("Server did not return a session id.")
        return session_id

    async def list_models(self) -> ModelListResponse:
        response = await self._client.get("/models")
        self._raise_for_status(response, "Failed to load models")
        return ModelListResponse.model_validate(response.json())

    async def get_session_model(self, session_id: str) -> SessionModelResponse:
        response = await self._client.get(f"/sessions/{session_id}/model")
        self._raise_for_status(response, "Failed to load model")
        return SessionModelResponse.model_validate(response.json())

    async def set_session_model(self, session_id: str, model: str | None) -> SessionModelResponse:
        payload = SessionModelRequest(model=model)
        response = await self._client.put(
            f"/sessions/{session_id}/model",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        self._raise_for_status(response, "Failed to set model")
        return SessionModelResponse.model_validate(response.json())

    async def list_threads(self, session_id: str) -> list[str]:
        response = await self._client.get(f"/sessions/{session_id}/threads")
        self._raise_for_status(response, "Failed to load threads")
        payload = ThreadListResponse.model_validate(response.json())
        return payload.threads

    async def create_thread(self, session_id: str, thread_id: str | None = None) -> str:
        payload = ThreadCreateRequest(thread_id=thread_id)
        response = await self._client.post(
            f"/sessions/{session_id}/threads",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        self._raise_for_status(response, "Failed to create thread")
        data = ThreadCreateResponse.model_validate(response.json())
        return data.thread_id

    async def delete_thread(self, session_id: str, thread_id: str) -> str:
        response = await self._client.delete(f"/sessions/{session_id}/threads/{thread_id}")
        self._raise_for_status(response, "Failed to delete thread")
        data = ThreadDeleteResponse.model_validate(response.json())
        return data.deleted

    async def clear_thread(self, session_id: str, thread_id: str) -> str:
        response = await self._client.post(f"/sessions/{session_id}/threads/{thread_id}/clear")
        self._raise_for_status(response, "Failed to clear thread")
        data = ThreadClearResponse.model_validate(response.json())
        return data.cleared

    async def get_thread_messages(self, session_id: str, thread_id: str) -> ThreadMessagesResponse:
        response = await self._client.get(f"/sessions/{session_id}/threads/{thread_id}/messages")
        self._raise_for_status(response, "Failed to load messages")
        return ThreadMessagesResponse.model_validate(response.json())

    async def iter_thread_events(self, session_id: str, thread_id: str) -> AsyncIterator[Event]:
        headers = {"accept": "text/event-stream"}
        async with self._client.stream(
            "GET",
            f"/sessions/{session_id}/threads/{thread_id}/events",
            headers=headers,
        ) as response:
            await self._raise_for_status_async(response, "Failed to load thread events")
            async for event in iter_ag_ui_events(response.aiter_lines()):
                yield event

    async def run_stream(self, run_input: RunAgentInput) -> AsyncIterator[Event]:
        payload = run_input.model_dump(mode="json", by_alias=True, exclude_none=True)
        headers = {"accept": "text/event-stream"}
        async with self._client.stream("POST", "/ag-ui", json=payload, headers=headers) as response:
            await self._raise_for_status_async(response, "Failed to run agent")
            async for event in iter_ag_ui_events(response.aiter_lines()):
                yield event
