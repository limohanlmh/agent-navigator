from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agent_navigator import __version__
from agent_navigator.cli import main


class AgentPolicyCliTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self) -> None:
        project_metadata = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"$', project_metadata, flags=re.MULTILINE)

        self.assertIsNotNone(match)
        self.assertEqual(__version__, match.group(1))

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.old_fixed_now = os.environ.get("AGENT_POLICY_FIXED_NOW")
        self.old_home = os.environ.get("HOME")
        self.old_agent_policy_home = os.environ.get("AGENT_POLICY_HOME")
        self.global_home = self.target / "home"
        os.environ["AGENT_POLICY_FIXED_NOW"] = "2026-06-18T00:00:00Z"
        os.environ["HOME"] = str(self.global_home)
        os.environ["AGENT_POLICY_HOME"] = str(self.global_home)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        if self.old_fixed_now is None:
            os.environ.pop("AGENT_POLICY_FIXED_NOW", None)
        else:
            os.environ["AGENT_POLICY_FIXED_NOW"] = self.old_fixed_now
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        if self.old_agent_policy_home is None:
            os.environ.pop("AGENT_POLICY_HOME", None)
        else:
            os.environ["AGENT_POLICY_HOME"] = self.old_agent_policy_home

    def run_cli(self, args: list[str]) -> str:
        code, output = self.run_cli_with_code(args)
        self.assertEqual(code, 0)
        return output

    def run_cli_with_code(self, args: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(args)
        return code, stream.getvalue()

    def test_init_creates_minimal_layer(self) -> None:
        out = self.run_cli(["init", "--target", str(self.target)])
        self.assertIn("Initialized Agent Navigator experience layer", out)
        self.assertNotIn("redistribute its contents by meaning", out)

        expected = [
            ".agent-policy/current.md",
            ".agent-policy/knowledge.md",
            ".agent-policy/lessons.md",
            ".agent-policy/heuristics.md",
            ".agent-policy/playbooks.md",
            ".agent-policy/inbox.md",
            ".agent-policy/imports/raw",
            "AGENTS.md",
            "CLAUDE.md",
            ".kiro/steering/agent-policy.md",
            ".gitignore",
        ]
        for relative in expected:
            self.assertTrue((self.target / relative).exists(), relative)

        forbidden = [
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
        for relative in forbidden:
            self.assertFalse((self.target / relative).exists(), relative)

        agents = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("<!-- agent-policy:start -->", agents)
        self.assertIn("retrieval-overlay policy stack", agents)
        self.assertIn("heuristics.md", agents)
        self.assertIn("even if they appeared after the conversation began", agents)
        self.assertIn("## Policy Layers", agents)
        self.assertIn("~/.agent-policy/tasks/<task-id>.md", agents)
        self.assertIn("~/.agent-policy/profile.md", agents)
        self.assertIn("Do not add filler guidance", agents)
        self.assertNotIn("Git already tracks it", agents)
        self.assertIn("relevant context in the current conversation, not only the latest message", agents)
        self.assertIn("A close match identifies where to compare", agents)
        self.assertIn("does not prove that the new signal is already covered", agents)
        self.assertIn("Keep the current experience set accurate and compact", agents)
        self.assertIn("policy prose and descriptive metadata in English", agents)
        self.assertIn("preserve identifiers exactly", agents)
        self.assertIn("use a short one-line title", agents)
        self.assertIn("more than one project scope", agents)
        self.assertIn("read its local agent guidance", agents)
        self.assertIn("relevant project scope's `knowledge.md`", agents)
        self.assertIn("read the relevant file in full as a final fallback", agents)
        self.assertIn("Use `current.md` only for compact project guidance", agents)
        self.assertIn("Store stable descriptive project facts in `knowledge.md`", agents)
        self.assertIn("do not treat the starting project as the scope for the whole task", agents)
        self.assertIn("agent-navi init --target <project-root>", agents)
        self.assertIn("signal, reusable takeaway, and future behavior are all clear", agents)
        self.assertIn("user intent is explicit, scope is clear, confidence is high", agents)
        self.assertIn("use more than one only when each serves a distinct purpose", agents)
        self.assertIn("failure avoidance, or output structure", agents)
        self.assertIn("reusable project workflow whose order or checkpoints matter", agents)
        self.assertIn("If none exists, leave the experience files unchanged", agents)
        self.assertIn("Candidate heuristics are considered only when explicitly requested", agents)
        self.assertIn("replace-entry", agents)
        for relative in ("CLAUDE.md", ".kiro/steering/agent-policy.md"):
            adapter = (self.target / relative).read_text(encoding="utf-8")
            self.assertIn("## Policy Layers", adapter)
            self.assertIn("~/.agent-policy/tasks/<task-id>.md", adapter)
            self.assertIn("~/.agent-policy/profile.md", adapter)
            self.assertIn("signal, reusable takeaway, and future behavior are all clear", adapter)
            self.assertIn("user intent is explicit, scope is clear, confidence is high", adapter)
            self.assertIn("current conversation, not only the latest message", adapter)
        current = (self.target / ".agent-policy" / "current.md").read_text(encoding="utf-8")
        self.assertIn("should be considered whenever this project scope becomes relevant", current)
        self.assertIn("Do not use this file for project knowledge", current)
        self.assertIn("## Project guidance", current)
        self.assertNotIn("Agent-native maintenance", current)
        self.assertNotIn("Lesson write threshold", current)
        self.assertNotIn("Heuristic write threshold", current)
        knowledge = (self.target / ".agent-policy" / "knowledge.md").read_text(encoding="utf-8")
        self.assertIn("Stable project-local facts", knowledge)
        self.assertIn("do not load it by default", knowledge)
        self.assertIn("reading the full file is the final fallback", knowledge)
        self.assertIn("Put project guidance in `current.md`", knowledge)
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertIn("use a short one-line human-readable title", lessons)
        self.assertIn("reusable future behavior", lessons)
        self.assertIn("update a close match instead of appending", lessons)
        heuristics = (self.target / ".agent-policy" / "heuristics.md").read_text(encoding="utf-8")
        self.assertIn("### Search bias", heuristics)
        self.assertIn("changes future search, planning, action selection", heuristics)
        self.assertIn("update a close match instead of appending", heuristics)
        self.assertNotIn("session-only", heuristics)
        playbooks = (self.target / ".agent-policy" / "playbooks.md").read_text(encoding="utf-8")
        self.assertIn("    ## Short task name", playbooks)
        gitignore = (self.target / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".agent-policy/", gitignore)
        self.assertNotIn(".agent-policy/heuristics.compact.md", gitignore)
        self.assertNotIn(".agent-policy/local.md", gitignore)
        self.assertIn("AGENTS.md", gitignore)
        self.assertIn("CLAUDE.md", gitignore)
        self.assertIn(".kiro/steering/agent-policy.md", gitignore)
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertIn("not an audit log", inbox)

    def test_init_suggests_one_time_current_knowledge_migration(self) -> None:
        policy = self.target / ".agent-policy"
        policy.mkdir()
        current = policy / "current.md"
        original = "# Current Agent Guidance\n\nExisting project facts and guidance.\n"
        current.write_text(original, encoding="utf-8")

        first = self.run_cli(["init", "--target", str(self.target)])

        self.assertTrue((policy / "knowledge.md").exists())
        self.assertEqual(original, current.read_text(encoding="utf-8"))
        self.assertIn("Created .agent-policy/knowledge.md and preserved the existing current.md", first)
        self.assertIn("Review .agent-policy/current.md incrementally", first)
        self.assertNotIn("0.2", first)
        self.assertNotIn("0.3", first)

        second = self.run_cli(["init", "--target", str(self.target)])

        self.assertNotIn("redistribute its contents by meaning", second)
        self.assertEqual(original, current.read_text(encoding="utf-8"))

    def test_init_no_ignore_leaves_gitignore_untouched(self) -> None:
        gitignore = self.target / ".gitignore"
        gitignore.write_text("custom-output/\n", encoding="utf-8")

        self.run_cli(["init", "--target", str(self.target), "--no-ignore"])

        self.assertEqual("custom-output/\n", gitignore.read_text(encoding="utf-8"))
        self.assertTrue((self.target / "AGENTS.md").exists())

    def test_init_replaces_legacy_per_file_ignore_rules(self) -> None:
        gitignore = self.target / ".gitignore"
        gitignore.write_text(
            "# Generated temporary Agent Navigator files\n"
            ".agent-policy/brief.md\n"
            ".agent-policy/lessons.compact.md\n"
            ".agent-policy/heuristics.compact.md\n"
            ".agent-policy/local.md\n",
            encoding="utf-8",
        )

        self.run_cli(["init", "--target", str(self.target)])

        updated = gitignore.read_text(encoding="utf-8")
        self.assertIn(".agent-policy/", updated)
        self.assertNotIn(".agent-policy/brief.md", updated)
        self.assertFalse(updated.startswith("\n"))

    def test_init_reports_legacy_brief_without_deleting_it(self) -> None:
        policy = self.target / ".agent-policy"
        policy.mkdir()
        legacy_brief = policy / "brief.md"
        legacy_brief.write_text("legacy task snapshot\n", encoding="utf-8")

        out = self.run_cli(["init", "--target", str(self.target)])

        self.assertIn("Legacy paths left in place; new commands do not use them", out)
        self.assertIn(".agent-policy/brief.md", out)
        self.assertEqual("legacy task snapshot\n", legacy_brief.read_text(encoding="utf-8"))

    def test_ignore_add_and_remove_only_manage_agent_navigator_rules(self) -> None:
        gitignore = self.target / ".gitignore"
        gitignore.write_text("custom-output/\n.agent-policy/\n", encoding="utf-8")

        out = self.run_cli(["ignore", "add", "--target", str(self.target)])
        self.assertIn("Added Agent Navigator ignore rules", out)
        added = gitignore.read_text(encoding="utf-8")
        self.assertIn("AGENTS.md", added)
        self.assertIn("CLAUDE.md", added)
        self.assertIn(".kiro/steering/agent-policy.md", added)

        out = self.run_cli(["ignore", "remove", "--target", str(self.target)])
        self.assertIn("Removed Agent Navigator ignore rules", out)
        removed = gitignore.read_text(encoding="utf-8")
        self.assertIn("custom-output/", removed)
        self.assertNotIn(".agent-policy/", removed)
        self.assertNotIn("AGENTS.md", removed)
        self.assertNotIn("CLAUDE.md", removed)
        self.assertNotIn(".kiro/steering/agent-policy.md", removed)

    def test_ignore_add_replaces_legacy_per_file_rules(self) -> None:
        gitignore = self.target / ".gitignore"
        gitignore.write_text(
            "custom-output/\n"
            "# Generated temporary Agent Navigator files\n"
            ".agent-policy/brief.md\n"
            ".agent-policy/lessons.compact.md\n"
            ".agent-policy/heuristics.compact.md\n"
            ".agent-policy/local.md\n",
            encoding="utf-8",
        )

        self.run_cli(["ignore", "add", "--target", str(self.target)])

        updated = gitignore.read_text(encoding="utf-8")
        self.assertIn("custom-output/", updated)
        self.assertIn(".agent-policy/", updated)
        self.assertNotIn(".agent-policy/brief.md", updated)
        self.assertNotIn(".agent-policy/heuristics.compact.md", updated)

    def test_ignore_add_warns_when_policy_files_are_already_tracked(self) -> None:
        policy = self.target / ".agent-policy"
        policy.mkdir()
        heuristic = policy / "heuristics.md"
        heuristic.write_text("# Heuristics\n", encoding="utf-8")
        subprocess.run(["git", "init", "--quiet"], cwd=self.target, check=True)
        subprocess.run(["git", "add", ".agent-policy/heuristics.md"], cwd=self.target, check=True)

        out = self.run_cli(["ignore", "add", "--target", str(self.target)])

        self.assertIn("Git already tracks Agent Navigator files", out)
        self.assertIn(".agent-policy/heuristics.md", out)
        self.assertIn("git rm -r --cached --ignore-unmatch", out)
        self.assertTrue(heuristic.exists())

    def test_setup_task_records_enabled_layer_without_copying_policy(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])

        out = self.run_cli(["setup", "--target", str(self.target), "--task", "trading-review", "--display", "交易复盘"])

        current = (self.target / ".agent-policy" / "current.md").read_text(encoding="utf-8")
        self.assertIn("Enabled task layers", current)
        self.assertIn("trading-review — 交易复盘 (`~/.agent-policy/tasks/trading-review.md`)", current)
        self.assertIn("not copied into the project", current)
        self.assertIn("Recorded enabled task layer", out)
        task_path = Path(os.environ["AGENT_POLICY_HOME"]) / ".agent-policy" / "tasks" / "trading-review.md"
        self.assertTrue(task_path.exists())
        task_text = task_path.read_text(encoding="utf-8")
        self.assertIn("Task ID: trading-review", task_text)
        self.assertIn("Display name: 交易复盘", task_text)
        self.assertIn("Aliases:", task_text)
        self.assertIn("Keywords:", task_text)
        self.assertFalse((self.target / ".agent-policy" / "tasks").exists())

        self.run_cli(["setup", "--target", str(self.target), "--task", "trading-review"])
        current = (self.target / ".agent-policy" / "current.md").read_text(encoding="utf-8")
        self.assertIn("trading-review — 交易复盘 (`~/.agent-policy/tasks/trading-review.md`)", current)
        self.assertNotIn("trading-review — trading-review", current)

        self.run_cli(["setup", "--target", str(self.target), "--task", "trading-review", "--display", "交易复盘更新"])
        current = (self.target / ".agent-policy" / "current.md").read_text(encoding="utf-8")
        self.assertIn("trading-review — 交易复盘更新 (`~/.agent-policy/tasks/trading-review.md`)", current)
        self.assertNotIn("trading-review — 交易复盘 (`~/.agent-policy/tasks/trading-review.md`)", current)
        self.assertIn("Display name: 交易复盘更新", task_path.read_text(encoding="utf-8"))

        with self.assertRaises(SystemExit):
            main(["setup", "--target", str(self.target), "--task", "交易复盘"])

    def test_init_global_creates_user_layer(self) -> None:
        out = self.run_cli(["init", "--global"])
        self.assertIn("Initialized global Agent Navigator layer", out)
        root = Path(os.environ["AGENT_POLICY_HOME"]) / ".agent-policy"
        self.assertTrue((root / "profile.md").exists())
        self.assertTrue((root / "heuristics.md").exists())
        self.assertTrue((root / "tasks").is_dir())

        heuristics = root / "heuristics.md"
        heuristics.write_text(heuristics.read_text(encoding="utf-8") + "\n## Preserve me\n", encoding="utf-8")
        self.run_cli(["init", "--global", "--force"])
        self.assertIn("## Preserve me", heuristics.read_text(encoding="utf-8"))

    def test_global_policy_home_override_is_independent_of_home(self) -> None:
        override_home = self.target / "override-home"
        regular_home = self.target / "regular-home"
        os.environ["AGENT_POLICY_HOME"] = str(override_home)
        os.environ["HOME"] = str(regular_home)

        self.run_cli(["init", "--global"])

        self.assertTrue((override_home / ".agent-policy" / "profile.md").exists())
        self.assertFalse((regular_home / ".agent-policy").exists())

    def test_init_interactive_does_not_crash_and_records_basic_answers(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            out = self.run_cli(["init", "--target", str(self.target), "--interactive"])
        self.assertIn("Interactive setup skipped", out)

        target = self.target / "interactive"
        answers = [
            "Build a file-based policy stack",
            "coding",
            "keep it minimal",
            "code review",
            "mixed",
        ]
        with patch("builtins.input", side_effect=answers):
            out = self.run_cli(["init", "--target", str(target), "--interactive"])
        self.assertIn("Recorded interactive setup notes", out)
        current = (target / ".agent-policy" / "current.md").read_text(encoding="utf-8")
        heuristics = (target / ".agent-policy" / "heuristics.md").read_text(encoding="utf-8")
        self.assertIn("Project setup notes", current)
        self.assertIn("Build a file-based policy stack", current)
        self.assertIn("Project setup retrieval heuristic", heuristics)

    def test_init_uses_marker_blocks_and_force_overwrites_generated_files(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        agents = self.target / "AGENTS.md"
        lessons = self.target / ".agent-policy" / "lessons.md"
        agents.write_text("custom\n", encoding="utf-8")
        lessons.write_text(lessons.read_text(encoding="utf-8") + "\n## Preserve me\n", encoding="utf-8")

        self.run_cli(["init", "--target", str(self.target)])
        content = agents.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("custom\n"))
        self.assertEqual(content.count("<!-- agent-policy:start -->"), 1)

        self.run_cli(["init", "--target", str(self.target), "--force"])
        content = agents.read_text(encoding="utf-8")
        self.assertFalse(content.startswith("custom\n"))
        self.assertIn("Agent Guidance", content)
        self.assertIn("## Preserve me", lessons.read_text(encoding="utf-8"))

    def test_init_updates_generated_legacy_agent_md(self) -> None:
        legacy = self.target / "agent.md"
        legacy.write_text(
            "<!-- agent-policy:start -->\n# Old generated guidance\n<!-- agent-policy:end -->\n",
            encoding="utf-8",
        )

        out = self.run_cli(["init", "--target", str(self.target)])
        self.assertIn("Updated generated legacy agent guidance", out)
        content = legacy.read_text(encoding="utf-8")
        self.assertIn("# Agent Guidance", content)
        self.assertIn("retrieval-overlay policy stack", content)
        self.assertNotIn("Old generated guidance", content)
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertNotIn("Legacy agent guidance pending migration", inbox)

    def test_init_preserves_custom_legacy_agent_md_and_records_migration(self) -> None:
        legacy = self.target / "agent.md"
        legacy.write_text("# Existing agent guidance\n\nKeep this project concise.\n", encoding="utf-8")

        out = self.run_cli(["init", "--target", str(self.target)])
        self.assertIn("Legacy agent guidance left in place for migration", out)
        self.assertEqual(
            legacy.read_text(encoding="utf-8"),
            "# Existing agent guidance\n\nKeep this project concise.\n",
        )
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertIn("Legacy agent guidance pending migration", inbox)
        self.assertIn("Source: `agent.md`", inbox)
        self.assertIn("not content to overwrite automatically", inbox)

        self.run_cli(["init", "--target", str(self.target)])
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertEqual(inbox.count("Legacy agent guidance pending migration"), 1)

    def test_add_feedback_raw_defaults_to_inbox(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(["add-feedback", "--target", str(self.target), "This table is useful"])

        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertIn("not an audit log", inbox)
        self.assertIn("## 2026-06-18 — general lesson", inbox)
        self.assertIn("Signal: This table is useful", inbox)
        self.assertIn("Status: candidate", inbox)
        self.assertNotIn("This table is useful", lessons)

    def test_add_feedback_complete_lesson_writes_searchable_active_entry(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--type",
                "negative",
                "--title",
                "Code review scope must be explicit",
                "--applies-to",
                "code review",
                "--keywords",
                "git status, unstaged changes, review scope",
                "--signal",
                "User asked whether uncommitted code had been reviewed.",
                "--lesson",
                "Code review should not assume scope is only the latest commit.",
                "--next-time",
                "Check git status and inspect staged, unstaged, and relevant untracked changes unless the user narrows scope.",
            ]
        )
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertIn("## 2026-06-18 — Code review scope must be explicit", lessons)
        self.assertIn("Type: negative", lessons)
        self.assertIn("Applies to: code review", lessons)
        self.assertIn("Keywords: git status, unstaged changes, review scope", lessons)
        self.assertIn("Status: active", lessons)

    def test_add_heuristic_writes_project_entry_without_requiring_search_bias(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--title",
                "Code review starts from repository state",
                "--applies-to",
                "code review",
                "--keywords",
                "git status, unstaged, untracked",
                "--source",
                "user correction",
                "--heuristic",
                "Start code review by checking the repository state before narrowing scope.",
                "--search-bias",
                "Inspect git status, staged changes, unstaged changes, and relevant untracked files early.",
                "--avoids",
                "Assuming only the latest commit is in scope.",
            ]
        )
        heuristics = (self.target / ".agent-policy" / "heuristics.md").read_text(encoding="utf-8")
        self.assertIn("## Code review starts from repository state", heuristics)
        self.assertIn("### Heuristic", heuristics)
        self.assertIn("### Search bias\n\nInspect git status", heuristics)
        self.assertIn("### Avoids\n\nAssuming only the latest commit", heuristics)
        self.assertIn("Status: active", heuristics)

        self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--title",
                "Keep retrieval direct",
                "--heuristic",
                "Search relevant policy files directly from the current task context.",
            ]
        )
        heuristics = (self.target / ".agent-policy" / "heuristics.md").read_text(encoding="utf-8")
        self.assertIn("## Keep retrieval direct", heuristics)
        self.assertIn("Status: active", heuristics)
        direct_entry = heuristics.split("## Keep retrieval direct", 1)[1]
        self.assertNotIn("### Search bias", direct_entry)

        self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--title",
                "Incomplete heuristic",
            ]
        )
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertIn("Incomplete heuristic signal", inbox)
        self.assertIn("Status: candidate", inbox)
        self.assertNotIn("Search bias: TBD", heuristics)

    def test_add_heuristic_dry_run_prints_entry_without_writing(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])

        out = self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--title",
                "Preview review scope",
                "--heuristic",
                "Preview the heuristic before committing it.",
                "--search-bias",
                "Inspect the proposed text and destination first.",
                "--dry-run",
            ]
        )
        heuristics = (self.target / ".agent-policy" / "heuristics.md").read_text(encoding="utf-8")
        self.assertIn("Dry run: no files changed.", out)
        self.assertIn("Destination:", out)
        self.assertIn("## Preview review scope", out)
        self.assertNotIn("Preview review scope", heuristics)

        out = self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--task",
                "trading-review",
                "--title",
                "复盘先看计划",
                "--heuristic",
                "先看原始交易计划。",
                "--search-bias",
                "优先检索交易计划和执行记录。",
                "--dry-run",
            ]
        )
        task_path = Path(os.environ["AGENT_POLICY_HOME"]) / ".agent-policy" / "tasks" / "trading-review.md"
        self.assertIn(str(task_path), out)
        self.assertFalse(task_path.exists())

    def test_replace_entry_uses_one_exact_heading_and_preserves_neighbors(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        heuristics_path = self.target / ".agent-policy" / "heuristics.md"
        heuristics_path.write_text(
            """# Heuristics

## First entry

Applies to: code review
Keywords: git status
Source: user correction
Heuristic: Old guidance.
Search bias: Inspect old context.
Status: active

## Neighbor entry

Applies to: document qa
Keywords: sources
Source: project discussion
Heuristic: Preserve this entry.
Search bias: Retrieve sources.
Status: active
""",
            encoding="utf-8",
        )
        replacement = self.target / "replacement.md"
        replacement.write_text(
            """## Updated first entry

Applies to: code review
Keywords: git status, scope
Source: user correction
Status: active

### Heuristic

Use current repository state to establish review scope.

### Search bias

- Inspect staged changes.
- Inspect unstaged changes.
""",
            encoding="utf-8",
        )

        before = heuristics_path.read_text(encoding="utf-8")
        out = self.run_cli(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "heuristics",
                "--heading",
                "First entry",
                "--from",
                str(replacement),
                "--dry-run",
            ]
        )
        self.assertIn("Dry run: no files changed.", out)
        self.assertIn("-## First entry", out)
        self.assertIn("+## Updated first entry", out)
        self.assertEqual(heuristics_path.read_text(encoding="utf-8"), before)

        out = self.run_cli(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "heuristics",
                "--heading",
                "First entry",
                "--from",
                str(replacement),
            ]
        )
        updated = heuristics_path.read_text(encoding="utf-8")
        self.assertIn("Replaced exact entry", out)
        self.assertNotIn("## First entry", updated)
        self.assertIn("## Updated first entry", updated)
        self.assertIn("## Neighbor entry", updated)
        self.assertIn("Preserve this entry.", updated)

        code, out = self.run_cli_with_code(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "heuristics",
                "--heading",
                "Missing entry",
                "--from",
                str(replacement),
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("Exact heading not found", out)
        self.assertEqual(heuristics_path.read_text(encoding="utf-8"), updated)

    def test_replace_entry_supports_project_playbooks(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        playbooks_path = self.target / ".agent-policy" / "playbooks.md"
        playbooks_path.write_text(
            """# Playbooks

## Adapter update

Aliases: generated guidance
Keywords: implementation-planning, adapters

Steps:
1. Update the source template.
2. Sync adapters.
""",
            encoding="utf-8",
        )
        replacement = self.target / "replacement-playbook.md"
        replacement.write_text(
            """## Adapter update

Aliases: generated guidance
Keywords: implementation-planning, adapters

Steps:
1. Update the source template.
2. Run tests.
3. Sync and verify adapters.
""",
            encoding="utf-8",
        )

        self.run_cli(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "playbooks",
                "--heading",
                "Adapter update",
                "--from",
                str(replacement),
            ]
        )
        updated = playbooks_path.read_text(encoding="utf-8")
        self.assertIn("2. Run tests.", updated)
        self.assertIn("3. Sync and verify adapters.", updated)

    def test_replace_entry_supports_project_knowledge(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        knowledge_path = self.target / ".agent-policy" / "knowledge.md"
        knowledge_path.write_text(
            """# Project Knowledge

## Service ownership

Keywords: service, ownership

The worker owns report generation.
""",
            encoding="utf-8",
        )
        replacement = self.target / "replacement-knowledge.md"
        replacement.write_text(
            """## Service ownership

Keywords: service, ownership

The worker owns report generation and translation.
""",
            encoding="utf-8",
        )

        self.run_cli(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "knowledge",
                "--heading",
                "Service ownership",
                "--from",
                str(replacement),
            ]
        )

        updated = knowledge_path.read_text(encoding="utf-8")
        self.assertIn("generation and translation", updated)

    def test_replace_entry_rejects_duplicate_exact_headings(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        heuristics_path = self.target / ".agent-policy" / "heuristics.md"
        heuristics_path.write_text(
            """# Heuristics

## Duplicate

First body.

## Duplicate

Second body.
""",
            encoding="utf-8",
        )
        replacement = self.target / "replacement.md"
        replacement.write_text("## Replacement\n\nNew body.\n", encoding="utf-8")
        before = heuristics_path.read_text(encoding="utf-8")

        code, out = self.run_cli_with_code(
            [
                "replace-entry",
                "--target",
                str(self.target),
                "--file",
                "heuristics",
                "--heading",
                "Duplicate",
                "--from",
                str(replacement),
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("occurs 2 times", out)
        self.assertEqual(heuristics_path.read_text(encoding="utf-8"), before)

    def test_add_feedback_without_title_uses_metadata_heading_not_content_slice(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        long_lesson = (
            "Document QA should preserve source attribution and avoid long generated headings "
            "that slice agent-authored content in the middle of a word."
        )
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--applies-to",
                "document qa",
                "--keywords",
                "source attribution, headings",
                "--signal",
                "A long signal should not become a chopped title.",
                "--lesson",
                long_lesson,
                "--next-time",
                "Use a short title or metadata fallback, and keep details in the body.",
            ]
        )
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertIn("## 2026-06-18 — document qa lesson", lessons)
        self.assertNotIn(long_lesson[:72], lessons.splitlines()[15:])

    def test_incomplete_feedback_always_goes_to_inbox(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--applies-to",
                "research",
                "--signal",
                "Source citation was useful.",
                "--lesson",
                "Citations help the user audit the answer.",
                "--status",
                "candidate",
            ]
        )
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--signal",
                "Active but incomplete should not become a lesson.",
                "--status",
                "active",
            ]
        )
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertIn("Source citation was useful.", inbox)
        self.assertIn("Active but incomplete should not become a lesson.", inbox)
        self.assertNotIn("Lesson: TBD", lessons)
        self.assertNotIn("Next time: TBD", lessons)

        with self.assertRaises(SystemExit):
            main(
                [
                    "add-feedback",
                    "--target",
                    str(self.target),
                    "--signal",
                    "Temporary signal",
                    "--lesson",
                    "Temporary lesson",
                    "--next-time",
                    "Temporary action",
                    "--status",
                    "session-only",
                ]
            )

    def test_add_heuristic_task_requires_stable_english_task_id(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(["init", "--global"])
        self.run_cli(
            [
                "add-heuristic",
                "--target",
                str(self.target),
                "--task",
                "trading-review",
                "--title",
                "复盘先看交易计划",
                "--applies-to",
                "交易复盘",
                "--keywords",
                "交易复盘, 计划, 执行",
                "--source",
                "user preference",
                "--heuristic",
                "先对照原始交易计划，再评价执行质量。",
                "--search-bias",
                "优先检索交易计划、入场理由、止损和退出记录。",
            ]
        )
        task_path = Path(os.environ["AGENT_POLICY_HOME"]) / ".agent-policy" / "tasks" / "trading-review.md"
        self.assertTrue(task_path.exists())
        self.assertEqual(task_path.name, "trading-review.md")
        task_text = task_path.read_text(encoding="utf-8")
        self.assertIn("复盘先看交易计划", task_text)
        self.assertIn("Task ID: trading-review", task_text)
        self.assertIn("Display name:", task_text)
        self.assertIn("Aliases:", task_text)
        self.assertIn("Keywords:", task_text)
        self.assertIn("Status: active", task_text)

        with self.assertRaises(SystemExit):
            main(
                [
                    "add-heuristic",
                    "--target",
                    str(self.target),
                    "--task",
                    "代码 Review",
                    "--title",
                    "代码 review 先看范围",
                    "--heuristic",
                    "先确认 review 范围。",
                    "--search-bias",
                    "优先检查变更范围和 git status。",
                ]
            )

    def test_sync_preserves_existing_content_with_marker_blocks(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        agents = self.target / "AGENTS.md"
        agents.write_text("Custom human note.\n", encoding="utf-8")

        self.run_cli(["sync", "--target", str(self.target)])
        content = agents.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("Custom human note."))
        self.assertEqual(content.count("<!-- agent-policy:start -->"), 1)
        self.assertIn("retrieval-overlay policy stack", content)
        self.assertIn("relevant context in the current conversation, not only the latest message", content)
        self.assertIn("A close match identifies where to compare", content)
        self.assertIn("Keep the current experience set accurate and compact", content)
        self.assertIn("more than one project scope", content)
        self.assertIn("Store stable descriptive project facts in `knowledge.md`", content)
        self.assertIn("agent-navi init --target <project-root>", content)
        self.assertIn("replace-entry", content)

        self.run_cli(["sync", "--target", str(self.target)])
        content = agents.read_text(encoding="utf-8")
        self.assertEqual(content.count("<!-- agent-policy:start -->"), 1)

    def test_import_handles_target_relative_globs_and_records_inbox_note(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        notes = self.target / "notes"
        notes.mkdir()
        (notes / "a.md").write_text("# A\n", encoding="utf-8")
        (notes / "b.md").write_text("# B\n", encoding="utf-8")

        out = self.run_cli(["import", "--target", str(self.target), "notes/*.md", "--applies-to", "research"])
        self.assertIn("Imported 2 file", out)
        imported = list((self.target / ".agent-policy" / "imports" / "raw").glob("*.md"))
        self.assertEqual(len(imported), 2)
        inbox = (self.target / ".agent-policy" / "inbox.md").read_text(encoding="utf-8")
        self.assertIn("Applies to: research", inbox)
        self.assertIn("Imported raw source file", inbox)

    def test_compact_writes_draft_without_rewriting_lessons_by_default(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.add_lesson("research", "source attribution", "Preserve source attribution.", "Separate evidence from interpretation.", "active")
        lessons_path = self.target / ".agent-policy" / "lessons.md"
        before = lessons_path.read_text(encoding="utf-8")

        self.run_cli(["compact", "--target", str(self.target)])
        compact = (self.target / ".agent-policy" / "lessons.compact.md").read_text(encoding="utf-8")
        self.assertIn("Lessons Compact Draft", compact)
        self.assertIn("## research", compact)
        self.assertTrue((self.target / ".agent-policy" / "heuristics.compact.md").exists())
        self.assertEqual(before, lessons_path.read_text(encoding="utf-8"))

        code, out = self.run_cli_with_code(["compact", "--target", str(self.target), "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("compact --apply is not supported yet", out)
        self.assertEqual(before, lessons_path.read_text(encoding="utf-8"))

    def test_compact_reads_legacy_and_sectioned_heuristics(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        heuristics_path = self.target / ".agent-policy" / "heuristics.md"
        heuristics_path.write_text(
            """# Heuristics

## Sectioned source guidance

Applies to: document qa
Keywords: document sources evidence
Source: user correction
Status: active

### Heuristic

Ground answers in the source document.

### Search bias

Retrieve source passages first.

## Legacy source guidance

Applies to: document qa
Keywords: document sources citations
Source: project discussion
Heuristic: Preserve source attribution.
Search bias: Check citations before finalizing.
Status: active
""",
            encoding="utf-8",
        )

        self.run_cli(["compact", "--target", str(self.target)])

        compact = (self.target / ".agent-policy" / "heuristics.compact.md").read_text(encoding="utf-8")
        self.assertIn("Ground answers in the source document.", compact)
        self.assertIn("Retrieve source passages first.", compact)
        self.assertIn("Preserve source attribution.", compact)
        self.assertIn("Check citations before finalizing.", compact)

    def test_compact_ignores_markdown_headings_inside_code_fences(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        heuristics_path = self.target / ".agent-policy" / "heuristics.md"
        heuristics_path.write_text(
            '''# Heuristics

## Preserve Markdown examples

Applies to: documentation
Keywords: examples
Source: user correction
Status: active

### Heuristic

Preserve examples such as:

```markdown
## Example heading
### Nested example
```

Continue preserving the surrounding guidance.
''',
            encoding="utf-8",
        )

        self.run_cli(["compact", "--target", str(self.target)])

        compact = (self.target / ".agent-policy" / "heuristics.compact.md").read_text(encoding="utf-8")
        self.assertIn("Continue preserving the surrounding guidance.", compact)

    def test_compact_preserves_multiline_lesson_fields(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--title",
                "Wrapped lesson",
                "--signal",
                "signal",
                "--lesson",
                "First line.\nSecondword remains available.",
                "--next-time",
                "Apply both lines.",
            ]
        )

        self.run_cli(["compact", "--target", str(self.target)])

        compact = (self.target / ".agent-policy" / "lessons.compact.md").read_text(encoding="utf-8")
        self.assertIn("First line. Secondword remains available.", compact)

    def test_checks_print_lightweight_reminders(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])

        out = self.run_cli(["check", "code-review", "--target", str(self.target)])
        self.assertIn("Confirm review scope", out)
        self.assertIn("Check git status", out)
        self.assertIn("State reviewed scope", out)

        out = self.run_cli(["check", "document-qa", "--target", str(self.target)])
        self.assertIn("Retrieve relevant source passages", out)
        self.assertIn("Cite source locations", out)

        review = self.target / "review.md"
        review.write_text("Market context and thesis. Risk, sizing, execution, uncertain lesson.\n", encoding="utf-8")
        out = self.run_cli(["check", "trading-review", "--target", str(self.target), "--review", str(review)])
        self.assertIn("not trading advice", out)
        self.assertIn("setup thesis: pass", out)

    def test_cli_requires_initialized_policy_and_removed_commands_stay_removed(self) -> None:
        with self.assertRaises(SystemExit):
            main(["add-feedback", "--target", str(self.target), "--signal", "ok"])
        with self.assertRaises(SystemExit):
            main(["propose", "--target", str(self.target)])
        with self.assertRaises(SystemExit):
            main(["brief", "--target", str(self.target), "code review"])

    def test_init_refuses_to_follow_adapter_symlink(self) -> None:
        repo = self.target / "repo"
        repo.mkdir()
        outside = self.target / "outside.md"
        outside.write_text("outside stays unchanged\n", encoding="utf-8")
        try:
            (repo / "AGENTS.md").symlink_to(outside)
        except (NotImplementedError, OSError):
            self.skipTest("Symbolic links are unavailable on this platform")

        with self.assertRaises(SystemExit):
            main(["init", "--target", str(repo)])

        self.assertEqual(outside.read_text(encoding="utf-8"), "outside stays unchanged\n")
        self.assertTrue((repo / "AGENTS.md").is_symlink())

    def test_init_refuses_symlinked_policy_directory(self) -> None:
        repo = self.target / "repo"
        outside = self.target / "outside-policy"
        repo.mkdir()
        outside.mkdir()
        try:
            (repo / ".agent-policy").symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("Symbolic links are unavailable on this platform")

        with self.assertRaises(SystemExit):
            main(["init", "--target", str(repo)])

        self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_feedback_writes_do_not_lose_entries(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        env = os.environ.copy()
        project_root = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = str(project_root)
        processes: list[subprocess.Popen[str]] = []
        for index in range(20):
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "agent_navigator",
                        "add-feedback",
                        "--target",
                        str(self.target),
                        "--title",
                        f"Concurrent {index}",
                        "--signal",
                        f"signal {index}",
                        "--lesson",
                        f"lesson {index}",
                        "--next-time",
                        f"next {index}",
                    ],
                    cwd=project_root,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )

        failures: list[str] = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            if process.returncode != 0:
                failures.append(stdout + stderr)
        self.assertEqual(failures, [])
        lessons = (self.target / ".agent-policy" / "lessons.md").read_text(encoding="utf-8")
        self.assertEqual(lessons.count(" — Concurrent "), 20)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not available on Windows")
    def test_global_policy_uses_private_permissions(self) -> None:
        self.run_cli(["init", "--global"])
        root = Path(os.environ["AGENT_POLICY_HOME"]) / ".agent-policy"
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((root / "tasks").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((root / "profile.md").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((root / "heuristics.md").stat().st_mode), 0o600)

        os.chmod(root, 0o755)
        os.chmod(root / "profile.md", 0o644)
        self.run_cli(["init", "--global"])
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((root / "profile.md").stat().st_mode), 0o600)

    def test_import_resolves_relative_globs_only_from_target(self) -> None:
        repo = self.target / "repo"
        caller = self.target / "caller"
        (repo / "notes").mkdir(parents=True)
        (caller / "notes").mkdir(parents=True)
        (repo / "notes" / "target.md").write_text("target source\n", encoding="utf-8")
        (caller / "notes" / "caller.md").write_text("caller source\n", encoding="utf-8")
        self.run_cli(["init", "--target", str(repo)])

        old_cwd = Path.cwd()
        try:
            os.chdir(caller)
            self.run_cli(["import", "--target", str(repo), "notes/*.md"])
        finally:
            os.chdir(old_cwd)

        imported = list((repo / ".agent-policy" / "imports" / "raw").glob("*.md"))
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].read_text(encoding="utf-8"), "target source\n")

    def test_heuristic_destination_flags_are_mutually_exclusive(self) -> None:
        self.run_cli(["init", "--target", str(self.target)])
        with self.assertRaises(SystemExit):
            main(
                [
                    "add-heuristic",
                    "--target",
                    str(self.target),
                    "--global",
                    "--task",
                    "code-review",
                    "--title",
                    "Ambiguous destination",
                    "--heuristic",
                    "Reject ambiguous destinations.",
                ]
            )

    def add_lesson(self, applies_to: str, keywords: str, lesson: str, next_time: str, status: str) -> None:
        self.run_cli(
            [
                "add-feedback",
                "--target",
                str(self.target),
                "--applies-to",
                applies_to,
                "--keywords",
                keywords,
                "--signal",
                f"Signal for {applies_to}",
                "--lesson",
                lesson,
                "--next-time",
                next_time,
                "--status",
                status,
            ]
        )


if __name__ == "__main__":
    unittest.main()
