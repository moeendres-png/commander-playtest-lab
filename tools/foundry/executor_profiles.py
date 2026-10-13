"""Canonical OpenCode executor-profile resolution (exactly two logical profiles).

Single source of truth: ``.foundry/executor-profiles.json``. The code never
invents a model identity and never falls back across executor families.

Logical profiles
----------------

- ``deepseek``: the default and only ACTIVE executor (Owner directive
  2026-10-13), served by OpenCode Go as ``opencode-go/deepseek-v4.1-flash`` at
  its native variant ``max``. When a catalog is inspected it is the pinned CLI
  catalog of the Go provider (``opencode models opencode-go``).
- ``step``: ``opencode/step-5-preview-free`` on OpenCode Zen at native
  ``high``; kept in the registry with ``runtime_status: SUSPENDED`` (Owner
  directive 2026-10-13). A suspended profile never resolves; only a new direct
  Owner instruction flips it back to ACTIVE, after which it resolves only
  after live catalog inspection of the Zen provider (``opencode models opencode``).

DeepSeek runtime selection pins the canonical Go id; if a catalog is supplied
or inspected, the id must be listed, else resolution fails closed.

No other provider/model (another family, a retired id, or the first available
catalog row) may ever substitute. A runtime/auth/quota/API/tool failure AFTER
selection is a failed/blocked run of the selected profile: the pin can only
report BLOCKED. Re-resolution is an explicit task-rerouting decision outside
this module.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / ".foundry" / "executor-profiles.json"

CANONICAL_PROVIDER = "opencode-go"
ZEN_PROVIDER = "opencode"
# Providers a registry runtime id may name: Go (active DeepSeek) and Zen (the
# suspended Step record only).
ADMITTED_PROVIDERS = (CANONICAL_PROVIDER, ZEN_PROVIDER)
STEP_RUNTIME_ID = "opencode/step-5-preview-free"
DEEPSEEK_RUNTIME_ID = "opencode-go/deepseek-v4.1-flash"
LOGICAL_PROFILES = ("deepseek", "step")
DEFAULT_PROFILE = "deepseek"
# Profiles served by OpenCode Zen: resolution needs live catalog inspection.
ZEN_PROFILES = ("step",)
CANONICAL_RUNTIME_IDS = {
    "deepseek": DEEPSEEK_RUNTIME_ID,
    "step": STEP_RUNTIME_ID,
}
# Each profile's single highest native variant as listed by its provider
# catalog. DeepSeek lists max; Step 5 Preview lists low/medium/high only, so
# `high` is its highest.
NATIVE_VARIANTS = {"deepseek": "max", "step": "high"}
CANONICAL_ALIAS_CLASS = "CANONICAL"
LEGACY_ALIAS_CLASS = "LEGACY_ALIAS"
ALIAS_CLASSES = (CANONICAL_ALIAS_CLASS, LEGACY_ALIAS_CLASS)
ACTIVE = "ACTIVE"
SUSPENDED = "SUSPENDED"
RUNTIME_STATUSES = (ACTIVE, SUSPENDED)
CATALOG_COMMAND = ("opencode", "models", CANONICAL_PROVIDER)
ZEN_CATALOG_COMMAND = ("opencode", "models", ZEN_PROVIDER)
CATALOG_TIMEOUT_SECONDS = 60
OPENCODE_BIN_ENV = "FOUNDRY_OPENCODE_BIN"


class ExecutorResolutionError(ValueError):
    """Fail-closed executor resolution refusal (no fallback is attempted)."""


@dataclass(frozen=True)
class AdmittedRuntime:
    """One runtime model ID admitted for exactly one logical profile."""

    runtime_id: str
    logical_profile: str
    alias_class: str


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    canonical_runtime_id: str
    native_variant: str
    role: str
    admitted: tuple[AdmittedRuntime, ...]
    runtime_status: str = ACTIVE

    @property
    def active(self) -> bool:
        return self.runtime_status == ACTIVE

    @property
    def admitted_runtime_ids(self) -> tuple[str, ...]:
        return tuple(item.runtime_id for item in self.admitted)

    @property
    def legacy_aliases(self) -> tuple[str, ...]:
        return tuple(
            item.runtime_id for item in self.admitted if item.alias_class == LEGACY_ALIAS_CLASS
        )


@dataclass(frozen=True)
class ExecutorRegistry:
    path: str
    schema_version: str
    provider: str
    default_profile: str
    profiles: dict[str, ProfileSpec]
    runtime_identity: dict[str, AdmittedRuntime]
    review_policy: dict
    resolution_policy: dict

    @property
    def logical_profiles(self) -> tuple[str, ...]:
        return tuple(self.profiles)

    @property
    def active_profiles(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.profiles.items() if spec.active)

    @property
    def active_runtime_ids(self) -> tuple[str, ...]:
        """Admitted runtime ids of ACTIVE profiles only, in registry order."""
        return tuple(
            runtime_id
            for runtime_id, item in self.runtime_identity.items()
            if self.profiles[item.logical_profile].active
        )

    def admitted_for(self, logical_profile: str) -> tuple[AdmittedRuntime, ...]:
        return self.profiles[logical_profile].admitted

    def admitted_runtime(self, runtime_id: str) -> AdmittedRuntime | None:
        return self.runtime_identity.get(runtime_id)


@dataclass(frozen=True)
class ResolvedExecutor:
    """One selected, pinned executor. Exact provenance, no inference."""

    logical_executor_profile: str
    resolved_provider: str
    resolved_model_id: str
    model_alias_class: str
    native_variant: str
    catalog_checked: bool
    catalog_source: str

    def to_provenance(self) -> dict:
        return {
            "logical_executor_profile": self.logical_executor_profile,
            "resolved_provider": self.resolved_provider,
            "resolved_model_id": self.resolved_model_id,
            "model_alias_class": self.model_alias_class,
            "native_variant": self.native_variant,
            "catalog_checked": self.catalog_checked,
            "catalog_source": self.catalog_source,
        }


@dataclass(frozen=True)
class ExecutorOutcome:
    """Terminal outcome for a selected executor (never a new executor)."""

    verdict: str
    executor: ResolvedExecutor
    failure_class: str
    detail: str = ""
    fallback_attempted: bool = False


@dataclass(frozen=True)
class ExecutorPin:
    """A resolved executor that can only fail closed after selection."""

    executor: ResolvedExecutor
    _reresolve: Callable[[], ResolvedExecutor] | None = field(default=None, repr=False)

    def on_failure(self, failure_class: str, detail: str = "") -> ExecutorOutcome:
        """Record a post-selection failure; never resolve another executor."""
        return ExecutorOutcome(
            verdict="BLOCKED",
            executor=self.executor,
            failure_class=failure_class,
            detail=detail,
            fallback_attempted=False,
        )


def _split_provider(runtime_id: str) -> tuple[str, str]:
    if "/" not in runtime_id or runtime_id.startswith("/") or runtime_id.endswith("/"):
        raise ExecutorResolutionError(f"runtime id {runtime_id!r} is not provider/model")
    provider, model = runtime_id.split("/", 1)
    return provider, model


def validate_registry(doc: dict, *, path: str = "<memory>") -> list[str]:
    """Validate the canonical registry: exactly two profiles, no third executor."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["registry must be a mapping"]
    if str(doc.get("provider", "")) != CANONICAL_PROVIDER:
        errors.append(f"registry provider must be {CANONICAL_PROVIDER!r}")
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict):
        return [*errors, "registry profiles must be a mapping"]
    if set(profiles) != set(LOGICAL_PROFILES):
        errors.append(
            f"registry must expose exactly {'+'.join(LOGICAL_PROFILES)}, got {sorted(profiles)}"
        )
    for name, spec in profiles.items():
        status = spec.get("runtime_status") if isinstance(spec, dict) else None
        if status not in RUNTIME_STATUSES:
            errors.append(
                f"profiles[{name!r}] runtime_status {status!r} not in {list(RUNTIME_STATUSES)}"
            )
    default = str(doc.get("current_runtime_default", ""))
    if default != DEFAULT_PROFILE:
        errors.append(f"registry default must be {DEFAULT_PROFILE}, got {default!r}")
    default_spec = profiles.get(DEFAULT_PROFILE)
    if isinstance(default_spec, dict) and default_spec.get("runtime_status") != ACTIVE:
        errors.append(f"the {DEFAULT_PROFILE} default profile must be ACTIVE")
    identity = doc.get("runtime_identity")
    if not isinstance(identity, dict) or not identity:
        errors.append("registry runtime_identity must be a non-empty mapping")
        identity = {}
    for runtime_id, spec in identity.items():
        if not isinstance(spec, dict):
            errors.append(f"runtime_identity[{runtime_id!r}] must be a mapping")
            continue
        profile_name = spec.get("logical_profile")
        alias_class = spec.get("alias_class")
        if profile_name not in profiles:
            errors.append(
                f"runtime_identity[{runtime_id!r}] names unknown logical profile "
                f"{profile_name!r} (no third executor is reachable)"
            )
        if alias_class not in ALIAS_CLASSES:
            errors.append(
                f"runtime_identity[{runtime_id!r}] alias_class {alias_class!r} "
                f"not in {sorted(ALIAS_CLASSES)}"
            )
        try:
            provider, _ = _split_provider(str(runtime_id))
        except ExecutorResolutionError as exc:
            errors.append(str(exc))
            continue
        if provider not in ADMITTED_PROVIDERS:
            errors.append(
                f"runtime_identity[{runtime_id!r}] provider is not one of {list(ADMITTED_PROVIDERS)}"
            )
        elif profile_name in ZEN_PROFILES and provider != ZEN_PROVIDER:
            errors.append(
                f"runtime_identity[{runtime_id!r}] {profile_name} runtime ids must use "
                f"{ZEN_PROVIDER!r} (Zen)"
            )
        elif (
            profile_name in LOGICAL_PROFILES
            and profile_name not in ZEN_PROFILES
            and (provider != CANONICAL_PROVIDER)
        ):
            errors.append(
                f"runtime_identity[{runtime_id!r}] {profile_name} runtime ids must use "
                f"{CANONICAL_PROVIDER!r} (Go)"
            )
    for name, spec in profiles.items():
        if not isinstance(spec, dict):
            errors.append(f"profiles[{name!r}] must be a mapping")
            continue
        model = str(spec.get("model", ""))
        want_variant = NATIVE_VARIANTS.get(name)
        if spec.get("native_variant") != want_variant:
            errors.append(f"profiles[{name!r}] native_variant must be {want_variant!r}")
        entry = identity.get(model)
        if not isinstance(entry, dict) or entry.get("logical_profile") != name:
            errors.append(f"profiles[{name!r}] canonical model {model!r} is not admitted to it")
        elif entry.get("alias_class") != CANONICAL_ALIAS_CLASS:
            errors.append(f"profiles[{name!r}] canonical model must be CANONICAL alias class")
    for zen_name in ZEN_PROFILES:
        zen = profiles.get(zen_name)
        if not isinstance(zen, dict):
            continue
        legacy = [
            runtime_id
            for runtime_id, spec in identity.items()
            if isinstance(spec, dict)
            and spec.get("logical_profile") == zen_name
            and spec.get("alias_class") == LEGACY_ALIAS_CLASS
        ]
        if legacy:
            errors.append(f"{zen_name} admits no legacy alias, got {legacy!r}")
    for name, want_id in CANONICAL_RUNTIME_IDS.items():
        spec = profiles.get(name)
        if isinstance(spec, dict) and str(spec.get("model", "")) != want_id:
            errors.append(f"{name} canonical runtime id must be {want_id}")
    return errors


def load_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> ExecutorRegistry:
    """Load and validate the canonical registry; any drift fails closed."""
    registry_path = Path(path)
    try:
        doc = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutorResolutionError(
            f"cannot read executor registry {registry_path}: {exc}"
        ) from exc
    errors = validate_registry(doc, path=str(registry_path))
    if errors:
        raise ExecutorResolutionError(f"executor registry invalid: {errors[0]}")
    identity: dict[str, AdmittedRuntime] = {}
    for runtime_id, spec in doc["runtime_identity"].items():
        identity[runtime_id] = AdmittedRuntime(
            runtime_id=runtime_id,
            logical_profile=spec["logical_profile"],
            alias_class=spec["alias_class"],
        )
    profiles: dict[str, ProfileSpec] = {}
    for name, spec in doc["profiles"].items():
        admitted = tuple(
            sorted(
                (item for item in identity.values() if item.logical_profile == name),
                key=lambda item: (
                    0 if item.alias_class == CANONICAL_ALIAS_CLASS else 1,
                    item.runtime_id,
                ),
            )
        )
        profiles[name] = ProfileSpec(
            name=name,
            canonical_runtime_id=str(spec["model"]),
            native_variant=str(spec["native_variant"]),
            role="PRIMARY" if name == doc["current_runtime_default"] else "SECONDARY",
            admitted=admitted,
            runtime_status=str(spec["runtime_status"]),
        )
    return ExecutorRegistry(
        path=str(registry_path),
        schema_version=str(doc.get("schema_version", "")),
        provider=str(doc["provider"]),
        default_profile=str(doc["current_runtime_default"]),
        profiles=profiles,
        runtime_identity=identity,
        review_policy=dict(doc.get("cross_executor_review_policy", {})),
        resolution_policy=dict(doc.get("resolution_policy", {})),
    )


def parse_catalog_output(stdout: str, provider: str = CANONICAL_PROVIDER) -> tuple[str, ...]:
    """Parse ``opencode models <provider>`` output into exact provider/model ids.

    One model per line; the first whitespace-delimited token is the identity.
    Rows from another provider, headers, blanks and malformed tokens are
    ignored (never guessed into a model id).
    """
    models: list[str] = []
    for line in stdout.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        if not token or "/" not in token:
            continue
        if not token.startswith(f"{provider}/"):
            continue
        models.append(token)
    return tuple(dict.fromkeys(models))


def load_live_catalog(
    opencode_bin: str | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
    provider: str = CANONICAL_PROVIDER,
) -> tuple[tuple[str, ...], str]:
    """Inspect the pinned CLI catalog of ``provider`` (default OpenCode Go).

    Returns (model_ids, catalog_source).

    Any launch/catalog failure raises ``ExecutorResolutionError``: an
    uninspectable catalog can never be replaced by a guessed or historical id.
    """
    binary = opencode_bin or os.environ.get(OPENCODE_BIN_ENV, CATALOG_COMMAND[0])
    command = [binary, "models", provider]
    run = runner or subprocess.run
    try:
        proc = run(
            command, capture_output=True, text=True, check=False, timeout=CATALOG_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutorResolutionError(
            f"live catalog inspection failed ({type(exc).__name__}); fail closed"
        ) from exc
    if proc.returncode != 0:
        raise ExecutorResolutionError(
            f"live catalog inspection failed (exit {proc.returncode}); fail closed"
        )
    models = parse_catalog_output(proc.stdout or "", provider)
    if not models:
        raise ExecutorResolutionError(f"live catalog listed no {provider} models; fail closed")
    return models, f"cli:{provider}"


def resolve_executor(
    logical_profile: str,
    *,
    registry: ExecutorRegistry | None = None,
    catalog: Iterable[str] | None = None,
    catalog_source: str | None = None,
    catalog_loader: Callable[[], tuple[tuple[str, ...], str]] | None = None,
    opencode_bin: str | None = None,
) -> ResolvedExecutor:
    """Resolve one logical profile to its exact pinned runtime identity.

    A SUSPENDED profile is refused before anything else. DeepSeek (when ACTIVE)
    uses the pinned canonical identity; when a catalog is supplied its
    presence is still verified. The Zen profile (Step, SUSPENDED since
    2026-10-13) would require catalog inspection and select its admitted Zen
    id, else fail closed.
    """
    reg = registry or load_registry()
    if logical_profile not in reg.profiles:
        raise ExecutorResolutionError(
            f"unknown execution profile {logical_profile!r} (known: {list(reg.logical_profiles)})"
        )
    spec = reg.profiles[logical_profile]
    if not spec.active:
        raise ExecutorResolutionError(
            f"execution profile {logical_profile!r} is {spec.runtime_status} "
            "(Owner directive 2026-10-13: DeepSeek V4.1 Flash on OpenCode Go is the only active "
            "OpenCode executor); fail closed, no fallback"
        )
    catalog_checked = False
    source = "not_inspected"
    listed: tuple[str, ...] | None = None
    if catalog is not None:
        listed = tuple(str(item) for item in catalog)
        catalog_checked = True
        source = catalog_source or "provided"
    elif catalog_loader is not None:
        listed, source = catalog_loader()
        catalog_checked = True
    elif logical_profile in ZEN_PROFILES:
        listed, source = load_live_catalog(opencode_bin, provider=ZEN_PROVIDER)
        catalog_checked = True

    if logical_profile == "deepseek":
        chosen = reg.runtime_identity.get(spec.canonical_runtime_id)
        if chosen is None:  # pragma: no cover - registry validation prevents this
            raise ExecutorResolutionError("deepseek canonical runtime id is not admitted")
        if listed is not None and chosen.runtime_id not in listed:
            raise ExecutorResolutionError(
                f"canonical {chosen.runtime_id!r} is absent from the inspected catalog; "
                "fail closed (no fallback)"
            )
    else:
        if listed is None:
            raise ExecutorResolutionError(
                f"{logical_profile} requires live catalog inspection before selection; fail closed"
            )
        present = [item for item in spec.admitted if item.runtime_id in listed]
        if not present:
            admitted = ", ".join(spec.admitted_runtime_ids)
            raise ExecutorResolutionError(
                f"no admitted {logical_profile} runtime id present in the inspected catalog "
                f"(admitted: {admitted}); fail closed (no cross-family substitute)"
            )
        chosen = present[0]

    provider, _model = _split_provider(chosen.runtime_id)
    return ResolvedExecutor(
        logical_executor_profile=logical_profile,
        resolved_provider=provider,
        resolved_model_id=chosen.runtime_id,
        model_alias_class=chosen.alias_class,
        native_variant=spec.native_variant,
        catalog_checked=catalog_checked,
        catalog_source=source,
    )
