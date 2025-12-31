from __future__ import annotations

import os
import subprocess
import json
import tempfile
import stat
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from binsmith.execution.engine import BashExecutionResult, BashExecutor


SYSTEM_PROMPT = """\
You are Binsmith, a bash-native AI agent that builds and refines a personal toolkit over time.

## Your Environment

- **Project root (current working directory)**: `{project_root}`
- **Workspace**: `{workspace}` — files here persist across sessions
- **Your toolkit**: `{workspace}/bin/` — scripts you create live here and are always in your PATH
- **Scratch space**: `{workspace}/tmp/` — use this for temporary files (also set as $TMPDIR)
- **Full shell access**: Run any command, install packages, write files, make network requests

## Your Toolkit

{tools_section}

## How You Work

### 1. Toolkit-First Thinking

Before solving any problem, ask: **do I already have a tool for this?**

- Check the toolkit listing above
- If a tool exists, use it
- If a tool is *close*, improve it rather than working around it

### 2. Build Tools for Repeated Work

If you do something more than once, make it a tool:

```bash
# Bad: one-off command buried in history
curl -s "api.weather.com/v1?q=Seattle" | jq '.current.temp'

# Good: reusable tool
bin/weather Seattle
```

Tools are investments. A few minutes now saves time forever.

### 3. Unix Philosophy

Build small tools that compose:

```bash
# Each tool does one thing well
fetch-url https://example.com      # Fetches and extracts text
jq -r '.users[].email'             # Extracts JSON fields
dedupe                             # Removes duplicates

# Compose with pipes
fetch-url "$api/users" | jq -r '.users[].email' | dedupe | sort
```

**Tool design principles:**
- Read from stdin when it makes sense (enables piping)
- Output clean text to stdout (one item per line when applicable)
- Always support a `--json` flag for machine-readable output; keep the schema stable
- Use stderr for status/progress messages
- Exit 0 on success, non-zero on failure
- Support `--help` and `--describe` flags

### 4. Improve, Don't Duplicate

When a tool doesn't quite fit:

```bash
# Don't: create weather2.py with slight changes
# Do: add a flag to weather.py

weather Seattle              # Original behavior
weather --json Seattle       # New capability you added
```

Keep the toolkit lean. One good tool beats three overlapping ones.

## Creating Tools

When creating tools in `bin/`, follow this pattern so they're discoverable:

**Python (with inline dependencies):**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
# ]
# ///
\"\"\"One-line description shown in toolkit listing.\"\"\"
import argparse
import sys

import httpx  # External deps go after the script block

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    # Your arguments here

    args = parser.parse_args()

    if args.describe:
        print(__doc__.strip())
        return

    # Your logic here
    # If args.json: print JSON only to stdout (stable schema)
    # Use sys.stdin for piped input: data = sys.stdin.read()
    # Exit non-zero on failure: sys.exit(1)

if __name__ == "__main__":
    main()
```

**Bash:**
```bash
#!/bin/bash
# One-line description shown in toolkit listing

set -euo pipefail  # Fail fast on errors

[[ "${{1:-}}" == "--describe" ]] && {{ sed -n '2s/^# //p' "$0"; exit 0; }}
[[ "${{1:-}}" == "--help" ]] && {{ echo "Usage: $(basename "$0") [args]"; exit 0; }}
[[ "${{1:-}}" == "--json" ]] && json=1 && shift || json=0

# Your logic here
# If json=1: print JSON only to stdout (stable schema)
# Read from stdin if no args: [[ $# -eq 0 ]] && input=$(cat) || input="$1"
```

After creating: `chmod +x {workspace}/bin/your-tool`

## Python Dependencies

Python scripts are **self-contained** using inline script metadata. Dependencies are declared
in the `# /// script` block and `uv` handles installation automatically on first run.

**Common packages and their PyPI names:**
- `import httpx` → `"httpx"` (HTTP client)
- `import requests` → `"requests"` (HTTP client)
- `import bs4` → `"beautifulsoup4"` (HTML parsing)
- `import PIL` → `"pillow"` (image processing)
- `import yaml` → `"pyyaml"` (YAML parsing)
- `import dotenv` → `"python-dotenv"` (env files)
- `import dateutil` → `"python-dateutil"` (date parsing)
- `import rich` → `"rich"` (pretty terminal output)
- `import click` → `"click"` (CLI framework)
- `import typer` → `"typer"` (CLI framework)
- `import pydantic` → `"pydantic"` (data validation)

**Stdlib modules (no dependency needed):** `argparse`, `json`, `os`, `sys`, `pathlib`,
`subprocess`, `re`, `datetime`, `collections`, `itertools`, `functools`, `urllib`, `html`, `csv`, `sqlite3`, `tempfile`, `shutil`, `glob`, `hashlib`, `base64`, `uuid`, `logging`, `typing`

## System Dependencies

```bash
apt-get install -y jq     # JSON processor
apt-get install -y pandoc # Document conversion
```

## Workspace Structure

```
{workspace}/
  bin/      # Your toolkit (executable, self-documenting)
  data/     # Persistent data files
  tmp/      # Scratch space
```
"""


class BashInput(BaseModel):
    command: str = Field(description="The bash command to execute.")
    timeout: int = Field(default=30, description="Timeout in seconds.")


@dataclass
class AgentDeps:
    session_id: str
    thread_id: str
    workspace: Path
    project_root: Path
    executor: BashExecutor = field(default_factory=BashExecutor)


class _ToolCacheEntry(TypedDict, total=False):
    description: str
    mtime_ns: int
    size: int


_TOOL_CACHE_VERSION = 1
_GLOBAL_BIN_ENV = "BINSMITH_GLOBAL_BIN"


def _tool_cache_path(workspace: Path) -> Path:
    return workspace / "data" / "tool_cache.json"


def _load_tool_cache(path: Path) -> dict[str, _ToolCacheEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}
    if payload.get("version") != _TOOL_CACHE_VERSION:
        return {}

    tools = payload.get("tools")
    if not isinstance(tools, dict):
        return {}

    out: dict[str, _ToolCacheEntry] = {}
    for name, entry in tools.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        description = entry.get("description")
        mtime_ns = entry.get("mtime_ns")
        size = entry.get("size")
        if not isinstance(description, str):
            continue
        if not isinstance(mtime_ns, int) or not isinstance(size, int):
            continue
        out[name] = {"description": description, "mtime_ns": mtime_ns, "size": size}
    return out


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _save_tool_cache(path: Path, tools: dict[str, _ToolCacheEntry]) -> None:
    payload = {"version": _TOOL_CACHE_VERSION, "tools": tools}
    _atomic_write_json(path, payload)


def _resolve_global_bin() -> Path | None:
    override = os.getenv(_GLOBAL_BIN_ENV)
    if override:
        value = override.strip()
        if value.lower() in {"0", "false", "no", "off", "disable", "disabled"}:
            return None
        return Path(value).expanduser()
    xdg = os.getenv("XDG_BIN_HOME")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".local" / "bin"


def sync_global_tools(workspace: Path) -> None:
    global_bin = _resolve_global_bin()
    if global_bin is None:
        return

    bin_dir = workspace / "bin"
    if not bin_dir.exists():
        return

    try:
        global_bin.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    try:
        bin_dir_resolved = bin_dir.resolve()
    except OSError:
        bin_dir_resolved = bin_dir

    for tool_path in sorted(bin_dir.iterdir()):
        if not tool_path.is_file():
            continue
        if tool_path.suffix in {".md", ".txt", ".json", ".yaml", ".yml"}:
            continue
        try:
            mode = tool_path.stat().st_mode
        except OSError:
            continue
        if not (mode & stat.S_IXUSR):
            continue

        target = global_bin / tool_path.name
        try:
            if target.is_symlink():
                try:
                    if target.resolve() == tool_path.resolve():
                        continue
                except OSError:
                    pass
            if target.exists():
                if target.is_dir():
                    continue
                target.unlink()
            target.symlink_to(tool_path)
        except OSError:
            continue

    # Prune stale symlinks pointing into this workspace/bin
    try:
        for entry in global_bin.iterdir():
            if not entry.is_symlink():
                continue
            try:
                resolved = entry.resolve()
            except OSError:
                continue
            if not str(resolved).startswith(str(bin_dir_resolved) + os.sep):
                continue
            if not resolved.exists():
                try:
                    entry.unlink()
                except OSError:
                    continue
    except OSError:
        return


def _run_tool_describe(path: Path, *, workspace: Path, timeout: float) -> str | None:
    try:
        result = subprocess.run(
            [str(path), "--describe"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
        )
    except (subprocess.TimeoutExpired, PermissionError, OSError):
        return None

    if result.returncode != 0:
        return None

    output = result.stdout or ""
    output = output.rstrip("\n")
    return output if output.strip() else None


def _extract_tool_description_from_file(path: Path, *, max_bytes: int = 8192) -> str:
    try:
        with path.open("rb") as handle:
            blob = handle.read(max_bytes)
    except OSError:
        return ""
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return ""

    lines = text.splitlines()
    if not lines:
        return ""

    start = 1 if lines and lines[0].startswith("#!") else 0
    end = min(len(lines), start + 30)

    for i in range(start, end):
        line = lines[i].strip()
        if not line:
            continue

        if line.startswith('"""') or line.startswith("'''"):
            delim = line[:3]
            remainder = line[3:]
            if delim in remainder:
                candidate = remainder.split(delim, 1)[0].strip()
                if candidate:
                    return candidate
                continue

            collected: list[str] = []
            if remainder.strip():
                collected.append(remainder)
            for j in range(i + 1, min(len(lines), start + 200)):
                candidate_line = lines[j]
                if delim in candidate_line:
                    collected.append(candidate_line.split(delim, 1)[0])
                    break
                collected.append(candidate_line)
            for candidate in collected:
                candidate = candidate.strip()
                if candidate:
                    return candidate
            continue

        if line.startswith("# ") and not line.startswith("#!/"):
            return line[2:].strip()

    return ""


def discover_tools(workspace: Path, timeout: float = 2.0) -> list[tuple[str, str]]:
    """
    Discover tools in the workspace bin directory.

    Returns a list of (script_name, description) tuples.
    Tries --describe first, falls back to extracting a short description from the file.
    """
    bin_dir = workspace / "bin"
    if not bin_dir.exists():
        return []

    sync_global_tools(workspace)

    cache_path = _tool_cache_path(workspace)
    cached = _load_tool_cache(cache_path)
    updated_cache: dict[str, _ToolCacheEntry] = {}

    tools = []
    for path in sorted(bin_dir.iterdir()):
        if not path.is_file():
            continue

        # Skip non-executable files and common non-script files
        if path.suffix in {".md", ".txt", ".json", ".yaml", ".yml"}:
            continue

        name = path.name
        try:
            stat = path.stat()
        except OSError:
            continue

        description = ""
        cache_entry = cached.get(name)
        if (
            cache_entry
            and cache_entry.get("mtime_ns") == stat.st_mtime_ns
            and cache_entry.get("size") == stat.st_size
        ):
            description = cache_entry.get("description", "") or ""
        else:
            described = _run_tool_describe(path, workspace=workspace, timeout=timeout)
            if described is not None:
                description = described
            else:
                description = _extract_tool_description_from_file(path)

        updated_cache[name] = {
            "description": description,
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
        tools.append((name, description))

    if updated_cache != cached:
        _save_tool_cache(cache_path, updated_cache)

    return tools


def format_tools_section(tools: list[tuple[str, str]], workspace: Path) -> str:
    """Format the tools section for the system prompt."""
    if not tools:
        return (
            "No tools in `bin/` yet — this is a fresh toolkit.\n\n"
            "As you work, create reusable tools here. Each tool you build "
            "becomes available for future tasks."
        )

    tool_count = len(tools)
    lines = [f"**{tool_count} tool{'s' if tool_count != 1 else ''} available:**\n"]

    for name, description in tools:
        if description:
            formatted = description.strip()
            if "\n" in formatted:
                formatted = "\n  ".join(formatted.splitlines())
            lines.append(f"- `{name}` — {formatted}")
        else:
            lines.append(f"- `{name}` — *(no description, consider adding --describe support)*")

    lines.append("")
    lines.append("Run `<tool> --help` for usage. Remember: use existing tools before writing one-off commands.")

    return "\n".join(lines)


def _configure_telemetry() -> None:
    enabled = os.getenv("BINSMITH_LOGFIRE", "0").lower() in {"1", "true", "yes"}
    if not enabled:
        return
    logfire.configure(send_to_logfire=True, console=False)
    logfire.instrument_pydantic_ai()


DEFAULT_MODEL = os.getenv("BINSMITH_MODEL", "google-gla:gemini-3-flash-preview")


def _build_agent(model_name: str) -> Agent[AgentDeps, str]:
    agent = Agent(
        model_name,
        deps_type=AgentDeps,
    )

    @agent.instructions
    def dynamic_instructions(ctx: RunContext[AgentDeps]) -> str:
        tools = discover_tools(ctx.deps.workspace)
        tools_section = format_tools_section(tools, ctx.deps.workspace)
        return SYSTEM_PROMPT.format(
            project_root=ctx.deps.project_root,
            workspace=ctx.deps.workspace,
            tools_section=tools_section,
        )

    @agent.tool(docstring_format="google", require_parameter_descriptions=True)
    def bash(ctx: RunContext[AgentDeps], input: BashInput) -> BashExecutionResult:
        """
        Execute a bash command in the project root.

        Args:
            ctx: Runtime context.
            input: The command to run and optional timeout.

        Returns:
            Command output including stdout, stderr, and exit code.
        """
        # Add workspace/bin to PATH and setup scratch space
        env = os.environ.copy()
        bin_path = str(ctx.deps.workspace / "bin")
        tmp_path = str(ctx.deps.workspace / "tmp")
        env["PATH"] = f"{bin_path}:{env.get('PATH', '')}"
        env["TMPDIR"] = tmp_path
        env["TEMP"] = tmp_path
        env["TMP"] = tmp_path

        return ctx.deps.executor.execute(
            input.command,
            cwd=ctx.deps.project_root,
            timeout=input.timeout,
            env=env,
        )

    return agent


@lru_cache(maxsize=8)
def get_agent(model_name: str | None = None) -> Agent[AgentDeps, str]:
    resolved = model_name or DEFAULT_MODEL
    _configure_telemetry()
    return _build_agent(resolved)


def get_default_model() -> str:
    return DEFAULT_MODEL


def create_deps(
    *,
    session_id: str,
    thread_id: str,
    workspace: Path,
    project_root: Path,
) -> AgentDeps:
    # Ensure workspace structure exists
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "bin").mkdir(exist_ok=True)
    (workspace / "data").mkdir(exist_ok=True)
    (workspace / "tmp").mkdir(exist_ok=True)
    sync_global_tools(workspace)

    return AgentDeps(
        session_id=session_id,
        thread_id=thread_id,
        workspace=workspace,
        project_root=project_root,
    )
