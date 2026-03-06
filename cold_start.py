"""
Cold Start CLI — generate a realistic Windows PC filesystem from a user persona.

Usage:
    uv run python cold_start.py --persona "A mid-career history professor..."
    uv run python cold_start.py --persona-file persona.txt
    uv run python cold_start.py --persona-file persona.txt --timestamp "2025-03-01T10:00:00"
    uv run python cold_start.py --persona-file persona.txt --plugins ../plugins/docx-plugin
"""

import argparse
import os
import sys
from datetime import datetime

import anyio

from pipeline import cold_start


def main():
    parser = argparse.ArgumentParser(
        description="Cold Start: generate a UserWorld from a persona"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--persona", type=str, help="Persona description text")
    group.add_argument("--persona-file", type=str, help="Path to a file containing the persona description")

    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Current timestamp (ISO format). Default: now",
    )
    parser.add_argument(
        "--world-id",
        type=str,
        default=None,
        help="Custom world ID. Default: auto-generated",
    )
    parser.add_argument(
        "--plugins",
        type=str,
        nargs="*",
        default=None,
        help="Paths to plugin/skill directories to load into Claude Code",
    )
    parser.add_argument(
        "--worlds-root",
        type=str,
        default="worlds",
        help="Root directory for generated worlds. Default: worlds/",
    )
    parser.add_argument(
        "--max-generate",
        type=int,
        default=None,
        help="Only generate content for the first N files (dry-run mode). Planning still produces the full file list.",
    )

    args = parser.parse_args()

    # Resolve persona text
    if args.persona_file:
        if not os.path.exists(args.persona_file):
            print(f"Error: persona file not found: {args.persona_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.persona_file, "r", encoding="utf-8") as f:
            persona = f.read().strip()
    else:
        persona = args.persona

    if not persona:
        print("Error: persona text is empty", file=sys.stderr)
        sys.exit(1)

    # Resolve plugins
    plugins = None
    if args.plugins:
        plugins = [{"type": "local", "path": os.path.normpath(p)} for p in args.plugins]

    # Resolve timestamp
    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    async def run():
        world_dir = await cold_start(
            persona=persona,
            current_timestamp=timestamp,
            world_id=args.world_id,
            plugins=plugins,
            worlds_root=args.worlds_root,
            max_generate=args.max_generate,
        )
        print(f"\nWorld created at: {world_dir}")

    anyio.run(run)


if __name__ == "__main__":
    main()
