# Binsmith

An AI agent that builds its own toolkit.

Most agents are stateless—they solve problems, then forget everything. Binsmith takes a different approach: when it does something useful, it writes a script. That script goes into a persistent toolkit.

Ask it to fetch a webpage, it writes `fetch-url`. Ask it to convert HTML to markdown, it writes `html2md`. A week later, when you ask for a daily briefing, it composes them:

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

That `brief` command didn't exist until you needed it. Now it does, and it builds on tools that already existed. The more you use Binsmith, the more capable it becomes.

## Quick start

```bash
uvx binsmith
```

This starts the TUI with Binsmith as the default agent. You can also run the server for access from other devices:

```bash
uvx binsmith server
# Then open http://localhost:8000
```

Binsmith is a [Lattis](https://github.com/caesarnine/lattis) plugin. If you want to run it alongside other agents or access it remotely, see the Lattis README.

## How it works

Binsmith has one tool: `bash`. It runs commands in your project directory with `workspace/bin` on the PATH. That's it.

The magic is in the prompt. On each run, Binsmith sees its current toolkit and is instructed to:

1. **Check existing tools first** — don't reinvent what's already there
2. **Build tools for repeated work** — if you do it twice, script it
3. **Improve, don't duplicate** — enhance existing tools rather than creating variants

```
.lattis/
  workspace/
    bin/      # Scripts Binsmith creates (persists across sessions)
    data/     # Persistent data files
    tmp/      # Scratch space
```

## What the toolkit looks like

After a few days of use:

```
.lattis/workspace/bin/
  fetch-url     # Fetch a URL, handle retries, extract text
  html2md       # Convert HTML to clean markdown
  news          # Top stories from news sources
  weather       # Weather for a location
  todo          # Manage a simple todo list
  brief         # Daily briefing (composes news, weather, todo)
  summarize     # Summarize text or URLs
  json-extract  # Pull fields from JSON
```

Each tool is standalone. Python scripts use inline metadata so dependencies are declared in the file itself:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Fetch a URL and extract text content."""

# ... implementation
```

Just run the script—`uv` handles the rest.

## Unix philosophy

Binsmith builds tools that compose:

```bash
# Each tool does one thing
fetch-url https://news.ycombinator.com
html2md < page.html
summarize "key points only"

# Chain them together
fetch-url "$url" | html2md | summarize --bullets
```

Tools are prompted to follow conventions:
- Read from stdin when appropriate
- Output clean text to stdout
- Support `--json` for machine-readable output
- Support `--help` and `--describe` for discoverability
- Exit 0 on success, non-zero on failure

This isn't just style—it's what makes `fetch-url | html2md | summarize` work.

## Architecture

```
┌──────────────────────────────────────────┐
│              Clients                     │
│        TUI  /  Web UI  /  API            │
└─────────────────┬────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────┐
│            Lattis Server                 │
│   FastAPI · SQLite · Session management  │
└─────────────────┬────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────┐
│           Binsmith Agent                 │
│   Dynamic prompt · bash tool · Toolkit   │
└─────────────────┬────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────┐
│            File System                   │
│      Scripts as files · Git-friendly     │
└──────────────────────────────────────────┘
```

Binsmith runs on [Lattis](https://github.com/caesarnine/lattis), which handles the server, TUI, web UI, and persistence. Binsmith itself is just the agent logic and the bash tool.

## Running remotely

I run Binsmith on a server in my Tailscale network. This lets me:

- Start a task on my laptop
- Check progress from my phone
- Pick it back up from anywhere

```bash
# On the server
uvx binsmith server --host 0.0.0.0

# From anywhere else
uvx binsmith --server http://your-server:8000
```

See the [Lattis README](https://github.com/caesarnine/lattis) for more on remote setups.

## TUI commands

```
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

Lattis configuration (`LATTIS_*` variables) controls storage and server settings—see the Lattis README.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An API key for at least one model provider

```bash
export GEMINI_API_KEY=...     # Google
export ANTHROPIC_API_KEY=...  # Anthropic
export OPENAI_API_KEY=...     # OpenAI
```

## Why "Binsmith"?

It forges tools in `bin/`. A smith that makes bins.

(Also, "toolsmith" was taken.)
