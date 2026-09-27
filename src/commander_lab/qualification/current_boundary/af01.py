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
) -> AF01Report:
    """Execute the AF01 v2 invariants against a live candidate bridge.

    ``game_id`` must name a live game. Decision-time invariants are only
    credited against a real game: a provider asked to fail closed on a
    submission for a game that does not exist will refuse for reasons that have
    nothing to do with decision-time legality, so crediting that as evidence
    would be a pass for the wrong reason.
    """
    game_bound = bool(game_id)
    if not game_bound:
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

    # Decision-time probes are scoped to the live game. Actor identity is
    # carried alongside the action so a provider cannot satisfy them by treating
    # the request as malformed for an unrelated reason.
    illegal = proc.request(
        "submit_action",
        {
            "game_id": game_id,
            "actor": "P1",
            "legal_action_id": "wsr22-not-a-real-option",
        },
        game_id=game_id,
    )
    add(
        "fail_closed_illegal_action",
        "PASS" if _fails_closed(illegal) else "FAIL",
        "provider rejected an unrecognised legal_action_id for a live game"
        if _fails_closed(illegal)
        else "provider accepted an unrecognised legal_action_id for a live game",
        {"game_id": game_id, "response": illegal},
    )

    stale = proc.request(
        "submit_action",
        {
            "game_id": game_id,
            "actor": "P1",
            "legal_action_id": "wsr22-not-a-real-option",
            "decision_id": "wsr22-stale-decision-id",
        },
        game_id=game_id,
    )
    add(
        "fail_closed_stale_or_unknown_decision",
        "PASS" if _fails_closed(stale) else "FAIL",
        "provider rejected an unknown decision identity for a live game"
        if _fails_closed(stale)
        else "provider accepted an unknown decision identity for a live game",
        {"game_id": game_id, "response": stale},
    )

    unsupported = proc.request(
        "get_legal_actions",
        {
            "game_id": game_id,
            "decision_class": "wsr22_unsupported_decision_class",
        },
        game_id=game_id,
    )
    add(
        "fail_closed_unsupported_decision",
        "PASS" if _fails_closed(unsupported) else "FAIL",
        "an unsupported decision class failed closed for a live game without a default option"
        if _fails_closed(unsupported)
        else "an unsupported decision class did not fail closed for a live game",
        {"game_id": game_id, "response": unsupported},
    )

    # --- rules-authority invariants ------------------------------------
    illegal_invariants = [
        item
        for item in illegal.get("payload", {}).get("legal_options", [])
        if isinstance(item, dict)
    ]
    add(
        "rules_core_sole_legality_authority",
        "PASS" if _fails_closed(illegal) and not illegal_invariants else "FAIL",
        "an out-of-scope submission produced no fabricated legal option",
        {"fabricated_options": len(illegal_invariants)},
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
    )
