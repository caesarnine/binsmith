"""Web UI static assets for Binsmith."""

from pathlib import Path


def get_static_dir() -> Path:
    """Return the path to the static assets directory."""
    return Path(__file__).parent / "static"
