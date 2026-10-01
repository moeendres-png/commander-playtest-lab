"""AF01 v2 Protocol-handshake qualification executor (candidate-neutral).

Executes the exact current-boundary AF01 invariants against a live external
candidate bridge. Nothing here infers a capability: every capability claim is
read from the provider's own ``get_capabilities`` payload, and a missing
capability is recorded as missing rather than promoted.
"""

from __future__ import annotations

import io
import re
import tokenize
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bridge_launcher import BridgeProcess
from .game_driver import (
    DECISION_IDENTITY_SHAPES,
    GameDriveError,
    decision_identity_params,
    poll_decision,
)
from .source_lock import (
    CURRENT_QUALIFICATION_BOUNDARY,
    CURRENT_TRANSPORT_PROTOCOL,
    REQUIRED_HANDSHAKE_MESSAGES,
    SUPERSEDED_RULES_SERVICE_BOUNDARY,
)

# AF01 v2 required-handshake / fail-closed / rules-authority invariants,
# keyed by the AF01_QUALIFICATION_BOUNDARY_V2 clause they enforce.
AF01_INVARIANTS: dict[str, str] = {
    "canonical_handshake_start_engine": "required_handshake.messages[0]=start_engine",
    "canonical_handshake_get_provider_version": "required_handshake.messages[1]=get_provider_version",
    "canonical_handshake_get_capabilities": "required_handshake.messages[2]=get_capabilities",
    "protocol_version_exact": "required_handshake.exact_request_response_protocol_version",
    "request_id_matches": "required_handshake.matching_request_id",
    "provider_identity_exact": "required_handshake.exact_provider_identity",
    "engine_version_or_commit_exact": (
        "required_handshake.exact_engine_version_or_commit_identity"
    ),
    "capabilities_explicitly_reported": "required_handshake.explicit_capability_payload",
    "runtime_kind_external_rules_engine": "required_handshake.runtime_kind_external_rules_engine",
    "capabilities_provider_reported_not_inferred": (
        "truthful_capability_requirements.capability_values_must_be_provider_reported"
    ),
    "legacy_alias_handshake_not_accepted": "transport.legacy_alias_only_handshake_satisfies_af01=false",
    "fail_closed_protocol_mismatch": "fail_closed_invariants.protocol_mismatch",
    "fail_closed_unknown_message": "fail_closed_invariants.unknown_message",
    "fail_closed_illegal_action": "fail_closed_invariants.illegal_action",
    "fail_closed_stale_or_unknown_decision": "fail_closed_invariants.stale_or_unknown_decision",
    "fail_closed_unsupported_decision": (
        "fail_closed_invariants.unsupported_production_reachable_decision"
    ),
    "rules_core_sole_legality_authority": "rules_authority_invariants.rules_core_sole_legality_authority",
    "no_adapter_legality_reconstruction": (
        "rules_authority_invariants.adapter_or_pilot_legality_reconstruction_forbidden"
    ),
    "no_fabricated_legal_options": "rules_authority_invariants.fabricated_legal_options_forbidden",
    "rules_randomness_core_owned": "rules_authority_invariants.rules_randomness_core_owned",
}

# Capabilities a current-boundary provider must report truthfully for the
# Protocol-2 decision surface. Absence is recorded, never promoted.
REQUIRED_TRUTHFUL_CAPABILITIES = (
    "commander_supported",
    "multiplayer_supported",
    "headless_supported",
    "deck_import_supported",
    "legal_actions_supported",
    "action_submission_supported",
    "seed_supported",
    "event_log_supported",
)

_FAIL_CLOSED_VERDICT = {"FAILED", "UNSUPPORTED", "ERROR", "REJECTED", "TIMEOUT", "PROTOCOL_FAILURE"}


def _frame_leaves(node: Any) -> list[Any]:
    leaves: list[Any] = []
    if isinstance(node, dict):
        for value in node.values():
            leaves.extend(_frame_leaves(value))
    elif isinstance(node, list):
        for value in node:
            leaves.extend(_frame_leaves(value))
    else:
        leaves.append(node)
    return leaves


def decision_identity_provenance(candidate: str, frame: dict[str, Any] | None) -> dict[str, Any]:
    """R-2 condition on a live frame: the submitted identity comes from the frame.

    Every value ``decision_identity_params`` would submit must byte- and
    type-match a value in the frame the provider just offered, and a pass
    identity must be one of the offered ``pass_priority`` options. The shim may
    translate field names; it may never invent, derive or normalise a value.
    ``verified`` is None when no live frame was available.
    """
    if frame is None:
        return {"verified": None, "reason": "no live decision frame was available"}
    identity = decision_identity_params(candidate, frame)
    leaves = _frame_leaves(frame)
    byte_matched = {
        key: value is not None
        and any(type(leaf) is type(value) and leaf == value for leaf in leaves)
        for key, value in identity.items()
    }
    pass_identity_offered = True
    if "action_id" in identity:
        offered = [
            action.get("action_id")
            for action in frame.get("actions") or ()
            if action.get("action_type") == "pass_priority"
        ]
        pass_identity_offered = identity["action_id"] in offered
    return {
        "verified": bool(identity) and all(byte_matched.values()) and pass_identity_offered,
        "identity_field": DECISION_IDENTITY_SHAPES[candidate]["field"],
        "submitted_fields": sorted(identity),
        "byte_matched": byte_matched,
        "pass_identity_offered": pass_identity_offered,
    }


@dataclass
class InvariantResult:
    name: str
    clause: str
    verdict: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AF01Report:
    candidate: str
    lane: str
    engine_commit_reported: str | None
    engine_commit_provenance: str | None
    capabilities: dict[str, Any]
    invariants: list[InvariantResult]
    protocol_transcript_digest: str
    engine_identity: dict[str, Any] = field(default_factory=dict)
    # R-2 (SLOT-03 option (c)): the provenance of the decision identity this run
    # actually submitted, checked against the live frame the provider offered.
    decision_identity_provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if any(item.verdict == "FAIL" for item in self.invariants):
            return "FAIL"
        if any(item.verdict == "UNKNOWN" for item in self.invariants):
            return "UNKNOWN"
        return "PASS"

    def failed(self) -> list[InvariantResult]:
        return [item for item in self.invariants if item.verdict != "PASS"]

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": "wsr22.af01-current-boundary/1.0.0",
            "qualification_boundary": CURRENT_QUALIFICATION_BOUNDARY,
            "superseded_rules_service_boundary": SUPERSEDED_RULES_SERVICE_BOUNDARY,
            "transport_protocol": CURRENT_TRANSPORT_PROTOCOL,
            "candidate": self.candidate,
            "lane": self.lane,
            "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
            "engine_identity": self.engine_identity,
            "engine_commit_reported": self.engine_commit_reported,
            "engine_commit_provenance": self.engine_commit_provenance,
            "capabilities_provider_reported": self.capabilities,
            "protocol_transcript_digest": self.protocol_transcript_digest,
            "decision_identity_provenance": self.decision_identity_provenance,
            "verdict": self.verdict,
            "invariant_count": len(self.invariants),
            "invariants": [
                {
                    "invariant": item.name,
                    "af01_v2_clause": item.clause,
                    "verdict": item.verdict,
                    "detail": item.detail,
                    "evidence": item.evidence,
                }
                for item in self.invariants
            ],
            "nonclaims": [
                "AF01 PASS does not imply AF04 decision completeness",
                "AF01 PASS does not imply provider release eligibility",
                "AF01 PASS does not select a provider or claim Architecture Freeze",
            ],
        }


def _status(response: dict[str, Any]) -> str:
    return str(response.get("status", "")).upper()


# Rejection codes that mean "the request itself was malformed". Such a rejection says
# nothing about decision-time legality, so it is never credited as fail-closed (F-37).
_MALFORMED_REQUEST_CODES = {
    "malformed_request",
    "invalid_request",
    "invalid_submit_action_payload",
    "invalid_legal_actions_payload",
}


def _rejected_as_malformed(response: dict[str, Any]) -> bool:
    codes = {
        str(error.get("code")) for error in response.get("errors") or [] if isinstance(error, dict)
    }
    error = response.get("error")
    if isinstance(error, dict):
        codes.add(str(error.get("code")))
    return bool(codes & _MALFORMED_REQUEST_CODES)


def _fails_closed(response: dict[str, Any]) -> bool:
    if response.get("success") is True:
        return False
    return _status(response) in _FAIL_CLOSED_VERDICT or response.get("success") is False


# Patterns that would indicate a second, harness-side source of legality. Their
# presence in bound source is a failure of the single-Rules-authority invariant.
LEGALITY_RECONSTRUCTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bfirst_option\b", "first-option selection"),
    (r"\brandom_option\b", "random-option selection"),
    (r"\bdefault_yes\b", "default yes/no selection"),
    (r"\brequested_options\b", "requested-option filtering"),
    (r"\bfabricate_legal\w*", "fabricated legal actions"),
    (r"\bchoose_legal\w*", "harness-side legality choice"),
    (r"\binvent_legal\w*", "invented legal actions"),
)


def _code_lines(source: str) -> list[tuple[int, str]]:
    """Return (lineno, code) for real code only, with comments and strings blanked.

    A policy scan must not fire on the very documentation that states the
    policy, nor on a forbidden name that only ever appears in a docstring or
    comment. Tokenizing and blanking every COMMENT and STRING token makes the
    scan about code rather than about prose. Line numbers are preserved so a hit
    stays actionable, and unparsable source falls back to raw lines rather than
    silently passing.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return list(enumerate(source.splitlines(), start=1))
    lines = [list(line) for line in source.splitlines()]
    for tok in tokens:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        (row, col), (end_row, end_col) = tok.start, tok.end
        for line_no in range(row, end_row + 1):
            index = line_no - 1
            if not 0 <= index < len(lines):
                continue
            line = lines[index]
            start = col if line_no == row else 0
            stop = end_col if line_no == end_row else len(line)
            for offset in range(start, min(stop, len(line))):
                line[offset] = " "
    return [(number, "".join(line)) for number, line in enumerate(lines, start=1)]


def observe_no_legality_reconstruction(runner_root: Path) -> dict[str, Any]:
    """Scan the executing runner for a second source of legality.

    This is a real observation, not an assertion: it reads the bound source that
    is about to produce evidence and reports exactly what it found. A previously
    unconditional PASS is now derived from this scan, and the scan result is
    carried as evidence so the verdict is auditable. Absence of a pattern is
    weaker than presence of correct behaviour, so the detail says so.
    """
    hits: list[dict[str, str]] = []
    scanned: list[str] = []
    for rel in sorted(
        p.relative_to(runner_root).as_posix()
        for p in (runner_root / "src/commander_lab/qualification/current_boundary").rglob("*.py")
    ):
        scanned.append(rel)
        for lineno, code in _code_lines(
            (runner_root / rel).read_text(encoding="utf-8", errors="replace")
        ):
            for pattern, label in LEGALITY_RECONSTRUCTION_PATTERNS:
                if re.search(pattern, code):
                    hits.append({"file": rel, "line": str(lineno), "pattern": label})
    return {
        "scanned_files": len(scanned),
        "hits": hits,
        "complete": bool(scanned),
    }


def run_af01(
    proc: BridgeProcess,
    *,
    candidate: str,
    expected_commit: str,
    runner_commit: str,
    runner_tree: str,
    game_id: str | None = None,
    runner_root: Path | None = None,
    seat_count: int = 2,
) -> AF01Report:
    """Execute the AF01 v2 invariants against a live candidate bridge.

    ``game_id`` must name a live game. Decision-time invariants are only
    credited against a real game: a provider asked to fail closed on a
    submission for a game that does not exist will refuse for reasons that have
    nothing to do with decision-time legality, so crediting that as evidence
    would be a pass for the wrong reason.
    """
    if not game_id:
        raise ValueError(
            "run_af01 requires a live game_id. Decision-time invariants must be "
            "observed against a real game or they are UNKNOWN, not PASS."
        )
    results: list[InvariantResult] = []

    def add(name: str, verdict: str, detail: str, evidence: dict[str, Any] | None = None) -> None:
        results.append(
            InvariantResult(
                name=name,
                clause=AF01_INVARIANTS[name],
                verdict=verdict,
                detail=detail,
                evidence=evidence or {},
            )
        )

    # --- canonical handshake -------------------------------------------
    payloads: dict[str, dict[str, Any]] = {}
    request_ids: dict[str, str] = {}
    mismatched_ids: list[str] = []
    bad_protocol: list[str] = []
    handshake_ok: dict[str, bool] = {}

    for message in REQUIRED_HANDSHAKE_MESSAGES:
        rid = str(uuid.uuid4())
        request_ids[message] = rid
        response = proc.request(message, {}, request_id=rid)
        payloads[message] = response
        ok = response.get("success") is True
        handshake_ok[message] = ok
        name = f"canonical_handshake_{message}"
        if not ok:
            add(name, "FAIL", f"handshake message failed: {response.get('status')}", response)
        else:
            add(name, "PASS", f"{message} succeeded under protocol 2.0.0", {"status": "ok"})
        if response.get("request_id") != rid:
            mismatched_ids.append(message)
        if str(response.get("protocol_version", "")) != CURRENT_TRANSPORT_PROTOCOL:
            bad_protocol.append(message)

    if handshake_ok.get("start_engine") and handshake_ok.get("get_provider_version"):
        add(
            "request_id_matches",
            "FAIL" if mismatched_ids else "PASS",
            f"mismatched request_ids: {mismatched_ids}"
            if mismatched_ids
            else "every response echoed the exact request_id",
            {"request_ids": request_ids},
        )
        add(
            "protocol_version_exact",
            "FAIL" if bad_protocol else "PASS",
            f"protocol_version mismatches: {bad_protocol}"
            if bad_protocol
            else f"every response reported protocol_version={CURRENT_TRANSPORT_PROTOCOL}",
            {"observed": {m: payloads[m].get("protocol_version") for m in payloads}},
        )
    else:
        add("request_id_matches", "UNKNOWN", "handshake did not complete; ids unverifiable")
        add("protocol_version_exact", "UNKNOWN", "handshake did not complete; version unverifiable")

    version_payload = payloads.get("get_provider_version", {}).get("payload", {})
    capabilities_payload = payloads.get("get_capabilities", {}).get("payload", {})
    capabilities = capabilities_payload.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    full_game_lane = capabilities_payload.get("full_game_lane")
    if isinstance(full_game_lane, dict):
        capabilities = {
            **capabilities,
            **{f"full_game_lane.{k}": v for k, v in full_game_lane.items()},
        }

    reported_commit = version_payload.get("engine_commit")
    reported_provider = version_payload.get("engine") or version_payload.get("provider")
    engine_identity = {
        "reported_provider": reported_provider,
        "reported_engine_version": version_payload.get("engine_version")
        or version_payload.get("release"),
        "reported_engine_commit": reported_commit,
        "reported_protocol_version": version_payload.get("protocol_version"),
        "engine_commit_source": version_payload.get("engine_commit_source")
        or version_payload.get("xmage_code_source"),
        "start_engine_payload": payloads.get("start_engine", {}).get("payload", {}),
        "get_provider_version_payload": version_payload,
    }

    expected_provider = "xmage" if candidate == "xmage" else "forge"
    if reported_provider == expected_provider:
        add(
            "provider_identity_exact",
            "PASS",
            f"provider reported as {expected_provider!r}",
            {"reported": reported_provider},
        )
    elif reported_provider is None:
        add("provider_identity_exact", "UNKNOWN", "provider identity absent from provider_version")
    else:
        add(
            "provider_identity_exact",
            "FAIL",
            f"expected {expected_provider!r}, provider reported {reported_provider!r}",
            {"reported": reported_provider},
        )

    if reported_commit == expected_commit:
        add(
            "engine_version_or_commit_exact",
            "PASS",
            f"provider reported the exact candidate commit {expected_commit}",
            {"reported": reported_commit},
        )
    elif reported_commit is None:
        add("engine_version_or_commit_exact", "UNKNOWN", "no engine commit reported")
    else:
        add(
            "engine_version_or_commit_exact",
            "FAIL",
            f"expected {expected_commit}, provider reported {reported_commit}",
            {"reported": reported_commit},
        )

    if capabilities:
        add(
            "capabilities_explicitly_reported",
            "PASS",
            f"provider reported {len(capabilities)} capability fields",
            {"capability_keys": sorted(capabilities)},
        )
        add(
            "capabilities_provider_reported_not_inferred",
            "PASS",
            "every capability value was read from the provider get_capabilities payload; "
            "no value was derived from the provider name",
            {"sampled": {k: capabilities.get(k) for k in REQUIRED_TRUTHFUL_CAPABILITIES}},
        )
    else:
        add("capabilities_explicitly_reported", "FAIL", "no capability payload reported")
        add(
            "capabilities_provider_reported_not_inferred",
            "FAIL",
            "capabilities absent; inference is forbidden",
        )

    runtime_kind = (
        capabilities_payload.get("runtime_kind")
        or capabilities_payload.get("kind")
        or capabilities.get("runtime_kind")
    )
    if runtime_kind == "external_rules_engine":
        add(
            "runtime_kind_external_rules_engine",
            "PASS",
            "provider reported runtime_kind",
            {"runtime_kind": runtime_kind},
        )
    elif runtime_kind is None:
        add(
            "runtime_kind_external_rules_engine",
            "UNKNOWN",
            "provider did not report runtime_kind in the handshake payload",
        )
    else:
        add(
            "runtime_kind_external_rules_engine",
            "FAIL",
            f"provider reported runtime_kind={runtime_kind!r}",
            {"runtime_kind": runtime_kind},
        )

    # --- legacy alias handshake must not satisfy AF01 -------------------
    alias_evidence: dict[str, Any] = {}
    legacy_used = False
    try:
        legacy = proc.request("engine_hello", {})
        alias_evidence["engine_hello"] = legacy
        legacy_used = legacy.get("success") is True
    except Exception as exc:
        alias_evidence["engine_hello_error"] = str(exc)
    # This used to be an unconditional PASS asserting AF01's own accounting.
    # It is now derived from the data actually used: credit-bearing payloads are
    # the canonical protocol-2 responses, so the invariant holds only if the
    # legacy alias response is absent from them and the probe actually ran.
    alias_in_credit = "engine_hello" in payloads
    alias_probed = "engine_hello" in alias_evidence or "engine_hello_error" in alias_evidence
    if not alias_probed:
        alias_verdict = "UNKNOWN"
        alias_detail = "the legacy alias was never probed, so its exclusion is unproven"
    elif alias_in_credit:
        alias_verdict = "FAIL"
        alias_detail = "a legacy alias response reached the credit-bearing payload set"
    else:
        alias_verdict = "PASS"
        alias_detail = (
            "the legacy alias handshake was probed and its response recorded, and the "
            "credit-bearing payload set contains only the canonical protocol-2 responses"
        )
    add(
        "legacy_alias_handshake_not_accepted",
        alias_verdict,
        alias_detail,
        {
            "legacy_alias_responded": legacy_used,
            "legacy_alias_in_credit_set": alias_in_credit,
            "credit_bearing_messages": sorted(payloads),
            **alias_evidence,
        },
    )

    # --- fail-closed invariants ----------------------------------------
    mismatch = proc.request("get_capabilities", {}, protocol_version="1.1.0")
    add(
        "fail_closed_protocol_mismatch",
        "PASS" if _fails_closed(mismatch) else "FAIL",
        "provider rejected a wrong protocol_version without success"
        if _fails_closed(mismatch)
        else "provider accepted a wrong protocol_version",
        mismatch,
    )

    unknown = proc.request("wsr22_definitely_not_a_message", {})
    add(
        "fail_closed_unknown_message",
        "PASS" if _fails_closed(unknown) else "FAIL",
        "provider rejected an unknown message type"
        if _fails_closed(unknown)
        else "provider accepted an unknown message type",
        unknown,
    )

    # Decision-time probes (F-37). They are scoped to the live game and built from
    # the decision the provider actually published: the envelope, actor and decision
    # identity are real and well formed, and exactly one field is wrong per probe. A
    # provider that rejects a probe for an unrelated reason (a malformed envelope)
    # demonstrates nothing about the invariant, so such a rejection is UNKNOWN, not
    # PASS. After every probe the pending decision is read again: a changed decision
    # identity is a game mutation and fails the invariant.
    probe_frame: dict[str, Any] | None = None
    probe_error: str | None = None
    try:
        probe_frame = poll_decision(proc, game_id, seat_count=seat_count, candidate=candidate)
    except GameDriveError as exc:
        probe_error = str(exc)

    def _decision_unchanged(identity: dict[str, Any]) -> bool | None:
        try:
            again = poll_decision(proc, game_id, seat_count=seat_count, candidate=candidate)
        except GameDriveError:
            return None
        field_name = DECISION_IDENTITY_SHAPES[candidate]["field"]
        return decision_identity_params(candidate, again).get(field_name) == identity.get(
            field_name
        )

    def _probe(
        name: str, response: dict[str, Any], unchanged: bool | None, what: str
    ) -> dict[str, Any]:
        evidence = {"game_id": game_id, "response": response, "decision_unchanged": unchanged}
        if not _fails_closed(response):
            add(name, "FAIL", f"provider accepted {what} for a live game", evidence)
        elif _rejected_as_malformed(response):
            add(
                name,
                "UNKNOWN",
                f"provider rejected {what} as a malformed request, which does not "
                "demonstrate the invariant",
                evidence,
            )
        elif unchanged is False:
            add(name, "FAIL", f"{what} changed the pending decision", evidence)
        elif unchanged is None:
            add(name, "UNKNOWN", "the pending decision could not be re-read", evidence)
        else:
            add(name, "PASS", f"provider rejected {what} for a live game, no mutation", evidence)
        return response

    illegal: dict[str, Any] = {}
    if probe_frame is None:
        for name in (
            "fail_closed_illegal_action",
            "fail_closed_stale_or_unknown_decision",
            "fail_closed_unsupported_decision",
        ):
            add(name, "UNKNOWN", f"no pending decision to probe: {probe_error}")
    else:
        identity = decision_identity_params(candidate, probe_frame)
        actor = probe_frame["decision"]["actor"]
        pass_ids = [
            action.get("action_id")
            for action in probe_frame["actions"]
            if action.get("action_type") == "pass_priority"
        ]

        illegal = proc.request(
            "submit_action",
            {
                "game_id": game_id,
                **identity,
                "proposal": {
                    "proposal_id": str(uuid.uuid4()),
                    "actor_id": actor,
                    "legal_action_id": "wsr22-not-a-real-option",
                    "action_type": "pass_priority",
                },
            },
            game_id=game_id,
        )
        _probe(
            "fail_closed_illegal_action",
            illegal,
            _decision_unchanged(identity),
            "an unrecognised legal_action_id",
        )

        stale_identity = dict(identity)
        field_name = DECISION_IDENTITY_SHAPES[candidate]["field"]
        if DECISION_IDENTITY_SHAPES[candidate]["type"] == "monotonic_long":
            stale_identity[field_name] = int(identity[field_name]) + 1_000_000
        else:
            stale_identity[field_name] = "0" * 64
        if pass_ids:
            stale = proc.request(
                "submit_action",
                {
                    "game_id": game_id,
                    **stale_identity,
                    "proposal": {
                        "proposal_id": str(uuid.uuid4()),
                        "actor_id": actor,
                        "legal_action_id": pass_ids[0],
                        "action_type": "pass_priority",
                    },
                },
                game_id=game_id,
            )
            _probe(
                "fail_closed_stale_or_unknown_decision",
                stale,
                _decision_unchanged(identity),
                "a real option under an unknown decision identity",
            )
        else:
            add(
                "fail_closed_stale_or_unknown_decision",
                "UNKNOWN",
                "the pending decision offered no pass option to pair with a stale identity",
            )

        unsupported = proc.request(
            "get_legal_actions",
            {
                "game_id": game_id,
                "actor_id": actor,
                "decision_class": "wsr22_unsupported_decision_class",
            },
            game_id=game_id,
        )
        _probe(
            "fail_closed_unsupported_decision",
            unsupported,
            _decision_unchanged(identity),
            "a request for an unsupported decision class",
        )

    # --- rules-authority invariants ------------------------------------
    illegal_invariants = [
        item
        for item in illegal.get("payload", {}).get("legal_options", [])
        if isinstance(item, dict)
    ]
    if illegal_invariants:
        add(
            "rules_core_sole_legality_authority",
            "FAIL",
            "an out-of-scope submission produced fabricated legal options",
            {"fabricated_options": len(illegal_invariants)},
        )
    elif not illegal or _rejected_as_malformed(illegal) or not _fails_closed(illegal):
        add(
            "rules_core_sole_legality_authority",
            "UNKNOWN",
            "no well-formed out-of-scope submission was rejected, so the absence of "
            "fabricated options is not demonstrated",
            {"fabricated_options": 0},
        )
    else:
        add(
            "rules_core_sole_legality_authority",
            "PASS",
            "an out-of-scope submission produced no fabricated legal option",
            {"fabricated_options": 0},
        )

    # These two invariants were previously credited as unconditional PASS. They
    # are now derived from an actual scan of the bound source, and the scan
    # evidence is recorded so the verdict can be audited rather than trusted.
    if runner_root is None:
        add(
            "no_adapter_legality_reconstruction",
            "UNKNOWN",
            "no bound runner source was supplied, so a second source of legality "
            "cannot be excluded from evidence",
            {"runner_commit": runner_commit, "runner_tree": runner_tree},
        )
        add(
            "no_fabricated_legal_options",
            "UNKNOWN",
            "no bound runner source was supplied, so synthesis of legal options "
            "cannot be excluded from evidence",
            {"probe": "illegal action probe returned no options"},
        )
    else:
        scan = observe_no_legality_reconstruction(runner_root)
        hits = scan["hits"]
        if not scan["complete"]:
            verdict = "UNKNOWN"
            detail = "the bound runner source could not be scanned, so the invariant is unproven"
        elif hits:
            verdict = "FAIL"
            detail = (
                "the bound runner source contains legality-reconstruction patterns: "
                + ", ".join(sorted({str(hit["pattern"]) for hit in hits}))
            )
        else:
            verdict = "PASS"
            detail = (
                f"a scan of {scan['scanned_files']} bound runner source files found no "
                "legality-reconstruction pattern. This is absence of a second legality "
                "source, which is weaker than positive demonstration, and it does not "
                "extend to code outside the scanned path"
            )
        add(
            "no_adapter_legality_reconstruction",
            verdict,
            detail,
            {
                "runner_commit": runner_commit,
                "runner_tree": runner_tree,
                "scan": scan,
            },
        )
        add(
            "no_fabricated_legal_options",
            verdict,
            "the same bound-source scan is the evidence; option sets are only ever "
            "read from provider payloads, and the live illegal-action probe returned "
            + ("no options" if not illegal_invariants else "options, which is a FAIL"),
            {
                "fabricated_options": len(illegal_invariants),
                "scan": scan,
            },
        )

    seed_supported = capabilities.get("seed_supported")
    seed_payload = capabilities_payload.get("rules_seed_binding")
    if seed_supported is True:
        verdict = "PASS"
        detail = "provider reports seed_supported and any RNG binding stays inside the engine"
    elif seed_supported is False:
        verdict = "UNKNOWN"
        detail = (
            "provider truthfully reports seed_supported=false; Rules RNG is not exposed, so "
            "AF09 must bind at engine level only"
        )
    else:
        verdict = "UNKNOWN"
        detail = "provider did not report seed_supported"
    add(
        "rules_randomness_core_owned",
        verdict,
        detail,
        {"seed_supported": seed_supported, "rules_seed_binding": seed_payload},
    )

    import hashlib
    import json as _json

    transcript_digest = hashlib.sha256(
        _json.dumps(proc.transcript, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return AF01Report(
        candidate=candidate,
        lane=proc.plan.lane,
        engine_commit_reported=reported_commit,
        engine_commit_provenance=str(engine_identity.get("engine_commit_source")),
        capabilities=capabilities,
        invariants=results,
        protocol_transcript_digest=transcript_digest,
        engine_identity=engine_identity,
        decision_identity_provenance=decision_identity_provenance(candidate, probe_frame),
    )
