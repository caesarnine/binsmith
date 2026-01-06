from __future__ import annotations

import os
from typing import Sequence

from lattis.cli import main as lattis_main


def main(argv: Sequence[str] | None = None) -> None:
    os.environ.setdefault("AGENT_DEFAULT", "binsmith")
    lattis_main(list(argv) if argv is not None else None)
