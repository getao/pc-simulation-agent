"""Cold Start pipeline orchestration.

Sequences Claude Code SDK calls to build a complete UserWorld from a persona.
"""

import json
import os
import uuid
from datetime import datetime

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
) -> str:
    """Call Claude Code CLI via the SDK and return collected text output."""
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        cwd=cwd,
        max_turns=max_turns,
    )
    if plugins:
        options.plugins = plugins

    output_parts: list[str] = []

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
                    output_parts.append(block.text)
        elif isinstance(message, ResultMessage):
            pass  # session ended

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

    if len(file_list) > 100:
        raise RuntimeError(f"file_list has {len(file_list)} files, exceeds 100 limit")

    # Validate timestamps
    for entry in file_list:
        ts = entry.get("timestamp", "")
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
) -> str:
    """Run the full Cold Start pipeline. Returns the world directory path.

    Args:
        max_generate: If set, only generate content for the first N files
                      (planning steps still produce the full file list).
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

    print(f"=== Cold Start: {world_id} ===")
    print(f"World dir: {world_dir}")
    print(f"Timestamp: {current_timestamp}")
    print()

    # ------------------------------------------------------------------
    # Step 1: Persona → User Profile
    # ------------------------------------------------------------------
    print("=" * 60)
    print("STEP 1: Generating User Profile...")
    print("=" * 60)
    prompt = build_user_profile_prompt(persona)
    await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins)
    profile = _validate_user_profile(world_dir)
    print("\n[OK] user_profile.json created and validated.\n")

    # ------------------------------------------------------------------
    # Step 2: User Profile → Filesystem Policy
    # ------------------------------------------------------------------
    print("=" * 60)
    print("STEP 2: Generating Filesystem Policy...")
    print("=" * 60)
    profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
    prompt = build_filesystem_policy_prompt(profile_json, current_timestamp)
    await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins)
    policy = _validate_filesystem_policy(world_dir, current_timestamp)
    system_start_ts = policy["system_start_timestamp"]
    print(f"\n[OK] filesystem_policy.json created. System start: {system_start_ts}\n")

    # ------------------------------------------------------------------
    # Step 3: Joint Planning
    # ------------------------------------------------------------------
    print("=" * 60)
    print("STEP 3: Planning Projects, Files, and File Graph...")
    print("=" * 60)
    policy_json = json.dumps(policy, indent=2, ensure_ascii=False)
    prompt = build_planning_prompt(profile_json, policy_json, current_timestamp)
    await call_claude(prompt, cwd=world_dir, max_turns=15, plugins=plugins)
    project_index, file_list, file_graph = _validate_planning(
        world_dir, current_timestamp, system_start_ts
    )
    print(f"\n[OK] Planning complete. {len(file_list)} files planned.\n")

    # ------------------------------------------------------------------
    # Step 4: Create Directory Structure
    # ------------------------------------------------------------------
    print("=" * 60)
    print("STEP 4: Creating directory structure...")
    print("=" * 60)
    _create_directories(world_dir, file_list)
    print("[OK] Directories created.\n")

    # ------------------------------------------------------------------
    # Step 5: Generate File Contents (batched)
    # ------------------------------------------------------------------
    print("=" * 60)
    print("STEP 5: Generating file contents...")
    print("=" * 60)

    user_summary = _build_user_summary(profile)

    # Apply max_generate limit
    sorted_files = sorted(file_list, key=lambda f: f["timestamp"])
    if max_generate is not None:
        files_to_generate = sorted_files[:max_generate]
        skipped = len(sorted_files) - len(files_to_generate)
        print(f"[dry-run] Generating only {len(files_to_generate)}/{len(sorted_files)} files (skipping {skipped})")
    else:
        files_to_generate = sorted_files

    batches = _batch_files(files_to_generate)

    for i, batch in enumerate(batches, 1):
        print(f"\n--- Batch {i}/{len(batches)} ({len(batch)} files) ---")
        for entry in batch:
            print(f"  {entry['content_mode']:>8}  {entry['path']}")

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
        await call_claude(prompt, cwd=world_dir, max_turns=500, plugins=plugins)
        _mark_generated(world_dir, batch)
        print(f"\n[OK] Batch {i} complete.")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print(f"Cold Start complete: {world_dir}")
    print("=" * 60)

    # Summary
    final_file_list = _read_json(os.path.join(world_dir, "file_list.json"))
    generated = sum(1 for f in final_file_list if f.get("content_generated"))
    print(f"Files planned: {len(final_file_list)}")
    print(f"Files generated: {generated}")

    activity_count = 0
    al_path = os.path.join(world_dir, "activity_log.jsonl")
    if os.path.exists(al_path):
        with open(al_path, "r", encoding="utf-8") as f:
            activity_count = sum(1 for line in f if line.strip())
    print(f"Activity log entries: {activity_count}")

    return world_dir
