"""Shared fixtures for the smoke-test suite."""

from __future__ import annotations

import importlib.util
import socket
import tempfile
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

_APP_PATH = Path(__file__).resolve().parents[1] / "targets" / "vulnerable_app" / "app.py"


def _load_vuln_app():
    """Import the vulnerable demo app as a module without running it."""
    spec = importlib.util.spec_from_file_location("vuln_app", _APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def target() -> str:
    """Run the vulnerable demo app on a random local port, with an isolated DB."""
    vuln = _load_vuln_app()
    vuln.DB_PATH = str(Path(tempfile.mkdtemp()) / "vuln-test.db")
    vuln.seed()
    port = _free_port()
    server = make_server("127.0.0.1", port, vuln.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=5)
