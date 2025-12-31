from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_ai.exceptions import UserError
from pydantic_ai.ui.ag_ui import AGUIAdapter
from ag_ui.encoder import EventEncoder

from binsmith.config import StorageConfig, load_storage_config, load_or_create_session_id
from binsmith.core.messages import merge_messages
from binsmith.persistence.sqlite_store import SQLiteSessionStore
from binsmith.runtime import create_deps, get_agent, sync_global_tools
from binsmith.server.context import AppContext
from binsmith.server.services.models import (
    get_default_model_name,
    is_known_model,
    list_known_models,
    validate_model_credentials,
)
from binsmith.server.services.sessions import resolve_session_id_from_run_input, select_message_history
from binsmith.server.services.threads import create_thread, delete_thread, list_threads, load_thread_messages
from binsmith.server.services.transcript import build_transcript
from binsmith.server.services.history_events import iter_history_events
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

logger = logging.getLogger(__name__)


def create_app(config: StorageConfig | None = None) -> FastAPI:
    config = config or load_storage_config()
    store = SQLiteSessionStore(config.db_path)
    ctx = AppContext(
        config=config,
        store=store,
        workspace=config.workspace_dir,
        project_root=config.project_root,
    )

    app = FastAPI(title="Binsmith Agent API")
    app.state.ctx = ctx

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/session")
    async def api_session() -> dict[str, str]:
        session_id = load_or_create_session_id(ctx.config.session_id_path)
        return {"session_id": session_id}

    @app.get("/models", response_model=ModelListResponse)
    async def api_list_models() -> ModelListResponse:
        default_model = get_default_model_name()
        return ModelListResponse(default_model=default_model, models=list(list_known_models()))

    @app.get("/sessions/{session_id}/model", response_model=SessionModelResponse)
    async def api_get_session_model(session_id: str) -> SessionModelResponse:
        default_model = get_default_model_name()
        model = ctx.store.get_session_model(session_id) or default_model
        return SessionModelResponse(
            model=model,
            default_model=default_model,
            is_default=model == default_model,
        )

    @app.put("/sessions/{session_id}/model", response_model=SessionModelResponse)
    async def api_set_session_model(
        session_id: str,
        payload: SessionModelRequest,
    ) -> SessionModelResponse:
        default_model = get_default_model_name()
        model = (payload.model or "").strip() if payload.model is not None else None
        if model:
            if not is_known_model(model):
                raise HTTPException(status_code=400, detail="Unknown model.")
            try:
                validate_model_credentials(model)
            except UserError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            ctx.store.set_session_model(session_id, model)
            selected = model
        else:
            ctx.store.set_session_model(session_id, None)
            selected = default_model
        return SessionModelResponse(
            model=selected,
            default_model=default_model,
            is_default=selected == default_model,
        )

    @app.get("/sessions/{session_id}/threads", response_model=ThreadListResponse)
    async def api_list_threads(session_id: str) -> ThreadListResponse:
        return ThreadListResponse(threads=list_threads(ctx.store, session_id))

    @app.post("/sessions/{session_id}/threads", response_model=ThreadCreateResponse)
    async def api_create_thread(session_id: str, payload: ThreadCreateRequest) -> ThreadCreateResponse:
        thread_id = payload.thread_id or ""
        if not thread_id:
            from binsmith.core.session import generate_thread_id

            thread_id = generate_thread_id()
        try:
            create_thread(ctx.store, session_id=session_id, thread_id=thread_id, workspace=ctx.workspace)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ThreadCreateResponse(thread_id=thread_id)

    @app.delete("/sessions/{session_id}/threads/{thread_id}", response_model=ThreadDeleteResponse)
    async def api_delete_thread(session_id: str, thread_id: str) -> ThreadDeleteResponse:
        if thread_id not in list_threads(ctx.store, session_id):
            raise HTTPException(status_code=404, detail="Thread not found.")
        delete_thread(ctx.store, session_id=session_id, thread_id=thread_id)
        return ThreadDeleteResponse(deleted=thread_id)

    @app.post(
        "/sessions/{session_id}/threads/{thread_id}/clear",
        response_model=ThreadClearResponse,
    )
    async def api_clear_thread(session_id: str, thread_id: str) -> ThreadClearResponse:
        if thread_id not in list_threads(ctx.store, session_id):
            raise HTTPException(status_code=404, detail="Thread not found.")
        ctx.store.save_thread(session_id, thread_id, workspace=ctx.workspace, messages=[])
        return ThreadClearResponse(cleared=thread_id)

    @app.get(
        "/sessions/{session_id}/threads/{thread_id}/messages",
        response_model=ThreadMessagesResponse,
    )
    async def api_thread_messages(session_id: str, thread_id: str) -> ThreadMessagesResponse:
        messages = load_thread_messages(
            ctx.store,
            session_id=session_id,
            thread_id=thread_id,
            workspace=ctx.workspace,
        )
        transcript = build_transcript(messages)
        return ThreadMessagesResponse(messages=transcript)

    @app.get("/sessions/{session_id}/threads/{thread_id}/events")
    async def api_thread_events(session_id: str, thread_id: str):
        messages = load_thread_messages(
            ctx.store,
            session_id=session_id,
            thread_id=thread_id,
            workspace=ctx.workspace,
        )
        encoder = EventEncoder()

        def stream():
            for event in iter_history_events(messages):
                yield encoder.encode(event)

        return StreamingResponse(stream(), media_type=encoder.get_content_type())

    @app.post("/ag-ui")
    async def ag_ui(request: Request):
        body = await request.body()
        run_input = AGUIAdapter.build_run_input(body)
        default_session_id = load_or_create_session_id(ctx.config.session_id_path)
        session_id = resolve_session_id_from_run_input(
            run_input,
            default_session_id=default_session_id,
        )
        model_name = ctx.store.get_session_model(session_id) or get_default_model_name()
        try:
            agent = get_agent(model_name)
        except UserError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        adapter = AGUIAdapter(agent=agent, run_input=run_input, accept=request.headers.get("accept"))
        thread_id = adapter.run_input.thread_id
        thread_state = ctx.store.load_thread(session_id, thread_id, workspace=ctx.workspace)
        message_history = select_message_history(adapter, thread_state.messages)
        if logger.isEnabledFor(logging.DEBUG):
            incoming_roles = [getattr(msg, "role", None) for msg in adapter.run_input.messages]
            history_roles = [getattr(msg, "role", None) for msg in message_history]
            logger.debug(
                "ag_ui session=%s thread=%s incoming=%s history=%s",
                session_id,
                thread_id,
                incoming_roles,
                history_roles,
            )

        deps = create_deps(
            session_id=session_id,
            thread_id=thread_id,
            workspace=ctx.workspace,
            project_root=ctx.project_root,
        )

        def on_complete(result) -> None:
            incoming_messages = adapter.messages
            history_base = message_history
            merged = merge_messages(history_base, incoming_messages, result.new_messages())
            ctx.store.save_thread(session_id, thread_id, workspace=ctx.workspace, messages=merged)
            sync_global_tools(ctx.workspace)

        stream = adapter.run_stream(deps=deps, message_history=message_history, on_complete=on_complete)
        return adapter.streaming_response(stream)

    return app
