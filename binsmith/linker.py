from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Mapping

from binsmith.env import read_bool_env

BINSMITH_BIN_DIR = "BINSMITH_BIN_DIR"
BINSMITH_LINK_BINS = "BINSMITH_LINK_BINS"

_SKIP_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}


def link_workspace_bins(workspace: Path) -> None:
    if not read_bool_env(BINSMITH_LINK_BINS, default=True):
        return

    env = os.environ
    link_dir = _pick_link_dir(env)
    if link_dir is None:
        return

    bin_dir = workspace / "bin"
    if not bin_dir.exists():
        return

    for path in sorted(bin_dir.iterdir()):
        if not _is_tool_path(path):
            continue
        _link_tool(path, link_dir, bin_dir, env)


def _pick_link_dir(env: Mapping[str, str]) -> Path | None:
    for candidate in _candidate_link_dirs(env):
        if _ensure_dir(candidate):
            return candidate
    return None


def _candidate_link_dirs(env: Mapping[str, str]) -> list[Path]:
    explicit = env.get(BINSMITH_BIN_DIR)
    if explicit:
        return [Path(explicit).expanduser()]

    home = _safe_resolve(Path.home())
    seen: set[str] = set()
    candidates: list[Path] = []
    for entry in _path_entries(env):
        resolved = str(_safe_resolve(entry))
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_under_home(entry, home):
            candidates.append(entry)
    return candidates


def _path_entries(env: Mapping[str, str]) -> list[Path]:
    raw = env.get("PATH", "")
    if not raw:
        return []
    return [Path(item).expanduser() for item in raw.split(os.pathsep) if item]


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser()


def _is_under_home(path: Path, home: Path) -> bool:
    try:
        return _safe_resolve(path).is_relative_to(home)
    except ValueError:
        return False


def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


def _is_tool_path(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    if path.suffix in _SKIP_SUFFIXES:
        return False
    return True


def _link_tool(
    source: Path,
    link_dir: Path,
    workspace_bin: Path,
    env: Mapping[str, str],
) -> None:
    target = link_dir / source.name

    if target.is_symlink():
        if _samefile(target, source):
            return
        if not target.exists() and _points_to_workspace(target, workspace_bin):
            _replace_symlink(target, source)
        return

    if target.exists():
        return

    if _shadows_existing(source.name, workspace_bin, link_dir, env):
        return

    _create_symlink(target, source)


def _points_to_workspace(link: Path, workspace_bin: Path) -> bool:
    try:
        resolved = link.resolve(strict=False)
    except OSError:
        return False
    return _is_under_path(resolved, workspace_bin)


def _shadows_existing(
    name: str,
    workspace_bin: Path,
    link_dir: Path,
    env: Mapping[str, str],
) -> bool:
    existing = shutil.which(name, path=env.get("PATH", ""))
    if not existing:
        return False
    existing_path = Path(existing)
    if _is_under_path(existing_path, workspace_bin):
        return False
    if _is_under_path(existing_path, link_dir):
        return False
    return True


def _is_under_path(path: Path, root: Path) -> bool:
    try:
        return _safe_resolve(path).is_relative_to(_safe_resolve(root))
    except ValueError:
        return False


def _samefile(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def _replace_symlink(target: Path, source: Path) -> None:
    try:
        target.unlink()
    except OSError:
        return
    _create_symlink(target, source)


def _create_symlink(target: Path, source: Path) -> None:
    try:
        target.symlink_to(source)
    except OSError:
        return
