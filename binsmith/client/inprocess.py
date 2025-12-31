from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI

from binsmith.client.api import BinsmithClient
from binsmith.config import StorageConfig, load_storage_config
from binsmith.server.app import create_app


@dataclass(frozen=True)
class InProcessServer:
    app: FastAPI
    config: StorageConfig


def create_inprocess_client(
    *,
    project_root: Path,
    workspace_mode: Literal["central", "local"] = "local",
) -> tuple[BinsmithClient, InProcessServer]:
    config = load_storage_config(project_root=project_root, workspace_mode=workspace_mode)
    app = create_app(config)
    transport = httpx.ASGITransport(app=app)
    base_url = "http://binsmith.inprocess"
    http_client = httpx.AsyncClient(base_url=base_url, transport=transport)
    return BinsmithClient(base_url, client=http_client), InProcessServer(app=app, config=config)

