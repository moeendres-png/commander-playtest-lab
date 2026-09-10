"""Deterministic Foundry workstream launcher (one command -> validated session).

``init``: validate everything (bootstrap gate), build the cross-repo policy
injection bundle, optionally install the pre-push hook, print the resolved
environment. Never starts OpenCode.

``launch``: init, then acquire and HOLD the single-writer lock for the whole
OpenCode child lifetime, inject canonical policy via supported mechanisms
only, collect start/end telemetry, and exit with the child's status.

Injection (all officially supported, verified Checkpoint A):

- OPENCODE_CONFIG_CONTENT: canonical model/share/provider/permission lock.
  Beats engine-local project config; deep-merges. Model/provider/variant
  invariants asserted before launch (fail closed on canonical drift).
- OPENCODE_CONFIG_DIR: snapshot of canonical .opencode agents/skills.
  Loads after repo .opencode dirs, so canonical definitions win.
- OPENCODE_DISABLE_PROJECT_CONFIG=1: only when drift is explicitly suppressed;
  keeps a stale engine AGENTS.md out of the model context at the cost of
  project discovery (logged degradation).
- Canonical AGENTS.md text: loaded from the project root automatically when
  CWD is CPL. For engine CWDs the launcher FAILS CLOSED on reachable stale
  routing unless suppression is explicit.

Effort: --effort must be high|xhigh (below-HIGH rejected). TUI sessions run
the HIGH implementer by config default; xhigh work routes to the
foundry-adjudicator subagent (variant xhigh). The launcher records effort in
telemetry and lock metadata; it invents no OpenCode flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap as bootstrap_mod
import drift_check as drift_mod
import metrics as metrics_mod
import writer_lock as writer_lock_mod

CANONICAL_MODEL = "opencode-go/muse-spark-1.3-contributor"
CANONICAL_PROVIDER = "opencode-go"
ALLOWED_EFFORTS = ("high", "xhigh")
BELOW_HIGH = ("medium", "low", "minimal", "none", "off")
OPENCODE_BIN_ENV = "FOUNDRY_OPENCODE_BIN"

HOOK_MARKER = "# foundry-launcher-managed pre-push hook"


def hook_script(branch: str) -> str:
    return f"""#!/bin/sh
{HOOK_MARKER} (branch refs/heads/{branch})
# L3-partial: refuses pushes to this workstream branch unless FOUNDRY_SAFE_PUSH=1
# (set only by tools/foundry/safe_push.py). Bypassable via --no-verify by
# construction; safe_push checks + remote branch protection are the real gates.
remote="$1"; url="$2"
while read local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in
    refs/heads/{branch})
      if [ "${{FOUNDRY_SAFE_PUSH:-}}" != "1" ]; then
        echo "HOOK_REJECT: pushing $remote_ref requires tools/foundry/safe_push.py" >&2
        exit 1
      fi
      ;;
  esac
done
exit 0
"""


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _git_dir(worktree: str) -> str:
    common = _git(["rev-parse", "--git-common-dir"], worktree)
    path = Path(common)
    return str(path if path.is_absolute() else Path(worktree) / common)


def install_hook(worktree: str, branch: str) -> str:
    """Install (or verify) the branch-scoped pre-push hook. Returns hook path."""
    hooks_dir = Path(_git_dir(worktree)) / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"
    if hook_path.exists() and HOOK_MARKER not in hook_path.read_text(encoding="utf-8"):
        raise ValueError(f"refusing to clobber foreign hook at {hook_path}")
    hook_path.write_text(hook_script(branch), encoding="utf-8")
    hook_path.chmod(0o755)
    return str(hook_path)


def sibling_denies(worktree: str) -> list[str]:
    """external_directory denies for every OTHER worktree of the same repo."""
    canonical = os.path.realpath(os.path.abspath(worktree))
    try:
        raw = _git(["worktree", "list", "--porcelain"], canonical)
    except RuntimeError:
        return []
    denies = []
    for line in raw.splitlines():
        if line.startswith("worktree "):
            path = os.path.realpath(line[len("worktree ") :])
            if path != canonical:
                denies.append(f"{path}*")
    return sorted(denies)


def build_content_bundle(canonical_root: str, extra_denies: list[str]) -> dict:
    """Canonical model/permission lock for OPENCODE_CONFIG_CONTENT."""
    config_path = Path(canonical_root) / "opencode.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read canonical opencode.json: {exc}") from exc
    if config.get("model") != CANONICAL_MODEL:
        raise ValueError(f"canonical model drift: {config.get('model')!r}")
    providers = config.get("enabled_providers", [])
    if providers != [CANONICAL_PROVIDER]:
        raise ValueError(f"canonical provider drift: {providers!r}")
    # NOTE: provider.models is keyed by SHORT model name (verified against the
    # resolved config); the provider/model pair lives in top-level "model".
    short_model = CANONICAL_MODEL.split("/", 1)[1]
    try:
        variants = config["provider"][CANONICAL_PROVIDER]["models"][short_model]["variants"]
    except KeyError as exc:
        raise ValueError(f"canonical model entry missing: {exc}") from exc
    for effort in BELOW_HIGH:
        if variants.get(effort) != {"disabled": True}:
            raise ValueError(f"canonical below-HIGH variant {effort!r} not disabled")
    bundle = {
        "model": config["model"],
        "share": config.get("share", "disabled"),
        "enabled_providers": providers,
        "provider": config["provider"],
        "permission": json.loads(json.dumps(config["permission"])),
    }
    ext = bundle["permission"].setdefault("external_directory", {})
    for deny in extra_denies:
        ext[deny] = "deny"
    if "instructions" in config:
        bundle["instructions"] = config["instructions"]
    return bundle


def build_config_dir(canonical_root: str, dest: str) -> dict:
    """Snapshot canonical .opencode agents/skills for OPENCODE_CONFIG_DIR."""
    manifest = {"files": [], "sha256": ""}
    digest = hashlib.sha256()
    src = Path(canonical_root) / ".opencode"
    out = Path(dest)
    for sub in ("agents", "skills", "commands", "modes"):
        sdir = src / sub
        if not sdir.is_dir():
            continue
        for path in sorted(sdir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src)
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            digest.update(str(rel).encode() + b"\0" + data + b"\0")
            manifest["files"].append(str(rel))
    manifest["sha256"] = digest.hexdigest()
    return manifest


def resolve_environment(
    *,
    canonical_root: str,
    worktree: str,
    branch: str,
    workstream: str,
    effort: str,
    session: str,
    drift_suppressed: bool,
    run_dir: str,
) -> dict:
    """Build the child environment. Raises ValueError fail-closed."""
    if effort in BELOW_HIGH or effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort {effort!r} rejected (allowed: {ALLOWED_EFFORTS})")
    canonical = Path(canonical_root)
    if not (canonical / "opencode.json").is_file() or not (canonical / "AGENTS.md").is_file():
        raise ValueError(f"canonical root {canonical_root!r} lacks policy files")
    denies = sibling_denies(worktree)
    static_denies = json.loads((canonical / "opencode.json").read_text(encoding="utf-8"))[
        "permission"
    ]["external_directory"]
    denies += [k for k, v in static_denies.items() if v == "deny"]
    bundle = build_content_bundle(canonical_root, sorted(set(denies)))
    env = dict(os.environ)
    config_dir = str(Path(run_dir) / "config-dir")
    manifest = build_config_dir(canonical_root, config_dir)
    policy_hash = drift_mod.canonical_bundle_hash(
        canonical_root, drift_mod.load_cpl_canonical_files(drift_mod.DEFAULT_PROFILES_DIR)
    )
    env[OPENCODE_BIN_ENV] = env.get(OPENCODE_BIN_ENV, "opencode")
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(bundle)
    env["OPENCODE_CONFIG_DIR"] = config_dir
    env["FOUNDRY_WORKSTREAM"] = workstream
    env["FOUNDRY_BRANCH"] = branch
    env["FOUNDRY_SESSION"] = session
    env["FOUNDRY_EFFORT"] = effort
    env["FOUNDRY_CANONICAL_POLICY_HASH"] = policy_hash
    env["FOUNDRY_CONFIG_DIR_MANIFEST"] = manifest["sha256"]
    if drift_suppressed:
        env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        env["FOUNDRY_ROUTING_SUPPRESSED"] = "1"
    return env


def _metrics_path(worktree: str) -> str:
    return str(Path(worktree) / ".foundry" / "metrics.jsonl")


def init(
    *,
    profile: str,
    worktree: str,
    workstream: str,
    branch: str,
    audit_base_sha: str,
    effort: str,
    mode: str,
    session: str,
    state_path: str | None,
    canonical_root: str,
    allow_same_cwd_pids: bool,
    allow_suppressed_routing: bool,
    install_pre_push_hook: bool,
    run_dir: str,
) -> dict:
    """Validate + prepare. Returns the launch plan (never execs)."""
    canonical = os.path.realpath(os.path.abspath(worktree))
    gate = bootstrap_mod.bootstrap(
        canonical,
        workstream,
        branch,
        audit_base_sha,
        state_path,
        profile,
        drift_mod.DEFAULT_PROFILES_DIR,
        canonical_root,
        allow_same_cwd_pids,
        allow_suppressed_routing,
    )
    if gate["verdict"] != "BOOTSTRAP_PASS":
        return {"verdict": "LAUNCH_REFUSED", "gate": gate}
    drift_suppressed = gate["drift"]["verdict"] == "DRIFT_FAIL"
    try:
        env = resolve_environment(
            canonical_root=canonical_root,
            worktree=canonical,
            branch=branch,
            workstream=workstream,
            effort=effort,
            session=session,
            drift_suppressed=drift_suppressed,
            run_dir=run_dir,
        )
    except ValueError as exc:
        return {"verdict": "LAUNCH_REFUSED", "gate": gate, "error": str(exc)}
    hook_path = None
    if install_pre_push_hook:
        try:
            hook_path = install_hook(canonical, branch)
        except (RuntimeError, ValueError, OSError) as exc:
            return {"verdict": "LAUNCH_REFUSED", "gate": gate, "error": f"hook: {exc}"}
    try:
        live_head = _git(["rev-parse", "HEAD"], canonical)
    except RuntimeError:
        live_head = "UNKNOWN"
    return {
        "verdict": "LAUNCH_READY",
        "gate": gate,
        "env_keys": sorted(k for k in env if k.startswith(("OPENCODE_", "FOUNDRY_"))),
        "canonical_policy_hash": env["FOUNDRY_CANONICAL_POLICY_HASH"],
        "config_dir_manifest": env["FOUNDRY_CONFIG_DIR_MANIFEST"],
        "hook_path": hook_path,
        "mode": mode,
        "session": session,
        "live_head": live_head,
        "_env": env,
    }


def launch(plan: dict, argv_extra: list[str], worktree: str, workstream: str, effort: str) -> int:
    """Hold the writer lock across the OpenCode child; telemetry; passthrough exit."""
    if plan.get("verdict") != "LAUNCH_READY":
        print(f"LAUNCH_REFUSED: {plan.get('error', plan.get('gate', {}))}", file=sys.stderr)
        return 1
    env: dict = plan["_env"]
    lock = writer_lock_mod.WriterLock(
        worktree, workstream, env.get("FOUNDRY_BRANCH", ""), env.get("FOUNDRY_SESSION", "")
    )
    try:
        lock.acquire()
    except writer_lock_mod.LockedError as exc:
        print(str(exc), file=sys.stderr)
        return writer_lock_mod.HELD_EXIT
    metrics_path = _metrics_path(worktree)
    start_mono = time.monotonic()
    try:
        metrics_mod.record(
            metrics_path,
            task_id=workstream,
            task_class="workstream-session",
            reasoning_effort=effort,
            source_sha=plan.get("live_head"),
        )
    except OSError as exc:
        print(f"LAUNCH_WARN: telemetry start not recorded: {exc}", file=sys.stderr)
    binary = env.get(OPENCODE_BIN_ENV, "opencode")
    argv = [binary, "--auto", *argv_extra]
    print(f"LAUNCH: holding writer lock; exec {' '.join(argv)} (cwd={worktree})")
    try:
        proc = subprocess.run(argv, cwd=worktree, env=env, check=False)
        rc = proc.returncode
    finally:
        elapsed = time.monotonic() - start_mono
        try:
            end_head = _git(["rev-parse", "HEAD"], worktree)
        except RuntimeError:
            end_head = "UNKNOWN"
        try:
            metrics_mod.record(
                metrics_path,
                task_id=workstream,
                reasoning_effort=effort,
                final_sha=end_head,
                completed=(rc == 0),
                elapsed_seconds=round(elapsed, 1),
            )
        except OSError as exc:
            print(f"LAUNCH_WARN: telemetry end not recorded: {exc}", file=sys.stderr)
        lock.release()
    print(f"LAUNCH_END: exit={rc} elapsed={elapsed:.1f}s (lock released)")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundry workstream launcher.")
    parser.add_argument("command", choices=("init", "launch"))
    parser.add_argument("--profile", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--workstream", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--audit-base-sha", required=True)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--mode", default="writer", choices=("writer", "reader"))
    parser.add_argument("--session", default="")
    parser.add_argument("--state", default=None)
    parser.add_argument("--canonical-root", required=True)
    parser.add_argument("--allow-same-cwd-pids", action="store_true")
    parser.add_argument("--allow-suppressed-routing", action="store_true")
    parser.add_argument("--install-hook", action="store_true")
    parser.add_argument("--run-dir", default=None)
    args, extra = parser.parse_known_args(argv)
    if args.command == "launch" and args.mode == "reader":
        print("LAUNCH_REFUSED: reader mode is audit-only (use init)", file=sys.stderr)
        return 1
    run_dir = args.run_dir or f"/tmp/foundry-launch-{args.workstream}"
    os.makedirs(run_dir, exist_ok=True)
    plan = init(
        profile=args.profile,
        worktree=args.worktree,
        workstream=args.workstream,
        branch=args.branch,
        audit_base_sha=args.audit_base_sha,
        effort=args.effort,
        mode=args.mode,
        session=args.session,
        state_path=args.state,
        canonical_root=args.canonical_root,
        allow_same_cwd_pids=args.allow_same_cwd_pids,
        allow_suppressed_routing=args.allow_suppressed_routing,
        install_pre_push_hook=args.install_hook,
        run_dir=run_dir,
    )
    printable = {k: v for k, v in plan.items() if k != "_env"}
    print(json.dumps(printable, indent=2, sort_keys=True, default=str))
    if args.command == "init":
        return 0 if plan["verdict"] == "LAUNCH_READY" else 1
    # launch: reader mode already refused above; writer holds the lock.
    if extra and extra[0] == "--":
        extra = extra[1:]
    return launch(plan, extra, args.worktree, args.workstream, args.effort)


if __name__ == "__main__":
    raise SystemExit(main())
