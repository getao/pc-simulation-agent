"""Cold Start pipeline orchestration.

Sequences Claude Code SDK calls to build a complete UserWorld from a persona.
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta

import anyio

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

from prompts import (
    build_user_profile_prompt,
    build_filesystem_policy_prompt,
    build_planning_prompt,
    build_file_generation_prompt,
)

# ---------------------------------------------------------------------------
# Claude Code SDK wrapper
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = {
    "type": "preset",
    "preset": "claude_code",
    "append": (
        "\n\nYou are building a simulated Windows PC filesystem environment. "
        "Follow instructions precisely. Write files exactly as specified. "
        "Output only what is requested — no explanations unless asked."
    ),
}


async def call_claude(
    prompt: str,
    cwd: str,
    max_turns: int = 10,
    plugins: list | None = None,
    model: str | None = None,
    log_file: str | None = None,
) -> str:
    """Call Claude Code CLI via the SDK and return collected text output.

    Args:
        log_file: If set, stream Claude Code output to this file instead of stdout.
    """
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        cwd=cwd,
        max_turns=max_turns,
    )
    if plugins:
        options.plugins = plugins
    if model:
        options.model = model

    output_parts: list[str] = []
    fh = open(log_file, "a", encoding="utf-8") if log_file else None

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        if fh:
                            fh.write(block.text)
                            fh.flush()
                        else:
                            print(block.text, end="", flush=True)
                        output_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                pass  # session ended
    finally:
        if fh:
            fh.write("\n")
            fh.close()

    if not fh:
        print()  # newline after streamed output
    return "".join(output_parts)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _read_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_user_profile(world_dir: str) -> dict:
    path = os.path.join(world_dir, "user_profile.json")
    if not os.path.exists(path):
        raise RuntimeError("user_profile.json was not created")
    data = _read_json(path)
    for key in ("identity", "work_context", "filesystem_relevant_traits"):
        if key not in data:
            raise RuntimeError(f"user_profile.json missing required key: {key}")
    return data


def _validate_filesystem_policy(world_dir: str, current_ts: str) -> dict:
    path = os.path.join(world_dir, "filesystem_policy.json")
    if not os.path.exists(path):
        raise RuntimeError("filesystem_policy.json was not created")
    data = _read_json(path)
    if "system_start_timestamp" not in data:
        raise RuntimeError("filesystem_policy.json missing system_start_timestamp")
    start = data["system_start_timestamp"]
    if start >= current_ts:
        raise RuntimeError(
            f"system_start_timestamp ({start}) must be before current_timestamp ({current_ts})"
        )
    return data


def _validate_planning(world_dir: str, current_ts: str, system_start_ts: str) -> tuple[dict, list, dict]:
    # project_index.json
    pi_path = os.path.join(world_dir, "project_index.json")
    if not os.path.exists(pi_path):
        raise RuntimeError("project_index.json was not created")
    project_index = _read_json(pi_path)

    # file_list.json
    fl_path = os.path.join(world_dir, "file_list.json")
    if not os.path.exists(fl_path):
        raise RuntimeError("file_list.json was not created")
    file_list = _read_json(fl_path)

    # Validate only originally planned entries (not extracted files added at runtime)
    planned = [f for f in file_list if not f.get("derived_from")]
    if len(planned) > 100:
        raise RuntimeError(f"file_list has {len(planned)} planned files, exceeds 100 limit")

    for entry in planned:
        ts = entry.get("timestamp", "")
        if not ts:
            continue
        if ts < system_start_ts:
            raise RuntimeError(
                f"File {entry['path']} timestamp {ts} is before system_start {system_start_ts}"
            )
        if ts > current_ts:
            raise RuntimeError(
                f"File {entry['path']} timestamp {ts} is after current_timestamp {current_ts}"
            )

    # file_graph.json
    fg_path = os.path.join(world_dir, "file_graph.json")
    if not os.path.exists(fg_path):
        raise RuntimeError("file_graph.json was not created")
    file_graph = _read_json(fg_path)

    return project_index, file_list, file_graph


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def _create_directories(world_dir: str, file_list: list[dict]) -> None:
    """Create all directories needed for the files in file_list."""
    drives_dir = os.path.join(world_dir, "drives")
    for entry in file_list:
        logical_path = entry["path"]  # e.g. "C:/Users/alice/Documents/file.docx"
        # Convert to physical: drives/C/Users/alice/Documents/file.docx
        parts = logical_path.split(":/", 1)
        if len(parts) != 2:
            continue
        drive_letter, rest = parts
        physical_path = os.path.join(drives_dir, drive_letter, rest)
        parent_dir = os.path.dirname(physical_path)
        os.makedirs(parent_dir, exist_ok=True)


# ---------------------------------------------------------------------------
# File generation batching
# ---------------------------------------------------------------------------

def _batch_files(file_list: list[dict], batch_size: int = 3) -> list[list[dict]]:
    """Split sorted file list into batches."""
    sorted_files = sorted(file_list, key=lambda f: f["timestamp"])
    batches = []
    for i in range(0, len(sorted_files), batch_size):
        batches.append(sorted_files[i : i + batch_size])
    return batches


def _get_recent_activity_log(world_dir: str, n: int = 20) -> list[dict]:
    """Read the most recent n entries from activity_log.jsonl."""
    path = os.path.join(world_dir, "activity_log.jsonl")
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-n:]


def _get_relevant_edges(file_graph: dict, batch_paths: set[str]) -> list[dict]:
    """Get file_graph edges relevant to the current batch of files."""
    edges = file_graph.get("edges", [])
    return [
        e for e in edges
        if e.get("from") in batch_paths or e.get("to") in batch_paths
    ]


def _build_user_summary(profile: dict) -> str:
    """Build a concise user summary for file generation context."""
    identity = profile.get("identity", {})
    bio = profile.get("biographical_summary", {}).get("short_bio", "")
    return (
        f"{identity.get('full_name', 'Unknown')} — "
        f"{identity.get('role', 'Unknown role')} at "
        f"{identity.get('organization', 'Unknown org')}. {bio}"
    )


def _mark_generated(world_dir: str, batch: list[dict]) -> None:
    """Mark files in file_list.json as content_generated=true."""
    fl_path = os.path.join(world_dir, "file_list.json")
    file_list = _read_json(fl_path)
    generated_paths = {entry["path"] for entry in batch}
    for entry in file_list:
        if entry["path"] in generated_paths:
            entry["content_generated"] = True
    with open(fl_path, "w", encoding="utf-8") as f:
        json.dump(file_list, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def cold_start(
    persona: str,
    current_timestamp: str | None = None,
    world_id: str | None = None,
    plugins: list | None = None,
    worlds_root: str = "worlds",
    max_generate: int | None = None,
    model: str | None = None,
) -> str:
    """Run the full Cold Start pipeline. Returns the world directory path.

    Args:
        max_generate: If set, only generate content for the first N files
                      (planning steps still produce the full file list).
        model: Claude model to use (e.g. "claude-sonnet-4-6"). Default: SDK default.
    """

    if current_timestamp is None:
        current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if world_id is None:
        world_id = uuid.uuid4().hex[:12]

    world_dir = os.path.join(worlds_root, world_id)
    os.makedirs(world_dir, exist_ok=True)

    # Save persona
    persona_path = os.path.join(world_dir, "persona.json")
    with open(persona_path, "w", encoding="utf-8") as f:
        json.dump({"persona": persona, "current_timestamp": current_timestamp}, f, indent=2, ensure_ascii=False)

    log_file = os.path.join(world_dir, "output.log")
    tag = f"[{world_id}]"

    def log(msg: str):
        elapsed = time.monotonic() - t0
        m, s = divmod(int(elapsed), 60)
        print(f"{tag} [{m:02d}:{s:02d}] {msg}", flush=True)

    t0 = time.monotonic()
    log(f"Cold Start started. dir={world_dir} ts={current_timestamp}")

    # ------------------------------------------------------------------
    # Check for resumable state
    # ------------------------------------------------------------------
    resuming = False
    planning_files = ["user_profile.json", "filesystem_policy.json",
                      "project_index.json", "file_list.json", "file_graph.json"]
    if all(os.path.exists(os.path.join(world_dir, f)) for f in planning_files):
        try:
            profile = _validate_user_profile(world_dir)
            policy = _validate_filesystem_policy(world_dir, current_timestamp)
            system_start_ts = policy["system_start_timestamp"]
            project_index, file_list, file_graph = _validate_planning(
                world_dir, current_timestamp, system_start_ts
            )
            resuming = True
            already_done = sum(1 for f in file_list if f.get("content_generated"))
            log(f"RESUME: {already_done}/{len(file_list)} files already generated.")
        except Exception as e:
            log(f"RESUME: Existing data invalid ({e}), re-running from scratch.")
            resuming = False

    if not resuming:
        # --------------------------------------------------------------
        # Step 1: Persona → User Profile
        # --------------------------------------------------------------
        log("Step 1: Generating User Profile...")
        prompt = build_user_profile_prompt(persona)
        await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins, model=model, log_file=log_file)
        profile = _validate_user_profile(world_dir)
        log("Step 1 done: user_profile.json created.")

        # --------------------------------------------------------------
        # Step 2: User Profile → Filesystem Policy
        # --------------------------------------------------------------
        log("Step 2: Generating Filesystem Policy...")
        profile_json = json.dumps(profile, indent=2, ensure_ascii=False)

        # Generate random system_start_timestamp in 2020-2025
        start_range = datetime(2020, 1, 1)
        end_range = datetime(2025, 12, 31)
        random_days = random.randint(0, (end_range - start_range).days)
        random_hour = random.randint(7, 20)
        random_minute = random.randint(0, 59)
        system_start = start_range + timedelta(days=random_days)
        system_start = system_start.replace(hour=random_hour, minute=random_minute, second=0)
        system_start_ts = system_start.strftime("%Y-%m-%dT%H:%M:%S")

        prompt = build_filesystem_policy_prompt(profile_json, current_timestamp, system_start_ts)
        await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins, model=model, log_file=log_file)
        policy = _validate_filesystem_policy(world_dir, current_timestamp)
        log(f"Step 2 done: filesystem_policy.json created. system_start={system_start_ts}")

        # --------------------------------------------------------------
        # Step 3: Joint Planning
        # --------------------------------------------------------------
        log("Step 3: Planning Projects, Files, and File Graph...")
        policy_json = json.dumps(policy, indent=2, ensure_ascii=False)
        profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
        prompt = build_planning_prompt(profile_json, policy_json, current_timestamp)
        await call_claude(prompt, cwd=world_dir, max_turns=15, plugins=plugins, model=model, log_file=log_file)
        system_start_ts = policy["system_start_timestamp"]
        project_index, file_list, file_graph = _validate_planning(
            world_dir, current_timestamp, system_start_ts
        )
        log(f"Step 3 done: {len(file_list)} files planned.")

    # ------------------------------------------------------------------
    # Step 4: Create Directory Structure
    # ------------------------------------------------------------------
    _create_directories(world_dir, file_list)
    log("Step 4 done: directories created.")

    # ------------------------------------------------------------------
    # Step 5: Generate File Contents (batched)
    # ------------------------------------------------------------------
    profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
    user_summary = _build_user_summary(profile)

    # Filter out already-generated files
    sorted_files = sorted(file_list, key=lambda f: f["timestamp"])
    remaining_files = [f for f in sorted_files if not f.get("content_generated")]

    if remaining_files and len(remaining_files) < len(sorted_files):
        log(f"Step 5: Skipping {len(sorted_files) - len(remaining_files)} already-generated, {len(remaining_files)} remaining.")

    # Apply max_generate limit
    if max_generate is not None:
        files_to_generate = remaining_files[:max_generate]
        skipped_count = len(remaining_files) - len(files_to_generate)
        log(f"Step 5 [dry-run]: generating {len(files_to_generate)}/{len(remaining_files)} files (skipping {skipped_count})")
    else:
        files_to_generate = remaining_files

    batches = _batch_files(files_to_generate)

    for i, batch in enumerate(batches, 1):
        paths = ", ".join(os.path.basename(e["path"]) for e in batch)
        log(f"Step 5: Batch {i}/{len(batches)} ({len(batch)} files: {paths})")

        activity_log = _get_recent_activity_log(world_dir)
        batch_paths = {entry["path"] for entry in batch}
        relevant_edges = _get_relevant_edges(file_graph, batch_paths)

        prompt = build_file_generation_prompt(
            batch=batch,
            activity_log_entries=activity_log,
            file_graph_edges=relevant_edges,
            user_profile_summary=user_summary,
            world_root=world_dir,
        )
        await call_claude(prompt, cwd=world_dir, max_turns=500, plugins=plugins, model=model, log_file=log_file)
        _mark_generated(world_dir, batch)
        log(f"Step 5: Batch {i}/{len(batches)} done.")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    final_file_list = _read_json(os.path.join(world_dir, "file_list.json"))
    generated = sum(1 for f in final_file_list if f.get("content_generated"))

    activity_count = 0
    al_path = os.path.join(world_dir, "activity_log.jsonl")
    if os.path.exists(al_path):
        with open(al_path, "r", encoding="utf-8") as f:
            activity_count = sum(1 for line in f if line.strip())

    # Write completion marker
    with open(os.path.join(world_dir, "_complete"), "w") as f:
        f.write(datetime.now().isoformat() + "\n")

    log(f"COMPLETE: {generated}/{len(final_file_list)} files generated, {activity_count} activity log entries.")

    return world_dir
