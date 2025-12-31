from __future__ import annotations

from pathlib import Path

from binsmith.config import load_storage_config


def get_default_workspace() -> Path:
    """Get the default workspace path."""
    config = load_storage_config()
    return config.workspace_dir


def get_default_project_root() -> Path:
    """Get the default project root."""
    config = load_storage_config()
    return config.project_root


def ensure_workspace(path: Path) -> Path:
    """Ensure workspace directory structure exists."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "bin").mkdir(exist_ok=True)
    (path / "data").mkdir(exist_ok=True)
    (path / "tmp").mkdir(exist_ok=True)
    return path
