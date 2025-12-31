from __future__ import annotations

import json
import re
from typing import Any, Optional

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Markdown, Static


class ToolCall(Widget):
    """A collapsible tool call widget showing command and output."""

    _COMMAND_REGEX = re.compile(r"""["']command["']\s*:\s*["']([^"']+)["']""")
    _PARTIAL_COMMAND_REGEX = re.compile(r"""["']command["']\s*:\s*["']([^"']*)""")
    _COMMAND_KEYS = ("command", "cmd")

    DEFAULT_CSS = """
    ToolCall {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        border-left: heavy #3fb950;
    }

    ToolCall .tool-header {
        height: 1;
        padding: 0 1;
        background: #1a2b21;
        color: #7d8590;
    }

    ToolCall .tool-header:hover {
        background: #213528;
    }

    ToolCall .tool-body {
        display: none;
        padding: 1;
        margin: 0;
        background: #121d16;
    }

    ToolCall.expanded .tool-body {
        display: block;
    }

    ToolCall .tool-output {
        color: #e6edf3;
        background: #111a14;
        border: solid #30363d;
        padding: 1;
    }

    ToolCall .exit-code {
        color: #3fb950;
        text-align: right;
    }

    ToolCall .exit-code.error {
        color: #f85149;
    }
    """

    expanded = reactive(False, init=False)

    def __init__(
        self,
        tool_name: str,
        args: Any,
        tool_call_id: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.args_raw = (
            args
            if isinstance(args, str)
            else json.dumps(args) if isinstance(args, dict) else str(args)
        )
        self.args_preview = self._format_args_preview(self.args_raw)
        self.tool_call_id = tool_call_id
        self.result_output: str = ""
        self.exit_code: Optional[int] = None
        self._composed = False
        self._command_regex = self._COMMAND_REGEX

    def _is_bash(self) -> bool:
        return self.tool_name == "bash" or self.tool_name.endswith(":bash")

    def _maybe_parse_json(self, value: str) -> Any | None:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def _find_command_in_data(self, data: Any) -> str | None:
        if isinstance(data, dict):
            for key in self._COMMAND_KEYS:
                if key in data and data[key] is not None:
                    return str(data[key])
            for key in ("input", "args", "arguments", "payload"):
                if key in data:
                    nested = data[key]
                    if isinstance(nested, str):
                        parsed = self._maybe_parse_json(nested)
                        if parsed is not None:
                            nested = parsed
                    command = self._find_command_in_data(nested)
                    if command:
                        return command
            for value in data.values():
                command = self._find_command_in_data(value)
                if command:
                    return command
        if isinstance(data, list):
            for item in data:
                command = self._find_command_in_data(item)
                if command:
                    return command
        return None

    def _format_args_preview(self, args: Any) -> str:
        is_bash = self._is_bash()
        if is_bash:
            command = self._extract_command(args)
            if command:
                preview = command.replace("\n", " ")[:60]
                return f"$ {preview}"
            if isinstance(args, str):
                stripped = args.strip()
                if stripped and not stripped.startswith(("{", "[")):
                    preview = args.replace("\n", " ")[:60]
                    return f"$ {preview}"
        if isinstance(args, str):
            parsed = self._maybe_parse_json(args)
            if isinstance(parsed, dict):
                return json.dumps(parsed)[:60]
            return args[:60]
        if isinstance(args, dict):
            return json.dumps(args)[:60]
        return str(args)[:60]

    def _extract_command(self, raw_args: Any) -> str | None:
        # Handle actual dict
        if isinstance(raw_args, dict):
            return self._find_command_in_data(raw_args)

        if isinstance(raw_args, list):
            return self._find_command_in_data(raw_args)

        if isinstance(raw_args, str):
            parsed = self._maybe_parse_json(raw_args)
            if parsed is not None:
                command = self._find_command_in_data(parsed)
                if command:
                    return command
                if isinstance(parsed, str):
                    reparsed = self._maybe_parse_json(parsed)
                    if reparsed is not None:
                        command = self._find_command_in_data(reparsed)
                        if command:
                            return command
        pattern = getattr(self, "_command_regex", self._COMMAND_REGEX)
        match = pattern.search(str(raw_args))
        if match:
            return match.group(1)
        partial_match = self._PARTIAL_COMMAND_REGEX.search(str(raw_args))
        if partial_match:
            return partial_match.group(1)
        return None

    def _looks_like_complete_json(self, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if not (
            (stripped.startswith("{") and stripped.endswith("}"))
            or (stripped.startswith("[") and stripped.endswith("]"))
        ):
            return False
        try:
            json.loads(stripped)
            return True
        except json.JSONDecodeError:
            return False

    def compose(self) -> ComposeResult:
        arrow = "▼" if self.expanded else "▶"
        header = self._format_header(arrow)
        yield Static(
            header,
            classes="tool-header",
            markup=False,
        )
        yield Static("", classes="tool-body tool-output", markup=False)
        yield Static("", classes="tool-body exit-code", markup=False)

    def on_mount(self) -> None:
        self._composed = True
        arrow = "▼" if self.expanded else "▶"
        header = self.query_one(".tool-header", Static)
        header.update(self._format_header(arrow))

    def watch_expanded(self, expanded: bool) -> None:
        self.set_class(expanded, "expanded")
        if not self._composed:
            return
        arrow = "▼" if expanded else "▶"
        header = self.query_one(".tool-header", Static)
        header.update(self._format_header(arrow))

    def on_click(self) -> None:
        self.expanded = not self.expanded

    def set_result(self, output: str, exit_code: int, timed_out: bool = False) -> None:
        self.result_output = output
        self.exit_code = exit_code

        output_widget = self.query_one(".tool-output", Static)
        output_widget.update(output if output else "(no output)")

        exit_widget = self.query_one(".exit-code", Static)
        suffix = " (timed out)" if timed_out else ""
        exit_widget.update(f"exit {exit_code}{suffix}")
        exit_widget.set_class(exit_code != 0, "error")

    def append_args(self, delta: str) -> None:
        if not delta:
            return
        if self._looks_like_complete_json(delta):
            self.args_raw = delta
        else:
            self.args_raw += delta
        self.args_preview = self._format_args_preview(self.args_raw)
        if not self._composed:
            return
        arrow = "▼" if self.expanded else "▶"
        header = self.query_one(".tool-header", Static)
        header.update(self._format_header(arrow))

    def _format_header(self, arrow: str) -> str:
        if self.args_preview.startswith("$"):
            return f"{arrow} {self.args_preview}"
        if self.args_preview:
            return f"{arrow} {self.tool_name}: {self.args_preview}"
        return f"{arrow} {self.tool_name}"

    def update_tool_name(self, tool_name: str) -> None:
        if tool_name == self.tool_name:
            return
        self.tool_name = tool_name
        self.args_preview = self._format_args_preview(self.args_raw)
        if not self._composed:
            return
        arrow = "▼" if self.expanded else "▶"
        header = self.query_one(".tool-header", Static)
        header.update(self._format_header(arrow))


class ChatMessage(Widget):
    """A single chat message with role-specific styling."""

    DEFAULT_CSS = """
    ChatMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        border-left: heavy #30363d;
    }

    ChatMessage.role-user {
        border-left: heavy #f0883e;
        background: #1b140c;
    }

    ChatMessage.role-assistant {
        border-left: heavy #a371f7;
        background: #171224;
    }

    ChatMessage.role-thinking {
        border-left: heavy #7d8590;
        background: #141922;
    }

    ChatMessage.role-system {
        border-left: heavy #7d8590;
        background: #141922;
    }

    ChatMessage.role-tool {
        border-left: heavy #3fb950;
        background: #121d16;
    }

    ChatMessage .msg-label {
        height: 1;
        text-style: bold;
        margin: 0;
    }

    ChatMessage .msg-label.user {
        color: #f0883e;
    }

    ChatMessage .msg-label.assistant {
        color: #a371f7;
    }

    ChatMessage .msg-label.thinking {
        color: #7d8590;
        text-style: italic;
    }

    ChatMessage .msg-label.system {
        color: #7d8590;
    }

    ChatMessage .msg-label.tool {
        color: #3fb950;
    }

    ChatMessage .msg-content {
        margin: 0;
        color: #e6edf3;
    }

    ChatMessage .msg-content.thinking {
        color: #7d8590;
        text-style: italic;
    }

    ChatMessage .msg-content.system {
        color: #7d8590;
    }

    """

    def __init__(
        self,
        role: str,
        content: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.add_class(f"role-{self.role}")

    def compose(self) -> ComposeResult:
        label_text, label_class = self._get_label()
        yield Static(label_text, classes=f"msg-label {label_class}")

        content_class = "thinking" if self.role == "thinking" else ""
        content_class = "system" if self.role == "system" else content_class

        if self.role == "assistant":
            yield Markdown(self.content, classes=f"msg-content {content_class}")
        else:
            yield Static(self.content, classes=f"msg-content {content_class}")

    def _get_label(self) -> tuple[str, str]:
        if self.role == "user":
            return "You", "user"
        if self.role == "assistant":
            return "Binsmith", "assistant"
        if self.role == "thinking":
            return "Binsmith (thinking)", "thinking"
        if self.role == "system":
            return "System", "system"
        if self.role == "tool":
            return "Tool", "tool"
        return self.role, ""

    def append_content(self, text: str) -> None:
        self.content += text
        content_widget = self.query_one(".msg-content")
        if isinstance(content_widget, Markdown):
            content_widget.update(self.content)
        else:
            content_widget.update(self.content)
