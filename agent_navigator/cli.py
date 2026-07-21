from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .commands import (
    add_feedback,
    add_heuristic,
    brief_task,
    check_code_review,
    check_document_qa,
    check_trading_review,
    compact_lessons,
    import_sources,
    init_policy,
    replace_entry,
    setup_task_layers,
    sync_adapters,
)


def build_parser(prog: str = "agent-navi") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Manage a compact, file-based experience navigation layer for agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create minimal .agent-policy/ files and adapters")
    init.add_argument("--target", default=".")
    init.add_argument(
        "--force",
        action="store_true",
        help="Regenerate adapter files without replacing accumulated experience Markdown",
    )
    init.add_argument("--global", dest="global_policy", action="store_true", help="Create ~/.agent-policy/ user/task layer")
    init.add_argument("--interactive", action="store_true", help="Collect lightweight project setup notes")

    setup = sub.add_parser("setup", help="Record retrieval-overlay setup choices for this project")
    add_target(setup)
    setup.add_argument("--task", action="append", default=[], help="Enable a stable English task id from ~/.agent-policy/tasks/<task-id>.md")
    setup.add_argument("--display", default="", help="Optional human-readable display name when enabling one task id")

    feedback = sub.add_parser("add-feedback", help="Record a short reusable lesson or inbox signal")
    add_target(feedback)
    feedback.add_argument("text", nargs="?", help="Raw feedback text")
    feedback.add_argument("--type", default="lesson", choices=["lesson", "preference", "positive", "negative", "observation"])
    feedback.add_argument("--applies-to", default="general")
    feedback.add_argument("--keywords", default="")
    feedback.add_argument("--title", default="")
    feedback.add_argument("--signal", default="")
    feedback.add_argument("--lesson", default="")
    feedback.add_argument("--next-time", default="")
    feedback.add_argument("--status", choices=["active", "candidate"])
    feedback.add_argument("--inbox", action="store_true", help="Write to .agent-policy/inbox.md instead of lessons.md")

    heuristic = sub.add_parser("add-heuristic", help="Record a project, task, or global heuristic")
    add_target(heuristic)
    heuristic.add_argument("--title", default="")
    heuristic.add_argument("--applies-to", default="general")
    heuristic.add_argument("--keywords", default="")
    heuristic.add_argument("--source", default="")
    heuristic.add_argument("--heuristic", default="")
    heuristic.add_argument("--search-bias", default="", help="Optional additional inspection, retrieval, or action priority")
    heuristic.add_argument("--avoids", default="")
    heuristic.add_argument("--status", choices=["active", "candidate"])
    heuristic_scope = heuristic.add_mutually_exclusive_group()
    heuristic_scope.add_argument("--global", dest="global_target", action="store_true")
    heuristic_scope.add_argument("--task", default="")
    heuristic.add_argument("--dry-run", action="store_true", help="Print the proposed heuristic entry without writing")

    replace = sub.add_parser("replace-entry", help="Replace one exact Markdown entry without semantic matching")
    add_target(replace)
    replace.add_argument("--file", dest="entry_file", required=True, choices=["lessons", "heuristics", "playbooks"])
    replace.add_argument("--heading", required=True, help="Exact Markdown level-two heading text, without `##`")
    replace.add_argument("--from", dest="source", required=True, help="File containing exactly one replacement `##` entry")
    replace.add_argument("--dry-run", action="store_true", help="Print a unified diff without writing")

    import_cmd = sub.add_parser("import", help="Copy source files into imports/raw and record a short note")
    add_target(import_cmd)
    import_cmd.add_argument("paths", nargs="+")
    import_cmd.add_argument("--applies-to", default="general")

    brief = sub.add_parser("brief", help="Generate a compact task-specific policy brief")
    add_target(brief)
    brief.add_argument("task")
    brief.add_argument("--task", dest="task_layer", default="", help="Explicit stable English task id from ~/.agent-policy/tasks/<task-id>.md")
    brief.add_argument("--include-candidate", action="store_true")

    compact = sub.add_parser("compact", help="Create a deterministic lessons.compact.md draft")
    add_target(compact)
    compact.add_argument("--apply", action="store_true", help="Unsupported: compact writes draft files only")

    sync = sub.add_parser("sync", help="Regenerate short adapter files")
    add_target(sync)
    sync.add_argument("--force", action="store_true", help="Overwrite adapter files instead of updating/appending marker blocks")

    check = sub.add_parser("check", help="Print lightweight task reminders")
    check_sub = check.add_subparsers(dest="check_name", required=True)
    code_review = check_sub.add_parser("code-review")
    add_target(code_review)
    document_qa = check_sub.add_parser("document-qa")
    add_target(document_qa)
    document_qa.add_argument("--answer")
    trading = check_sub.add_parser("trading-review")
    add_target(trading)
    trading.add_argument("--review")

    return parser


def add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", default=".")


def main(argv: list[str] | None = None) -> int:
    prog = "agent-navi"
    if argv is None:
        invoked = Path(sys.argv[0]).name
        if invoked in {"agent-navi", "agent-navigator"}:
            prog = invoked
    parser = build_parser(prog=prog)
    args = parser.parse_args(argv)

    if args.command == "init":
        result = init_policy(args.target, args.force, args.global_policy, args.interactive)
    elif args.command == "setup":
        result = setup_task_layers(args.target, args.task, display=args.display)
    elif args.command == "add-feedback":
        result = add_feedback(
            target=args.target,
            text=args.text,
            entry_type=args.type,
            applies_to=args.applies_to,
            keywords=args.keywords,
            title=args.title,
            signal=args.signal,
            lesson=args.lesson,
            next_time=args.next_time,
            status=args.status,
            inbox=args.inbox,
        )
    elif args.command == "add-heuristic":
        result = add_heuristic(
            target=args.target,
            title=args.title,
            applies_to=args.applies_to,
            keywords=args.keywords,
            source=args.source,
            heuristic=args.heuristic,
            search_bias=args.search_bias,
            avoids=args.avoids,
            status=args.status,
            global_target=args.global_target,
            task=args.task,
            dry_run=args.dry_run,
        )
    elif args.command == "replace-entry":
        result = replace_entry(
            target=args.target,
            entry_file=args.entry_file,
            heading=args.heading,
            source=args.source,
            dry_run=args.dry_run,
        )
    elif args.command == "import":
        result = import_sources(args.target, args.paths, args.applies_to)
    elif args.command == "brief":
        result = brief_task(args.target, args.task, args.include_candidate, task_layer=args.task_layer)
    elif args.command == "compact":
        result = compact_lessons(args.target, args.apply)
    elif args.command == "sync":
        result = sync_adapters(args.target, args.force)
    elif args.command == "check" and args.check_name == "code-review":
        result = check_code_review(args.target)
    elif args.command == "check" and args.check_name == "document-qa":
        result = check_document_qa(args.target, args.answer)
    elif args.command == "check" and args.check_name == "trading-review":
        result = check_trading_review(args.target, args.review)
    else:
        parser.error("Unknown command")
        return 2

    if result.message:
        print(result.message)
    return result.code


if __name__ == "__main__":
    sys.exit(main())
