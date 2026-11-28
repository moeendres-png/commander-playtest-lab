"""Claude Code routing policy: helper tiers, flat topology and the AGENTS.md/CLAUDE.md split.

Owner instruction 2026-11-28: helpers follow Anthropic's guidance (Haiku for simple read-only
jobs, Sonnet for coding, Opus for review); CLAUDE.md holds only what is Claude-specific and
imports AGENTS.md; AGENTS.md holds only rules for every agent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / ".claude" / "agents"

ACTIVE_ROUTING = (
    ROOT / "CLAUDE.md",
    ROOT / "docs" / "claude" / "SESSION_PLAYBOOK.md",
    ROOT / ".claude" / "skills" / "COMMANDER_ROUTING.md",
    ROOT / ".claude" / "skills" / "lab-ops" / "SKILL.md",
    *sorted(AGENTS_DIR.glob("*.md")),
)

# name -> (model, effort, omitClaudeMd, may write)
HELPERS = {
    "scout": ("haiku", "low", True, False),
    "ci-triage": ("sonnet", "medium", True, False),
    "builder": ("sonnet", "high", False, True),
    "reviewer": ("opus", "high", False, False),
}
EFFORT_WORD = {"low": "low", "medium": "medium", "high": "high"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> dict[str, str]:
    text = read(path)
    assert text.startswith("---\n"), path.name
    block = text.split("---\n", 2)[1]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def test_project_defaults_to_medium_and_unassigned_subagents_to_sonnet():
    settings = json.loads(read(ROOT / ".claude" / "settings.json"))
    assert settings["effortLevel"] == "medium"
    assert settings["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"


def test_the_helper_set_is_exactly_the_documented_one():
    assert {p.stem for p in AGENTS_DIR.glob("*.md")} == set(HELPERS)


def test_each_helper_pins_model_effort_context_and_tools():
    assert len(HELPERS) == 4
    for name, (model, effort, omit, writes) in HELPERS.items():
        fm = frontmatter(AGENTS_DIR / f"{name}.md")
        assert fm["name"] == name
        assert fm["model"] == model, name
        assert fm["effort"] == effort, name
        assert int(fm["maxTurns"]) > 0, name
        assert (fm.get("omitClaudeMd") == "true") is omit, name
        tools = {t.strip() for t in fm["tools"].split(",")}
        assert "Agent" not in tools and "Task" not in tools, name
        assert ({"Edit", "Write"} & tools != set()) is writes, name
        assert fm["description"].startswith("Use"), name


def test_claude_md_table_matches_the_frontmatter():
    text = read(ROOT / "CLAUDE.md")
    assert len(HELPERS) == 4
    for name, (model, effort, _omit, _writes) in HELPERS.items():
        row = re.search(rf"^\| `{re.escape(name)}` \| ([A-Za-z]+) / ([a-z]+) \|", text, re.M)
        assert row, name
        assert row.group(1).lower() == model and row.group(2) == EFFORT_WORD[effort], name


def test_claude_md_imports_agents_md_and_stays_short():
    text = read(ROOT / "CLAUDE.md")
    assert "@AGENTS.md" in text.splitlines()[:5]
    assert len(text.splitlines()) <= 200
    flat = " ".join(text.split())
    assert "no automatic fallback between models" in flat
    assert "none spawns children" in flat
    assert "No agent teams or recursive coordinator/worker trees" in flat
    # Delegation discipline: consume the report, no duplicate reads.
    assert "Consume a helper's report first" in flat
    # The MATERIAL review never runs below the reviewer tier.
    assert "always runs on `reviewer`" in flat


def test_agents_md_is_tool_neutral():
    text = read(ROOT / "AGENTS.md")
    for tier in ("Sonnet", "Opus", "Haiku", "omitClaudeMd", "Claude sessions"):
        assert tier not in text, tier
    flat = " ".join(text.split())
    assert "each tool's own entrypoint" in flat
    assert "the Lead's level or higher" in flat


def test_active_claude_routing_has_only_current_executor_policy():
    joined = "\n".join(read(path) for path in ACTIVE_ROUTING)
    assert "no automatic fallback" in joined.lower()
    for removed in ("muse-spark", "glm", "log-scanner", "evidence-reviewer"):
        assert removed not in joined.lower(), removed
    # The OpenCode/Foundry lanes were removed (Owner decision 2026-11-12): no active
    # routing surface names them or their model ids.
    for removed in ("opencode", "deepseek", "foundry", "/assure", "/ro-review", "oc_dispatch"):
        assert removed not in joined.lower(), removed


def test_helper_effort_policy_is_per_agent_not_a_blanket_rule():
    """Neither the retired blanket rule nor the retired Haiku ban returns."""
    for path in ACTIVE_ROUTING:
        flat = " ".join(read(path).split())
        assert "at least Sonnet at `high`" not in flat, path.name
        assert "never Haiku" not in flat, path.name
