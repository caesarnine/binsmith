from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import uvicorn

from binsmith.tui.app import run_tui

DEFAULT_SERVER_URL = os.getenv("BINSMITH_SERVER_URL", "http://localhost:8000")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        argv = ["tui"]
    elif argv[0].startswith("-") and argv[0] not in {"-h", "--help"}:
        argv = ["tui", *argv]
    args = parser.parse_args(argv)

    command = args.command or "tui"
    if command == "tui":
        _run_tui_command(args)
        return
    if command == "server":
        _run_server_command(args)
        return

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="binsmith", description="Binsmith CLI")
    subparsers = parser.add_subparsers(dest="command")

    tui_parser = subparsers.add_parser("tui", help="Run the Binsmith TUI client")
    _add_tui_args(tui_parser)

    server_parser = subparsers.add_parser("server", help="Run the Binsmith API server")
    _add_server_args(server_parser)

    return parser


def _add_tui_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URL,
        help="Binsmith server base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Do not auto-start a local server if missing",
    )
    parser.add_argument(
        "--server-workspace",
        choices=("local", "central"),
        default="local",
        help="Workspace mode for an auto-started server (default: %(default)s)",
    )


def _add_server_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (default: %(default)s)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload",
    )
    parser.add_argument(
        "--local-workspace",
        action="store_true",
        help="Use a project-local .binsmith workspace on the server",
    )


def _run_tui_command(args: argparse.Namespace) -> None:
    server_url = _normalize_server_url(args.server)
    project_root = Path.cwd()

    autostart = _autostart_enabled(args)
    server_process = _ensure_server(
        server_url,
        autostart=autostart,
        project_root=project_root,
        local_workspace=(args.server_workspace == "local"),
    )

    try:
        run_tui(server_url=server_url, server_process=server_process)
    finally:
        if server_process and server_process.poll() is None:
            _stop_process(server_process)


def _run_server_command(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    os.environ.setdefault("BINSMITH_PROJECT_ROOT", str(project_root))
    if args.local_workspace:
        os.environ.setdefault("BINSMITH_WORKSPACE_MODE", "local")

    uvicorn.run("binsmith.server.asgi:app", host=args.host, port=args.port, reload=args.reload)


def _autostart_enabled(args: argparse.Namespace) -> bool:
    if args.no_autostart:
        return False
    env_value = os.getenv("BINSMITH_SERVER_AUTOSTART", "1").strip().lower()
    return env_value not in {"0", "false", "no"}


def _normalize_server_url(url: str) -> str:
    if "://" not in url:
        url = f"http://{url}"
    parsed = urlparse(url)
    if not parsed.netloc:
        raise SystemExit(f"Invalid server URL: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    if parsed.scheme not in {"http", ""}:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def _ensure_server(
    server_url: str,
    *,
    autostart: bool,
    project_root: Path,
    local_workspace: bool,
) -> subprocess.Popen | None:
    if _server_healthy(server_url):
        return None

    if not autostart:
        _exit_unavailable(server_url)

    if not _is_local_url(server_url):
        _exit_unavailable(server_url)

    process = _start_local_server(server_url, project_root, local_workspace)
    if not _wait_for_server(server_url):
        _stop_process(process)
        raise SystemExit("Server failed to start; check logs or port availability.")

    return process


def _server_healthy(server_url: str) -> bool:
    try:
        response = httpx.get(f"{server_url}/health", timeout=1.0)
    except httpx.RequestError:
        return False
    return response.status_code == 200


def _wait_for_server(server_url: str, timeout: float = 10.0, interval: float = 0.2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_healthy(server_url):
            return True
        time.sleep(interval)
    return False


def _start_local_server(
    server_url: str,
    project_root: Path,
    local_workspace: bool,
) -> subprocess.Popen:
    parsed = urlparse(server_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000

    env = os.environ.copy()
    env["BINSMITH_PROJECT_ROOT"] = str(project_root)
    if local_workspace:
        env["BINSMITH_WORKSPACE_MODE"] = "local"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "binsmith.server.asgi:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    return subprocess.Popen(
        cmd,
        cwd=project_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _exit_unavailable(server_url: str) -> None:
    print(
        f"Binsmith server not reachable at {server_url}. "
        "Start it with `binsmith server` or pass --no-autostart to disable checks.",
        file=sys.stderr,
    )
    raise SystemExit(1)
