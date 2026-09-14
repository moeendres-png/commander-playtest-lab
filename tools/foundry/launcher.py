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

WS75 hardening:

- ``--ui-mode headless`` (default) execs first-class headless argv
  ``opencode run --auto <extra...>`` exactly in that order (opencode.ai
  CLI docs: ``opencode run --auto "msg"``). ``--ui-mode tui`` preserves
  the interactive form ``opencode --auto <extra...>``. No external
  wrapper is needed for either form.
- Runtime telemetry lives under ``run_dir`` (outside the Git worktree);
  launcher execution leaves the worktree clean.
- The exact ``--state`` path plus worktree/branch/workstream/run-dir/
  mode/effort reach Muse as ``FOUNDRY_*`` env (no secrets) and as
  ``run_dir/launch-context.json``.
- Canonical control-plane tool identity (WS196): the exact canonical root
  plus the exact canonical ``tools/foundry/safe_push.py`` reach Muse as
  ``FOUNDRY_CANONICAL_ROOT`` / ``FOUNDRY_SAFE_PUSH`` and as
  ``canonical_root`` / ``canonical_safe_push`` in ``launch-context.json``.
  Cross-repo (Forge/XMage) sessions resolve the same identity by
  construction — no filesystem globbing, no sibling-worktree discovery, no
  copied control-plane tools. A canonical root without the exact tool file
  fails closed before any discovery.
- Declared read-only reference roots (``--reference`` JSON, repeatable)
  are verified at bootstrap and exposed as ``FOUNDRY_REFERENCE_ROOTS``.
- The installed OpenCode CLI must equal the canonical qualified version
  (``tools/foundry/opencode_cli_version.py``) unless explicit
  ``--version-audit-mode`` bounds the drift for migration/audit runs.
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
import opencode_cli_version as version_mod
import reference_roots as reference_mod
import writer_lock as writer_lock_mod

try:  # package import (tests) vs script CWD (tools/foundry)
    from foundry import autonomy as autonomy_mod
    from foundry import session_capture as session_capture_mod
except ImportError:  # pragma: no cover - script-relative fallback
    import autonomy as autonomy_mod  # type: ignore[no-redef]
    import session_capture as session_capture_mod  # type: ignore[no-redef]

CANONICAL_MODEL = "opencode-go/muse-spark-1.3-contributor"
CANONICAL_PROVIDER = "opencode-go"
ZEN_MODEL = "opencode/muse-spark-1.3-contributor-free"
ALLOWED_EFFORTS = ("high", "xhigh")
BELOW_HIGH = ("medium", "low", "minimal", "none", "off")
OPENCODE_BIN_ENV = "FOUNDRY_OPENCODE_BIN"
UI_MODES = ("headless", "tui")


def execution_identity(override: str | None, effort: str) -> dict:
    """Operator selection, never inferred from quota, credentials or environment."""
    if override not in (None, "zen"):
        raise ValueError(f"unknown execution provider override {override!r}")
    if effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort {effort!r} rejected (allowed: {ALLOWED_EFFORTS})")
    return {
        "override": override or "canonical",
        "provider": "opencode" if override else CANONICAL_PROVIDER,
        "model": ZEN_MODEL if override else CANONICAL_MODEL,
        "requested_effort": effort,
        "variant_resolution": "provider_default_unverified"
        if override
        else "canonical_agent_variant",
    }


def validate_child_options(extra: list[str]) -> None:
    """Selection belongs to the launcher; explicit session IDs remain supported.

    NOTE (WS198): a bare ``--`` separator does NOT make trailing text safe
    prompt input for every mode. Headless ``run [message..]`` accepts a bare
    message, but TUI ``opencode [project]`` binds a bare positional to the
    project path (pinned 1.18.30: instant ``Failed to change directory`` with
    child exit 0). TUI prompt text must use ``--prompt`` (see
    ``canonicalize_tui_extras``); this function only guards model/variant/
    session-resume selection here.
    """
    for arg in extra:
        if arg == "--":
            continue  # Separator is structural, not a CLI option; TUI bare-
            # positional safety is enforced separately (canonicalize_tui_extras).
        key = arg.split("=", 1)[0]
        if (
            key in ("--model", "--variant", "--continue")
            or (arg.startswith("-m") and not arg.startswith("--"))
            or arg == "-c"
        ):
            raise ValueError("model/variant/continue child flags are launcher-controlled")


# WS198: TUI value flags whose immediate successor is a value, never a
# project path. Pinned CLI 1.18.30 TUI options (``opencode --help``).
_TUI_VALUE_FLAGS = frozenset(
    {
        "--prompt",
        "--agent",
        "-s",
        "--session",
        "--log-level",
        "--port",
        "--hostname",
        "--replay-limit",
    }
)


def canonicalize_tui_extras(argv_extra: list[str]) -> list[str]:
    """Fail-closed TUI extras: prompt injection must use ``--prompt``.

    DIRECTLY_VERIFIED (pinned 1.18.30, WS92/WS93 shape reproduced): TUI
    syntax is ``opencode [project]`` — a bare positional is bound to the
    project path, fails instantly with ``Failed to change directory`` on
    stderr, and STILL returns child exit 0, so ``LAUNCH_END: exit=0`` would
    certify a session in which no agent task executed. Refusing the shape
    at construction is the systemic fix: post-hoc detection without
    heuristic stderr parsing is not reliable (exit 0 is the CLI contract).

    - A single leading ``--`` (launcher-argparse passthrough artifact) is
      dropped; the canonical child form carries no stray separator.
    - Any remaining bare positional outside a value-flag value raises
      ``ValueError`` (``LAUNCH_REFUSED``) directing the caller to
      ``--prompt "<task>"`` (launcher spelling: ``-- --prompt "<task>"``).
    - Headless is untouched: ``opencode run [message..]`` takes a bare
      message, so headless/TUI prompt semantics stay explicitly distinct.
    """
    extras = list(argv_extra)
    if extras and extras[0] == "--":
        extras = extras[1:]
    skip_next = False
    for token in extras:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-") and token != "-":
            if "=" not in token and token in _TUI_VALUE_FLAGS:
                skip_next = True
            continue
        raise ValueError(
            f"TUI positional {token!r} refused: TUI syntax is `opencode [project]`, "
            'so bare text is a project path, not a prompt (it fails with '
            "'Failed to change directory' yet child exit 0). Pass prompt text via "
            '`--prompt "<task>"` (launcher: `-- --prompt "<task>"`).'
        )
    return extras


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


def build_argv(binary: str, ui_mode: str, argv_extra: list[str]) -> list[str]:
    """Exact child argv for one UI mode (fail closed on unknown mode).

    headless: ``<bin> run --auto <extra...>`` — the documented
    non-interactive form (opencode.ai CLI + permissions docs).
    tui: ``<bin> --auto <extra...>`` — the interactive form, which also
    accepts ``--auto``. ``run`` stays first after the binary and
    ``--auto`` immediately after ``run``; extras keep caller order.
    """
    if ui_mode == "headless":
        return [binary, "run", "--auto", *argv_extra]
    if ui_mode == "tui":
        return [binary, "--auto", *argv_extra]
    raise ValueError(f"unknown ui_mode {ui_mode!r} (want one of {UI_MODES})")


def resolve_opencode_binary(explicit: str | None) -> str:
    """Explicit flag wins, then FOUNDRY_OPENCODE_BIN, then PATH ``opencode``."""
    if explicit:
        return explicit
    return os.environ.get(OPENCODE_BIN_ENV, "opencode")


CANONICAL_SAFE_PUSH_REL = ("tools", "foundry", "safe_push.py")


def resolve_canonical_tools(canonical_root: str) -> dict:
    """Deterministic canonical control-plane tool identity (no discovery).

    Returns ``{"canonical_root": <realpath>, "safe_push": <abspath>}`` where
    ``safe_push`` is exactly ``<root>/tools/foundry/safe_push.py`` joined by
    construction — never globbed, never searched across sibling worktrees,
    never assumed inside the session CWD (which for Forge/XMage runs is an
    engine checkout without control-plane tooling).

    Fail-closed: an empty root or a root whose exact tool file is absent
    raises ``ValueError`` so ``init`` refuses the launch before any
    model-driven discovery can start. Permissions are intentionally
    untouched here: the identity is the grant, and the external-directory
    surface stays narrow (no broad allow is injected).
    """
    if not canonical_root:
        raise ValueError("canonical root is required to resolve canonical tools")
    root = os.path.realpath(os.path.abspath(canonical_root))
    safe_push = os.path.join(root, *CANONICAL_SAFE_PUSH_REL)
    if not os.path.isfile(safe_push):
        raise ValueError(
            f"canonical safe_push missing at {safe_push!r} "
            "(canonical root must carry tools/foundry/safe_push.py; "
            "refusing before any filesystem discovery)"
        )
    return {"canonical_root": root, "safe_push": safe_push}


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


def _validated_tool_output(value: object) -> dict:
    """Fail closed on malformed tool_output (pinned 1.18.30: positive ints).

    Only the DIRECTLY_VERIFIED keys ``max_lines`` / ``max_bytes`` pass
    through; unknown keys are refused so no canonical bound is silently
    dropped by the injection bundle.
    """
    if not isinstance(value, dict):
        raise ValueError(f"tool_output must be an object, got {type(value).__name__}")
    out: dict = {}
    for key in ("max_lines", "max_bytes"):
        if key in value:
            item = value[key]
            if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
                raise ValueError(f"tool_output.{key} must be a positive int, got {item!r}")
            out[key] = item
    unknown = sorted(set(value) - {"max_lines", "max_bytes"})
    if unknown:
        raise ValueError(f"tool_output has unknown keys: {unknown}")
    return out


def build_content_bundle(
    canonical_root: str, extra_denies: list[str], execution_provider: str | None = None
) -> dict:
    """Canonical model/permission lock for OPENCODE_CONFIG_CONTENT."""
    config_path = Path(canonical_root) / "opencode.json"
    execution = execution_identity(execution_provider, "high")
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
    if config.get("share", "disabled") != "disabled":
        raise ValueError("canonical share must remain disabled")
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
    if "tool_output" in config:
        bundle["tool_output"] = _validated_tool_output(config["tool_output"])
    # Copy all non-provider policies, replacing only the execution allowlist.
    experimental = json.loads(json.dumps(config.get("experimental", {})))
    policies = [p for p in experimental.get("policies", []) if p.get("action") != "provider.use"]
    experimental["policies"] = [
        *policies,
        {"action": "provider.use", "effect": "deny", "resource": "*"},
        {"action": "provider.use", "effect": "allow", "resource": execution["provider"]},
    ]
    bundle["experimental"] = experimental
    if "default_agent" in config:
        bundle["default_agent"] = config["default_agent"]
    if execution_provider == "zen":
        bundle["model"] = ZEN_MODEL
        bundle["small_model"] = ZEN_MODEL
        bundle["enabled_providers"] = ["opencode"]
        bundle["disabled_providers"] = [CANONICAL_PROVIDER]
        short = ZEN_MODEL.split("/", 1)[1]
        bundle["provider"] = {
            "opencode": {
                "whitelist": [short],
                "models": {
                    short: {
                        "variants": {
                            name: {"disabled": True} for name in (*BELOW_HIGH, *ALLOWED_EFFORTS)
                        }
                    }
                },
            }
        }
        # Inline agent values override the unchanged canonical Markdown snapshot.
        # Empty variant clears Go's inherited value (pinned agent.ts uses ??),
        # without inventing a supported Zen HIGH/XHIGH variant or reasoning option.
        names = {"build", "plan", "general", "explore", "compaction", "title", "summary"}
        names.update(config.get("agent", {}))
        names.update(p.stem for p in (Path(canonical_root) / ".opencode" / "agents").glob("*.md"))
        bundle["agent"] = {name: {"model": ZEN_MODEL, "variant": ""} for name in sorted(names)}
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
    state_path: str,
    mode: str,
    references: list[dict],
    opencode_binary: str,
    execution_provider: str | None = None,
) -> dict:
    """Build the child environment. Raises ValueError fail-closed."""
    if effort in BELOW_HIGH or effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort {effort!r} rejected (allowed: {ALLOWED_EFFORTS})")
    canonical = Path(canonical_root)
    if not (canonical / "opencode.json").is_file() or not (canonical / "AGENTS.md").is_file():
        raise ValueError(f"canonical root {canonical_root!r} lacks policy files")
    # WS196: exact canonical tool identity by construction (fail closed when
    # the canonical root carries no control-plane tooling). CPL-native and
    # Forge/XMage sessions receive the same authority model.
    tools = resolve_canonical_tools(canonical_root)
    denies = sibling_denies(worktree)
    static_denies = json.loads((canonical / "opencode.json").read_text(encoding="utf-8"))[
        "permission"
    ]["external_directory"]
    denies += [k for k, v in static_denies.items() if v == "deny"]
    bundle = build_content_bundle(canonical_root, sorted(set(denies)), execution_provider)
    env = dict(os.environ)
    # Pinned CLI applies this after CONFIG_CONTENT; never let ambient overrides
    # widen canonical permissions. Do not read or log its value.
    env.pop("OPENCODE_PERMISSION", None)
    config_dir = str(Path(run_dir) / "config-dir")
    manifest = build_config_dir(canonical_root, config_dir)
    policy_hash = drift_mod.canonical_bundle_hash(
        canonical_root, drift_mod.load_cpl_canonical_files(drift_mod.DEFAULT_PROFILES_DIR)
    )
    env[OPENCODE_BIN_ENV] = opencode_binary
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(bundle)
    env["OPENCODE_CONFIG_DIR"] = config_dir
    env["FOUNDRY_WORKSTREAM"] = workstream
    env["FOUNDRY_BRANCH"] = branch
    env["FOUNDRY_SESSION"] = session
    env["FOUNDRY_EFFORT"] = effort
    # WS75 state-path context, hardened by ROOT_STATE_SEMANTICS: the exact
    # explicit launcher state path is mandatory. There is no implicit active
    # repository-root state and no silent fallback, so Muse never guesses
    # `.foundry/WORKSTREAM_STATE.yaml`.
    # Values are paths/identities only — never secrets.
    if not state_path:
        raise ValueError("explicit --state is required (no implicit active state)")
    env["FOUNDRY_STATE_PATH"] = state_path
    env["FOUNDRY_WORKTREE"] = worktree
    env["FOUNDRY_RUN_DIR"] = run_dir
    env["FOUNDRY_MODE"] = mode
    env["FOUNDRY_REFERENCE_ROOTS"] = json.dumps(references, sort_keys=True)
    # WS196 canonical tool identity (paths/identities only — never secrets).
    # The session CWD may be an engine checkout; the exact canonical tool
    # path is authoritative, so no globbing or sibling discovery is needed.
    env["FOUNDRY_CANONICAL_ROOT"] = tools["canonical_root"]
    env["FOUNDRY_SAFE_PUSH"] = tools["safe_push"]
    env["FOUNDRY_CANONICAL_POLICY_HASH"] = policy_hash
    env["FOUNDRY_CONFIG_DIR_MANIFEST"] = manifest["sha256"]
    if drift_suppressed:
        env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        env["FOUNDRY_ROUTING_SUPPRESSED"] = "1"
    return env


def _metrics_path(run_dir: str) -> str:
    """Runtime telemetry lives under run_dir, outside the Git worktree."""
    return str(Path(run_dir) / "metrics.jsonl")


def write_launch_context(run_dir: str, context: dict) -> str:
    """Persist non-secret launch context for Muse/audit. Returns path."""
    path = Path(run_dir) / "launch-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def session_end_telemetry(
    *,
    run_dir: str,
    workstream: str,
    worktree: str,
    opencode_binary: str,
    explicit_session_id: str | None = None,
    timeout: int = 60,
) -> dict:
    """WS199 fail-open session-end telemetry (never blocks engineering).

    When the exact OpenCode session ID is available (explicit launcher flag,
    ``FOUNDRY_OPENCODE_SESSION_ID`` env, or ``<run_dir>/opencode-session-id``
    file), attempt one bounded exact-session capture. Otherwise emit a
    concise TELEMETRY_PENDING/TELEMETRY_HINT directing the operator to the
    explicit follow-up command. Never lists sessions, never guesses newest,
    never raises, never changes the engineering exit code (callers preserve
    ``rc`` regardless of this result).
    """
    try:
        exact = session_capture_mod.read_exact_session_id(run_dir, explicit_session_id)
    except Exception:
        exact = None
    if not exact:
        print("TELEMETRY_PENDING: exact OpenCode session ID unavailable", file=sys.stderr)
        print(
            f"TELEMETRY_HINT: {session_capture_mod.format_hint(run_dir)}",
            file=sys.stderr,
        )
        return {"status": "PENDING", "reason": "EXACT_SESSION_ID_UNAVAILABLE"}
    try:
        result = session_capture_mod.capture(
            run_dir=run_dir,
            session_id=exact,
            metrics_path=_metrics_path(run_dir),
            opencode_bin=opencode_binary,
            task_id=workstream,
            worktree=worktree,
            timeout=timeout,
        )
    except ValueError as exc:
        print(f"TELEMETRY_PENDING: {exc}", file=sys.stderr)
        print(
            f"TELEMETRY_HINT: {session_capture_mod.format_hint(run_dir)}",
            file=sys.stderr,
        )
        return {"status": "PENDING", "reason": str(exc)[:200]}
    except Exception as exc:  # fail-open: telemetry defects never gate engineering
        print(f"TELEMETRY_PENDING: capture defect: {exc}", file=sys.stderr)
        print(
            f"TELEMETRY_HINT: {session_capture_mod.format_hint(run_dir)}",
            file=sys.stderr,
        )
        return {"status": "PENDING", "reason": "CAPTURE_DEFECT"}
    if result.get("status") == "CAPTURED":
        # Aggregate identity only; raw content never reaches stdout/stderr.
        print(
            f"TELEMETRY_CAPTURED: session={result.get('session_id')} "
            f"metrics={result.get('metrics_path')}",
        )
    else:
        print(
            f"TELEMETRY_PENDING: {result.get('reason')} session={result.get('session_id')}",
            file=sys.stderr,
        )
        print(
            f"TELEMETRY_HINT: {session_capture_mod.format_hint(run_dir)}",
            file=sys.stderr,
        )
    return result


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
    state_path: str,
    canonical_root: str,
    allow_same_cwd_pids: bool,
    allow_suppressed_routing: bool,
    install_pre_push_hook: bool,
    run_dir: str,
    ui_mode: str = "headless",
    references: list[str] | None = None,
    opencode_bin: str | None = None,
    version_audit_mode: bool = False,
    worktree_states: list[str] | None = None,
    execution_provider: str | None = None,
    opencode_session_id: str | None = None,
) -> dict:
    """Validate + prepare. Returns the launch plan (never execs)."""
    try:
        execution = execution_identity(execution_provider, effort)
    except ValueError as exc:
        return {"verdict": "LAUNCH_REFUSED", "error": str(exc)}
    if not state_path:
        return {
            "verdict": "LAUNCH_REFUSED",
            "error": "explicit --state is required (no implicit active repository-root state)",
        }
    if ui_mode not in UI_MODES:
        return {"verdict": "LAUNCH_REFUSED", "error": f"unknown ui_mode {ui_mode!r}"}
    canonical = os.path.realpath(os.path.abspath(worktree))
    parsed_refs: list[dict] = []
    for raw in references or []:
        try:
            parsed_refs.append(reference_mod.parse_spec(raw))
        except reference_mod.ReferenceError as exc:
            return {"verdict": "LAUNCH_REFUSED", "error": f"reference: {exc}"}
    # Explicit ownership authority: the launcher always declares its own
    # worktree/state pair (ground truth for this run) plus any
    # operator-declared sibling pairs. A conflicting operator pair for our
    # own worktree is ambiguous and fails closed. Nothing is discovered.
    state_map: dict[str, str] = {}
    for raw in worktree_states or []:
        try:
            key, value = bootstrap_mod.parse_worktree_state(raw)
        except ValueError as exc:
            return {"verdict": "LAUNCH_REFUSED", "error": f"worktree-state: {exc}"}
        if key in state_map and state_map[key] != value:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"conflicting --worktree-state for {key!r}",
            }
        state_map[key] = value
    if canonical in state_map and state_map[canonical] != state_path:
        return {
            "verdict": "LAUNCH_REFUSED",
            "error": "--worktree-state for this worktree conflicts with --state",
        }
    state_map[canonical] = state_path
    binary = resolve_opencode_binary(opencode_bin)
    try:
        version = version_mod.verify(binary)
    except version_mod.VersionCheckError as exc:
        return {"verdict": "LAUNCH_REFUSED", "error": f"opencode version: {exc}"}
    version_note: str | None = None
    if not version["ok"] and not version_audit_mode:
        return {
            "verdict": "LAUNCH_REFUSED",
            "error": (
                f"opencode version drift: installed {version['installed']!r} != "
                f"qualified {version['expected']!r} "
                "(pass --version-audit-mode only for bounded migration/audit runs)"
            ),
        }
    if not version["ok"]:
        version_note = (
            f"version audit mode: installed {version['installed']!r} != "
            f"qualified {version['expected']!r} (proceeding explicitly)"
        )
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
        parsed_refs,
        state_map,
    )
    if gate["verdict"] != "BOOTSTRAP_PASS":
        return {"verdict": "LAUNCH_REFUSED", "gate": gate}
    drift_suppressed = gate["drift"]["verdict"] == "DRIFT_FAIL"
    resolved_state = state_path
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
            state_path=resolved_state,
            mode=mode,
            references=parsed_refs,
            opencode_binary=binary,
            execution_provider=execution_provider,
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
    # WS198 autonomy values (paths/identities/bounded enums only — never
    # prose, never secrets, never telemetry). Advisory snapshot for audit
    # parity with the capsule; the state file stays authoritative.
    autonomy_values: dict = autonomy_mod.autonomy_defaults({})
    autonomy_values.update(
        {
            "completion_ready": True,
            "completion_reason": "state unreadable at init (capsule is authoritative)",
        }
    )
    try:
        import yaml as _yaml

        with open(resolved_state, encoding="utf-8") as _handle:
            _state_data = _yaml.safe_load(_handle)
        if isinstance(_state_data, dict):
            _resolved = autonomy_mod.autonomy_defaults(_state_data)
            _ready, _reasons = autonomy_mod.check_completion_readiness(_state_data)
            autonomy_values = {
                **_resolved,
                "completion_ready": _ready,
                "completion_reason": _reasons[0] if _reasons else "n/a",
            }
    except Exception:
        _state_data = None
    # WS200 rotation advisory (fail-open, advisory-only): the same pure
    # state/Git observation the capsule renders, plus a telemetry
    # availability flag. It never gates LAUNCH_READY, never kills/resets,
    # never changes model/provider, and never thresholds telemetry values
    # (values are not read here at all).
    rotation_advisory: dict = {
        "recommendation": autonomy_values["rotation_recommendation"],
        "reasons": [],
        "fingerprint": None,
        "provenance": "state-derived",
    }
    rotation_telemetry_available = False
    try:
        if isinstance(_state_data, dict) and live_head != "UNKNOWN":
            _facts: dict = {"head": live_head}
            _porcelain = _git(["status", "--porcelain"], canonical)
            _facts["dirty_entries"] = len(_porcelain.splitlines()) if _porcelain else 0
            _observation = autonomy_mod.observe_rotation(_state_data, _facts, None)
            rotation_advisory = {
                "recommendation": _observation.get("recommendation"),
                "reasons": _observation.get("reasons"),
                "fingerprint": _observation.get("fingerprint"),
                "provenance": _observation.get("provenance"),
            }
        _status_raw = Path(run_dir, "telemetry-status.json").read_text(encoding="utf-8")
        _status_doc = json.loads(_status_raw)
        if (
            isinstance(_status_doc, dict)
            and _status_doc.get("status") == "CAPTURED"
            and isinstance(_status_doc.get("session_id"), str)
            and _status_doc.get("session_id")
        ):
            rotation_telemetry_available = True
    except Exception:
        pass
    context = {
        "execution": execution,
        "workstream": workstream,
        "branch": branch,
        "worktree": canonical,
        "state_path": resolved_state,
        "run_dir": run_dir,
        "mode": mode,
        "ui_mode": ui_mode,
        "effort": effort,
        "session": session,
        # WS199: exact OpenCode session ID for session-end capture when the
        # operator supplies it. FOUNDRY_SESSION stays the workstream label
        # (never an OpenCode ID). Empty means capture stays PENDING with a
        # hint; telemetry never blocks engineering and never guesses.
        "opencode_session_id": (opencode_session_id or "").strip(),
        "opencode_binary": binary,
        "opencode_version": version,
        "version_audit_mode": version_audit_mode,
        "canonical_policy_hash": env["FOUNDRY_CANONICAL_POLICY_HASH"],
        "config_dir_manifest": env["FOUNDRY_CONFIG_DIR_MANIFEST"],
        # WS196: machine-readable canonical tool identity (paths only).
        "canonical_root": env["FOUNDRY_CANONICAL_ROOT"],
        "canonical_safe_push": env["FOUNDRY_SAFE_PUSH"],
        # WS198: autonomy values snapshot (values only; state authoritative).
        "technical_decision_authority": autonomy_values["technical_decision_authority"],
        "continuation_policy": autonomy_values["continuation_policy"],
        "successor_status": autonomy_values["successor_status"],
        "rotation_recommendation": autonomy_values["rotation_recommendation"],
        "rotation_advisory": rotation_advisory,
        "rotation_telemetry_available": rotation_telemetry_available,
        "completion_ready": autonomy_values["completion_ready"],
        "completion_reason": autonomy_values["completion_reason"],
        "references": parsed_refs,
        "worktree_states": state_map,
        "live_head": live_head,
    }
    try:
        context_path = write_launch_context(run_dir, context)
    except OSError as exc:
        return {"verdict": "LAUNCH_REFUSED", "gate": gate, "error": f"context: {exc}"}
    # WS199: persist an explicitly supplied exact session ID for session-end
    # capture durability (fail-open: a write failure never refuses launch).
    notes = []
    explicit_sid = (opencode_session_id or "").strip()
    if explicit_sid:
        try:
            Path(run_dir, "opencode-session-id").write_text(explicit_sid + "\n", encoding="utf-8")
        except OSError:
            notes.append("opencode session ID not persisted (run-dir unwritable)")
    if version_note:
        notes.append(version_note)
    return {
        "verdict": "LAUNCH_READY",
        "execution": execution,
        "gate": gate,
        "env_keys": sorted(k for k in env if k.startswith(("OPENCODE_", "FOUNDRY_"))),
        "canonical_policy_hash": env["FOUNDRY_CANONICAL_POLICY_HASH"],
        "config_dir_manifest": env["FOUNDRY_CONFIG_DIR_MANIFEST"],
        "canonical_root": env["FOUNDRY_CANONICAL_ROOT"],
        "canonical_safe_push": env["FOUNDRY_SAFE_PUSH"],
        "hook_path": hook_path,
        "mode": mode,
        "ui_mode": ui_mode,
        "session": session,
        "opencode_session_id": (opencode_session_id or "").strip(),
        "live_head": live_head,
        "run_dir": run_dir,
        "state_path": resolved_state,
        "worktree_states": state_map,
        "opencode_binary": binary,
        "opencode_version": version,
        "version_audit_mode": version_audit_mode,
        "context_path": context_path,
        "notes": notes,
        "_env": env,
    }


def launch(
    plan: dict,
    argv_extra: list[str],
    worktree: str,
    workstream: str,
    effort: str,
    ui_mode: str | None = None,
) -> int:
    """Hold the writer lock across the OpenCode child; telemetry; passthrough exit."""
    if plan.get("verdict") != "LAUNCH_READY":
        print(f"LAUNCH_REFUSED: {plan.get('error', plan.get('gate', {}))}", file=sys.stderr)
        return 1
    try:
        validate_child_options(argv_extra)
        mode = ui_mode or plan.get("ui_mode", "headless")
        if mode == "tui":
            # WS198: bare TUI positionals are project paths, not prompts
            # (exit-0 false success). Canonicalize before taking the lock.
            argv_extra = canonicalize_tui_extras(argv_extra)
        execution = plan.get("execution") or execution_identity(None, effort)
        if effort not in ALLOWED_EFFORTS or execution["requested_effort"] != effort:
            raise ValueError("launch effort differs from validated plan")
    except ValueError as exc:
        print(f"LAUNCH_REFUSED: {exc}", file=sys.stderr)
        return 1
    mode = ui_mode or plan.get("ui_mode", "headless")
    env: dict = plan["_env"]
    lock = writer_lock_mod.WriterLock(
        worktree, workstream, env.get("FOUNDRY_BRANCH", ""), env.get("FOUNDRY_SESSION", "")
    )
    try:
        lock.acquire()
    except writer_lock_mod.LockedError as exc:
        print(str(exc), file=sys.stderr)
        return writer_lock_mod.HELD_EXIT
    try:
        rc = _launch_locked(plan, argv_extra, worktree, workstream, effort, mode, execution)
    finally:
        lock.release()
    # WS199: fail-open session-end telemetry runs AFTER the writer lock is
    # released (run_dir only; never the worktree). It never changes rc:
    # exact ID -> bounded capture attempt; absent -> PENDING + hint.
    try:
        session_end_telemetry(
            run_dir=plan.get("run_dir") or "/tmp/foundry-launch-unknown",
            workstream=workstream,
            worktree=worktree,
            opencode_binary=plan.get("opencode_binary")
            or plan.get("_env", {}).get(OPENCODE_BIN_ENV, "opencode"),
            explicit_session_id=plan.get("opencode_session_id") or None,
        )
    except Exception as exc:  # never gate engineering on telemetry
        print(f"TELEMETRY_PENDING: session-end telemetry defect: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("TELEMETRY_PENDING: session-end telemetry interrupted", file=sys.stderr)
    return rc


def _launch_locked(
    plan: dict,
    argv_extra: list[str],
    worktree: str,
    workstream: str,
    effort: str,
    mode: str,
    execution: dict,
) -> int:
    """Child + telemetry; the caller releases ownership even if telemetry fails."""
    env = plan["_env"]
    run_dir = plan.get("run_dir") or env.get("FOUNDRY_RUN_DIR") or "/tmp/foundry-launch-unknown"
    metrics_path = _metrics_path(run_dir)
    start_mono = time.monotonic()
    start_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    auto = {
        "task_id": "AUTOCAPTURED",
        "task_class": "AUTOCAPTURED",
        "repo_profile": "AUTOCAPTURED",
        "ui_mode": "AUTOCAPTURED",
        "model": "AUTOCAPTURED",
        "reasoning_effort": "AUTOCAPTURED",
        "source_sha": "AUTOCAPTURED",
        "started_utc": "AUTOCAPTURED",
        "execution_provider": "AUTOCAPTURED",
        "execution_override": "AUTOCAPTURED",
        "variant_resolution": "AUTOCAPTURED",
    }
    try:
        metrics_mod.record(
            metrics_path,
            _provenance=auto,
            task_id=workstream,
            task_class="workstream-session",
            repo_profile=plan.get("gate", {}).get("profile", "UNKNOWN"),
            ui_mode=mode,
            model=execution["model"],
            execution_provider=execution["provider"],
            execution_override=execution["override"],
            variant_resolution=execution["variant_resolution"],
            reasoning_effort=effort,
            source_sha=plan.get("live_head"),
            started_utc=start_utc,
        )
    except OSError as exc:
        print(f"LAUNCH_WARN: telemetry start not recorded: {exc}", file=sys.stderr)
    binary = plan.get("opencode_binary") or env.get(OPENCODE_BIN_ENV, "opencode")
    try:
        # CLI selection outranks persisted session/model history on an explicit
        # Zen launch. Caller model flags were rejected before taking the lock.
        selected = ["--model", execution["model"]] if execution["override"] == "zen" else []
        argv = build_argv(binary, mode, [*selected, *argv_extra])
    except ValueError as exc:
        print(f"LAUNCH_REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"LAUNCH: holding writer lock; exec {' '.join(argv)} (cwd={worktree})")
    rc = 1
    interrupted = False
    failure_class = "CHILD_EXCEPTION"
    try:
        proc = subprocess.run(argv, cwd=worktree, env=env, check=False)
        rc = proc.returncode
        interrupted = rc in (-2, 130)
        if rc == -2:
            rc = 130
        failure_class = "INTERRUPTED" if interrupted else "NONE" if rc == 0 else "CHILD_EXIT"
    except KeyboardInterrupt:
        rc = 130
        interrupted = True
        failure_class = "INTERRUPTED"
    except OSError:
        rc = 127
        failure_class = "CHILD_START_FAILED"
    finally:
        elapsed = time.monotonic() - start_mono
        try:
            end_head = _git(["rev-parse", "HEAD"], worktree)
        except (RuntimeError, KeyboardInterrupt):
            end_head = "UNKNOWN"
        try:
            metrics_mod.record(
                metrics_path,
                _provenance={
                    **auto,
                    "final_sha": "AUTOCAPTURED",
                    "ended_utc": "AUTOCAPTURED",
                    "elapsed_seconds": "AUTOCAPTURED",
                    "exit_status": "AUTOCAPTURED",
                    "completed": "AUTOCAPTURED",
                    "interrupted": "AUTOCAPTURED",
                    "failure_class": "AUTOCAPTURED",
                    "ui_mode": "AUTOCAPTURED",
                },
                task_id=workstream,
                task_class="workstream-session",
                repo_profile=plan.get("gate", {}).get("profile", "UNKNOWN"),
                ui_mode=mode,
                model=execution["model"],
                execution_provider=execution["provider"],
                execution_override=execution["override"],
                variant_resolution=execution["variant_resolution"],
                reasoning_effort=effort,
                final_sha=end_head,
                ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                exit_status=rc,
                completed=(rc == 0),
                interrupted=interrupted,
                failure_class=failure_class,
                elapsed_seconds=round(elapsed, 1),
            )
        except OSError as exc:
            print(f"LAUNCH_WARN: telemetry end not recorded: {exc}", file=sys.stderr)
    print(f"LAUNCH_END: exit={rc} elapsed={elapsed:.1f}s")
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
    parser.add_argument(
        "--execution-provider",
        choices=("zen",),
        default=None,
        help="Explicit operator-authorized Zen execution only; omitted keeps OpenCode Go.",
    )
    parser.add_argument("--mode", default="writer", choices=("writer", "reader"))
    parser.add_argument("--session", default="")
    parser.add_argument(
        "--state",
        required=True,
        help="Explicit workstream state file (mandatory; no implicit fallback).",
    )
    parser.add_argument("--canonical-root", required=True)
    parser.add_argument("--allow-same-cwd-pids", action="store_true")
    parser.add_argument("--allow-suppressed-routing", action="store_true")
    parser.add_argument("--install-hook", action="store_true")
    parser.add_argument("--run-dir", default=None)
    parser.add_argument(
        "--ui-mode",
        default="headless",
        choices=("headless", "tui"),
        help="headless execs `opencode run --auto <bare message>`; tui execs "
        "`opencode --auto --prompt <message>`. Bare positional text is a "
        "prompt ONLY for headless (TUI binds it to [project] and fails); "
        "pass TUI prompt text as `-- --prompt \"<task>\"`.",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Declared read-only reference root as JSON (repeatable).",
    )
    parser.add_argument(
        "--worktree-state",
        action="append",
        default=[],
        help="Explicit ownership authority as WORKTREE=STATE (repeatable).",
    )
    parser.add_argument(
        "--opencode-bin",
        default=None,
        help="Exact OpenCode binary (default: $FOUNDRY_OPENCODE_BIN or PATH `opencode`).",
    )
    parser.add_argument(
        "--version-audit-mode",
        action="store_true",
        help="Bounded migration/audit mode: proceed despite CLI version drift (recorded).",
    )
    parser.add_argument(
        "--opencode-session-id",
        default="",
        help="Exact OpenCode session ID for WS199 session-end telemetry capture "
        "(optional; never auto-selected). FOUNDRY_SESSION stays the workstream "
        "label. Absent keeps telemetry PENDING with a follow-up hint; telemetry "
        "never blocks engineering.",
    )
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
        ui_mode=args.ui_mode,
        references=args.reference,
        opencode_bin=args.opencode_bin,
        version_audit_mode=args.version_audit_mode,
        worktree_states=args.worktree_state,
        execution_provider=args.execution_provider,
        opencode_session_id=args.opencode_session_id,
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
