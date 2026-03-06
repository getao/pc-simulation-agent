"""
Dummy agent using the Anthropic Python SDK against the localhost proxy.

Sends a simple prompt and prints the response.

Usage:
    1. Start the proxy: uv run python -m transport.server
    2. In another terminal: uv run python agent.py
    3. Or with a custom prompt: uv run python agent.py --prompt "Explain recursion"
"""

import argparse

import anthropic


def run_agent(prompt: str, base_url: str):
    client = anthropic.Anthropic(
        base_url=base_url,
        api_key="unused",  # proxy handles auth via MSAL
    )

    print(f"Agent prompt: {prompt}")
    print(f"Proxy: {base_url}\n")
    print("--- Response ---")

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in message.content:
        if block.type == "text":
            print(block.text)

    print("--- Done ---")


def main():
    parser = argparse.ArgumentParser(description="Dummy Claude Agent (LLM API proxy)")
    parser.add_argument("--prompt", type=str, default="What is 2 + 2? Reply in one word.")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8082/v1")
    args = parser.parse_args()

    run_agent(args.prompt, args.base_url)


if __name__ == "__main__":
    main()
