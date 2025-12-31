from __future__ import annotations

import json
import subprocess
from typing import Any, Optional
from uuid import uuid4

from ag_ui.core import (
    BaseEvent,
    RunAgentInput,
    RunErrorEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingTextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UserMessage,
)
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.suggester import Suggester
from textual.widgets import Input, Static

from binsmith.client import BinsmithClient
from binsmith.core.session import generate_thread_id
from binsmith.tui.widgets import ChatMessage, ToolCall


class _CommandSuggester(Suggester):
    def __init__(self, *, commands: list[str], model_provider) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self._commands = commands
        self._model_provider = model_provider

    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith("/"):
            return None

        if value.startswith("/model"):
            return self._suggest_model(value)

        for command in self._commands:
            if command.startswith(value):
                return command
        return None

    def _suggest_model(self, value: str) -> str | None:
        if value == "/model":
            return "/model "

        remainder = value[len("/model") :].lstrip()
        if remainder.startswith("list"):
            return "/model list "
        if remainder.startswith("default"):
            return "/model default"
        if remainder.startswith("set"):
            if remainder == "set":
                return "/model set "
            if remainder.startswith("set "):
                prefix = remainder[4:]
                base = "/model set "
            else:
                prefix = remainder
                base = "/model "
        else:
            prefix = remainder
            base = "/model "

        models = self._model_provider() or []
        if not models:
            return None

        needle = prefix.casefold()
        for model in models:
            if model.casefold().startswith(needle):
                return f"{base}{model}"
        return None


class BinsmithApp(App):
    """Binsmith - A bash-native AI agent (client)."""

    CSS = """
    Screen {
        background: #0d1117;
    }

    #header {
        height: 2;
        dock: top;
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 1;
    }

    #header-left {
        width: 1fr;
        content-align: left middle;
        color: #e6edf3;
        text-style: bold;
    }

    #header-right {
        width: auto;
        content-align: right middle;
        color: #7d8590;
    }

    #chat-scroll {
        height: 1fr;
        padding: 1 2;
        background: #0d1117;
    }

    #input-container {
        height: 3;
        dock: bottom;
        background: #161b22;
        border-top: solid #30363d;
        padding: 0 1;
    }

    #input {
        width: 1fr;
        border: none;
        background: #0d1117;
        color: #e6edf3;
        padding: 0 1;
    }

    #input:focus {
        border: none;
    }

    #status {
        width: 12;
        content-align: right middle;
        color: #7d8590;
    }

    #status.streaming {
        color: #58a6ff;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "cancel_run", "Cancel", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
    ]

    def __init__(
        self,
        *,
        server_url: str,
        server_process: subprocess.Popen | None = None,
    ):
        super().__init__()
        self.session_id = "..."
        self.thread_id = "..."  # Placeholder until mounted
        self.model_name: str | None = None
        self._default_model: str | None = None
        self._model_cache: list[str] | None = None
        self._model_loading = False
        self.server_url = server_url
        self.client = BinsmithClient(self.server_url)
        self._server_process = server_process
        self._command_suggester = _CommandSuggester(
            commands=[
                "/help",
                "/threads",
                "/thread",
                "/thread new",
                "/thread delete",
                "/clear",
                "/model",
                "/model list",
                "/model set",
                "/model default",
                "/quit",
                "/exit",
            ],
            model_provider=self._get_model_suggestions,
        )

        self._worker = None
        self._current_assistant: Optional[ChatMessage] = None
        self._current_thinking: Optional[ChatMessage] = None
        self._tool_calls: dict[str, ToolCall] = {}
        self._message_map: dict[str, ChatMessage] = {}
        self._mounted = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static("Binsmith", id="header-left")
            yield Static(self.thread_id, id="header-right")
        yield VerticalScroll(id="chat-scroll")
        with Horizontal(id="input-container"):
            yield Input(
                placeholder="Ask something... (/help)",
                id="input",
                suggester=self._command_suggester,
            )
            yield Static("", id="status")

    async def on_mount(self) -> None:
        self._mounted = True
        self.query_one("#input", Input).focus()

        try:
            self.session_id = await self.client.get_session_id()
        except Exception as exc:
            self._add_system_message(f"Failed to load session: {exc}")
            return

        threads = await self.client.list_threads(self.session_id)
        if threads:
            self.thread_id = threads[0]
        else:
            self.thread_id = "default"
            await self.client.create_thread(self.session_id, self.thread_id)

        await self._refresh_model()
        self.run_worker(self._load_thread_state(self.thread_id), exclusive=False)

    async def on_shutdown(self) -> None:
        await self.client.close()
        if self._server_process and self._server_process.poll() is None:
            self._server_process.terminate()
            try:
                self._server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._server_process.kill()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_cancel_run(self) -> None:
        if self._worker and self._worker.is_running:
            self._worker.cancel()
            self._set_status("")

    def action_clear_chat(self) -> None:
        chat = self.query_one("#chat-scroll", VerticalScroll)
        chat.remove_children()
        self._current_assistant = None
        self._current_thinking = None
        self._tool_calls = {}
        self._message_map = {}

    # -------------------------------------------------------------------------
    # Input Handling
    # -------------------------------------------------------------------------

    @on(Input.Submitted, "#input")
    async def handle_input(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        event.input.value = ""

        if not user_input:
            return

        if user_input.lower() in {"/quit", "/exit"}:
            self.exit()
            return

        if user_input.lower() == "/clear":
            await self._clear_current_thread()
            return

        if user_input.lower() in {"/help", "/?"}:
            self._add_system_message(self._help_text())
            return

        if user_input.lower().startswith("/model"):
            await self._handle_model_command(user_input)
            return

        if user_input.lower() == "/threads":
            threads = await self.client.list_threads(self.session_id)
            listing = ", ".join(threads) if threads else "(none)"
            self._add_system_message(f"Threads: {listing}")
            return

        if user_input.lower().startswith("/thread"):
            await self._handle_thread_command(user_input)
            return

        self._add_user_message(user_input)
        self._worker = self.run_worker(self._run_agent(user_input), exclusive=True)

    @on(Input.Changed, "#input")
    async def handle_input_changed(self, event: Input.Changed) -> None:
        value = event.value.strip()
        if value.startswith("/model") and self._model_cache is None and not self._model_loading:
            self.run_worker(self._prefetch_models(), exclusive=False)

    async def _handle_thread_command(self, user_input: str) -> None:
        parts = user_input.split()

        if len(parts) == 1:
            self._add_system_message(f"Current thread: {self.thread_id}")
            return

        subcommand = parts[1].lower()

        if subcommand in {"new", "create"}:
            new_id = parts[2].strip() if len(parts) > 2 else generate_thread_id()
            if await self._thread_exists(new_id):
                self._add_system_message(f"Thread '{new_id}' already exists.")
                return
            await self.client.create_thread(self.session_id, new_id)
            await self._switch_thread(new_id, created=True)
            return

        if subcommand in {"delete", "del", "rm"}:
            if len(parts) < 3:
                self._add_system_message("Usage: /thread delete <id>")
                return
            await self._delete_thread(parts[2].strip())
            return

        target = parts[1].strip()
        if target == self.thread_id:
            self._add_system_message(f"Already on thread '{self.thread_id}'.")
            return
        await self._switch_thread(target, created=not await self._thread_exists(target))

    async def _handle_model_command(self, user_input: str) -> None:
        parts = user_input.split()
        if len(parts) == 1 or parts[1].lower() in {"current", "show"}:
            await self._refresh_model()
            current = self.model_name or "(unknown)"
            self._add_system_message(f"Current model: {current}")
            return

        subcommand = parts[1].lower()

        if subcommand == "list":
            query = " ".join(parts[2:]).strip()
            models = await self._load_models()
            if query:
                matches = [m for m in models if query.lower() in m.lower()]
            else:
                matches = models

            if not matches:
                self._add_system_message(f"No models found for '{query}'.")
                return

            limit = 30
            shown = matches[:limit]
            header = f"Models ({len(matches)} match{'es' if len(matches) != 1 else ''}):"
            lines = [header, *[f"- {model}" for model in shown]]
            if len(matches) > limit:
                lines.append(f"... showing first {limit}. Use /model list <filter> to narrow.")
            self._add_system_message("\n".join(lines))
            return

        if subcommand in {"default", "reset"}:
            await self._set_session_model(None)
            return

        if subcommand == "set":
            if len(parts) < 3:
                self._add_system_message("Usage: /model set <model-name>")
                return
            model_name = " ".join(parts[2:]).strip()
            await self._set_session_model(model_name)
            return

        # Assume /model <name>
        model_name = " ".join(parts[1:]).strip()
        if not model_name:
            self._add_system_message("Usage: /model <model-name>")
            return
        await self._set_session_model(model_name)

    async def _load_models(self) -> list[str]:
        if self._model_cache is not None:
            return self._model_cache
        if self._model_loading:
            return self._model_cache or []
        self._model_loading = True
        try:
            payload = await self.client.list_models()
        except Exception as exc:
            self._add_system_message(f"Failed to load models: {exc}")
            self._model_loading = False
            return []
        self._model_cache = payload.models
        self._default_model = payload.default_model
        self._model_loading = False
        return self._model_cache

    async def _prefetch_models(self) -> None:
        await self._load_models()

    def _get_model_suggestions(self) -> list[str]:
        return self._model_cache or []

    async def _refresh_model(self) -> None:
        try:
            payload = await self.client.get_session_model(self.session_id)
        except Exception as exc:
            self._add_system_message(f"Failed to load model: {exc}")
            return
        self.model_name = payload.model
        self._default_model = payload.default_model
        self._update_header()

    async def _set_session_model(self, model_name: str | None) -> None:
        try:
            payload = await self.client.set_session_model(self.session_id, model_name)
        except Exception as exc:
            self._add_system_message(f"Failed to set model: {exc}")
            return
        self.model_name = payload.model
        self._default_model = payload.default_model
        self._update_header()
        if payload.is_default:
            self._add_system_message(f"Model reset to default: {payload.model}")
        else:
            self._add_system_message(f"Model set to: {payload.model}")

    def _help_text(self) -> str:
        lines = [
            "Commands:",
            "/help                     Show this help message",
            "/threads                  List threads",
            "/thread <id>              Switch to a thread",
            "/thread new [id]          Create a new thread",
            "/thread delete <id>       Delete a thread",
            "/clear                    Clear current thread history",
            "/model                    Show current model",
            "/model list [filter]      List or search models",
            "/model set <name>         Set session model",
            "/model default            Reset to default model",
            "/quit or /exit            Exit the app",
        ]
        return "\n".join(lines)

    async def _clear_current_thread(self) -> None:
        self.action_clear_chat()
        try:
            await self.client.clear_thread(self.session_id, self.thread_id)
        except Exception as exc:  # pragma: no cover - UI fallback
            self._add_system_message(f"Failed to clear thread: {exc}")

    # -------------------------------------------------------------------------
    # Agent Streaming
    # -------------------------------------------------------------------------

    async def _run_agent(self, user_input: str) -> None:
        self._set_status("streaming", streaming=True)
        self._current_assistant = None
        self._current_thinking = None
        self._tool_calls = {}
        self._message_map = {}

        run_input = self._build_run_input(user_input)

        try:
            async for event in self.client.run_stream(run_input):
                self._handle_ag_ui_event(event)
        except Exception as exc:
            self._add_system_message(f"Run error: {exc}")
        finally:
            self._set_status("")
            self._scroll_to_bottom()

    def _build_run_input(self, user_input: str) -> RunAgentInput:
        return RunAgentInput(
            thread_id=self.thread_id,
            run_id=uuid4().hex,
            parent_run_id=None,
            state={},
            messages=[UserMessage(id=uuid4().hex, content=user_input)],
            tools=[],
            context=[],
            forwarded_props={},
        )

    def _handle_ag_ui_event(self, event: BaseEvent) -> None:
        if isinstance(event, TextMessageStartEvent):
            self._handle_text_message_start(event)
            return
        if isinstance(event, TextMessageContentEvent):
            self._handle_text_message_content(event)
            return
        if isinstance(event, TextMessageEndEvent):
            return
        if isinstance(event, ThinkingStartEvent):
            self._ensure_thinking()
            return
        if isinstance(event, ThinkingTextMessageStartEvent):
            self._ensure_thinking()
            return
        if isinstance(event, ThinkingTextMessageContentEvent):
            self._ensure_thinking()
            if self._current_thinking:
                self._current_thinking.append_content(event.delta)
            return
        if isinstance(event, ThinkingTextMessageEndEvent):
            return
        if isinstance(event, ThinkingEndEvent):
            return
        if isinstance(event, ToolCallStartEvent):
            self._add_tool_call(event.tool_call_name, "", event.tool_call_id)
            return
        if isinstance(event, ToolCallArgsEvent):
            self._append_tool_args(event.tool_call_id, event.delta)
            return
        if isinstance(event, ToolCallEndEvent):
            return
        if isinstance(event, ToolCallResultEvent):
            self._set_tool_result_content(event.tool_call_id, event.content)
            return
        if isinstance(event, RunErrorEvent):
            self._add_system_message(f"Run error: {event.message}")
            return

    def _handle_text_message_start(self, event: TextMessageStartEvent) -> None:
        role = event.role or "assistant"
        if role == "assistant":
            msg = ChatMessage(role="assistant")
            self._current_assistant = msg
        elif role in {"system", "developer"}:
            msg = ChatMessage(role="system")
        elif role == "user":
            msg = ChatMessage(role="user")
        else:
            msg = ChatMessage(role=role)
        chat = self.query_one("#chat-scroll", VerticalScroll)
        chat.mount(msg)
        self._message_map[event.message_id] = msg
        self._scroll_to_bottom()

    def _handle_text_message_content(self, event: TextMessageContentEvent) -> None:
        msg = self._message_map.get(event.message_id)
        if msg is None:
            msg = ChatMessage(role="assistant")
            chat = self.query_one("#chat-scroll", VerticalScroll)
            chat.mount(msg)
            self._message_map[event.message_id] = msg
            self._current_assistant = msg
            self._scroll_to_bottom()
        msg.append_content(event.delta)

    def _ensure_thinking(self) -> None:
        if self._current_thinking is None:
            self._current_thinking = ChatMessage(role="thinking")
            chat = self.query_one("#chat-scroll", VerticalScroll)
            chat.mount(self._current_thinking)
            self._scroll_to_bottom()

    def _ensure_assistant(self) -> None:
        if self._current_assistant is None:
            self._current_assistant = ChatMessage(role="assistant")
            chat = self.query_one("#chat-scroll", VerticalScroll)
            chat.mount(self._current_assistant)
            self._scroll_to_bottom()

    # -------------------------------------------------------------------------
    # Message Helpers
    # -------------------------------------------------------------------------

    def _add_user_message(self, content: str) -> None:
        chat = self.query_one("#chat-scroll", VerticalScroll)
        chat.mount(ChatMessage(role="user", content=content))
        self._scroll_to_bottom()

    def _add_assistant_message(self, content: str) -> None:
        chat = self.query_one("#chat-scroll", VerticalScroll)
        msg = ChatMessage(role="assistant", content=content)
        chat.mount(msg)
        self._current_assistant = msg
        self._scroll_to_bottom()

    def _add_system_message(self, content: str) -> None:
        chat = self.query_one("#chat-scroll", VerticalScroll)
        chat.mount(ChatMessage(role="system", content=content))
        self._scroll_to_bottom()

    def _add_tool_call(self, tool_name: str, args: Any, tool_call_id: str) -> None:
        tool_widget = self._tool_calls.get(tool_call_id)
        if tool_widget is None:
            tool_widget = ToolCall(tool_name, args, tool_call_id)
            self._tool_calls[tool_call_id] = tool_widget
            chat = self.query_one("#chat-scroll", VerticalScroll)
            chat.mount(tool_widget)
            self._scroll_to_bottom()
            return

        tool_widget.update_tool_name(tool_name)
        if args:
            payload = args if isinstance(args, str) else json.dumps(args)
            tool_widget.append_args(payload)

    def _append_tool_args(self, tool_call_id: str, delta: str) -> None:
        tool_widget = self._tool_calls.get(tool_call_id)
        if tool_widget is None:
            tool_widget = ToolCall("tool", "", tool_call_id)
            self._tool_calls[tool_call_id] = tool_widget
            chat = self.query_one("#chat-scroll", VerticalScroll)
            chat.mount(tool_widget)
        tool_widget.append_args(delta)

    def _set_tool_result_content(self, tool_call_id: str, content: str) -> None:
        data: Any = content
        if isinstance(content, str):
            stripped = content.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    data = content
        self._set_tool_result(tool_call_id, data)

    def _set_tool_result(self, tool_call_id: str, result: Any) -> None:
        if tool_call_id not in self._tool_calls:
            return

        tool_widget = self._tool_calls[tool_call_id]

        data = result
        if hasattr(data, "content"):
            data = data.content
        if hasattr(data, "data"):
            data = data.data

        output = ""
        exit_code = 0
        timed_out = False
        stdout = ""
        stderr = ""

        if hasattr(data, "stdout"):
            stdout = data.stdout or ""
            stderr = data.stderr or ""
            exit_code = data.exit_code
            timed_out = bool(getattr(data, "timed_out", False))
        elif isinstance(data, dict):
            stdout = data.get("stdout", "") or ""
            stderr = data.get("stderr", "") or ""
            exit_code = data.get("exit_code", 0)
            timed_out = bool(data.get("timed_out", False))
        else:
            output = str(data)

        if stdout or stderr:
            if stdout and stderr:
                output = f"{stdout}\\n{stderr}"
            else:
                output = stdout or stderr

        output = self._truncate_output(output)
        tool_widget.set_result(output, exit_code, timed_out=timed_out)

    def _truncate_output(self, output: str, limit: int = 4000) -> str:
        if len(output) <= limit:
            return output
        return output[:limit] + f"\\n... (truncated, {len(output) - limit} chars)"

    def _scroll_to_bottom(self) -> None:
        chat = self.query_one("#chat-scroll", VerticalScroll)
        chat.scroll_end(animate=False)

    def _set_status(self, text: str, streaming: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(streaming, "streaming")

    # -------------------------------------------------------------------------
    # Thread Management
    # -------------------------------------------------------------------------

    async def _thread_exists(self, thread_id: str) -> bool:
        return thread_id in await self.client.list_threads(self.session_id)

    async def _switch_thread(self, new_thread_id: str, *, created: bool = False) -> None:
        self.action_clear_chat()
        await self._load_thread_state(new_thread_id)

        if created:
            self._add_system_message(f"Created thread '{self.thread_id}'.")
        else:
            self._add_system_message(f"Switched to thread '{self.thread_id}'.")

    async def _load_thread_state(self, thread_id: str) -> None:
        self.thread_id = thread_id
        self._update_header()
        try:
            async for event in self.client.iter_thread_events(self.session_id, thread_id):
                self._handle_ag_ui_event(event)
        except Exception as exc:
            self._add_system_message(f"Failed to load history: {exc}")
            return
        self._scroll_to_bottom()

    async def _delete_thread(self, thread_id: str) -> None:
        threads = await self.client.list_threads(self.session_id)

        if thread_id not in threads:
            self._add_system_message(f"Thread '{thread_id}' not found.")
            return

        if thread_id != self.thread_id:
            await self.client.delete_thread(self.session_id, thread_id)
            self._add_system_message(f"Deleted thread '{thread_id}'.")
            return

        await self.client.delete_thread(self.session_id, thread_id)
        remaining = [t for t in threads if t != thread_id]

        if remaining:
            self.action_clear_chat()
            await self._load_thread_state(remaining[0])
            self._add_system_message(
                f"Deleted '{thread_id}'. Switched to '{remaining[0]}'."
            )
        else:
            self.action_clear_chat()
            await self.client.create_thread(self.session_id, "default")
            await self._load_thread_state("default")
            self._add_system_message(f"Deleted '{thread_id}'. Created 'default'.")

    def _update_header(self) -> None:
        if not self._mounted:
            return
        header_right = self.query_one("#header-right", Static)
        if self.model_name:
            header_right.update(f"{self.thread_id} | {self.model_name}")
        else:
            header_right.update(self.thread_id)


def run_tui(
    *,
    server_url: str,
    server_process: subprocess.Popen | None = None,
) -> None:
    BinsmithApp(server_url=server_url, server_process=server_process).run()
