# claude-agent-llmapi - Project Memory

## Overview
- **Purpose**: Localhost proxy bridging the Claude Agent SDK to an internal LLM API
- **Tech Stack**: Python, Flask, MSAL, requests

## How It Works
1. Claude Agent SDK sends Anthropic-format requests to `http://127.0.0.1:8082/v1/messages`
2. Proxy extracts `model` from body, maps it to `X-ModelType` header (`dev-anthropic-` prefix)
3. Authenticates via MSAL Bearer token (cached after first interactive login)
4. Forwards request to LLM API (`https://fe-26.qas.bing.net/sdf/messages`)
5. Streams or returns the response back to the SDK

## Structure
- `transport/server.py` — Proxy server: MSAL auth, LLM API forwarding, and Flask routes (single file)
- `transport/__init__.py` — Package marker
- `agent.py` — Dummy agent using the `anthropic` SDK against the proxy
- `word_agent.py` — Word document agent using @anthropic/docx skill, routed through proxy
- `workspace/` — Working directory for document I/O
- `tests/test_transport.py` — Functional tests (real LLM API calls through the proxy)
- `pyproject.toml` — Project metadata and dependencies (uv)

## Commands
- Install: `uv sync`
- Run: `uv run python -m transport.server` (default port 8082)
- Run with custom port: `uv run python -m transport.server --port 9000`
- Override LLM API endpoint: `uv run python -m transport.server --endpoint https://other-host/path/`
- Test: `uv run pytest tests/test_transport.py -v` (requires auth + network)
- SDK config: set base URL to `http://127.0.0.1:8082/v1`

## Conventions
- Model mapping: SDK sends `claude-sonnet-4-5`, proxy prepends `dev-anthropic-` → `dev-anthropic-claude-sonnet-4-5`
- Auth happens once at startup via `token_manager.authenticate()`; all requests use silent token refresh
- Streaming uses raw byte proxying (`iter_content`) to preserve SSE format

## Learnings
- Word agent sets `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` via `ClaudeAgentOptions.env` to route Claude Code CLI through the proxy
- MSAL `acquire_token_silent` handles refresh tokens automatically — no manual expiry tracking needed
- `model` field must be popped from body before forwarding — LLM API uses `X-ModelType` header only. If model stays in the body, the API tries to validate it as an Anthropic model name and fails.
- `claude-3-5-haiku-latest` is not a valid model name on LLM API; use `claude-haiku-4-5`, `claude-sonnet-4-5`, `claude-opus-4-1` etc.
- `pymsalruntime` is needed on Windows for the WAM broker to work
