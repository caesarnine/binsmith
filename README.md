# Binsmith

An AI agent that works by running shell commands and writing scripts.
Tools it creates persist across sessions.

## The idea

Most AI agents are stateless. They solve problems, then forget everything.
Binsmith takes a different approach: when it does something useful, it writes
a script. That script goes into a persistent toolkit.

Ask Binsmith to fetch a webpage, and it writes `fetch-url`. Ask it to convert
HTML to markdown, and it writes `html2md`. A week later, when you ask for
a daily briefing, it composes them:

```
$ brief

# News
- AI lab announces new model...
- Tech company acquires startup...

# Weather
San Francisco: 62°F, partly cloudy

# Your todos
- [ ] Review PR #42
- [ ] Write README improvements
```

That `brief` command didn't exist until you needed it. Now it does, and it
builds on tools that already existed.

Binsmith uses a server/client architecture. The TUI runs with an in-process server
by default, or can connect to a standalone server. The web UI connects to a
standalone server.

## Requirements

- [uv](https://docs.astral.sh/uv/) — used both to run Binsmith and by the scripts it creates
- Python 3.14+ (uv will install this automatically)
- An API key for at least one LLM provider (Gemini, Anthropic, or OpenAI)

## Quick start

```bash
uvx binsmith
```

Or clone and run locally:

```bash
uv sync
binsmith
```

This starts the TUI, which runs a local in-process server by default.

Set `GEMINI_API_KEY` for the default model (Gemini Flash), or `ANTHROPIC_API_KEY`
/ `OPENAI_API_KEY` for alternatives. See [Models](#models).

## CLI

```bash
binsmith                 # Run the TUI (default)
binsmith tui             # Run the TUI explicitly
binsmith server          # Run the API server
```

### `binsmith tui`

```
--server <url>           Connect to a specific Binsmith server
--local                  Force local mode (skip server auto-discovery)
```

By default, the TUI checks if a server is running on `localhost:8000`. If the server
is for the same project, it connects automatically. Otherwise, it runs in local
(in-process) mode. Use `--local` to skip auto-discovery, or `--server` to connect
to a specific server (local or remote).

### `binsmith server`

```
--host <host>            Host interface to bind (default: 127.0.0.1)
--port <port>            Port to bind (default: 8000)
--reload                 Enable auto-reload
--workspace              Workspace mode: local | central
```

## What the agent builds

After a few days of use, a toolkit might look like:

```
~/.binsmith/workspace/bin/
  fetch-url     # Fetch a URL, handle retries, extract text
  html2md       # Convert HTML to clean markdown
  news          # Top stories from news sources
  weather       # Weather for a location
  todo          # Manage a simple todo list
  brief         # Daily briefing (composes news, weather, todo)
  code-map      # Map out a codebase structure
  code-ref      # Find references to a symbol
```

Each tool is a standalone, self-contained script that works for both you and
Binsmith. Python scripts use [inline script metadata](https://docs.astral.sh/uv/guides/scripts/)
so dependencies are declared in the file itself — just run the script and `uv`
handles the rest. No virtualenv, no pip install.

Run `todo add "buy milk"` yourself, or let Binsmith do it — same interface, same tool.

Tools are symlinked to `~/.local/bin` (or `$BINSMITH_GLOBAL_BIN`) so they're
available everywhere, not just inside Binsmith. They pipe into each other
and compose naturally.

## How it works

Binsmith has one tool: `bash`. It runs commands in your project directory with
the workspace `bin/` on the PATH. The workspace persists:

```
.binsmith/
  workspace/
    bin/      # Scripts the agent creates
    data/     # Persistent data
    tmp/      # Scratch space
  binsmith.db # Conversation history
```

On each run, the agent sees its current toolkit and is prompted to use
existing tools before writing one-off commands.

### Architecture

```
┌──────────────────────────────────────────┐
│              Clients                     │
│        TUI  /  Web UI  /  (API)          │
└─────────────────┬────────────────────────┘
                  │ HTTP + AG-UI streaming
                  ▼
┌──────────────────────────────────────────┐
│          Binsmith Server                 │
│   FastAPI · SQLite · Session management  │
└─────────────────┬────────────────────────┘
                  │ pydantic-ai
                  ▼
┌──────────────────────────────────────────┐
│               Agent                      │
│   Dynamic prompt · bash tool · Toolkit   │
└─────────────────┬────────────────────────┘
                  │ subprocess
                  ▼
┌──────────────────────────────────────────┐
│            File System                   │
│   Scripts as files · Git-friendly        │
└──────────────────────────────────────────┘
```

The TUI and web UI are interchangeable clients. Both talk to the same server,
share the same history, and see the same toolkit.

## Models

Default: `google-gla:gemini-3-flash-preview`

```bash
export GEMINI_API_KEY=...     # Google
export ANTHROPIC_API_KEY=...  # Anthropic
export OPENAI_API_KEY=...     # OpenAI
```

Switch models in the TUI with `/model set <name>` or via the web UI sidebar.
Run `/model list` to see available models.

## Web UI

The web UI is bundled with the server. Just run:

```bash
binsmith server
```

Then open `http://localhost:8000` in your browser. The web UI and TUI share
the same backend — threads, history, and tools are synchronized.

## TUI commands

```
/help                     Show help
/threads                  List threads
/thread <id>              Switch to a thread
/thread new [id]          Create a new thread
/thread delete <id>       Delete a thread
/clear                    Clear current thread
/model                    Show current model
/model list [filter]      List models
/model set <name>         Set model
/model default            Reset to default
/quit                     Exit
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BINSMITH_MODEL` | `google-gla:gemini-3-flash-preview` | Default model |
| `BINSMITH_WORKSPACE_MODE` | `local` | `local` (per-project) or `central` (~/.binsmith) |
| `BINSMITH_SERVER_URL` | *(unset)* | Server URL for clients that connect over HTTP |
| `BINSMITH_LOGFIRE` | `0` | Enable Logfire telemetry |

## Running the server

```bash
binsmith server
```

This starts the API server with the web UI at `http://localhost:8000`. Run the
server when you want:

- The web UI
- Multiple TUI clients sharing the same backend
- Remote access (use `--host 0.0.0.0`)
