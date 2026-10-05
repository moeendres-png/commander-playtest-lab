from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_agent_root_is_compact_router() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents.encode("utf-8")) < 15_000
    assert "Read-on-demand policy routing" in agents
    assert "Rules Core alone determines legal actions" in agents
    assert "UNKNOWN != PASS" in agents
    assert "PRODUCTION_PROVIDER = NOT_SELECTED" in agents
    assert "ARCHITECTURE_FREEZE = NOT_CLAIMED" in agents
    assert "PRODUCTION_REPOSITORY = NOT_CREATED" in agents


def test_routed_policy_modules_preserve_critical_rules() -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "docs/agent-policy/execution-and-authority.md",
        ROOT / "docs/agent-policy/reuse-git-and-workstreams.md",
        ROOT / "docs/agent-policy/privacy-completion-and-handoff.md",
    ]
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    required = [
        "AUTONOMOUS_CAMPAIGN_AUTHORITY = ENABLED",
        "NEW_IMPLEMENTATION_REQUIRED",
        "DELEGATED_GIT_INTEGRATION_AUTHORITY = ENABLED",
        "no force push in any spelling",
        "Cross-workstream access",
        "Raw credentials, keys, and tokens are",
        "Semantic Completion Rule",
        "Source Lock; Work Completed; New Findings; Changes; Tests/Evidence",
    ]
    for phrase in required:
        assert phrase in corpus, phrase


def test_agent_router_links_exist() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for relative in (
        "docs/agent-policy/execution-and-authority.md",
        "docs/agent-policy/reuse-git-and-workstreams.md",
        "docs/agent-policy/privacy-completion-and-handoff.md",
        ".claude/skills/COMMANDER_ROUTING.md",
    ):
        assert relative in agents
        assert (ROOT / relative).is_file()


def test_claude_efficiency_configuration_present() -> None:
    mcp = (ROOT / ".mcp.json").read_text(encoding="utf-8")
    settings = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    serena = (ROOT / ".serena/project.yml").read_text(encoding="utf-8")
    assert "b4a83eec1097042f34a09985783c9491f99919c4" in mcp
    assert "claude_rtk_hook.py" in settings
    assert "read_only: true" in serena
    assert "no-memories" in serena
