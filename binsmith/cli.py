from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from lattis.cli import main as lattis_main


def _normalize_workspace_mode(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if not value:
        return None
    if value in {"central"}:
        return "central"
    if value in {"local", "project", "cwd"}:
        return "local"
    return None


def _extract_workspace_mode(argv: Sequence[str]) -> str | None:
    for idx, arg in enumerate(argv):
        if arg.startswith("--workspace="):
            return arg.split("=", 1)[1]
        if arg == "--workspace" and idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def _default_data_dir(mode: str) -> str:
    if mode == "central":
        return str(Path.home() / ".binsmith")
    project_root = os.environ.get("LATTIS_PROJECT_ROOT")
    if project_root:
        return str(Path(project_root) / ".binsmith")
    return ".binsmith"


def main(argv: Sequence[str] | None = None) -> None:
    os.environ.setdefault("AGENT_DEFAULT", "binsmith")

    if "LATTIS_DATA_DIR" not in os.environ:
        env_mode = _normalize_workspace_mode(os.environ.get("LATTIS_WORKSPACE_MODE"))
        arg_mode = _normalize_workspace_mode(_extract_workspace_mode(argv or ()))
        mode = env_mode or arg_mode or "local"
        os.environ["LATTIS_DATA_DIR"] = _default_data_dir(mode)

    lattis_main(list(argv) if argv is not None else None)
