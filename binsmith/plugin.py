from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from binsmith.env import AGENT_MODEL, first_env, read_bool_env
from binsmith.linker import link_workspace_bins
from binsmith.tools import discover_tools, format_tools_section
from binsmith.workspace import ensure_workspace
from lattis.plugins import AgentPlugin, AgentRunContext, list_known_models

BINSMITH_MODEL = "BINSMITH_MODEL"
BINSMITH_LOGFIRE = "BINSMITH_LOGFIRE"


class BashExecutionResult(BaseModel):
    """Result of a bash command execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class BashExecutor:
    """Execute bash commands via subprocess."""

    def execute(
        self,
        command: str,
        cwd: Path | None = None,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> BashExecutionResult:
        start = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)

            return BashExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            stdout = exc.stdout
            stderr = exc.stderr
            if isinstance(stdout, bytes):
                stdout = stdout.decode()
            if isinstance(stderr, bytes):
                stderr = stderr.decode()
            return BashExecutionResult(
                exit_code=-1,
                stdout=stdout or "",
                stderr=stderr or "",
                duration_ms=duration_ms,
                timed_out=True,
            )

        except Exception as exc:  # pragma: no cover - defensive
            duration_ms = int((time.perf_counter() - start) * 1000)
            return BashExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=duration_ms,
            )


SYSTEM_PROMPT = """\
You are Binsmith, a toolkit-focused AI agent that builds and refines a personal toolbox over time.

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


def _configure_telemetry() -> None:
    enabled = read_bool_env(BINSMITH_LOGFIRE)
    if not enabled:
        return
    logfire.configure(send_to_logfire=True, console=False)
    logfire.instrument_pydantic_ai()


DEFAULT_MODEL = first_env(BINSMITH_MODEL, AGENT_MODEL) or "google-gla:gemini-3-flash-preview"


def _build_agent(model_name: str) -> Agent[AgentDeps, str]:
    agent = Agent(
        model_name,
        deps_type=AgentDeps,
    )

    @agent.instructions
    def dynamic_instructions(ctx: RunContext[AgentDeps]) -> str:
        tools = discover_tools(ctx.deps.workspace)
        tools_section = format_tools_section(tools)
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


def create_deps(
    *,
    session_id: str,
    thread_id: str,
    workspace: Path,
    project_root: Path,
) -> AgentDeps:
    ensure_workspace(workspace)

    return AgentDeps(
        session_id=session_id,
        thread_id=thread_id,
        workspace=workspace,
        project_root=project_root,
    )


def _create_agent(model: str) -> Agent:
    return get_agent(model)


def _create_deps(ctx: AgentRunContext) -> AgentDeps:
    return create_deps(
        session_id=ctx.session_id,
        thread_id=ctx.thread_id,
        workspace=ctx.workspace,
        project_root=ctx.project_root,
    )


def _on_complete(ctx: AgentRunContext, result: Any) -> None:
    link_workspace_bins(ctx.workspace)


plugin = AgentPlugin(
    id="binsmith",
    name="Binsmith",
    create_agent=_create_agent,
    create_deps=_create_deps,
    on_complete=_on_complete,
    default_model=DEFAULT_MODEL,
    list_models=lambda: list_known_models(default_model=DEFAULT_MODEL),
)
