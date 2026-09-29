"""Production-reachable mid-game starting-state capability, consumed from the engine.

The Rules Core is the only authority here. This module is transport plus
classification, never semantics: it launches the pinned candidate's
``midgame`` Protocol-2 lane, submits decisions the engine itself offered, and
records what the engine reported. It computes no legality, no cost, no target,
no mode, no division and no outcome.

Why this module exists
----------------------
The current-boundary qualification lane classified every mid-game obligation
fail-closed against a single coarse capability bit,
``starting_state_injection_supported``. That bit is false on both production
lanes, so a consumer had exactly one statement to read even though the pinned
engine's own restoration seam publishes a per-dimension manifest describing
precisely which starting-state dimensions it can construct. This module is the
consumer that was missing: it reads the engine's own per-dimension statement,
requests an explicit frozen starting state, and reports the engine's own
construction verdict.

It refuses to promote anything. A row is only ever reported as
``ENGINE_NATIVE_REACHABLE`` when the engine accepted the explicit starting state
and the engine's own field-level readback compare produced no mismatch outside
the documented declaration-step priority allowance. Everything else is reported
with the engine's own rejection code and stays fail-closed.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PROTOCOL_VERSION = "2.0.0"
MIDGAME_LANE = "xmage_midgame_native_starting_state"

# Field prefixes the engine's readback may legitimately report differently at a
# declaration checkpoint. During a declaration step the engine does not hold
# priority the way the readback reports it, so ``priority_player`` may read as
# the next seat. This allowance is the engine seam's own documented arrival
# semantics, not a Lab relaxation: anything outside these prefixes is a real
# construction defect and fails the lane.
DECLARATION_STEP_PRIORITY_ALLOWANCE = ("priority_player:", "priority ")

Outcome = Literal[
    "ENGINE_NATIVE_REACHABLE",
    "ENGINE_STATE_ACCEPTED",
    "CAUSAL_ROUTE_REACHABLE",
    "CAUSAL_ROUTE_MEASURED_BLOCKED",
    "CONSTRUCTION_MISMATCH",
    "ENGINE_REJECTED",
    "TRANSPORT_FAILURE",
]


class MidgameLaneError(RuntimeError):
    """The mid-game lane could not be launched or answered."""


@dataclass(frozen=True)
class DimensionManifest:
    """The engine's own per-dimension starting-state statement.

    ``global_supported`` stays the coarse bit the engine publishes for a
    globally complete injection of arbitrary states. It is deliberately not
    treated as the capability answer; ``per_dimension_supported`` plus the
    enumerated lists are.
    """

    schema_version: str
    global_supported: bool
    per_dimension_supported: bool
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "global_supported": self.global_supported,
            "per_dimension_supported": self.per_dimension_supported,
            "supported_dimensions": list(self.supported),
            "unsupported_dimensions": list(self.unsupported),
        }


@dataclass(frozen=True)
class RowVerdict:
    """One row's engine-reported reachability, with the engine's own evidence.

    ``construction_match`` is the engine's own raw field-level verdict, kept
    verbatim. ``outcome`` applies the one documented allowance — priority is not
    held the way the readback reports it during a declaration step — and is
    derived only from the mismatches outside that allowance. Both are reported
    so a reviewer can see the raw engine bit and the classification side by side;
    neither is hidden inside the other.
    """

    fixture_id: str
    outcome: Outcome
    code: str | None
    detail: str | None
    construction_match: bool | None
    mismatches: tuple[str, ...]
    requested_state_digest: str | None
    constructed_state_digest: str | None
    lane: str
    engine_commit: str | None
    allowance_applied: tuple[str, ...] = ()
    engine_accepted_starting_state: bool = False
    entry_mode: str = "placement"
    causal_verdict: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "outcome": self.outcome,
            "engine_accepted_starting_state": self.engine_accepted_starting_state,
            "code": self.code,
            "detail": self.detail,
            "engine_construction_match": self.construction_match,
            "mismatches": list(self.mismatches),
            "declaration_step_priority_allowance_applied": list(self.allowance_applied),
            "entry_mode": self.entry_mode,
            "causal_verdict": self.causal_verdict,
            "requested_state_digest": self.requested_state_digest,
            "constructed_state_digest": self.constructed_state_digest,
            "lane": self.lane,
            "engine_commit": self.engine_commit,
        }


class MidgameLaneClient:
    """One isolated mid-game session over the pinned engine's Protocol 2.0.0."""

    def __init__(self, argv: tuple[str, ...], cwd: Path) -> None:
        self._argv = argv
        self._cwd = cwd
        self._process: subprocess.Popen[str] | None = None
        self._engine_commit: str | None = None
        self._tape: list[dict[str, Any]] = []
        self.manifest: DimensionManifest | None = None

    # -- transport ---------------------------------------------------

    def __enter__(self) -> MidgameLaneClient:
        try:
            self._process = subprocess.Popen(
                list(self._argv),
                cwd=str(self._cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise MidgameLaneError(f"cannot launch the mid-game lane: {exc}") from exc
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._process is None:
            return
        process = self._process
        self._process = None
        with contextlib.suppress(MidgameLaneError):
            self.request("shutdown_engine", {})
        if process.stdin is not None:
            with contextlib.suppress(OSError):
                process.stdin.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()

    def request(
        self,
        message_type: str,
        payload: dict[str, Any] | None,
        *,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]:
        """Send exactly one Protocol-2 request and return the parsed response.

        A failed or malformed provider response is returned verbatim, including
        its error code. It is never converted into a success, a default or a
        pass.
        """
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise MidgameLaneError("the mid-game lane process is not running")
        envelope: dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": f"{message_type}-{uuid.uuid4()}",
            "message_type": message_type,
        }
        if payload is not None:
            envelope["payload"] = payload
            envelope["params"] = payload
        line = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        try:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise MidgameLaneError(f"mid-game lane stdin unavailable: {exc}") from exc
        raw = self._process.stdout.readline()
        if not raw:
            stderr = ""
            if self._process.stderr is not None:
                stderr = self._process.stderr.read()[-2000:]
            raise MidgameLaneError(
                f"mid-game lane closed stdout for {message_type} (stderr tail: {stderr})"
            )
        parsed: dict[str, Any]
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MidgameLaneError(f"non-JSON mid-game response: {raw[:200]!r}") from exc
        if not isinstance(decoded, dict):
            raise MidgameLaneError(f"mid-game response is not a JSON object: {raw[:200]!r}")
        parsed = decoded
        entry = {"message_type": message_type, "request": envelope, "response": parsed}
        self._tape.append(entry)
        if message_type == "get_provider_version" and parsed.get("success"):
            payload_obj = parsed.get("payload") or {}
            if isinstance(payload_obj, dict):
                commit = payload_obj.get("engine_commit")
                self._engine_commit = commit if isinstance(commit, str) else None
        return parsed

    @property
    def tape(self) -> list[dict[str, Any]]:
        return self._tape

    @property
    def engine_commit(self) -> str | None:
        return self._engine_commit

    # -- capability --------------------------------------------------

    def read_dimension_manifest(self) -> DimensionManifest:
        """Read the engine's own per-dimension starting-state statement."""
        response = self.request("get_capabilities", None)
        if not response.get("success"):
            code = _error_code(response)
            raise MidgameLaneError(f"get_capabilities failed closed: {code}")
        capabilities = (response.get("payload") or {}).get("capabilities") or {}
        manifest = capabilities.get("starting_state_dimensions")
        if not isinstance(manifest, dict):
            raise MidgameLaneError(
                "the engine published no per-dimension starting-state manifest; this is the "
                "unconsumed-capability condition and it must fail closed rather than fall back "
                "to the coarse global flag"
            )
        self.manifest = DimensionManifest(
            schema_version=str(manifest.get("schema_version", "")),
            global_supported=bool(capabilities.get("starting_state_injection_supported")),
            per_dimension_supported=bool(capabilities.get("starting_state_dimensions_supported")),
            supported=tuple(manifest.get("supported_dimensions") or ()),
            unsupported=tuple(manifest.get("unsupported_dimensions") or ()),
            raw=manifest,
        )
        return self.manifest

    # -- decisions ---------------------------------------------------

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        """Return the exact currently pending engine decision, or None."""
        import time

        for _ in range(attempts):
            response = self.request("get_midgame_decision", None)
            if not response.get("success"):
                code = _error_code(response)
                if (
                    code == "midgame_decision_failed"
                    and "TERMINAL" in str(_error_message(response)).upper()
                ):
                    return None
                raise MidgameLaneError(f"get_midgame_decision failed closed: {code}")
            payload = response.get("payload")
            if isinstance(payload, dict):
                decision = payload.get("decision")
                if isinstance(decision, dict) and decision:
                    return decision
            time.sleep(interval_s)
        return None

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> dict[str, Any]:
        """Submit exact engine-offered option ids for the pending decision.

        The caller selects from the engine's own ``legal_options``. This method
        never substitutes an option, and an empty selection is rejected by the
        engine rather than defaulted here.

        Numeric fields are sent only when the pending frame's own context
        authorizes them. The engine treats a numeric vector on a frame without
        joint numeric legs as schema confusion and fails it closed, so a client
        that always sends them is rejected for a transport reason rather than
        for its answer.
        """
        response: dict[str, Any] = {
            "decision_id": decision["decision_id"],
            "actor_id": decision["actor_id"],
            "selected_option_ids": list(option_ids),
            "ordering": [],
        }
        context = decision.get("context")
        if isinstance(context, dict):
            if context.get("numeric_min") is not None and context.get("numeric_max") is not None:
                response["numeric_choice"] = None
            if isinstance(context.get("numeric_legs"), list):
                response["numeric_choices"] = None
        result = self.request("submit_midgame_decision", {"response": response})
        if not result.get("success"):
            raise MidgameLaneError(
                f"the engine rejected the submitted decision: {_error_code(result)} "
                f"{_error_message(result)}"
            )
        return result.get("payload") or {}

    def complete_arrival(self) -> dict[str, Any]:
        """Ask the engine for its post-arrival completion and construction verdict.

        While the engine is parked on a decision this is a pure query: it runs
        the engine's own commander cast-count restore, revalidation, native
        readback and field-level compare, and answers no decision.
        """
        response = self.request("complete_midgame_arrival", {})
        if not response.get("success"):
            raise MidgameLaneError(
                f"complete_midgame_arrival failed closed: {_error_code(response)}"
            )
        return response.get("payload") or {}

    def zone_counts(self, actor_id: str) -> dict[str, Any]:
        """Principal-scoped public-zone counts for exactly one principal."""
        response = self.request("get_midgame_state", {"actor_id": actor_id})
        if not response.get("success"):
            raise MidgameLaneError(f"get_midgame_state failed closed: {_error_code(response)}")
        return response.get("payload") or {}


def _error_code(response: dict[str, Any]) -> str | None:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            value = first.get("code")
            return value if isinstance(value, str) else None
    return None


def _error_message(response: dict[str, Any]) -> str:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            value = first.get("message")
            return value if isinstance(value, str) else ""
    return ""


def classification_from_arrival(
    fixture_id: str,
    lane: str,
    arrival: dict[str, Any],
    *,
    engine_commit: str | None,
) -> RowVerdict:
    """Classify the engine's own construction verdict for one row.

    The decision is entirely the engine's. A row is reachable only when the
    engine reported no mismatch outside the documented declaration-step
    priority allowance. Nothing here relaxes a mismatch into a pass.
    """
    mismatches = tuple(str(item) for item in (arrival.get("mismatches") or ()))
    allowance = tuple(
        mismatch
        for mismatch in mismatches
        if mismatch.startswith(DECLARATION_STEP_PRIORITY_ALLOWANCE)
    )
    unexpected = tuple(mismatch for mismatch in mismatches if mismatch not in allowance)
    construction_match = bool(arrival.get("construction_match"))
    outcome: Outcome = "CONSTRUCTION_MISMATCH" if unexpected else "ENGINE_NATIVE_REACHABLE"
    return RowVerdict(
        fixture_id=fixture_id,
        outcome=outcome,
        code=None,
        detail=None if outcome == "ENGINE_NATIVE_REACHABLE" else "; ".join(unexpected),
        construction_match=construction_match,
        mismatches=mismatches,
        requested_state_digest=arrival.get("requested_state_digest"),
        constructed_state_digest=arrival.get("constructed_state_digest"),
        lane=lane,
        engine_commit=engine_commit,
        allowance_applied=allowance,
        engine_accepted_starting_state=True,
    )


def classification_from_causal_verdict(
    fixture_id: str,
    lane: str,
    entry_mode: str,
    verdict: dict[str, Any],
    terminal_obligation: dict[str, Any] | None,
    *,
    engine_commit: str | None,
) -> RowVerdict:
    """Classify the engine's own causal-route verdict for one row.

    The decision is entirely the engine's, in two separately reported parts.
    ``CAUSAL_ROUTE_REACHABLE`` requires the engine to report ``causal_match``
    with no mismatches **and** the row's terminal obligation to be observed.
    A route the engine executed but whose terminal obligation it did not
    produce — the commander-zone choice that never appears for a setup copy,
    for example — is ``CAUSAL_ROUTE_MEASURED_BLOCKED``: the causal execution
    is proven, the missing terminal is measured, and nothing is promoted. A
    route the engine did not produce is ``CONSTRUCTION_MISMATCH``. The
    engine's own verdict and the terminal record travel verbatim in the row.
    """
    mismatches = tuple(str(item) for item in (verdict.get("mismatches") or ()))
    causal_match = bool(verdict.get("causal_match"))
    outcome: Outcome
    detail: str | None
    if not causal_match or mismatches:
        outcome = "CONSTRUCTION_MISMATCH"
        detail = "; ".join(mismatches) or "the engine did not produce the causal route"
    elif terminal_obligation is None or terminal_obligation.get("observed"):
        outcome = "CAUSAL_ROUTE_REACHABLE"
        detail = None
    else:
        outcome = "CAUSAL_ROUTE_MEASURED_BLOCKED"
        detail = str(terminal_obligation.get("detail") or "terminal obligation not observed")
    combined_verdict = dict(verdict)
    if terminal_obligation is not None:
        combined_verdict["terminal_obligation"] = terminal_obligation
    return RowVerdict(
        fixture_id=fixture_id,
        outcome=outcome,
        code=None,
        detail=detail,
        construction_match=None,
        mismatches=mismatches,
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        engine_accepted_starting_state=True,
        entry_mode=entry_mode,
        causal_verdict=combined_verdict,
    )


def rejected_verdict(
    fixture_id: str,
    lane: str,
    *,
    code: str | None,
    detail: str | None,
    engine_commit: str | None,
    state_accepted: bool = False,
) -> RowVerdict:
    """Record a row the lane did not reach a verdict on, with the engine's own code.

    ``state_accepted`` separates the two genuinely different failures. When it
    is false the engine rejected the explicit starting state and the row is not
    materializable. When it is true the engine accepted the state and the lane
    simply did not execute the row's scripted obligation, which is recorded as
    ``ENGINE_STATE_ACCEPTED`` by the caller. Neither is a pass.
    """
    return RowVerdict(
        fixture_id=fixture_id,
        outcome="ENGINE_REJECTED",
        code=code,
        detail=detail,
        construction_match=None,
        mismatches=(),
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        engine_accepted_starting_state=state_accepted,
    )


def iter_frozen_records(materialization_path: Path) -> Iterator[dict[str, Any]]:
    """Yield the frozen materialization records in file order."""
    document = json.loads(materialization_path.read_text(encoding="utf-8"))
    for record in document.get("records") or ():
        if isinstance(record, dict) and record.get("fixture_id"):
            yield record


def frozen_record(materialization_path: Path, fixture_id: str) -> dict[str, Any]:
    """Return one frozen record, or fail closed when it is absent."""
    for record in iter_frozen_records(materialization_path):
        if record["fixture_id"] == fixture_id:
            return record
    raise KeyError(f"frozen materialization record missing: {fixture_id}")
