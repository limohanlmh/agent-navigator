from __future__ import annotations


GENERATED_START = "<!-- agent-policy:start -->"
GENERATED_END = "<!-- agent-policy:end -->"


REQUIRED_DIRS = [
    ".agent-policy/imports/raw",
]

ADAPTER_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    ".kiro/steering/agent-policy.md",
}


BASE_FILE_TEMPLATES: dict[str, str] = {
    ".agent-policy/current.md": """# Current Agent Guidance

This file stores compact project guidance and enabled task-layer selections that should be considered whenever this project scope becomes relevant.
General retrieval and maintenance behavior lives in the generated agent adapter files.

Guidance in this file may still be conditional and remains subject to the policy priority rules.
Current explicit user instruction overrides this file and prior experience unless safety, data integrity, or an explicit project rule is involved.
User and task policy is selected during retrieval; it is not copied into the project.

Do not use this file for project knowledge, task status, handoff history, execution logs, or one-off investigation results.
Store stable reusable project facts in `knowledge.md`.

## Project guidance

No additional project-specific guidance has been recorded here yet.
""",
    ".agent-policy/knowledge.md": """# Project Knowledge

Stable project-local facts that may materially help future work.

Search this file only when the current task may need project knowledge; do not load it by default.
If targeted search finds nothing, reading the full file is the final fallback. Keep only genuinely relevant content in the working context.

Store durable facts such as architecture, component ownership, interfaces, data relationships, configuration semantics, and pointers to authoritative project documentation.
Do not use this file for project guidance, task status, handoff history, execution logs, or one-off investigation results.
Put project guidance in `current.md`, reusable workflows in `playbooks.md`, and learned behavior in `lessons.md` or `heuristics.md`.

Before adding content, search for an existing related section and update it when appropriate.
Keep headings short and searchable.
""",
    ".agent-policy/lessons.md": """# Lessons

Core memory for reusable project experience. Keep entries short, searchable, and concrete.

Write to this file only when the signal has a reusable future behavior.
A good lesson should answer what signal triggered it, what reusable takeaway was learned, and what a future agent should do differently.
If any of those are unclear, write the signal to `inbox.md` instead.
Do not use this file as a full audit log.
Before adding a new entry, search existing lessons and heuristics; update a close match instead of appending a near-duplicate.

When adding a lesson, use a short one-line human-readable title.
Do not use long sentence headings. Put details in Signal / Lesson / Next time.

Entry format:

## YYYY-MM-DD — Short lesson title

Type: lesson | preference | positive | negative | observation
Applies to: code review, document comparison, implementation planning, etc.
Keywords: git status, unstaged changes, review scope, source attribution, etc.
Signal: Raw user signal or imported-note signal.
Lesson: Reusable lesson in one or two sentences.
Next time: Concrete behavior future agents should consider.
Status: active | candidate
""",
    ".agent-policy/heuristics.md": """# Heuristics

Reusable search, planning, action-selection, and output-structure guidance.
Heuristics guide agents toward promising context and actions; they are not hard rules.

Write to this file only when the entry changes future search, planning, action selection, or output structure.
Before adding a new entry, search existing heuristics and lessons; update a close match instead of appending a near-duplicate.
`Search bias` is optional. Use it when it adds a concrete inspection, retrieval, or action priority not already clear from the heuristic.

Entry format:

## Short heuristic title

Applies to: code review, trading review, document comparison, implementation planning
Keywords: git status, unstaged changes, review scope
Source: user correction | positive feedback | imported note | project discussion | repeated pattern
Status: active | candidate

### Heuristic

One or two sentences describing the search/planning/output guidance.

### Search bias

Optional: what should agents inspect, retrieve, prioritize, or structure earlier because of this heuristic?

### Avoids

What failure mode or wasted search path does this avoid?
""",
    ".agent-policy/playbooks.md": """# Playbooks

Project-specific stable workflows learned or confirmed in this repository.
Generic cross-project task guidance and base workflows belong in `~/.agent-policy/tasks/<task-id>.md`.
Write a playbook only when explicit instruction or repeated experience establishes a reusable sequence whose order or checkpoints matter.
Keep one-off task traces in `lessons.md` or `inbox.md`. Search existing playbooks before adding a near-duplicate.
Keep this file small and easy to search.

Entry format for real entries:

    ## Short task name

    Aliases:
    Keywords: include a stable English task id when one applies

    Steps:
    1. ...
    2. ...
""",
    ".agent-policy/inbox.md": """# Inbox

Raw, uncertain, or not-yet-promoted signals live here until they become lessons.
This is not an audit log for every accepted lesson or heuristic; clear complete signals may go directly to `lessons.md` or `heuristics.md`.
""",
    "AGENTS.md": "",
    "CLAUDE.md": "",
    ".kiro/steering/agent-policy.md": "",
}


GLOBAL_FILE_TEMPLATES: dict[str, str] = {
    "profile.md": """# Agent Policy Profile

Long-lived user preferences, working habits, and cross-project guidance.
Keep this private unless the user explicitly decides otherwise.
""",
    "heuristics.md": """# Global Heuristics

Reusable cross-project heuristics for search, planning, action selection, and output structure.

Entry format:

## Short heuristic title

Applies to: code review, research, document analysis, implementation planning
Keywords: source attribution, scope, concise output
Source: user preference | repeated pattern | cross-project lesson
Status: active | candidate

### Heuristic

One or two sentences describing the guidance.

### Search bias

Optional: what should agents inspect, retrieve, prioritize, or structure earlier?

### Avoids

What failure mode or wasted path does this avoid?
""",
}


LEGACY_PATHS = [
    ".agent-policy/brief.md",
    ".agent-policy/assets",
    ".agent-policy/patches",
    ".agent-policy/reviews",
    ".agent-policy/indexes",
    ".agent-policy/examples",
    ".agent-policy/templates",
    ".agent-policy/sources",
    ".agent-policy/adapters",
    ".agent-policy/imports/processed",
    ".agent-policy/manifest.yaml",
    ".agents/skills",
]


def expected_files() -> list[str]:
    return list(BASE_FILE_TEMPLATES.keys())


def initial_template_for(relative: str) -> str:
    if relative == "AGENTS.md":
        return render_agents_md()
    if relative == "CLAUDE.md":
        return render_claude_md()
    if relative == ".kiro/steering/agent-policy.md":
        return render_kiro_steering()
    return BASE_FILE_TEMPLATES[relative]


def generated_block(body: str) -> str:
    return f"{GENERATED_START}\n{body.strip()}\n{GENERATED_END}\n"


def render_agents_md() -> str:
    return render_agent_guidance(
        "Agent Guidance",
        "This repository uses `.agent-policy/` as a lightweight project-local experience layer.",
    )


def render_claude_md() -> str:
    return render_agent_guidance(
        "Claude Code Agent Policy",
        "Use `.agent-policy/` as the compact project experience layer for this repository.",
    )


def render_kiro_steering() -> str:
    return render_agent_guidance(
        "Kiro Steering: Agent Policy",
        "This project keeps a compact agent experience layer in `.agent-policy/`.",
    )


def render_agent_guidance(title: str, intro: str) -> str:
    return generated_block(
        f"""# {title}

{intro}
Optional private user and task guidance may live under `~/.agent-policy/`; higher-layer policy is selected during retrieval, not copied into the repository.
Treat the layers as a retrieval-overlay policy stack rather than inherited files copied during initialization.

## Policy Layers

1. Current user instruction in the conversation.
2. Project layer(s): each project scope may provide its own `.agent-policy/current.md`, `knowledge.md`, `heuristics.md`, `lessons.md`, and project-specific `playbooks.md`. A task may involve more than one project scope, and each project layer applies only within its own scope.
3. Task layer: generic cross-project guidance and base workflows from an explicit or enabled `~/.agent-policy/tasks/<task-id>.md`.
4. User layer: `~/.agent-policy/profile.md` and `~/.agent-policy/heuristics.md`.
5. Historical lessons relevant to the current task. Candidate heuristics are considered only when explicitly requested or being evaluated.

Inheritance happens during retrieval. Do not copy task or user policy into project files.

## At Task Start

1. When a project scope becomes relevant, read its local agent guidance and `.agent-policy/current.md` if they exist, even if they appeared after the conversation began.
2. Resolve priority for the project scope currently being acted on as: current user instruction, that project's guidance, explicit or enabled task guidance, user guidance, then relevant historical lessons. Consider candidate heuristics only when explicitly requested or being evaluated.
3. When project knowledge or prior experience may matter, use the same current-task context to search the relevant project scope's `knowledge.md`, `heuristics.md`, `lessons.md`, and `playbooks.md` directly, plus the optional user files when available. One entry type does not need to lead to another. If targeted search finds no useful match and relevant material may still exist, read the relevant file in full as a final fallback, but retain only materially relevant content in the working context.
4. Retrieve task guidance only from a task layer explicitly named by the user or enabled in `current.md`; do not scan every `~/.agent-policy/tasks/*.md` file.
5. Use the user's wording, Task ID, Display name, Aliases, Keywords, and project context to judge relevance.
6. Retrieve only items that can materially affect the current task. Do not add filler guidance; keep the working context compact.

## Priority

Current explicit user instruction overrides prior experience. Within a project scope, that project's guidance, including a project-specific playbook, overrides generic task or user guidance unless the user says otherwise.

## During Work

- Complete the user's actual task or fix the immediate issue first.
- Do not interrupt ordinary work just to maintain the experience layer, and do not ask the user to run policy maintenance commands during normal work.
- When work spans project scopes, apply and maintain each project's local guidance within its own scope; do not treat the starting project as the scope for the whole task.
- When a relevant project scope does not yet have `.agent-policy/`, initialize it explicitly with `agent-navi init --target <project-root>` before maintaining project guidance there.
- When a clear, stable, reusable signal forms within the current conversation context, record it at a natural pause. Brief acknowledgements and continuation requests normally continue the existing context.
- Constraints on task artifacts apply to those outputs by default; they do not disable `.agent-policy/` maintenance unless the user explicitly says not to update it.

## Maintain Experience

1. Keep the current experience set accurate and compact. Search existing knowledge, lessons, heuristics, and playbooks before adding an entry.
2. A close match identifies where to compare; it does not prove that the new signal is already covered. Update the closest entry when the new signal changes its scope, exceptions, future behavior, failure mode, or an example that changes its interpretation. If there is no reusable change, do not write.
3. Use `current.md` only for compact project guidance and enabled task-layer selections that should be considered whenever the project scope becomes relevant. Store stable descriptive project facts in `knowledge.md`, and retrieve them only when relevant.
4. Write to `knowledge.md` only when a stable project fact may materially help future work. Do not use it for task status, handoff history, execution logs, or one-off results.
5. Write to `lessons.md` only when the signal, reusable takeaway, and future behavior are all clear.
6. Write to `heuristics.md` only when the entry changes future search, planning, action selection, failure avoidance, or output structure. A separate `Search bias` is optional and should add a concrete priority rather than repeat the heuristic.
7. Write to project `playbooks.md` only when explicit instruction or repeated experience establishes a reusable project workflow whose order or checkpoints matter. A generic cross-project base workflow belongs in the relevant task file instead.
8. Use `inbox.md` when the signal, takeaway, stability, or write target remains unclear.
9. Write agent-authored policy prose and descriptive metadata in English, preserve identifiers exactly, and use a short one-line title with detail in the entry fields.
10. Complete, low-risk project knowledge, lessons, and heuristics may be maintained quietly. A project playbook requires a clear stable workflow, not merely a successful one-off sequence.
11. Task or user guidance may be updated when user intent is explicit, scope is clear, confidence is high, risk is low, and no conflict exists. Ask when those conditions are not met or the change affects a long-lived user preference.
12. After an interruption, use the conversation context still available and the experience already written to files; do not assume unwritten history can be recovered.

## Experience Maintenance Judgment

Before finishing, review the relevant context in the current conversation, not only the latest message, for a clear reusable change to future behavior or stable project knowledge that may materially help future work. If none exists, leave the experience files unchanged. When a change exists, update only the smallest relevant set of current guidance, knowledge, inbox, lesson, heuristic, or playbook entries; use more than one only when each serves a distinct purpose. Do not use these files as an audit log.

The CLI is a deterministic Markdown helper, not a semantic retrieval or classification engine. Agents may edit the files directly or use `agent-navi replace-entry` for an exact project knowledge, lesson, heuristic, or playbook heading. Use ordinary user-facing language when mentioning maintenance; avoid internal implementation terms unless the user asks about them.
"""
    )
