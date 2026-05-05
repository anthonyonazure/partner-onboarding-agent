"""Shared fixtures: spin the mock portal in-process so tests have no port dependency."""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn

# Ensure stub content path runs (no real Anthropic calls during tests)
os.environ.pop("ANTHROPIC_API_KEY", None)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UvicornInThread:
    def __init__(self, app, host: str, port: int):
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        # Wait for ready
        for _ in range(50):
            if self.server.started:
                break
            time.sleep(0.05)
        return self

    def __exit__(self, *_):
        self.server.should_exit = True
        self.thread.join(timeout=5)


@pytest.fixture(scope="session")
def mock_portal_url():
    from mock_portal.main import app

    # Reset module-level dicts between sessions for cleanliness
    from mock_portal import main as mp

    mp._ACCOUNTS.clear()
    mp._ASSETS.clear()
    mp._INTAKE_FORMS.clear()

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    os.environ["B2B_PORTAL_BASE_URL"] = url
    os.environ["B2B_USE_MOCKS"] = "true"

    with _UvicornInThread(app, "127.0.0.1", port):
        # Verify reachable
        for _ in range(20):
            try:
                httpx.get(f"{url}/v1/accounts/__none__/usage", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        yield url


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
