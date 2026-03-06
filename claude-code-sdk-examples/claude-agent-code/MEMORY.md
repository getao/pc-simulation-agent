# claude-agent-code - Project Memory

## Overview
- **Purpose**: Claude agents using Claude Code CLI via the claude-agent-sdk Python package
- **Tech Stack**: Python, claude-agent-sdk, anyio

## How It Works
1. Python calls `claude-agent-sdk` which shells out to the Claude Code CLI (Node.js)
2. Claude Code CLI authenticates via your org's Anthropic console account
3. Agents get full Claude Code capabilities: file editing, bash, tools, MCP servers

## Prerequisites
- Python 3.11+
- Node.js
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Authenticated Claude Code session

## Structure
- `agent.py` — Dummy agent sending a prompt and printing the response
- `word_agent.py` — Word document agent using @anthropic/docx skill via plugin
- `workspace/` — Working directory for document I/O
- `pyproject.toml` — Project metadata and dependencies (uv)

## Shared Resources (workspace root)
- `plugins/docx-plugin/` — Local plugin wrapper with junction to `anthropic-skills/skills/docx`
- `anthropic-skills/` — Cloned from github.com/anthropics/skills (docx, xlsx, pptx, pdf skills)

## Commands
- Install: `uv sync`
- Run dummy agent: `uv run python agent.py`
- Run Word agent: `uv run python word_agent.py`
- Run with prompt: `uv run python word_agent.py --prompt "Create a report about AI"`

## Conventions
- Word agent uses `permission_mode="bypassPermissions"` for headless operation
- Plugin loaded via `SdkPluginConfig(type="local", path=...)` which maps to `--plugin-dir` CLI flag
- `SystemPromptPreset` with `append` extends the default claude_code prompt

## Learnings
- `claude-agent-sdk` passes plugins to CLI as `--plugin-dir <path>` — the directory must contain `.claude-plugin/plugin.json` and `skills/` subdirectory
- `SdkPluginConfig` is a TypedDict with `type: Literal["local"]` and `path: str`
- `ClaudeCodeOptions` was renamed to `ClaudeAgentOptions` in claude-agent-sdk
- Node.js + `npm install -g docx` required for the docx skill's document creation (docx-js)
- nvm-windows installed at `C:\Users\visuryan\AppData\Local\nvm`, symlink at `C:\nvm4w\nodejs` — env vars NVM_HOME/NVM_SYMLINK must be set in new shells
