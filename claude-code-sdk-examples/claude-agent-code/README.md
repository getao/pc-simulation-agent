# claude-agent-code

Claude agents using Claude Code CLI via the `claude-agent-sdk` Python package.
Includes a **Word Document Agent** powered by the `@anthropic/docx` skill.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |
| [nvm-windows](https://github.com/coreybutler/nvm-windows) | 1.2+ | Node.js version manager |
| Node.js | 24.x LTS | Required by docx skill (docx-js) |
| Claude Code CLI | latest | Agent backend |

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

Authenticate with your Anthropic account:
```powershell
claude login
```

### 5. Install Python dependencies

```powershell
uv sync
```

## Project Structure

```
claude-agent-code/
├── agent.py           # Simple dummy agent
├── word_agent.py      # Word document agent (docx skill)
├── workspace/         # Document I/O directory
├── pyproject.toml     # Dependencies
└── README.md
```

The Word agent also depends on the shared plugin at `../plugins/docx-plugin/`.

## Usage

### Dummy Agent

```powershell
uv run python agent.py
uv run python agent.py --prompt "Explain what a Makefile does"
```

### Word Document Agent

```powershell
# Default prompt (creates a Q4 memo)
uv run python word_agent.py

# Custom prompt
uv run python word_agent.py --prompt "Create a professional cover letter for a software engineer role"

# Edit an existing document
uv run python word_agent.py --prompt "Edit workspace/report.docx and add a table of contents"
```

Documents are saved to the `workspace/` directory.

## How It Works

1. `word_agent.py` calls `claude-agent-sdk` with the docx plugin (`--plugin-dir`)
2. Claude Code CLI loads the `@anthropic/docx` skill (SKILL.md + helper scripts)
3. For **new documents**: generates JavaScript using `docx-js`, runs it via Node.js
4. For **editing**: unpacks .docx → edits XML → repacks
5. Output is saved to `workspace/`

Authentication uses your Anthropic console account (via Claude Code CLI).
