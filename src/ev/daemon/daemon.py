"""Hi-EV daemon runner."""

import uvicorn

from ev.server.api import app


def run(host: str = "127.0.0.1", port: int = 7345):
    """Run the EV Daemon API with uvicorn."""
    uvicorn.run(app, host=host, port=port)
