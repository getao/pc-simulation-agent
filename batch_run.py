"""
Batch runner — iterate over personas from a JSONL file and generate a UserWorld for each.

Each world runs as a separate subprocess (uv run python cold_start.py ...) with a
per-world timeout. If a world hangs, the subprocess tree is killed and the world
can be retried on the next run (resume support via _complete marker).

Usage:
    uv run python batch_run.py --input personas_subset_1k.jsonl
    uv run python batch_run.py --input personas_subset_1k.jsonl --limit 10
    uv run python batch_run.py --input personas_subset_1k.jsonl --limit 10 --offset 50
    uv run python batch_run.py --input personas_subset_1k.jsonl --max-generate 5
    uv run python batch_run.py --input personas_subset_1k.jsonl --concurrency 5
    uv run python batch_run.py --input personas_subset_1k.jsonl --timeout 3600
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime


def _load_personas(input_file: str, offset: int, limit: int | None) -> list[tuple[int, str]]:
    """Read personas from a JSONL file, applying offset and limit."""
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
    return personas


def _process_one(
    line_num: int,
    persona_text: str,
    worlds_root: str,
    prefix: str,
    model: str | None,
    max_generate: int | None,
    plugins: list[str] | None,
    timeout: int,
    counters: dict,
    lock: threading.Lock,
    total: int,
) -> dict:
    """Run cold_start for one world in a subprocess with timeout."""
    world_id = f"{prefix}_{line_num:06d}"
    world_dir = os.path.join(worlds_root, world_id)

    # Skip already-completed worlds
    if os.path.exists(os.path.join(world_dir, "_complete")):
        with lock:
            counters["skipped"] += 1
            counters["completed"] += 1
            print(f"[SKIP] {world_id} already complete. ({counters['completed']}/{total})")
        return {"world_id": world_id, "line": line_num, "status": "skipped"}

    # Write persona to a temp file in worlds_root
    os.makedirs(worlds_root, exist_ok=True)
    persona_file = os.path.join(worlds_root, f".persona_{world_id}.txt")
    with open(persona_file, "w", encoding="utf-8") as f:
        f.write(persona_text)

    # Build command
    cmd = [
        "uv", "run", "python", "cold_start.py",
        "--persona-file", persona_file,
        "--world-id", world_id,
        "--worlds-root", worlds_root,
    ]
    if model:
        cmd.extend(["--model", model])
    if max_generate is not None:
        cmd.extend(["--max-generate", str(max_generate)])
    if plugins:
        cmd.extend(["--plugins"] + plugins)

    print(f"[START] {world_id} (line {line_num}): {persona_text[:80]}{'...' if len(persona_text) > 80 else ''}")

    proc = None
    try:
        # Inherit stdout so tagged log lines appear in real time.
        # stderr is captured for error reporting.
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=subprocess.PIPE)
        proc.wait(timeout=timeout)

        if proc.returncode == 0:
            with lock:
                counters["succeeded"] += 1
                counters["completed"] += 1
                print(f"[OK] {world_id} complete. ({counters['completed']}/{total} done, "
                      f"{counters['succeeded']} ok, {counters['failed']} failed, "
                      f"{counters['timed_out']} timeout)")
            return {"world_id": world_id, "line": line_num, "status": "ok"}
        else:
            stderr = ""
            if proc.stderr:
                stderr = proc.stderr.read().decode(errors="replace")[-500:]
            with lock:
                counters["failed"] += 1
                counters["completed"] += 1
                print(f"[ERROR] {world_id} exit code {proc.returncode}. ({counters['completed']}/{total})")
                if stderr:
                    print(f"  stderr: {stderr}")
            return {"world_id": world_id, "line": line_num, "status": "error", "error": stderr}

    except subprocess.TimeoutExpired:
        # Kill the entire process tree
        if proc:
            try:
                subprocess.run(
                    f"taskkill /T /F /PID {proc.pid}",
                    shell=True, capture_output=True, timeout=15,
                )
            except Exception:
                proc.kill()
            proc.wait()
        with lock:
            counters["timed_out"] += 1
            counters["completed"] += 1
            print(f"[TIMEOUT] {world_id} killed after {timeout}s. ({counters['completed']}/{total})")
        return {"world_id": world_id, "line": line_num, "status": "timeout"}

    except Exception as e:
        with lock:
            counters["failed"] += 1
            counters["completed"] += 1
            print(f"[ERROR] {world_id}: {e}. ({counters['completed']}/{total})")
        return {"world_id": world_id, "line": line_num, "status": "error", "error": str(e)}

    finally:
        if os.path.exists(persona_file):
            os.unlink(persona_file)


def main():
    parser = argparse.ArgumentParser(description="Batch Cold Start runner")
    parser.add_argument("--input", type=str, required=True, help="Path to personas JSONL file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of personas to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N personas")
    parser.add_argument("--prefix", type=str, default="world",
                        help="World ID prefix. Default: world (produces world_000000, world_000001, ...)")
    parser.add_argument("--worlds-root", type=str, default="worlds", help="Output directory")
    parser.add_argument("--max-generate", type=int, default=None, help="Max files to generate per world")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6",
                        help="Claude model. Default: claude-sonnet-4-6")
    parser.add_argument("--plugins", type=str, nargs="*", default=None, help="Plugin directories")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="Number of concurrent worlds to generate. Default: 5")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="Per-world timeout in seconds. Default: 3600 (60 min)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    personas = _load_personas(args.input, args.offset, args.limit)
    total = len(personas)

    print(f"Loaded {total} personas (offset={args.offset}, limit={args.limit})")
    print(f"Model: {args.model or 'default'}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Per-world timeout: {args.timeout}s")
    print(f"Worlds root: {args.worlds_root}")
    if args.max_generate is not None:
        print(f"Max generate per world: {args.max_generate}")
    print()

    counters = {"succeeded": 0, "failed": 0, "skipped": 0, "timed_out": 0, "completed": 0}
    lock = threading.Lock()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {}
        for line_num, persona_text in personas:
            future = pool.submit(
                _process_one,
                line_num, persona_text,
                args.worlds_root, args.prefix, args.model, args.max_generate,
                args.plugins, args.timeout,
                counters, lock, total,
            )
            futures[future] = f"{args.prefix}_{line_num:06d}"

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"Batch complete: {counters['succeeded']} succeeded, {counters['failed']} failed, "
          f"{counters['timed_out']} timed out, {counters['skipped']} skipped out of {total}")
    print(f"{'=' * 60}")

    # Save results log
    log_path = os.path.join(args.worlds_root, "batch_log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        for r in results:
            r["timestamp"] = datetime.now().isoformat()
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Results appended to {log_path}")


if __name__ == "__main__":
    main()
