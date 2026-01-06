from __future__ import annotations

from pathlib import Path


def ensure_workspace(path: Path) -> Path:
    """Ensure the Binsmith workspace directory structure exists."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "bin").mkdir(exist_ok=True)
    (path / "data").mkdir(exist_ok=True)
    (path / "tmp").mkdir(exist_ok=True)
    return path
