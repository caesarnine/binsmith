"""ASGI application entrypoint for Binsmith server."""

from binsmith.server.app import create_app

app = create_app()
