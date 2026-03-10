"""Prompt templates for Daily Work Simulation (Steps 6–8).

These extend the Cold Start pipeline with monthly objectives planning,
external persona construction, weekly day-by-day planning, and daily
file generation.
"""

import json

# ---------------------------------------------------------------------------
# GDP-val reference examples (quality floor for deep_work outputs)
# ---------------------------------------------------------------------------

_GDPVAL_EXAMPLES = """\
These GDP-val tasks represent the MINIMUM complexity for any single deep_work output:
- Auditor: Sample-size calculation at 90% confidence, variance analysis on anti-financial-crime risk metrics, multi-criteria audit sampling → xlsx with workings tab
- Warehouse Manager: Write a 5-page SOP for ESD-sensitive component handling per IPC-A-610G → professional docx
- Lawyer: Draft an 8–11 page Last Will and Testament from scratch under Texas law with trust provisions → pdf
Every deep_work file you plan must be AT LEAST this complex."""


# ===================================================================
# Step 6: Monthly Objectives + External Personas + Real-world Context
# ===================================================================

def build_monthly_objectives_prompt(
    profile_json: str,
    project_index_json: str,
    file_list_json: str,
    start_date: str,
    real_world_context: str = "",
) -> str:
    """Build prompt for Step 6: monthly objectives + external personas.

    The LLM must output THREE JSON files:
      1. monthly_objectives.json
      2. external_context.json
      3. context_seeds.json (workspace prerequisite files)
    """
    return f"""\
You are planning a **one-month daily work simulation** for a user whose PC
filesystem has already been populated by a Cold Start process.  Your job is
to design what this user will actually DO over ~20 working days — the
projects they advance, the people they interact with, and the deliverables
they produce.

## User Profile
{profile_json}

## Current Projects
{project_index_json}

## Existing Files (Cold Start output)
{file_list_json}

## Simulation Start Date
{start_date}
(Simulation covers ~20 working days = 4 weeks from this date.)

## Real-World Context (from web search)
{real_world_context if real_world_context else "(No real-world context provided — use your training knowledge for the simulation period.)"}

## Quality Floor
{_GDPVAL_EXAMPLES}

─────────────────────────────────────────────────────────
## YOUR TASK

Produce **three JSON files** by writing them to the current directory.

### 1. `monthly_objectives.json`

Plan the user's month.  Include:

```json
{{
  "simulation_period": {{
    "start": "{start_date}",
    "end": "<4 weeks later>",
    "working_days": 20
  }},
  "long_horizon_deliverables": [
    {{
      "id": "lhd_001",
      "title": "<descriptive title>",
      "project_id": "<from project_index>",
      "description": "<what this deliverable is, why it matters>",
      "target_completion": "<ISO date>",
      "milestones": [
        {{"week": 1, "goal": "<concrete goal>"}},
        {{"week": 2, "goal": "..."}},
        {{"week": 3, "goal": "..."}},
        {{"week": 4, "goal": "..."}}
      ],
      "output_files": ["<filename_v1.ext>", "<filename_v2.ext>", "<filename_FINAL.ext>"]
    }}
  ],
  "recurring_activities": [
    {{"frequency": "daily|weekly|biweekly", "activity": "<description>"}}
  ],
  "weekly_focus": [
    {{"week": 1, "focus": "<theme>", "lhd_ids": ["lhd_001"]}},
    ...
  ]
}}
```

**Rules for long_horizon_deliverables:**
- Number of LHDs depends on the user's role and seniority (not fixed).
  Senior/management roles naturally juggle more concurrent work items;
  junior or focused roles may have just 1–2.  Choose what is most realistic
  for THIS persona.
- Each LHD is a **work package** (5–10 interrelated files), not a single doc.
- Each must go through ≥3 iterations (draft → revision → final).
- Milestones must be concrete and measurable.
- output_files list the key filenames that will be created (versions included).

### 2. `external_context.json`

Design 3–5 external personas who will interact with the user during the month.
These are real people in the user's work life — managers, clients, colleagues,
direct reports, external partners.

**Every external persona must include:**
- Detailed background (age, education, tenure, personality, work style)
- key_facts with domain-specific data (not vague — exact numbers, names, dates)
- reference_files: concrete files this persona "brings" to the interaction.
  Each reference file has an id, filename, description (detailed enough to
  generate the actual file), content_scale (small/medium/large), and optionally
  intentional_errors (for files from junior staff that the user should catch).
- interaction_timeline: week-by-week planned interactions with the user.
  Each entry has: week, day (1-20), type (email/meeting/deliverable/feedback/
  question/approval/call), content (specific and detailed — not vague),
  and optionally delivers_file (ref id) or references_files [ref ids].
- communication_style description

**Types of reference files by persona role:**
| Role | Reference Files |
|------|----------------|
| Manager/Director | Quality exemplar deliverables, review checklists, process docs, templates |
| Client | Their data files, project specs, company templates |
| Direct Report | Data exports (may contain errors), draft work products, analysis templates |
| External Party | Industry standards, regulatory templates, third-party reports |

**Hidden Rubric** — for each LHD, specify a rubric from its requester:
```json
{{
  "rubric": {{
    "deliverable_id": "lhd_001",
    "requester_id": "ext_...",
    "communication_style": "structured|scattered|minimal",
    "criteria": [
      {{"name": "...", "weight": 0.3, "description": "..."}}
    ],
    "initially_communicated": ["<criteria names told upfront>"],
    "revealed_on_ask": ["<criteria revealed when user asks>"],
    "only_at_review": ["<criteria revealed only at review time>"]
  }}
}}
```

### 3. `context_seeds.json`

List workspace prerequisite files that need to exist in the user's filesystem
BEFORE daily simulation starts (company policies, internal templates, etc.
that Cold Start didn't generate but the simulation needs):

```json
{{
  "workspace_prerequisites": [
    {{
      "path": "<logical Windows path, e.g. C:/Users/.../file.ext>",
      "description": "<what this file is and why it's needed>",
      "origin": "company_policy|internal_template|historical_communication",
      "content_scale": "small|medium|large",
      "needed_by": ["lhd_001"]
    }}
  ]
}}
```

## CRITICAL RULES
1. All personas, data, and interactions must be **internally consistent**.
2. Reference files must contain enough detail to actually generate realistic files.
3. Interaction timelines must form coherent causal chains (Week 1 data → Week 2 analysis → Week 3 review).
4. Use real-world context (market data, regulations, news) where relevant.
5. The user's daily work should reflect what someone in this exact role would actually do.
6. Do NOT be generic. Be specific: real numbers, real names, real dates, real domain terminology.

Write all three files now.
"""


# ===================================================================
# Step 6.5: External Persona Reference Files Generation
# ===================================================================

def build_ref_files_prompt(
    persona_entry: dict,
    user_profile_summary: str,
    real_world_context: str = "",
) -> str:
    """Build prompt for generating one external persona's reference files.

    Called once per external persona.  The LLM creates the actual files
    described in persona_entry['reference_files'].
    """
    ref_files = persona_entry.get("reference_files", [])
    persona_id = persona_entry.get("id", "unknown")
    ref_descriptions = json.dumps(ref_files, indent=2, ensure_ascii=False)

    return f"""\
You are generating **reference files** for an external persona in a work
simulation.  These files represent documents, data, and templates that this
persona brings to their interactions with the main user.

## Main User (for context)
{user_profile_summary}

## External Persona
{json.dumps(persona_entry, indent=2, ensure_ascii=False)}

## Real-World Context
{real_world_context if real_world_context else "(Use your training knowledge.)"}

## Files to Generate
{ref_descriptions}

─────────────────────────────────────────────────────────
## YOUR TASK

Create each file listed above in the directory `external_refs/{persona_id}/`.

**For each file:**
- Use the `description` to guide content generation.
- Respect the `content_scale`:
  - small: 1–2 pages or a brief file
  - medium: 3–5 pages or a moderately detailed file
  - large: 6+ pages or a complex, data-rich file
- If `intentional_errors` are specified, embed those exact errors naturally
  into the file.  They should look like genuine mistakes, not flagged errors.
- Use the appropriate tool/library for the file type:
  - .docx → docx skill or Node.js docx library
  - .xlsx → openpyxl (Python) or xlsx (Node.js)
  - .pptx → pptxgenjs (Node.js)
  - .pdf → reportlab (Python) or pdf-lib (Node.js)
  - .txt/.eml → Write tool directly
- Content must be **professional, domain-accurate, and realistic**.
  These files will be used as input data and quality benchmarks in the
  simulation — they must look like real work products.

## PATH RULE
All paths must start with `external_refs/{persona_id}/`.
For example: `external_refs/{persona_id}/Henderson_IPS_2024.pdf`

Create all files now.
"""


# ===================================================================
# Step 6.5 (continued): Workspace Prerequisite Files
# ===================================================================

def build_workspace_prereqs_prompt(
    prerequisites: list[dict],
    user_profile_summary: str,
) -> str:
    """Build prompt for generating workspace prerequisite files.

    These go into the user's drives/ filesystem.
    """
    prereqs_json = json.dumps(prerequisites, indent=2, ensure_ascii=False)

    return f"""\
You are generating **workspace prerequisite files** for a work simulation.
These are company policies, internal templates, and other documents that
must exist in the user's filesystem before daily work simulation begins.

## User
{user_profile_summary}

## Files to Generate
{prereqs_json}

─────────────────────────────────────────────────────────
## YOUR TASK

Create each file listed above.  For each entry:
- Convert the `path` (e.g. `C:/Users/alice/Documents/file.docx`) to
  the physical path `drives/C/Users/alice/Documents/file.docx`.
- Use the `description` to guide content generation.
- Respect `content_scale` (small/medium/large).
- Use the appropriate tool/library for the file type.
- Content must be professional and realistic.

## PATH RULE
All file paths MUST start with `drives/`.

Create all files now.
"""


# ===================================================================
# Step 7: Weekly Day-by-Day Planning
# ===================================================================

def build_weekly_plan_prompt(
    objectives_json: str,
    external_context_json: str,
    week_num: int,
    activity_log_json: str,
    file_list_json: str,
    user_profile_summary: str,
    real_world_context: str = "",
) -> str:
    """Build prompt for Step 7: plan one week's activities day by day.

    Called 4 times (once per week).
    """
    return f"""\
You are planning **Week {week_num}** of a 4-week daily work simulation.

## User
{user_profile_summary}

## Monthly Objectives
{objectives_json}

## External Personas & Interaction Timeline
{external_context_json}

## Activity Log (everything that has happened so far)
{activity_log_json if activity_log_json else "[]"}

## Current File List (files that already exist on disk)
{file_list_json}

## Real-World Context
{real_world_context if real_world_context else "(Use your training knowledge.)"}

─────────────────────────────────────────────────────────
## YOUR TASK

Write `week_{week_num}_plan.json` with this structure:

```json
{{
  "week": {week_num},
  "days": [
    {{
      "date": "<YYYY-MM-DD>",
      "day_of_week": "<Monday|Tuesday|...>",
      "activities": [
        {{
          "time": "<HH:MM>",
          "type": "<deep_work|email_read|email_write|meeting|web_research|internal_lookup|chat|clarify|review|admin>",
          "description": "<specific description of what the user does>",
          "files_to_create": ["<logical Windows path>"],
          "files_to_modify": ["<logical Windows path of existing file>"],
          "content_notes": "<detailed guidance for file generation>",
          "lhd_id": "<if related to a long-horizon deliverable>",
          "external_persona_id": "<if involves an external persona>",
          "milestone_progress": "<if advances an LHD milestone>",
          "derived_from": ["<paths of files this depends on>"]
        }}
      ]
    }}
  ]
}}
```

## RULES

1. **5 working days** (Mon–Fri) for this week.
2. **3–6 activities per day**, mixing routine (email, meetings) with deep work.
3. **Follow the interaction_timeline**: if an external persona has a planned
   interaction for week {week_num}, it MUST appear in the plan on the correct day.
4. **Advance LHD milestones**: check the milestone for week {week_num} and
   ensure activities progress toward that goal.
5. **Non-file activities are important**: email_read, internal_lookup don't
   create files but must be included — they provide context for later work.
6. **Realistic pacing**: not every day is equally productive.  Some days
   have more meetings, some have more deep work.  Vary naturally.
7. **file content_notes must be detailed**: these will be used as instructions
   for actual file generation.  Don't be vague — specify what the file should
   contain, what data to include, what format to use.
8. **files_to_modify**: when a file is being revised (v1→v2), list the
   original file path here.  The generator will read the existing file and
   produce an updated version.
9. **Each deep_work file must be ≥ GDP-val complexity level**:
   {_GDPVAL_EXAMPLES}

Write the file now.
"""


# ===================================================================
# Step 8: Daily File Generation (extends Cold Start's file gen prompt)
# ===================================================================

def build_daily_file_generation_prompt(
    day_plan: dict,
    activity_log_entries: list[dict],
    file_graph_edges: list[dict],
    user_profile_summary: str,
    world_root: str,
    external_personas_context: str = "",
    real_world_context: str = "",
    existing_file_contents: dict[str, str] | None = None,
) -> str:
    """Build prompt for Step 8: generate files for one day's activities.

    Similar to Cold Start's build_file_generation_prompt but adds:
    - Day context (what day it is, what the user is working toward)
    - External persona context for interactions
    - File modification support (read existing → edit → save)
    - Richer activity log entries including non-file activities
    """
    day_date = day_plan.get("date", "unknown")
    day_of_week = day_plan.get("day_of_week", "unknown")
    activities = day_plan.get("activities", [])

    # Separate file-producing activities from non-file activities
    file_activities = []
    non_file_activities = []
    for act in activities:
        if act.get("files_to_create") or act.get("files_to_modify"):
            file_activities.append(act)
        else:
            non_file_activities.append(act)

    # Build file list for generation
    files_to_process = []
    for act in file_activities:
        for path in act.get("files_to_create", []):
            files_to_process.append({
                "path": path,
                "description": act.get("content_notes", act.get("description", "")),
                "activity_description": act.get("description", ""),
                "derived_from": act.get("derived_from", []),
                "is_modification": False,
            })
        for path in act.get("files_to_modify", []):
            files_to_process.append({
                "path": path,
                "description": act.get("content_notes", act.get("description", "")),
                "activity_description": act.get("description", ""),
                "derived_from": act.get("derived_from", []),
                "is_modification": True,
            })

    files_json = json.dumps(files_to_process, indent=2, ensure_ascii=False)
    non_file_json = json.dumps(non_file_activities, indent=2, ensure_ascii=False)
    activity_log_json = json.dumps(activity_log_entries, indent=2, ensure_ascii=False)
    edges_json = json.dumps(file_graph_edges, indent=2, ensure_ascii=False)

    # Build existing file contents section
    existing_contents_section = ""
    if existing_file_contents:
        parts = []
        for path, content in existing_file_contents.items():
            # Truncate very large files
            if len(content) > 5000:
                content = content[:5000] + "\n... [truncated] ..."
            parts.append(f"### {path}\n```\n{content}\n```")
        existing_contents_section = (
            "\n## Existing File Contents (for modifications)\n"
            + "\n\n".join(parts)
        )

    return f"""\
⚠️ PATH RULE — READ THIS FIRST ⚠️
All file paths MUST be RELATIVE to cwd, starting with `drives/`.
Convert logical paths: `C:/Users/alice/file.docx` → `drives/C/Users/alice/file.docx`
NEVER use `/mnt/d/...`, `/d/...`, `/home/...`, `C:/...`, or `D:/...`.

═══════════════════════════════════════════════════════════════════

## Today: {day_of_week}, {day_date}

## User
{user_profile_summary}

## External Personas (relevant to today's interactions)
{external_personas_context if external_personas_context else "(No external interactions today.)"}

## Real-World Context
{real_world_context if real_world_context else "(Use your training knowledge.)"}

## Recent Activity Log
{activity_log_json}

## File Graph Edges (relationships)
{edges_json}
{existing_contents_section}

═══════════════════════════════════════════════════════════════════

## FILES TO CREATE OR MODIFY

{files_json}

## NON-FILE ACTIVITIES TO LOG

These activities don't produce files but must be recorded in activity_log.jsonl:
{non_file_json}

═══════════════════════════════════════════════════════════════════

## INSTRUCTIONS

### For each file to CREATE:
1. Convert the logical path to `drives/...` format.
2. Create parent directories if needed (use Bash `mkdir -p`).
3. Generate the file using the appropriate tool:
   - .docx → use the docx skill or `npm` docx library via a Node.js script
   - .xlsx → use `openpyxl` (Python script) or `npm` xlsx library
   - .pptx → use `pptxgenjs` via a Node.js script
   - .pdf → use `reportlab` (Python) or `pdf-lib` (Node.js)
   - .txt / .eml / .md / .json / .csv → use the Write tool directly
   - .png / .jpg → use image-generation skill or Jimp
4. Content must be professional, domain-accurate, and realistic.
5. Each deep_work file must be ≥ GDP-val complexity level.

### For each file to MODIFY:
1. Read the existing file to understand its current content.
2. Make the changes described in `content_notes`.
3. Save as a new version file (e.g., `_v2`, `_revised`, `_FINAL`).
4. The modification should reflect real iterative improvement — not just
   trivial edits, but substantive changes based on feedback or new data.

### Activity Logging:
After processing all files AND non-file activities, append entries to
`activity_log.jsonl` (one JSON object per line):

```json
{{"timestamp": "{day_date}T<HH:MM>:00", "activity": "<information-dense description>", "related_files": ["<path1>", "<path2>"]}}
```

Include entries for ALL activities — both file-producing and non-file ones.
Non-file activities are important context (e.g., "Read email from Henderson
about Q4 performance concerns and Fed rate outlook").

### File Graph Updates:
After creating/modifying files, append new edges to `file_graph.json`:
- `version_of` edges for file modifications (v1 → v2)
- `derived_from` edges for files built on other files
- `references` edges for files that cite other files

## PATH RULE REMINDER
| Correct ✓ | Wrong ✗ |
|-----------|---------|
| `drives/C/Users/alice/report.docx` | `C:/Users/alice/report.docx` |
| `drives/D/Projects/data.xlsx` | `/mnt/d/Projects/data.xlsx` |

In scripts: output path must be a variable like
`const outPath = 'drives/C/Users/alice/report.docx';`

Now create/modify all files and log all activities.
"""
