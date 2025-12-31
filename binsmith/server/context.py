from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from binsmith.config import StorageConfig
from binsmith.core.session import SessionStore


@dataclass(frozen=True)
class AppContext:
    config: StorageConfig
    store: SessionStore
    workspace: Path
    project_root: Path
