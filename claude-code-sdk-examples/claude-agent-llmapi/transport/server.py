"""
Localhost proxy: Anthropic-compatible API → internal LLM API.

Point the Claude Agent SDK at http://127.0.0.1:<port>/v1 instead of
https://api.anthropic.com.  The proxy translates auth (MSAL Bearer)
and model names (dev-anthropic-* header) transparently.

MSAL token is cached after first interactive auth — subsequent calls
use acquire_token_silent, so the user only sees a login prompt once.
"""

import argparse
import json
import sys

import requests
from flask import Flask, Response, request, stream_with_context
from msal import PublicClientApplication

# ── LLM API defaults ────────────────────────────────────────────────
LLMAPI_BASE = "https://fe-26.qas.bing.net/sdf/"
LLMAPI_SCOPES = ["https://substrate.office.com/llmapi/LLMAPI.dev"]
CLIENT_ID = "68df66a4-cad9-4bfd-872b-c6ddde00d6b2"
AUTHORITY = "https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47"
TIMEOUT = (10, 300)  # (connect, read) seconds
MODEL_PREFIX = "dev-anthropic-"

# ── MSAL auth ───────────────────────────────────────────────────────


class TokenManager:
    """Handles MSAL auth with in-memory token caching.

    Call authenticate() once at startup to front-load the interactive
    prompt.  All later get_token() calls resolve silently from cache
    until the refresh token itself expires.
    """

    def __init__(self):
        self._app = PublicClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            enable_broker_on_windows=True,
        )

    def authenticate(self):
        """Trigger interactive auth up front so requests never block on login."""
        return self._acquire_interactive()

    def get_token(self) -> str:
        """Return a valid access token, refreshing silently when possible."""
        accounts = self._app.get_accounts()
        if accounts:
            result = self._app.acquire_token_silent(LLMAPI_SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]
        return self._acquire_interactive()

    def _acquire_interactive(self) -> str:
        if sys.platform == "win32":
            result = self._app.acquire_token_interactive(
                scopes=LLMAPI_SCOPES,
                parent_window_handle=self._app.CONSOLE_WINDOW_HANDLE,
            )
        else:
            flow = self._app.initiate_device_flow(scopes=LLMAPI_SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(
                    f"Device flow init failed: {json.dumps(flow, indent=2)}"
                )
            print(flow["message"])
            result = self._app.acquire_token_by_device_flow(flow)

        if "error" in result:
            raise RuntimeError(
                f"Token error: {result.get('error_description', result['error'])}"
            )
        return result["access_token"]


# ── Model mapping ───────────────────────────────────────────────────


def _resolve_model(model: str) -> str:
    """Map an Anthropic SDK model name to the LLM API X-ModelType value."""
    if model.startswith(MODEL_PREFIX):
        return model
    return f"{MODEL_PREFIX}{model}"


# ── LLM API forwarding ─────────────────────────────────────────────


def _forward_request(
    token_manager: TokenManager,
    model: str,
    body: dict,
    stream: bool = False,
) -> requests.Response:
    """Send a request to the LLM API messages endpoint."""
    token = token_manager.get_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-ModelType": _resolve_model(model),
        "anthropic-version": "2023-06-01",
    }
    endpoint = f"{LLMAPI_BASE}messages"
    return requests.post(
        endpoint,
        data=json.dumps(body),
        headers=headers,
        stream=stream,
        timeout=TIMEOUT,
    )


# ── Flask app ───────────────────────────────────────────────────────

app = Flask(__name__)
token_manager: TokenManager = None  # initialised in main()


def _error(message: str, status: int = 400) -> Response:
    body = json.dumps(
        {
            "type": "error",
            "error": {"type": "invalid_request_error", "message": message},
        }
    )
    return Response(body, status=status, content_type="application/json")


@app.route("/v1/messages", methods=["POST"])
def messages():
    body = request.get_json(force=True)

    model = body.pop("model", None)
    if not model:
        return _error("model is required")

    is_stream = body.get("stream", False)

    try:
        upstream = _forward_request(token_manager, model, body, stream=is_stream)
    except Exception as exc:
        return _error(str(exc), status=502)

    if is_stream:

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(
            stream_with_context(generate()),
            status=upstream.status_code,
            headers={
                "Content-Type": upstream.headers.get(
                    "Content-Type", "text/event-stream"
                ),
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


# ── Entrypoint ──────────────────────────────────────────────────────


def main():
    global token_manager, LLMAPI_BASE

    parser = argparse.ArgumentParser(description="Anthropic API → LLM API proxy")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--endpoint", type=str, help="Override LLM API base URL")
    args = parser.parse_args()

    if args.endpoint:
        LLMAPI_BASE = args.endpoint.rstrip("/") + "/"

    token_manager = TokenManager()

    print("Authenticating with LLM API …")
    token_manager.authenticate()
    print(f"Authenticated.  Proxy listening on http://{args.host}:{args.port}")
    print(f"  SDK base URL → http://{args.host}:{args.port}/v1")

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
