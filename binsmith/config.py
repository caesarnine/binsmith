from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class StorageConfig:
    data_dir: Path
    db_path: Path
    session_id_path: Path
    workspace_dir: Path
    project_root: Path
    workspace_mode: Literal["central", "local"]


def _resolve_workspace_mode(explicit: str | None) -> Literal["central", "local"]:
    value = (explicit or os.getenv("BINSMITH_WORKSPACE_MODE") or "local").strip().lower()
    if value in {"local", "project", "cwd"}:
        return "local"
    return "central"


def load_storage_config(
    *,
    project_root: Path | None = None,
    workspace_mode: str | None = None,
    data_dir: Path | None = None,
    workspace_dir: Path | None = None,
) -> StorageConfig:
    env_project_root = os.getenv("BINSMITH_PROJECT_ROOT")
    if project_root is not None:
        resolved_project_root = project_root
    elif env_project_root:
        resolved_project_root = Path(env_project_root)
    else:
        resolved_project_root = Path.cwd()
    resolved_mode = _resolve_workspace_mode(workspace_mode)

    if data_dir is None:
        data_dir_env = os.getenv("BINSMITH_DATA_DIR")
        if data_dir_env:
            data_dir = Path(data_dir_env)

    if data_dir is None:
        if resolved_mode == "local":
            data_dir = resolved_project_root / ".binsmith"
        else:
            data_dir = Path.home() / ".binsmith"

    if workspace_dir is None:
        workspace_dir_env = os.getenv("BINSMITH_WORKSPACE_DIR")
        if workspace_dir_env:
            workspace_dir = Path(workspace_dir_env)

    if workspace_dir is None:
        workspace_dir = data_dir / "workspace"

    db_path = Path(os.getenv("BINSMITH_DB_PATH", data_dir / "binsmith.db"))
    session_id_path = Path(os.getenv("BINSMITH_SESSION_FILE", data_dir / "session_id"))

    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    return StorageConfig(
        data_dir=data_dir,
        db_path=db_path,
        session_id_path=session_id_path,
        workspace_dir=workspace_dir,
        project_root=resolved_project_root,
        workspace_mode=resolved_mode,
    )


def load_or_create_session_id(path: Path, *, env_var: str = "BINSMITH_SESSION_ID") -> str:
    override = os.getenv(env_var)
    if override:
        return override
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    session_id = f"tui-{uuid.uuid4()}"
    path.write_text(session_id, encoding="utf-8")
    return session_id
