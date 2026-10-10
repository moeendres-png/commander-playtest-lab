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

Effort: --effort must be high|xhigh (below-HIGH rejected) and describes task and
authority routing only; it never lowers a selected executor's native level. Both
reachable executors run at native ``max`` regardless of the requested project
effort. The launcher records effort in telemetry and lock metadata; it invents no
OpenCode flags.

WS75 hardening:

- ``--ui-mode headless`` (default) execs first-class headless argv
  ``opencode run --auto <extra...>`` exactly in that order (opencode.ai
  CLI docs: ``opencode run --auto "msg"``). ``--ui-mode tui`` preserves
  the interactive form ``opencode --auto <extra...>``. No external
  wrapper is needed for either form.
- Runtime telemetry lives under ``run_dir`` (outside the Git worktree);
  launcher execution leaves the worktree clean.
- The exact ``--state`` path plus worktree/branch/workstream/run-dir/
  mode/effort reach the selected worker as ``FOUNDRY_*`` env (no secrets) and as
  ``run_dir/launch-context.json``.
- Declared read-only reference roots (``--reference`` JSON, repeatable) are verified and materialized as disposable detached snapshots; the authoritative source root remains denied.
- Explicit ``--workspace-access`` surfaces may be read-only or owned-write; writable
  surfaces bind repo/branch/HEAD/tree/state/ownership and are multi-locked for the
  complete child lifetime.
- Any run with cross-workstream references/access is executed under a fail-closed
  Bubblewrap read-only-root mount namespace. Only the primary standalone checkout,
  explicit standalone owned-write roots,
  run/temp state and narrow tool caches are writable; sandbox setup failure refuses launch.
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
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap as bootstrap_mod
import drift_check as drift_mod
import executor_profiles as executor_mod
import metrics as metrics_mod
import opencode_cli_version as version_mod
import reference_roots as reference_mod
import workspace_access as workspace_access_mod
import writer_lock as writer_lock_mod

CANONICAL_PROVIDER = executor_mod.CANONICAL_PROVIDER
# Operator authority (2026-09-29), durable cross-executor policy (2026-10-06)
# and Owner directive (2026-10-10): the registry holds exactly two LOGICAL
# executors, each pinned to one native reasoning level, but only ACTIVE ones are
# reachable. Space Bunny MAX is the default and only ACTIVE executor and the
# mandatory fresh-context read-only reviewer for MATERIAL implementation
# workstreams; DeepSeek MAX is SUSPENDED (OpenCode Go monthly quota exhausted)
# and is refused at resolution. The logical `space-bunny` profile admits exactly
# its OpenCode Zen runtime id (see .foundry/executor-profiles.json); the Go ids
# are retired and no third executor exists. A
# runtime/quota/auth/catalog failure after selection is fail-closed and never
# re-resolves to another executor family.
SPACE_BUNNY_PROFILE = "space-bunny"
DEEPSEEK_PROFILE = "deepseek"
# Single generic profile->canonical-runtime table, loaded from the validated
# registry so code and durable policy cannot drift.
EXECUTOR_REGISTRY = executor_mod.load_registry()
PRIMARY_EXECUTION_PROFILE = EXECUTOR_REGISTRY.default_profile
EXECUTION_PROFILES = EXECUTOR_REGISTRY.logical_profiles
ACTIVE_EXECUTION_PROFILES = EXECUTOR_REGISTRY.active_profiles
DEFAULT_EXECUTION_PROFILE = PRIMARY_EXECUTION_PROFILE
PROFILE_MODELS = {
    name: spec.canonical_runtime_id for name, spec in EXECUTOR_REGISTRY.profiles.items()
}
DEEPSEEK_MODEL = PROFILE_MODELS[DEEPSEEK_PROFILE]
SPACE_BUNNY_MODEL = PROFILE_MODELS[SPACE_BUNNY_PROFILE]
CANONICAL_MODEL = PROFILE_MODELS[PRIMARY_EXECUTION_PROFILE]
# The admitted Space Bunny runtime ids (only the Zen id since 2026-10-10).
ADMITTED_BUNNY_MODELS = EXECUTOR_REGISTRY.profiles[SPACE_BUNNY_PROFILE].admitted_runtime_ids
# Only ACTIVE profiles' runtime ids are reachable; the root opencode.json
# whitelist must match exactly this set, so a SUSPENDED model is not even
# selectable by a plain `opencode` invocation.
ADMITTED_RUNTIME_MODELS = EXECUTOR_REGISTRY.active_runtime_ids
ADMITTED_MODEL_SHORTS = tuple(model.split("/", 1)[1] for model in ADMITTED_RUNTIME_MODELS)
AUTHORIZED_NATIVE_VARIANT = {
    model.split("/", 1)[1]: EXECUTOR_REGISTRY.profiles[
        EXECUTOR_REGISTRY.runtime_identity[model].logical_profile
    ].native_variant
    for model in ADMITTED_RUNTIME_MODELS
}
ALLOWED_EFFORTS = ("high", "xhigh")
BELOW_HIGH = ("medium", "low", "minimal", "none", "off")
OPENCODE_BIN_ENV = "FOUNDRY_OPENCODE_BIN"
UI_MODES = ("headless", "tui")


def execution_identity(
    override: str | None,
    effort: str,
    execution_profile: str | None = None,
    *,
    catalog: list[str] | tuple[str, ...] | None = None,
    catalog_source: str | None = None,
) -> dict:
    """Resolve one explicit executor; never infer/fallback from quota or failures.

    Space Bunny resolution requires live pinned-CLI catalog inspection (or an
    explicit ``catalog`` supplied by hermetic callers/tests); the canonical
    runtime id wins, the admitted legacy alias is second, and an empty
    admission fails closed. A post-selection failure never re-resolves.
    """
    if override is not None:
        # Legacy provider overrides are retired. Every provider override fails
        # closed so callers cannot escape the exact two-profile allowlist.
        raise ValueError(
            f"execution provider override {override!r} is retired; provider overrides "
            "are not authorized by the current two-profile execution policy"
        )
    if execution_profile not in (None, *EXECUTION_PROFILES):
        raise ValueError(f"unknown execution profile {execution_profile!r}")
    if effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort {effort!r} rejected (allowed: {ALLOWED_EFFORTS})")

    profile = execution_profile or DEFAULT_EXECUTION_PROFILE
    try:
        resolved = executor_mod.resolve_executor(
            profile,
            registry=EXECUTOR_REGISTRY,
            catalog=catalog,
            catalog_source=catalog_source,
        )
    except executor_mod.ExecutorResolutionError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "profile": resolved.logical_executor_profile,
        "override": resolved.logical_executor_profile,
        "provider": resolved.resolved_provider,
        "model": resolved.resolved_model_id,
        "requested_effort": effort,
        "variant_resolution": "native_max",
        "native_variant": resolved.native_variant,
        **resolved.to_provenance(),
    }


def validate_child_options(extra: list[str]) -> None:
    """Selection belongs to the launcher; explicit session IDs remain supported."""
    for arg in extra:
        if arg == "--":
            break  # Remaining words are literal prompt text, not CLI options.
        key = arg.split("=", 1)[0]
        if (
            key in ("--model", "--variant", "--continue")
            or (arg.startswith("-m") and not arg.startswith("--"))
            or arg == "-c"
        ):
            raise ValueError("model/variant/continue child flags are launcher-controlled")


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


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _git_dir(worktree: str) -> str:
    common = _git(["rev-parse", "--git-common-dir"], worktree)
    path = Path(common)
    return str(path if path.is_absolute() else Path(worktree) / common)


def _git_path(root: str, args: list[str]) -> str:
    raw = _git(args, root)
    path = Path(raw)
    return os.path.realpath(str(path if path.is_absolute() else Path(root) / path))


def _is_standalone_checkout(root: str) -> bool:
    """True only when all Git metadata belongs to this checkout."""
    canonical = os.path.realpath(os.path.abspath(root))
    dotgit = Path(canonical) / ".git"
    if not dotgit.is_dir():
        return False
    try:
        git_dir = _git_path(canonical, ["rev-parse", "--git-dir"])
        common_dir = _git_path(canonical, ["rev-parse", "--git-common-dir"])
    except RuntimeError:
        return False
    expected = os.path.realpath(str(dotgit))
    if git_dir != expected or common_dir != expected:
        return False

    # A nested repository would inherit the parent writable mount even though it is
    # a distinct mutation surface. Submodules/nested repos therefore require their
    # own isolated assignment instead of silently riding the parent capability.
    for current, dirs, files in os.walk(canonical):
        if os.path.realpath(current) == canonical:
            dirs[:] = [name for name in dirs if name != ".git"]
            continue
        if ".git" in dirs or ".git" in files:
            return False
    return True


def _contains_path(parent: str, child: str) -> bool:
    parent_real = os.path.realpath(os.path.abspath(parent))
    child_real = os.path.realpath(os.path.abspath(child))
    try:
        return os.path.commonpath([parent_real, child_real]) == parent_real
    except ValueError:
        return False


def _paths_overlap(a: str, b: str) -> bool:
    return _contains_path(a, b) or _contains_path(b, a)


def _repo_worktree_roots(root: str) -> set[str]:
    try:
        raw = _git(["worktree", "list", "--porcelain"], root)
    except RuntimeError:
        return {os.path.realpath(os.path.abspath(root))}
    roots = {
        os.path.realpath(line[len("worktree ") :])
        for line in raw.splitlines()
        if line.startswith("worktree ")
    }
    return roots or {os.path.realpath(os.path.abspath(root))}


def _state_inside_surface(state_path: str, root: str) -> bool:
    state_real = os.path.realpath(os.path.abspath(state_path))
    foundry_root = os.path.realpath(os.path.join(root, ".foundry"))
    return _contains_path(foundry_root, state_real)


def _validate_cross_ws_topology(
    primary: str,
    state_path: str,
    refs: list[dict],
    access: list[dict],
    requested_run_dir: str,
) -> str | None:
    """Fail closed on topology that can leak cross-workstream mutation authority."""
    if not refs and not access:
        return None

    writable = {os.path.realpath(primary)}
    writable.update(
        os.path.realpath(spec["root"]) for spec in access if spec.get("access") == "owned-write"
    )
    readonly = {os.path.realpath(ref["root"]) for ref in refs}
    readonly.update(
        os.path.realpath(spec["root"]) for spec in access if spec.get("access") == "read-only"
    )

    # Cross-WS mutation requires checkout-local Git metadata. Shared worktree Git
    # directories would otherwise expose refs/index/config for foreign surfaces.
    for root in sorted(writable):
        if not _is_standalone_checkout(root):
            return (
                f"cross-workstream writable surface {root!r} is not a standalone "
                "checkout with checkout-local .git metadata"
            )

    if not _state_inside_surface(state_path, primary):
        return "cross-workstream primary --state must live under PRIMARY/.foundry"
    for spec in access:
        if spec.get("access") != "owned-write":
            continue
        if not _state_inside_surface(spec["state_path"], spec["root"]):
            return f"owned-write surface {spec['label']!r} state must live under ROOT/.foundry"

    protected = set(readonly)
    for root in sorted(writable | readonly):
        protected.update(_repo_worktree_roots(root) - writable)

    writable_list = sorted(writable)
    for index, write_root in enumerate(writable_list):
        for other in writable_list[index + 1 :]:
            if _paths_overlap(write_root, other):
                return (
                    f"writable surfaces {write_root!r} and {other!r} overlap; "
                    "each mutation surface must be disjoint"
                )
        for protected_root in sorted(protected):
            if _paths_overlap(write_root, protected_root):
                return (
                    f"writable surface {write_root!r} overlaps protected workspace "
                    f"{protected_root!r}"
                )

    run_real = os.path.realpath(os.path.abspath(requested_run_dir))
    if not _runtime_base_allowed(run_real):
        return (
            "cross-workstream run-dir must be under the system temp directory or "
            "~/.local/share/commander-foundry/runs"
        )
    for root in sorted(writable | protected):
        if _paths_overlap(run_real, root):
            return f"run-dir {run_real!r} overlaps authoritative/protected workspace {root!r}"
    return None


def _runtime_base_allowed(path: str) -> bool:
    canonical = os.path.realpath(os.path.abspath(path))
    tmp_base = os.path.realpath(tempfile.gettempdir())
    home = Path(os.environ.get("HOME", str(Path.home())))
    foundry_base = os.path.realpath(str(home / ".local" / "share" / "commander-foundry" / "runs"))
    return _contains_path(tmp_base, canonical) or _contains_path(foundry_base, canonical)


def _reserve_run_dir(requested_run_dir: str, workstream: str) -> str:
    if not _runtime_base_allowed(requested_run_dir):
        raise ValueError(
            "cross-workstream run-dir must be under the system temp directory or "
            "~/.local/share/commander-foundry/runs"
        )
    parent = Path(requested_run_dir)
    parent.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in workstream)[:48]
    return os.path.realpath(tempfile.mkdtemp(prefix=f"launch-{safe}-", dir=str(parent)))


def _sandbox_write_roots(plan: dict, worktree: str, run_dir: str) -> list[str]:
    """Exact paths the cross-WS child may mutate under the mount sandbox."""
    roots = {
        os.path.realpath(worktree),
        os.path.realpath(run_dir),
    }
    for spec in plan.get("workspace_access", []):
        if spec.get("access") == "owned-write":
            roots.add(os.path.realpath(spec["root"]))

    home = Path(os.environ.get("HOME", str(Path.home())))
    cache_candidates = [
        home / ".cache" / "opencode",
        home / ".local" / "share" / "opencode",
        home / ".local" / "state" / "opencode",
        home / ".m2",
        home / ".gradle",
        home / ".npm",
    ]
    for path in cache_candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        roots.add(os.path.realpath(str(path)))
    if Path("/dev/shm").is_dir():
        roots.add("/dev/shm")
    return sorted(roots)


def _sandbox_command(plan: dict, argv: list[str], worktree: str, run_dir: str) -> list[str]:
    """Wrap cross-WS execution in the fail-closed read-only-root mount sandbox."""
    if not plan.get("references") and not plan.get("workspace_access"):
        return argv
    sandbox = Path(__file__).resolve().parent / "fs_sandbox.py"
    if not sandbox.is_file():
        raise ValueError(f"cross-workstream sandbox helper missing: {sandbox}")
    command = [sys.executable, str(sandbox)]
    for root in _sandbox_write_roots(plan, worktree, run_dir):
        command.extend(["--allow-write", root])
    return [*command, "--", *argv]


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


def _root_patterns(root: str) -> tuple[str, str]:
    """Exact directory + descendants without same-prefix sibling leakage."""
    canonical = os.path.realpath(os.path.abspath(root)).rstrip("/")
    return canonical, f"{canonical}/*"


def _edit_patterns(root: str, worktree: str) -> tuple[str, ...]:
    """Edit-permission patterns for one root, in the form the pinned CLI matches.

    OpenCode asks the ``edit`` permission with ``path.relative(worktree, file)``
    (write/edit/patch tools, CLI 1.18.30), so an absolute pattern never matches
    an edit. The E1 runtime canary proved it: an absolute ``edit`` deny on a
    directory outside the worktree let the write through, the same directory
    as a worktree-relative pattern was denied. The absolute forms are kept for
    readers of the bundle; the relative forms are the ones that bind.
    """
    absolute = _root_patterns(root)
    try:
        relative = os.path.relpath(absolute[0], os.path.realpath(os.path.abspath(worktree)))
    except ValueError:  # different drive on Windows: no relative form exists
        return absolute
    return (*absolute, relative, f"{relative}/*")


def sibling_denies(worktree: str, accessible_roots: set[str] | None = None) -> list[str]:
    """Deny every undeclared sibling worktree of the same repo at path boundaries."""
    canonical = os.path.realpath(os.path.abspath(worktree))
    accessible = {os.path.realpath(path) for path in (accessible_roots or set())}
    try:
        raw = _git(["worktree", "list", "--porcelain"], canonical)
    except RuntimeError:
        return []
    denies: list[str] = []
    for line in raw.splitlines():
        if line.startswith("worktree "):
            path = os.path.realpath(line[len("worktree ") :])
            if path != canonical and path not in accessible:
                denies.extend(_root_patterns(path))
    return sorted(set(denies))


def _clone_snapshot(source_root: str, commit: str, destination: Path) -> str:
    """Materialize one exact disposable snapshot at a fresh unique destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(f"reference snapshot destination already exists: {destination}")
    proc = subprocess.run(
        ["git", "clone", "--no-hardlinks", "--no-checkout", source_root, str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"reference snapshot clone failed: {proc.stderr.strip()[:200]}")
    proc = subprocess.run(
        ["git", "checkout", "--detach", commit],
        cwd=str(destination),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"reference snapshot checkout failed: {proc.stderr.strip()[:200]}")
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=str(destination),
        capture_output=True,
        text=True,
        check=False,
    )
    live = _git(["rev-parse", "HEAD"], str(destination))
    if live != commit:
        raise ValueError(f"reference snapshot HEAD {live!r} != expected {commit!r}")
    return os.path.realpath(str(destination))


def materialize_runtime_references(
    references: list[dict], workspace_access: list[dict], run_dir: str
) -> tuple[list[dict], list[dict]]:
    """Replace read-only source roots with disposable runtime snapshots.

    The authoritative source worktree is never added to the OpenCode external-directory
    allowlist. Build tools may write into the disposable snapshot without mutating source.
    """
    base = Path(run_dir) / "reference-snapshots"
    base.mkdir(parents=True, exist_ok=True)
    runtime_refs: list[dict] = []
    runtime_access: list[dict] = []
    for ref in references:
        source_root = os.path.realpath(ref["root"])
        slot = Path(tempfile.mkdtemp(prefix=f"reference-{ref['label']}-", dir=str(base)))
        runtime_root = _clone_snapshot(source_root, ref["commit"], slot / "checkout")
        item = dict(ref)
        item["source_root"] = source_root
        item["root"] = runtime_root
        runtime_refs.append(item)
    for spec in workspace_access:
        if spec["access"] == "owned-write":
            runtime_access.append(dict(spec))
            continue
        source_root = os.path.realpath(spec["root"])
        slot = Path(tempfile.mkdtemp(prefix=f"workspace-{spec['label']}-", dir=str(base)))
        runtime_root = _clone_snapshot(source_root, spec["commit"], slot / "checkout")
        item = dict(spec)
        item["source_root"] = source_root
        item["root"] = runtime_root
        runtime_access.append(item)
    return runtime_refs, runtime_access


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
    canonical_root: str,
    extra_denies: list[str],
    execution_provider: str | None = None,
    execution_profile: str | None = None,
    catalog: list[str] | tuple[str, ...] | None = None,
    catalog_source: str | None = None,
) -> dict:
    """Canonical permissions with one explicitly selected execution model."""
    config_path = Path(canonical_root) / "opencode.json"
    execution = execution_identity(
        execution_provider,
        "high",
        execution_profile,
        catalog=catalog,
        catalog_source=catalog_source,
    )
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
    # The whitelist admits exactly the ACTIVE runtime identities: the Zen Space
    # Bunny id. A SUSPENDED profile (DeepSeek), the retired Go ids and any third
    # executor are not admitted.
    try:
        models = config["provider"][CANONICAL_PROVIDER]["models"]
    except KeyError as exc:
        raise ValueError(f"canonical model entry missing: {exc}") from exc
    whitelist = config["provider"][CANONICAL_PROVIDER].get("whitelist", [])
    if whitelist != list(ADMITTED_MODEL_SHORTS):
        raise ValueError(
            f"canonical execution allowlist drift: {whitelist!r} "
            f"(want admitted runtime identities {list(ADMITTED_MODEL_SHORTS)!r})"
        )
    for model_name in ADMITTED_MODEL_SHORTS:
        try:
            variants = models[model_name]["variants"]
        except KeyError as exc:
            raise ValueError(f"canonical model entry missing: {exc}") from exc
        for effort in BELOW_HIGH:
            if variants.get(effort) != {"disabled": True}:
                raise ValueError(
                    f"canonical below-HIGH variant {effort!r} not disabled for {model_name!r}"
                )
        # Exactly one reachable native level per model, and it must be the
        # authorized one. Anything else would silently re-open a retired effort
        # level, so fail closed instead of trusting the declaration order.
        want = AUTHORIZED_NATIVE_VARIANT[model_name]
        enabled = sorted(name for name, spec in variants.items() if spec != {"disabled": True})
        if enabled != [want]:
            raise ValueError(
                f"authorized-variant drift for {model_name!r}: enabled {enabled!r} "
                f"(want exactly [{want!r}])"
            )
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
    # Narrow the bundle to the RESOLVED profile/model, never the raw flag. An
    # omitted flag resolves to the registry default, so branching on the flag
    # would let a default launch fall through to the wrong executor block.
    # For Space Bunny the model is the resolved Zen runtime identity, already
    # provenance-recorded in `execution`.
    selected_model = execution["model"]
    short = selected_model.split("/", 1)[1]
    bundle["model"] = selected_model
    bundle["small_model"] = selected_model
    bundle["enabled_providers"] = [CANONICAL_PROVIDER]
    bundle["provider"] = {
        CANONICAL_PROVIDER: {
            "whitelist": [short],
            "models": {
                short: {
                    "options": {"reasoningEffort": "max"},
                    "variants": {"max": {}},
                }
            },
        }
    }
    # Inline run config wins over the canonical Markdown snapshot and pins every
    # reachable agent to the selected executor at exactly its authorized native
    # level, so no agent can silently run at another level or executor.
    names = {"build", "plan", "general", "explore", "compaction", "title", "summary"}
    names.update(config.get("agent", {}))
    names.update(p.stem for p in (Path(canonical_root) / ".opencode" / "agents").glob("*.md"))
    bundle["agent"] = {name: {"model": selected_model, "variant": "max"} for name in sorted(names)}
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
    workspace_access: list[dict],
    opencode_binary: str,
    execution_provider: str | None = None,
    execution_profile: str | None = None,
    catalog: list[str] | tuple[str, ...] | None = None,
    catalog_source: str | None = None,
) -> dict:
    """Build the child environment. Raises ValueError fail-closed."""
    if effort in BELOW_HIGH or effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort {effort!r} rejected (allowed: {ALLOWED_EFFORTS})")
    canonical = Path(canonical_root)
    if not (canonical / "opencode.json").is_file() or not (canonical / "AGENTS.md").is_file():
        raise ValueError(f"canonical root {canonical_root!r} lacks policy files")
    writable_roots = {
        os.path.realpath(spec["root"])
        for spec in workspace_access
        if spec["access"] == "owned-write"
    }
    authoritative_roots = {os.path.realpath(worktree)}
    authoritative_roots.update(
        os.path.realpath(ref.get("source_root", ref["root"])) for ref in references
    )
    authoritative_roots.update(
        os.path.realpath(spec.get("source_root", spec["root"])) for spec in workspace_access
    )
    denies: list[str] = []
    for repo_root in sorted(authoritative_roots):
        denies.extend(sibling_denies(repo_root, writable_roots))
    static_denies = json.loads((canonical / "opencode.json").read_text(encoding="utf-8"))[
        "permission"
    ]["external_directory"]
    static_denies_only = [k for k, v in static_denies.items() if v == "deny"]
    source_roots = {os.path.realpath(ref.get("source_root", ref["root"])) for ref in references} | {
        os.path.realpath(spec.get("source_root", spec["root"])) for spec in workspace_access
    }
    for root in sorted(source_roots):
        for pattern in static_denies_only:
            prefix = pattern[:-1] if pattern.endswith("*") else pattern
            if root == prefix or root.startswith(prefix):
                raise ValueError(
                    f"declared workspace root {root!r} conflicts with static deny {pattern!r}"
                )
    denies += static_denies_only
    execution = execution_identity(
        execution_provider,
        effort,
        execution_profile,
        catalog=catalog,
        catalog_source=catalog_source,
    )
    bundle = build_content_bundle(
        canonical_root,
        sorted(set(denies)),
        execution_provider,
        execution_profile,
        catalog=catalog,
        catalog_source=catalog_source,
    )
    ext = bundle["permission"].setdefault("external_directory", {})
    edit = bundle["permission"].setdefault("edit", {})
    # E1: sibling worktrees are also denied at the edit layer. External-directory
    # denies alone do not bind under the system temp directory, which the pinned
    # CLI exempts from that check (runtime canary); edit rules always apply.
    for pattern in denies:
        if not pattern.endswith("/*") and pattern not in static_denies_only:
            for edit_pattern in _edit_patterns(pattern, worktree):
                edit[edit_pattern] = "deny"
    for ref in references:
        source = ref.get("source_root")
        if source:
            for pattern in _root_patterns(source):
                ext[pattern] = "deny"
            for pattern in _edit_patterns(source, worktree):
                edit[pattern] = "deny"
        root = os.path.realpath(ref["root"])
        for pattern in _root_patterns(root):
            ext[pattern] = "allow"
        for pattern in _edit_patterns(root, worktree):
            edit[pattern] = "deny"
    for spec in workspace_access:
        source = spec.get("source_root")
        if source:
            for pattern in _root_patterns(source):
                ext[pattern] = "deny"
            for pattern in _edit_patterns(source, worktree):
                edit[pattern] = "deny"
        root = os.path.realpath(spec["root"])
        for pattern in _root_patterns(root):
            ext[pattern] = "allow"
        for pattern in _edit_patterns(root, worktree):
            edit[pattern] = "allow" if spec["access"] == "owned-write" else "deny"
    # Root-specific allows are intentionally broad, so canonical sensitive-file
    # edit denials must be reinserted LAST (OpenCode permission matching is
    # last-match-wins). Reinsert rather than overwrite to move ordering.
    canonical_edit = json.loads((canonical / "opencode.json").read_text(encoding="utf-8"))[
        "permission"
    ]["edit"]
    for pattern, action in canonical_edit.items():
        if action != "deny":
            continue
        edit.pop(pattern, None)
        edit[pattern] = "deny"
    env = dict(os.environ)
    # E1: the pinned CLI takes its session directory (and so its project, its
    # worktree-relative edit patterns and its external-directory boundary) from
    # PWD, not from the process cwd. An inherited PWD would run the child in
    # the operator's directory, e.g. the main checkout, while cwd is the
    # worktree (runtime canary: session directory = parent PWD).
    env["PWD"] = os.path.realpath(os.path.abspath(worktree))
    # Pinned CLI applies this after CONFIG_CONTENT; never let ambient overrides
    # widen canonical permissions. Do not read or log its value.
    env.pop("OPENCODE_PERMISSION", None)
    # Conditional execution-identity keys must be cleared before this launch
    # plan is applied. Otherwise a nested Foundry invocation can inherit an
    # outer session's native variant or routing-suppression state even when
    # the child plan does not authorize it.
    for inherited_identity_key in (
        "FOUNDRY_NATIVE_VARIANT",
        "OPENCODE_DISABLE_PROJECT_CONFIG",
        "FOUNDRY_ROUTING_SUPPRESSED",
    ):
        env.pop(inherited_identity_key, None)
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
    env["FOUNDRY_EXECUTION_PROFILE"] = execution["profile"]
    env["FOUNDRY_EXECUTOR_MODEL"] = execution["resolved_model_id"]
    env["FOUNDRY_MODEL_ALIAS_CLASS"] = execution["model_alias_class"]
    if execution["native_variant"]:
        env["FOUNDRY_NATIVE_VARIANT"] = execution["native_variant"]
    # WS75 state-path context, hardened by ROOT_STATE_SEMANTICS: the exact
    # explicit launcher state path is mandatory. There is no implicit active
    # repository-root state and no silent fallback, so the worker never guesses
    # `.foundry/WORKSTREAM_STATE.yaml`.
    # Values are paths/identities only — never secrets.
    if not state_path:
        raise ValueError("explicit --state is required (no implicit active state)")
    env["FOUNDRY_STATE_PATH"] = state_path
    env["FOUNDRY_WORKTREE"] = worktree
    env["FOUNDRY_RUN_DIR"] = run_dir
    env["FOUNDRY_MODE"] = mode
    public_refs = [
        {key: value for key, value in ref.items() if key != "source_root"} for ref in references
    ]
    public_access = [
        {key: value for key, value in spec.items() if key != "source_root"}
        for spec in workspace_access
    ]
    env["FOUNDRY_REFERENCE_ROOTS"] = json.dumps(public_refs, sort_keys=True)
    env["FOUNDRY_WORKSPACE_ACCESS"] = json.dumps(public_access, sort_keys=True)
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
    """Persist non-secret launch context for audit. Returns path."""
    path = Path(run_dir) / "launch-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


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
    workspace_access: list[str] | None = None,
    opencode_bin: str | None = None,
    version_audit_mode: bool = False,
    worktree_states: list[str] | None = None,
    execution_provider: str | None = None,
    execution_profile: str | None = None,
    model_catalog: list[str] | None = None,
) -> dict:
    """Validate + prepare. Returns the launch plan (never execs)."""
    effective_catalog = model_catalog
    catalog_source: str | None = None
    active_profile = execution_profile or DEFAULT_EXECUTION_PROFILE
    if effective_catalog is None and active_profile == SPACE_BUNNY_PROFILE:
        # Space Bunny resolution must inspect the live pinned-CLI catalog
        # before selection. Load it once here and pass the exact snapshot to
        # every internal resolver call so no second, possibly different,
        # inspection can occur.
        try:
            live_models, catalog_source = executor_mod.load_live_catalog(opencode_bin)
            effective_catalog = list(live_models)
        except executor_mod.ExecutorResolutionError as exc:
            return {"verdict": "LAUNCH_REFUSED", "error": str(exc)}
    try:
        execution = execution_identity(
            execution_provider,
            effort,
            execution_profile,
            catalog=effective_catalog,
            catalog_source=catalog_source,
        )
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
    seen_labels: set[str] = set()
    seen_reference_roots: set[str] = set()
    for raw in references or []:
        try:
            ref = reference_mod.parse_spec(raw)
        except reference_mod.ReferenceError as exc:
            return {"verdict": "LAUNCH_REFUSED", "error": f"reference: {exc}"}
        root = os.path.realpath(os.path.abspath(ref["root"]))
        if ref["label"] in seen_labels:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"duplicate declared workspace label {ref['label']!r}",
            }
        if root in seen_reference_roots:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"duplicate --reference root {root!r}",
            }
        fetch_error = workspace_access_mod.exact_fetch_identity_error(root, ref["repo_slug"])
        if fetch_error is not None:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"reference {ref['label']!r}: exact fetch identity rejected ({fetch_error})",
            }
        seen_labels.add(ref["label"])
        seen_reference_roots.add(root)
        parsed_refs.append(ref)
    parsed_access: list[dict] = []
    seen_access_roots: set[str] = set()
    for raw in workspace_access or []:
        try:
            spec = workspace_access_mod.parse_spec(raw)
        except workspace_access_mod.WorkspaceAccessError as exc:
            return {"verdict": "LAUNCH_REFUSED", "error": f"workspace-access: {exc}"}
        root = os.path.realpath(spec["root"])
        if root == canonical:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": "workspace-access must not redeclare the primary worktree",
            }
        if spec["label"] in seen_labels:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"duplicate declared workspace label {spec['label']!r}",
            }
        if root in seen_reference_roots:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": (
                    f"workspace root {root!r} cannot be both --reference and --workspace-access"
                ),
            }
        if root in seen_access_roots:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"duplicate --workspace-access root {root!r}",
            }
        seen_access_roots.add(root)
        seen_labels.add(spec["label"])
        reasons = workspace_access_mod.verify(spec)
        if reasons:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"workspace-access {spec['label']!r}: {reasons[0]}",
            }
        if spec["access"] == "owned-write" and spec["ownership"] != workstream:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": (
                    f"workspace-access {spec['label']!r}: owned-write ownership "
                    f"{spec['ownership']!r} != current workstream {workstream!r}"
                ),
            }
        parsed_access.append(spec)
    topology_error = _validate_cross_ws_topology(
        canonical,
        state_path,
        parsed_refs,
        parsed_access,
        run_dir,
    )
    if topology_error is not None:
        return {"verdict": "LAUNCH_REFUSED", "error": topology_error}
    effective_run_dir = (
        _reserve_run_dir(run_dir, workstream) if parsed_refs or parsed_access else run_dir
    )
    Path(effective_run_dir).mkdir(parents=True, exist_ok=True)
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
    for spec in parsed_access:
        if spec["access"] != "owned-write":
            continue
        root = os.path.realpath(spec["root"])
        other_state = spec["state_path"]
        if root in state_map and state_map[root] != other_state:
            return {
                "verdict": "LAUNCH_REFUSED",
                "error": f"owned-write state conflicts with --worktree-state for {root!r}",
            }
        state_map[root] = other_state
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
    try:
        runtime_refs, runtime_access = materialize_runtime_references(
            parsed_refs, parsed_access, effective_run_dir
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return {"verdict": "LAUNCH_REFUSED", "gate": gate, "error": f"snapshot: {exc}"}
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
            run_dir=effective_run_dir,
            state_path=resolved_state,
            mode=mode,
            references=runtime_refs,
            workspace_access=runtime_access,
            opencode_binary=binary,
            execution_provider=execution_provider,
            execution_profile=execution_profile,
            catalog=effective_catalog,
            catalog_source=catalog_source,
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
    public_refs = [
        {key: value for key, value in ref.items() if key != "source_root"} for ref in runtime_refs
    ]
    public_access = [
        {key: value for key, value in spec.items() if key != "source_root"}
        for spec in runtime_access
    ]
    context = {
        "execution": execution,
        "workstream": workstream,
        "branch": branch,
        "worktree": canonical,
        "state_path": resolved_state,
        "run_dir": effective_run_dir,
        "mode": mode,
        "ui_mode": ui_mode,
        "effort": effort,
        "session": session,
        "opencode_binary": binary,
        "opencode_version": version,
        "version_audit_mode": version_audit_mode,
        "canonical_policy_hash": env["FOUNDRY_CANONICAL_POLICY_HASH"],
        "config_dir_manifest": env["FOUNDRY_CONFIG_DIR_MANIFEST"],
        "references": public_refs,
        "workspace_access": public_access,
        "worktree_states": state_map,
        "live_head": live_head,
    }
    try:
        context_path = write_launch_context(effective_run_dir, context)
    except OSError as exc:
        return {"verdict": "LAUNCH_REFUSED", "gate": gate, "error": f"context: {exc}"}
    notes = []
    if version_note:
        notes.append(version_note)
    return {
        "verdict": "LAUNCH_READY",
        "execution": execution,
        "gate": gate,
        "env_keys": sorted(k for k in env if k.startswith(("OPENCODE_", "FOUNDRY_"))),
        "canonical_policy_hash": env["FOUNDRY_CANONICAL_POLICY_HASH"],
        "config_dir_manifest": env["FOUNDRY_CONFIG_DIR_MANIFEST"],
        "hook_path": hook_path,
        "mode": mode,
        "ui_mode": ui_mode,
        "session": session,
        "live_head": live_head,
        "run_dir": effective_run_dir,
        "state_path": resolved_state,
        "worktree_states": state_map,
        "references": public_refs,
        "workspace_access": public_access,
        "opencode_binary": binary,
        "opencode_version": version,
        "version_audit_mode": version_audit_mode,
        "context_path": context_path,
        "notes": notes,
        "_env": env,
    }


def _revalidate_locked_surfaces(
    plan: dict, worktree: str, workstream: str, env: dict
) -> str | None:
    """Recheck exact writable identities and foreign-process occupancy under locks."""
    try:
        live_branch = _git(["branch", "--show-current"], worktree)
        live_head = _git(["rev-parse", "HEAD"], worktree)
    except RuntimeError:
        return "primary worktree identity unreadable after writer lock acquisition"
    if live_branch != env.get("FOUNDRY_BRANCH", ""):
        return (
            f"primary branch changed after init: {live_branch!r} != "
            f"{env.get('FOUNDRY_BRANCH', '')!r}"
        )
    if live_head != plan.get("live_head"):
        return (
            f"primary HEAD changed after init: {live_head[:12]} != "
            f"{str(plan.get('live_head'))[:12]}"
        )

    for spec in plan.get("workspace_access", []):
        if spec.get("access") != "owned-write":
            continue
        if spec.get("ownership") != workstream:
            return (
                f"owned-write surface {spec.get('label')!r} ownership "
                f"{spec.get('ownership')!r} != current workstream {workstream!r}"
            )
        procs = writer_lock_mod.scan_cwd_processes(spec["root"])
        if procs:
            return (
                f"owned-write surface {spec.get('label')!r} has foreign/unknown "
                f"same-CWD OpenCode occupancy; refusing competing writer"
            )
        reasons = workspace_access_mod.verify(spec)
        if reasons:
            return f"owned-write surface {spec.get('label')!r} changed after init: {reasons[0]}"
    return None


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
        execution = plan.get("execution") or execution_identity(None, effort)
        if effort not in ALLOWED_EFFORTS or execution["requested_effort"] != effort:
            raise ValueError("launch effort differs from validated plan")
    except ValueError as exc:
        print(f"LAUNCH_REFUSED: {exc}", file=sys.stderr)
        return 1
    mode = ui_mode or plan.get("ui_mode", "headless")
    env: dict = plan["_env"]
    lock_specs = [
        {
            "root": os.path.realpath(worktree),
            "workstream": workstream,
            "branch": env.get("FOUNDRY_BRANCH", ""),
        }
    ]
    for spec in plan.get("workspace_access", []):
        if spec.get("access") == "owned-write":
            lock_specs.append(
                {
                    "root": os.path.realpath(spec["root"]),
                    "workstream": spec["ownership"],
                    "branch": spec["branch"],
                }
            )
    locks: list[writer_lock_mod.WriterLock] = []
    for spec in sorted(lock_specs, key=lambda item: item["root"]):
        lock = writer_lock_mod.WriterLock(
            spec["root"],
            spec["workstream"],
            spec["branch"],
            env.get("FOUNDRY_SESSION", ""),
        )
        try:
            lock.acquire()
        except writer_lock_mod.LockedError as exc:
            for held in reversed(locks):
                held.release()
            print(str(exc), file=sys.stderr)
            return writer_lock_mod.HELD_EXIT
        locks.append(lock)
    try:
        stale = _revalidate_locked_surfaces(plan, worktree, workstream, env)
        if stale is not None:
            print(f"LAUNCH_REFUSED: {stale}", file=sys.stderr)
            return 1
        return _launch_locked(plan, argv_extra, worktree, workstream, effort, mode, execution)
    finally:
        for lock in reversed(locks):
            lock.release()


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
        "model": "AUTOCAPTURED",
        "reasoning_effort": "AUTOCAPTURED",
        "source_sha": "AUTOCAPTURED",
        "started_utc": "AUTOCAPTURED",
        "execution_provider": "AUTOCAPTURED",
        "execution_override": "AUTOCAPTURED",
        "execution_profile": "AUTOCAPTURED",
        "logical_executor_profile": "AUTOCAPTURED",
        "resolved_provider": "AUTOCAPTURED",
        "resolved_model_id": "AUTOCAPTURED",
        "model_alias_class": "AUTOCAPTURED",
        "variant_resolution": "AUTOCAPTURED",
    }
    if execution["native_variant"] is not None:
        auto["native_variant"] = "AUTOCAPTURED"
    try:
        metrics_mod.record(
            metrics_path,
            _provenance=auto,
            task_id=workstream,
            task_class="workstream-session",
            repo_profile=plan.get("gate", {}).get("profile", "UNKNOWN"),
            model=execution["model"],
            execution_provider=execution["provider"],
            execution_override=execution["override"],
            execution_profile=execution["profile"],
            logical_executor_profile=execution["logical_executor_profile"],
            resolved_provider=execution["resolved_provider"],
            resolved_model_id=execution["resolved_model_id"],
            model_alias_class=execution["model_alias_class"],
            native_variant=execution["native_variant"],
            variant_resolution=execution["variant_resolution"],
            reasoning_effort=effort,
            source_sha=plan.get("live_head"),
            started_utc=start_utc,
        )
    except OSError as exc:
        print(f"LAUNCH_WARN: telemetry start not recorded: {exc}", file=sys.stderr)
    binary = plan.get("opencode_binary") or env.get(OPENCODE_BIN_ENV, "opencode")
    try:
        # CLI model selection outranks persisted session/model history, so every
        # profile is pinned explicitly on the child argv. An earlier "canonical"
        # sentinel skipped this for the committed default, which relied on the
        # child inheriting the right model; pinning instead makes a silent
        # fallback to another executor impossible. Caller model flags are refused.
        selected = ["--model", execution["model"]]
        argv = build_argv(binary, mode, [*selected, *argv_extra])
        argv = _sandbox_command(plan, argv, worktree, run_dir)
        if plan.get("references") or plan.get("workspace_access"):
            tmp_dir = Path(run_dir) / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            env["TMPDIR"] = str(tmp_dir)
            env["FOUNDRY_FS_SANDBOX"] = "bubblewrap-readonly-root"
    except (OSError, RuntimeError, ValueError) as exc:
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
                },
                task_id=workstream,
                task_class="workstream-session",
                repo_profile=plan.get("gate", {}).get("profile", "UNKNOWN"),
                model=execution["model"],
                execution_provider=execution["provider"],
                execution_override=execution["override"],
                execution_profile=execution["profile"],
                logical_executor_profile=execution["logical_executor_profile"],
                resolved_provider=execution["resolved_provider"],
                resolved_model_id=execution["resolved_model_id"],
                model_alias_class=execution["model_alias_class"],
                native_variant=execution["native_variant"],
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
        "--execution-profile",
        choices=ACTIVE_EXECUTION_PROFILES,
        default=None,
        help=(
            "Explicit OpenCode Go executor profile. Omitted selects the Space Bunny MAX "
            "default, the only ACTIVE profile; 'deepseek' is SUSPENDED (Owner directive "
            "2026-10-10) and refused. Any other execution profile is unauthorized."
        ),
    )
    parser.add_argument(
        "--execution-provider",
        choices=("zen",),
        default=None,
        help=(
            "Retired legacy provider override; always refused. Kept as an "
            "explicit refusal so it cannot be silently forwarded to the child argv."
        ),
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
        help="headless execs `opencode run --auto ...`; tui execs `opencode --auto ...`.",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Declared read-only reference root as JSON (repeatable).",
    )
    parser.add_argument(
        "--workspace-access",
        action="append",
        default=[],
        help=(
            "Verified project surface as JSON (repeatable): access=read-only or "
            "owned-write; writable surfaces require branch/state_path/ownership."
        ),
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
    args, extra = parser.parse_known_args(argv)
    if args.command == "launch" and args.mode == "reader":
        print("LAUNCH_REFUSED: reader mode is audit-only (use init)", file=sys.stderr)
        return 1
    run_dir = args.run_dir or f"/tmp/foundry-launch-{args.workstream}"
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
        workspace_access=args.workspace_access,
        opencode_bin=args.opencode_bin,
        version_audit_mode=args.version_audit_mode,
        worktree_states=args.worktree_state,
        execution_provider=args.execution_provider,
        execution_profile=args.execution_profile,
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
