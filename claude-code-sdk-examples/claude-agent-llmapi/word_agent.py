"""
Word Document Agent using Claude Agent SDK + @anthropic/docx skill.

Routes through the localhost LLM API proxy (transport/server.py) so
Claude Code uses the internal LLM API instead of Anthropic's console.

Usage:
    1. Start the proxy:  uv run python -m transport.server
    2. Run the agent:    uv run python word_agent.py
    3. Custom prompt:    uv run python word_agent.py --prompt "Create a report about AI trends"
"""

import argparse
import os
import anyio

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

# Resolve paths relative to this file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "workspace")
PLUGIN_DIR = os.path.join(SCRIPT_DIR, os.pardir, "plugins", "docx-plugin")

PROXY_BASE_URL = "http://127.0.0.1:8082/v1"
PROXY_MODEL = "claude-haiku-4-5"  # See README.md for supported models

SYSTEM_PROMPT = {
    "type": "preset",
    "preset": "claude_code",
    "append": (
        "\n\nYou are an expert Word document creator and editor. "
        "You have access to the @anthropic/docx skill for creating and editing .docx files. "
        "Always produce professional, well-formatted documents. "
        "For new documents, use docx-js (JavaScript) with proper styles, headings, and formatting. "
        "For editing existing documents, use the unpack → edit XML → repack workflow. "
        "All documents should be saved in the current working directory. "
        "When creating documents, always validate them after creation."
    ),
}

DEFAULT_PROMPT = (
    "Create a professional one-page memo in Word format (.docx). "
    "Topic: Q4 2025 Performance Summary. "
    "Include a header with company name 'Acme Corp', date, and a 'CONFIDENTIAL' watermark text. "
    "Add sections: Executive Summary, Key Metrics (as a table with Revenue, Expenses, Net Income), "
    "and Next Steps. Use professional formatting with Arial font. "
    "Save it as 'Q4_Memo.docx' in the current directory."
)


async def run_word_agent(prompt: str, proxy_url: str, model: str):
    plugin_path = os.path.normpath(PLUGIN_DIR)
    workspace_path = os.path.normpath(WORKSPACE_DIR)

    os.makedirs(workspace_path, exist_ok=True)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        cwd=workspace_path,
        plugins=[{"type": "local", "path": plugin_path}],
        model=model,
        max_turns=25,
        env={
            "ANTHROPIC_BASE_URL": proxy_url,
            "ANTHROPIC_API_KEY": "unused",  # proxy handles auth via MSAL
        },
    )

    print(f"Workspace: {workspace_path}")
    print(f"Plugin:    {plugin_path}")
    print(f"Proxy:     {proxy_url}")
    print(f"Model:     {model}")
    print(f"Prompt:    {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print()
    print("--- Agent Output ---")

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Session: {message.session_id}]")

    print("\n--- Done ---")

    # List any created/modified files
    files = [f for f in os.listdir(workspace_path) if f.endswith(".docx")]
    if files:
        print(f"\nDocuments in workspace: {', '.join(files)}")


def main():
    parser = argparse.ArgumentParser(
        description="Word Document Agent (LLM API proxy)"
    )
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--proxy-url", type=str, default=PROXY_BASE_URL)
    parser.add_argument("--model", type=str, default=PROXY_MODEL)
    args = parser.parse_args()

    anyio.run(run_word_agent, args.prompt, args.proxy_url, args.model)


if __name__ == "__main__":
    main()
