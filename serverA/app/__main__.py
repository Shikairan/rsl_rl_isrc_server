"""Unified Server A entry: setup logging first, then uvicorn with log_config=None."""

from __future__ import annotations

import argparse

import uvicorn

from app.config import load_settings
from app.logging_setup import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Server A")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    setup_logging(settings)
    host = args.host or settings.server.host
    port = args.port if args.port is not None else settings.server.port
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
