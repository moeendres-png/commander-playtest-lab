"""Canonical OpenCode executor-profile resolution (exactly two logical profiles).

Single source of truth: ``.foundry/executor-profiles.json``. The code never
invents a model identity and never falls back across executor families.

Logical profiles
----------------

- ``space-bunny``: the default and only ACTIVE executor (Owner directive
  2026-10-10), resolved only after live catalog inspection of the pinned
  OpenCode CLI (``opencode models opencode-go``).
- ``deepseek``: ``opencode-go/deepseek-v4.1-flash`` at native ``max``; kept in
  the registry with ``runtime_status: SUSPENDED`` (its OpenCode Go monthly
  quota is exhausted). A suspended profile never resolves; only a new direct
  Owner instruction flips it back to ACTIVE.

Space Bunny runtime preference is deterministic:

1. ``opencode-go/space-bunny`` = CANONICAL;
2. else ``opencode-go/space-bunny-free`` = LEGACY_ALIAS (the same logical
   profile, admitted only as a runtime identity);
3. neither present => explicit fail-closed resolution error.

No other provider/model (Longcat, DeepSeek, another family, or the first
available catalog row) may ever substitute. A runtime/auth/quota/API/tool
failure AFTER selection is a failed/blocked Space Bunny run: the pin can only
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
CANONICAL_ALIAS_CLASS = "CANONICAL"
LEGACY_ALIAS_CLASS = "LEGACY_ALIAS"
ALIAS_CLASSES = (CANONICAL_ALIAS_CLASS, LEGACY_ALIAS_CLASS)
NATIVE_VARIANT = "max"
ACTIVE = "ACTIVE"
SUSPENDED = "SUSPENDED"
RUNTIME_STATUSES = (ACTIVE, SUSPENDED)
CATALOG_COMMAND = ("opencode", "models", "opencode-go")
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
    if set(profiles) != {"deepseek", "space-bunny"}:
        errors.append(f"registry must expose exactly deepseek+space-bunny, got {sorted(profiles)}")
    for name, spec in profiles.items():
        status = spec.get("runtime_status") if isinstance(spec, dict) else None
        if status not in RUNTIME_STATUSES:
            errors.append(
                f"profiles[{name!r}] runtime_status {status!r} not in {list(RUNTIME_STATUSES)}"
            )
    default = str(doc.get("current_runtime_default", ""))
    if default != "space-bunny":
        errors.append(f"registry default must be space-bunny, got {default!r}")
    bunny_spec = profiles.get("space-bunny")
    if isinstance(bunny_spec, dict) and bunny_spec.get("runtime_status") != ACTIVE:
        errors.append("the space-bunny default profile must be ACTIVE")
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
        if provider != CANONICAL_PROVIDER:
            errors.append(
                f"runtime_identity[{runtime_id!r}] provider is not {CANONICAL_PROVIDER!r}"
            )
    for name, spec in profiles.items():
        if not isinstance(spec, dict):
            errors.append(f"profiles[{name!r}] must be a mapping")
            continue
        model = str(spec.get("model", ""))
        if spec.get("native_variant") != NATIVE_VARIANT:
            errors.append(f"profiles[{name!r}] native_variant must be {NATIVE_VARIANT!r}")
        entry = identity.get(model)
        if not isinstance(entry, dict) or entry.get("logical_profile") != name:
            errors.append(f"profiles[{name!r}] canonical model {model!r} is not admitted to it")
        elif entry.get("alias_class") != CANONICAL_ALIAS_CLASS:
            errors.append(f"profiles[{name!r}] canonical model must be CANONICAL alias class")
    bunny = profiles.get("space-bunny")
    if isinstance(bunny, dict):
        model = str(bunny.get("model", ""))
        legacy = [
            runtime_id
            for runtime_id, spec in identity.items()
            if isinstance(spec, dict)
            and spec.get("logical_profile") == "space-bunny"
            and spec.get("alias_class") == LEGACY_ALIAS_CLASS
        ]
        if model != "opencode-go/space-bunny":
            errors.append("space-bunny canonical runtime id must be opencode-go/space-bunny")
        if legacy != ["opencode-go/space-bunny-free"]:
            errors.append(
                "space-bunny must admit exactly the legacy alias "
                f"opencode-go/space-bunny-free, got {legacy!r}"
            )
    deepseek = profiles.get("deepseek")
    if isinstance(deepseek, dict) and str(deepseek.get("model", "")) != (
        "opencode-go/deepseek-v4.1-flash"
    ):
        errors.append("deepseek runtime id must remain opencode-go/deepseek-v4.1-flash")
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
) -> tuple[tuple[str, ...], str]:
    """Inspect the pinned CLI catalog. Returns (model_ids, catalog_source).

    Any launch/catalog failure raises ``ExecutorResolutionError``: an
    uninspectable catalog can never be replaced by a guessed or historical id.
    """
    binary = opencode_bin or os.environ.get(OPENCODE_BIN_ENV, CATALOG_COMMAND[0])
    command = [binary, "models", CANONICAL_PROVIDER]
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
    models = parse_catalog_output(proc.stdout or "")
    if not models:
        raise ExecutorResolutionError("live catalog listed no opencode-go models; fail closed")
    return models, f"cli:{CANONICAL_PROVIDER}"


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
    presence is still verified. Space Bunny requires catalog inspection and
    selects the canonical id, else the admitted legacy alias, else fails closed.
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
            "(Owner directive 2026-10-10: Space Bunny MAX only); fail closed, no fallback"
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
    elif logical_profile == "space-bunny":
        listed, source = load_live_catalog(opencode_bin)
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
                "space-bunny requires live catalog inspection before selection; fail closed"
            )
        present = [item for item in spec.admitted if item.runtime_id in listed]
        if not present:
            admitted = ", ".join(spec.admitted_runtime_ids)
            raise ExecutorResolutionError(
                f"no admitted space-bunny runtime id present in the inspected catalog "
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
