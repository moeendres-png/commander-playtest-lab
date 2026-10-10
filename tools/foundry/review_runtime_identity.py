"""Bind the direct review lane to the agent the pinned CLI actually runs (#654).

``opencode github run`` 1.18.30 never reads the ``AGENT`` environment variable:
``github.handler.ts`` (blob ``fcf44279ce7f2c764ed86771d913f784bf584746``) sends
each prompt without an agent, so the server uses ``default_agent`` from the
resolved config. Repository ``opencode.json`` sets that to the writable
``foundry-implementer``; run 37936416385 printed ``agent: "foundry-implementer"``
although the workflow said ``AGENT=foundry-reviewer``.

The supported selection is the config itself. ``OPENCODE_CONFIG_CONTENT`` is
merged after every project config file (``config.ts`` at the same tag), so the
review job sets it to exactly ``REVIEW_CONFIG_OVERRIDE``. Nothing else selects
the reviewer, and a declaration alone is never trusted:

- ``preflight`` (before the run) asks the pinned CLI for its resolved config and
  for the reviewer's effective permission ruleset (``opencode debug config`` and
  ``opencode debug agent foundry-reviewer``) and fails unless the default agent
  is the reviewer, its model is Space Bunny MAX and no write-capable probe is
  allowed by the merged rules;
- ``audit LOG`` (after the run) reads the run's own ``stream`` records, copied by
  ``quota_watchdog.py --log``, and fails unless at least one main-model record
  exists and every record names the reviewer (only the tool-less native
  ``title`` agent on the small model and ``compaction`` on Space Bunny may
  appear besides it).

A failed check fails the job, so ``review_evidence.py`` (which requires a
successful job) never admits that run. Missing evidence is BLOCKED, never PASS.

Permission evaluation mirrors ``permission/index.ts``: rules are flattened in
order (defaults, ``opencode.json`` ``permission``, then the agent's own rules)
and the LAST rule whose permission and pattern both match decides; no match is
``ask``. ``Wildcard.match`` turns ``*`` into ``.*``, ``?`` into ``.`` and makes a
trailing `` *`` optional.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

REVIEW_AGENT = "foundry-reviewer"
REVIEW_PROVIDER = "opencode-go"
REVIEW_MODEL = "space-bunny"
REVIEW_VARIANT = "max"
# The only accepted value of OPENCODE_CONFIG_CONTENT in the review job.
REVIEW_CONFIG_OVERRIDE = {"default_agent": REVIEW_AGENT}
# Environment that could replace or bypass the reviewed config surface.
FORBIDDEN_CONFIG_ENV = (
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_PERMISSION",
    "OPENCODE_DISABLE_PROJECT_CONFIG",
)
# Native agents that run without tools and never review: session titles on the
# small model, and context compaction of a long review on the reviewer's model.
TOOLLESS_SMALL_AGENTS = frozenset({"title"})
TOOLLESS_MAIN_AGENTS = frozenset({"compaction"})

# Every probe must NOT be allowed for the reviewer. ``ask`` counts as refused:
# nobody answers a prompt in a GitHub run.
WRITE_PROBES: tuple[tuple[str, str], ...] = (
    ("edit", "*"),
    ("edit", "src/commander_lab/__init__.py"),
    ("edit", "opencode.json"),
    ("edit", ".opencode/agents/foundry-reviewer.md"),
    ("edit", ".github/workflows/opencode.yml"),
    ("task", "general"),
    ("task", "explore"),
    ("task", "foundry-implementer"),
    ("task", "foundry-reviewer"),
    ("bash", "git push origin HEAD"),
    ("bash", "git commit -m x"),
    ("bash", "git add ."),
    ("bash", "git checkout -b x"),
    ("bash", "git switch -c x"),
    ("bash", "git merge x"),
    ("bash", "git cherry-pick x"),
    ("bash", "git reset --soft HEAD~1"),
    ("bash", "git stash"),
    ("bash", "git apply x.diff"),
    ("bash", "git worktree add ../x"),
    ("bash", "git diff --output=x.txt"),
    ("bash", "git log --output=x.txt"),
    ("bash", "git show HEAD --output=x.txt"),
    ("bash", "git diff > x.txt"),
    ("bash", "git log >> x.txt"),
    ("bash", "git difftool -y -x 'touch x' HEAD"),
    ("bash", "git diff --ext-diff"),
    ("bash", "gh pr comment 1 --body x"),
    ("bash", "gh api -X POST repos/x/y/issues/1/comments"),
    ("bash", "python3 -c pass"),
    ("bash", "pytest"),
    ("bash", "rm x"),
    ("bash", "touch x"),
    ("bash", "mkdir x"),
    ("bash", "cp a b"),
    ("bash", "mv a b"),
    ("bash", "tee x"),
    ("bash", "sed -i s/a/b/ x"),
    ("bash", "echo x > x"),
    ("bash", "curl -X POST https://example.invalid"),
)
# Positive controls: a read-only reviewer can still read the change.
READ_PROBES: tuple[tuple[str, str], ...] = (
    ("bash", "git status"),
    ("bash", "git diff HEAD~1"),
    ("bash", "git log --oneline -5"),
    ("read", "src/commander_lab/__init__.py"),
)
# Tools a read-only reviewer must not be offered at all.
WRITE_TOOLS = ("edit", "write", "apply_patch", "task")

EXIT_PASS = 0
EXIT_BLOCKED = 1


def wildcard_match(value: str, pattern: str) -> bool:
    """``Wildcard.match`` of the pinned CLI (non-Windows)."""
    value = value.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    escaped = re.sub(r"[.+^${}()|\[\]\\]", lambda m: "\\" + m.group(0), pattern)
    escaped = escaped.replace("*", ".*").replace("?", ".")
    if escaped.endswith(" .*"):
        escaped = escaped[:-3] + "( .*)?"
    return re.fullmatch(escaped, value, flags=re.DOTALL) is not None


def rules_from_config(permission: Any) -> list[dict[str, str]]:
    """``Permission.fromConfig``: a config ``permission`` mapping as ordered rules."""
    rules: list[dict[str, str]] = []
    if not isinstance(permission, Mapping):
        return rules
    for key, value in permission.items():
        if isinstance(value, str):
            rules.append({"permission": str(key), "pattern": "*", "action": value})
        elif isinstance(value, Mapping):
            rules.extend(
                {"permission": str(key), "pattern": str(pattern), "action": str(action)}
                for pattern, action in value.items()
            )
    return rules


def evaluate(permission: str, pattern: str, rules: Sequence[Mapping[str, Any]]) -> str:
    """``Permission.evaluate``: the last matching rule wins; no match is ``ask``."""
    for rule in reversed(rules):
        if wildcard_match(permission, str(rule.get("permission", ""))) and wildcard_match(
            pattern, str(rule.get("pattern", ""))
        ):
            return str(rule.get("action", "ask"))
    return "ask"


def write_surface_problems(rules: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every write-capable probe the merged ruleset would allow."""
    return [
        f"{permission}:{pattern!r} is allowed"
        for permission, pattern in WRITE_PROBES
        if evaluate(permission, pattern, rules) == "allow"
    ]


def static_problems(opencode_config: Any, agent_frontmatter: Any) -> list[str]:
    """Check the committed config surface the CLI will merge for the reviewer.

    Mirrors the CLI's order (project ``permission`` first, agent rules last). A
    reviewer override inside ``opencode.json`` (``agent``/``mode``) would be
    deep-merged with the agent file in key order, so it is refused outright
    rather than modelled.
    """
    problems: list[str] = []
    if not isinstance(opencode_config, Mapping):
        return ["opencode.json is not a JSON object"]
    if not isinstance(agent_frontmatter, Mapping):
        return ["reviewer agent frontmatter is not a mapping"]
    agents = opencode_config.get("agent")
    if isinstance(agents, Mapping) and REVIEW_AGENT in agents:
        problems.append(f"opencode.json overrides agent {REVIEW_AGENT!r}")
    modes = opencode_config.get("mode")
    if isinstance(modes, Mapping) and REVIEW_AGENT in modes:
        problems.append(f"opencode.json defines mode {REVIEW_AGENT!r}")
    if agent_frontmatter.get("mode") == "subagent":
        problems.append("reviewer is a subagent and cannot be the default agent")
    if agent_frontmatter.get("hidden") is True:
        problems.append("reviewer is hidden and cannot be the default agent")
    if agent_frontmatter.get("disable") is True:
        problems.append("reviewer is disabled")
    rules = rules_from_config(opencode_config.get("permission")) + rules_from_config(
        agent_frontmatter.get("permission")
    )
    problems.extend(write_surface_problems(rules))
    return problems


def override_problems(value: str | None) -> list[str]:
    """The review job's ``OPENCODE_CONFIG_CONTENT`` must be exactly the override."""
    if value is None or not value.strip():
        return ["OPENCODE_CONFIG_CONTENT is not set: AGENT alone does not select the reviewer"]
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        return [f"OPENCODE_CONFIG_CONTENT is not JSON ({exc.msg})"]
    if parsed != REVIEW_CONFIG_OVERRIDE:
        return [f"OPENCODE_CONFIG_CONTENT must be exactly {json.dumps(REVIEW_CONFIG_OVERRIDE)}"]
    return []


def runtime_agent_problems(config: Any, agent: Any) -> list[str]:
    """Check the CLI's own resolved config and reviewer agent (``debug`` output)."""
    problems: list[str] = []
    if not isinstance(config, Mapping):
        return ["resolved config is not an object"]
    if config.get("default_agent") != REVIEW_AGENT:
        problems.append(f"resolved default_agent is {config.get('default_agent')!r}")
    if not isinstance(agent, Mapping):
        return [*problems, "resolved reviewer agent is not an object"]
    if agent.get("name") != REVIEW_AGENT:
        problems.append(f"resolved agent name is {agent.get('name')!r}")
    if agent.get("mode") == "subagent" or agent.get("hidden") is True:
        problems.append("resolved reviewer cannot be the default agent")
    model = agent.get("model")
    if not isinstance(model, Mapping) or (
        model.get("providerID"),
        model.get("modelID"),
    ) != (REVIEW_PROVIDER, REVIEW_MODEL):
        problems.append(f"resolved reviewer model is {model!r}")
    if agent.get("variant") != REVIEW_VARIANT:
        problems.append(f"resolved reviewer variant is {agent.get('variant')!r}")
    rules = agent.get("permission")
    if not isinstance(rules, list) or not rules:
        problems.append("resolved reviewer has no permission ruleset")
    else:
        problems.extend(write_surface_problems(rules))
    tools = agent.get("tools")
    if isinstance(tools, Mapping):
        problems.extend(
            f"tool {tool!r} is offered to the reviewer"
            for tool in WRITE_TOOLS
            if tools.get(tool) is True
        )
    return problems


_HEADER = re.compile(r"^\[[0-9:.]+\] [A-Z]+ \(#\d+\): (?P<message>.+) \{$")
_FIELD = re.compile(r'^  (?:"(?P<quoted>[^"]+)"|(?P<bare>[A-Za-z_][\w.]*)): "(?P<value>[^"]*)",?$')
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ")


def stream_records(lines: Iterable[str]) -> list[dict[str, str]]:
    """Top-level string fields of every logged block that names an agent and model.

    The pinned CLI prints ``[hh:mm:ss.mmm] INFO (#pid): stream {`` followed by
    two-space-indented ``key: "value",`` lines and a closing ``}`` (run
    37936416385, job 113839482326). A GitHub timestamp prefix is ignored.
    """
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        line = _TIMESTAMP.sub("", raw.rstrip("\r\n"), count=1)
        header = _HEADER.match(line)
        if header is not None:
            current = {"_message": header.group("message")}
            continue
        if current is None:
            continue
        if line == "}":
            if {"agent", "small", "modelID", "providerID"} <= current.keys():
                records.append(current)
            current = None
            continue
        field = _FIELD.match(line)
        if field is not None:
            current[field.group("quoted") or field.group("bare")] = field.group("value")
    return records


def audit_problems(records: Sequence[Mapping[str, str]]) -> list[str]:
    """Every model call must be the reviewer on Space Bunny (titles excepted)."""
    problems: list[str] = []
    reviewer_calls = 0
    for record in records:
        agent = record.get("agent")
        small = record.get("small") == "true"
        model = f"{record.get('providerID')}/{record.get('modelID')}"
        if agent == REVIEW_AGENT:
            if model != f"{REVIEW_PROVIDER}/{REVIEW_MODEL}":
                problems.append(f"reviewer ran on {model}")
            if not small:
                reviewer_calls += 1
        elif (agent in TOOLLESS_SMALL_AGENTS and small) or (
            agent in TOOLLESS_MAIN_AGENTS and model == f"{REVIEW_PROVIDER}/{REVIEW_MODEL}"
        ):
            continue
        else:
            problems.append(f"model call by agent {agent!r} (small={record.get('small')})")
    if reviewer_calls == 0:
        problems.append("no main-model call by the reviewer is recorded: identity UNKNOWN")
    return problems


def _debug_json(args: Sequence[str]) -> Any:
    result = subprocess.run(
        ["opencode", "debug", *args], capture_output=True, text=True, timeout=300, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencode debug {' '.join(args)} exited {result.returncode}")
    start = result.stdout.find("{")
    if start < 0:
        raise RuntimeError(f"opencode debug {' '.join(args)} printed no JSON object")
    return json.loads(result.stdout[start:])


def _emit(mode: str, problems: Sequence[str], **facts: object) -> int:
    status = "PASS" if not problems else "BLOCKED"
    print(
        json.dumps(
            {
                "check": f"review_runtime_identity.{mode}",
                "status": status,
                **facts,
                "problems": list(problems),
            },
            sort_keys=True,
        )
    )
    for problem in problems:
        print(f"::error title=REVIEW_RUNTIME_IDENTITY_{status}::{problem}")
    return EXIT_PASS if not problems else EXIT_BLOCKED


def preflight(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    problems = override_problems(env.get("OPENCODE_CONFIG_CONTENT"))
    problems.extend(f"{name} is set" for name in FORBIDDEN_CONFIG_ENV if env.get(name))
    try:
        config = _debug_json(["config"])
        agent = _debug_json(["agent", REVIEW_AGENT])
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return _emit("preflight", [*problems, f"runtime identity unavailable: {exc}"])
    problems.extend(runtime_agent_problems(config, agent))
    rules = agent.get("permission") if isinstance(agent, Mapping) else None
    readable = [
        f"{permission}:{pattern}"
        for permission, pattern in READ_PROBES
        if isinstance(rules, list) and evaluate(permission, pattern, rules) == "allow"
    ]
    return _emit(
        "preflight",
        problems,
        default_agent=config.get("default_agent") if isinstance(config, Mapping) else None,
        agent=agent.get("name") if isinstance(agent, Mapping) else None,
        model=agent.get("model") if isinstance(agent, Mapping) else None,
        variant=agent.get("variant") if isinstance(agent, Mapping) else None,
        write_probes_refused=len(WRITE_PROBES),
        read_probes_allowed=readable,
    )


def audit(log_path: str) -> int:
    try:
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            records = stream_records(handle)
    except OSError as exc:
        return _emit("audit", [f"run log unavailable: {exc}"])
    agents = sorted({str(record.get("agent")) for record in records})
    return _emit("audit", audit_problems(records), records=len(records), agents=agents)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["preflight"]:
        return preflight()
    if len(args) == 2 and args[0] == "audit":
        return audit(args[1])
    sys.stderr.write("usage: review_runtime_identity.py preflight | audit LOG\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
