"""Deterministic shadow-mode context router for Commander Foundry work.

The router decides only what repository context to retrieve next. It is DERIVED/INDEX
output, never Rules, Evidence, Source-Truth, ownership, or qualification authority.

It deliberately reuses context_capsule's validated state + live-Git identity gate.
Unknown/ambiguous routing broadens context instead of omitting it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import context_capsule as capsule_mod
import reference_roots as reference_mod
import source_lock as source_lock_mod

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / ".foundry" / "repo-profiles"
ROUTER_KIND = "DERIVED_RETRIEVAL_PLAN (shadow only; not Source Authority)"
MAP_KIND = "DERIVED_ON_DEMAND_REPO_MAP (not Source Authority)"
MAX_CHANGED_PATHS = 20
MAX_MAP_PREFIXES = 16
MAX_MAP_DIRECTORIES = 500
MAX_MAP_ROOT_ENTRIES = 200
MAX_REPO_PATH_LENGTH = 512
GIT_TIMEOUT_SECONDS = 30
SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._@+-]+$")

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


def _strings(value: object, field: str) -> list[str]:
    """Return a string-list state field, refusing any other shape.

    A gate or path that is not a string (an unquoted YAML ``key: value`` entry,
    a null, a number) is never silently dropped: dropping it could turn a gated
    or out-of-bounds state into a bounded plan.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise RouterError(f"state field {field!r} must be a string list")


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
    ):
        pieces.extend(_strings(state.get(field), field))
    return "\n".join(pieces).casefold()


def _clean_repo_path(value: str, *, field: str) -> str:
    if not value or value != value.strip() or len(value) > MAX_REPO_PATH_LENGTH:
        raise RouterError(f"{field} must be a bounded repository-relative path")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise RouterError(f"{field} must be a bounded repository-relative path")
    parts = normalized.split("/")
    if any(
        not part or part in {".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part) for part in parts
    ):
        raise RouterError(f"{field} must be a bounded repository-relative path")
    return normalized


def _changed_paths(state: dict) -> list[str]:
    values = _strings(state.get("files_modified"), "files_modified")
    cleaned = [_clean_repo_path(value, field="files_modified entry") for value in values]
    return list(dict.fromkeys(cleaned))


def _domains(state: dict, profile: str) -> tuple[list[str], list[str]]:
    selected: set[str] = set()
    reasons: list[str] = []
    paths = _changed_paths(state)
    for path in paths:
        normalized = path
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
    state: dict,
    facts: dict,
    domains: list[str],
    paths: list[str],
    profile: str,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not domains:
        reasons.append("no deterministic route matched")
    if len(paths) > MAX_CHANGED_PATHS:
        reasons.append(f"files_modified exceeds {MAX_CHANGED_PATHS}")
    if "engine_bridge" in domains and profile == "cpl":
        reasons.append("engine bridge provider ambiguous")
    if _strings(state.get("authority_gates"), "authority_gates"):
        reasons.append("authority gate present")
    if str(state.get("failure_class", "NONE")) == "UNKNOWN":
        reasons.append("failure class UNKNOWN")
    if str(state.get("root_cause_class", "")) == "UNKNOWN":
        reasons.append("root cause class UNKNOWN")
    if _strings(state.get("invalidated_gates"), "invalidated_gates"):
        reasons.append("invalidated gates present")
    if str(state.get("status", "")) != "ACTIVE":
        reasons.append("state status is not ACTIVE")
    recorded = _recorded_head(state)
    if recorded is None:
        reasons.append("state HEAD unknown")
    elif recorded != facts["head"]:
        reasons.append("state HEAD drift")
    if facts["dirty_entries"] != 0:
        reasons.append("worktree is dirty")
    return bool(reasons), reasons


def _recorded_head(state: dict) -> str | None:
    """HEAD the state was written against: schema 2.0 or the 1.0 field."""
    recorded = state.get("state_written_against_head") or state.get("current_head")
    return str(recorded) if recorded else None


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
    profile: str,
    profile_data: dict,
) -> dict:
    """Build a bounded retrieval plan; never decide project semantics."""
    if state.get("repository") != profile_data.get("repo_slug"):
        raise RouterError("state repository does not match selected repository profile")

    changed_paths = _changed_paths(state)
    domains, reasons = _domains(state, profile)
    broad, broad_reasons = _needs_broad_context(
        state,
        facts,
        domains,
        changed_paths,
        profile,
    )

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
    if not broad and profile in {"mage", "forge"}:
        repo_maps.append(
            {
                "profile": profile,
                "mode": "ON_DEMAND_ONLY",
                "command": (
                    "python3 tools/foundry/context_router.py repo-map "
                    f"--profile {profile} "
                    "--workdir <DECLARED_REFERENCE_ROOT> --max-depth 3"
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
        "state_written_against_head": _recorded_head(state),
        "head_drift": _recorded_head(state) not in (None, facts["head"]),
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
        "full_state_reference": "$FOUNDRY_STATE_PATH",
        "read_next": (_refs(domains, changed_paths) if not broad else ["$FOUNDRY_STATE_PATH"]),
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
    expected_worktree = state.get("worktree")
    if not isinstance(expected_worktree, str) or os.path.realpath(workdir) != os.path.realpath(
        expected_worktree
    ):
        raise RouterError("workdir does not match the state worktree")
    try:
        toplevel = os.path.realpath(_git(["rev-parse", "--show-toplevel"], workdir))
        remote = source_lock_mod.remote_identity(workdir)
        rewrites_clean = source_lock_mod._no_url_rewrites(
            workdir,
            dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never"),
        )
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        raise RouterError("workdir identity unavailable or ambiguous") from exc
    if toplevel != os.path.realpath(workdir):
        raise RouterError("workdir must be the checkout toplevel")
    if not source_lock_mod.is_canonical_remote(remote, profile_data["repo_slug"]):
        raise RouterError("workdir does not match selected canonical repository")
    if not rewrites_clean:
        raise RouterError("workdir URL rewrite configuration present or unreadable")
    return build_plan(
        state,
        facts,
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
    return _clean_repo_path(value, field="repo-map prefix")


def _verify_declared_reference(
    profile: str,
    workdir: str,
    profile_data: dict,
    reference: dict,
) -> dict:
    if profile not in {"mage", "forge"}:
        raise RouterError("repo-map is restricted to declared engine reference roots")
    if reference.get("label") != profile:
        raise RouterError("declared reference label does not match repo-map profile")
    if reference.get("repo_slug") != profile_data.get("repo_slug"):
        raise RouterError("declared reference repository does not match profile")
    if os.path.realpath(str(reference.get("root", ""))) != os.path.realpath(workdir):
        raise RouterError("repo-map workdir does not match declared reference root")
    reasons = reference_mod.verify(reference)
    if reasons:
        raise RouterError("declared reference root verification failed")
    try:
        rewrites_clean = source_lock_mod._no_url_rewrites(
            workdir,
            dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never"),
        )
    except (OSError, subprocess.TimeoutExpired):
        rewrites_clean = False
    if not rewrites_clean:
        raise RouterError("repo-map URL rewrite configuration present or unreadable")
    return reference


def _load_declared_reference(
    profile: str,
    workdir: str,
    profile_data: dict,
) -> dict:
    if os.environ.get("FOUNDRY_ROUTING_SUPPRESSED") == "1":
        raise RouterError("repo-map unavailable while Foundry routing is suppressed")
    raw = os.environ.get("FOUNDRY_REFERENCE_ROOTS")
    if raw is None:
        raise RouterError("repo-map requires FOUNDRY_REFERENCE_ROOTS")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise RouterError("FOUNDRY_REFERENCE_ROOTS is not valid JSON") from exc
    if not isinstance(data, list):
        raise RouterError("FOUNDRY_REFERENCE_ROOTS must be a JSON list")
    matches = [item for item in data if isinstance(item, dict) and item.get("label") == profile]
    if len(matches) != 1:
        raise RouterError("repo-map requires exactly one declared reference for the profile")
    try:
        reference = reference_mod.parse_spec(json.dumps(matches[0]))
    except reference_mod.ReferenceError as exc:
        raise RouterError("declared reference is malformed") from exc
    return _verify_declared_reference(profile, workdir, profile_data, reference)


def _safe_tree_names(raw: str) -> list[str]:
    names: list[str] = []
    for line in raw.splitlines():
        name = line.strip()
        if not name:
            continue
        if SAFE_PATH_SEGMENT.fullmatch(name) is None:
            raise RouterError("repo-map encountered an unsupported repository path segment")
        names.append(name)
    return sorted(set(names))


def _bounded_directories(
    workdir: str,
    *,
    tree: str,
    max_depth: int,
    requested: list[str],
) -> list[str]:
    queue: deque[tuple[str, int]] = deque()
    if requested:
        for prefix in requested:
            depth = len(Path(prefix).parts)
            if depth > max_depth:
                raise RouterError("repo-map prefix is deeper than max-depth")
            if _git(["cat-file", "-t", f"{tree}:{prefix}"], workdir) != "tree":
                raise RouterError("repo-map prefix must name a committed directory")
            queue.append((prefix, depth))
    else:
        for name in _safe_tree_names(_git(["ls-tree", "-d", "--name-only", tree], workdir)):
            queue.append((name, 1))

    directories: list[str] = []
    seen: set[str] = set()
    while queue:
        path, depth = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        directories.append(path)
        if len(directories) > MAX_MAP_DIRECTORIES:
            raise RouterError(f"repo-map exceeds {MAX_MAP_DIRECTORIES} directories")
        if depth >= max_depth:
            continue
        children = _safe_tree_names(
            _git(["ls-tree", "-d", "--name-only", f"{tree}:{path}"], workdir)
        )
        for child in children:
            queue.append((f"{path}/{child}", depth + 1))
    return sorted(directories)


def build_repo_map(
    workdir: str,
    *,
    profile: str,
    profile_data: dict,
    reference: dict,
    max_depth: int = 3,
    prefixes: list[str] | None = None,
) -> dict:
    """Return a bounded map for one verified launcher-declared engine reference."""
    if max_depth < 1 or max_depth > 6:
        raise RouterError("repo-map max-depth must be between 1 and 6")
    verified = _verify_declared_reference(profile, workdir, profile_data, reference)
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], workdir)
    head = _git(["rev-parse", "HEAD"], workdir)
    tree = _git(["rev-parse", "HEAD^{tree}"], workdir)
    if head != verified["commit"] or tree != verified["tree"]:
        raise RouterError("repo-map live source no longer matches declared reference")
    if branch == "HEAD":
        branch = "(detached)"

    if len(prefixes or []) > MAX_MAP_PREFIXES:
        raise RouterError(f"repo-map accepts at most {MAX_MAP_PREFIXES} prefixes")
    requested = list(dict.fromkeys(_clean_prefix(item) for item in (prefixes or [])))
    directories = _bounded_directories(
        workdir,
        tree=verified["tree"],
        max_depth=max_depth,
        requested=requested,
    )

    root_args = ["ls-tree", "--name-only", verified["tree"]]
    if requested:
        root_args.extend(["--", *requested])
    root_entries = sorted(
        line.strip() for line in _git(root_args, workdir).splitlines() if line.strip()
    )
    if len(root_entries) > MAX_MAP_ROOT_ENTRIES:
        raise RouterError(f"repo-map exceeds {MAX_MAP_ROOT_ENTRIES} root entries")

    return {
        "_kind": MAP_KIND,
        "profile": profile,
        "expected_repo_slug": verified["repo_slug"],
        "expected_HEAD": verified["commit"],
        "expected_tree": verified["tree"],
        "branch": branch,
        "HEAD": head,
        "tree": tree,
        "dirty_entries": 0,
        "prefixes": requested,
        "max_depth": max_depth,
        "directories": directories,
        "root_entries": root_entries,
        "note": (
            "Map is derived from a launcher-declared, re-verified read-only reference. "
            "Directory presence is navigation data, not evidence of behavior."
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
    repo_map.add_argument("--profile", required=True, choices=("mage", "forge"))
    repo_map.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR))
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
            reference = _load_declared_reference(args.profile, args.workdir, profile_data)
            result = build_repo_map(
                args.workdir,
                profile=args.profile,
                profile_data=profile_data,
                reference=reference,
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
