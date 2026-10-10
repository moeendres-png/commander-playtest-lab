"""Controls for the direct review lane's runtime agent identity (#654).

The pinned ``opencode github run`` ignores ``AGENT`` and prompts the config's
``default_agent``. These tests pin the CLI semantics the checker mirrors
(``Wildcard.match``, last-match-wins ``Permission.evaluate``), the preflight on
the CLI's own resolved config and agent, and the post-run audit of the run's
``stream`` records, including the real record from run 37936416385.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from tools.foundry import quota_watchdog as qw
from tools.foundry import review_runtime_identity as rid

REPO_ROOT = Path(__file__).resolve().parents[2]

# Job 113839482326 (run 37936416385), lines 313-320: the workflow said
# AGENT=foundry-reviewer, the CLI ran foundry-implementer.
REAL_IMPLEMENTER_RECORD = """\
2026-10-09T13:23:08.8841181Z [13:23:08.883] INFO (#8297): process {
2026-10-09T13:23:08.8841750Z   "session.id": "ses_edf2b1c17ffeagl4A4gQpslPs1",
2026-10-09T13:23:08.8842230Z   messageID: "msg_120d4ecde001d1u6tDh20ETVYb",
2026-10-09T13:23:08.8842637Z }
2026-10-09T13:23:08.8851119Z [13:23:08.884] INFO (#8297): stream {
2026-10-09T13:23:08.8851596Z   providerID: "opencode-go",
2026-10-09T13:23:08.8852072Z   modelID: "space-bunny",
2026-10-09T13:23:08.8852437Z   "session.id": "ses_edf2b1c17ffeagl4A4gQpslPs1",
2026-10-09T13:23:08.8852854Z   small: "false",
2026-10-09T13:23:08.8853179Z   agent: "foundry-implementer",
2026-10-09T13:23:08.8853607Z   mode: "primary",
2026-10-09T13:23:08.8853898Z }
"""


def _record(agent: str, *, small: str = "false", model: str = "space-bunny") -> str:
    return (
        "[13:23:08.884] INFO (#8297): stream {\n"
        '  providerID: "opencode-go",\n'
        f'  modelID: "{model}",\n'
        '  "session.id": "ses_x",\n'
        f'  small: "{small}",\n'
        f'  agent: "{agent}",\n'
        '  mode: "primary",\n'
        "}\n"
    )


def _audit(text: str) -> list[str]:
    return rid.audit_problems(rid.stream_records(text.splitlines()))


def _frontmatter(name: str) -> dict:
    text = (REPO_ROOT / ".opencode/agents" / name).read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def _project_config() -> dict:
    return json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))


# --- CLI semantics ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "pattern", "expected"),
    [
        ("git status", "git status*", True),
        ("git diff --output=x", "git diff*", True),
        ("ls", "ls *", True),
        ("ls -la", "ls *", True),
        ("lsof", "ls *", False),
        ("a.b", "a?b", True),
        ("git push", "git pull*", False),
        ("src\\x.py", "src/*", True),
    ],
)
def test_wildcard_matches_pinned_cli(value: str, pattern: str, expected: bool) -> None:
    assert rid.wildcard_match(value, pattern) is expected


def test_last_matching_rule_wins_and_no_match_asks() -> None:
    rules = rid.rules_from_config({"bash": {"*": "allow", "git push*": "allow"}})
    rules += rid.rules_from_config({"bash": {"*": "deny", "git status*": "allow"}})
    assert rid.evaluate("bash", "git push origin", rules) == "deny"
    assert rid.evaluate("bash", "git status", rules) == "allow"
    assert rid.evaluate("webfetch", "x", rules) == "ask"


# --- committed config surface -------------------------------------------------


def test_committed_reviewer_merged_with_project_config_is_read_only() -> None:
    config = _project_config()
    reviewer = _frontmatter("foundry-reviewer.md")
    assert rid.static_problems(config, reviewer) == []
    rules = rid.rules_from_config(config["permission"]) + rid.rules_from_config(
        reviewer["permission"]
    )
    for permission, pattern in rid.READ_PROBES:
        assert rid.evaluate(permission, pattern, rules) == "allow", pattern


def test_writable_default_agent_is_refused() -> None:
    """Negative control: what actually ran in 37936416385 is not read-only."""
    problems = rid.static_problems(_project_config(), _frontmatter("foundry-implementer.md"))
    assert any("git push origin HEAD" in problem for problem in problems)
    assert any(problem.startswith("edit:") for problem in problems)


def test_read_only_git_cannot_write_files_through_output_or_redirects() -> None:
    reviewer = _frontmatter("foundry-reviewer.md")
    del reviewer["permission"]["bash"]["*--output*"]
    del reviewer["permission"]["bash"]["*>*"]
    problems = rid.static_problems(_project_config(), reviewer)
    assert any("--output" in problem for problem in problems)
    assert any(">" in problem for problem in problems)


def test_prefix_rules_would_reach_difftool_exec() -> None:
    """``git diff*`` also matches ``git difftool -x CMD`` (fresh review of #654)."""
    reviewer = _frontmatter("foundry-reviewer.md")
    reviewer["permission"]["bash"] = {"*": "deny", "git diff*": "allow"}
    problems = rid.static_problems(_project_config(), reviewer)
    assert any("difftool" in problem for problem in problems)


@pytest.mark.parametrize(
    ("where", "patch", "needle"),
    [
        ("config", {"mode": {"foundry-reviewer": {}}}, "defines mode"),
        ("agent", {"mode": "subagent"}, "subagent"),
        ("agent", {"hidden": True}, "hidden"),
        ("agent", {"disable": True}, "disabled"),
    ],
)
def test_reviewer_that_cannot_be_default_is_refused(where: str, patch: dict, needle: str) -> None:
    config = _project_config()
    reviewer = _frontmatter("foundry-reviewer.md")
    (config if where == "config" else reviewer).update(patch)
    assert any(needle in problem for problem in rid.static_problems(config, reviewer))


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ('{"default_agent":"foundry-reviewer"}', True),
        ('{ "default_agent" : "foundry-reviewer" }', True),
        (None, False),
        ("", False),
        ('{"default_agent":"foundry-implementer"}', False),
        ('{"default_agent":"foundry-reviewer","agent":{}}', False),
        ("{", False),
    ],
)
def test_config_override_must_be_exact(value: str | None, ok: bool) -> None:
    assert (rid.override_problems(value) == []) is ok


# --- preflight on the CLI's own resolution ------------------------------------


def _resolved_reviewer() -> dict:
    """Agent.Info as the CLI builds it: defaults, project rules, agent rules."""
    defaults = rid.rules_from_config({"*": "allow", "question": "deny"})
    rules = (
        defaults
        + rid.rules_from_config(_project_config()["permission"])
        + rid.rules_from_config(_frontmatter("foundry-reviewer.md")["permission"])
    )
    return {
        "name": "foundry-reviewer",
        "mode": "all",
        "model": {"providerID": "opencode-go", "modelID": "space-bunny"},
        "variant": "max",
        "permission": rules,
        "tools": {"read": True, "edit": False, "write": False, "task": False},
    }


def _preflight(monkeypatch, capsys, *, config: dict, agent: dict, env: dict) -> tuple[int, str]:
    outputs = {"config": config, "agent": agent}
    monkeypatch.setattr(rid, "_debug_json", lambda args: outputs[args[0]])
    code = rid.preflight(env)
    return code, capsys.readouterr().out


GOOD_ENV = {"OPENCODE_CONFIG_CONTENT": '{"default_agent":"foundry-reviewer"}'}


def test_preflight_passes_on_resolved_reviewer(monkeypatch, capsys) -> None:
    code, out = _preflight(
        monkeypatch,
        capsys,
        config={"default_agent": "foundry-reviewer"},
        agent=_resolved_reviewer(),
        env=GOOD_ENV,
    )
    assert code == rid.EXIT_PASS, out
    receipt = json.loads(out.splitlines()[0])
    assert receipt["status"] == "PASS"
    assert "bash:git status" in receipt["read_probes_allowed"]


@pytest.mark.parametrize(
    "case", ["env_only_agent", "implementer_default", "writable_rules", "edit_tool", "bypass_env"]
)
def test_preflight_blocks(monkeypatch, capsys, case: str) -> None:
    config = {"default_agent": "foundry-reviewer"}
    agent = _resolved_reviewer()
    env = dict(GOOD_ENV)
    if case == "env_only_agent":
        env = {"AGENT": "foundry-reviewer"}
        config = {"default_agent": "foundry-implementer"}
    elif case == "implementer_default":
        config = {"default_agent": "foundry-implementer"}
    elif case == "writable_rules":
        agent["permission"] = [
            *agent["permission"],
            {"permission": "bash", "pattern": "git push*", "action": "allow"},
        ]
    elif case == "edit_tool":
        agent["tools"]["edit"] = True
    else:
        env["OPENCODE_PERMISSION"] = '{"bash":"allow"}'
    code, out = _preflight(monkeypatch, capsys, config=config, agent=agent, env=env)
    assert code == rid.EXIT_BLOCKED
    assert json.loads(out.splitlines()[0])["status"] == "BLOCKED"


def test_preflight_without_cli_answer_is_blocked(monkeypatch, capsys) -> None:
    def fail(args):
        raise RuntimeError("opencode debug config exited 1")

    monkeypatch.setattr(rid, "_debug_json", fail)
    assert rid.preflight(GOOD_ENV) == rid.EXIT_BLOCKED
    assert "runtime identity unavailable" in capsys.readouterr().out


# --- post-run audit -----------------------------------------------------------


def test_real_implementer_record_is_refused() -> None:
    records = rid.stream_records(REAL_IMPLEMENTER_RECORD.splitlines())
    assert [r["agent"] for r in records] == ["foundry-implementer"]
    problems = rid.audit_problems(records)
    assert any("'foundry-implementer'" in problem for problem in problems)


def test_reviewer_records_pass_and_tool_less_helpers_are_tolerated() -> None:
    text = _record("title", small="true") + _record("foundry-reviewer") + _record("compaction")
    assert _audit(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        _record("title", small="true"),
        _record("foundry-reviewer", small="true"),
        _record("foundry-reviewer") + _record("compaction", model="deepseek-v4.1-flash"),
        _record("foundry-reviewer") + _record("build"),
        _record("foundry-reviewer") + _record("title"),
        _record("foundry-reviewer", model="deepseek-v4.1-flash"),
    ],
)
def test_audit_blocks_unknown_or_foreign_identity(text: str) -> None:
    assert _audit(text) != []


def test_audit_cli_on_missing_log_is_blocked(tmp_path, capsys) -> None:
    assert rid.main(["audit", str(tmp_path / "absent.log")]) == rid.EXIT_BLOCKED
    log = tmp_path / "run.log"
    log.write_text(_record("foundry-reviewer"), encoding="utf-8")
    assert rid.main(["audit", str(log)]) == rid.EXIT_PASS
    assert rid.main(["nonsense"]) == 2
    capsys.readouterr()


def test_checker_runs_isolated_with_stdlib_only(tmp_path) -> None:
    """The workflow runs a copy with ``python3 -I`` outside the repository."""
    copy = tmp_path / "review_runtime_identity.py"
    copy.write_text(
        (REPO_ROOT / "tools/foundry/review_runtime_identity.py").read_text(encoding="utf-8")
    )
    log = tmp_path / "run.log"
    log.write_text(REAL_IMPLEMENTER_RECORD, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(copy), "audit", str(log)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == rid.EXIT_BLOCKED
    assert "foundry-implementer" in result.stdout


# --- watchdog copies the output for the audit ---------------------------------


def test_watchdog_log_option_copies_output(tmp_path, capsysbinary) -> None:
    log = tmp_path / "out.log"
    code = qw.main(["--log", str(log), "--", sys.executable, "-c", "print('stream line')"])
    assert code == 0
    assert log.read_text(encoding="utf-8") == "stream line\n"
    assert b"stream line" in capsysbinary.readouterr().out
    assert qw.main(["--log"]) == 2


# --- workflow wiring ----------------------------------------------------------


def test_review_job_selects_and_checks_the_reviewer() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["opencode-bunny-review"]
    assert json.loads(job["env"]["OPENCODE_CONFIG_CONTENT"]) == rid.REVIEW_CONFIG_OVERRIDE
    names = [step["name"] for step in job["steps"]]
    assert names.index("Preflight reviewer runtime identity") < names.index("Run opencode")
    assert names.index("Run opencode") < names.index("Audit reviewer runtime identity")
    # The implementation lanes keep their own default agent.
    for lane in ("opencode", "opencode-bunny"):
        assert "OPENCODE_CONFIG_CONTENT" not in (workflow["jobs"][lane].get("env") or {})
