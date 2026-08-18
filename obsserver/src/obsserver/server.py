"""本机 HTTP POST → transform → ZMQ PUB。HTTP 尽快 200，避免拖训练中继。"""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import zmq

from obsserver.transform import transform

logger = logging.getLogger("obsserver")

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 15558
DEFAULT_PUB_BIND = "0.0.0.0"
DEFAULT_PUB_PORT = 15557
DEFAULT_HTTP_PATH = "/post"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip()


class Forwarder:
    def __init__(
        self,
        *,
        http_host: str = DEFAULT_HTTP_HOST,
        http_port: int = DEFAULT_HTTP_PORT,
        http_path: str = DEFAULT_HTTP_PATH,
        pub_bind: str = DEFAULT_PUB_BIND,
        pub_port: int = DEFAULT_PUB_PORT,
    ) -> None:
        self.http_host = http_host
        self.http_port = http_port
        self.http_path = http_path if http_path.startswith("/") else f"/{http_path}"
        self.pub_bind = pub_bind
        self.pub_port = pub_port
        self._ctx = zmq.Context.instance()
        self._pub = self._ctx.socket(zmq.PUB)
        self._pub.setsockopt(zmq.LINGER, 0)
        self._pub.setsockopt(zmq.SNDHWM, 100)
        self._pub.setsockopt(zmq.SNDTIMEO, 0)
        self._pub.bind(f"tcp://{self.pub_bind}:{self.pub_port}")

    def publish(self, payload: Any) -> None:
        try:
            body = json.dumps(transform(payload), separators=(",", ":")).encode("utf-8")
            self._pub.send(body, zmq.NOBLOCK)
        except zmq.Again:
            return
        except Exception:
            logger.exception("PUB send failed")

    def close(self) -> None:
        self._pub.close(linger=0)


def make_handler(forwarder: Forwarder):
    path = forwarder.http_path.rstrip("/") or "/post"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), fmt % args)

        def _ok(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "2")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"ok")

        def do_POST(self) -> None:  # noqa: N802
            req_path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if req_path != path:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length > 0 else b""
            self._ok()
            try:
                payload = json.loads(raw.decode("utf-8") or "null")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            forwarder.publish(payload)

    return Handler


def serve(forwarder: Forwarder | None = None) -> None:
    if forwarder is None:
        forwarder = Forwarder(
            http_host=_env_str("OBS_HTTP_HOST", DEFAULT_HTTP_HOST),
            http_port=_env_int("OBS_HTTP_PORT", DEFAULT_HTTP_PORT),
            http_path=_env_str("OBS_HTTP_PATH", DEFAULT_HTTP_PATH),
            pub_bind=_env_str("OBS_PUB_BIND", DEFAULT_PUB_BIND),
            pub_port=_env_int("OBS_PUB_PORT", DEFAULT_PUB_PORT),
        )
    httpd = ThreadingHTTPServer((forwarder.http_host, forwarder.http_port), make_handler(forwarder))
    logger.info(
        "obsserver http://%s:%s%s -> pub tcp://%s:%s",
        forwarder.http_host,
        forwarder.http_port,
        forwarder.http_path,
        forwarder.pub_bind,
        forwarder.pub_port,
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        forwarder.close()
