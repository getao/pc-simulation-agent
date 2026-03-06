"""
Word Document Agent using Claude Agent SDK + @anthropic/docx skill.

Uses Claude Code CLI with the docx plugin for expert Word document
creation, editing, and analysis.

Usage:
    uv run python word_agent.py
    uv run python word_agent.py --prompt "Create a professional memo about Q4 results"
    uv run python word_agent.py --prompt "Edit workspace/report.docx and add a table of contents"
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


async def run_word_agent(prompt: str):
    plugin_path = os.path.normpath(PLUGIN_DIR)
    workspace_path = os.path.normpath(WORKSPACE_DIR)

    os.makedirs(workspace_path, exist_ok=True)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        cwd=workspace_path,
        plugins=[{"type": "local", "path": plugin_path}],
        max_turns=25,
    )

    print(f"Workspace: {workspace_path}")
    print(f"Plugin:    {plugin_path}")
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
    parser = argparse.ArgumentParser(description="Word Document Agent (Claude Code)")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    args = parser.parse_args()

    anyio.run(run_word_agent, args.prompt)


if __name__ == "__main__":
    main()
