# PC Simulation Agent

## Project Overview
- Simulates realistic PC filesystems for evaluating AI agents on professional tasks
- Cold Start (Steps 1-5): generates user profile + filesystem
- Daily Simulation (Steps 6-8): monthly work simulation with deliverables
- Step 9: GDPval-level evaluation with 45-65 rubric items per deliverable
- Uses Claude Agent SDK (`claude_agent_sdk`) to run sub-agents

## Key Files
- `pipeline.py` — main orchestration (cold_start, daily_simulate, call_claude)
- `daily_prompts.py` — prompt templates for Steps 6-9
- `daily_sim.py` — CLI entry point for daily simulation
- `batch_run.py` — CLI for cold start, defaults to claude-sonnet-4-6

## Architecture

### Folder Structure
```
gdpeval_world_XXXXXX/
├── drives/                    # Main persona's private filesystem
│   ├── C/Users/.../
│   ├── D/ClientWork/...
│   └── share/                 # Main → external outbound file share
├── external_refs/             # External personas' private files (NOT visible to main)
│   ├── ext_001/
│   └── ...
└── external_share/            # External → main inbound file share + replies
    ├── ext_001/
    │   ├── reply_day3_r1.txt  # Text replies from persona
    │   └── data_file.xlsx     # Files shared by persona
    └── ...
```

### Multi-Agent Communication (MCP Tool)
Main agent communicates with external personas via `contact_persona` MCP tool:
1. `contact_persona` defined as `@sdk_tool` closure inside `daily_simulate()`
2. Registered as MCP server via `create_sdk_mcp_server("persona-tools", ...)`
3. Main agent calls the tool inline — gets instant reply, no file routing needed
4. Multiple calls per day supported (seq counter tracks rounds)

### Per-Day Flow (Step 8)
1. Update sim_state (day_num, day_date, reset seq counters)
2. Run main agent session with `contact_persona` tool available
3. Post-day bookkeeping (verify files, update file_list.json, save logs)

### Step 9: Evaluation
- Per deliverable: evaluator persona generates GDPval-level rubric (45-65 items)
- Evaluator sees: deliverable spec + preferences/rubric + interaction history + ref files + deliverable file paths
- Agent reads files via tools (supports xlsx, docx, pdf) — no content truncation in prompt
- Each item: criterion, source (spec|reference|interaction|expertise|quality), points, met/unmet

## Known Issues
- SDK ExceptionGroup after contact_persona MCP tool (~50% of calls) — mitigated with 3-retry logic
- `_ensure_dependencies` uses `uv pip install` (not `pip`) because venv has no pip module
- SDK defaults to Sonnet when no --model flag is passed

## Development Notes
- Run with: `uv run python daily_sim.py --world-id <id> [--model claude-sonnet-4-6]`
- Cold start: `uv run python batch_run.py --world-id <id>`
- Import check: `uv run python -c "import pipeline; import daily_prompts"`
