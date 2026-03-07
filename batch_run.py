"""
Batch runner — iterate over personas from a JSONL file and generate a UserWorld for each.

Usage:
    uv run python batch_run.py --input personas_subset_1k.jsonl
    uv run python batch_run.py --input personas_subset_1k.jsonl --limit 10
    uv run python batch_run.py --input personas_subset_1k.jsonl --limit 10 --offset 50
    uv run python batch_run.py --input personas_subset_1k.jsonl --max-generate 5
    uv run python batch_run.py --input personas_subset_1k.jsonl --concurrency 5
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime

import anyio

from pipeline import cold_start


async def run_batch(
    input_file: str,
    limit: int | None,
    offset: int,
    worlds_root: str,
    max_generate: int | None,
    model: str | None,
    plugins: list | None,
    concurrency: int = 1,
):
    # Stream-read personas
    personas = []
    with open(input_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if limit is not None and len(personas) >= limit:
                break
            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    persona_text = data.get("persona", "")
                    if persona_text:
                        personas.append((offset + len(personas), persona_text))
                except json.JSONDecodeError:
                    pass

    total = len(personas)
    print(f"Loaded {total} personas (offset={offset}, limit={limit})")
    print(f"Model: {model or 'default'}")
    print(f"Concurrency: {concurrency}")
    print(f"Worlds root: {worlds_root}")
    if max_generate is not None:
        print(f"Max generate per world: {max_generate}")
    print()

    # Thread-safe counters using a lock
    lock = anyio.Lock()
    succeeded = 0
    failed = 0
    skipped = 0
    completed = 0
    results = []

    sem = anyio.Semaphore(concurrency)

    async def process_one(line_num: int, persona_text: str):
        nonlocal succeeded, failed, completed, skipped

        world_id = f"world_{line_num:06d}"
        world_dir = os.path.join(worlds_root, world_id)

        # Skip already-completed worlds
        if os.path.exists(os.path.join(world_dir, "_complete")):
            async with lock:
                skipped += 1
                completed += 1
                print(f"[SKIP] {world_id} already complete. ({completed}/{total})")
            return

        async with sem:
            print(f"\n{'#' * 60}")
            print(f"# [START] Persona line {line_num} → {world_id}")
            print(f"# {persona_text[:100]}{'...' if len(persona_text) > 100 else ''}")
            print(f"{'#' * 60}\n")

            try:
                world_dir = await cold_start(
                    persona=persona_text,
                    world_id=world_id,
                    worlds_root=worlds_root,
                    max_generate=max_generate,
                    model=model,
                    plugins=plugins,
                )
                async with lock:
                    succeeded += 1
                    completed += 1
                    results.append({"world_id": world_id, "line": line_num, "status": "ok"})
                    print(f"\n[OK] {world_id} complete. Progress: {completed}/{total} done, {succeeded} ok, {failed} failed")
            except Exception as e:
                async with lock:
                    failed += 1
                    completed += 1
                    results.append({"world_id": world_id, "line": line_num, "status": "error", "error": str(e)})
                    print(f"\n[ERROR] {world_id} failed: {e}")
                    traceback.print_exc()
                    print(f"Progress: {completed}/{total} done, {succeeded} ok, {failed} failed")

    async with anyio.create_task_group() as tg:
        for line_num, persona_text in personas:
            tg.start_soon(process_one, line_num, persona_text)

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"Batch complete: {succeeded} succeeded, {failed} failed, {skipped} skipped out of {total}")
    print(f"{'=' * 60}")

    # Save results log
    log_path = os.path.join(worlds_root, "batch_log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        for r in results:
            r["timestamp"] = datetime.now().isoformat()
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Results appended to {log_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch Cold Start runner")
    parser.add_argument("--input", type=str, required=True, help="Path to personas JSONL file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of personas to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N personas")
    parser.add_argument("--worlds-root", type=str, default="worlds", help="Output directory")
    parser.add_argument("--max-generate", type=int, default=None, help="Max files to generate per world")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6", help="Claude model. Default: claude-sonnet-4-6")
    parser.add_argument("--plugins", type=str, nargs="*", default=None, help="Plugin directories")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent worlds to generate. Default: 5")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    plugins = None
    if args.plugins:
        plugins = [{"type": "local", "path": os.path.normpath(p)} for p in args.plugins]

    anyio.run(
        run_batch,
        args.input,
        args.limit,
        args.offset,
        args.worlds_root,
        args.max_generate,
        args.model,
        plugins,
        args.concurrency,
    )


if __name__ == "__main__":
    main()
