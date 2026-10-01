"""AF09 clean-process semantic replay twins (candidate-neutral contract).

The AF09 obligation family (``REPLAY_CLEAN_PROCESS``, ``REPLAY_DECISION_TAPE``,
``REPLAY_EVENT_TAPE``, ``REPLAY_STATE_HASHES``, ``RNG_RULES_TAPE``) requires a
fresh-process semantic replay *twin*: two genuinely separate OS processes whose
externally supplied decisions, Rules RNG binding, semantic events, checkpoint
state hashes and terminal outcome are compared semantically. A seed
acknowledgement, an identical setup, or a refused ``export_replay`` is an honest
non-PASS, never replay proof.

This module owns the twin contract. It does not own Rules semantics: every
semantic fact it persists is an engine-published observation (a native decision
frame, an engine-published semantic fingerprint/digest, an engine event or an
engine terminal payload) or a digest over exactly those fields. It never
computes legality, never fabricates an option and never substitutes a choice for
the engine.

Contract shape
--------------

Each twin process produces a :class:`TwinRun` with the required sections:

``fixture_identity``
    The exact fixture (id, candidate, player count, seed, deck hashes, lane).
``candidate_build``
    The candidate/build the process actually executed (provider version
    payload, observed artifact digest, launch-plan build identity).
``lab_source``
    The exact Lab source identity of the producing checkout (commit/tree).
``process``
    The engine process identity (pid, pid start ticks, boot id, argv digest).
``rules_rng``
    Requested seed, provider acknowledgement, classification and the per-step
    Rules-RNG call coordinates when the provider exposes them.
``decisions``
    The externally supplied decision tape: one semantic entry per answered
    decision, identified by the provider's own semantic option identity.
``semantic_events``
    The ordered semantic event tape: one digest per answered decision over the
    engine-published transition coordinates.
``checkpoint_state_hashes``
    The defined checkpoint chain: engine-published state digests and engine
    coordinates before and after every answered decision.
``terminal``
    The engine's terminal facts/outcome, or an explicit bounded-horizon fact
    (which is not a PASS).

:func:`compare_twin_runs` compares two runs semantically and returns typed
divergences. Only process-local identifiers may ever be normalized, and only
through :class:`NormalizationRule` with an allow-listed path and a declared
justification; any attempt to normalize a Rules-significant field fails closed.
:func:`run_adversarial_controls` proves the checker detects every mandatory
adversarial mutation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import receipts as receipt_mod
from .bridge_launcher import BridgeLaunchError, build_launch_plan, launch
from .game_driver import (
    DecisionUnsatisfied,
    GameDriveError,
    _acknowledged_seed,
    _create_request,
    _declares_seed_support,
    _payload,
    _require_ok,
    build_deck,
    decision_identity_params,
    poll_decision,
    select_cost_order_action,
    self_choice_pass,
)
from .source_lock import repo_root

SCHEMA_VERSION = "commander-lab.af09-replay-twin/1.0.0"
EVIDENCE_CLASS = "CLEAN_PROCESS_SEMANTIC_REPLAY_TWIN"

# The exact elements the AF09 gate derivation requires to be present and
# non-empty on a `clean_process_twin` document.
REQUIRED_TWIN_SECTIONS: tuple[str, ...] = (
    "fixture_identity",
    "process_identity",
    "decisions",
    "rules_rng",
    "semantic_events",
    "checkpoint_state_hashes",
    "terminal_outcome",
)

# How many tape entries are embedded verbatim in the compact evidence document.
# The full sequences are always compared; only the *embedding* is bounded so a
# multi-thousand-decision twin does not bloat the current-boundary artifact.
MAX_EMBEDDED_ENTRIES = 96

_GENERIC_SUPPORTED_KINDS = frozenset(
    {
        "MULLIGAN",
        "KEEP_OR_MULLIGAN",
        "STARTING_PLAYER",
        "CHOOSE_STARTING_PLAYER",
        "ORDER_CHOICE",
        "PRIORITY",
    }
)

# --------------------------------------------------------------------------- #
# Divergence vocabulary. These names are the comparison's public contract.
# --------------------------------------------------------------------------- #

DIVERGENCE_FIXTURE = "FIXTURE_DIVERGENCE"
DIVERGENCE_BUILD = "BUILD_DIVERGENCE"
DIVERGENCE_LAB_SOURCE = "LAB_SOURCE_DIVERGENCE"
DIVERGENCE_PROCESS_MISSING = "PROCESS_IDENTITY_MISSING"
DIVERGENCE_PROCESS_NOT_DISTINCT = "PROCESS_IDENTITY_NOT_DISTINCT"
DIVERGENCE_RNG = "RNG_DIVERGENCE"
DIVERGENCE_DECISION = "DECISION_DIVERGENCE"
DIVERGENCE_EVENT_MISSING = "EVENT_MISSING"
DIVERGENCE_EVENT_REORDERED = "EVENT_REORDERED"
DIVERGENCE_EVENT = "EVENT_DIVERGENCE"
DIVERGENCE_STATE = "STATE_DIVERGENCE"
DIVERGENCE_TERMINAL = "TERMINAL_DIVERGENCE"
DIVERGENCE_TERMINAL_INCOMPLETE = "TERMINAL_INCOMPLETE"
DIVERGENCE_SECTION_MISSING = "REQUIRED_SECTION_MISSING"
DIVERGENCE_NOT_EXECUTED = "TWIN_NOT_EXECUTED"


class ReplayTwinError(RuntimeError):
    """A twin could not be produced or verified as required."""


class TwinChannelUnavailable(ReplayTwinError):
    """The provider/lane cannot expose a required twin evidence channel.

    The exact channel and the exact missing evidence route are carried so the
    caller can persist a terminal UNKNOWN with a specific blocker instead of an
    invented workaround.
    """

    def __init__(self, channel: str, detail: str, *, evidence_channel: str) -> None:
        super().__init__(f"{channel} unavailable: {detail}")
        self.channel = channel
        self.detail = detail
        self.evidence_channel = evidence_channel

    def to_document(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "detail": self.detail,
            "evidence_channel": self.evidence_channel,
        }


class TwinReplayDivergence(ReplayTwinError):
    """A replay process could not reproduce the externally supplied tape."""


class NormalizationContractError(ReplayTwinError):
    """A requested normalization is not allowed by the contract."""


class TwinTerminalUnavailable(ReplayTwinError):
    """The run ended without a complete terminal fact."""


# --------------------------------------------------------------------------- #
# Canonicalization helpers
# --------------------------------------------------------------------------- #


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Process identity
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProcessIdentity:
    """One engine OS process identity, observed rather than asserted.

    ``start_ticks`` is field 22 of ``/proc/<pid>/stat`` (process start time in
    clock ticks). Together with ``boot_id`` it distinguishes a reused pid. A
    process whose identity could not be observed is represented with ``None``
    fields and can never satisfy the twin's distinctness requirement.
    """

    role: str
    pid: int | None
    start_ticks: int | None
    boot_id: str | None
    command_sha256: str
    command: tuple[str, ...]
    observation: str

    @property
    def observed(self) -> bool:
        return self.pid is not None and self.start_ticks is not None and bool(self.boot_id)

    @property
    def key(self) -> tuple[int, int, str] | None:
        if not self.observed:
            return None
        assert self.pid is not None and self.start_ticks is not None and self.boot_id is not None
        return (self.pid, self.start_ticks, self.boot_id)

    def to_document(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "pid": self.pid,
            "start_ticks": self.start_ticks,
            "boot_id": self.boot_id,
            "command_sha256": self.command_sha256,
            "command": list(self.command),
            "observation": self.observation,
            "observed": self.observed,
        }


def _parse_stat_start_ticks(text: str) -> int | None:
    """Field 22 of /proc/<pid>/stat, robust to spaces in the comm field."""
    close = text.rfind(")")
    if close < 0:
        return None
    fields = text[close + 1 :].split()
    # After the comm field, fields start at field 3 (state).
    index = 22 - 3
    if index >= len(fields):
        return None
    try:
        return int(fields[index])
    except ValueError:
        return None


def read_process_identity(
    pid: int,
    *,
    role: str,
    command: Sequence[str],
    proc_root: Path | None = None,
) -> ProcessIdentity:
    """Observe a live engine process identity from /proc; never invent one."""
    root = proc_root or Path("/proc")
    command_tuple = tuple(str(part) for part in command)
    command_digest = sha256_json(list(command_tuple))
    try:
        boot_id = (
            (root / "sys" / "kernel" / "random" / "boot_id").read_text(encoding="utf-8").strip()
        )
    except OSError:
        boot_id = None
    try:
        stat_text = (root / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        stat_text = ""
    start_ticks = _parse_stat_start_ticks(stat_text)
    return ProcessIdentity(
        role=role,
        pid=int(pid),
        start_ticks=start_ticks,
        boot_id=boot_id or None,
        command_sha256=command_digest,
        command=command_tuple,
        observation="/proc live observation",
    )


def read_pidfile_identity(
    pidfile: Path,
    *,
    role: str,
    command: Sequence[str],
) -> ProcessIdentity:
    """Read a wrapper-captured identity: ``pid start_ticks boot_id``.

    The wrapper writes this line immediately before ``exec``, so the recorded
    start ticks belong to the process that became the engine, and the file is
    still valid after the process has exited.
    """
    command_tuple = tuple(str(part) for part in command)
    command_digest = sha256_json(list(command_tuple))
    try:
        parts = pidfile.read_text(encoding="utf-8").split()
    except OSError as exc:
        return ProcessIdentity(
            role=role,
            pid=None,
            start_ticks=None,
            boot_id=None,
            command_sha256=command_digest,
            command=command_tuple,
            observation=f"pidfile unreadable: {exc}",
        )
    if len(parts) != 3:
        return ProcessIdentity(
            role=role,
            pid=None,
            start_ticks=None,
            boot_id=None,
            command_sha256=command_digest,
            command=command_tuple,
            observation=f"pidfile malformed: {parts!r}",
        )
    try:
        pid = int(parts[0])
        start_ticks = int(parts[1])
    except ValueError:
        return ProcessIdentity(
            role=role,
            pid=None,
            start_ticks=None,
            boot_id=None,
            command_sha256=command_digest,
            command=command_tuple,
            observation=f"pidfile non-numeric: {parts!r}",
        )
    return ProcessIdentity(
        role=role,
        pid=pid,
        start_ticks=start_ticks,
        boot_id=parts[2],
        command_sha256=command_digest,
        command=command_tuple,
        observation="wrapper-captured before exec",
    )


def process_identities_distinct(
    identities: Sequence[ProcessIdentity],
) -> tuple[bool, str]:
    """Two or more observed identities, all on the same boot, pairwise distinct."""
    if len(identities) < 2:
        return False, "fewer than two process identities were recorded"
    for identity in identities:
        if not identity.observed:
            return False, f"{identity.role}: process identity was not observed"
    boot_ids = {identity.boot_id for identity in identities}
    if len(boot_ids) != 1:
        return False, f"process identities come from different boots: {sorted(map(str, boot_ids))}"
    keys = [identity.key for identity in identities]
    if len(set(keys)) != len(keys):
        return False, "the same engine process identity was recorded for two phases"
    return True, "all recorded process identities are observed and pairwise distinct"


# --------------------------------------------------------------------------- #
# Normalization contract
# --------------------------------------------------------------------------- #

# The only document paths that may ever be normalized away. Every one of them is
# a process-local identifier or an incidental process artifact; none carries a
# Rules-visible observation.
PROCESS_LOCAL_PATHS: frozenset[str] = frozenset(
    {
        "fixture_identity.game_id",
        "fixture_identity.engine_game_id",
        "fixture_identity.session_id",
        "rules_rng.acknowledgement_session_id",
        "decisions.*.engine_game_id",
        "decisions.*.session_id",
        "semantic_events.*.engine_game_id",
        "semantic_events.*.session_id",
        "checkpoint_state_hashes.*.engine_game_id",
        "checkpoint_state_hashes.*.session_id",
        "terminal.engine_game_id",
        "terminal.session_id",
        "terminal.wall_clock",
        "process_local_identifiers",
    }
)

# The declared justifications. A rule must name exactly one and it must describe
# a genuinely process-local or incidental fact.
NORMALIZATION_JUSTIFICATIONS: Mapping[str, str] = {
    "process_local_identifier": (
        "an identifier minted per OS process (session/game/handle id); two fresh "
        "processes cannot share it and it carries no Rules observation"
    ),
    "wall_clock": "a wall-clock timestamp, which is incidental and non-semantic",
    "absolute_path": "an absolute filesystem path, which is machine-local",
}

ALLOWED_NORMALIZATION_JUSTIFICATIONS = frozenset(NORMALIZATION_JUSTIFICATIONS)


@dataclass(frozen=True)
class NormalizationRule:
    """One explicitly justified removal of a process-local value.

    The path must be allow-listed and the justification must be declared; a
    path that is not allow-listed (for example ``decisions.*.chosen``) raises at
    construction time so no caller can normalize a Rules-significant field by
    accident.
    """

    path: str
    justification: str

    def __post_init__(self) -> None:
        if self.path not in PROCESS_LOCAL_PATHS:
            raise NormalizationContractError(
                f"path {self.path!r} is not a declared process-local path; "
                "Rules-significant fields may never be normalized"
            )
        if self.justification not in ALLOWED_NORMALIZATION_JUSTIFICATIONS:
            raise NormalizationContractError(
                f"justification {self.justification!r} is not declared; "
                f"declared justifications are {sorted(ALLOWED_NORMALIZATION_JUSTIFICATIONS)}"
            )

    def to_document(self) -> dict[str, str]:
        return {"path": self.path, "justification": self.justification}


def validate_normalization_rules(rules: Sequence[NormalizationRule]) -> None:
    for rule in rules:
        if rule.path not in PROCESS_LOCAL_PATHS:
            raise NormalizationContractError(
                f"path {rule.path!r} is not a declared process-local path"
            )
        if rule.justification not in ALLOWED_NORMALIZATION_JUSTIFICATIONS:
            raise NormalizationContractError(
                f"justification {rule.justification!r} is not declared"
            )


def _iter_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.append(child)
            paths.extend(_iter_paths(inner, child))
    elif isinstance(value, list):
        for inner in value:
            paths.extend(_iter_paths(inner, f"{prefix}.*"))
    return paths


def _rule_matches(path: str, rule_path: str) -> bool:
    return path == rule_path or path.startswith(rule_path + ".")


def apply_normalization(
    document: Mapping[str, Any],
    rules: Sequence[NormalizationRule],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a copy with declared process-local paths removed.

    Only exact allow-listed paths (or their descendants) are removed, and every
    removal is reported. A rule whose path does not exist is a no-op and is
    reported as not applied; it is never silently widened to a nearby key.
    """
    validate_normalization_rules(rules)
    normalized = copy.deepcopy(dict(document))
    report: list[dict[str, Any]] = []

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key in list(node):
                path = f"{prefix}.{key}" if prefix else str(key)
                matched = [rule for rule in rules if _rule_matches(path, rule.path)]
                if matched:
                    removed = node.pop(key)
                    report.append(
                        {
                            "path": path,
                            "justification": matched[0].justification,
                            "removed_sha256": sha256_json(removed),
                            "applied": True,
                        }
                    )
                    continue
                _walk(node[key], path)
        elif isinstance(node, list):
            for item in node:
                _walk(item, f"{prefix}.*")

    _walk(normalized, "")
    applied_paths = {entry["path"] for entry in report}
    for rule in rules:
        if not any(_rule_matches(path, rule.path) for path in applied_paths):
            report.append(
                {
                    "path": rule.path,
                    "justification": rule.justification,
                    "applied": False,
                    "detail": "path not present in this document",
                }
            )
    return normalized, report


# --------------------------------------------------------------------------- #
# Twin run record
# --------------------------------------------------------------------------- #


@dataclass
class TwinRun:
    """One process's required twin evidence."""

    role: str
    candidate: str
    fixture_identity: dict[str, Any]
    candidate_build: dict[str, Any]
    lab_source: dict[str, Any]
    process: ProcessIdentity | None
    rules_rng: dict[str, Any]
    decisions: list[dict[str, Any]]
    semantic_events: list[dict[str, Any]]
    checkpoint_state_hashes: list[dict[str, Any]]
    terminal: dict[str, Any]
    process_local_identifiers: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None
    limitations: list[str] = field(default_factory=list)

    def to_document(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "candidate": self.candidate,
            "fixture_identity": self.fixture_identity,
            "candidate_build": self.candidate_build,
            "lab_source": self.lab_source,
            "process_identity": (self.process.to_document() if self.process is not None else None),
            "rules_rng": self.rules_rng,
            "decisions": self.decisions,
            "semantic_events": self.semantic_events,
            "checkpoint_state_hashes": self.checkpoint_state_hashes,
            "terminal_outcome": self.terminal,
            "process_local_identifiers": self.process_local_identifiers,
            "failure": self.failure,
            "limitations": self.limitations,
        }


# --------------------------------------------------------------------------- #
# Semantic comparison
# --------------------------------------------------------------------------- #


@dataclass
class TwinComparison:
    """The typed result of comparing a record run and a replay run."""

    verdict: str
    verified: bool
    checks: list[dict[str, Any]]
    divergences: list[dict[str, Any]]
    normalization: list[dict[str, Any]]
    record_role: str
    replay_role: str

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "verdict": self.verdict,
            "verified": self.verified,
            "record_role": self.record_role,
            "replay_role": self.replay_role,
            "checks": self.checks,
            "divergences": self.divergences,
            "normalization": self.normalization,
        }


def _as_document(run: TwinRun | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(run, TwinRun):
        return run.to_document()
    return copy.deepcopy(dict(run))


def _ordered_equality(
    left: Sequence[Any],
    right: Sequence[Any],
) -> bool:
    return _canonical(list(left)) == _canonical(list(right))


def _missing_or_reordered(
    expected: Sequence[Any],
    actual: Sequence[Any],
) -> str:
    """Classify an ordered-sequence mismatch that is a subset/reorder.

    Returns ``EVENT_MISSING`` when ``actual`` is ``expected`` with elements
    removed, ``EVENT_REORDERED`` when both multisets are equal but order
    differs, otherwise the generic divergence.
    """
    expected_keys = [_canonical(item) for item in expected]
    actual_keys = [_canonical(item) for item in actual]
    if len(actual_keys) < len(expected_keys):
        cursor = 0
        for key in actual_keys:
            while cursor < len(expected_keys) and expected_keys[cursor] != key:
                cursor += 1
            if cursor >= len(expected_keys):
                break
            cursor += 1
        else:
            return DIVERGENCE_EVENT_MISSING
    if sorted(expected_keys) == sorted(actual_keys) and expected_keys != actual_keys:
        return DIVERGENCE_EVENT_REORDERED
    return DIVERGENCE_EVENT


def compare_twin_runs(
    record: TwinRun | Mapping[str, Any],
    replay: TwinRun | Mapping[str, Any],
    *,
    normalizations: Sequence[NormalizationRule] = (),
    require_complete_terminal: bool = True,
) -> TwinComparison:
    """Compare two twin runs semantically and classify every divergence.

    Process-local identifiers are never compared (the ``process`` and
    ``process_local_identifiers`` sections are outside the compared surface).
    Any additional normalization must be declared; the result records exactly
    what was applied.
    """
    left, left_report = apply_normalization(_as_document(record), normalizations)
    right, right_report = apply_normalization(_as_document(replay), normalizations)

    checks: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str, code: str, **extra: Any) -> None:
        entry: dict[str, Any] = {"check": name, "passed": passed, "detail": detail}
        entry.update(extra)
        checks.append(entry)
        if not passed:
            divergences.append({"code": code, "check": name, "detail": detail, **extra})

    # -- required sections -------------------------------------------------
    for section in REQUIRED_TWIN_SECTIONS:
        left_value = left.get(section)
        right_value = right.get(section)
        present = bool(left_value) and bool(right_value)
        check(
            f"required_section:{section}",
            present,
            f"left present={bool(left_value)} right present={bool(right_value)}",
            DIVERGENCE_SECTION_MISSING,
            section=section,
        )

    # -- identity ----------------------------------------------------------
    check(
        "fixture_identity",
        left.get("fixture_identity") == right.get("fixture_identity"),
        "the two runs must be about the same fixture",
        DIVERGENCE_FIXTURE,
    )
    check(
        "candidate_build",
        left.get("candidate_build") == right.get("candidate_build"),
        "the two runs must execute the same candidate/build identity",
        DIVERGENCE_BUILD,
    )
    check(
        "lab_source",
        left.get("lab_source") == right.get("lab_source"),
        "the two runs must be produced by the same Lab source identity",
        DIVERGENCE_LAB_SOURCE,
    )

    # -- process identity --------------------------------------------------
    left_process = left.get("process_identity") or {}
    right_process = right.get("process_identity") or {}
    left_observed = bool(left_process.get("observed")) if isinstance(left_process, dict) else False
    right_observed = (
        bool(right_process.get("observed")) if isinstance(right_process, dict) else False
    )
    check(
        "process_identity_present",
        left_observed and right_observed,
        "both engine process identities must be observed from the OS",
        DIVERGENCE_PROCESS_MISSING,
    )
    left_key = (
        (
            left_process.get("pid"),
            left_process.get("start_ticks"),
            left_process.get("boot_id"),
        )
        if isinstance(left_process, dict)
        else None
    )
    right_key = (
        (
            right_process.get("pid"),
            right_process.get("start_ticks"),
            right_process.get("boot_id"),
        )
        if isinstance(right_process, dict)
        else None
    )
    distinct = (
        left_observed
        and right_observed
        and left_key is not None
        and right_key is not None
        and left_key != right_key
    )
    check(
        "process_identity_distinct",
        distinct,
        "the two phases must be genuinely distinct OS processes",
        DIVERGENCE_PROCESS_NOT_DISTINCT,
    )

    # -- rules RNG ---------------------------------------------------------
    left_rng = left.get("rules_rng") or {}
    right_rng = right.get("rules_rng") or {}
    rng_fields = (
        "requested_seed",
        "acknowledged_seed",
        "classification",
        "controlled",
        "rng_credit",
        "rng_call_coordinates",
    )
    rng_mismatch = [
        key
        for key in rng_fields
        if _canonical(_rng_view(left_rng).get(key)) != _canonical(_rng_view(right_rng).get(key))
    ]
    check(
        "rules_rng",
        not rng_mismatch,
        "requested seed, provider acknowledgement and RNG coordinates must match",
        DIVERGENCE_RNG,
        differing_fields=rng_mismatch,
    )
    # A twin whose seed was never acknowledged earns no replay credit.
    acknowledged = _rng_view(right_rng).get("acknowledged_seed")
    requested = _rng_view(right_rng).get("requested_seed")
    check(
        "rules_rng_acknowledged",
        acknowledged is not None and acknowledged == requested,
        "the provider must acknowledge the requested seed; acknowledgement is a precondition",
        DIVERGENCE_RNG,
    )

    # -- decisions ---------------------------------------------------------
    left_decisions = left.get("decisions") or []
    right_decisions = right.get("decisions") or []
    check(
        "decisions",
        _ordered_equality(left_decisions, right_decisions),
        "the externally supplied decision tape must replay identically",
        DIVERGENCE_DECISION,
        left_count=len(left_decisions),
        right_count=len(right_decisions),
        first_difference=_first_difference(left_decisions, right_decisions),
    )

    # -- semantic events ---------------------------------------------------
    left_events = left.get("semantic_events") or []
    right_events = right.get("semantic_events") or []
    if not _ordered_equality(left_events, right_events):
        check(
            "semantic_events",
            False,
            "the ordered semantic event tape differs",
            _missing_or_reordered(left_events, right_events),
            left_count=len(left_events),
            right_count=len(right_events),
            first_difference=_first_difference(left_events, right_events),
        )
    else:
        check("semantic_events", True, "the ordered semantic event tape is identical", "")

    # -- checkpoint state hashes -------------------------------------------
    left_checkpoints = left.get("checkpoint_state_hashes") or []
    right_checkpoints = right.get("checkpoint_state_hashes") or []
    check(
        "checkpoint_state_hashes",
        _ordered_equality(left_checkpoints, right_checkpoints),
        "the ordered checkpoint chain must be identical",
        DIVERGENCE_STATE,
        left_count=len(left_checkpoints),
        right_count=len(right_checkpoints),
        first_difference=_first_difference(left_checkpoints, right_checkpoints),
    )

    # -- terminal ----------------------------------------------------------
    left_terminal = left.get("terminal_outcome") or {}
    right_terminal = right.get("terminal_outcome") or {}
    check(
        "terminal_outcome",
        left_terminal == right_terminal,
        "the terminal facts/outcome must be identical",
        DIVERGENCE_TERMINAL,
    )
    if require_complete_terminal:
        complete = (
            isinstance(right_terminal, dict)
            and right_terminal.get("complete") is True
            and isinstance(left_terminal, dict)
            and left_terminal.get("complete") is True
        )
        check(
            "terminal_complete",
            complete,
            "a bounded-horizon or missing terminal is never a replay PASS",
            DIVERGENCE_TERMINAL_INCOMPLETE,
        )

    real_divergences = [item for item in divergences]
    verified = not real_divergences
    verdict = "PASS" if verified else "FAIL"
    if not verified and any(
        item["code"] in {DIVERGENCE_SECTION_MISSING, DIVERGENCE_TERMINAL_INCOMPLETE}
        for item in real_divergences
    ):
        verdict = "UNKNOWN"
    comparison = TwinComparison(
        verdict=verdict,
        verified=verified,
        checks=checks,
        divergences=real_divergences,
        normalization=[*left_report, *right_report],
        record_role=str(left.get("role") or "RECORD"),
        replay_role=str(right.get("role") or "REPLAY"),
    )
    return comparison


def _rng_view(rules_rng: Any) -> dict[str, Any]:
    if not isinstance(rules_rng, Mapping):
        return {}
    binding = rules_rng.get("binding")
    if isinstance(binding, Mapping):
        merged = dict(rules_rng)
        merged.update(binding)
        return merged
    return dict(rules_rng)


def _first_difference(left: Sequence[Any], right: Sequence[Any]) -> dict[str, Any] | None:
    for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
        if _canonical(left_item) != _canonical(right_item):
            return {"index": index, "record": left_item, "replay": right_item}
    if len(left) != len(right):
        longer, shorter = (left, right) if len(left) > len(right) else (right, left)
        return {"index": len(shorter), "only_in_longer": longer[len(shorter)]}
    return None


# --------------------------------------------------------------------------- #
# Gate-facing twin document
# --------------------------------------------------------------------------- #


def _embedded(entries: Sequence[Any]) -> dict[str, Any]:
    payload = list(entries)
    if len(payload) <= MAX_EMBEDDED_ENTRIES:
        sample = payload
        kind = "full"
    else:
        half = MAX_EMBEDDED_ENTRIES // 2
        sample = [*payload[:half], *payload[-half:]]
        kind = "head_tail_sample"
    return {
        "count": len(payload),
        "sha256": sha256_json(payload),
        "embedded": kind,
        "omitted": max(0, len(payload) - len(sample)),
        "entries": sample,
    }


def clean_process_twin_document(
    *,
    record: TwinRun,
    replay: TwinRun,
    comparison: TwinComparison,
    replay_check: Mapping[str, Any] | None = None,
    adversarial_controls: Sequence[Mapping[str, Any]] = (),
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the ``clean_process_twin`` block the AF09 gate derives from.

    The block carries every required element non-empty, the exact comparison
    verdict, and the adversarial control receipts. ``verified`` is true only
    when the semantic comparison passed and (where a lane has its own engine
    consumer) that consumer also re-derived the tape in a fresh process.
    """
    process_documents = [
        document
        for document in (
            record.process.to_document() if record.process is not None else None,
            replay.process.to_document() if replay.process is not None else None,
        )
        if document is not None
    ]
    external_ok = True
    if replay_check is not None:
        external_ok = bool(replay_check.get("pass"))
    verified = bool(comparison.verified and external_ok)
    verdict = "PASS" if verified else ("FAIL" if comparison.verdict == "FAIL" else "UNKNOWN")
    if not external_ok:
        verdict = "UNKNOWN" if comparison.verdict != "FAIL" else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "verified": verified,
        "verdict": verdict,
        "fixture_identity": record.fixture_identity,
        "candidate_build": record.candidate_build,
        "lab_source": record.lab_source,
        "process_identity": process_documents,
        "decisions": _embedded(record.decisions),
        "rules_rng": record.rules_rng,
        "semantic_events": _embedded(record.semantic_events),
        "checkpoint_state_hashes": _embedded(record.checkpoint_state_hashes),
        "terminal_outcome": record.terminal,
        "comparison": comparison.to_document(),
        "fresh_process_engine_check": dict(replay_check) if replay_check else None,
        "adversarial_controls": list(adversarial_controls),
        "limitations": list(limitations),
    }


# --------------------------------------------------------------------------- #
# Adversarial controls
# --------------------------------------------------------------------------- #


def _mutate_document(document: Mapping[str, Any], mutator: Any) -> dict[str, Any]:
    mutated = copy.deepcopy(dict(document))
    mutator(mutated)
    return mutated


def run_adversarial_controls(
    record: TwinRun,
    replay: TwinRun,
    *,
    normalizations: Sequence[NormalizationRule] = (),
) -> list[dict[str, Any]]:
    """Run every mandatory adversarial control against the twin checker.

    Each control mutates one semantic fact and requires the checker to reject
    the mutated twin with the expected divergence class. Controls that cannot
    apply to this twin (for example a reorder on a one-event tape) are reported
    as NOT_APPLICABLE with the reason, never silently skipped.
    """
    baseline = compare_twin_runs(record, replay, normalizations=normalizations)
    results: list[dict[str, Any]] = []

    def control(name: str, expected: set[str], mutator: Any, applicable: bool, reason: str) -> None:
        if not applicable:
            results.append(
                {
                    "control": name,
                    "detected": False,
                    "applicable": False,
                    "detail": reason,
                }
            )
            return
        mutated = _mutate_document(replay.to_document(), mutator)
        comparison = compare_twin_runs(record, mutated, normalizations=normalizations)
        codes = {item["code"] for item in comparison.divergences}
        detected = (not comparison.verified) and bool(codes & expected)
        results.append(
            {
                "control": name,
                "detected": detected,
                "applicable": True,
                "expected": sorted(expected),
                "observed_codes": sorted(codes),
                "detail": (
                    "the checker rejected the mutated twin with the expected divergence"
                    if detected
                    else "the checker did not detect the mutation as expected"
                ),
            }
        )

    def _change_decision(document: dict[str, Any]) -> None:
        document["decisions"][0]["chosen_fingerprint"] = "tampered-decision"

    def _change_seed(document: dict[str, Any]) -> None:
        binding = document["rules_rng"].setdefault("binding", {})
        binding["acknowledged_seed"] = 999
        document["rules_rng"]["acknowledged_seed"] = 999

    def _change_rng_coordinate(document: dict[str, Any]) -> None:
        document["rules_rng"]["rng_call_coordinates"][0]["after"] = (
            int(document["rules_rng"]["rng_call_coordinates"][0]["after"]) + 7
        )

    def _remove_event(document: dict[str, Any]) -> None:
        document["semantic_events"].pop(0)

    def _reorder_events(document: dict[str, Any]) -> None:
        document["semantic_events"][0], document["semantic_events"][1] = (
            document["semantic_events"][1],
            document["semantic_events"][0],
        )

    def _change_checkpoint(document: dict[str, Any]) -> None:
        document["checkpoint_state_hashes"][0]["public_state_digest"] = "f" * 64

    def _change_terminal(document: dict[str, Any]) -> None:
        outcomes = document["terminal_outcome"].get("outcomes")
        if isinstance(outcomes, list) and outcomes:
            outcomes[0]["won"] = not bool(outcomes[0].get("won"))
        else:
            document["terminal_outcome"]["state_digest"] = "0" * 64

    def _same_seed_different_decisions(document: dict[str, Any]) -> None:
        document["decisions"][0]["chosen_fingerprint"] = "different-with-same-seed"

    def _same_process_identity(document: dict[str, Any]) -> None:
        document["process_identity"] = copy.deepcopy(record.to_document()["process_identity"])

    has_decisions = bool(record.decisions) and bool(replay.decisions)
    has_rng_coordinates = bool(record.rules_rng.get("rng_call_coordinates")) and bool(
        replay.rules_rng.get("rng_call_coordinates")
    )
    has_events = len(record.semantic_events) >= 1 and len(replay.semantic_events) >= 1
    has_two_events = len(record.semantic_events) >= 2 and len(replay.semantic_events) >= 2
    has_checkpoints = bool(record.checkpoint_state_hashes) and bool(replay.checkpoint_state_hashes)

    control(
        "changed_decision",
        {DIVERGENCE_DECISION},
        _change_decision,
        has_decisions,
        "no decision tape entries to mutate",
    )
    control(
        "changed_seed_or_rng_binding",
        {DIVERGENCE_RNG},
        _change_seed,
        has_decisions,
        "no decision tape entries to mutate",
    )
    control(
        "changed_rng_coordinates",
        {DIVERGENCE_RNG},
        _change_rng_coordinate,
        has_rng_coordinates,
        "the provider exposed no per-decision RNG coordinates",
    )
    control(
        "missing_event",
        {DIVERGENCE_EVENT_MISSING, DIVERGENCE_EVENT},
        _remove_event,
        has_events,
        "no semantic event entries to mutate",
    )
    control(
        "reordered_event",
        {DIVERGENCE_EVENT_REORDERED, DIVERGENCE_EVENT},
        _reorder_events,
        has_two_events,
        "fewer than two distinct semantic events",
    )
    control(
        "changed_checkpoint_hash",
        {DIVERGENCE_STATE},
        _change_checkpoint,
        has_checkpoints,
        "no checkpoint entries to mutate",
    )
    control(
        "changed_terminal",
        {DIVERGENCE_TERMINAL},
        _change_terminal,
        bool(record.terminal) and bool(replay.terminal),
        "no terminal facts to mutate",
    )
    control(
        "same_seed_different_decisions",
        {DIVERGENCE_DECISION},
        _same_seed_different_decisions,
        has_decisions,
        "no decision tape entries to mutate",
    )
    control(
        "same_process_identity_is_not_a_twin",
        {DIVERGENCE_PROCESS_NOT_DISTINCT},
        _same_process_identity,
        True,
        "",
    )

    # The normalization guard is itself a mandatory control: a Rules-significant
    # path must never be accepted as normalizable.
    normalization_guard = False
    guard_detail = ""
    try:
        NormalizationRule(path="decisions.*.chosen_fingerprint", justification="wall_clock")
    except NormalizationContractError as exc:
        normalization_guard = True
        guard_detail = str(exc)
    results.append(
        {
            "control": "normalization_of_rules_significant_field_fails",
            "detected": normalization_guard,
            "applicable": True,
            "detail": guard_detail or "a Rules-significant normalization rule was NOT rejected",
        }
    )

    results.append(
        {
            "control": "baseline_twin_verified",
            "detected": baseline.verified,
            "applicable": True,
            "detail": (
                "the unmodified twin verifies"
                if baseline.verified
                else "the unmodified twin does not verify"
            ),
        }
    )
    return results


# --------------------------------------------------------------------------- #
# Generic-lane twin driver (candidate-neutral Protocol-2 surface)
# --------------------------------------------------------------------------- #

GENERIC_LANE_FIXTURE_TEMPLATE = "AF09-GENERIC-{candidate}-{player_count}P-v1"


def _lab_source_identity(root: Path | None = None) -> dict[str, Any]:
    resolved = root or repo_root()
    try:
        commit = receipt_mod.git_fact(resolved, "rev-parse", "HEAD", sha=True)
        tree = receipt_mod.git_fact(resolved, "rev-parse", "HEAD^{tree}", sha=True)
        dirty_paths = sorted(receipt_mod._git_porcelain(resolved))
    except receipt_mod.ReceiptError as exc:
        raise ReplayTwinError(f"the Lab source identity could not be established: {exc}") from exc
    return {
        "repository": "moeendres-png/commander-playtest-lab",
        "commit": commit,
        "tree": tree,
        "clean": not dirty_paths,
        "dirty_paths": dirty_paths,
    }


def _fingerprint_channel(candidate: str) -> str:
    if candidate == "forge":
        return "legal_action.semantic_fingerprint (WS227 forge-semantic-option-identity/1.0.0)"
    return (
        "no cross-process semantic option identity is published on this lane; "
        "XMage's generic-lane action ids are process-local handles"
    )


def _action_fingerprint(candidate: str, action: Mapping[str, Any]) -> str:
    fingerprint = action.get("semantic_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise TwinChannelUnavailable(
            "semantic_option_identity",
            f"a {candidate} legal action was published without a semantic fingerprint",
            evidence_channel=_fingerprint_channel(candidate),
        )
    return fingerprint


def _decision_checkpoint(candidate: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    decision = raw.get("decision")
    decision = decision if isinstance(decision, Mapping) else {}
    rng = decision.get("rng_binding")
    rng = rng if isinstance(rng, Mapping) else {}
    return {
        "decision_class": decision.get("decision_class"),
        "kind": decision.get("kind"),
        "actor": decision.get("actor"),
        "revision": decision.get("revision"),
        "legal_set_digest": decision.get("legal_set_digest"),
        "legal_set_size": decision.get("legal_set_size"),
        "rng_calls": rng.get("rules_calls"),
        "rng_root_seed": rng.get("rules_root_seed"),
        "explicit_seed": rng.get("explicit_seed"),
        "event_offset": decision.get("event_offset"),
        "public_state_digest": decision.get("public_state_digest"),
        "principal_observation_digest": decision.get("principal_observation_digest"),
    }


def _state_checkpoint(state: Mapping[str, Any] | None) -> dict[str, Any]:
    state = state if isinstance(state, Mapping) else {}
    rng = state.get("rng_binding")
    rng = rng if isinstance(rng, Mapping) else {}
    return {
        "public_state_digest": state.get("public_state_digest"),
        "principal_observation_digest": state.get("principal_observation_digest"),
        "rng_calls": rng.get("rules_calls"),
        "rng_root_seed": rng.get("rules_root_seed"),
        "event_offset": state.get("event_offset"),
        "phase": state.get("phase"),
        "step": state.get("step"),
        "active_player_id": state.get("active_player_id"),
        "priority_player_id": state.get("priority_player_id"),
        "status": state.get("status"),
    }


def _terminal_outcomes(state: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    state = state if isinstance(state, Mapping) else {}
    raw = state.get("terminal_outcomes")
    if not isinstance(raw, list):
        return []
    outcomes: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        outcomes.append(
            {
                "seat": item.get("seat"),
                "player_id": item.get("player_id"),
                "life": item.get("life"),
                "lost": bool(item.get("lost")),
                "won": bool(item.get("won")),
                "left": bool(item.get("left")),
            }
        )
    outcomes.sort(key=lambda entry: (entry["seat"] is None, entry["seat"]))
    return outcomes


def _event_digest(entry: Mapping[str, Any]) -> str:
    return sha256_json(
        {
            "sequence": entry.get("sequence"),
            "kind": entry.get("kind"),
            "actor": entry.get("actor"),
            "chosen_fingerprint": entry.get("chosen_fingerprint"),
            "rng_calls_before": entry.get("rng_calls_before"),
            "rng_calls_after": entry.get("rng_calls_after"),
            "public_state_digest_before": entry.get("public_state_digest_before"),
            "public_state_digest_after": entry.get("public_state_digest_after"),
            "event_offset_before": entry.get("event_offset_before"),
            "event_offset_after": entry.get("event_offset_after"),
            "engine_executed": entry.get("engine_executed"),
        }
    )


def _record_action_for_kind(
    candidate: str,
    kind: str,
    actions: list[dict[str, Any]],
    frame: dict[str, Any],
    *,
    scripted_starting_seat: str,
) -> tuple[dict[str, Any], str]:
    """Apply the declared recording policy and return (action, policy)."""
    if kind in {"STARTING_PLAYER", "CHOOSE_STARTING_PLAYER"}:
        matches = [
            action
            for action in actions
            if action.get("action_type") == "structural_decision"
            and action.get("source_object_id") == scripted_starting_seat
        ]
        if len(matches) != 1:
            raise DecisionUnsatisfied(
                f"the fixture script requires starting seat {scripted_starting_seat!r}; "
                f"the engine offered {[a.get('source_object_id') for a in actions]}"
            )
        return matches[0], "fixture_scripted_seat"
    if kind == "ORDER_CHOICE":
        return select_cost_order_action(actions), "native_declared_cost_part_order"
    if kind == "PRIORITY":
        for action in actions:
            if action.get("action_type") == "pass_priority":
                return action, "pass_when_offered"
        raise DecisionUnsatisfied("PRIORITY exposed no pass_priority option")
    if "DRAW" in kind:
        chosen = self_choice_pass(actions, str(frame["decision"].get("actor")), None)
        if chosen is None:
            raise DecisionUnsatisfied(f"{kind} exposed no pass option")
        for action in actions:
            if str(action.get("action_id")) == chosen:
                return action, "pass_when_offered"
        raise DecisionUnsatisfied(f"{kind} pass option was not among the offered actions")
    # Any other engine-offered discretionary frame: choose the deterministically
    # smallest semantic fingerprint that occurs exactly once among the offered
    # options. This is an explicit external policy over engine-offered options;
    # it fabricates nothing.
    #
    # The engine's own identity discipline deliberately treats fully
    # indistinguishable duplicate siblings (identical name/controller/zone and
    # tie-breakers) as one colliding fingerprint. Selecting among them would be
    # a forbidden first-match, so a frame whose entire offered set collides
    # fails closed with the exact ambiguity.
    fingerprints = [_action_fingerprint(candidate, action) for action in actions]
    if not fingerprints:
        raise DecisionUnsatisfied(f"{kind} exposed no offered options")
    counts: dict[str, int] = {}
    for fingerprint in fingerprints:
        counts[fingerprint] = counts.get(fingerprint, 0) + 1
    unique = sorted(fingerprint for fingerprint, count in counts.items() if count == 1)
    if not unique:
        raise DecisionUnsatisfied(
            f"{kind} offered only indistinguishable duplicate options "
            f"({len(fingerprints)} options across {len(counts)} colliding fingerprints); "
            "no authoritative occurrence identity exists, so the choice cannot be replayed"
        )
    wanted = unique[0]
    return (
        next(action for action in actions if _action_fingerprint(candidate, action) == wanted),
        "deterministic_unique_lexicographic_fingerprint",
    )


def _resolve_replay_action(
    candidate: str,
    entry: Mapping[str, Any],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    recorded = entry.get("chosen_fingerprint")
    if not isinstance(recorded, str) or not recorded:
        raise TwinReplayDivergence(
            f"decision {entry.get('sequence')}: the tape records no chosen fingerprint"
        )
    matches = [action for action in actions if _action_fingerprint(candidate, action) == recorded]
    if len(matches) != 1:
        raise TwinReplayDivergence(
            f"decision {entry.get('sequence')}: the recorded choice "
            f"{recorded!r} matched {len(matches)} offered options; exactly one is required"
        )
    return matches[0]


def _submit_generic_decision(
    proc: Any,
    *,
    candidate: str,
    kind: str,
    action: Mapping[str, Any] | None,
    frame: dict[str, Any],
    game_id: str,
) -> dict[str, Any]:
    """Submit one engine-offered action through the candidate's transport.

    Dedicated messages are used where the lane defines them (mulligan keep,
    priority pass); every other class uses the engine's own action submission.
    The payload is never synthesized beyond what the offered action published.
    """
    identity = decision_identity_params(candidate, frame)
    if kind in {"MULLIGAN", "KEEP_OR_MULLIGAN"}:
        return _require_ok(
            proc.request(
                "resolve_mulligan",
                {
                    "player_id": str(frame["decision"].get("actor")),
                    **identity,
                    "keep": True,
                    "bottom_card_ids": [],
                },
                game_id=game_id,
                timeout_s=120.0,
            ),
            "resolve_mulligan",
        )
    if action is None:
        raise DecisionUnsatisfied(f"{kind} has no chosen offered action to submit")
    if kind == "PRIORITY" and action.get("action_type") != "concede":
        return _require_ok(
            proc.request("pass_priority", identity, game_id=game_id, timeout_s=120.0),
            "pass_priority",
        )
    action_id = action.get("action_id")
    action_type = action.get("action_type")
    if not action_id:
        raise DecisionUnsatisfied(f"the chosen {kind} option has no action_id")
    proposal = {
        "proposal_id": f"af09-{game_id}-{frame['decision'].get('revision')}",
        "actor_id": str(frame["decision"].get("actor") or frame.get("seat")),
        "legal_action_id": str(action_id),
        "action_type": str(action_type or "structural_decision"),
    }
    return _require_ok(
        proc.request(
            "submit_action",
            {**identity, "proposal": proposal},
            game_id=game_id,
            timeout_s=120.0,
        ),
        f"submit_action({kind})",
    )


def gather_generic_lane_process(
    proc: Any,
    *,
    role: str,
    candidate: str,
    player_count: int,
    seed: int,
    fixture_id: str,
    game_id: str,
    plan_command: Sequence[str],
    build_identity: dict[str, Any],
    expected_engine_commit: str,
    lab_source: dict[str, Any],
    decision_tape: Sequence[Mapping[str, Any]] | None,
    max_decisions: int = 6000,
    scripted_starting_seat: str = "p1",
    deck_payloads: Sequence[Mapping[str, Any]] | None = None,
    concede_after_decisions: int | None = None,
) -> TwinRun:
    """Drive one fresh engine process and record its twin evidence.

    With ``decision_tape=None`` the process records the tape under the declared
    external policy. With a tape it replays that tape: every decision is
    resolved to exactly one engine-offered semantic option and the engine's own
    acceptance is required. Nothing is answered when the resolution is missing
    or ambiguous.
    """
    replaying = decision_tape is not None
    tape = list(decision_tape or [])
    conceded_actors: set[str] = set()
    run_limitations: list[str] = []
    decisions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    terminal: dict[str, Any] = {
        "kind": "NONE",
        "complete": False,
        "reason": "the process did not reach a terminal fact",
    }
    failure: str | None = None

    provider: dict[str, Any] = {}
    seed_supported = False
    binding_document: dict[str, Any] = {}
    created_player_count: Any = None
    start_status: Any = None
    deck_identity: list[str] = []
    deck_hashes: list[str] = []
    fixture_identity: dict[str, Any] = {}
    candidate_build: dict[str, Any] = {}
    rules_rng: dict[str, Any] = {}

    try:
        for message in ("start_engine", "get_provider_version", "get_capabilities"):
            response = proc.request(message, {}, timeout_s=60.0)
            payload = _require_ok(response, message)
            if message == "get_provider_version":
                provider = dict(payload)
        handles: list[str] = []
        resolved_decks = list(deck_payloads) if deck_payloads is not None else []
        if resolved_decks and len(resolved_decks) != player_count:
            raise GameDriveError(
                f"{len(resolved_decks)} fixture decks were supplied for {player_count} seats"
            )
        for seat in range(1, player_count + 1):
            deck = (
                dict(resolved_decks[seat - 1])
                if resolved_decks
                else build_deck(f"{candidate}-af09-twin-seat{seat}")
            )
            deck_identity.append(str(deck.get("deck_id")))
            deck_hashes.append(str(deck.get("deck_hash")))
            payload = _require_ok(
                proc.request("import_deck", {"deck": deck}, timeout_s=120.0),
                "import_deck",
            )
            handle = payload.get("deck_handle")
            handle_id = handle.get("handle_id") if isinstance(handle, dict) else None
            if not handle_id:
                raise GameDriveError(f"import_deck returned no deck handle: {payload}")
            handles.append(str(handle_id))

        seed_supported = _declares_seed_support(proc)
        created = _require_ok(
            proc.request(
                "create_commander_game",
                _create_request(game_id, handles, seed, seed_supported),
                game_id=game_id,
                timeout_s=300.0,
            ),
            "create_commander_game",
        )
        binding = receipt_mod.classify_seed_binding(
            requested_seed=seed,
            acknowledged_seed=_acknowledged_seed(created),
            source="create_commander_game_response",
        )
        binding_document = binding.to_document()
        created_player_count = created.get("player_count", len(handles))
        started = _require_ok(
            proc.request("start_game", {}, game_id=game_id, timeout_s=300.0), "start_game"
        )
        start_status = started.get("status")

        steps = 0
        frame: dict[str, Any] | None = None
        last_state: dict[str, Any] | None = None
        while steps < max_decisions:
            try:
                frame = poll_decision(proc, game_id, seat_count=player_count, candidate=candidate)
            except GameDriveError:
                # No parked decision: either the game ended or the lane stalled.
                state = _read_generic_state(proc, game_id, observer=None)
                if state is not None and _state_is_game_over(state):
                    last_state = state
                    break
                raise
            steps += 1
            decision = frame["decision"]
            raw = frame["raw"]
            kind = str(decision.get("kind") or "").upper()
            actor = str(decision.get("actor") or frame.get("seat"))
            revision = decision.get("revision")
            actions = [action for action in frame["actions"] if isinstance(action, dict)]
            checkpoint_before = _decision_checkpoint(candidate, raw)

            if replaying:
                if steps > len(tape):
                    raise TwinReplayDivergence(
                        f"the live game offers decision {steps} but the tape has {len(tape)}"
                    )
                entry = tape[steps - 1]
                recorded = entry.get("pre_checkpoint") or {}
                for field_name in ("kind", "actor", "revision"):
                    if (
                        recorded.get(field_name)
                        != {
                            "kind": kind,
                            "actor": actor,
                            "revision": revision,
                        }[field_name]
                    ):
                        raise TwinReplayDivergence(
                            f"decision {steps}: {field_name} is "
                            f"{ {'kind': kind, 'actor': actor, 'revision': revision}[field_name]!r}, "
                            f"the tape records {recorded.get(field_name)!r}"
                        )
                if recorded.get("public_state_digest") != checkpoint_before.get(
                    "public_state_digest"
                ):
                    raise TwinReplayDivergence(
                        f"decision {steps}: the engine's public state digest differs from the tape"
                    )
                if recorded.get("legal_set_digest") != checkpoint_before.get("legal_set_digest"):
                    raise TwinReplayDivergence(
                        f"decision {steps}: the engine's legal set digest differs from the tape"
                    )
                chosen = _resolve_replay_action(candidate, entry, actions)
                policy = str(entry.get("policy") or "externally_supplied_decision_tape")
            else:
                concede_action: dict[str, Any] | None = None
                if (
                    concede_after_decisions is not None
                    and steps >= concede_after_decisions
                    and kind == "PRIORITY"
                    and actor not in conceded_actors
                ):
                    # The engine itself offers native concession on every
                    # supported priority frame (CR 104.3a); choosing it is an
                    # ordinary engine-offered external decision that reaches a
                    # real terminal outcome.
                    concede_action = next(
                        (action for action in actions if action.get("action_type") == "concede"),
                        None,
                    )
                if concede_action is not None:
                    chosen, policy = concede_action, "concede_at_defined_horizon"
                else:
                    chosen, policy = _record_action_for_kind(
                        candidate,
                        kind,
                        actions,
                        frame,
                        scripted_starting_seat=scripted_starting_seat,
                    )
            chosen_fingerprint = _action_fingerprint(candidate, chosen)

            answer = _submit_generic_decision(
                proc,
                candidate=candidate,
                kind=kind,
                action=chosen,
                frame=frame,
                game_id=game_id,
            )
            answer_decision = answer.get("decision")
            answer_decision = answer_decision if isinstance(answer_decision, dict) else {}
            engine_executed = answer_decision.get("executed") is True
            if not engine_executed:
                raise TwinReplayDivergence(
                    f"decision {steps}: the engine did not execute the submission "
                    f"(executed={answer_decision.get('executed')!r})"
                )
            if chosen.get("action_type") == "concede":
                conceded_actors.add(actor)
            state = answer.get("state")
            state = state if isinstance(state, dict) else None
            checkpoint_after = _state_checkpoint(state)

            tape_entry = {
                "sequence": steps,
                "kind": kind,
                "actor": actor,
                "revision": revision,
                "decision_class": checkpoint_before.get("decision_class"),
                "policy": policy,
                "chosen_fingerprint": chosen_fingerprint,
                "chosen_action_type": chosen.get("action_type"),
                "offered_fingerprints": sorted(
                    _action_fingerprint(candidate, action) for action in actions
                ),
                "pre_checkpoint": checkpoint_before,
            }
            decisions.append(tape_entry)
            event = {
                "sequence": steps,
                "kind": kind,
                "actor": actor,
                "chosen_fingerprint": chosen_fingerprint,
                "rng_calls_before": checkpoint_before.get("rng_calls"),
                "rng_calls_after": checkpoint_after.get("rng_calls"),
                "public_state_digest_before": checkpoint_before.get("public_state_digest"),
                "public_state_digest_after": checkpoint_after.get("public_state_digest"),
                "event_offset_before": checkpoint_before.get("event_offset"),
                "event_offset_after": checkpoint_after.get("event_offset"),
                "engine_executed": engine_executed,
            }
            event["digest"] = _event_digest(event)
            events.append(event)
            checkpoints.append(
                {
                    "sequence": steps,
                    "scope": "pre",
                    "public_state_digest": checkpoint_before.get("public_state_digest"),
                    "rng_calls": checkpoint_before.get("rng_calls"),
                    "event_offset": checkpoint_before.get("event_offset"),
                }
            )
            checkpoints.append(
                {
                    "sequence": steps,
                    "scope": "post",
                    "public_state_digest": checkpoint_after.get("public_state_digest"),
                    "rng_calls": checkpoint_after.get("rng_calls"),
                    "event_offset": checkpoint_after.get("event_offset"),
                }
            )
            if state is not None:
                last_state = state
            if answer.get("game_over") is True:
                terminal = _terminal_document(state, complete=True)
                break
        else:
            terminal = {
                "kind": "DECISION_HORIZON",
                "complete": False,
                "decisions": max_decisions,
                "reason": "the run reached the configured decision horizon without a terminal fact",
                **_state_checkpoint(last_state),
            }
            run_limitations.append(
                f"the run reached the bounded decision horizon ({max_decisions}) without a "
                "terminal game-over fact"
            )

        if replaying and terminal.get("complete") is True and steps < len(tape):
            raise TwinReplayDivergence(
                f"the tape records {len(tape)} decisions but the engine terminated after {steps}"
            )
        if terminal.get("kind") == "NONE":
            if last_state is not None and _state_is_game_over(last_state):
                terminal = _terminal_document(last_state, complete=True)
            elif steps >= max_decisions:
                terminal = {
                    "kind": "DECISION_HORIZON",
                    "complete": False,
                    "decisions": steps,
                    "reason": "no terminal fact was observed within the decision horizon",
                    **_state_checkpoint(last_state),
                }
            else:
                terminal = {
                    "kind": "NONE",
                    "complete": False,
                    "decisions": steps,
                    "reason": "no terminal fact was observed",
                    **_state_checkpoint(last_state),
                }
        fixture_identity = {
            "fixture_id": fixture_id,
            "candidate": candidate,
            "player_count": player_count,
            "seed": seed,
            "lane": "protocol2-jsonl",
            "deck_identity": deck_identity,
            "deck_hashes": deck_hashes,
            "commander": "Isamaru, Hound of Konda",
            "starting_seat_policy": "fixture_scripted_seat:p1",
        }
        candidate_build = {
            "candidate": candidate,
            "provider_payload": provider,
            "engine": provider.get("engine"),
            "engine_version": provider.get("engine_version"),
            "engine_commit": provider.get("engine_commit"),
            "engine_artifact_kind": provider.get("engine_artifact_kind"),
            "engine_artifact_sha256": provider.get("engine_artifact_sha256"),
            "expected_engine_commit": expected_engine_commit,
            "build_identity": dict(build_identity),
            "command": [str(part) for part in plan_command],
            "command_sha256": sha256_json([str(part) for part in plan_command]),
            "protocol_version": provider.get("protocol_version"),
        }
        rules_rng = {
            "requested_seed": seed,
            "provider_seed_supported": seed_supported,
            "binding": binding_document,
            "acknowledged_seed": binding_document.get("acknowledged_seed"),
            "classification": binding_document.get("classification"),
            "controlled": binding_document.get("controlled"),
            "rng_credit": binding_document.get("rng_credit"),
            "rng_call_coordinates": [
                {
                    "sequence": entry["sequence"],
                    "before": entry["rng_calls_before"],
                    "after": entry["rng_calls_after"],
                }
                for entry in events
            ],
        }
    except (GameDriveError, DecisionUnsatisfied, BridgeLaunchError, TwinReplayDivergence) as exc:
        failure = f"{type(exc).__name__}: {exc}"

    process = None
    popen = getattr(proc, "popen", None)
    if popen is not None and getattr(popen, "pid", None) is not None:
        process = read_process_identity(popen.pid, role=role, command=plan_command)
    if failure is not None and terminal.get("complete") is not True:
        terminal = {
            "kind": "FAILED",
            "complete": False,
            "reason": failure,
        }
    return TwinRun(
        role=role,
        candidate=candidate,
        fixture_identity=fixture_identity,
        candidate_build=candidate_build,
        lab_source=lab_source,
        process=process,
        rules_rng=rules_rng,
        decisions=decisions,
        semantic_events=events,
        checkpoint_state_hashes=checkpoints,
        terminal=terminal,
        process_local_identifiers={
            "game_id": game_id,
            "created_player_count": created_player_count,
            "start_status": start_status,
        },
        failure=failure,
        limitations=run_limitations,
    )


def _state_is_game_over(state: Mapping[str, Any] | None) -> bool:
    """Read the engine's own terminal marker; never infer one from a draw count."""
    if not isinstance(state, Mapping):
        return False
    if state.get("game_over") is True:
        return True
    status = str(state.get("status") or "").strip().lower()
    return status in {"finished", "complete", "game_over", "ended"}


def _read_generic_state(proc: Any, game_id: str, *, observer: str | None) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    if observer is not None:
        params["observer_player_id"] = observer
    try:
        payload = _payload(proc.request("get_game_state", params, game_id=game_id, timeout_s=60.0))
    except Exception:
        return None
    state = payload.get("state")
    if isinstance(state, dict):
        state = dict(state)
        if "game_over" not in state:
            state["game_over"] = payload.get("game_over")
        if state.get("game_over") is None and isinstance(payload.get("bridge"), dict):
            state["game_over"] = payload["bridge"].get("game_over")
        return state
    return None


def _terminal_document(state: Mapping[str, Any] | None, *, complete: bool) -> dict[str, Any]:
    checkpoint = _state_checkpoint(state)
    return {
        "kind": "GAME_OVER" if complete else "NONE",
        "complete": bool(complete),
        "game_over": True,
        "state_digest": checkpoint.get("public_state_digest"),
        "rng_calls": checkpoint.get("rng_calls"),
        "rng_root_seed": checkpoint.get("rng_root_seed"),
        "event_offset": checkpoint.get("event_offset"),
        "phase": checkpoint.get("phase"),
        "step": checkpoint.get("step"),
        "outcomes": _terminal_outcomes(state),
    }


def run_generic_lane_twin(
    *,
    candidate: str = "forge",
    player_count: int = 4,
    seed: int = 424242,
    fixture_id: str | None = None,
    xmage_workspace: Path | None = None,
    forge_workspace: Path | None = None,
    max_decisions: int = 6000,
    deck_payloads: Sequence[Mapping[str, Any]] | None = None,
    concede_after_decisions: int | None = None,
) -> tuple[TwinRun, TwinRun, TwinComparison]:
    """Run the two-process generic-lane twin for one candidate/fixture.

    Only the Forge lane currently publishes the cross-process semantic option
    identity this contract requires; an attempt on another candidate fails
    closed with the exact missing channel.
    """
    if candidate != "forge":
        raise TwinChannelUnavailable(
            "semantic_option_identity",
            f"the {candidate} generic Protocol-2 lane does not publish a cross-process "
            "semantic option identity for externally supplied replay",
            evidence_channel=_fingerprint_channel(candidate),
        )
    resolved_fixture = fixture_id or GENERIC_LANE_FIXTURE_TEMPLATE.format(
        candidate=candidate, player_count=player_count
    )
    # The guard above established that only the Forge lane is supported here.
    plan = build_launch_plan(
        "forge",
        xmage_workspace=xmage_workspace,
        forge_workspace=forge_workspace,
    )
    lab_source = _lab_source_identity()
    record_game_id = f"af09-{candidate}-{player_count}p-record-{os.getpid()}"
    record_proc = launch(plan)
    try:
        record = gather_generic_lane_process(
            record_proc,
            role="RECORD",
            candidate=candidate,
            player_count=player_count,
            seed=seed,
            fixture_id=resolved_fixture,
            game_id=record_game_id,
            plan_command=plan.argv,
            build_identity=dict(plan.build_identity),
            expected_engine_commit=plan.expected_engine_commit,
            lab_source=lab_source,
            decision_tape=None,
            max_decisions=max_decisions,
            deck_payloads=deck_payloads,
            concede_after_decisions=concede_after_decisions,
        )
    finally:
        record_proc.close()

    if record.failure is not None:
        raise ReplayTwinError(f"the recording process failed: {record.failure}")

    replay_game_id = f"af09-{candidate}-{player_count}p-replay-{os.getpid()}"
    replay_proc = launch(plan)
    try:
        replay = gather_generic_lane_process(
            replay_proc,
            role="REPLAY",
            candidate=candidate,
            player_count=player_count,
            seed=seed,
            fixture_id=resolved_fixture,
            game_id=replay_game_id,
            plan_command=plan.argv,
            build_identity=dict(plan.build_identity),
            expected_engine_commit=plan.expected_engine_commit,
            lab_source=lab_source,
            decision_tape=record.decisions,
            max_decisions=max_decisions,
            deck_payloads=deck_payloads,
            concede_after_decisions=concede_after_decisions,
        )
    finally:
        replay_proc.close()

    comparison = compare_twin_runs(record, replay)
    return record, replay, comparison


# --------------------------------------------------------------------------- #
# XMage full-game semantic tape twin adapter
# --------------------------------------------------------------------------- #


def xmage_tape_run_from_document(
    raw: Mapping[str, Any],
    *,
    role: str,
    process: ProcessIdentity | None,
    lab_source: dict[str, Any],
    candidate_build: dict[str, Any],
    fixture_identity: dict[str, Any],
) -> TwinRun:
    """Reduce one recorded XMage semantic tape to the twin run sections.

    Every field reduced here is a tape field produced by the qualified WS218
    recorder; no new state model is introduced. The event tape is the per-step
    ``event_digest`` chain, the checkpoints are the tape's own semantic state
    digests, and the Rules RNG tape is the per-step call coordinate chain.
    """
    initial = raw.get("initial_checkpoint") or {}
    steps = [step for step in (raw.get("steps") or []) if isinstance(step, Mapping)]
    terminal = raw.get("terminal_checkpoint") or {}
    decisions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = [
        {
            "sequence": 0,
            "scope": "initial",
            "semantic_state_digest": initial.get("semantic_state_digest"),
            "public_state_digest": initial.get("public_state_digest"),
            "rng_calls": initial.get("rules_random_calls"),
            "event_offset": initial.get("event_offset"),
            "turn_number": initial.get("turn_number"),
        }
    ]
    rng_coordinates: list[dict[str, Any]] = []
    for step in steps:
        sequence = step.get("sequence")
        decisions.append(
            {
                "sequence": sequence,
                "step_kind": step.get("step_kind"),
                "decision_class": step.get("decision_class"),
                "actor_principal": step.get("actor_principal"),
                "decision_revision": step.get("decision_revision"),
                "selected_fingerprints": step.get("selected_fingerprints"),
                "selected_labels": step.get("selected_labels"),
                "numeric_choice": step.get("numeric_choice"),
                "legal_set_size": step.get("legal_set_size"),
            }
        )
        events.append(
            {
                "sequence": sequence,
                "step_kind": step.get("step_kind"),
                "decision_class": step.get("decision_class"),
                "actor_principal": step.get("actor_principal"),
                "event_digest": step.get("event_digest"),
                "rng_calls_before": step.get("rng_calls_before"),
                "rng_calls_after": step.get("rng_calls_after"),
                "event_offset_before": step.get("event_offset_before"),
                "event_offset_after": step.get("event_offset_after"),
            }
        )
        checkpoints.append(
            {
                "sequence": sequence,
                "scope": "post",
                "semantic_state_digest": step.get("post_checkpoint_digest"),
                "rng_calls": step.get("rng_calls_after"),
                "event_offset": step.get("event_offset_after"),
            }
        )
        rng_coordinates.append(
            {
                "sequence": sequence,
                "before": step.get("rng_calls_before"),
                "after": step.get("rng_calls_after"),
            }
        )
    outcomes = terminal.get("outcomes")
    normalized_outcomes = []
    if isinstance(outcomes, list):
        for item in outcomes:
            if isinstance(item, Mapping):
                normalized_outcomes.append(
                    {
                        "seat": item.get("seat"),
                        "life": item.get("life"),
                        "lost": bool(item.get("lost")),
                        "won": bool(item.get("won")),
                        "left": bool(item.get("left")),
                    }
                )
        normalized_outcomes.sort(key=lambda entry: (entry["seat"] is None, entry["seat"]))
    rng_contract = raw.get("rng_contract") or {}
    manifest = raw.get("game_manifest") or {}
    initial = raw.get("initial_checkpoint") or {}
    seed_acknowledged = bool(
        manifest.get("rules_seed") is not None
        and initial.get("rules_seed") == manifest.get("rules_seed")
        and rng_contract.get("root_rules_seed") == manifest.get("rules_seed")
    )
    return TwinRun(
        role=role,
        candidate="xmage",
        fixture_identity={
            **fixture_identity,
            "tape_schema_version": raw.get("schema_version"),
            "rules_seed": manifest.get("rules_seed"),
            "player_count": manifest.get("player_count"),
            "commander_identities": manifest.get("commander_identities"),
        },
        candidate_build=candidate_build,
        lab_source=lab_source,
        process=process,
        rules_rng={
            "requested_seed": manifest.get("rules_seed"),
            "acknowledged_seed": initial.get("rules_seed"),
            "classification": (
                "ACKNOWLEDGED_ENGINE_SEED" if seed_acknowledged else "UNCONTROLLED_ENGINE_RNG"
            ),
            "controlled": seed_acknowledged,
            "rng_credit": bool(seed_acknowledged and rng_contract.get("rules_seed_explicit")),
            "root_rules_seed": rng_contract.get("root_rules_seed"),
            "require_explicit_seed": rng_contract.get("require_explicit_seed"),
            "rng_call_coordinates": rng_coordinates,
        },
        decisions=decisions,
        semantic_events=events,
        checkpoint_state_hashes=checkpoints,
        terminal={
            "kind": "GAME_OVER",
            "complete": bool(raw.get("terminal_checkpoint")),
            "game_over": bool(raw.get("terminal_checkpoint")),
            "turn_number": terminal.get("turn_number"),
            "rng_calls": terminal.get("rules_random_calls"),
            "state_digest": terminal.get("semantic_state_digest"),
            "terminal_digest": (raw.get("seal") or {}).get("terminal_digest"),
            "outcomes": normalized_outcomes,
        },
        process_local_identifiers={
            "tape_id": raw.get("tape_id"),
            "engine_game_id": ((raw.get("initial_checkpoint") or {}).get("engine_game_id")),
        },
        limitations=[],
    )


def run_xmage_tape_twin(
    *,
    scenario: Any,
    decks: tuple[Any, ...],
    pilots: tuple[Any, ...],
    command: Sequence[str],
    cwd: str | Path | None,
    work_dir: Path,
    max_decisions: int = 120,
) -> tuple[
    TwinRun,
    TwinRun,
    TwinComparison,
    dict[str, Any],
    dict[str, Any],
    list[ProcessIdentity],
]:
    """Record two fresh-process tapes, compare them, and consume the first.

    The recorder and consumer are the qualified WS218 surfaces; this function
    only binds process identities, reduces the tapes to the twin sections, and
    runs the semantic comparison and fresh-process consumption. It returns
    ``(run_a, run_b, comparison, replay_check, tape_comparison, processes)``
    where ``replay_check`` is the fresh consumer's own verdict and
    ``tape_comparison`` additionally carries the WS218 tape comparison and the
    process-distinctness record. Two recordings are required: a single
    recording compared with itself is not a twin.
    """
    from commander_lab.semantic_replay import comparator, consumer, recorder

    wrapper = _write_pid_wrapper(work_dir)
    paths: list[Path] = []
    processes: list[ProcessIdentity] = []
    runs: list[TwinRun] = []
    provider_probe, probe_identity = _probe_full_game_provider(
        command, cwd=cwd, wrapper=wrapper, work_dir=work_dir
    )
    build_identity = {
        "module": "engine-bridge",
        "lane": "full-game",
        "provider": provider_probe,
        "provider_probe_process": (
            probe_identity.to_document() if probe_identity is not None else None
        ),
        "command": [str(part) for part in command],
        "command_sha256": sha256_json([str(part) for part in command]),
    }
    lab_source = _lab_source_identity()
    fixture_identity = {
        "fixture_id": str(getattr(scenario, "scenario_id", "xmage-tape-twin")),
        "candidate": "xmage",
    }
    for index in range(2):
        role = "RECORD_FIRST" if index == 0 else "RECORD_SECOND"
        pidfile = work_dir / f"{role.lower()}.pid"
        wrapped = (str(wrapper), str(pidfile), *[str(part) for part in command])
        output = work_dir / f"{role.lower()}.tape.json"
        recorder.record_tape(
            scenario=scenario,
            decks=decks,
            pilots=pilots,
            command=wrapped,
            output_path=output,
            cwd=cwd,
            max_decisions=max_decisions,
        )
        identity = read_pidfile_identity(pidfile, role=role, command=command)
        processes.append(identity)
        raw = json.loads(output.read_text(encoding="utf-8"))
        runs.append(
            xmage_tape_run_from_document(
                raw,
                role=role,
                process=identity,
                lab_source=lab_source,
                candidate_build=build_identity,
                fixture_identity=fixture_identity,
            )
        )
        paths.append(output)

    raw_a = json.loads(paths[0].read_text(encoding="utf-8"))
    raw_b = json.loads(paths[1].read_text(encoding="utf-8"))
    tape_comparison = comparator.compare_tapes(raw_a, raw_b)
    comparison = compare_twin_runs(runs[0], runs[1])
    first_divergence = tape_comparison.divergence
    comparison_document: dict[str, Any] = {
        "tape_comparison_match": bool(tape_comparison.match),
        "compared_steps": int(tape_comparison.compared_steps),
        "first_divergence_kind": (
            first_divergence.kind.value if first_divergence is not None else None
        ),
    }

    # Fresh-process consumption of the first tape.
    replay_pidfile = work_dir / "replay.pid"
    replay_wrapped = (str(wrapper), str(replay_pidfile), *[str(part) for part in command])
    replay_check: dict[str, Any] = {"pass": False, "detail": "no consumer verdict"}
    try:
        verdict = consumer.replay_tape(paths[0], command=replay_wrapped, cwd=cwd)
        replay_check = {
            "pass": bool(verdict.get("pass")),
            "detail": f"{verdict.get('steps_verified')} steps re-derived in a fresh process",
            "steps_verified": verdict.get("steps_verified"),
            "tape_id": verdict.get("tape_id"),
        }
    except Exception as exc:  # a divergence is evidence, never a crash
        from commander_lab.semantic_replay.divergence import ReplayDivergence

        if isinstance(exc, ReplayDivergence):
            replay_check = {
                "pass": False,
                "detail": f"fresh-process replay diverged: {exc}",
                "divergence_class": exc.divergence.value,
            }
        else:
            raise
    finally:
        consumer_identity = read_pidfile_identity(
            replay_pidfile, role="REPLAY_CONSUMER", command=command
        )
        processes.append(consumer_identity)

    comparison_document["fresh_process_engine_check"] = replay_check
    comparison_document["process_identities_distinct"] = process_identities_distinct(processes)[0]
    comparison_document["process_identity_detail"] = process_identities_distinct(processes)[1]
    return runs[0], runs[-1], comparison, replay_check, comparison_document, processes


def _probe_full_game_provider(
    command: Sequence[str],
    *,
    cwd: str | Path | None,
    wrapper: Path,
    work_dir: Path,
) -> tuple[dict[str, Any], ProcessIdentity | None]:
    """Launch one fresh full-game process and read its provider identity.

    This is an identity observation, not a twin phase: it records the artifact
    the bridge actually loaded (path, kind, sha256) and the declared engine
    commit. A failed probe is recorded as ``probe_error`` and never asserted as
    an identity.
    """
    from commander_lab.engine.rules.full_game import _RawFullGameClient

    pidfile = work_dir / "provider_probe.pid"
    wrapped = (str(wrapper), str(pidfile), *[str(part) for part in command])
    provider: dict[str, Any] = {}
    try:
        with _RawFullGameClient(wrapped, cwd=cwd) as client:
            client.request("start_engine")
            provider = dict(client.request("get_provider_version"))
    except Exception as exc:  # identity observation must not mask the twin
        provider = {"probe_error": f"{type(exc).__name__}: {exc}"}
    identity = (
        read_pidfile_identity(pidfile, role="PROVIDER_PROBE", command=command)
        if pidfile.exists()
        else None
    )
    return provider, identity


def _write_pid_wrapper(work_dir: Path) -> Path:
    """Write the exec-wrapper that captures the engine pid before exec.

    The wrapper replaces itself with the engine via ``exec``, so the recorded
    pid is the engine's own pid, and the recorded start ticks/boot id are read
    from ``/proc`` before the engine exists. It adds no behavior.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    wrapper = work_dir / "af09-pid-wrapper.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        "# AF09 twin process-identity capture; execs the engine unchanged.\n"
        'pidfile="$1"\n'
        "shift\n"
        "start=$(awk '{print $22}' /proc/$$/stat 2>/dev/null)\n"
        "boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)\n"
        'printf \'%s %s %s\\n\' "$$" "$start" "$boot" > "$pidfile" || exit 1\n'
        'exec "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


__all__ = [
    "DIVERGENCE_BUILD",
    "DIVERGENCE_DECISION",
    "DIVERGENCE_EVENT",
    "DIVERGENCE_EVENT_MISSING",
    "DIVERGENCE_EVENT_REORDERED",
    "DIVERGENCE_FIXTURE",
    "DIVERGENCE_LAB_SOURCE",
    "DIVERGENCE_PROCESS_MISSING",
    "DIVERGENCE_PROCESS_NOT_DISTINCT",
    "DIVERGENCE_RNG",
    "DIVERGENCE_SECTION_MISSING",
    "DIVERGENCE_STATE",
    "DIVERGENCE_TERMINAL",
    "DIVERGENCE_TERMINAL_INCOMPLETE",
    "EVIDENCE_CLASS",
    "GENERIC_LANE_FIXTURE_TEMPLATE",
    "PROCESS_LOCAL_PATHS",
    "REQUIRED_TWIN_SECTIONS",
    "SCHEMA_VERSION",
    "NormalizationContractError",
    "NormalizationRule",
    "ProcessIdentity",
    "ReplayTwinError",
    "TwinChannelUnavailable",
    "TwinComparison",
    "TwinReplayDivergence",
    "TwinRun",
    "apply_normalization",
    "clean_process_twin_document",
    "compare_twin_runs",
    "gather_generic_lane_process",
    "process_identities_distinct",
    "read_pidfile_identity",
    "read_process_identity",
    "run_adversarial_controls",
    "run_generic_lane_twin",
    "run_xmage_tape_twin",
    "sha256_json",
    "validate_normalization_rules",
    "xmage_tape_run_from_document",
]
