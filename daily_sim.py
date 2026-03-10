"""
Daily Simulation CLI — simulate ~20 working days of daily activity on an
existing Cold Start world.

Usage:
    uv run python daily_sim.py --world-id gdpeval_world_000000
    uv run python daily_sim.py --world-id gdpeval_world_000000 --weeks 2
    uv run python daily_sim.py --world-id gdpeval_world_000000 --start-date 2026-02-02
    uv run python daily_sim.py --world-id gdpeval_world_000000 --model claude-sonnet-4-6
"""

import argparse
import os
import sys
from datetime import datetime

import anyio

from pipeline import daily_simulate


def main():
    parser = argparse.ArgumentParser(
        description="Daily Simulation: simulate daily work on an existing Cold Start world"
    )

    parser.add_argument(
        "--world-id",
        type=str,
        required=True,
        help="World ID (directory name under worlds/)",
    )
    parser.add_argument(
        "--worlds-root",
        type=str,
        default="worlds",
        help="Root directory for worlds. Default: worlds/",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Simulation start date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=4,
        help="Number of weeks to simulate. Default: 4",
    )
    parser.add_argument(
        "--plugins",
        type=str,
        nargs="*",
        default=None,
        help="Paths to plugin/skill directories to load into Claude Code",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Claude model to use (e.g. claude-sonnet-4-6). Default: SDK default.",
    )

    args = parser.parse_args()

    # Resolve world directory
    world_dir = os.path.join(args.worlds_root, args.world_id)
    if not os.path.isdir(world_dir):
        print(f"Error: world directory not found: {world_dir}", file=sys.stderr)
        sys.exit(1)

    # Check Cold Start completion
    if not os.path.exists(os.path.join(world_dir, "_complete")):
        print(
            f"Error: world {args.world_id} has not completed Cold Start. "
            f"Run cold_start.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve plugins
    plugins = None
    if args.plugins:
        plugins = [{"type": "local", "path": os.path.normpath(p)} for p in args.plugins]

    # Resolve start date
    start_date = args.start_date or datetime.now().strftime("%Y-%m-%d")

    async def run():
        result_dir = await daily_simulate(
            world_dir=world_dir,
            start_date=start_date,
            num_weeks=args.weeks,
            plugins=plugins,
            model=args.model,
        )
        print(f"\nDaily Simulation complete: {result_dir}")

    anyio.run(run)


if __name__ == "__main__":
    main()
