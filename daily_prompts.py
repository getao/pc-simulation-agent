"""Prompt templates for Daily Work Simulation (Steps 6–9).

These extend the Cold Start pipeline with monthly objectives planning,
external persona construction, weekly day-by-day planning, daily
file generation, and deliverable evaluation.
"""

from __future__ import annotations

import copy
import json


# ---------------------------------------------------------------------------
# Context filtering helpers (information isolation)
# ---------------------------------------------------------------------------

def strip_persona_for_main_agent(persona: dict) -> dict:
    """Return a copy of a persona entry with rubric removed.

    Used when building prompts for the main agent (Steps 7/8) so it cannot
    see hidden evaluation criteria.
    """
    p = copy.deepcopy(persona)
    p.pop("rubric", None)
    return p


def strip_personas_for_main_agent(personas: list[dict]) -> list[dict]:
    """Convenience: strip all personas for main agent context."""
    return [strip_persona_for_main_agent(p) for p in personas]

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
filesystem has already been populated by a Cold Start process.

## Your Perspective

You are NOT the user.  You are the user's **senior manager** (or an industry
expert at the top of this profession) who deeply understands:
- What excellent work looks like in this role
- What a realistic but challenging monthly workload is
- What deliverables would demonstrate real professional competence
- Who this person interacts with and what those interactions look like

Your job is to set **month-level objectives** for this user — the kind of
KPI/OKR targets a manager would assign — that require roughly one full month
of sustained professional effort.  The final acceptance criteria are concrete
**deliverables** (work packages of 5–10 interrelated files each).

Study the user's profile, their active projects, and their existing filesystem
carefully.  Most objectives should build on what's already on their desk —
continuing in-progress work, responding to recent events, advancing existing
projects.  But new assignments (from a manager, a new client, an emerging
opportunity) are also realistic and welcome if they fit the user's role.

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
  "deliverables": [
    {{
      "id": "dlv_001",
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
    {{"week": 1, "focus": "<theme>", "deliverable_ids": ["dlv_001"]}},
    ...
  ]
}}
```

**Rules for deliverables:**
- **Task Complexity**: Each deliverable must be a genuinely hard, long-horizon
  task — multi-hop, multi-step, NOT something completable in one sitting.
  Examples of what makes a task complex: incomplete starting information that
  forces clarification rounds with collaborators; needing to cross-reference
  and reconcile multiple sources; non-trivial intermediate steps (data
  cleaning, analysis, calculations, verification, web search) before reaching the final
  output; dependencies on information that arrives over time.  Design tasks
  that are realistic for the role but at the challenging end of the spectrum.
- Number of deliverables depends on the user's role and seniority (not fixed).
  Senior/management roles naturally juggle more concurrent work items;
  junior or focused roles may have just 1–2.  Choose what is most realistic
  for THIS persona.
- Each deliverable is a **work package** (5–10 interrelated files), not a single doc.
- Each must go through ≥3 iterations (draft → revision → final).
- Milestones must be concrete and measurable.
- output_files list the key filenames that will be created (versions included).
- Deliverables should primarily build upon existing projects and files visible
  in the file list.  However, new projects or assignments that arrive during
  the month (e.g. from a manager or new client) are realistic and allowed —
  just ensure they fit naturally with the user's role and workload.
- **External Interaction Dependency (recommended)**: Prefer designing
  deliverables that cannot be completed using only prerequisite files and
  the user's existing filesystem.  Ideally the user should depend on ongoing
  external persona interactions to succeed — e.g. data that arrives via
  external personas, feedback loops that require revision, approvals that
  gate progress, or information gaps that force proactive clarification.
  This multi-week, multi-person, iterative nature is what distinguishes
  Daily Sim from single-shot GDP-val tasks.
- **Realistic Cognitive Complexity**: Deliverables should reflect how this
  professional actually works.  If the role naturally involves data analysis,
  the deliverable should require real computation (not hand-waved numbers).
  If the work depends on current real-world facts (market prices, regulatory
  updates, industry benchmarks), the agent should need to look them up.  If
  findings need to be communicated visually, charts and tables with actual
  workings should be produced — not just prose descriptions.  In short:
  design deliverables that are faithful to the profession's actual workflow,
  whatever that workflow entails (research, computation, drafting, review,
  visualization, etc.).  The goal is multi-hop, long-horizon tasks that
  cannot be completed in a single step.

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
- what_they_provide: brief description of what the main agent can get from this
  persona (data, feedback, approvals, domain expertise, etc.)
- communication_style description

**External personas are purely reactive.** They do NOT initiate contact.
The main agent must reach out to them when it needs information, data,
feedback, or approvals.  When contacted, a persona agent will respond
in character — sharing relevant files, answering questions, providing
feedback on submitted work, etc.  There is NO interaction_timeline.

**Types of reference files by persona role:**
| Role | Reference Files |
|------|----------------|
| Manager/Director | Quality exemplar deliverables, review checklists, process docs, templates |
| Client | Their data files, project specs, company templates |
| Direct Report | Data exports (may contain errors), draft work products, analysis templates |
| External Party | Industry standards, regulatory templates, third-party reports |

**Hidden Rubric** — **every deliverable MUST have exactly one persona with a rubric** for it.
Assign the rubric to the persona who is the natural requester/evaluator of that deliverable:
```json
{{
  "rubric": {{
    "deliverable_id": "dlv_001",
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
      "needed_by": ["dlv_001"]
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
    external_personas_json: str,
    week_num: int,
    activity_log_json: str,
    file_list_json: str,
    user_profile_summary: str,
    real_world_context: str = "",
) -> str:
    """Build prompt for Step 7: main agent plans its own week.

    Called 4 times (once per week).  The plan is from the main agent's
    perspective — it decides what to work on and when to reach out to
    external personas for help.
    """
    return f"""\
You are the main user.  Plan **your Week {week_num}** of a 4-week work month.

## Who You Are
{user_profile_summary}

## Your Monthly Objectives
{objectives_json}

## Your Collaborators
These external personas are available to you.  They are **purely reactive** —
they will NOT contact you on their own.  When you need data, feedback,
clarification, or approvals, you must proactively reach out to them.

{external_personas_json}

## What You've Done So Far
{activity_log_json if activity_log_json else "(Nothing yet — this is the start of the month.)"}

## Files on Your Disk
{file_list_json}

## Real-World Context
{real_world_context if real_world_context else "(Use your training knowledge.)"}

─────────────────────────────────────────────────────────
## YOUR TASK

Think through what you need to accomplish this week to stay on track for
your monthly milestones.  Consider:
- What deliverables need progress this week?
- What information or data do you need from collaborators?
- What drafts should you prepare for review/feedback?
- What dependencies block your work until you get answers?

Write `week_{week_num}_plan.json` **in the current working directory root** (NOT inside `drives/`). This is a simulation control file, not a user document.

**CRITICAL: valid JSON** — escape all double quotes inside string values (use `\\"` not `"`).
Use a Python or Node.js script to write the JSON to guarantee validity.

Use this structure:

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
          "type": "<deep_work|email_write|review|admin|outreach>",
          "description": "<specific description of what you do>",
          "files_to_create": ["<logical Windows path>"],
          "files_to_modify": ["<logical Windows path of existing file>"],
          "content_notes": "<detailed guidance for file generation>",
          "deliverable_id": "<if related to a multi-week deliverable>",
          "outreach_to": "<persona id, if reaching out for data/feedback/clarification>",
          "outreach_purpose": "<what you need from them>",
          "derived_from": ["<paths of files this depends on>"]
        }}
      ]
    }}
  ]
}}
```

## RULES

1. **5 working days** (Mon–Fri) for this week.
2. **3–6 activities per day**, mixing routine work with deep work.
3. **Advance deliverable milestones**: check the milestone for week {week_num}
   and plan activities that progress toward that goal.
4. **Proactive outreach**: when you need data, feedback, or approvals from a
   collaborator, schedule an `outreach` activity.  During execution, you will
   use the `contact_persona` tool to message them and get an instant reply.
   For file sharing, use `drives/share/` (outbound) and `external_share/` (inbound).
5. **Request feedback on drafts**: before finalizing a deliverable, schedule
   an outreach to the relevant reviewer/approver persona to request feedback.
   You must complete the draft BEFORE requesting review.
6. **file content_notes must be detailed**: these will be used as instructions
   for actual file generation.  Don't be vague — specify what the file should
   contain, what data to include, what format to use.
7. **files_to_modify**: when a file is being revised (v1→v2), list the
   original file path here.  The generator will read the existing file and
   produce an updated version.
8. **Each deep_work file must be ≥ GDP-val complexity level**:
   {_GDPVAL_EXAMPLES}
9. **Realistic pacing**: not every day is equally productive.  Vary naturally.

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

## Your Collaborators (external personas you can reach out to)
{external_personas_context if external_personas_context else "(No collaborators assigned.)"}

## Real-World Context
{real_world_context if real_world_context else "(Use your training knowledge.)"}

## Recent Activity Log
{activity_log_json}

## File Graph Edges (relationships)
{edges_json}
{existing_contents_section}

═══════════════════════════════════════════════════════════════════

## COMMUNICATING WITH COLLABORATORS

You are the main user agent.

**Contacting collaborators**: Use the `contact_persona` tool to send a message
and get an instant reply:
```
contact_persona(persona_id="ext_tyler", message="Hi Tyler, is the Q4 data pull ready?")
```
You can call this tool multiple times — even within a single day — for
back-and-forth conversations.

**File sharing**:
- Your filesystem: `drives/` (all your files)
- Share files out: copy to `drives/share/` BEFORE calling `contact_persona`
  (e.g. share a draft for review)
- Receive files: check `external_share/<persona_id>/` after receiving a reply

You CANNOT see: `external_refs/` (personas' private files)

**External personas are purely reactive.** They will NOT contact you first.
When you need data, feedback, clarification, or approvals, YOU must reach out
using `contact_persona`.

**FIRST THING**: Check `external_share/` for any files from personas
(from previous days' interactions).  Read them and incorporate into your work.

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
6. If the activity involves external persona interaction (email, chat,
   clarify), check `external_share/<persona_id>/` for relevant files first.

### For each file to MODIFY:
1. Read the existing file to understand its current content.
2. Make the changes described in `content_notes`.
3. Save as a new version file (e.g., `_v2`, `_revised`, `_FINAL`).
4. The modification should reflect real iterative improvement — not just
   trivial edits, but substantive changes based on feedback or new data.

### Outreach to Collaborators:
If today's plan includes an `outreach` activity, or if you need information,
data, or feedback from a collaborator, use the `contact_persona` tool.

For requesting feedback on a draft: first copy the draft to `drives/share/`,
then call `contact_persona` describing which files you want reviewed and what
kind of feedback you need.  The persona can read files in `drives/share/` and
will respond with substantive feedback.

### Activity Logging:
After processing all files AND non-file activities, append entries to
`daily_activity_log.jsonl` (one JSON object per line):

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
| `drives/share/draft_v1.docx` | `/mnt/d/share/draft_v1.docx` |
| `external_share/ext_tyler/data.xlsx` | `external_refs/ext_tyler/data.xlsx` |

In scripts: output path must be a variable like
`const outPath = 'drives/C/Users/alice/report.docx';`

Now create/modify all files and log all activities.
"""


# ===================================================================
# Step 8 Persona Agent: External Persona Response
# ===================================================================

def build_persona_response_prompt(
    persona: dict,
    interaction_context: str,
    interaction_history: list[dict],
    shared_files_from_main: list[str],
    current_day: int,
    current_date: str,
    response_seq: int = 1,
) -> str:
    """Build prompt for an external persona agent responding to the main agent.

    The persona agent can:
    - Read/reference its own files in external_refs/<persona_id>/
    - See files shared by main agent in drives/share/
    - Produce responses written to external_share/<persona_id>/
    - Share files by copying from external_refs/ to external_share/

    It CANNOT see drives/C/, drives/D/ (main agent's private filesystem)
    or other personas' files.
    """
    persona_id = persona.get("id", "unknown")
    persona_name = persona.get("name", "Unknown")

    # Build interaction history summary
    history_json = json.dumps(interaction_history, indent=2, ensure_ascii=False) if interaction_history else "[]"

    # Shared files list
    shared_files_str = "\n".join(f"  - {f}" for f in shared_files_from_main) if shared_files_from_main else "  (none)"

    # Strip rubric from persona context passed to persona agent
    persona_clean = copy.deepcopy(persona)
    persona_clean.pop("rubric", None)

    return f"""\
You are **{persona_name}**, responding in a work simulation.

## Your Identity
{json.dumps(persona_clean, indent=2, ensure_ascii=False)}

## Current Date
Day {current_day} ({current_date})

## Interaction Context
{interaction_context}

## Prior Interaction History (your exchanges with the main user)
{history_json}

## Files Shared With You by the Main User
The main user has shared the following files for you to review/use.
**Read them** using the Read tool if they are relevant to the request.
{shared_files_str}

═══════════════════════════════════════════════════════════════════

## YOUR TASK

Respond to the interaction context above **in character** as {persona_name}.

**Guidelines:**
1. Stay fully in character — use your communication style, expertise level,
   and personality as described in your profile.
2. Your response should be realistic — the length, tone, and detail level
   should match what this person would actually write/say.
3. Write your text response (email/message body) to:
   `external_share/{persona_id}/reply_day{current_day}_r{response_seq}.txt`
4. If you need to share a file with the main user (data, reports, templates),
   copy it from `external_refs/{persona_id}/` to `external_share/{persona_id}/`.
5. If you need to create a new file (e.g., a corrected data export, a
   review markup, a response memo), create it in `external_share/{persona_id}/`.
6. You can read your own files in `external_refs/{persona_id}/` to inform
   your response.
7. You can read files in `drives/share/` that the main user shared with you.
8. Do NOT access `drives/C/...`, `drives/D/...` (main user's private filesystem).

## PATH RULES
- Your text reply: `external_share/{persona_id}/reply_day{current_day}_r{response_seq}.txt`
- Your private files: `external_refs/{persona_id}/`
- Your file share: `external_share/{persona_id}/`
- Main user's shared files: `drives/share/`
- Do NOT access: `drives/C/...`, `drives/D/...`

Respond now.
"""


# ===================================================================
# Step 9: Deliverable Evaluation
# ===================================================================

def build_evaluation_prompt(
    persona: dict,
    deliverable: dict,
    interaction_history: list[dict],
    deliverable_file_paths: dict[str, str],
    reference_file_paths: list[str],
) -> str:
    """Build prompt for an evaluator persona agent to generate a GDPval-level
    granular rubric and score a deliverable.

    The evaluator receives in the prompt (for rubric generation):
    - The deliverable specification (description, milestones, expected outputs)
    - Their own preferences and priorities (high-level rubric from Step 6)
    - Full interaction history with the main agent

    The evaluator reads with tools (for rubric generation + scoring):
    - Reference files (to extract exact expected values for rubric items)
    - Deliverable files (to score against the rubric)

    Args:
        deliverable_file_paths: {logical_path: physical_path_relative_to_cwd}
        reference_file_paths: list of paths relative to cwd
    """
    persona_name = persona.get("name", "Unknown")
    persona_id = persona.get("id", "unknown")
    rubric = persona.get("rubric", {})
    rubric_json = json.dumps(rubric, indent=2, ensure_ascii=False) if rubric else "{}"

    # Build deliverable specification
    dlv_id = deliverable.get("id", "unknown")
    dlv_title = deliverable.get("title", "Unknown")
    dlv_desc = deliverable.get("description", "")
    dlv_milestones = deliverable.get("milestones", [])
    dlv_output_files = deliverable.get("output_files", [])
    milestones_text = "\n".join(
        f"  Week {m.get('week', '?')}: {m.get('goal', '')}"
        for m in dlv_milestones
    )
    output_files_text = "\n".join(f"  - {f}" for f in dlv_output_files)

    history_json = json.dumps(interaction_history, indent=2, ensure_ascii=False) if interaction_history else "[]"

    # Build deliverable file path listing
    deliv_path_lines = []
    for logical, physical in deliverable_file_paths.items():
        deliv_path_lines.append(f"  - `{physical}`  (← {logical})")
    deliv_paths_section = "\n".join(deliv_path_lines) if deliv_path_lines else "  (No deliverable files found)"

    # Build reference file path listing
    ref_path_lines = [f"  - `{p}`" for p in reference_file_paths]
    ref_paths_section = "\n".join(ref_path_lines) if ref_path_lines else "  (No reference files)"

    return f"""\
You are **{persona_name}**, evaluating a deliverable in a work simulation.

## Your Role
You are the evaluator/reviewer for this deliverable. You have worked with
the main user throughout the month — sharing data, providing feedback,
making requests, and communicating requirements. Now you must produce a
rigorous, fine-grained evaluation.

## Deliverable Specification
**ID**: {dlv_id}
**Title**: {dlv_title}
**Description**: {dlv_desc}
**Milestones**:
{milestones_text}
**Expected Output Files**:
{output_files_text}

## Your Preferences and Priorities
These are the high-level areas you care about as the evaluator. Use them
as a starting point, but your detailed rubric must go far beyond these.
{rubric_json}

## Your Full Interaction History with the Main User
This is the complete record of every message exchanged. Mine this carefully —
every correction you made, every requirement you communicated, every data
point you provided becomes a verifiable rubric item.
{history_json}

## Files You Must Read

**Your Reference Files** (data you shared, templates you provided):
{ref_paths_section}

**Deliverable Files to Evaluate**:
{deliv_paths_section}

Read ALL of these files using the Read tool before generating your rubric.
For .xlsx, .docx, and .pdf files, the Read tool will handle them correctly.

═══════════════════════════════════════════════════════════════════

## YOUR TASK

You must produce an evaluation at the granularity level of professional
benchmark rubrics (like GDPval). This means **45–65 specific, independently
verifiable items**, each with concrete expected values wherever possible.

### Phase 1: Read All Files
Read every reference file and every deliverable file listed above.
You need the reference files to know what values to expect, and the
deliverable files to verify those values.

### Phase 2: Generate Granular Rubric

Systematically derive rubric items from ALL of these sources:

**A. From the Deliverable Specification** (~5–10 items)
- Each expected output file exists and is in the correct format
- Each milestone goal is addressed in the final deliverable
- The deliverable title/scope is fully covered

**B. From Your Reference Files** (~10–15 items)
- Specific data values from your reference files are correctly used
  (e.g., "F&A rate is exactly 52.5%", "loop duration for position B-S1
  is exactly 12:00")
- Template formats and required fields are followed
- Standards and specifications from your documents are met

**C. From Interaction History** (~10–20 items)
- Every specific correction you communicated is incorporated
  (e.g., "Panel B-2 word count reduced to ≤120 words per my Feb 19 note")
- Every requirement you stated in conversation is met
- Every question you answered is reflected in the deliverable
- Agreements and decisions made during exchanges are honored
- Items you flagged as blocking or conditional are resolved

**D. From Domain Expertise** (~5–10 items)
- Professional standards for this type of deliverable
- Internal consistency (numbers add up, cross-references are correct)
- Completeness checks (all sections present, no gaps)
- Technical accuracy of claims, calculations, or data

**E. Overall Quality** (~3–5 items)
- Formatting and presentation
- Professional language and tone
- Organization and navigability

Each rubric item MUST follow this format:
```
[+N] Concrete, verifiable criterion with expected value if applicable
```

Point values:
- **+1**: Minor formatting, style, or cosmetic item
- **+2**: Substantive requirement (correct value, required section, spec compliance)
- **+5**: Critical requirement (blocking issue, major accuracy, core deliverable)

**Be specific.** BAD: "Budget is complete." GOOD: "Personnel line items include
PI (0.5 FTE), Co-PI (0.25 FTE), and Postdoc (1.0 FTE) with salary rates
matching Year 4 actuals from FARI expenditure report."

**Use exact values.** BAD: "Indirect costs are calculated correctly."
GOOD: "F&A is calculated at 52.5% of MTDC, yielding $47,250 on a $90,000
MTDC base."

### Phase 3: Score Each Item
For each rubric item:
- **Full points** if the criterion is clearly met in the deliverable
- **0 points** if not met or not present
- **Partial credit** (with explanation) only if partially addressed

Be strict. If a value is wrong, it is wrong — do not give partial credit
for "attempting" it. Partial credit is for items that are substantively
addressed but have a minor discrepancy.

### Phase 4: Write Evaluation File
Write the complete rubric and scores to `evaluation_{persona_id}_{dlv_id}.json`
**in the current working directory root** (NOT inside `drives/`):
```json
{{
  "deliverable_id": "{dlv_id}",
  "evaluator_id": "{persona_id}",
  "evaluator_name": "{persona_name}",
  "total_possible": <sum of all point values>,
  "total_earned": <sum of earned points>,
  "percentage": <round(earned/possible * 100, 1)>,
  "items": [
    {{
      "criterion": "<specific criterion text with expected value>",
      "source": "<spec|reference|interaction|expertise|quality>",
      "points_possible": N,
      "points_earned": M,
      "met": true/false/"partial",
      "notes": "<evidence from deliverable, or explanation if not met>"
    }}
  ],
  "overall_comments": "<qualitative assessment in character, 2-3 paragraphs>"
}}
```

**IMPORTANT**: You must produce at least 45 rubric items. Aim for 50–60.
Each item must be independently verifiable — no vague or subjective criteria.
Use a script to write the JSON file to ensure validity.

Generate the rubric and evaluate now.
"""
