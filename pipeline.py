"""Cold Start pipeline orchestration.

Sequences Claude Code SDK calls to build a complete UserWorld from a persona.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta

import anyio

import re

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ThinkingBlock,
    ResultMessage,
    PermissionResultAllow,
    PermissionResultDeny,
    tool as sdk_tool,
    create_sdk_mcp_server,
)

from prompts import (
    build_user_profile_prompt,
    build_filesystem_policy_prompt,
    build_planning_prompt,
    build_file_generation_prompt,
)

from daily_prompts import (
    build_monthly_objectives_prompt,
    build_ref_files_prompt,
    build_workspace_prereqs_prompt,
    build_weekly_plan_prompt,
    build_daily_file_generation_prompt,
    build_persona_response_prompt,
    build_evaluation_prompt,
    strip_personas_for_main_agent,
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
        "Output only what is requested — no explanations unless asked.\n\n"
        "## PATH RULE (applies to ALL file operations)\n"
        "Your current working directory (cwd) IS the world directory. "
        "All file paths MUST be RELATIVE to cwd, starting with `drives/`. "
        "For example: `drives/C/Users/alice/Documents/report.docx`.\n"
        "NEVER use absolute paths such as `/mnt/d/...`, `/d/...`, `/home/...`, "
        "`C:/...`, `D:/...`, or any path that does NOT start with `drives/`. "
        "This rule applies everywhere: Write tool file_path, Bash commands, "
        "and inside any Python/JS scripts you generate.\n\n"
        "## PRE-INSTALLED PACKAGES (already available — do NOT reinstall)\n"
        "Python: openpyxl, reportlab, python-docx, python-pptx\n"
        "Node.js (in cwd): docx, pptxgenjs (require via `require('docx')` etc.)\n"
        "Skip any `pip install` or `npm install` steps for these packages."
    ),
}

# Regex: bare Windows drive letter path (C:/ D:/ etc.) NOT preceded by "drives/"
_BARE_DRIVE_RE = re.compile(r'(?<!/)\b[A-Z]:[/\\]')


def _make_path_guard(allowed_dir: str):
    """Return a can_use_tool callback that blocks writes outside allowed_dir."""
    allowed_prefix = os.path.normcase(os.path.abspath(allowed_dir)) + os.sep

    async def _guard(tool_name, tool_input, _context):
        # Guard Write / Edit — check file_path
        if tool_name in ("Write", "Edit", "NotebookEdit"):
            file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
            abs_path = os.path.normcase(os.path.abspath(file_path))
            if not abs_path.startswith(allowed_prefix):
                return PermissionResultDeny(
                    message=f"BLOCKED: path {file_path} is outside allowed directory {allowed_dir}"
                )

        # Guard Bash — reject commands containing bare drive-letter paths
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if _BARE_DRIVE_RE.search(command):
                return PermissionResultDeny(
                    message=f"BLOCKED: command contains a bare Windows drive path. "
                            f"Use drives/C/ or drives/D/ instead."
                )

        return PermissionResultAllow()

    return _guard


_STRAY_DIRS = ["mnt", "d", "home"]


def _cleanup_stray_files(world_dir: str, log_fn=None):
    """Remove stray directories created by Git Bash path confusion.

    Claude Code on Git Bash sometimes writes to /mnt/d/..., /d/..., /home/...
    which end up as D:\\mnt, D:\\d, D:\\home on Windows.
    """
    drive = os.path.splitdrive(os.path.abspath(world_dir))[0]  # e.g. "D:"
    removed = 0
    for dirname in _STRAY_DIRS:
        stray = os.path.join(drive + os.sep, dirname)
        if os.path.isdir(stray):
            try:
                count = sum(len(files) for _, _, files in os.walk(stray))
                shutil.rmtree(stray)
                removed += count
                if log_fn:
                    log_fn(f"CLEANUP: removed {stray} ({count} files)")
            except Exception as e:
                if log_fn:
                    log_fn(f"CLEANUP: failed to remove {stray}: {e}")
    return removed


async def _as_stream(text: str):
    """Wrap a string prompt as an async iterable (required for can_use_tool)."""
    yield {"type": "user", "message": {"role": "user", "content": text}}


def _truncate(s: str, max_len: int = 200) -> str:
    """Truncate a string for logging."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"...({len(s)} chars)"


async def call_claude(
    prompt: str,
    cwd: str,
    max_turns: int = 10,
    plugins: list | None = None,
    model: str | None = None,
    mcp_servers: dict | None = None,
    log_file: str | None = None,
    turn_log_file: str | None = None,
    step_label: str = "",
) -> dict:
    """Call Claude Code CLI via the SDK and return result info.

    Returns a dict with keys: text, cost_usd, usage, duration_ms, num_turns.

    Args:
        mcp_servers: Optional MCP server configs to register with the agent.
        log_file: If set, stream Claude Code output to this file instead of stdout.
        turn_log_file: If set, write per-turn diagnostic JSONL to this file.
        step_label: Label for this session in the turn log (e.g. "step6", "step6.5_ext_tyler").
    """
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        cwd=cwd,
        max_turns=max_turns,
        can_use_tool=_make_path_guard(cwd),
    )
    if plugins:
        options.plugins = plugins
    if model:
        options.model = model
    if mcp_servers:
        options.mcp_servers = mcp_servers

    output_parts: list[str] = []
    result_info: dict = {}
    fh = open(log_file, "a", encoding="utf-8") if log_file else None
    turn_fh = open(turn_log_file, "a", encoding="utf-8") if turn_log_file else None
    if turn_fh and step_label:
        turn_fh.write(json.dumps({"type": "session_start", "step": step_label, "max_turns": max_turns}) + "\n")
        turn_fh.flush()

    turn_num = 0
    turn_t0 = time.monotonic()

    try:
        async for message in query(prompt=_as_stream(prompt), options=options):
            if isinstance(message, AssistantMessage):
                turn_num += 1
                now = time.monotonic()
                turn_elapsed = round(now - turn_t0, 1)
                turn_t0 = now

                # Collect block summaries
                tool_calls = []
                text_len = 0
                thinking_len = 0
                for block in message.content:
                    if isinstance(block, TextBlock):
                        if fh:
                            fh.write(block.text)
                            fh.flush()
                        else:
                            print(block.text, end="", flush=True)
                        output_parts.append(block.text)
                        text_len += len(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_input = block.input or {}
                        # Summarize tool input
                        if block.name in ("Write", "Edit"):
                            summary = {
                                "file_path": tool_input.get("file_path", ""),
                                "content_len": len(tool_input.get("content", "")),
                            }
                        elif block.name == "Read":
                            summary = {"file_path": tool_input.get("file_path", "")}
                        elif block.name == "Bash":
                            summary = {"command": _truncate(tool_input.get("command", ""), 300)}
                        elif block.name == "Glob":
                            summary = {"pattern": tool_input.get("pattern", "")}
                        elif block.name == "Grep":
                            summary = {
                                "pattern": tool_input.get("pattern", ""),
                                "path": tool_input.get("path", ""),
                            }
                        elif block.name == "WebSearch":
                            summary = {"query": tool_input.get("query", "")}
                        else:
                            summary = {k: _truncate(str(v)) for k, v in list(tool_input.items())[:3]}
                        tool_calls.append({"tool": block.name, **summary})
                    elif isinstance(block, ThinkingBlock):
                        thinking_len += len(block.thinking or "")

                # Write turn log entry
                if turn_fh:
                    entry = {
                        "turn": turn_num,
                        "elapsed_s": turn_elapsed,
                        "model": message.model,
                        "tool_calls": tool_calls,
                        "text_len": text_len,
                        "thinking_len": thinking_len,
                    }
                    turn_fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    turn_fh.flush()

            elif isinstance(message, ResultMessage):
                result_info = {
                    "cost_usd": message.total_cost_usd or 0.0,
                    "usage": message.usage or {},
                    "duration_ms": message.duration_ms,
                    "duration_api_ms": message.duration_api_ms,
                    "num_turns": message.num_turns,
                    "session_id": message.session_id,
                }
                if turn_fh:
                    turn_fh.write(json.dumps({
                        "type": "result",
                        "num_turns": message.num_turns,
                        "cost_usd": message.total_cost_usd,
                        "duration_ms": message.duration_ms,
                        "duration_api_ms": message.duration_api_ms,
                        "usage": message.usage,
                    }, ensure_ascii=False) + "\n")
                    turn_fh.flush()
    finally:
        if fh:
            fh.write("\n")
            fh.close()
        if turn_fh:
            turn_fh.close()

    if not fh:
        print()  # newline after streamed output
    result_info["text"] = "".join(output_parts)
    return result_info


# ---------------------------------------------------------------------------
# Dependency pre-installation
# ---------------------------------------------------------------------------

# Packages that Claude Code subprocess sessions commonly need.
# Pre-installing them avoids repeated `pip install` / `npm install` in every
# call_claude session, saving significant wall-clock time.

# (pip_name, import_name)
_PYTHON_PACKAGES = [
    ("openpyxl", "openpyxl"),       # .xlsx generation
    ("reportlab", "reportlab"),     # .pdf generation
    ("python-docx", "docx"),        # .docx generation
    ("python-pptx", "pptx"),        # .pptx generation
]

_NPM_PACKAGES = {
    "docx": "^9.6.1",        # .docx generation (Node)
    "pptxgenjs": "^4.0.1",   # .pptx generation (Node)
}


def _ensure_dependencies(world_dir: str, log_fn=None):
    """Pre-install Python and Node.js packages into the world directory.

    - Python packages: installed via pip into the system/venv (idempotent).
    - Node packages: installs into world_dir/node_modules via package.json.

    Skips if already satisfied.
    """
    log = log_fn or (lambda msg: print(msg, flush=True))

    # --- Python packages ---
    # Check which ones are missing
    missing_py = []
    for pip_name, import_name in _PYTHON_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing_py.append(pip_name)

    if missing_py:
        log(f"Pre-installing Python packages: {', '.join(missing_py)}")
        subprocess.run(
            ["uv", "pip", "install", "--quiet"] + missing_py,
            check=True, capture_output=True,
        )
    else:
        log("Python packages already installed.")

    # --- Node.js packages ---
    pkg_json_path = os.path.join(world_dir, "package.json")
    node_modules = os.path.join(world_dir, "node_modules")

    # Write package.json if missing or outdated
    need_npm = False
    if os.path.exists(pkg_json_path):
        existing = json.loads(open(pkg_json_path, "r").read())
        existing_deps = existing.get("dependencies", {})
        if all(k in existing_deps for k in _NPM_PACKAGES):
            # Check node_modules exists
            if os.path.isdir(node_modules):
                log("Node packages already installed.")
            else:
                need_npm = True
        else:
            # Merge in any missing packages
            existing_deps.update(_NPM_PACKAGES)
            existing["dependencies"] = existing_deps
            with open(pkg_json_path, "w") as f:
                json.dump(existing, f, indent=2)
            need_npm = True
    else:
        with open(pkg_json_path, "w") as f:
            json.dump({"dependencies": _NPM_PACKAGES}, f, indent=2)
        need_npm = True

    if need_npm:
        log(f"Pre-installing Node packages: {', '.join(_NPM_PACKAGES.keys())}")
        subprocess.run(
            ["npm", "install"],
            cwd=world_dir, check=True, capture_output=True, shell=True,
        )
    log("Dependency pre-installation complete.")


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


def _logical_to_physical(world_dir: str, logical_path: str) -> str:
    """Convert logical path (C:/Users/...) to physical path (world_dir/drives/C/Users/...)."""
    parts = logical_path.split(":/", 1)
    if len(parts) != 2:
        return ""
    drive, rest = parts
    return os.path.join(world_dir, "drives", drive, rest)


def _verify_batch(world_dir: str, batch: list[dict], log_fn=None) -> list[str]:
    """Check that batch files exist at their expected physical paths.

    Returns list of logical paths that are missing.
    """
    missing = []
    for entry in batch:
        logical = entry["path"]
        physical = _logical_to_physical(world_dir, logical)
        if not physical:
            continue
        if os.path.exists(physical):
            if log_fn:
                log_fn(f"  OK: {logical}")
        else:
            missing.append(logical)
            if log_fn:
                log_fn(f"  MISSING: {logical}")
    return missing


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

    world_dir = os.path.abspath(os.path.join(worlds_root, world_id))
    os.makedirs(world_dir, exist_ok=True)

    # Save persona
    persona_path = os.path.join(world_dir, "persona.json")
    with open(persona_path, "w", encoding="utf-8") as f:
        json.dump({"persona": persona, "current_timestamp": current_timestamp}, f, indent=2, ensure_ascii=False)

    log_file = os.path.join(world_dir, "output.log")
    turn_log_file = os.path.join(world_dir, "turns.jsonl")
    tag = f"[{world_id}]"

    def log(msg: str):
        elapsed = time.monotonic() - t0
        m, s = divmod(int(elapsed), 60)
        print(f"{tag} [{m:02d}:{s:02d}] {msg}", flush=True)

    t0 = time.monotonic()
    log(f"Cold Start started. dir={world_dir} ts={current_timestamp}")

    # Pre-install common dependencies so subprocess sessions don't waste time
    _ensure_dependencies(world_dir, log_fn=log)

    # Usage tracking
    total_cost_usd = 0.0
    total_turns = 0
    total_usage: dict = {}

    def _save_usage():
        """Save current usage stats to usage.json (called after each step)."""
        elapsed_s = time.monotonic() - t0
        usage_summary = {
            "total_cost_usd": round(total_cost_usd, 4),
            "total_turns": total_turns,
            "total_duration_s": round(elapsed_s, 1),
            "usage": total_usage,
        }
        with open(os.path.join(world_dir, "usage.json"), "w", encoding="utf-8") as f:
            json.dump(usage_summary, f, indent=2, ensure_ascii=False)

    def _accumulate(result: dict):
        nonlocal total_cost_usd, total_turns, total_usage
        total_cost_usd += result.get("cost_usd", 0.0)
        total_turns += result.get("num_turns", 0)
        usage = result.get("usage", {})
        for k, v in usage.items():
            if isinstance(v, (int, float)):
                total_usage[k] = total_usage.get(k, 0) + v
        _save_usage()

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
        _accumulate(await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins, model=model, log_file=log_file, turn_log_file=turn_log_file, step_label="step1_user_profile"))
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
        _accumulate(await call_claude(prompt, cwd=world_dir, max_turns=5, plugins=plugins, model=model, log_file=log_file, turn_log_file=turn_log_file, step_label="step2_fs_policy"))
        policy = _validate_filesystem_policy(world_dir, current_timestamp)
        log(f"Step 2 done: filesystem_policy.json created. system_start={system_start_ts}")

        # --------------------------------------------------------------
        # Step 3: Joint Planning
        # --------------------------------------------------------------
        log("Step 3: Planning Projects, Files, and File Graph...")
        policy_json = json.dumps(policy, indent=2, ensure_ascii=False)
        profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
        prompt = build_planning_prompt(profile_json, policy_json, current_timestamp)
        _accumulate(await call_claude(prompt, cwd=world_dir, max_turns=15, plugins=plugins, model=model, log_file=log_file, turn_log_file=turn_log_file, step_label="step3_planning"))
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
        _accumulate(await call_claude(prompt, cwd=world_dir, max_turns=500, plugins=plugins, model=model, log_file=log_file, turn_log_file=turn_log_file, step_label=f"step5_batch{i}"))
        _cleanup_stray_files(world_dir, log_fn=log)
        missing = _verify_batch(world_dir, batch, log_fn=log)
        _mark_generated(world_dir, batch)
        if missing:
            log(f"Step 5: Batch {i}/{len(batches)} done. WARNING: {len(missing)} files missing.")
        else:
            log(f"Step 5: Batch {i}/{len(batches)} done. All {len(batch)} files verified.")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    final_file_list = _read_json(os.path.join(world_dir, "file_list.json"))
    generated = sum(1 for f in final_file_list if f.get("content_generated"))

    # Final verification: remove missing files from file_list and file_graph
    verified = 0
    all_missing = set()
    for entry in final_file_list:
        if not entry.get("content_generated"):
            continue
        physical = _logical_to_physical(world_dir, entry["path"])
        if physical and os.path.exists(physical):
            verified += 1
        else:
            all_missing.add(entry["path"])

    if all_missing:
        log(f"PRUNE: {len(all_missing)} files missing on disk, removing from file_list/file_graph: {list(all_missing)[:10]}")

        # Prune file_list.json
        fl_path = os.path.join(world_dir, "file_list.json")
        final_file_list = [e for e in final_file_list if e["path"] not in all_missing]
        with open(fl_path, "w", encoding="utf-8") as f:
            json.dump(final_file_list, f, indent=2, ensure_ascii=False)

        # Prune file_graph.json
        fg_path = os.path.join(world_dir, "file_graph.json")
        if os.path.exists(fg_path):
            file_graph_data = _read_json(fg_path)
            file_graph_data["nodes"] = [
                n for n in file_graph_data.get("nodes", [])
                if n.get("path") not in all_missing
            ]
            file_graph_data["edges"] = [
                e for e in file_graph_data.get("edges", [])
                if e.get("from") not in all_missing and e.get("to") not in all_missing
            ]
            with open(fg_path, "w", encoding="utf-8") as f:
                json.dump(file_graph_data, f, indent=2, ensure_ascii=False)

    generated = sum(1 for f in final_file_list if f.get("content_generated"))

    activity_count = 0
    al_path = os.path.join(world_dir, "activity_log.jsonl")
    if os.path.exists(al_path):
        with open(al_path, "r", encoding="utf-8") as f:
            activity_count = sum(1 for line in f if line.strip())

    # Write completion marker and final usage
    _save_usage()
    with open(os.path.join(world_dir, "_complete"), "w") as f:
        f.write(datetime.now().isoformat() + "\n")

    usage_str = ", ".join(f"{k}={v}" for k, v in total_usage.items())
    log(f"COMPLETE: {generated}/{len(final_file_list)} files, {verified} verified on disk, {activity_count} activities. Cost: ${total_cost_usd:.4f}, turns: {total_turns}, {usage_str}")

    return world_dir


# ---------------------------------------------------------------------------
# Daily Simulation pipeline
# ---------------------------------------------------------------------------

def _read_jsonl(path: str) -> list[dict]:
    """Read all entries from a JSONL file."""
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
    return entries


def _get_all_activity_log(world_dir: str) -> list[dict]:
    """Read ALL entries from activity_log.jsonl (Cold Start only)."""
    return _read_jsonl(os.path.join(world_dir, "activity_log.jsonl"))


def _get_all_daily_activity_log(world_dir: str) -> list[dict]:
    """Read ALL entries from both activity logs (Cold Start + Daily Sim)."""
    cs = _read_jsonl(os.path.join(world_dir, "activity_log.jsonl"))
    ds = _read_jsonl(os.path.join(world_dir, "daily_activity_log.jsonl"))
    return cs + ds


def _read_file_as_text(filepath: str, max_chars: int = 10000) -> str:
    """Read a file as text, returning empty string on failure."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        return content
    except Exception:
        return ""


async def daily_simulate(
    world_dir: str,
    start_date: str | None = None,
    num_weeks: int = 4,
    plugins: list | None = None,
    model: str | None = None,
    real_world_context: str = "",
    plan_only: bool = False,
) -> str:
    """Run the Daily Simulation pipeline on an existing Cold Start world.

    Steps:
        6   — Monthly objectives + external personas planning
        6.5 — Generate external persona reference files + workspace prerequisites
        7   — Weekly day-by-day planning (per week)
        8   — Daily file generation (per week)

    Returns the world directory path.
    """
    world_dir = os.path.abspath(world_dir)
    world_id = os.path.basename(world_dir)
    log_file = os.path.join(world_dir, "daily_sim_output.log")
    turn_log_file = os.path.join(world_dir, "daily_sim_turns.jsonl")

    tag = f"[{world_id}]"
    t0 = time.monotonic()

    def log(msg: str):
        elapsed = time.monotonic() - t0
        m, s = divmod(int(elapsed), 60)
        print(f"{tag} [{m:02d}:{s:02d}] {msg}", flush=True)

    # Validate Cold Start is complete
    if not os.path.exists(os.path.join(world_dir, "_complete")):
        raise RuntimeError(f"World {world_dir} has not completed Cold Start.")

    # Load Cold Start outputs
    profile = _read_json(os.path.join(world_dir, "user_profile.json"))
    project_index = _read_json(os.path.join(world_dir, "project_index.json"))
    file_list = _read_json(os.path.join(world_dir, "file_list.json"))
    file_graph = _read_json(os.path.join(world_dir, "file_graph.json"))

    user_summary = _build_user_summary(profile)
    profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
    project_index_json = json.dumps(project_index, indent=2, ensure_ascii=False)
    file_list_json = json.dumps(file_list, indent=2, ensure_ascii=False)

    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")

    log(f"Daily Simulation started. start_date={start_date}, weeks={num_weeks}")

    # Pre-install common dependencies so subprocess sessions don't waste time
    _ensure_dependencies(world_dir, log_fn=log)

    # Usage tracking
    total_cost_usd = 0.0
    total_turns = 0
    total_usage: dict = {}

    def _save_usage():
        elapsed_s = time.monotonic() - t0
        usage_summary = {
            "daily_sim_cost_usd": round(total_cost_usd, 4),
            "daily_sim_turns": total_turns,
            "daily_sim_duration_s": round(elapsed_s, 1),
            "daily_sim_usage": total_usage,
        }
        usage_path = os.path.join(world_dir, "daily_sim_usage.json")
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(usage_summary, f, indent=2, ensure_ascii=False)

    def _accumulate_ds(result: dict):
        nonlocal total_cost_usd, total_turns, total_usage
        total_cost_usd += result.get("cost_usd", 0.0)
        total_turns += result.get("num_turns", 0)
        usage = result.get("usage", {})
        for k, v in usage.items():
            if isinstance(v, (int, float)):
                total_usage[k] = total_usage.get(k, 0) + v
        _save_usage()

    # ==================================================================
    # Step 6: Monthly Objectives + External Personas
    # ==================================================================
    objectives_path = os.path.join(world_dir, "monthly_objectives.json")
    external_ctx_path = os.path.join(world_dir, "external_context.json")

    if os.path.exists(objectives_path) and os.path.exists(external_ctx_path):
        log("Step 6: RESUME — monthly_objectives.json and external_context.json already exist.")
        objectives = _read_json(objectives_path)
        external_context = _read_json(external_ctx_path)
    else:
        log("Step 6: Planning monthly objectives and external personas...")
        prompt = build_monthly_objectives_prompt(
            profile_json=profile_json,
            project_index_json=project_index_json,
            file_list_json=file_list_json,
            start_date=start_date,
            real_world_context=real_world_context,
        )
        _accumulate_ds(await call_claude(
            prompt, cwd=world_dir, max_turns=30, plugins=plugins,
            model=model, log_file=log_file, turn_log_file=turn_log_file,
            step_label="step6_monthly_objectives",
        ))

        if not os.path.exists(objectives_path):
            raise RuntimeError("Step 6 failed: monthly_objectives.json was not created")
        if not os.path.exists(external_ctx_path):
            raise RuntimeError("Step 6 failed: external_context.json was not created")

        objectives = _read_json(objectives_path)
        external_context = _read_json(external_ctx_path)
        dlv_count = len(objectives.get("deliverables", []))
        persona_count = len(external_context.get("external_personas", []))
        log(f"Step 6 done: {dlv_count} deliverables, {persona_count} external personas.")

    # ==================================================================
    # Step 6.5: Generate External Persona Reference Files
    # ==================================================================
    external_refs_dir = os.path.join(world_dir, "external_refs")
    os.makedirs(external_refs_dir, exist_ok=True)

    personas = external_context.get("external_personas", [])
    for persona_entry in personas:
        persona_id = persona_entry.get("id", "unknown")
        persona_dir = os.path.join(external_refs_dir, persona_id)
        ref_files = persona_entry.get("reference_files", [])

        if not ref_files:
            continue

        # Check if already generated (at least one ref file exists)
        expected_files = [rf.get("filename", "") for rf in ref_files]
        existing_count = sum(
            1 for fn in expected_files
            if os.path.exists(os.path.join(persona_dir, fn))
        )

        if existing_count == len(expected_files) and existing_count > 0:
            log(f"Step 6.5: RESUME — {persona_id} reference files already exist ({existing_count} files).")
            continue

        os.makedirs(persona_dir, exist_ok=True)
        log(f"Step 6.5: Generating reference files for {persona_id} ({len(ref_files)} files)...")

        prompt = build_ref_files_prompt(
            persona_entry=persona_entry,
            user_profile_summary=user_summary,
            real_world_context=real_world_context,
        )
        _accumulate_ds(await call_claude(
            prompt, cwd=world_dir, max_turns=200, plugins=plugins,
            model=model, log_file=log_file, turn_log_file=turn_log_file,
            step_label=f"step6.5_ref_{persona_id}",
        ))
        _cleanup_stray_files(world_dir, log_fn=log)

        # Verify ref files
        generated_count = sum(
            1 for fn in expected_files
            if os.path.exists(os.path.join(persona_dir, fn))
        )
        log(f"Step 6.5: {persona_id} done. {generated_count}/{len(expected_files)} files generated.")

    # Generate workspace prerequisites
    context_seeds_path = os.path.join(world_dir, "context_seeds.json")
    if os.path.exists(context_seeds_path):
        context_seeds = _read_json(context_seeds_path)
        prereqs = context_seeds.get("workspace_prerequisites", [])
        if prereqs:
            # Check if already generated
            prereqs_done = all(
                os.path.exists(_logical_to_physical(world_dir, p["path"]))
                for p in prereqs
                if _logical_to_physical(world_dir, p["path"])
            )
            if prereqs_done:
                log("Step 6.5: RESUME — workspace prerequisite files already exist.")
            else:
                log(f"Step 6.5: Generating {len(prereqs)} workspace prerequisite files...")
                prompt = build_workspace_prereqs_prompt(
                    prerequisites=prereqs,
                    user_profile_summary=user_summary,
                )
                _accumulate_ds(await call_claude(
                    prompt, cwd=world_dir, max_turns=200, plugins=plugins,
                    model=model, log_file=log_file, turn_log_file=turn_log_file,
                    step_label="step6.5_workspace_prereqs",
                ))
                _cleanup_stray_files(world_dir, log_fn=log)
                log("Step 6.5: Workspace prerequisite files done.")

    log("Step 6.5 complete: all reference files and prerequisites generated.")

    if plan_only:
        _save_usage()
        log("--plan-only: stopping after Step 6.5.")
        return world_dir

    # ==================================================================
    # Setup shared folders
    # ==================================================================
    external_share_dir = os.path.join(world_dir, "external_share")  # persona → main (files)
    drives_share_dir = os.path.join(world_dir, "drives", "share")   # main → persona (files)
    os.makedirs(external_share_dir, exist_ok=True)
    os.makedirs(drives_share_dir, exist_ok=True)
    for p in personas:
        pid = p.get("id", "unknown")
        os.makedirs(os.path.join(external_share_dir, pid), exist_ok=True)

    # Per-persona interaction history (tracks all exchanges)
    # Load existing logs on resume so conversation history is preserved
    intlog_path = os.path.join(world_dir, "persona_interaction_logs.json")
    if os.path.exists(intlog_path):
        persona_interaction_logs: dict[str, list[dict]] = _read_json(intlog_path)
    else:
        persona_interaction_logs: dict[str, list[dict]] = {
            p.get("id", "unknown"): [] for p in personas
        }

    # Helper: compute the global day number (1-20) from week_num + day_idx
    def _global_day(wk: int, idx: int) -> int:
        return (wk - 1) * 5 + idx + 1

    # ==================================================================
    # contact_persona MCP tool (closure over simulation state)
    # ==================================================================
    # Mutable state shared between the tool handler and the daily loop
    sim_state = {
        "day_num": 0,
        "day_date": "",
        "persona_response_seq": {},  # {pid: int} per-persona counter, reset daily
    }
    # Index personas by id for fast lookup
    persona_by_id = {p.get("id", "unknown"): p for p in personas}

    @sdk_tool(
        "contact_persona",
        "Send a message to a collaborator and get their response. "
        "Returns the persona's reply text and a list of any files they shared.",
        {"persona_id": str, "message": str},
    )
    async def contact_persona_tool(args: dict) -> dict:
        pid = args["persona_id"]
        message = args["message"]
        day_num = sim_state["day_num"]
        day_date = sim_state["day_date"]

        persona_entry = persona_by_id.get(pid)
        if not persona_entry:
            return {
                "content": [{"type": "text", "text": f"Error: unknown persona '{pid}'. "
                             f"Available: {list(persona_by_id.keys())}"}],
                "is_error": True,
            }

        # Sequence number for this persona today
        seq = sim_state["persona_response_seq"].get(pid, 0) + 1
        sim_state["persona_response_seq"][pid] = seq
        pname = persona_entry.get("name", "Unknown")
        log(f"    [contact_persona] {pname} responding (day {day_num}, msg {seq})...")

        # Build interaction context
        interaction_ctx = (
            f"The main user has sent you the following message/request "
            f"on day {day_num} ({day_date}):\n\n"
            f"--- BEGIN MESSAGE ---\n{message}\n--- END MESSAGE ---"
        )

        # List shared files from main agent
        shared_files = []
        if os.path.isdir(drives_share_dir):
            for root, _dirs, files in os.walk(drives_share_dir):
                for fn in files:
                    shared_files.append(os.path.relpath(
                        os.path.join(root, fn), world_dir
                    ).replace("\\", "/"))

        # Snapshot external_share/{pid}/ before persona runs
        pid_share_dir = os.path.join(external_share_dir, pid)
        before_files = set()
        if os.path.isdir(pid_share_dir):
            for root, _dirs, files in os.walk(pid_share_dir):
                for fn in files:
                    before_files.add(os.path.relpath(
                        os.path.join(root, fn), world_dir
                    ).replace("\\", "/"))

        persona_prompt = build_persona_response_prompt(
            persona=persona_entry,
            interaction_context=interaction_ctx,
            interaction_history=persona_interaction_logs.get(pid, []),
            shared_files_from_main=shared_files,
            current_day=day_num,
            current_date=day_date,
            response_seq=seq,
        )
        result = await call_claude(
            persona_prompt, cwd=world_dir, max_turns=30,
            plugins=plugins, model=model, log_file=log_file,
            turn_log_file=turn_log_file,
            step_label=f"step8_persona_{pid}_day{day_num}_r{seq}",
        )
        _accumulate_ds(result)

        # Read persona's reply file
        reply_path = os.path.join(
            world_dir, "external_share", pid,
            f"reply_day{day_num}_r{seq}.txt",
        )
        reply_text = _read_file_as_text(reply_path)
        if not reply_text:
            # Fallback: use agent's text output
            reply_text = result.get("text", "(No reply generated)")

        # Detect new files shared by persona
        after_files = set()
        if os.path.isdir(pid_share_dir):
            for root, _dirs, files in os.walk(pid_share_dir):
                for fn in files:
                    after_files.add(os.path.relpath(
                        os.path.join(root, fn), world_dir
                    ).replace("\\", "/"))
        new_files = sorted(after_files - before_files)
        # Exclude the reply file itself from "new shared files"
        reply_relpath = f"external_share/{pid}/reply_day{day_num}_r{seq}.txt"
        new_files = [f for f in new_files if f != reply_relpath]

        # Record interaction in logs (keep full text for history fidelity)
        persona_interaction_logs.setdefault(pid, []).append({
            "day": day_num, "date": day_date,
            "direction": "main_to_persona",
            "type": "request",
            "content": message,
        })
        persona_interaction_logs.setdefault(pid, []).append({
            "day": day_num, "date": day_date,
            "direction": "persona_to_main",
            "type": "response",
            "content": reply_text,
        })

        # Persist logs after each interaction
        intlog_path = os.path.join(world_dir, "persona_interaction_logs.json")
        with open(intlog_path, "w", encoding="utf-8") as f:
            json.dump(persona_interaction_logs, f, indent=2, ensure_ascii=False)

        # Build tool result
        parts = [{"type": "text", "text": reply_text}]
        if new_files:
            file_list_str = "\n".join(f"  - {f}" for f in new_files)
            parts.append({"type": "text", "text": f"\n\nFiles shared by {pname}:\n{file_list_str}"})

        log(f"    [contact_persona] {pname} done (reply {len(reply_text)} chars, {len(new_files)} files shared)")
        return {"content": parts}

    # Create MCP server with the persona tool
    persona_mcp_server = create_sdk_mcp_server(
        "persona-tools",
        tools=[contact_persona_tool],
    )

    # ==================================================================
    # Steps 7–8: Weekly Planning + Daily Execution
    # ==================================================================
    objectives_json = json.dumps(objectives, indent=2, ensure_ascii=False)

    # Strip rubric from personas for main agent context
    personas_for_main = strip_personas_for_main_agent(personas)

    for week_num in range(1, num_weeks + 1):
        week_plan_path = os.path.join(world_dir, f"week_{week_num}_plan.json")

        # --- Step 7: Main Agent Weekly Planning ---
        if os.path.exists(week_plan_path):
            log(f"Step 7 (Week {week_num}): RESUME — plan already exists.")
            week_plan = _read_json(week_plan_path)
        else:
            log(f"Step 7 (Week {week_num}): Main agent planning week...")
            activity_log = _get_all_daily_activity_log(world_dir)
            current_file_list = _read_json(os.path.join(world_dir, "file_list.json"))

            prompt = build_weekly_plan_prompt(
                objectives_json=objectives_json,
                external_personas_json=json.dumps(
                    personas_for_main, indent=2, ensure_ascii=False,
                ),
                week_num=week_num,
                activity_log_json=json.dumps(activity_log, indent=2, ensure_ascii=False),
                file_list_json=json.dumps(current_file_list, indent=2, ensure_ascii=False),
                user_profile_summary=user_summary,
                real_world_context=real_world_context,
            )
            _accumulate_ds(await call_claude(
                prompt, cwd=world_dir, max_turns=30, plugins=plugins,
                model=model, log_file=log_file, turn_log_file=turn_log_file,
                step_label=f"step7_week{week_num}_plan",
            ))

            if not os.path.exists(week_plan_path):
                raise RuntimeError(f"Step 7 failed: week_{week_num}_plan.json was not created")

            week_plan = _read_json(week_plan_path)
            day_count = len(week_plan.get("days", []))
            log(f"Step 7 (Week {week_num}): done. {day_count} days planned.")

        # --- Step 8: Daily Execution ---
        days = week_plan.get("days", [])
        for day_idx, day_plan in enumerate(days):
            day_date = day_plan.get("date", f"week{week_num}_day{day_idx}")
            day_num = _global_day(week_num, day_idx)
            activities = day_plan.get("activities", [])

            # Resume: skip days that already completed
            day_marker = os.path.join(world_dir, f"_day{day_num}_complete")
            if os.path.exists(day_marker):
                log(f"Step 8 (Week {week_num}, Day {day_num}, {day_date}): RESUME — already complete.")
                continue

            # Update sim_state for the contact_persona tool closure
            sim_state["day_num"] = day_num
            sim_state["day_date"] = day_date
            sim_state["persona_response_seq"] = {}  # reset per day

            file_count = sum(
                len(a.get("files_to_create", [])) + len(a.get("files_to_modify", []))
                for a in activities
            )
            log(f"Step 8 (Week {week_num}, Day {day_num}, {day_date}): "
                f"{file_count} files + {len(activities)} activities...")

            # ========== Main Agent Session ==========
            # Create directories for new files
            for act in activities:
                for path in act.get("files_to_create", []):
                    physical = _logical_to_physical(world_dir, path)
                    if physical:
                        os.makedirs(os.path.dirname(physical), exist_ok=True)

            # Collect existing file contents for modifications
            existing_contents = {}
            for act in activities:
                for path in act.get("files_to_modify", []):
                    physical = _logical_to_physical(world_dir, path)
                    if physical and os.path.exists(physical):
                        content = _read_file_as_text(physical)
                        if content:
                            existing_contents[path] = content

            # All personas visible (rubric stripped) — main agent needs full list
            # for the contact_persona tool descriptions
            ext_persona_context = json.dumps(
                personas_for_main, indent=2, ensure_ascii=False,
            )

            # Re-read file_graph each day (agent may have added edges)
            file_graph = _read_json(os.path.join(world_dir, "file_graph.json"))
            all_day_paths = set()
            for act in activities:
                all_day_paths.update(act.get("files_to_create", []))
                all_day_paths.update(act.get("files_to_modify", []))
            relevant_edges = _get_relevant_edges(file_graph, all_day_paths)

            # Full activity log (Cold Start + Daily Sim)
            activity_log = _get_all_daily_activity_log(world_dir)

            prompt = build_daily_file_generation_prompt(
                day_plan=day_plan,
                activity_log_entries=activity_log,
                file_graph_edges=relevant_edges,
                user_profile_summary=user_summary,
                world_root=world_dir,
                external_personas_context=ext_persona_context,
                real_world_context=real_world_context,
                existing_file_contents=existing_contents if existing_contents else None,
            )
            _accumulate_ds(await call_claude(
                prompt, cwd=world_dir, max_turns=500, plugins=plugins,
                model=model,
                mcp_servers={"persona-tools": persona_mcp_server},
                log_file=log_file, turn_log_file=turn_log_file,
                step_label=f"step8_week{week_num}_day{day_idx}_{day_date}",
            ))
            _cleanup_stray_files(world_dir, log_fn=log)

            # ========== Post-day bookkeeping ==========
            created_paths = []
            for act in activities:
                for path in act.get("files_to_create", []):
                    created_paths.append({"path": path})
            if created_paths:
                missing = _verify_batch(world_dir, created_paths, log_fn=log)
                if missing:
                    log(f"  WARNING: {len(missing)} files missing on {day_date}.")

            # Update file_list.json with new files
            current_file_list = _read_json(os.path.join(world_dir, "file_list.json"))
            existing_paths = {e["path"] for e in current_file_list}
            for act in activities:
                for path in act.get("files_to_create", []):
                    if path not in existing_paths:
                        current_file_list.append({
                            "path": path,
                            "timestamp": f"{day_date}T{act.get('time', '09:00')}:00",
                            "origin": "user_created",
                            "description": act.get("description", ""),
                            "content_mode": "generate",
                            "content_scale": "medium",
                            "project_ids": [act["deliverable_id"]] if act.get("deliverable_id") else [],
                            "content_generated": True,
                        })
                        existing_paths.add(path)
            fl_path = os.path.join(world_dir, "file_list.json")
            with open(fl_path, "w", encoding="utf-8") as f:
                json.dump(current_file_list, f, indent=2, ensure_ascii=False)

            # Save persona interaction logs
            intlog_path = os.path.join(world_dir, "persona_interaction_logs.json")
            with open(intlog_path, "w", encoding="utf-8") as f:
                json.dump(persona_interaction_logs, f, indent=2, ensure_ascii=False)

            # Mark day as complete for resume
            with open(day_marker, "w") as f:
                f.write(datetime.now().isoformat() + "\n")
            log(f"Step 8 (Week {week_num}, Day {day_num}, {day_date}): done.")

        log(f"Week {week_num} complete.")

    # ==================================================================
    # Step 9: Deliverable Evaluation
    # ==================================================================
    log("Step 9: Evaluating deliverables...")
    deliverables = objectives.get("deliverables", [])
    evaluation_results = []

    for dlv in deliverables:
        dlv_id = dlv.get("id", "unknown")

        # Find the evaluator persona (the one with rubric for this deliverable)
        evaluator_persona = None
        for p in personas:
            rubric = p.get("rubric", {})
            if rubric and rubric.get("deliverable_id") == dlv_id:
                evaluator_persona = p
                break

        if not evaluator_persona:
            log(f"  Step 9: No evaluator found for {dlv_id} — skipping.")
            continue

        eval_pid = evaluator_persona.get("id", "unknown")
        eval_name = evaluator_persona.get("name", "Unknown")
        log(f"  Step 9: {eval_name} evaluating {dlv_id}...")

        # Collect deliverable files
        deliv_files = {}
        for path in dlv.get("output_files", []):
            physical = _logical_to_physical(world_dir, path)
            if physical and os.path.exists(physical):
                content = _read_file_as_text(physical)
                if content:
                    deliv_files[path] = content

        # Collect evaluator's reference files
        ref_files_content = {}
        eval_ref_dir = os.path.join(world_dir, "external_refs", eval_pid)
        if os.path.isdir(eval_ref_dir):
            for fn in os.listdir(eval_ref_dir):
                fpath = os.path.join(eval_ref_dir, fn)
                content = _read_file_as_text(fpath)
                if content:
                    ref_files_content[fn] = content

        prompt = build_evaluation_prompt(
            persona=evaluator_persona,
            deliverable=dlv,
            interaction_history=persona_interaction_logs.get(eval_pid, []),
            deliverable_files=deliv_files,
            reference_files=ref_files_content,
        )
        result = await call_claude(
            prompt, cwd=world_dir, max_turns=30, plugins=plugins,
            model=model, log_file=log_file, turn_log_file=turn_log_file,
            step_label=f"step9_eval_{dlv_id}_{eval_pid}",
        )
        _accumulate_ds(result)

        # Check for evaluation output file
        eval_file = os.path.join(world_dir, f"evaluation_{eval_pid}_{dlv_id}.json")
        if os.path.exists(eval_file):
            eval_data = _read_json(eval_file)
            evaluation_results.append(eval_data)
            pct = eval_data.get("percentage", "?")
            log(f"  Step 9: {eval_name} scored {dlv_id}: {pct}%")
        else:
            log(f"  Step 9: WARNING — evaluation file not created for {dlv_id}.")

    # Save all evaluation results
    if evaluation_results:
        eval_summary_path = os.path.join(world_dir, "evaluation_summary.json")
        with open(eval_summary_path, "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)

    # ==================================================================
    # Final Summary
    # ==================================================================
    _save_usage()

    final_file_list = _read_json(os.path.join(world_dir, "file_list.json"))
    activity_count = len(_read_jsonl(
        os.path.join(world_dir, "daily_activity_log.jsonl")
    ))

    # Write daily sim completion marker
    with open(os.path.join(world_dir, "_daily_sim_complete"), "w") as f:
        f.write(datetime.now().isoformat() + "\n")

    usage_str = ", ".join(f"{k}={v}" for k, v in total_usage.items())
    log(
        f"DAILY SIM COMPLETE: {len(final_file_list)} total files, "
        f"{activity_count} activities. "
        f"Cost: ${total_cost_usd:.4f}, turns: {total_turns}, {usage_str}"
    )

    return world_dir
