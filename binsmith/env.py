from __future__ import annotations

import os

AGENT_MODEL = "AGENT_MODEL"


def read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def first_env(*names: str) -> str | None:
    for name in names:
        value = read_env(name)
        if value is not None:
            return value
    return None


def read_bool_env(name: str, *, default: bool = False) -> bool:
    value = read_env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}
