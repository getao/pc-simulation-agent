# PC Filesystem Simulation Agent

Generate realistic Windows PC filesystem environments (UserWorlds) from user personas. Each UserWorld contains documents, spreadsheets, images, downloads, and other files that a real user would have — complete with realistic content, timestamps, and file relationships.

Uses [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk) to orchestrate Claude Code CLI for multi-step file generation.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Claude Code CLI installed and authenticated (`claude` command available)

## Setup

```bash
git clone https://github.com/getao/pc-simulation-agent.git
cd pc-simulation-agent
uv sync
```

## Quick Start

### Single persona

```bash
# Inline persona
uv run python cold_start.py --persona "A mid-career history professor at Duke University who researches Roman military logistics"

# From file
uv run python cold_start.py --persona-file persona.txt

# With options
uv run python cold_start.py --persona "..." --model claude-sonnet-4-6 --timestamp "2025-03-01T10:00:00"
```

### Batch run (multiple personas)

```bash
# Run 10 personas starting from line 0, with 5 concurrent workers
uv run python batch_run.py --input personas.jsonl --limit 10 --concurrency 5

# Custom world ID prefix (produces gdpeval_world_000000, gdpeval_world_000001, ...)
uv run python batch_run.py --input personas.jsonl --limit 3 --concurrency 3 --prefix gdpeval_world

# Resume from line 50
uv run python batch_run.py --input personas.jsonl --offset 50 --limit 20 --concurrency 10

# Per-world timeout (default: 3600s)
uv run python batch_run.py --input personas.jsonl --limit 5 --timeout 1800
```

The input JSONL file should have one JSON object per line with a `"persona"` field:

```json
{"persona": "A senior data analyst at a healthcare company..."}
{"persona": "A freelance graphic designer based in Portland..."}
```

## Pipeline

The system runs a 5-step pipeline for each persona:

| Step | What it does | Output |
|------|-------------|--------|
| 1 | Expand persona into detailed user profile | `user_profile.json` |
| 2 | Derive filesystem behavior patterns | `filesystem_policy.json` |
| 3 | Plan projects, files, and relationships | `project_index.json`, `file_list.json`, `file_graph.json` |
| 4 | Create directory structure | `drives/` folder tree |
| 5 | Generate file contents (batched, chronological) | Actual files + `activity_log.jsonl` |

## Output Structure

Each world is generated under `worlds/<world_id>/`:

```
worlds/world_000001/
  persona.json              # Input persona + timestamp
  user_profile.json         # Expanded user profile
  filesystem_policy.json    # Filesystem behavior patterns
  project_index.json        # Project metadata
  file_list.json            # All planned files with metadata
  file_graph.json           # File relationships (DAG)
  activity_log.jsonl        # Chronological activity entries
  usage.json                # Token usage and cost summary
  output.log                # Claude Code output log
  _complete                 # Completion marker
  drives/
    C/Users/alice/
      Desktop/
      Documents/
      Downloads/
      Pictures/
    D/Projects/
      ...
```

## Resume Support

The pipeline supports resuming at two levels:

- **World level**: Completed worlds (with `_complete` marker) are skipped on re-run
- **File level**: If a run is interrupted during file generation, already-generated files (`content_generated: true` in `file_list.json`) are skipped on resume. Planning steps (1-3) are also skipped if their outputs are valid.

Just re-run the same command — it picks up where it left off.

## CLI Reference

### `cold_start.py`

| Flag | Description | Default |
|------|-------------|---------|
| `--persona` | Persona text (mutually exclusive with `--persona-file`) | required |
| `--persona-file` | Path to persona text file | required |
| `--timestamp` | Simulated current time (ISO format) | now |
| `--world-id` | Custom world ID | auto-generated |
| `--model` | Claude model (e.g. `claude-sonnet-4-6`) | SDK default |
| `--max-generate` | Only generate first N files | all |
| `--worlds-root` | Output directory | `worlds/` |
| `--plugins` | Plugin directories to load | none |

### `batch_run.py`

| Flag | Description | Default |
|------|-------------|---------|
| `--input` | Path to personas JSONL file | required |
| `--limit` | Max personas to process | all |
| `--offset` | Skip first N personas | 0 |
| `--prefix` | World ID prefix | `world` |
| `--concurrency` | Parallel workers | 5 |
| `--timeout` | Per-world timeout in seconds | 3600 |
| `--model` | Claude model | `claude-sonnet-4-6` |
| `--max-generate` | Max files to generate per world | all |
| `--worlds-root` | Output directory | `worlds/` |
| `--plugins` | Plugin directories | none |

## File Types Supported

The system generates real files using appropriate tools:

| Format | Tool |
|--------|------|
| `.docx` | docx-js (npm `docx`) |
| `.xlsx` | openpyxl (Python) |
| `.pptx` | PptxGenJS (npm `pptxgenjs`) |
| `.pdf` | reportlab (Python) |
| `.png`, `.jpg` | image-generation skill |
| Text files | Direct write |
| Downloads | `curl`/`wget` from real URLs |

Skills for these formats are included in `.claude/skills/`.
