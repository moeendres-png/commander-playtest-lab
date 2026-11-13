from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACTIVE_ROUTING = (
    ROOT / "CLAUDE.md",
    ROOT / "docs" / "claude" / "SESSION_PLAYBOOK.md",
    ROOT / ".claude" / "skills" / "COMMANDER_ROUTING.md",
    ROOT / ".claude" / "skills" / "lab-ops" / "SKILL.md",
    ROOT / ".claude" / "agents" / "log-scanner.md",
    ROOT / ".claude" / "agents" / "ci-triage.md",
    ROOT / ".claude" / "agents" / "evidence-reviewer.md",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> str:
    text = read(path)
    assert text.startswith("---\n")
    return text.split("---\n", 2)[1]


def test_project_defaults_to_medium_and_unassigned_subagents_to_sonnet():
    settings = json.loads(read(ROOT / ".claude" / "settings.json"))
    assert settings["effortLevel"] == "medium"
    assert settings["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"


def test_specialized_helper_models_effort_turns_and_context_are_bounded():
    log = frontmatter(ROOT / ".claude" / "agents" / "log-scanner.md")
    assert "model: sonnet" in log
    assert "effort: low" in log
    assert "maxTurns: 10" in log
    assert "omitClaudeMd: true" in log

    triage = frontmatter(ROOT / ".claude" / "agents" / "ci-triage.md")
    assert "model: sonnet" in triage
    assert "effort: medium" in triage
    assert "maxTurns: 18" in triage
    assert "omitClaudeMd: true" in triage

    review = frontmatter(ROOT / ".claude" / "agents" / "evidence-reviewer.md")
    assert "model: opus" in review
    assert "effort: high" in review
    assert "maxTurns: 30" in review
    assert "omitClaudeMd:" not in review


def test_project_helpers_are_read_only_and_cannot_spawn_agents():
    for name in ("log-scanner.md", "ci-triage.md", "evidence-reviewer.md"):
        fm = frontmatter(ROOT / ".claude" / "agents" / name)
        tools_line = next(line for line in fm.splitlines() if line.startswith("tools:"))
        assert "Write" not in tools_line
        assert "Edit" not in tools_line
        assert "Agent" not in tools_line


def test_active_claude_routing_has_only_current_executor_policy():
    joined = "\n".join(read(path) for path in ACTIVE_ROUTING)
    assert "no automatic fallback" in joined.lower()
    assert "muse-spark" not in joined.lower()
    assert "glm" not in joined.lower()
    # The OpenCode/Foundry lanes were removed (Owner decision 2026-11-12): no active
    # routing surface names them or their model ids.
    for removed in ("opencode", "deepseek", "foundry", "/assure", "/ro-review", "oc_dispatch"):
        assert removed not in joined.lower(), removed


def test_claude_policy_allows_sonnet_workers_but_forbids_agent_trees_and_duplicate_reads():
    """Owner decision: Claude Sonnet 5.5 may be an implementation worker.

    Recursive coordinator/worker trees and duplicate re-reading of worker output stay forbidden.
    """
    text = read(ROOT / "CLAUDE.md")
    flat = " ".join(text.split())
    # Sonnet is an authorized worker tier; it is no longer forbidden as an implementer.
    assert "Claude Sonnet" in flat
    assert "may also be an implementation worker" in flat
    assert "Do not use `general-purpose`" not in flat
    # Flat helpers, no agent teams or recursive trees.
    assert "must not\nspawn children" in text
    assert "Do not create agent teams or recursive coordinator/worker trees" in flat
    # Delegation discipline: no duplicate reads of worker output.
    assert "Do not automatically re-read" in text
    # Owner instruction 2026-10-16: models are selected manually; the always-read
    # entrypoint carries no model allowlist and no fallback between models.
    assert "the worker the Owner selected" in flat
    assert "No automatic fallback between models" in flat
    assert "opencode" not in flat.lower()


def test_helper_effort_policy_is_per_agent_not_a_blanket_high_rule():
    """The retired blanket rule must not return to any active routing surface."""
    for path in ACTIVE_ROUTING:
        flat = " ".join(read(path).split())
        assert "at least Sonnet at `high`" not in flat, path.name
    for rel in (".claude/skills/lab-ops/SKILL.md",):
        flat = " ".join(read(ROOT / rel).split())
        assert "Sonnet `low`" in flat and "Sonnet `medium`" in flat, rel
        assert "never Haiku" in flat, rel
