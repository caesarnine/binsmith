from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal, Sequence

from lattis.cli import main as lattis_main
from lattis.settings.env import (
    LATTIS_DATA_DIR,
    LATTIS_DATA_DIR_NAME,
    LATTIS_DB_PATH,
    LATTIS_SESSION_FILE,
    LATTIS_WORKSPACE_DIR,
)

StorageMode = Literal["global", "project"]


def _default_global_data_dir() -> str:
    return str(Path.home() / ".binsmith")


def _strip_binsmith_flags(argv: list[str]) -> tuple[StorageMode | None, list[str]]:
    mode: StorageMode | None = None
    forwarded: list[str] = []
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--":
            forwarded.extend(argv[idx:])
            break
        if arg == "--global":
            if mode and mode != "global":
                raise SystemExit("binsmith: --global and --project are mutually exclusive")
            mode = "global"
            idx += 1
            continue
        if arg == "--project":
            if mode and mode != "project":
                raise SystemExit("binsmith: --global and --project are mutually exclusive")
            mode = "project"
            idx += 1
            continue
        forwarded.append(arg)
        idx += 1

    return mode, forwarded


def _apply_storage_mode(mode: StorageMode, *, explicit: bool) -> None:
    if mode == "project":
        for key in (
            LATTIS_DATA_DIR,
            LATTIS_WORKSPACE_DIR,
            LATTIS_DB_PATH,
            LATTIS_SESSION_FILE,
        ):
            os.environ.pop(key, None)
        os.environ[LATTIS_DATA_DIR_NAME] = "binsmith"
        return

    data_dir = _default_global_data_dir()
    if explicit:
        os.environ[LATTIS_DATA_DIR] = data_dir
        for key in (LATTIS_DATA_DIR_NAME, LATTIS_WORKSPACE_DIR, LATTIS_DB_PATH, LATTIS_SESSION_FILE):
            os.environ.pop(key, None)
    else:
        os.environ.setdefault(LATTIS_DATA_DIR, data_dir)


def _wants_help(argv: list[str]) -> bool:
    for arg in argv:
        if arg == "--":
            break
        if arg in {"-h", "--help"}:
            return True
    return False


def _print_binsmith_help() -> None:
    print("Binsmith options (affects storage, not where commands run):")
    print("  --global   Store tools + history in ~/.binsmith (default)")
    print("  --project  Store tools + history in .binsmith/ under the current directory")
    print("")
    print("Commands still run in the project directory (the directory the server starts in).")
    print("")


def main(argv: Sequence[str] | None = None) -> None:
    os.environ.setdefault("AGENT_DEFAULT", "binsmith")

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    mode, forwarded = _strip_binsmith_flags(raw_argv)
    resolved: StorageMode = mode or "global"
    _apply_storage_mode(resolved, explicit=mode is not None)

    if _wants_help(raw_argv):
        _print_binsmith_help()

    lattis_main(forwarded)
