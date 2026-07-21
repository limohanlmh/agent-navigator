from __future__ import annotations

import difflib
import glob
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import (
    append_text,
    copy_file,
    ensure_safe_directory,
    now_human,
    now_stamp,
    now_utc,
    require_policy,
    resolve_target,
    slugify,
    update_text,
    write_text,
)
from .templates import (
    ADAPTER_PATHS,
    GENERATED_END,
    GENERATED_START,
    GLOBAL_FILE_TEMPLATES,
    LEGACY_PATHS,
    REQUIRED_DIRS,
    expected_files,
    initial_template_for,
    render_agents_md,
    render_claude_md,
    render_kiro_steering,
)


LESSON_TYPES = {"lesson", "preference", "positive", "negative", "observation"}
FEEDBACK_TYPES = LESSON_TYPES | {"heuristic"}
FEEDBACK_STATUSES = {"active", "candidate"}
HEURISTIC_STATUSES = FEEDBACK_STATUSES
TASK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
GITIGNORE_LINES = [
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".DS_Store",
    "~$*.docx",
    "build/",
    "*.egg-info/",
    "",
    "# Generated temporary Agent Navigator files",
    ".agent-policy/brief.md",
    ".agent-policy/lessons.compact.md",
    ".agent-policy/heuristics.compact.md",
    ".agent-policy/local.md",
]
LEGACY_AGENT_GUIDANCE_NAMES = {"agent.md"}
REPLACEABLE_ENTRY_FILES = {
    "lessons": "lessons.md",
    "heuristics": "heuristics.md",
    "playbooks": "playbooks.md",
}
INLINE_FIELD_NAMES = {
    "Aliases",
    "Applies to",
    "Avoids",
    "Display name",
    "Guidance",
    "Heuristic",
    "Keywords",
    "Lesson",
    "Next time",
    "Search bias",
    "Signal",
    "Source",
    "Status",
    "Summary",
    "Task ID",
    "Type",
}


@dataclass
class CommandResult:
    message: str
    code: int = 0


@dataclass
class LessonEntry:
    heading: str
    entry_type: str
    applies_to: str
    keywords: str
    signal: str
    lesson: str
    next_time: str
    status: str
    raw: str
    order: int


@dataclass
class HeuristicEntry:
    heading: str
    applies_to: str
    keywords: str
    source: str
    heuristic: str
    search_bias: str
    avoids: str
    status: str
    raw: str
    order: int
    layer: str = "project"


@dataclass
class PlaybookEntry:
    title: str
    aliases: str
    keywords: str
    body: str
    order: int


@dataclass
class PolicyEntry:
    title: str
    keywords: str
    body: str
    order: int
    layer: str


@dataclass
class BriefItem:
    kind: str
    title: str
    text: str
    match_level: str
    order: int
    layer: str = "project"
    status: str = "active"


@dataclass
class RetrievalContext:
    query_terms: set[str]
    task_terms: set[str]


def init_policy(target: str = ".", force: bool = False, global_policy: bool = False, interactive: bool = False) -> CommandResult:
    if global_policy:
        return init_global_policy(force=force)

    repo = resolve_target(target)
    root = repo / ".agent-policy"
    repo.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []

    for directory in REQUIRED_DIRS:
        path = repo / directory
        existed = path.exists()
        ensure_safe_directory(path, root=repo)
        if existed:
            skipped.append(directory + "/")
        else:
            created.append(directory + "/")

    for relative in expected_files():
        path = repo / relative
        if relative in ADAPTER_PATHS:
            write_adapter(path, initial_template_for(relative), force=force, root=repo)
            created.append(relative)
            continue
        if write_text(path, initial_template_for(relative), force=False, root=repo):
            created.append(relative)
        else:
            skipped.append(relative)

    updated_legacy, pending_legacy = handle_legacy_agent_guidance(repo, root)
    gitignore_result = ensure_gitignore(repo)
    if gitignore_result:
        created.append(gitignore_result)

    legacy = [relative for relative in LEGACY_PATHS if (repo / relative).exists()]
    lines = [f"Initialized Agent Navigator experience layer at {repo}"]
    if created:
        lines.append("Created/updated:")
        lines.extend(f"- {item}" for item in created)
    if skipped:
        lines.append("Skipped:")
        lines.extend(f"- {item}" for item in skipped)
    if updated_legacy:
        lines.append("Updated generated legacy agent guidance:")
        lines.extend(f"- {item}" for item in updated_legacy)
    if pending_legacy:
        lines.append("Legacy agent guidance left in place for migration:")
        lines.extend(f"- {item}" for item in pending_legacy)
    if legacy:
        lines.append("Legacy paths left in place; new commands do not use them:")
        lines.extend(f"- {item}" for item in legacy)
    if interactive:
        setup_message = interactive_project_setup(root)
        if setup_message:
            lines.append(setup_message)
    return CommandResult("\n".join(lines))


def init_global_policy(force: bool = False) -> CommandResult:
    root = global_policy_root()
    created: list[str] = []
    skipped: list[str] = []
    ensure_safe_directory(root, root=root, mode=0o700)
    tasks_dir = root / "tasks"
    tasks_existed = tasks_dir.exists()
    ensure_safe_directory(tasks_dir, root=root, mode=0o700)
    if tasks_existed:
        skipped.append("tasks/")
    else:
        created.append("tasks/")

    for relative, content in GLOBAL_FILE_TEMPLATES.items():
        path = root / relative
        if write_text(path, content, force=False, root=root, mode=0o600):
            created.append(relative)
        else:
            skipped.append(relative)

    lines = [f"Initialized global Agent Navigator layer at {root}"]
    if created:
        lines.append("Created/updated:")
        lines.extend(f"- {item}" for item in created)
    if skipped:
        lines.append("Skipped:")
        lines.extend(f"- {item}" for item in skipped)
    return CommandResult("\n".join(lines))


def handle_legacy_agent_guidance(repo: Path, root: Path) -> tuple[list[str], list[str]]:
    updated_generated: list[str] = []
    pending_migration: list[str] = []
    for path in legacy_agent_guidance_files(repo):
        existing = read_optional(path)
        if GENERATED_START in existing and GENERATED_END in existing:
            write_adapter(path, render_agents_md(), force=False, root=repo)
            updated_generated.append(path.name)
            continue
        if record_legacy_agent_migration(root, path.name):
            pending_migration.append(path.name)
    return updated_generated, pending_migration


def legacy_agent_guidance_files(repo: Path) -> list[Path]:
    if not repo.exists():
        return []
    candidates = [
        path
        for path in repo.iterdir()
        if path.is_file() and path.name.lower() in LEGACY_AGENT_GUIDANCE_NAMES
    ]
    return sorted(candidates, key=lambda path: path.name.lower())


def record_legacy_agent_migration(root: Path, filename: str) -> bool:
    inbox = root / "inbox.md"
    source_marker = f"Source: `{filename}`"
    date = now_utc().strftime("%Y-%m-%d")
    entry = "\n".join(
        [
            f"## {date} — Legacy agent guidance pending migration",
            "",
            "Type: import",
            source_marker,
            "Signal: Existing root-level agent guidance was found during init.",
            "Lesson: Treat custom legacy agent guidance as a source to migrate, not content to overwrite automatically.",
            "Next time: Read the legacy file, promote stable reusable guidance into `.agent-policy/current.md`, `heuristics.md`, `lessons.md`, or `playbooks.md`, and keep or remove the legacy file only after user confirmation.",
            "Status: candidate",
        ]
    )
    added = False

    def add_once(existing: str) -> str:
        nonlocal added
        if "Legacy agent guidance pending migration" in existing and source_marker in existing:
            return existing
        added = True
        if existing.strip():
            return existing.rstrip() + "\n\n" + entry
        return entry

    update_text(inbox, add_once, root=root)
    return added


def setup_task_layers(target: str, tasks: list[str], display: str = "") -> CommandResult:
    root = require_policy(target)
    task_ids = [normalize_task_id(task) for task in tasks if task and task.strip()]
    if not task_ids:
        return CommandResult("Nothing to set up. Pass one or more `--task <task-id>` values.", code=2)
    if display and len(task_ids) != 1:
        return CommandResult("`--display` can only be used when enabling one `--task <task-id>`.", code=2)
    for task_id in task_ids:
        validate_task_id(task_id)

    created_task_files: list[Path] = []
    for task_id in task_ids:
        task_path = global_policy_root() / "tasks" / f"{task_id}.md"
        existed = task_path.exists()
        task_display = " ".join(display.split()) if display and len(task_ids) == 1 else ""
        ensured = ensure_global_task_file(task_id, task_display)
        if not existed:
            created_task_files.append(ensured)

    merged: dict[str, str] = {}

    def merge_task_layers(current_text: str) -> str:
        nonlocal merged
        existing = enabled_task_layers_from_text(current_text)
        merged = {slug: display_name for slug, display_name in existing}
        for task_id in task_ids:
            if display:
                merged[task_id] = " ".join(display.split())
            elif task_id not in merged:
                merged[task_id] = ""
        section_lines = [
            "These task layers are selected during retrieval/brief generation. They are not copied into the project.",
            "",
        ]
        for slug, display_name in merged.items():
            label = f"{slug} — {display_name}" if display_name else slug
            section_lines.append(f"- {label} (`~/.agent-policy/tasks/{slug}.md`)")
        return replace_markdown_section(current_text, "Enabled task layers", section_lines)

    update_text(root / "current.md", merge_task_layers, root=root)

    lines = ["Recorded enabled task layer(s) in .agent-policy/current.md:"]
    for slug, display_name in merged.items():
        label = f"{slug} — {display_name}" if display_name else slug
        lines.append(f"- {label} -> ~/.agent-policy/tasks/{slug}.md")
    if created_task_files:
        lines.append("Created task policy file(s):")
        lines.extend(f"- {path}" for path in created_task_files)
    return CommandResult("\n".join(lines))


def add_feedback(
    target: str,
    text: str | None = None,
    entry_type: str = "lesson",
    applies_to: str = "general",
    keywords: str = "",
    title: str = "",
    signal: str = "",
    lesson: str = "",
    next_time: str = "",
    status: str | None = None,
    inbox: bool = False,
) -> CommandResult:
    if entry_type not in FEEDBACK_TYPES:
        raise SystemExit(f"Invalid feedback type: {entry_type}")
    if status is not None and status not in FEEDBACK_STATUSES:
        raise SystemExit(f"Invalid feedback status: {status}")

    root = require_policy(target)
    raw_text = (text or "").strip()
    signal = signal.strip() or raw_text or "TBD"
    lesson = lesson.strip()
    next_time = next_time.strip()
    keywords = keywords.strip()
    title = title.strip()
    applies_to = applies_to.strip() or "general"

    complete_lesson = bool(lesson and next_time)
    if inbox or not complete_lesson:
        entry_status = status or "candidate"
        if entry_status == "active":
            entry_status = "candidate"
        entry = render_inbox_feedback_entry(
            entry_type=entry_type,
            applies_to=applies_to,
            keywords=keywords,
            title=title,
            signal=signal,
            lesson=lesson,
            next_time=next_time,
            status=entry_status,
        )
        append_text(root / "inbox.md", entry, root=root)
        return CommandResult("Recorded feedback in .agent-policy/inbox.md")

    entry_status = status or "active"
    entry = render_feedback_entry(
        entry_type=entry_type,
        applies_to=applies_to,
        keywords=keywords,
        title=title,
        signal=signal,
        lesson=lesson,
        next_time=next_time,
        status=entry_status,
    )
    append_text(root / "lessons.md", entry, root=root)
    return CommandResult("Recorded feedback in .agent-policy/lessons.md")


def add_heuristic(
    target: str,
    title: str = "",
    applies_to: str = "general",
    keywords: str = "",
    source: str = "",
    heuristic: str = "",
    search_bias: str = "",
    avoids: str = "",
    status: str | None = None,
    global_target: bool = False,
    task: str = "",
    dry_run: bool = False,
) -> CommandResult:
    if status is not None and status not in HEURISTIC_STATUSES:
        raise SystemExit(f"Invalid heuristic status: {status}")
    if global_target and task:
        raise SystemExit("Choose only one heuristic destination: `--global` or `--task <task-id>`.")

    title = " ".join(title.split())
    applies_to = applies_to.strip() or "general"
    keywords = keywords.strip()
    source = source.strip() or "project discussion"
    heuristic = heuristic.strip()
    search_bias = search_bias.strip()
    avoids = avoids.strip()
    complete = bool(title and heuristic)
    if not complete:
        entry_status = status or "candidate"
        if entry_status == "active":
            entry_status = "candidate"
        root = require_policy(target)
        note = render_incomplete_heuristic_note(
            title=title,
            applies_to=applies_to,
            keywords=keywords,
            source=source,
            heuristic=heuristic,
            search_bias=search_bias,
            avoids=avoids,
            status=entry_status,
        )
        if dry_run:
            return CommandResult(render_dry_run(root / "inbox.md", note))
        append_text(root / "inbox.md", note, root=root)
        return CommandResult("Recorded incomplete heuristic signal in .agent-policy/inbox.md")

    entry_status = status or "active"
    entry = render_heuristic_entry(
        title=title,
        applies_to=applies_to,
        keywords=keywords,
        source=source,
        heuristic=heuristic,
        search_bias=search_bias,
        avoids=avoids,
        status=entry_status,
    )

    if task:
        task_id = normalize_task_id(task)
        validate_task_id(task_id)
        destination = global_policy_root() / "tasks" / f"{task_id}.md"
        if dry_run:
            return CommandResult(render_dry_run(destination, entry))
        destination = ensure_global_task_file(task_id)
        fill_empty_task_metadata(
            destination,
            display_name=applies_to if applies_to != "general" else "",
            keywords=keywords,
        )
        append_text(destination, entry, root=global_policy_root(), mode=0o600)
        return CommandResult(f"Recorded heuristic in {destination}")
    if global_target:
        destination = global_policy_root() / "heuristics.md"
        if dry_run:
            return CommandResult(render_dry_run(destination, entry))
        root = ensure_global_policy()
        append_text(root / "heuristics.md", entry, root=root, mode=0o600)
        return CommandResult(f"Recorded heuristic in {root / 'heuristics.md'}")

    root = require_policy(target)
    if dry_run:
        return CommandResult(render_dry_run(root / "heuristics.md", entry))
    append_text(root / "heuristics.md", entry, root=root)
    return CommandResult("Recorded heuristic in .agent-policy/heuristics.md")


def replace_entry(
    target: str,
    entry_file: str,
    heading: str,
    source: str,
    dry_run: bool = False,
) -> CommandResult:
    root = require_policy(target)
    filename = REPLACEABLE_ENTRY_FILES.get(entry_file)
    if filename is None:
        choices = ", ".join(f"`{name}`" for name in REPLACEABLE_ENTRY_FILES)
        raise SystemExit(f"Replaceable file must be one of: {choices}.")

    exact_heading = heading.strip()
    if not exact_heading:
        raise SystemExit("An exact `--heading` is required.")

    destination = root / filename
    source_path = resolve_input_file(target, source)
    replacement = source_path.read_text(encoding="utf-8").strip()
    replacement_blocks = markdown_h2_blocks(replacement)
    if len(replacement_blocks) != 1 or replacement[: replacement_blocks[0][1]].strip():
        return CommandResult("Replacement file must contain exactly one Markdown `##` entry.", code=2)

    def build_update(original: str) -> tuple[str, str]:
        matches = [block for block in markdown_h2_blocks(original) if block[0] == exact_heading]
        if not matches:
            return original, f"Exact heading not found in .agent-policy/{filename}: {exact_heading}"
        if len(matches) > 1:
            return (
                original,
                f"Exact heading occurs {len(matches)} times in .agent-policy/{filename}; "
                f"no files changed: {exact_heading}",
            )
        _, start, end = matches[0]
        replacement_text = replacement + "\n"
        if end < len(original):
            replacement_text += "\n"
        return original[:start] + replacement_text + original[end:], ""

    if dry_run:
        original = read_optional(destination)
        updated, error = build_update(original)
        if error:
            return CommandResult(error, code=2)
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(destination),
                tofile=str(destination),
            )
        )
        return CommandResult("Dry run: no files changed.\n" + (diff or "No textual change."))

    error_message = ""

    def transform(original: str) -> str:
        nonlocal error_message
        updated, error_message = build_update(original)
        return updated

    update_text(destination, transform, root=root)
    if error_message:
        return CommandResult(error_message, code=2)
    return CommandResult(f"Replaced exact entry in .agent-policy/{filename}: {exact_heading}")


def import_sources(
    target: str,
    source_paths: list[str],
    applies_to: str = "general",
) -> CommandResult:
    root = require_policy(target)
    repo = root.parent
    raw_dir = root / "imports" / "raw"
    imported: list[Path] = []

    for source in expand_source_paths(repo, source_paths):
        destination_name = f"{now_stamp()}-{slugify(source.stem)}{source.suffix or '.txt'}"
        destination = copy_file(source, raw_dir / destination_name, root=root, mode=0o600)
        imported.append(destination)

    note = render_import_note(root, imported, applies_to)
    append_text(root / "inbox.md", note, root=root)
    return CommandResult(f"Imported {len(imported)} file(s) into .agent-policy/imports/raw")


def brief_task(target: str, task: str, include_candidate: bool = False, task_layer: str = "") -> CommandResult:
    root = require_policy(target)
    destination = root / "brief.md"
    tracking_status = git_tracking_status(root.parent, destination)
    if tracking_status is not False:
        reason = "Git already tracks it" if tracking_status else "its Git tracking status could not be verified"
        action = "untrack the file first" if tracking_status else "verify that the destination is untracked first"
        return CommandResult(
            f"Refusing to write .agent-policy/brief.md because {reason}. "
            f"The brief may contain selected private user/task guidance; {action}.",
            code=2,
        )
    task_layers = selected_task_layers(root, task_layer)
    query_terms = keywords_for(task)
    task_terms: set[str] = set()
    global_root = global_policy_root()
    task_documents: list[tuple[str, str]] = []
    for task_slug in task_layers:
        task_terms.add(task_slug)
        task_terms.add(task_slug.replace("-", " "))
        task_file = global_root / "tasks" / f"{task_slug}.md"
        if not task_file.exists():
            continue
        task_text = read_optional(task_file)
        task_terms.update(task_metadata_terms(task_text))
        task_documents.append((task_slug, task_text))
    context = RetrievalContext(query_terms=query_terms, task_terms=task_terms)

    user_guidance = select_policy_items(
        parse_policy_entries(read_optional(global_root / "profile.md"), layer="user"),
        context,
        kind="user",
    )
    task_guidance: list[BriefItem] = []
    task_heuristics: list[BriefItem] = []
    for task_slug, task_text in task_documents:
        task_policy_items = select_task_policy_items(parse_policy_entries(task_text, layer=f"task:{task_slug}"), context)
        task_heuristic_items = select_heuristic_items(
            parse_heuristic_entries(task_text, layer=f"task:{task_slug}"),
            context,
            include_candidate,
        )
        task_overview = task_policy_overview_item(task_text, task_slug)
        if task_overview and (task_overview.title == "Task guidance" or (not task_policy_items and not task_heuristic_items)):
            task_guidance.append(task_overview)
        task_guidance.extend(task_policy_items)
        task_heuristics.extend(task_heuristic_items)

    heuristic_items = sorted(
        select_heuristic_items(parse_heuristic_entries(read_optional(root / "heuristics.md"), layer="project"), context, include_candidate)
        + task_heuristics
        + select_heuristic_items(parse_heuristic_entries(read_optional(global_root / "heuristics.md"), layer="user"), context, include_candidate),
        key=brief_item_sort_key,
    )
    lesson_items = select_lesson_items(parse_lesson_entries(read_optional(root / "lessons.md")), context, include_candidate)
    playbook_items = select_playbook_items(parse_playbook_entries(read_optional(root / "playbooks.md")), context)

    selected = limit_brief_sections(
        user_guidance=user_guidance,
        task_guidance=sorted(task_guidance, key=brief_item_sort_key),
        heuristics=heuristic_items,
        lessons=lesson_items,
        playbooks=playbook_items,
    )
    content = render_brief(task, selected, task_layers)
    write_text(destination, content, force=True, root=root, mode=0o600)
    count = sum(len(items) for items in selected.values())
    return CommandResult(f"Wrote temporary .agent-policy/brief.md with {count} relevant item(s)")


def compact_lessons(target: str, apply: bool = False) -> CommandResult:
    if apply:
        return CommandResult(
            "compact --apply is not supported yet because compact drafts are not schema-preserving.\n"
            "Use .agent-policy/lessons.compact.md as a human/agent-reviewed draft.",
            code=2,
        )

    root = require_policy(target)
    lessons = parse_lesson_entries(read_optional(root / "lessons.md"))
    heuristics = parse_heuristic_entries(read_optional(root / "heuristics.md"), layer="project")
    groups: dict[str, list[str]] = {}
    heuristic_groups: dict[str, list[str]] = {}

    for entry in lessons:
        applies_to = entry.applies_to or "general"
        lesson = entry.lesson or first_non_heading_line(entry.raw) or "TBD"
        line = concise_join([lesson, f"Next time: {entry.next_time}" if entry.next_time else ""])
        groups.setdefault(applies_to, []).append(line)
    for entry in heuristics:
        applies_to = entry.applies_to or "general"
        line = concise_join([entry.heuristic, f"Search bias: {entry.search_bias}" if entry.search_bias else ""])
        heuristic_groups.setdefault(applies_to, []).append(line)

    lines = [
        "# Lessons Compact Draft",
        "",
        f"Generated: {now_human()}",
        "",
        "Draft only. Review before replacing `lessons.md`.",
        "",
    ]
    if not groups:
        lines.append("No lesson entries found yet.")
    else:
        for applies_to in sorted(groups):
            lines.append(f"## {applies_to}")
            lines.append("")
            for item in groups[applies_to]:
                lines.append(f"- {item}")
            lines.append("")

    content = "\n".join(lines)
    write_text(root / "lessons.compact.md", content, force=True, root=root, mode=0o600)

    heuristic_lines = [
        "# Heuristics Compact Draft",
        "",
        f"Generated: {now_human()}",
        "",
        "Draft only. Review before replacing `heuristics.md`.",
        "",
    ]
    if not heuristic_groups:
        heuristic_lines.append("No heuristic entries found yet.")
    else:
        for applies_to in sorted(heuristic_groups):
            heuristic_lines.append(f"## {applies_to}")
            heuristic_lines.append("")
            for item in heuristic_groups[applies_to]:
                heuristic_lines.append(f"- {item}")
            heuristic_lines.append("")
    write_text(root / "heuristics.compact.md", "\n".join(heuristic_lines), force=True, root=root, mode=0o600)
    return CommandResult("Wrote .agent-policy/lessons.compact.md and .agent-policy/heuristics.compact.md")


def sync_adapters(target: str, force: bool = False) -> CommandResult:
    root = require_policy(target)
    repo = root.parent
    adapters = {
        "AGENTS.md": render_agents_md(),
        "CLAUDE.md": render_claude_md(),
        ".kiro/steering/agent-policy.md": render_kiro_steering(),
    }
    written: list[str] = []
    for relative, content in adapters.items():
        write_adapter(repo / relative, content, force=force, root=repo)
        written.append(relative)
    lines = ["Synced adapter files:"]
    lines.extend(f"- {relative}" for relative in written)
    return CommandResult("\n".join(lines))


def check_code_review(target: str) -> CommandResult:
    repo = resolve_target(target)
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    lines = [
        "# Code Review Check",
        "",
        "Lightweight reminder, not a validator.",
        "",
        "- Confirm review scope.",
        "- Check git status.",
        "- Inspect staged changes.",
        "- Inspect unstaged changes.",
        "- Consider relevant untracked files.",
        "- State reviewed scope in final answer.",
    ]
    if completed.returncode != 0:
        lines.extend(["", "Git status unavailable or target is not a git repository."])
        return CommandResult("\n".join(lines))

    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for raw in completed.stdout.splitlines():
        if raw.startswith("??"):
            untracked.append(raw[3:])
            continue
        if len(raw) >= 2:
            if raw[0] != " ":
                staged.append(raw[3:])
            if raw[1] != " ":
                unstaged.append(raw[3:])

    lines.extend(
        [
            "",
            f"Staged changes: {len(staged)}",
            f"Unstaged changes: {len(unstaged)}",
            f"Untracked files: {len(untracked)}",
        ]
    )
    if staged:
        lines.append("\nStaged:")
        lines.extend(f"- {item}" for item in staged)
    if unstaged:
        lines.append("\nUnstaged:")
        lines.extend(f"- {item}" for item in unstaged)
    if untracked:
        lines.append("\nUntracked:")
        lines.extend(f"- {item}" for item in untracked)
    return CommandResult("\n".join(lines))


def check_document_qa(target: str, answer: str | None = None) -> CommandResult:
    checklist = [
        "# Document QA Check",
        "",
        "Lightweight reminder, not a validator.",
        "",
        "- Retrieve relevant source passages.",
        "- Cite source locations where possible.",
        "- Separate document facts from interpretation.",
        "- Say when evidence is missing.",
    ]
    if not answer:
        return CommandResult("\n".join(checklist))

    answer_path = resolve_input_file(target, answer)
    text = answer_path.read_text(encoding="utf-8").lower()
    evidence_terms = ["evidence", "citation", "citations", "source", "page", "section", "quote"]
    fact_terms = ["interpretation", "assumption", "uncertain", "missing evidence", "not found"]
    lines = checklist + ["", f"Checked answer: {answer_path}"]
    lines.append("Evidence/citation signal: " + ("pass" if any(term in text for term in evidence_terms) else "warn"))
    lines.append("Fact/interpretation boundary signal: " + ("pass" if any(term in text for term in fact_terms) else "warn"))
    return CommandResult("\n".join(lines))


def check_trading_review(target: str, review: str | None = None) -> CommandResult:
    checklist = [
        "# Trading Review Check",
        "",
        "Lightweight reminder, not a validator and not trading advice.",
        "",
        "- Treat trading heuristics as review aids, not trade signals.",
        "- Review market context.",
        "- Review setup thesis.",
        "- Review entry, invalidation, sizing, and exit.",
        "- Separate thesis quality from execution quality.",
        "- Extract lessons with uncertainty.",
    ]
    if not review:
        return CommandResult("\n".join(checklist))

    review_path = resolve_input_file(target, review)
    text = review_path.read_text(encoding="utf-8").lower()
    groups = {
        "market context": ["market context", "regime", "volatility", "liquidity"],
        "setup thesis": ["thesis", "setup", "idea"],
        "risk/sizing": ["risk", "invalidation", "stop", "position sizing", "sizing"],
        "execution": ["execution", "entry", "exit"],
        "lesson": ["lesson", "heuristic", "learned", "uncertain"],
    }
    lines = checklist + ["", f"Checked review: {review_path}"]
    for label, terms in groups.items():
        lines.append(f"{label}: " + ("pass" if any(term in text for term in terms) else "warn"))
    return CommandResult("\n".join(lines))


def render_dry_run(destination: Path, content: str) -> str:
    return "\n".join(
        [
            "Dry run: no files changed.",
            f"Destination: {destination}",
            "",
            content.strip(),
        ]
    )


def render_feedback_entry(
    entry_type: str,
    applies_to: str,
    keywords: str,
    title: str,
    signal: str,
    lesson: str,
    next_time: str,
    status: str,
) -> str:
    date = now_utc().strftime("%Y-%m-%d")
    heading = feedback_heading(date, title, applies_to, entry_type)
    return f"""
## {heading}

Type: {entry_type}
Applies to: {applies_to}
Keywords: {keywords or "TBD"}
Signal: {signal}
Lesson: {lesson}
Next time: {next_time}
Status: {status}
"""


def render_inbox_feedback_entry(
    entry_type: str,
    applies_to: str,
    keywords: str,
    title: str,
    signal: str,
    lesson: str,
    next_time: str,
    status: str,
) -> str:
    date = now_utc().strftime("%Y-%m-%d")
    heading = feedback_heading(date, title, applies_to, entry_type)
    lines = [
        f"## {heading}",
        "",
        f"Type: {entry_type}",
        f"Applies to: {applies_to}",
    ]
    if keywords:
        lines.append(f"Keywords: {keywords}")
    lines.append(f"Signal: {signal}")
    if lesson:
        lines.append(f"Lesson: {lesson}")
    if next_time:
        lines.append(f"Next time: {next_time}")
    lines.append(f"Status: {status}")
    return "\n".join(lines) + "\n"


def feedback_heading(date: str, title: str, applies_to: str, entry_type: str) -> str:
    clean_title = " ".join(title.split())
    if clean_title:
        return f"{date} — {clean_title}"
    clean_applies_to = " ".join(applies_to.split())
    clean_type = " ".join(entry_type.split())
    if clean_applies_to and clean_type:
        return f"{date} — {clean_applies_to} {clean_type}"
    if clean_type:
        return f"{date} — {clean_type}"
    return f"{date} — Feedback"


def render_heuristic_entry(
    title: str,
    applies_to: str,
    keywords: str,
    source: str,
    heuristic: str,
    search_bias: str,
    avoids: str,
    status: str,
) -> str:
    search_bias_section = f"\n### Search bias\n\n{search_bias}\n" if search_bias else ""
    avoids_section = f"\n### Avoids\n\n{avoids}\n" if avoids else ""
    return f"""
## {title}

Applies to: {applies_to}
Keywords: {keywords}
Source: {source}
Status: {status}

### Heuristic

{heuristic}
{search_bias_section}
{avoids_section}
"""


def render_incomplete_heuristic_note(
    title: str,
    applies_to: str,
    keywords: str,
    source: str,
    heuristic: str,
    search_bias: str,
    avoids: str,
    status: str,
) -> str:
    date = now_utc().strftime("%Y-%m-%d")
    lines = [
        f"## {date} — Incomplete heuristic signal",
        "",
        "Signal: A heuristic was requested but required fields were missing.",
        f"Applies to: {applies_to}",
        f"Source: {source}",
        f"Status: {status}",
    ]
    optional_fields = [
        ("Title", title),
        ("Keywords", keywords),
        ("Heuristic", heuristic),
        ("Search bias", search_bias),
        ("Avoids", avoids),
    ]
    for label, value in optional_fields:
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines) + "\n"


def expand_source_paths(repo: Path, source_paths: list[str]) -> list[Path]:
    sources: list[Path] = []
    seen: set[Path] = set()
    for pattern in source_paths:
        raw = Path(pattern).expanduser()
        search_path = raw if raw.is_absolute() else repo / raw
        candidates = [Path(path) for path in glob.glob(str(search_path))]
        if not candidates:
            candidates = [search_path]
        for source in candidates:
            source = source.expanduser()
            if not source.is_absolute():
                source = source.resolve()
            if not source.exists() or not source.is_file():
                raise SystemExit(f"Import source is not a file: {source}")
            resolved = source.resolve()
            if resolved not in seen:
                seen.add(resolved)
                sources.append(resolved)
    return sources


def render_import_note(root: Path, imported: list[Path], applies_to: str) -> str:
    date = now_utc().strftime("%Y-%m-%d")
    files = "\n".join(f"- `{path.relative_to(root.parent)}`" for path in imported)
    return f"""
## {date} - Imported source

Applies to: {applies_to or "general"}
Signal: Imported raw source file(s). Review manually before turning into lessons.

Files:
{files}
"""


def select_lesson_items(
    entries: list[LessonEntry],
    context: RetrievalContext,
    include_candidate: bool,
) -> list[BriefItem]:
    items: list[BriefItem] = []
    for entry in entries:
        if entry.status == "candidate" and not include_candidate:
            continue
        if entry.status not in {"active", "candidate"}:
            continue
        match_level = match_level_for_fields(
            context,
            metadata_fields=[entry.heading, entry.keywords, entry.applies_to],
            body_fields=[entry.lesson, entry.next_time, entry.signal],
        )
        if match_level is None:
            continue
        text = concise_join(
            [
                f"{entry.heading}:",
                entry.lesson,
                f"Next time: {entry.next_time}" if entry.next_time and entry.next_time != "TBD" else "",
                f"Status: {entry.status}",
            ]
        )
        items.append(BriefItem("lesson", entry.heading, text, match_level, entry.order, status=entry.status))
    return sorted(items, key=brief_item_sort_key)


def select_heuristic_items(
    entries: list[HeuristicEntry],
    context: RetrievalContext,
    include_candidate: bool,
) -> list[BriefItem]:
    items: list[BriefItem] = []
    for entry in entries:
        if entry.status == "candidate" and not include_candidate:
            continue
        if entry.status not in HEURISTIC_STATUSES:
            continue
        match_level = match_level_for_fields(
            context,
            metadata_fields=[entry.heading, entry.keywords, entry.applies_to],
            body_fields=[entry.heuristic, entry.search_bias, entry.avoids],
        )
        if match_level is None:
            continue
        text_lines = [
            entry.heading,
            f"  Guidance: {entry.heuristic}",
        ]
        if entry.search_bias:
            text_lines.append(f"  Additional priority: {entry.search_bias}")
        if entry.avoids:
            text_lines.append(f"  Avoid: {entry.avoids}")
        text_lines.append(f"  Layer: {entry.layer}")
        if entry.status != "active":
            text_lines.append(f"  Status: {entry.status}")
        text = "\n".join(text_lines)
        item = BriefItem(
            "heuristic",
            entry.heading,
            text,
            match_level,
            entry.order,
            layer=entry.layer,
            status=entry.status,
        )
        items.append(item)
    return sorted(items, key=brief_item_sort_key)


def select_policy_items(entries: list[PolicyEntry], context: RetrievalContext, kind: str) -> list[BriefItem]:
    items: list[BriefItem] = []
    for entry in entries:
        match_level = match_level_for_fields(
            context,
            metadata_fields=[entry.title, entry.keywords],
            body_fields=[entry.body],
        )
        if match_level is None:
            continue
        summary = first_steps_summary(entry.body)
        text = concise_join([f"{entry.title}:", summary, f"Layer: {entry.layer}"])
        items.append(BriefItem(kind, entry.title, text, match_level, entry.order, layer=entry.layer))
    return sorted(items, key=brief_item_sort_key)


def select_task_policy_items(entries: list[PolicyEntry], context: RetrievalContext) -> list[BriefItem]:
    items: list[BriefItem] = []
    for entry in entries:
        match_level = match_level_for_fields(
            context,
            metadata_fields=[entry.title, entry.keywords],
            body_fields=[entry.body],
        )
        if match_level is None:
            continue
        summary = first_steps_summary(entry.body)
        text = concise_join([f"{entry.title}:", summary, f"Layer: {entry.layer}"])
        items.append(BriefItem("task", entry.title, text, match_level, entry.order, layer=entry.layer))
    return sorted(items, key=brief_item_sort_key)


def select_playbook_items(entries: list[PlaybookEntry], context: RetrievalContext) -> list[BriefItem]:
    items: list[BriefItem] = []
    for entry in entries:
        match_level = match_level_for_fields(
            context,
            metadata_fields=[entry.title, entry.keywords, entry.aliases],
            body_fields=[entry.body],
        )
        if match_level is None:
            continue
        note = first_steps_summary(entry.body)
        text = concise_join([f"{entry.title}:", note, "Layer: project"])
        items.append(BriefItem("playbook", entry.title, text, match_level, entry.order))
    return sorted(items, key=brief_item_sort_key)


def limit_brief_sections(
    user_guidance: list[BriefItem],
    task_guidance: list[BriefItem],
    heuristics: list[BriefItem],
    lessons: list[BriefItem],
    playbooks: list[BriefItem],
) -> dict[str, list[BriefItem]]:
    section_caps = {
        "task_guidance": 1,
        "user_guidance": 1,
        "heuristics": 2,
        "lessons": 2,
        "playbooks": 1,
    }
    source = {
        "task_guidance": task_guidance,
        "user_guidance": user_guidance,
        "heuristics": heuristics,
        "lessons": lessons,
        "playbooks": playbooks,
    }
    selected: dict[str, list[BriefItem]] = {}
    remaining = 7
    for key in ["playbooks", "task_guidance", "user_guidance", "heuristics", "lessons"]:
        if remaining <= 0:
            selected[key] = []
            continue
        take = min(section_caps[key], remaining)
        selected[key] = source[key][:take]
        remaining -= len(selected[key])
    return selected


def render_brief(task: str, sections: dict[str, list[BriefItem]], task_layers: list[str] | None = None) -> str:
    lines = [
        "# Agent Policy Brief",
        "",
        "Temporary brief for current task. Refresh before reuse.",
        "May contain selected private user/task guidance. Do not commit or share this file.",
        "",
        f"Task: {task}",
    ]
    if task_layers:
        joined_layers = ", ".join(f"`~/.agent-policy/tasks/{slug}.md`" for slug in task_layers)
        lines.append(f"Task layer(s): {joined_layers}")
    lines.extend(
        [
            f"Generated: {now_human()}",
            "Selection: up to 3-7 relevant items when enough relevant items exist; no filler items.",
            "",
        ]
    )
    section_titles = [
        ("playbooks", "Project Playbook"),
        ("task_guidance", "Task Guidance"),
        ("user_guidance", "User / Global Guidance"),
        ("heuristics", "Relevant Heuristics"),
        ("lessons", "Relevant Lessons"),
    ]
    emitted_dynamic_section = False
    for key, title in section_titles:
        items = sections.get(key, [])
        if not items:
            continue
        emitted_dynamic_section = True
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {item.text}" for item in items)
        lines.append("")
    if not emitted_dynamic_section:
        lines.extend(["No directly relevant prior experience found.", ""])
    lines.extend(
        [
            "## Reminder",
            "",
            "- Current user intent overrides prior heuristics unless safety, data integrity, or explicit project rules are involved.",
        ]
    )
    return "\n".join(lines)


def parse_lesson_entries(text: str) -> list[LessonEntry]:
    entries: list[LessonEntry] = []
    for index, (heading, raw) in enumerate(markdown_h2_entries(text)):
        entry = LessonEntry(
            heading=heading,
            entry_type=field_value(raw, "Type"),
            applies_to=field_value(raw, "Applies to"),
            keywords=field_value(raw, "Keywords"),
            signal=field_value(raw, "Signal"),
            lesson=field_value(raw, "Lesson"),
            next_time=field_value(raw, "Next time"),
            status=field_value(raw, "Status"),
            raw=raw,
            order=index,
        )
        if entry.entry_type in FEEDBACK_TYPES and entry.status in FEEDBACK_STATUSES:
            entries.append(entry)
    return entries


def parse_heuristic_entries(text: str, layer: str) -> list[HeuristicEntry]:
    entries: list[HeuristicEntry] = []
    for index, (heading, raw) in enumerate(markdown_h2_entries(text)):
        entry = HeuristicEntry(
            heading=heading,
            applies_to=field_value(raw, "Applies to"),
            keywords=field_value(raw, "Keywords"),
            source=field_value(raw, "Source"),
            heuristic=field_or_subsection_value(raw, "Heuristic"),
            search_bias=field_or_subsection_value(raw, "Search bias"),
            avoids=field_or_subsection_value(raw, "Avoids"),
            status=field_value(raw, "Status"),
            raw=raw,
            order=index,
            layer=layer,
        )
        if entry.heuristic and entry.status in HEURISTIC_STATUSES:
            entries.append(entry)
    return entries


def parse_policy_entries(text: str, layer: str) -> list[PolicyEntry]:
    h2_entries = markdown_h2_entries(text)
    if text.strip() and not h2_entries:
        raw = text.strip()
        if field_or_subsection_value(raw, "Heuristic") or field_value(raw, "Task ID") or is_default_profile_template(raw) or is_empty_task_policy_template(raw):
            return []
        return [
            PolicyEntry(
                title=markdown_title(raw) or f"{layer} guidance",
                keywords=field_value(raw, "Keywords"),
                body=raw,
                order=0,
                layer=layer,
            )
        ]

    entries: list[PolicyEntry] = []
    for index, (title, raw) in enumerate(h2_entries):
        if field_or_subsection_value(raw, "Heuristic") or field_value(raw, "Task ID") or is_default_profile_template(raw) or is_empty_task_policy_template(raw):
            continue
        entries.append(
            PolicyEntry(
                title=title,
                keywords=field_value(raw, "Keywords"),
                body=raw,
                order=index,
                layer=layer,
            )
        )
    return entries


def task_policy_overview_item(text: str, task_id: str) -> BriefItem | None:
    if is_empty_task_policy_template(text):
        return None
    guidance = field_value(text, "Guidance") or field_value(text, "Summary")
    if not guidance:
        return None
    return BriefItem(
        "task",
        "Task guidance",
        concise_join([f"Task guidance ({task_id}):", f"Guidance: {guidance}"]),
        match_level="task-metadata",
        order=-100,
        layer=f"task:{task_id}",
    )


def is_default_profile_template(text: str) -> bool:
    normalized = "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())
    return normalized == "\n".join(
        [
            "# Agent Policy Profile",
            "Long-lived user preferences, working habits, and cross-project guidance.",
            "Keep this private unless the user explicitly decides otherwise.",
        ]
    )


def is_empty_task_policy_template(text: str) -> bool:
    stripped = text.strip()
    if re.search(r"(?m)^##\s+", stripped):
        return False
    if not field_value(stripped, "Task ID"):
        return False
    meaningful_fields = [
        field_value(stripped, "Display name"),
        field_value(stripped, "Aliases"),
        field_value(stripped, "Keywords"),
    ]
    if any(meaningful_fields):
        return False
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    allowed_prefixes = ("# Task Policy:", "Task ID:", "Display name:", "Aliases:", "Keywords:")
    return all(line.startswith(allowed_prefixes) for line in lines)


def selected_task_layers(root: Path, task_layer: str = "") -> list[str]:
    if task_layer and task_layer.strip():
        task_id = normalize_task_id(task_layer)
        validate_task_id(task_id)
        return [task_id]
    return [slug for slug, _display in enabled_task_layers(root)]


def enabled_task_layers(root: Path) -> list[tuple[str, str]]:
    return enabled_task_layers_from_text(read_optional(root / "current.md"))


def enabled_task_layers_from_text(text: str) -> list[tuple[str, str]]:
    section = markdown_section(text, "Enabled task layers")
    layers: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        match = re.search(r"`~/.agent-policy/tasks/([^`/]+)\.md`", item)
        if match:
            slug = match.group(1)
            if not is_valid_task_id(slug):
                continue
            label = re.sub(r"\s*\(`~/.agent-policy/tasks/[^`/]+\.md`\)\s*$", "", item).strip()
            if " — " in label:
                _task_id, display = label.split(" — ", 1)
            else:
                display = ""
        else:
            slug = normalize_task_id(item)
            if not is_valid_task_id(slug):
                continue
            display = ""
        if slug in seen:
            continue
        layers.append((slug, display))
        seen.add(slug)
    return layers


def normalize_task_id(value: str) -> str:
    return value.strip()


def is_valid_task_id(value: str) -> bool:
    return bool(TASK_ID_PATTERN.fullmatch(value))


def validate_task_id(value: str) -> None:
    if is_valid_task_id(value):
        return
    raise SystemExit(
        "Task id must be a stable English id such as `code-review` or `trading-review`. "
        "Use `--display` for non-English human-readable names, for example "
        "`agent-navi setup --task trading-review --display \"交易复盘\"`."
    )


def markdown_section(text: str, title: str) -> str:
    pattern = re.compile(rf"(?ms)^##\s+{re.escape(title)}\s*\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def markdown_heading_blocks(text: str, level: int) -> list[tuple[str, int, int]]:
    headings: list[tuple[str, int]] = []
    offset = 0
    fence_char = ""
    fence_length = 0
    prefix = "#" * level

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        fence_match = re.match(r"(`{3,}|~{3,})", stripped)
        if fence_match:
            marker = fence_match.group(1)
            if not fence_char:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = ""
                fence_length = 0
        elif not fence_char:
            heading_match = re.match(rf"^{re.escape(prefix)}[ \t]+(.+?)[ \t]*(?:\r?\n)?$", line)
            if heading_match:
                headings.append((heading_match.group(1).strip(), offset))
        offset += len(line)

    return [
        (heading, start, headings[index + 1][1] if index + 1 < len(headings) else len(text))
        for index, (heading, start) in enumerate(headings)
    ]


def markdown_h2_blocks(text: str) -> list[tuple[str, int, int]]:
    return markdown_heading_blocks(text, 2)


def markdown_h2_entries(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for heading, start, end in markdown_h2_blocks(text):
        block = text[start:end].strip()
        _heading_line, separator, remainder = block.partition("\n")
        raw = heading if not separator else f"{heading}\n{remainder}".strip()
        entries.append((heading, raw))
    return entries


def upsert_markdown_section(path: Path, title: str, body_lines: list[str], *, root: Path) -> None:
    update_text(path, lambda original: replace_markdown_section(original, title, body_lines), root=root)


def replace_markdown_section(text: str, title: str, body_lines: list[str]) -> str:
    body = "\n".join(body_lines).rstrip()
    replacement = f"## {title}\n\n{body}\n"
    existing = text.rstrip()
    pattern = re.compile(rf"(?ms)^##\s+{re.escape(title)}\s*\n.*?(?=^##\s+|\Z)")
    if pattern.search(existing):
        return pattern.sub(lambda _match: replacement.rstrip() + "\n\n", existing).rstrip() + "\n"
    separator = "\n\n" if existing else ""
    return existing + separator + replacement


def markdown_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def parse_playbook_entries(text: str) -> list[PlaybookEntry]:
    entries: list[PlaybookEntry] = []
    for index, (title, raw) in enumerate(markdown_h2_entries(text)):
        if is_placeholder_playbook(title, raw):
            continue
        entries.append(
            PlaybookEntry(
                title=title,
                aliases=field_value(raw, "Aliases"),
                keywords=field_value(raw, "Keywords"),
                body=raw,
                order=index,
            )
        )
    return entries


def is_placeholder_playbook(title: str, raw: str) -> bool:
    return title == "Short task name" and "1. ..." in raw and "2. ..." in raw


def first_steps_summary(body: str) -> str:
    step_lines = [line.strip() for line in body.splitlines() if re.match(r"^\d+\.\s+", line.strip())]
    if step_lines:
        return " ".join(step_lines[:3])
    bullet_lines = [line[2:].strip() for line in body.splitlines() if line.strip().startswith("- ")]
    if bullet_lines:
        return " ".join(bullet_lines[:3])
    return first_non_heading_line(body)


def keywords_for(task: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", task.lower()))
    return words


def task_metadata_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for field in ("Task ID", "Display name", "Aliases", "Keywords"):
        value = field_value(text, field)
        if not value:
            continue
        for item in re.split(r"[,;]", value):
            normalized = normalize_search_text(item)
            if normalized:
                terms.add(normalized)
        terms.update(keywords_for(value))
    return terms


def match_level_for_fields(
    context: RetrievalContext,
    metadata_fields: list[str],
    body_fields: list[str],
) -> str | None:
    if fields_match_terms(metadata_fields, context.query_terms):
        return "query-metadata"
    if fields_match_terms(body_fields, context.query_terms):
        return "query-body"
    if fields_match_terms(metadata_fields, context.task_terms):
        return "task-metadata"
    if fields_match_terms(body_fields, context.task_terms):
        return "task-body"
    return None


def fields_match_terms(fields: list[str], terms: set[str]) -> bool:
    return any(term_matches_field(term, field) for term in terms for field in fields if field)


def term_matches_field(term: str, field: str) -> bool:
    normalized_term = normalize_search_text(term)
    normalized_field = normalize_search_text(field)
    if not normalized_term or not normalized_field:
        return False
    if re.search(r"[a-z0-9]", normalized_term):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
        return bool(re.search(pattern, normalized_field))
    return normalized_term in normalized_field


def normalize_search_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def brief_item_sort_key(item: BriefItem) -> tuple[int, int, int, int]:
    match_order = {
        "query-metadata": 0,
        "query-body": 1,
        "task-metadata": 2,
        "task-body": 3,
    }
    if item.layer == "project":
        layer_order = 0
    elif item.layer.startswith("task:"):
        layer_order = 1
    else:
        layer_order = 2
    status_order = 0 if item.status == "active" else 1
    return (layer_order, match_order[item.match_level], status_order, item.order)


def field_value(entry: str, field: str) -> str:
    lines = entry.splitlines()
    pattern = re.compile(rf"^{re.escape(field)}:[ \t]*(.*)$")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        parts = [match.group(1).strip()] if match.group(1).strip() else []
        for continuation in lines[index + 1 :]:
            stripped = continuation.strip()
            if not stripped or stripped.startswith("#"):
                break
            next_field = re.match(r"^([^:]+):[ \t]*", continuation)
            if next_field and next_field.group(1).strip() in INLINE_FIELD_NAMES:
                break
            parts.append(stripped)
        return " ".join(parts)
    return ""


def field_or_subsection_value(entry: str, field: str) -> str:
    inline = field_value(entry, field)
    if inline:
        return inline
    section = ""
    for heading, start, end in markdown_heading_blocks(entry, 3):
        if heading.casefold() != field.casefold():
            continue
        block = entry[start:end].strip()
        _heading_line, separator, section = block.partition("\n")
        if not separator:
            return ""
        break
    if not section:
        return ""
    lines: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        lines.append(stripped)
    return " ".join(lines)


def first_non_heading_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def concise_join(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def git_tracking_status(repo: Path, path: Path) -> bool | None:
    try:
        relative = path.relative_to(repo)
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(relative)],
            cwd=repo,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except ValueError:
        return False
    except (OSError, subprocess.TimeoutExpired):
        return None if any((parent / ".git").exists() for parent in (repo, *repo.parents)) else False
    return completed.returncode == 0


def resolve_input_file(target: str, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = resolve_target(target) / path
    if not path.exists() or not path.is_file():
        raise SystemExit(f"File not found: {path}")
    return path


def global_policy_root() -> Path:
    home = Path(os.environ.get("AGENT_POLICY_HOME") or Path.home()).expanduser().resolve()
    return home / ".agent-policy"


def ensure_global_policy() -> Path:
    root = global_policy_root()
    ensure_safe_directory(root, root=root, mode=0o700)
    ensure_safe_directory(root / "tasks", root=root, mode=0o700)
    for relative, content in GLOBAL_FILE_TEMPLATES.items():
        write_text(root / relative, content, force=False, root=root, mode=0o600)
    return root


def ensure_global_task_file(task_id: str, display_name: str = "") -> Path:
    validate_task_id(task_id)
    root = ensure_global_policy()
    path = root / "tasks" / f"{task_id}.md"
    title = " ".join(part.capitalize() for part in task_id.split("-"))
    metadata_lines = [
        f"Task ID: {task_id}",
        f"Display name: {display_name}",
        "Aliases:",
        "Keywords:",
    ]
    created = write_text(
        path,
        f"# Task Policy: {title}\n\n" + "\n".join(metadata_lines) + "\n",
        force=False,
        root=root,
        mode=0o600,
    )
    if display_name and not created:
        def update_display(original: str) -> str:
            updated, count = re.subn(
                r"(?m)^Display name:[ \t]*.*$",
                lambda _match: f"Display name: {display_name}",
                original,
                count=1,
            )
            if count == 0:
                updated, _count = re.subn(
                    r"(?m)^(Task ID:[ \t]*[^\n]+)$",
                    lambda match: f"{match.group(1)}\nDisplay name: {display_name}",
                    original,
                    count=1,
                )
            return updated

        update_text(path, update_display, root=root, mode=0o600)
    return path


def fill_empty_task_metadata(path: Path, display_name: str = "", keywords: str = "") -> None:
    root = global_policy_root()

    def fill(original: str) -> str:
        updated = original
        for field, value in (("Display name", display_name), ("Keywords", keywords)):
            if not value or field_value(updated, field):
                continue
            replacement = f"{field}: {value}"
            updated, count = re.subn(
                rf"(?m)^{re.escape(field)}:[ \t]*$",
                lambda _match, replacement=replacement: replacement,
                updated,
                count=1,
            )
            if count == 0:
                updated, _count = re.subn(
                    r"(?m)^(Task ID:[ \t]*[^\n]+)$",
                    lambda match, replacement=replacement: f"{match.group(1)}\n{replacement}",
                    updated,
                    count=1,
                )
        return updated

    update_text(path, fill, root=root, mode=0o600)


def interactive_project_setup(root: Path) -> str:
    prompts = [
        ("Project purpose", "What is this project trying to accomplish? "),
        ("Project type", "What kind of project/task is this? "),
        ("Constraints", "Most important constraints or preferences? "),
        ("Task guidance", "Known task layer guidance to consider? "),
        ("Git/privacy", "Should .agent-policy/ be committed, private, or mixed? "),
    ]
    answers: list[tuple[str, str]] = []
    for label, prompt in prompts:
        try:
            value = input(prompt).strip()
        except EOFError:
            value = ""
        if value:
            answers.append((label, value))
    if not answers:
        return "Interactive setup skipped; no answers provided."

    current_lines = ["", "## Project setup notes", ""]
    for label, value in answers:
        current_lines.append(f"- {label}: {value}")
    append_text(root / "current.md", "\n".join(current_lines), root=root)

    heuristic_lines = [
        "",
        "## Project setup retrieval heuristic",
        "",
        "Applies to: project work",
        "Keywords: project setup, constraints, task guidance",
        "Source: project setup",
        "Heuristic: Check the project setup notes before assuming generic task defaults.",
        "Search bias: Prefer project-specific constraints and task guidance recorded during setup.",
        "Avoids: Applying generic workflow assumptions before reading project intent.",
        "Status: candidate",
    ]
    append_text(root / "heuristics.md", "\n".join(heuristic_lines), root=root)
    return "Recorded interactive setup notes in current.md and a candidate heuristic."


def write_adapter(path: Path, generated: str, force: bool = False, *, root: Path) -> None:
    if force:
        write_text(path, generated, force=True, root=root)
        return

    pattern = re.compile(
        rf"{re.escape(GENERATED_START)}.*?{re.escape(GENERATED_END)}\n?",
        re.DOTALL,
    )

    def merge(existing: str) -> str:
        if pattern.search(existing):
            return pattern.sub(lambda _match: generated, existing)
        separator = "\n\n" if existing.strip() else ""
        return existing.rstrip() + separator + generated

    update_text(path, merge, root=root)


def ensure_gitignore(repo: Path) -> str:
    path = repo / ".gitignore"
    changed = False

    def merge(existing: str) -> str:
        nonlocal changed
        if not existing:
            changed = True
            return "\n".join(GITIGNORE_LINES)
        current_lines = set(existing.splitlines())
        missing = [line for line in GITIGNORE_LINES if line and line not in current_lines]
        if not missing:
            return existing
        changed = True
        addition = "\n\n# Agent Navigator\n" + "\n".join(missing) + "\n"
        return existing.rstrip() + addition

    update_text(path, merge, root=repo)
    return ".gitignore" if changed else ""
