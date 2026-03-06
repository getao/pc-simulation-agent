"""
Functional tests for the proxy server.

These tests start the Flask app, authenticate via MSAL, and make real
requests through the proxy to the LLM API.  They require network
access and valid credentials.

Run:  uv run pytest tests/test_transport.py -v
"""

import json
import threading
import time

import pytest
import requests

from transport.server import TokenManager, app

BASE = None  # set in module setup


@pytest.fixture(scope="module", autouse=True)
def _start_proxy():
    """Boot the proxy on a random port and authenticate once."""
    global BASE
    import transport.server as srv

    srv.token_manager = TokenManager()
    print("\n[test] Authenticating …")
    srv.token_manager.authenticate()

    # Port 0 → OS picks a free port; we extract it after startup.
    server = None

    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    port = server.socket.getsockname()[1]
    BASE = f"http://127.0.0.1:{port}"

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # Give the server a moment to be ready.
    time.sleep(0.3)
    yield
    server.shutdown()


# ── Health ──────────────────────────────────────────────────────────

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Validation ──────────────────────────────────────────────────────

def test_missing_model_returns_400():
    r = requests.post(
        f"{BASE}/v1/messages",
        json={"max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["type"] == "invalid_request_error"


# ── Non-streaming ──────────────────────────────────────────────────

def test_messages_non_streaming():
    r = requests.post(
        f"{BASE}/v1/messages",
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with exactly: hello"}],
        },
    )
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:500]}"
    body = r.json()
    # Anthropic response shape: { "content": [ { "type": "text", "text": "..." } ] }
    assert "content" in body
    assert any(block.get("text") for block in body["content"])


# ── Streaming ──────────────────────────────────────────────────────

def test_messages_streaming():
    r = requests.post(
        f"{BASE}/v1/messages",
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with exactly: hello"}],
            "stream": True,
        },
        stream=True,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("Content-Type", "")

    events = []
    for line in r.iter_lines():
        text = line.decode("utf-8").strip()
        if text.startswith("data: "):
            payload = text[6:]
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))
    r.close()

    # We should have received at least one SSE event.
    assert len(events) > 0
