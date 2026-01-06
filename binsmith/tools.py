from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, TypedDict


class _ToolCacheEntry(TypedDict, total=False):
    description: str
    mtime_ns: int
    size: int


_TOOL_CACHE_VERSION = 1


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


def format_tools_section(tools: list[tuple[str, str]]) -> str:
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
    lines.append(
        "Run `<tool> --help` for usage. Remember: use existing tools before writing one-off commands."
    )

    return "\n".join(lines)
