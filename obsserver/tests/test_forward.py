from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import closing

import pytest
import zmq

from obsserver.server import Forwarder, make_handler
from obsserver.transform import transform
from http.server import ThreadingHTTPServer


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_transform_identity() -> None:
    payload = [[[0.1, 0.2, 0.3], [0, 0, 0, 1], [0.0, 0.1]]]
    assert transform(payload) is payload
    assert transform(payload) == payload


def test_http_post_reaches_pub() -> None:
    http_port = _free_port()
    pub_port = _free_port()
    fwd = Forwarder(
        http_host="127.0.0.1",
        http_port=http_port,
        pub_bind="127.0.0.1",
        pub_port=pub_port,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", http_port), make_handler(fwd))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, b"")
    sub.setsockopt(zmq.RCVTIMEO, 2000)
    sub.connect(f"tcp://127.0.0.1:{pub_port}")
    time.sleep(0.15)

    import urllib.request

    payload = [[[1.0, 2.0, 3.0], [0.0, 0.0, 0.0, 1.0], [0.5]]]
    req = urllib.request.Request(
        f"http://127.0.0.1:{http_port}/post",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status == 200
        assert resp.read() == b"ok"

    raw = sub.recv()
    assert json.loads(raw.decode()) == payload

    sub.close()
    httpd.shutdown()
    fwd.close()


def test_bad_json_still_200() -> None:
    http_port = _free_port()
    pub_port = _free_port()
    fwd = Forwarder(
        http_host="127.0.0.1",
        http_port=http_port,
        pub_bind="127.0.0.1",
        pub_port=pub_port,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", http_port), make_handler(fwd))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    import urllib.request

    req = urllib.request.Request(
        f"http://127.0.0.1:{http_port}/post",
        data=b"not-json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status == 200

    httpd.shutdown()
    fwd.close()


def test_wrong_path_404() -> None:
    http_port = _free_port()
    pub_port = _free_port()
    fwd = Forwarder(
        http_host="127.0.0.1",
        http_port=http_port,
        pub_bind="127.0.0.1",
        pub_port=pub_port,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", http_port), make_handler(fwd))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"http://127.0.0.1:{http_port}/other",
        data=b"[]",
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=2)
    assert exc.value.code == 404

    httpd.shutdown()
    fwd.close()
