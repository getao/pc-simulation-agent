"""
Dummy agent using Claude Agent SDK (backed by Claude Code CLI).

Sends a simple prompt and prints the response.

Usage:
    uv run python agent.py
    uv run python agent.py --prompt "Explain what a Makefile does"
"""

import argparse
import anyio

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock


async def run_agent(prompt: str):
    options = ClaudeAgentOptions(
        max_turns=1,
    )

    print(f"Agent prompt: {prompt}\n")
    print("--- Response ---")

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)

    print("\n--- Done ---")


def main():
    parser = argparse.ArgumentParser(description="Dummy Claude Agent (Claude Code)")
    parser.add_argument("--prompt", type=str, default="What is 2 + 2? Reply in one word.")
    args = parser.parse_args()

    anyio.run(run_agent, args.prompt)


if __name__ == "__main__":
    main()
