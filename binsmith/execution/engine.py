from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class BashExecutionResult(BaseModel):
    """Result of a bash command execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class BashExecutor:
    """Execute bash commands via subprocess."""

    def execute(
        self,
        command: str,
        cwd: Path | None = None,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> BashExecutionResult:
        start = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)

            return BashExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return BashExecutionResult(
                exit_code=-1,
                stdout=e.stdout or "" if isinstance(e.stdout, str) else (e.stdout.decode() if e.stdout else ""),
                stderr=e.stderr or "" if isinstance(e.stderr, str) else (e.stderr.decode() if e.stderr else ""),
                duration_ms=duration_ms,
                timed_out=True,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return BashExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
