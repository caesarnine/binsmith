<p align="center" style="bold">Binsmith</p>
<p align="center">
An agent that accumulates small CLI tools in a persistent workspace.
<img width="90%" height="90%" alt="Binsmith" src="https://github.com/user-attachments/assets/6d42d9d4-652c-45a5-b880-35bc0a62152a" />
</p>

Most chat-style agents are “stateless” in the sense that they don’t leave behind reusable artifacts. Binsmith is configured to turn repeated work into scripts and keep them under `.lattis/workspace/bin`, so later tasks can compose existing tools instead of re-solving the same problem.

Binsmith is distributed as a [Lattis](https://github.com/caesarnine/lattis) plugin.

## Quick start

```bash
export GOOGLE_API_KEY=... # see below for other providers
uvx binsmith
```

This starts a local server and opens the TUI. A web UI is also available at http://localhost:8000 while running.

To run the server only (no TUI):

```bash
uvx binsmith server
# Open http://localhost:8000 for the web UI
```

Or run via Lattis alongside other agents:

```bash
uv pip install binsmith
uvx lattis --agent binsmith
```

## What it does

Binsmith is an agent prompt + a workspace.

- It runs commands using a single tool: **`bash`**
- Your project workspace has `workspace/bin` on the PATH
- When a task is worth repeating, it writes a script into `workspace/bin`
- Those scripts persist across sessions and can call each other (Unix-style)
- It can symlink tools into a user-writable bin directory on your PATH (see Configuration)

Over time you end up with a small toolkit of scripts you and the agent can both use.

Example (tools invented over time; names illustrative):

```bash
fetch-url https://news.ycombinator.com | html2md | summarize --bullets
brief
todo add "Review PR #42"
```

## Workspace layout

```text
.lattis/
  workspace/
    bin/      # Scripts Binsmith creates (persists across sessions)
    data/     # Persistent data files
    tmp/      # Scratch space
```

## Script format

Scripts are intended to be standalone and “git-friendly”. Python scripts use `uv` inline metadata so dependencies are declared in the file:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Fetch a URL and extract text content."""
```

## Tool conventions

Binsmith is prompted to keep tools composable and discoverable:

- Prefer stdin/stdout for data flow
- Produce clean text output by default
- Support `--json` when machine-readable output makes sense
- Support `--help` and optionally `--describe`
- Exit `0` on success, non-zero on failure
- Reuse or extend existing tools instead of creating near-duplicates

The point is to make workflows like `fetch-url | html2md | summarize` viable.

## How it works (mechanics)

Binsmith is “just” an agent configuration:

- It can run shell commands inside the project directory
- It can see what’s already in `.lattis/workspace/bin`
- It is instructed to:
  1. use existing scripts when possible
  2. write scripts when you hit repetition
  3. improve existing scripts rather than cloning variants

Lattis handles the server, UIs, thread persistence, and session state.

## Remote usage

A common setup is to run the server on a machine that stays up and connect from anywhere:

```bash
# On the server
uvx binsmith server --host 0.0.0.0

# From a client machine (TUI)
uvx binsmith --server http://your-server:8000

# Or open http://your-server:8000 in a browser for the web UI
```

(If you bind to a public interface, keep it on a private network / VPN.)

## Interfaces

Binsmith provides two interfaces, both connecting to the same server and sharing threads:

- **TUI** — Terminal interface, launched by default with `uvx binsmith`
- **Web UI** — Browser interface at http://localhost:8000

### TUI commands

```text
/help                     Show help
/threads                  List threads
/thread <id>              Switch to thread
/thread new [id]          Create new thread
/thread delete <id>       Delete thread
/clear                    Clear current thread
/model                    Show current model
/model list [filter]      List models
/model set <name>         Set model
/quit                     Exit
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BINSMITH_MODEL` | `google-gla:gemini-2.0-flash` | Default model |
| `BINSMITH_LOGFIRE` | `0` | Enable Logfire telemetry |
| `BINSMITH_LINK_BINS` | `1` | Link tools into a writable PATH directory |
| `BINSMITH_BIN_DIR` | | Override the link directory (should be on your PATH) |

Binsmith only links tools when it can find a writable PATH directory under your home folder, and it skips names
that already resolve on PATH to avoid shadowing existing commands. Set `BINSMITH_BIN_DIR` to control the link
location when you want a specific directory.

When auto-picking a link directory, Binsmith prefers `~/.local/bin` (then `~/bin`) if present on your `PATH`, and
it avoids linking into the Binsmith workspace `bin/` directory or an active virtualenv’s `bin/`.

Lattis configuration (`LATTIS_*`) controls storage and server settings.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An API key for at least one model provider

```bash
export GOOGLE_API_KEY=...     # Google
export ANTHROPIC_API_KEY=...  # Anthropic
export OPENAI_API_KEY=...     # OpenAI
```

## Why the name

It forges tools into `bin/`.
