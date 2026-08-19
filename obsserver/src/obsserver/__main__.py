from __future__ import annotations

from obsserver.logging_setup import setup_logging
from obsserver.server import serve


def main() -> None:
    setup_logging()
    serve()


if __name__ == "__main__":
    main()
