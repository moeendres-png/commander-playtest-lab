"""Deterministic shadow-mode context router for Commander Foundry work.

The router decides only what repository context to retrieve next. It is DERIVED/INDEX
output, never Rules, Evidence, Source-Truth, ownership, or qualification authority.

It deliberately reuses context_capsule's validated state + live-Git identity gate.
Unknown/ambiguous routing broadens context instead of omitting it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import context_capsule as capsule_mod
import source_lock as source_lock_mod

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / ".foundry" / "repo-profiles"
ROUTER_KIND = "DERIVED_RETRIEVAL_PLAN (shadow only; not Source Authority)"
MAP_KIND = "DERIVED_ON_DEMAND_REPO_MAP (not Source Authority)"
MAX_CHANGED_PATHS = 20
GIT_TIMEOUT_SECONDS = 30

DOMAIN_REFS: dict[str, tuple[str, ...]] = {
    "foundry": (
        "docs/foundry-execution/README.md",
        "docs/foundry-execution/METRICS.md",
    ),
    "execution_routing": (
        "docs/foundry-execution/ROUTING_AND_EFFORT.md",
        "docs/CURRENT_EXECUTION_AUTHORITY.md",
    ),
    "ci": (
        ".github/workflows/",
        "tests/unit/test_workflow_security.py",
    ),
    "qualification": (
        "qualification/",
        "tests/qualification/",
        "docs/qualification/",
    ),
    "evidence": (
        ".opencode/skills/evidence-seal/SKILL.md",
        ".opencode/skills/component-change-review/SKILL.md",
    ),
    "failure": (".opencode/skills/failure-classification/SKILL.md",),
    "engine_bridge": ("engine-bridge/",),
    "mage": (".foundry/repo-profiles/mage.json",),
    "forge": (".foundry/repo-profiles/forge.json",),
}

PATH_SIGNALS: tuple[tuple[str, str], ...] = (
    ("tools/foundry/", "foundry"),
    ("tests/foundry/", "foundry"),
    (".opencode/", "foundry"),
    (".foundry/", "foundry"),
    ("docs/foundry-execution/", "foundry"),
    (".github/workflows/", "ci"),
    ("qualification/", "qualification"),
    ("tests/qualification/", "qualification"),
    ("docs/qualification/", "qualification"),
    ("engine-bridge/", "engine_bridge"),
)

TEXT_SIGNALS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("opencode", "foundry", "context capsule", "context router"), "foundry"),
    (("executor", "routing", "deepseek", "space bunny"), "execution_routing"),
    (("workflow", "github action", " ci ", "check gate"), "ci"),
    (("qualification", "receipt", "evidence seal", "current boundary"), "qualification"),
    (("evidence", "artifact", "sha256", "provenance"), "evidence"),
    (("xmage", "mage", "maven"), "mage"),
    (("forge", "gradle"), "forge"),
)


class RouterError(ValueError):
    """Fail-closed routing refusal."""


def _load_profile(profile: str, profiles_dir: Path) -> dict:
    if profile not in {"cpl", "mage", "forge"}:
        raise RouterError("profile must be cpl, mage, or forge")
    path = profiles_dir / f"{profile}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RouterError("cannot read valid repository profile") from exc
    if not isinstance(data, dict) or data.get("profile") != profile:
        raise RouterError("repository profile identity mismatch")
    slug = data.get("repo_slug")
    if not isinstance(slug, str) or not slug:
        raise RouterError("repository profile has no canonical repo_slug")
    return data


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


def _routing_text(state: dict) -> str:
    fields = (
        "objective",
        "exact_next_action",
        "current_failure",
        "current_hypothesis",
        "first_failing_boundary",
        "root_cause_class",
        "failure_class",
    )
    pieces = [str(state.get(field, "")) for field in fields]
    for field in (
        "in_scope",
        "remaining_scope",
        "dependencies",
        "hard_gates",
        "failed_gates",
        "invalidated_gates",
        "files_modified",
    ):
        pieces.extend(_strings(state.get(field)))
    return "\n".join(pieces).casefold()


def _changed_paths(state: dict) -> list[str]:
    values = _strings(state.get("files_modified"))
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _domains(state: dict, profile: str) -> tuple[list[str], list[str]]:
    selected: set[str] = set()
    reasons: list[str] = []
    paths = _changed_paths(state)
    for path in paths:
        normalized = path.replace("\\", "/").lstrip("./")
        for prefix, domain in PATH_SIGNALS:
            if normalized.startswith(prefix):
                selected.add(domain)
                reasons.append(f"path:{prefix}->{domain}")

    text = _routing_text(state)
    for needles, domain in TEXT_SIGNALS:
        if any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(needle.strip())}(?![a-z0-9])",
                text,
            )
            for needle in needles
        ):
            selected.add(domain)
            reasons.append(f"state-signal:{domain}")

    if profile in {"mage", "forge"}:
        selected.add(profile)
        reasons.append(f"repo-profile:{profile}")

    failure = str(state.get("failure_class", "NONE"))
    if failure not in {"", "NONE"}:
        selected.add("failure")
        reasons.append("state:failure_class")

    if "qualification" in selected:
        selected.add("evidence")

    return sorted(selected), sorted(set(reasons))


def _needs_broad_context(
    state: dict, domains: list[str], paths: list[str]
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not domains:
        reasons.append("no deterministic route matched")
    if len(paths) > MAX_CHANGED_PATHS:
        reasons.append(f"files_modified exceeds {MAX_CHANGED_PATHS}")
    if "engine_bridge" in domains and not ({"mage", "forge"} & set(domains)):
        reasons.append("engine bridge provider ambiguous")
    if _strings(state.get("authority_gates")):
        reasons.append("authority gate present")
    if str(state.get("failure_class", "NONE")) == "UNKNOWN":
        reasons.append("failure class UNKNOWN")
    if _strings(state.get("invalidated_gates")):
        reasons.append("invalidated gates present")
    if str(state.get("status", "")) in {"STALE", "SUPERSEDED"}:
        reasons.append("state status requires rebaseline")
    return bool(reasons), reasons


def _refs(domains: list[str], changed_paths: list[str]) -> list[str]:
    refs: list[str] = []
    for domain in domains:
        refs.extend(DOMAIN_REFS.get(domain, ()))
    refs.extend(changed_paths[:MAX_CHANGED_PATHS])
    return list(dict.fromkeys(refs))


def build_plan(
    state: dict,
    facts: dict,
    *,
    state_path: str,
    profile: str,
    profile_data: dict,
) -> dict:
    """Build a bounded retrieval plan; never decide project semantics."""
    if state.get("repository") != profile_data.get("repo_slug"):
        raise RouterError("state repository does not match selected repository profile")

    changed_paths = _changed_paths(state)
    domains, reasons = _domains(state, profile)
    broad, broad_reasons = _needs_broad_context(state, domains, changed_paths)

    tools: list[str] = []
    if changed_paths:
        tools.append(f"python3 tools/foundry/test_impact.py --base {state.get('audit_base_sha')}")
    if "failure" in domains:
        tools.append("skill: failure-classification")
    if "evidence" in domains:
        tools.append("skill: evidence-seal")
    if "qualification" in domains:
        tools.append("skill: component-change-review")

    repo_maps: list[dict[str, str]] = []
    for engine_profile in ("mage", "forge"):
        if engine_profile not in domains:
            continue
        repo_maps.append(
            {
                "profile": engine_profile,
                "mode": "ON_DEMAND_ONLY",
                "command": (
                    "python3 tools/foundry/context_router.py repo-map "
                    f"--profile {engine_profile} "
                    "--workdir <DECLARED_REFERENCE_ROOT> "
                    "--expected-head <DECLARED_SOURCE_LOCK_SHA> --max-depth 3"
                ),
            }
        )

    return {
        "_kind": ROUTER_KIND,
        "profile": profile,
        "repository": state.get("repository"),
        "branch": facts["branch"],
        "live_HEAD": facts["head"],
        "live_tree": facts["tree"],
        "tree_clean": facts["dirty_entries"] == 0,
        "capsule_required": True,
        "policy_note": (
            "AGENTS.md remains privileged always-on policy; this plan only routes "
            "on-demand repository reads."
        ),
        "route_mode": "BROAD_FALLBACK" if broad else "BOUNDED_ON_DEMAND",
        "selected_domains": domains,
        "route_reasons": reasons,
        "broad_context_reasons": broad_reasons,
        "full_state_read_required": broad,
        "full_state": state_path,
        "read_next": _refs(domains, changed_paths) if not broad else [state_path],
        "recommended_deterministic_tools": tools,
        "repo_maps": repo_maps,
        "default_activation_authorized": False,
        "promotion_gate": (
            "Representative quality-preserving A/B evidence is required before "
            "any default /work or AGENTS.md integration."
        ),
    }


def derive_plan(
    state_path: str,
    workdir: str,
    profile: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict:
    state = capsule_mod._load_state(state_path)
    facts = capsule_mod._git_facts(workdir)
    problems = capsule_mod._check_identity(state, facts, workdir)
    if problems:
        raise RouterError(problems[0])
    profile_data = _load_profile(profile, profiles_dir)
    return build_plan(
        state,
        facts,
        state_path=state_path,
        profile=profile,
        profile_data=profile_data,
    )


def _git(args: list[str], workdir: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise RouterError("repository map Git query unavailable") from None
    if proc.returncode != 0:
        raise RouterError(f"repository map Git query failed (exit {proc.returncode})")
    return proc.stdout.strip()


def _clean_prefix(value: str) -> str:
    path = value.replace("\\", "/").strip("/")
    if not path or path == "." or ".." in path.split("/"):
        raise RouterError("repo-map prefix must be a safe repository-relative path")
    return path


def build_repo_map(
    workdir: str,
    *,
    expected_slug: str,
    expected_head: str,
    max_depth: int = 3,
    prefixes: list[str] | None = None,
) -> dict:
    """Return a bounded map of committed directories at exact canonical HEAD."""
    if max_depth < 1 or max_depth > 6:
        raise RouterError("repo-map max-depth must be between 1 and 6")
    try:
        remote = source_lock_mod.remote_identity(workdir)
    except RuntimeError as exc:
        raise RouterError("repo-map remote identity unavailable or ambiguous") from exc
    if not source_lock_mod.is_canonical_remote(remote, expected_slug):
        raise RouterError("repo-map workdir does not match expected canonical repository")
    if len(expected_head) != 40 or any(
        char not in "0123456789abcdefABCDEF" for char in expected_head
    ):
        raise RouterError("repo-map expected-head must be a full 40-hex SHA")
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], workdir)
    head = _git(["rev-parse", "HEAD"], workdir)
    if head.casefold() != expected_head.casefold():
        raise RouterError("repo-map HEAD does not match declared source lock")
    tree = _git(["rev-parse", "HEAD^{tree}"], workdir)
    if branch == "HEAD":
        branch = "(detached)"

    requested = [_clean_prefix(item) for item in (prefixes or [])]
    args = ["ls-tree", "-d", "-r", "--name-only", "HEAD"]
    if requested:
        args.extend(["--", *requested])
    raw = _git(args, workdir)
    directories = []
    for line in raw.splitlines():
        path = line.strip()
        if not path:
            continue
        depth = len(Path(path).parts)
        if depth <= max_depth:
            directories.append(path)

    root_files_raw = _git(["ls-tree", "--name-only", "HEAD"], workdir)
    root_files = sorted(line for line in root_files_raw.splitlines() if line and "/" not in line)
    porcelain = _git(["status", "--porcelain"], workdir)
    return {
        "_kind": MAP_KIND,
        "branch": branch,
        "HEAD": head,
        "tree": tree,
        "dirty_entries": len(porcelain.splitlines()) if porcelain else 0,
        "prefixes": requested,
        "max_depth": max_depth,
        "directories": sorted(set(directories)),
        "root_entries": root_files,
        "note": (
            "Map is derived from committed HEAD only. Read source on demand; "
            "directory presence is not evidence of behavior."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow context routing and on-demand repo maps.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--state", default=None)
    plan.add_argument("--workdir", default=None)
    plan.add_argument("--profile", required=True, choices=("cpl", "mage", "forge"))
    plan.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR))

    repo_map = sub.add_parser("repo-map")
    repo_map.add_argument("--workdir", required=True)
    repo_map.add_argument("--profile", required=True, choices=("cpl", "mage", "forge"))
    repo_map.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR))
    repo_map.add_argument("--expected-head", required=True)
    repo_map.add_argument("--max-depth", type=int, default=3)
    repo_map.add_argument("--prefix", action="append", default=[])

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            state_path = capsule_mod.resolve_state_path(args.state)
            result = derive_plan(
                state_path,
                args.workdir or str(Path.cwd()),
                args.profile,
                Path(args.profiles_dir),
            )
        else:
            profile_data = _load_profile(args.profile, Path(args.profiles_dir))
            result = build_repo_map(
                args.workdir,
                expected_slug=profile_data["repo_slug"],
                expected_head=args.expected_head,
                max_depth=args.max_depth,
                prefixes=args.prefix,
            )
    except (RouterError, capsule_mod.CapsuleError) as exc:
        print(f"CONTEXT_ROUTER_REJECT: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
