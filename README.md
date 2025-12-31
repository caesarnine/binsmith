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

Binsmith uses a server/client architecture. The TUI and web UI are interchangeable
clients — they talk to the same server, share the same threads, and see the
same toolkit.

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

This starts the TUI, which auto-starts a local server.

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
--server <url>           Binsmith server base URL (default: http://localhost:8000)
--no-autostart           Do not auto-start a local server if missing
--server-workspace       Workspace mode for auto-started server: local | central
```

### `binsmith server`

```
--host <host>            Host interface to bind (default: 127.0.0.1)
--port <port>            Port to bind (default: 8000)
--reload                 Enable auto-reload
--local-workspace        Use a project-local .binsmith workspace on the server
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

```bash
cd frontend
npm install
npm run dev
```

Connects to `http://localhost:8000` by default. Override with
`VITE_BINSMITH_SERVER_URL` in `frontend/.env.local`.

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
| `BINSMITH_SERVER_URL` | `http://localhost:8000` | Server URL for clients |
| `BINSMITH_LOGFIRE` | `0` | Enable Logfire telemetry |

## Running the server directly

```bash
binsmith server
# or
uvicorn binsmith.server.asgi:app --reload --port 8000
```

The TUI auto-starts a server if needed, so this is mainly for development
or running a shared server.
