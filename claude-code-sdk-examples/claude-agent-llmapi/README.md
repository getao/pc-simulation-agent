# claude-agent-llmapi

Localhost proxy bridging the Claude Agent SDK to an internal LLM API via MSAL auth.
Includes a **Word Document Agent** powered by the `@anthropic/docx` skill, routed
through the proxy so Claude Code uses the internal LLM API instead of Anthropic's console.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |
| [nvm-windows](https://github.com/coreybutler/nvm-windows) | 1.2+ | Node.js version manager |
| Node.js | 24.x LTS | Required by docx skill (docx-js) |
| Claude Code CLI | latest | Agent backend |
| Network access | — | LLM API + MSAL auth endpoints |

## Environment Setup

### 1. Install uv (Python package manager)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install nvm-windows + Node.js

```powershell
# Install nvm-windows
winget install CoreyButler.NVMforWindows

# Restart your terminal, then:
nvm install lts
nvm use 24.14.0        # or whatever version was installed

# Verify
node --version
npm --version
```

> **PowerShell note:** If you get "running scripts is disabled", run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install docx npm package (globally)

```powershell
npm install -g docx
```

### 4. Install Claude Code CLI

```powershell
npm install -g @anthropic-ai/claude-code
```

### 5. Install Python dependencies

```powershell
uv sync
```

MSAL authentication will prompt interactively on first run (browser login).
Subsequent runs use cached tokens with silent refresh.

## Project Structure

```
claude-agent-llmapi/
├── transport/
│   ├── server.py      # Proxy server (MSAL auth + LLM API forwarding)
│   └── __init__.py
├── tests/
│   ├── test_transport.py  # Functional tests
│   └── __init__.py
├── agent.py           # Simple dummy agent (anthropic SDK)
├── word_agent.py      # Word document agent (docx skill, via proxy)
├── workspace/         # Document I/O directory
├── pyproject.toml     # Dependencies
└── README.md
```

The Word agent also depends on the shared plugin at `../plugins/docx-plugin/`.

## Usage

### Proxy Server

```powershell
# Start on default port 8082
uv run python -m transport.server

# Custom port
uv run python -m transport.server --port 9000

# Override LLM API endpoint
uv run python -m transport.server --endpoint https://other-host/path/
```

### Dummy Agent

```powershell
# Start proxy first, then in another terminal:
uv run python agent.py
uv run python agent.py --prompt "Explain recursion"
```

### Word Document Agent

```powershell
# Start proxy first, then in another terminal:
uv run python word_agent.py

# Custom prompt
uv run python word_agent.py --prompt "Create a professional cover letter"

# Use a different model
uv run python word_agent.py --model claude-sonnet-4-5
```

Documents are saved to the `workspace/` directory.

### Tests

```powershell
uv run pytest tests/test_transport.py -v
```

Functional tests — requires MSAL authentication and network access to the LLM API.

## How It Works

1. `transport/server.py` starts a Flask proxy on `http://127.0.0.1:8082`
2. MSAL authenticates via browser on first run, then uses silent token refresh
3. `word_agent.py` sets `ANTHROPIC_BASE_URL=http://127.0.0.1:8082/v1` so Claude Code CLI routes through the proxy
4. Proxy maps model names to `X-ModelType` header (prepends `dev-anthropic-`) and forwards to the LLM API
5. The docx plugin provides the `@anthropic/docx` skill for document creation/editing

## Model Registry

Tested against the LLM API (February 2026):

| Model | X-ModelType | Status |
|-------|-------------|--------|
| `claude-opus-4-6` | `dev-anthropic-claude-opus-4-6` | OK |
| `claude-opus-4-5` | `dev-anthropic-claude-opus-4-5` | OK |
| `claude-opus-4-1` | `dev-anthropic-claude-opus-4-1` | OK |
| `claude-opus-4-0` | `dev-anthropic-claude-opus-4-0` | OK |
| `claude-sonnet-4-5` | `dev-anthropic-claude-sonnet-4-5` | OK |
| `claude-sonnet-4-0` | `dev-anthropic-claude-sonnet-4-0` | OK |
| `claude-haiku-4-5` | `dev-anthropic-claude-haiku-4-5` | OK |
| `claude-3-7-sonnet-latest` | `dev-anthropic-claude-3-7-sonnet-latest` | 404 — not found |
| `claude-3-5-haiku-latest` | `dev-anthropic-claude-3-5-haiku-latest` | 404 — not found |
| `claude-3-5-sonnet-latest` | `dev-anthropic-claude-3-5-sonnet-latest` | 403 — unauthorized |
