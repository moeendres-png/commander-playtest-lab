"""Cross-repo policy drift check (fail closed on ambiguous authority).

Answers, for a target worktree under a repo profile:

- is the target the repository the profile claims (remote slug check)?
- what canonical policy bundle applies (hash over the canonical files)?
- is stale routing production-reachable (root instruction/config surfaces
  carrying superseded markers, or an engine-local project config that would
  shadow central injection)?
- is the engine source tree itself modified (report-only signal)?

Classifications per surface: CURRENT_REACHABLE, HISTORICAL_NONREACHABLE,
AMBIGUOUS, SUPERSEDED_BUT_REACHABLE. Any SUPERSEDED_BUT_REACHABLE or AMBIGUOUS
root surface fails the check: the launcher must not start an unattended
session where Muse could receive contradictory authority. Historical files
under research/handoffs/docs nests are reported, never deleted.

Read-only. Never modifies any tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

REACHABLE_INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
REACHABLE_CONFIG_FILES = ("opencode.json", "opencode.jsonc")
REACHABLE_DIRS = (".opencode", ".claude")
HISTORICAL_NESTS = ("research", "handoffs", "docs", "artifacts", "qualification")

CANONICAL_MODEL = "opencode-go/muse-spark-1.3-contributor"


def _run(args: list[str], cwd: str) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def load_profile(name: str, profiles_dir: str) -> dict:
    path = Path(profiles_dir) / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"DRIFT_ERROR: cannot load profile {name!r}: {exc}") from exc


def canonical_bundle_hash(canonical_root: str, files: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        path = Path(canonical_root) / rel
        if not path.is_file():
            digest.update(f"MISSING:{rel}\n".encode())
            continue
        digest.update(f"FILE:{rel}\n".encode())
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _stale_hits(text: str, markers: list[str]) -> list[str]:
    return [m for m in markers if m and m in text]


DEFAULT_PROFILES_DIR = str(
    Path(__file__).resolve().parent.parent.parent / ".foundry" / "repo-profiles"
)


def check(
    target: str,
    profile: dict,
    canonical_root: str,
    profiles_dir: str = DEFAULT_PROFILES_DIR,
) -> dict:
    findings: list[dict] = []
    failed = False
    target_real = os.path.realpath(os.path.abspath(target))

    # 1. repository identity.
    try:
        url = _run(["git", "config", "--get", "remote.origin.url"], target_real)
    except RuntimeError as exc:
        return {
            "profile": profile.get("profile"),
            "target": target_real,
            "verdict": "DRIFT_FAIL",
            "findings": [
                {"surface": "(repo identity)", "classification": "AMBIGUOUS", "detail": str(exc)}
            ],
            "canonical_policy_hash": None,
        }
    if profile.get("repo_slug", "") not in url:
        findings.append(
            {
                "surface": "(repo identity)",
                "classification": "AMBIGUOUS",
                "detail": f"target remote lacks profile slug {profile.get('repo_slug')!r}",
            }
        )
        failed = True

    # 2. reachable instruction surfaces.
    markers: list[str] = profile.get("stale_markers", [])
    for name in REACHABLE_INSTRUCTION_FILES:
        path = Path(target_real) / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(
                {"surface": name, "classification": "AMBIGUOUS", "detail": f"unreadable: {exc}"}
            )
            failed = True
            continue
        hits = _stale_hits(text, markers)
        if hits:
            findings.append(
                {
                    "surface": name,
                    "classification": "SUPERSEDED_BUT_REACHABLE",
                    "detail": f"superseded markers reachable by the model: {hits}",
                }
            )
            failed = True
        elif profile.get("canonical_policy"):
            findings.append(
                {"surface": name, "classification": "CURRENT_REACHABLE", "detail": "canonical"}
            )
        else:
            findings.append(
                {
                    "surface": name,
                    "classification": "AMBIGUOUS",
                    "detail": "non-canonical instruction surface with no recognized markers "
                    "(human must adjudicate before unattended launch)",
                }
            )
            failed = True

    # 3. reachable project config (shadows OPENCODE_CONFIG injection).
    for name in REACHABLE_CONFIG_FILES:
        path = Path(target_real) / name
        if not path.is_file():
            continue
        if profile.get("canonical_policy"):
            findings.append(
                {"surface": name, "classification": "CURRENT_REACHABLE", "detail": "canonical"}
            )
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            model = data.get("model")
        except (OSError, ValueError) as exc:
            findings.append(
                {
                    "surface": name,
                    "classification": "AMBIGUOUS",
                    "detail": f"unparseable local project config: {exc}",
                }
            )
            failed = True
            continue
        # A local project config beats OPENCODE_CONFIG injection, so ANY model
        # pin here (matching or not) is ambiguous authority: fail closed.
        findings.append(
            {
                "surface": name,
                "classification": "AMBIGUOUS",
                "detail": f"engine-local project config pins model={model!r}; central "
                "injection cannot shadow it (resolve by hand before launch)",
            }
        )
        failed = True

    # 4. reachable agent/skill dirs (overridable via OPENCODE_CONFIG_DIR: warn).
    for name in REACHABLE_DIRS:
        path = Path(target_real) / name
        if not path.is_dir():
            continue
        if profile.get("canonical_policy"):
            findings.append(
                {"surface": name, "classification": "CURRENT_REACHABLE", "detail": "canonical"}
            )
            continue
        entries = sorted(p.name for p in path.iterdir())
        findings.append(
            {
                "surface": name,
                "classification": "AMBIGUOUS",
                "detail": f"engine-local {name}/ present ({entries[:8]}); overridable via "
                "OPENCODE_CONFIG_DIR but explicit invocation stays possible "
                "(launcher warns; default-agent pin decides)",
            }
        )

    # 5. historical nests (informational only).
    historical = []
    for nest in HISTORICAL_NESTS:
        if (Path(target_real) / nest).is_dir():
            historical.append(nest)
    if historical:
        findings.append(
            {
                "surface": f"nests:{','.join(historical)}",
                "classification": "HISTORICAL_NONREACHABLE",
                "detail": "nested docs are not auto-loaded; left untouched",
            }
        )

    # 6. engine-tree modification signal (report-only).
    try:
        porcelain = _run(["git", "status", "--porcelain"], target_real)
        dirty = len(porcelain.splitlines()) if porcelain else 0
        findings.append(
            {
                "surface": "(tree status)",
                "classification": "HISTORICAL_NONREACHABLE",
                "detail": f"{dirty} dirty entries (signal only; work in progress is normal)",
            }
        )
    except RuntimeError as exc:
        findings.append(
            {"surface": "(tree status)", "classification": "AMBIGUOUS", "detail": str(exc)}
        )

    # 7. canonical bundle hash (what the launcher must inject).
    bundle_hash = None
    if profile.get("canonical_policy"):
        bundle_hash = canonical_bundle_hash(target_real, profile.get("canonical_files", []))
    elif canonical_root:
        try:
            bundle_hash = canonical_bundle_hash(
                canonical_root, load_cpl_canonical_files(profiles_dir)
            )
        except (OSError, ValueError) as exc:
            findings.append(
                {
                    "surface": "(canonical bundle)",
                    "classification": "AMBIGUOUS",
                    "detail": f"cannot hash canonical bundle: {exc}",
                }
            )
            failed = True

    return {
        "profile": profile.get("profile"),
        "target": target_real,
        "verdict": "DRIFT_FAIL" if failed else "DRIFT_CLEAN",
        "findings": findings,
        "canonical_policy_hash": bundle_hash,
    }


def load_cpl_canonical_files(profiles_dir: str) -> list[str]:
    cpl = load_profile("cpl", profiles_dir)
    files = cpl.get("canonical_files", [])
    if not files:
        raise ValueError("cpl profile lists no canonical_files")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-repo policy drift check.")
    parser.add_argument("--target", required=True, help="Worktree to inspect.")
    parser.add_argument("--profile", required=True, help="cpl | mage | forge.")
    parser.add_argument(
        "--profiles-dir",
        default=str(Path(__file__).resolve().parent.parent.parent / ".foundry" / "repo-profiles"),
        help="Directory holding <profile>.json files.",
    )
    parser.add_argument(
        "--canonical-root",
        default=None,
        help="CPL checkout holding canonical policy (for bundle hash).",
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--fail-on-drift", action="store_true", help="Exit nonzero on DRIFT_FAIL.")
    args = parser.parse_args(argv)
    profile = load_profile(args.profile, args.profiles_dir)
    result = check(args.target, profile, args.canonical_root or "")
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.fail_on_drift and result["verdict"] == "DRIFT_FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
