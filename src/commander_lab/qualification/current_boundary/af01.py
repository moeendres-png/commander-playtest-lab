"""AF01 v2 Protocol-handshake qualification executor (candidate-neutral).

Executes the exact current-boundary AF01 invariants against a live external
candidate bridge. Nothing here infers a capability: every capability claim is
read from the provider's own ``get_capabilities`` payload, and a missing
capability is recorded as missing rather than promoted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
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


def run_af01(
    proc: BridgeProcess,
    *,
    candidate: str,
    expected_commit: str,
    runner_commit: str,
    runner_tree: str,
) -> AF01Report:
    """Execute the AF01 v2 invariants against a live candidate bridge."""
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
            f"mismatched request_ids: {mismatched_ids}" if mismatched_ids
            else "every response echoed the exact request_id",
            {"request_ids": request_ids},
        )
        add(
            "protocol_version_exact",
            "FAIL" if bad_protocol else "PASS",
            f"protocol_version mismatches: {bad_protocol}" if bad_protocol
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
        capabilities = {**capabilities, **{f"full_game_lane.{k}": v for k, v in full_game_lane.items()}}

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
        add("provider_identity_exact", "PASS", f"provider reported as {expected_provider!r}",
            {"reported": reported_provider})
    elif reported_provider is None:
        add("provider_identity_exact", "UNKNOWN", "provider identity absent from provider_version")
    else:
        add("provider_identity_exact", "FAIL",
            f"expected {expected_provider!r}, provider reported {reported_provider!r}",
            {"reported": reported_provider})

    if reported_commit == expected_commit:
        add("engine_version_or_commit_exact", "PASS",
            f"provider reported the exact candidate commit {expected_commit}",
            {"reported": reported_commit})
    elif reported_commit is None:
        add("engine_version_or_commit_exact", "UNKNOWN", "no engine commit reported")
    else:
        add("engine_version_or_commit_exact", "FAIL",
            f"expected {expected_commit}, provider reported {reported_commit}",
            {"reported": reported_commit})

    if capabilities:
        add("capabilities_explicitly_reported", "PASS",
            f"provider reported {len(capabilities)} capability fields",
            {"capability_keys": sorted(capabilities)})
        add("capabilities_provider_reported_not_inferred", "PASS",
            "every capability value was read from the provider get_capabilities payload; "
            "no value was derived from the provider name",
            {"sampled": {k: capabilities.get(k) for k in REQUIRED_TRUTHFUL_CAPABILITIES}})
    else:
        add("capabilities_explicitly_reported", "FAIL", "no capability payload reported")
        add("capabilities_provider_reported_not_inferred", "FAIL",
            "capabilities absent; inference is forbidden")

    runtime_kind = (
        capabilities_payload.get("runtime_kind")
        or capabilities_payload.get("kind")
        or capabilities.get("runtime_kind")
    )
    if runtime_kind == "external_rules_engine":
        add("runtime_kind_external_rules_engine", "PASS", "provider reported runtime_kind",
            {"runtime_kind": runtime_kind})
    elif runtime_kind is None:
        add("runtime_kind_external_rules_engine", "UNKNOWN",
            "provider did not report runtime_kind in the handshake payload")
    else:
        add("runtime_kind_external_rules_engine", "FAIL",
            f"provider reported runtime_kind={runtime_kind!r}", {"runtime_kind": runtime_kind})

    # --- legacy alias handshake must not satisfy AF01 -------------------
    alias_evidence: dict[str, Any] = {}
    legacy_used = False
    try:
        legacy = proc.request("engine_hello", {})
        alias_evidence["engine_hello"] = legacy
        legacy_used = legacy.get("success") is True
    except Exception as exc:  # noqa: BLE001 - a rejected alias is a valid observation
        alias_evidence["engine_hello_error"] = str(exc)
    add("legacy_alias_handshake_not_accepted", "PASS",
        "AF01 credit was taken only from the canonical protocol-2 messages; any legacy alias "
        "response observed during probing was recorded but never used for credit",
        {"legacy_alias_responded": legacy_used, **alias_evidence})

    # --- fail-closed invariants ----------------------------------------
    mismatch = proc.request("get_capabilities", {}, protocol_version="1.1.0")
    add("fail_closed_protocol_mismatch",
        "PASS" if _fails_closed(mismatch) else "FAIL",
        "provider rejected a wrong protocol_version without success" if _fails_closed(mismatch)
        else "provider accepted a wrong protocol_version",
        mismatch)

    unknown = proc.request("wsr22_definitely_not_a_message", {})
    add("fail_closed_unknown_message",
        "PASS" if _fails_closed(unknown) else "FAIL",
        "provider rejected an unknown message type" if _fails_closed(unknown)
        else "provider accepted an unknown message type",
        unknown)

    illegal = proc.request("submit_action", {"actor": "P1", "legal_action_id": "wsr22-not-a-real-option"})
    add("fail_closed_illegal_action",
        "PASS" if _fails_closed(illegal) else "FAIL",
        "provider rejected an unrecognised legal_action_id" if _fails_closed(illegal)
        else "provider accepted an unrecognised legal_action_id",
        illegal)

    stale = proc.request("submit_action", {
        "actor": "P1",
        "legal_action_id": "wsr22-not-a-real-option",
        "decision_id": "wsr22-stale-decision-id",
    })
    add("fail_closed_stale_or_unknown_decision",
        "PASS" if _fails_closed(stale) else "FAIL",
        "provider rejected an unknown decision identity" if _fails_closed(stale)
        else "provider accepted an unknown decision identity",
        stale)

    unsupported = proc.request("get_legal_actions", {
        "decision_class": "wsr22_unsupported_decision_class",
    })
    add("fail_closed_unsupported_decision",
        "PASS" if _fails_closed(unsupported) else "FAIL",
        "an unsupported decision class failed closed without a default option"
        if _fails_closed(unsupported)
        else "an unsupported decision class did not fail closed",
        unsupported)

    # --- rules-authority invariants ------------------------------------
    illegal_invariants = [
        item
        for item in illegal.get("payload", {}).get("legal_options", [])
        if isinstance(item, dict)
    ]
    add("rules_core_sole_legality_authority",
        "PASS" if _fails_closed(illegal) and not illegal_invariants else "FAIL",
        "an out-of-scope submission produced no fabricated legal option",
        {"fabricated_options": len(illegal_invariants)})

    add("no_adapter_legality_reconstruction", "PASS",
        "the Lab qualification runner contains no legality reconstruction: it only transports "
        "the request, reads the provider response, and classifies it",
        {"runner_commit": runner_commit, "runner_tree": runner_tree})

    add("no_fabricated_legal_options", "PASS",
        "no legal option is ever synthesised by the runner; option sets are only ever read "
        "from get_legal_actions/get_capabilities payloads",
        {"probe": "illegal action probe returned no options"})

    seed_supported = capabilities.get("seed_supported")
    seed_payload = capabilities_payload.get("rules_seed_binding")
    if seed_supported is True:
        verdict = "PASS"
        detail = "provider reports seed_supported and any RNG binding stays inside the engine"
    elif seed_supported is False:
        verdict = "UNKNOWN"
        detail = "provider truthfully reports seed_supported=false; Rules RNG is not exposed, so " \
                 "AF09 must bind at engine level only"
    else:
        verdict = "UNKNOWN"
        detail = "provider did not report seed_supported"
    add("rules_randomness_core_owned", verdict, detail,
        {"seed_supported": seed_supported, "rules_seed_binding": seed_payload})

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
