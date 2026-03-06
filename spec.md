# PC Filesystem Simulation System Specification (Anthropic Claude Agent SDK Version, Final Chinese Draft)

> **Purpose**: Given a user persona, generate a realistic, diverse, and traceable Windows PC filesystem environment (UserWorld) to simulate user files, project structures, and historical behaviors in real-world knowledge work / office / research scenarios.
> This specification is designed for native Agent runtimes such as the **Anthropic Claude Agent SDK (Claude Code)**, and focuses on defining the **world model, fixed data structures, Cold Start initialization flow, and generation constraints**.
> The current version covers only the **Cold Start initialization phase**; incremental evolution is not discussed for now.

---

# 1. Project Overview

## 1.1 System Goal

The goal of this system is:

Given a free-text **user persona description**, generate a corresponding **Windows PC filesystem environment (UserWorld)** for that user.

This UserWorld should not be merely a collection of random files, but should resemble the state of a real user’s computer after a period of sustained use. It needs to reflect:

* who the user is and what they do
* how the user uses their computer
* the user’s file saving, naming, and organization habits
* what kinds of files are typically on the user’s computer
* where those files came from
* how files form project relationships and derivation relationships
* what the user has done in the past
* what the user is currently working on, what has been paused, and what has been continued

What this system is meant to generate is:

> **a user environment that looks like a real person has actually worked on this PC over a long period of time**

rather than:

> a static dataset that contains many files but lacks history, relationships, and behavioral logic.

---

## 1.2 System Scope

This system focuses on:

* user files and directories
* file origins
* logical relationships between files
* user workflows and behavioral history
* realism and diversity of the filesystem

This system does **not** simulate complete OS-level contents, such as:

* Program Files
* registry
* drivers
* complete software installation state
* system services

This system simulates only:

> **the user-level filesystem environment**

---

## 1.3 Core Principle: Diverse and Realistic

The two most important goals of this system are:

### 1) Diversity

Different personas and different user worlds should not produce highly repetitive filesystems.
The system must allow for:

* different file organization styles
* different disk layouts
* different project types
* different file type combinations
* different levels of messiness
* different behavior trajectories
* different collaboration patterns and work priorities

### 2) Realism

This diversity cannot be arbitrary randomness; it should reflect real-world distributions.

In other words, the system should follow:

> **biased randomness**

rather than:

* completely fixed templates
* completely unconstrained random generation

For example:

* technical users are more likely to have customized directories and multiple drives
* ordinary office users are more likely to keep the default layout
* but exceptions must be allowed for both

The ultimate goal is:

> **the results should look like different real users in the real world, rather than fake computers mass-produced from the same template.**

---

# 2. The UserWorld World Model

## 2.1 Definition of UserWorld

Each user corresponds to an independent **UserWorld**.

A UserWorld represents:

> the complete filesystem environment formed after a particular user has used a Windows PC for some period of time.

All generated files must be placed inside the sandbox of that UserWorld, and must not escape into the real filesystem outside it.

A UserWorld can be understood as consisting of the following layers:

```text
Persona
↓
User Profile
↓
Filesystem Policy
↓
Project Index (implicit)
↓
File List + File Graph
↓
Activity Log
↓
Filesystem (explicit)
```

Where:

* **Persona**: the input persona description
* **User Profile**: a more concrete and richly structured user profile
* **Filesystem Policy**: the user’s PC filesystem style and usage habits
* **Project Index**: the system’s internal project semantic layer
* **File List**: what files exist on this user’s computer
* **File Graph**: the logical relationships between those files
* **Activity Log**: what this user has done in the past
* **Filesystem**: the final materialized file and directory structure

---

## 2.2 Directory Structure of UserWorld

Each UserWorld uses the following directory structure:

```text
worlds/{world_id}/
├── persona.json
├── user_profile.json
├── filesystem_policy.json
├── project_index.json
├── file_list.json
├── file_graph.json
├── activity_log.jsonl
└── drives/
    ├── C/
    ├── D/
    ├── E/
    └── ...
```

Where:

* `persona.json`: the raw persona input
* `user_profile.json`: the concrete user profile inferred from the persona
* `filesystem_policy.json`: disk layout, default save habits, organization style, naming style, system start time, etc.
* `project_index.json`: project semantic index (internal state, not part of the user-visible filesystem)
* `file_list.json`: the current list of files in this world
* `file_graph.json`: file derivation, versioning, and cross-file dependency relationships
* `activity_log.jsonl`: time-ordered records of the user’s behavior history
* `drives/`: the actual simulated disk contents

---

## 2.3 Windows Path Model

This system must strictly use **Windows-style paths** as the logical path representation.

Correct examples:

```text
C:/Users/alice/Documents/report.docx
D:/Projects/Alpha/proposal_v2.docx
```

Constraints:

* paths must begin with a drive letter (such as `C:/`, `D:/`)
* always use forward slashes `/`
* do not use Linux-style paths
* do not use backslashes `\`

There is a mapping between logical paths and physical sandbox paths. For example:

Logical path:

```text
D:/Projects/Alpha/proposal.docx
```

Corresponding physical path:

```text
worlds/{world_id}/drives/D/Projects/Alpha/proposal.docx
```

---

## 2.4 Typical Windows User Directories

Each UserWorld should contain the typical Windows user directory:

```text
C:/Users/{username}/
```

Under this directory, the following common directories should usually exist (at least logically):

* `Desktop`
* `Documents`
* `Downloads`
* `Pictures`
* `Music`
* `Videos`
* `AppData`

For example:

```text
C:/Users/marcus/Desktop
C:/Users/marcus/Documents
C:/Users/marcus/Downloads
C:/Users/marcus/Pictures
C:/Users/marcus/AppData
```

---

# 3. Cold Start Initialization

> Cold Start refers to constructing, in one pass, a user PC environment that already “has history” for a new persona.
> The focus of the current specification is precisely this Cold Start process.

---

## 3.1 Overall Goal of Cold Start

The goal of Cold Start is not to generate a “new computer,” but to generate:

> **a computer that has already been used by this user for some period of time**

Therefore, Cold Start must construct all of the following at the same time:

* user profile
* filesystem style
* project semantic layer
* file list
* relationships between files
* the user’s past behavior history
* the final materialized file contents

The result of Cold Start should make it feel like:

* this user has already been working / living on this computer for some time
* their files have history and context
* they have ongoing projects, as well as old projects
* there are traces of downloading, receiving, editing, and deriving files
* there are also miscellaneous files unrelated to projects, but realistically present

---

## 3.2 Inputs and Outputs of Cold Start

### Input

The input to Cold Start is a **user persona**.

This persona may be simple or detailed.

A simple persona may contain only:

* a profession
* one sentence about usage habits
* one sentence about organization style

A more detailed persona may contain:

* identity / job title
* technical skill level
* interests
* common project types
* file management habits
* frequency of computer use
* software or device preferences

The system must be able to handle persona inputs of different levels of granularity.

### Output

The output of Cold Start is a complete UserWorld, including:

* `user_profile.json`
* `filesystem_policy.json`
* `project_index.json`
* `file_list.json`
* `file_graph.json`
* `activity_log.jsonl`
* actual materialized files under `drives/`

---

## 3.2.1 Time Input Constraint for Cold Start

In addition to the persona, Cold Start must also be explicitly provided with:

* `current_timestamp`

This represents the real current time at which initialization is executed, and serves as the global upper bound of time for this Cold Start run.

Therefore, Cold Start must satisfy two temporal boundary conditions:

* lower bound: `filesystem_policy.system_start_timestamp`
* upper bound: `current_timestamp`

For any file that appears in the UserWorld, the following must hold:

```text
filesystem_policy.system_start_timestamp <= file.timestamp <= current_timestamp
```

That is:

* a file’s timestamp cannot be earlier than the system start time
* a file’s timestamp cannot be later than the actual current time

These two constraints apply to:

* all file entries in `file_list.json`
* all files materialized into the filesystem
* the timestamps of corresponding behavior records in `activity_log.jsonl`

---

## 3.2.2 Target File Count Constraint for Cold Start

The target number of files in Cold Start should be controlled to:

> **no more than 100 files**

The “files” here refer to the total number of files planned in `file_list.json`, including:

* files actively created by the user
* files downloaded from the web
* shared files
* system-generated files
* binary / compressed / placeholder files

In addition, the proportions of files from different origins must not be based on a fixed template, but should be inferred from `user_profile`. That is:

> **how many are actively created by the user, how many are downloaded from the web, and how many are shared or system-generated should be simulated based on the user profile, rather than hard-coded into a uniform ratio.**

For example:

* an office worker may have more documents, spreadsheets, and downloaded forms
* a software engineer may have more code files, config files, and source archives
* a researcher may have more PDFs, notes, drafts, and reference materials
* tidy users and messy users may also differ in their proportions of downloading, retaining, extracting, and secondary processing

---

## 3.3 Overall Cold Start Flow

Cold Start follows the overall logic below:

```text
1. Persona → User Profile
2. User Profile → Filesystem Policy
3. User Profile + Filesystem Policy → Project Index
4. Jointly plan File List and File Graph (including timestamps)
5. Process files one by one in global chronological order (old → new)
   - Before processing, read recent Activity Log as context
   - Generate / download / skip according to content_mode
   - After processing, append new Activity Log
6. Finalize the complete UserWorld
```

A key point to emphasize here:

* **File List** and **File Graph** are not two strictly serial and independent stages, but two views of the same “world skeleton planning” step.
* `file_list` defines “what files exist on this user’s computer.”
* `file_graph` defines “the logical relationships, derivation relationships, and project relationships between those files.”

Therefore, when planning files, the system should simultaneously consider:

* which files belong to the same project
* which files form a version chain
* which files are produced from templates, downloaded files, archives, or shared files
* which files will become upstream inputs for other files in the future
* how these files are interleaved over time

---

# 4. Internal State File Schemas (Fixed Structure)

To ensure consistent parseability across different UserWorld instances, all internal state files must use fixed schemas.
These files are located at the root of the UserWorld and are internal system metadata, not part of the user-visible filesystem.

The following files must keep stable structures:

* `user_profile.json`
* `filesystem_policy.json`
* `project_index.json`
* `file_list.json`
* `file_graph.json`
* `activity_log.jsonl`

Across different user instances, only the following may vary:

* field values
* array lengths
* content

**Schema shape drift is not allowed.**

---

## 4.1 `user_profile.json`

`user_profile.json` is used to store the concrete user profile expanded from the persona.
It should form a **concrete, actionable, lightweight work-oriented persona profile**.

The recommended fixed structure is:

```json
{
  "identity": {
    "full_name": "Marcus Thornton",
    "username": "marcus",
    "role": "Associate Professor of Ancient History",
    "organization": "Duke University",
    "location": "Durham, NC, United States",
    "career_stage": "mid_career"
  },
  "biographical_summary": {
    "short_bio": "Marcus Thornton is a mid-career historian specializing in Roman economic and trade networks. He balances research, teaching, and administrative work, and frequently produces research notes, lecture materials, and proposal documents."
  },
  "career_profile": {
    "career_summary": "Marcus has built a career around historical research, teaching, and academic writing, with growing experience in grant-facing and conference-facing document preparation.",
    "experience_highlights": [
      "Developed multiple upper-level lecture series on Roman and Mediterranean history.",
      "Led several research proposal efforts tied to departmental and external funding opportunities.",
      "Regularly reviews student drafts and peer research materials."
    ],
    "career_history": [
      {
        "period": "2016-2019",
        "role": "Assistant Professor of Ancient History",
        "organization": "Midwest State University",
        "focus": "Teaching-focused role with course development and early-stage research output.",
        "notable_work": [
          "Built core lecture materials for Roman political history.",
          "Produced extensive teaching notes and reading summaries."
        ]
      },
      {
        "period": "2019-2023",
        "role": "Associate Professor of Ancient History",
        "organization": "Duke University",
        "focus": "Expanded into research proposals, conference participation, and collaborative academic work.",
        "notable_work": [
          "Prepared multiple conference presentations and proposal packages.",
          "Began sustained work on Roman trade and economic history."
        ]
      }
    ],
    "notable_achievements": [
      "Received internal research support for curriculum development.",
      "Presented work at multiple academic conferences.",
      "Built a reusable archive of lecture and proposal materials."
    ]
  },
  "historical_work_context": {
    "historical_focus_timeline": [
      {
        "time_range": "2023-01 to 2023-12",
        "focus": "Late Roman administrative systems",
        "notes": "Focused on teaching materials and reading summaries related to governance and administration."
      },
      {
        "time_range": "2024-01 to 2024-12",
        "focus": "Mediterranean trade routes",
        "notes": "Shifted into economic history work, producing lecture updates and proposal drafts."
      },
      {
        "time_range": "2025-01 to present",
        "focus": "Roman trade networks and comparative economic history",
        "notes": "Currently preparing proposal materials, lecture revisions, and conference-facing documents."
      }
    ]
  },
  "work_context": {
    "primary_responsibilities": [
      "research",
      "lecture preparation",
      "paper review",
      "student supervision"
    ],
    "likely_project_types": [
      "research proposal",
      "lecture preparation",
      "paper review",
      "conference presentation"
    ],
    "current_focus_areas": [
      "Roman trade networks",
      "Mediterranean economic history"
    ],
    "common_document_types": [
      "research notes",
      "lecture slides",
      "paper drafts",
      "reading summaries",
      "review comments"
    ]
  },
  "current_projects_overview": [
    {
      "project_id": "project_alpha",
      "name": "Roman Trade Proposal",
      "what_it_is": "A research proposal and presentation package on Roman trade networks.",
      "user_role": "primary author and coordinator",
      "why_it_matters": "Tied to a near-term funding and conference opportunity."
    }
  ],
  "work_style": {
    "work_patterns": [
      "writes iterative drafts",
      "frequently reuses prior materials",
      "switches across multiple active tasks",
      "reads and annotates downloaded PDFs"
    ],
    "strengths": [
      "strong at synthesizing research material",
      "good at drafting long-form documents"
    ],
    "weaknesses": [
      "less consistent with file organization",
      "may leave intermediate drafts in default folders"
    ],
    "preferred_inputs": [
      "PDF papers",
      "shared notes",
      "older drafts",
      "templates"
    ],
    "preferred_outputs": [
      "Word documents",
      "PDF summaries",
      "PowerPoint lecture slides"
    ]
  },
  "document_behavior": {
    "documents_written_well": [
      "research proposals",
      "lecture notes",
      "literature summaries"
    ],
    "documents_written_less_well": [
      "administrative forms",
      "budget spreadsheets"
    ],
    "editing_habits": [
      "often creates v2 and final versions",
      "reuses previous files as starting points"
    ],
    "naming_behavior": {
      "usually_descriptive": true,
      "sometimes_keeps_default_names": false,
      "uses_version_suffixes": true
    }
  },
  "collaboration_context": {
    "manager_relationship": "Professional, but deadlines can create tension with the department chair.",
    "peer_collaboration_style": "Frequently exchanges drafts and notes with a small set of trusted collaborators.",
    "direct_report_context": "none",
    "external_stakeholder_context": "Produces more polished summaries and slides when documents are intended for conferences or funding stakeholders."
  },
  "related_people": [
    {
      "name": "Elena Morris",
      "role": "department chair",
      "relationship": "manager",
      "context": "Reviews major proposals and teaching plans."
    }
  ],
  "external_relationships": [
    {
      "name": "Northbridge Research Foundation",
      "type": "grant sponsor",
      "relationship_to_user": "funding stakeholder",
      "relationship_to_projects": ["project_alpha"],
      "notes": "Receives proposal documents, summaries, and supporting materials."
    }
  ],
  "filesystem_relevant_traits": {
    "tech_level": "intermediate",
    "computer_usage_level": "high",
    "tidiness": "medium"
  }
}
```

---

## 4.2 `filesystem_policy.json`

`filesystem_policy.json` is used to describe the user’s filesystem behavior pattern.
It is a global planning structure and is not part of the user-visible filesystem.

The recommended fixed structure is:

```json
{
  "system_start_timestamp": "2024-03-15T09:20:00",
  "drive_layout": [
    {"letter": "C", "role": "system"},
    {"letter": "D", "role": "data"}
  ],
  "default_paths": {
    "desktop": "C:/Users/marcus/Desktop",
    "documents": "C:/Users/marcus/Documents",
    "downloads": "C:/Users/marcus/Downloads",
    "pictures": "C:/Users/marcus/Pictures",
    "appdata": "C:/Users/marcus/AppData"
  },
  "storage_patterns": {
    "office_files_usually_go_to": ["documents"],
    "downloads_usually_go_to": ["downloads"],
    "screenshots_usually_go_to": ["desktop", "pictures"],
    "project_files_usually_go_to": ["documents", "D:/Projects"],
    "temporary_files_often_end_up_in": ["desktop", "downloads"]
  },
  "organization_style": {
    "tidiness": "medium",
    "uses_project_folders": true,
    "default_folder_piling": true,
    "desktop_clutter_likelihood": "medium",
    "download_clutter_likelihood": "high"
  },
  "naming_style": {
    "is_consistent": false,
    "uses_version_suffixes": true,
    "keeps_default_filenames": true,
    "common_default_names": [
      "Document.docx",
      "Untitled.xlsx",
      "New Folder"
    ]
  },
  "usage_patterns": {
    "computer_usage_level": "high",
    "frequently_downloads_files": true,
    "frequently_creates_documents": true,
    "frequently_edits_existing_files": true,
    "frequently_switches_between_projects": true,
    "frequently_takes_screenshots": false
  }
}
```

Where:

* `system_start_timestamp`: the installation / start-of-use time of the PC environment corresponding to this UserWorld
* it is the **global lower bound** for all file timestamps

---

## 4.3 `project_index.json`

`project_index.json` is used to maintain the project semantic layer. It is an internal state file and is not part of the user-visible filesystem.

The recommended fixed structure is:

```json
{
  "projects": [
    {
      "project_id": "project_alpha",
      "name": "Roman Trade Proposal",
      "description": "A research and presentation project about Roman trade networks.",
      "tags": ["research", "history", "proposal"],
      "related_people": ["Elena Morris"],
      "related_projects": [],
      "activity_timeline": [
        {
          "start": "2024-03-01",
          "end": "2024-05-15",
          "level": "very_active"
        },
        {
          "start": "2024-05-16",
          "end": "2024-08-31",
          "level": "inactive"
        },
        {
          "start": "2024-09-01",
          "end": "2024-11-30",
          "level": "low_activity"
        },
        {
          "start": "2025-01-10",
          "end": "2025-02-28",
          "level": "active"
        }
      ]
    }
  ]
}
```

Recommended activity levels:

* `very_active`
* `active`
* `low_activity`
* `inactive`
* `completed`

---

## 4.4 `file_list.json`

`file_list.json` is used to define what files exist in the UserWorld.

The recommended fixed structure is:

```json
[
  {
    "path": "C:/Users/marcus/Documents/proposal_v1.docx",
    "timestamp": "2025-02-12T14:30:00",
    "origin": "user_created",
    "description": "First draft of a project proposal about Roman trade networks.",
    "content_mode": "generate",
    "project_ids": ["project_alpha"],
    "derived_from": [
      "C:/Users/marcus/Documents/proposal_template.docx"
    ],
    "content_generated": false
  },
  {
    "path": "C:/Users/marcus/Downloads/fw4_2025.pdf",
    "timestamp": "2025-01-08T09:10:00",
    "origin": "web_download",
    "description": "IRS W-4 tax withholding form downloaded for payroll onboarding.",
    "content_mode": "download",
    "project_ids": [],
    "derived_from": [],
    "content_generated": false
  }
]
```

Notes:

* `timestamp` is determined during the planning stage
* `origin` must reflect the file’s source
* `content_mode` must explicitly define the subsequent handling mode

---

## 4.5 `file_graph.json`

`file_graph.json` is used to describe dependencies and derivation relationships between files.

The recommended fixed structure is:

```json
{
  "nodes": [
    {
      "path": "C:/Users/marcus/Documents/proposal_template.docx",
      "project_ids": ["project_alpha"]
    },
    {
      "path": "C:/Users/marcus/Documents/proposal_v1.docx",
      "project_ids": ["project_alpha"]
    },
    {
      "path": "C:/Users/marcus/Downloads/templates_bundle.zip",
      "project_ids": []
    }
  ],
  "edges": [
    {
      "from": "C:/Users/marcus/Documents/proposal_template.docx",
      "to": "C:/Users/marcus/Documents/proposal_v1.docx",
      "type": "derived_from"
    },
    {
      "from": "C:/Users/marcus/Downloads/templates_bundle.zip",
      "to": "C:/Users/marcus/Documents/Templates/resume_template.docx",
      "type": "derived_from"
    }
  ]
}
```

Constraints:

* the graph must be a DAG
* cyclic dependencies are not allowed
* one file may have multiple upstreams
* one file may have multiple downstreams

---

## 4.6 `activity_log.jsonl`

`activity_log.jsonl` is used to record important user behavior history.
Each line is one JSON record, appended in chronological order.

The recommended fixed structure is:

```json
{
  "timestamp": "2025-02-12T14:30:00",
  "activity": "Marcus drafted the first version of a project proposal about Roman trade networks using an existing proposal template. He added the initial outline, research motivation, and key discussion points, then saved it as proposal_v1.docx in the Documents folder.",
  "related_files": [
    "C:/Users/marcus/Documents/proposal_template.docx",
    "C:/Users/marcus/Documents/proposal_v1.docx"
  ]
}
```

Notes:

* `summary` is no longer retained
* `activity` itself must be information-dense

---

# 5. From Persona to User Profile

## 5.1 Goal of User Profile

Persona is an abstract description; User Profile is a more concrete, more richly structured user profile.

The goal of this step is:

> to expand a simple persona into something that looks more like a “specific person.”

The User Profile is then used to drive:

* filesystem style
* project types
* file contents
* behavior patterns
* relationship networks
* historical work background and current priorities

---

## 5.2 Core Requirements of User Profile

The User Profile should try to answer:

* who this person is
* what they have done in the past
* what they are working on now
* what kinds of documents they usually produce
* what they are good at and what they are not good at
* who they frequently collaborate with
* why certain old files and work traces would remain on their computer

It should resemble a:

> **lightweight, work-oriented professional profile**

---

# 6. From User Profile to Filesystem Policy

## 6.1 Goal of Filesystem Policy

Once the User Profile is available, the system needs to further derive the user’s **Filesystem Policy**.

The role of Filesystem Policy is not only to define path rules, but to define:

> **this user’s filesystem behavior pattern on this PC.**

It describes:

* roughly what this user’s computer looks like
* where files are usually saved
* how the user names files
* whether the user organizes files, and when
* what kinds of typical saving and piling behaviors the user has
* when this computer begins its valid historical range

---

## 6.2 Dimensions That Filesystem Policy Should Cover

Filesystem Policy should cover at least the following:

1. disk layout
2. default directory usage habits
3. file organization habits (Tidiness)
4. naming habits
5. computer usage intensity and usage patterns
6. installation / start-of-use time (`system_start_timestamp`)

---

## 6.3 Design Requirements for Filesystem Policy

Filesystem Policy must be:

* **diverse**
* **reasonable**
* **aligned with real-world distributions**

For example:

* technical users are more likely to customize more
* ordinary office users are more likely to use default configurations
* but exceptions must be allowed in both cases

---

# 7. Project Index (Implicit Project Semantic Layer)

## 7.1 Why a Project Index Is Needed

In a real user environment, many files semantically belong to a project, but they **do not necessarily** appear in the filesystem as a neatly clustered directory set.

That is:

* a **project** is a logical concept
* a **project directory** is only one possible external organization pattern for some users

Therefore, project relationships cannot be represented solely by “whether files are in the same folder.”

---

## 7.2 Storage Location of the Project Index

The system should maintain an internal state file under the UserWorld root:

```text
project_index.json
```

This file is part of **UserWorld internal metadata** and should not be placed in the user-visible `drives/` filesystem.

---

## 7.3 Relationship Between Project Index and File Graph

* `project_index.json`: a **project-centric** semantic index
* `file_graph.json`: a **file-centric** dependency graph

The two should be stored separately and should not be merged.

---

## 7.4 Project Activity Timeline

Projects should be represented using a **time-segmented activity timeline**, rather than a single status field.

Recommended semantic levels:

* `very_active`
* `active`
* `low_activity`
* `inactive`
* `completed`

---

## 7.5 A Project Is a Semantic Cluster, Not Necessarily a Directory Cluster

The system should clearly distinguish between:

* **directory cluster**: files are physically stored together
* **project cluster**: files logically belong to the same project

For tidy users, the two may overlap heavily; for untidy users, they may be clearly separated.

---

# 8. Joint Planning of File List and File Graph

## 8.0 Timestamps Must Be Determined During the Planning Stage

In Cold Start, `file_list.json` must assign a timestamp to each file when it is generated.
Therefore, file time is not metadata appended in a later post-processing stage, but part of the world skeleton itself.

This means:

* each file’s `timestamp` must be generated during `file_list` planning
* the timestamp must satisfy the global time constraints:

  * later than `system_start_timestamp`
  * earlier than `current_timestamp`
* and it must also satisfy logical constraints:

  * child files must be later than parent files
  * newer versions must be later than older versions
  * different stages of the same project may be distributed over long periods
  * files from multiple projects may be interleaved in time

---

## 8.1 Why Joint Planning Is Necessary

After User Profile, Filesystem Policy, and Project Index are determined, the system needs to simultaneously plan:

* `file_list.json`
* `file_graph.json`

These should be treated as one joint planning phase, not as completely separate serial steps.

---

## 8.2 Role of File List

`file_list.json` defines:

> what files exist on this user’s computer.

---

## 8.3 Role of File Graph

`file_graph.json` defines:

> how those files are related, derived, and reused.

---

## 8.4 File Origins

When generating `file_list`, the system must clearly plan the origin of every file.

At a minimum, the following four categories must currently be distinguished:

### 1) `user_created`

Files created by the user.

### 2) `web_download`

Files publicly downloadable from the web.

This includes not only single files, but also:

* archives downloaded as bundled resources
* template bundles
* image asset bundles
* document collections
* installers or bundled resource packages
* public source code archives or sample project packages
* other packaged downloadable contents in `.zip` / `.rar` / `.7z` form

That is:

> **archive download is a general file origin pattern, not limited to any single user type.**

### 3) `shared`

Files sent or shared with the user by others.

### 4) `system_generated`

Files automatically generated by the system or by applications.

---

## 8.5 File Content Handling Modes

Each file must have an explicit `content_mode`:

### 1) `generate`

Content needs to be generated locally.

### 2) `download`

Content is not generated locally; it is obtained directly from the internet.

### 3) `skip`

The file is listed in the file list, but content is not populated; only a placeholder is kept.

---

## 8.5.1 Extraction and Derivation After Downloading an Archive

For archives downloaded from the web (such as `.zip`, `.rar`, `.7z`), the system should allow the following realistic scenarios:

1. **Only the archive itself is retained**
   The archive exists, but has not yet been extracted. Typically:

   * `origin = web_download`
   * `content_mode = download`

2. **The archive is downloaded and then extracted, producing a batch of derived files**
   In this case, both the original archive and the extracted file set exist in the filesystem. In this situation:

   * the archive itself is still retained as the original downloaded file
   * the extracted files enter `file_list`
   * these files should be treated as derived from the archive, and this source relationship should be reflected in `file_graph`

3. **The archive has been extracted, but the original archive has been deleted or moved**
   The user keeps only the extracted contents, while the original archive no longer exists. This is also common in real environments and should be allowed by the system.

This is a:

> **general file ingress and expansion path across user types**

and is not limited to software engineers or development scenarios.

---

## 8.6 Common File Type Distributions Should Vary by User Type

The file types generated in Cold Start should not follow a fixed template, but should be strongly influenced by the user’s profession, work content, and persona.

That is:

> **the distribution of common file types should vary dynamically based on different user types, rather than all users sharing the same file type structure.**

### For office workers / general knowledge workers

Common file types usually include:

#### Document and text types

* `.docx`
* `.txt`
* `.md`
* `.pdf`

#### Office types

* `.xlsx`
* `.pptx`

#### Image types

* `.png`
* `.jpg`
* screenshot images

#### Structured / auxiliary types

* `.csv`
* `.json`
* `.log`

#### Archive / installer / binary placeholder types

* `.zip`
* `.exe`
* other binary files

These users are typically dominated by:

> **documents, spreadsheets, presentations, PDFs, screenshots, and transactional files**

### For software engineers / development users

In addition to the general file types above, there should naturally be more development-related files, for example:

#### Source code files

* `.cpp`
* `.c`
* `.h`
* `.java`
* `.py`
* `.js`
* `.ts`
* `.go`
* `.rs`

#### Configuration and structured files

* `.json`
* `.yaml`
* `.yml`
* `.toml`
* `.xml`
* `.ini`
* `.cfg`

#### Script and tooling files

* `.sh`
* `.bat`
* `.ps1`

#### Development-related text and repository metadata

* `README.md`
* `requirements.txt`
* `Dockerfile`
* `Makefile`
* `.gitignore`

#### Logs / intermediate outputs

* `.log`
* `.csv`

These users also typically have obvious:

> **code, scripts, config files, repository files, and intermediate development artifacts**

### General Requirement

When planning file types, the system should jointly consider:

* `user_profile.work_context`
* `user_profile.common_document_types`
* `user_profile.work_style`
* `filesystem_policy`
* `project_index`

to determine what kinds of files this user is more likely to have, and their approximate proportions.

### Generality of Archives and Their Extracted Contents

Regardless of user type, the filesystem may contain:

* downloaded archives
* batches of files generated by extracting those archives
* cases where the original archive and extracted files coexist

Therefore, the system should treat the “archive → extracted contents” source chain as a common general pattern, not as something special to a particular profession.

---

## 8.7 Not All Files Belong to a Project

The system should prioritize maintaining a project semantic layer, but must clearly recognize:

> **not all files are directly related to a project.**

In real user computers, besides project-related files, there are usually many non-project files, including but not limited to:

* administrative / HR / background-check / tax-related files
* payroll, reimbursement, identity verification, and other transactional documents
* casually downloaded public materials or forms
* software installers
* screenshots, temporary notes, personal memos
* other scattered but realistically present files

For development users, non-project files may also include:

* repo archives not yet formally incorporated into the current workflow
* test scripts
* temporary config files
* standalone utility code
* source files weakly related to, or not yet categorized into, the current main project

---

# 9. Process Files One by One in Chronological Order

## 9.1 Why Processing Must Be Old to New

After `file_list` and `file_graph` are planned, the system should process files in **global chronological order**, from oldest to newest.

Reasons for processing old to new include:

* version chains must start with old files before new files
* later files can reference earlier ones
* the Activity Log can accumulate naturally as history
* the User Profile and project context become richer over time

---

## 9.2 Projects Progress in an Interleaved Manner Over Time

Real users typically work on multiple projects in parallel and alternate between them, rather than fully finishing one before starting the next.

Therefore, the system must allow:

* multi-project parallelism
* project pauses
* project resumption
* returning to old projects after long periods

And because file timestamps are determined during the `file_list` planning stage:

> **the interleaved temporal progress of projects must already be reflected in the file timestamp distribution when planning `file_list`.**

---

## 9.3 Context Mechanism When Processing Each File

When processing a given file, the system must use the existing context of the current UserWorld.

### 1) Recent Activity Log must be read before processing

To understand:

* what the user has been working on recently
* which projects are active
* which related files have been handled recently

### 2) Processing should combine file graph and file metadata

Specifically:

* `origin`
* `content_mode`
* `derived_from`
* `project_ids`

### 3) A new Activity Log entry should be written after processing

Therefore, the Activity Log is a:

> **read-before-write memory layer**

---

## 9.4 Handling of Different Content Modes

### `generate`

Generate content locally.

### `download`

Obtain content directly online.

### `skip`

Only keep the file’s existence, without expanding or populating content.

---

# 10. Activity Log (Behavior Memory Layer)

## 10.1 Role of the Activity Log

The system must maintain `activity_log.jsonl` to record important user operation history.

Its functions are:

* to record what the user did previously
* to provide a compressed representation of the user’s historical behavior and work trajectory
* to provide context for later generation
* to help the system understand which projects are currently active and what has been done in the past

---

## 10.2 Core Requirements of the Activity Log

The Activity Log must not simply record atomic actions.

Not recommended:

* “saved a file”
* “edited a document”
* “downloaded a PDF”

Each Activity Log entry should, as much as possible, explain at least:

1. what task the user was working on
2. which file was operated on
3. what the file was roughly about
4. whether it was created, edited, downloaded, derived, or continued from an old project
5. if modified, what key content was changed
6. which existing files or projects it relates to

---

## 10.3 Example

```json
{
  "timestamp": "2025-02-12T14:30:00",
  "activity": "Marcus revised the second draft of the project proposal about Roman trade networks. He expanded the research background, clarified the timeline and budget assumptions, and reorganized the structure based on the earlier draft and template before saving it as proposal_v2.docx.",
  "related_files": [
    "C:/Users/marcus/Documents/proposal_template.docx",
    "C:/Users/marcus/Documents/proposal_v1.docx",
    "C:/Users/marcus/Documents/proposal_v2.docx"
  ]
}
```

---

## 10.4 Length Limit of the Activity Log

Recommended:

* keep the most recent 100 entries
* once exceeded, discard the oldest records

---

# 11. Time Consistency Constraints

The entire Cold Start must satisfy unified time consistency requirements:

1. all file timestamps must be after the system start time
2. all file timestamps must be before the actual current time
3. all derivation relationships must satisfy temporal causality
4. all Activity Log records must be time-consistent with their corresponding files
5. the project activity timeline, file time distribution, and behavior log order must be mutually consistent

This ensures that the final UserWorld is not merely “a set of files,” but a self-consistent historical timeline.

---

# 12. Final Output of Cold Start

When Cold Start is complete, the UserWorld should contain at least the following:

1. a more concrete `User Profile`
2. a clearly defined `Filesystem Policy`
3. a complete `Project Index`
4. a complete `File List`
5. a clear `File Graph`
6. a readable and usable `Activity Log`
7. real materialized filesystem contents

In other words, the world after Cold Start should not merely be:

> “there are many files”

but rather:

> **a real working environment with a user, history, files, relationships, and behavioral traces**

---

# 13. Summary of Design Principles

At the current stage, the system must follow these key principles:

1. **Build the person first, then the computer, then the files.**
2. **The filesystem must be diverse and realistic.**
3. **The User Profile must be sufficiently concrete.**
4. **The Filesystem Policy must include the system start time.**
5. **Cold Start must explicitly receive the current time.**
6. **The target file count for Cold Start must not exceed 100.**
7. **The proportions of files from different origins should be inferred from `user_profile`.**
8. **A Project is a semantic layer, not the same as a directory structure.**
9. **Project Index is internal state, not a user file.**
10. **File List and File Graph must be planned jointly.**
11. **File timestamps must be determined during the planning stage.**
12. **Files must distinguish their origins.**
13. **Files must distinguish their content handling modes.**
14. **Public web files should preferably be downloaded directly.**
15. **Binary files may exist, but do not need to be populated.**
16. **Archive download and extraction-derived files are a cross-user-type general pattern.**
17. **Not all files belong to a project.**
18. **Projects are logically continuous but temporally interleaved.**
19. **When processing files, the Activity Log must be read before writing.**
20. **The Activity Log must be information-dense.**
21. **The goal of Cold Start is to establish a realistic user PC world with existing history and temporal consistency.**

---

# 14. Current Version Conclusion

The focus of the current version is to clearly define **Cold Start initialization**:

* what the input is
* how the system progressively abstracts from persona to profile, policy, project index, file list, and file graph
* what file origins exist
* which files should be generated, which should be downloaded, and which should be skipped
* how file count and origin proportions are constrained by the user profile
* how temporal boundaries constrain the entire world
* why an information-rich activity log must be maintained
* why the final result should be a “real user environment with existing history”

In short:

> At the current stage, the core is not “generate a few files,” but rather **to establish, in one pass, a credible, temporally self-consistent, user-characteristic-driven PC world**.
