# Binsmith

An AI agent that works by running shell commands and writing reusable, composable CLIs.
Tools it creates persist across sessions.

## The idea

Most AI agents are stateless. They solve problems, then forget everything.
Binsmith takes a different approach: when it does something useful, it writes
a script. That script goes into a persistent toolkit.

Ask Binsmith to fetch a webpage, and it writes `fetch-url`. Ask it to convert
HTML to markdown, and it writes `html2md`. A week later, when you ask for a
daily briefing, it composes them:

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

That `brief` command did not exist until you needed it. Now it does, and it
builds on tools that already existed.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.12+ (uv can install it automatically)
- An API key for at least one model provider (Gemini, Anthropic, or OpenAI)

## Quick start

```bash
uvx binsmith
```

This starts the TUI (via [Lattis](https://github.com/caesarnine/lattis)) with Binsmith as the default agent.

```bash
uv sync
uv run binsmith
```

## CLI

```bash
binsmith                 # Run the TUI (default)
binsmith tui             # Run the TUI explicitly
binsmith server          # Run the API server (and web UI, if built)
```

All Lattis flags are supported, including `--server`, `--local`, and
`--workspace`. See the Lattis README for the full CLI reference.

## What the agent builds

After a few days of use, a toolkit might look like:

```
.lattis/workspace/bin/
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
Binsmith. Python scripts use inline script metadata so dependencies are declared
in the file itself. Just run the script and `uv` handles the rest.

## How it works

Binsmith has one tool: `bash`. It runs commands in your project directory with
`workspace/bin` on the PATH. The workspace persists between runs.

```
.lattis/
  lattis.db
  session_id
  workspace/
    bin/      # Scripts the agent creates
    data/     # Persistent data
    tmp/      # Scratch space
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
│            Lattis Server                 │
│   FastAPI · SQLite · Session management  │
└─────────────────┬────────────────────────┘
                  │ pydantic-ai
                  ▼
┌──────────────────────────────────────────┐
│             Binsmith Agent               │
│   Dynamic prompt · bash tool · Toolkit   │
└─────────────────┬────────────────────────┘
                  │ subprocess
                  ▼
┌──────────────────────────────────────────┐
│            File System                   │
│   Scripts as files · Git-friendly        │
└──────────────────────────────────────────┘
```

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

The web UI is bundled with the [Lattis server](https://github.com/caesarnine/lattis). Just run:

```bash
binsmith server
```

Then open `http://localhost:8000` in your browser.

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
| `BINSMITH_LOGFIRE` | `0` | Enable Logfire telemetry |

[Lattis](https://github.com/caesarnine/lattis) configuration (storage, server URLs, workspace mode) is controlled via
`LATTIS_*` environment variables; see the Lattis README for details.
By default, Binsmith uses `.lattis/` in local mode and `~/.lattis/` in
central mode. Override with `LATTIS_DATA_DIR` if needed.
