"""WSR24-owned freeze-readiness validators (provider-neutral, dependency-free).

Implements the eligibility conditional of
``qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json``
as a pure function so both the Lab qualification suite and (later) the
production repository can reject invalid ``freeze_eligible=true`` records
without a JSON-Schema runtime dependency.

Rules mirrored from the schema ``allOf`` conditional:
``freeze_eligible=true`` is conformant ONLY IF every required AF00-AF11 gate
is PASS AND ``missing_required_capabilities`` is empty AND every required
capability flag is true. Anything else MUST evaluate to not-eligible.
"""

from __future__ import annotations

from typing import Any

REQUIRED_GATES = [
    "AF00",
    "AF01",
    "AF02",
    "AF03",
    "AF04",
    "AF05",
    "AF06",
    "AF07",
    "AF08",
    "AF09",
    "AF10",
    "AF11",
]

REQUIRED_CAPABILITIES = [
    "action_submission_supported",
    "commander_supported",
    "deck_import_supported",
    "engine_shutdown_supported",
    "event_log_supported",
    "game_shutdown_supported",
    "headless_supported",
    "legal_actions_supported",
    "multiplayer_supported",
    "replay_supported",
    "seed_supported",
]

PASS = "PASS"

NON_PASS_VERDICTS = ("FAIL", "UNKNOWN", "PARTIAL", "NOT_RUN", "UNSUPPORTED")

BANNED_RANKING_KEYS = ("score", "rank", "ranking", "winner", "selected_provider")


def check_freeze_eligibility(
    gate_results: list[dict[str, Any]],
    capabilities: dict[str, Any],
    missing_required_capabilities: list[Any],
) -> tuple[bool, list[str]]:
    """Return ``(eligible, reasons)``.

    ``eligible`` is True only when the record satisfies the full Freeze
    condition. ``reasons`` names every violated requirement; it is empty
    exactly when ``eligible`` is True. Never promotes, never defaults:
    unknown shapes evaluate to not-eligible with an explicit reason.
    """
    reasons: list[str] = []
    if not isinstance(gate_results, list):
        return False, ["gate_results is not a list"]
    if len(gate_results) != len(REQUIRED_GATES):
        reasons.append(
            f"gate_results has {len(gate_results)} entries, required exactly {len(REQUIRED_GATES)}"
        )
    seen: dict[str, int] = {}
    for entry in gate_results:
        if not isinstance(entry, dict):
            reasons.append("gate_results entry is not an object")
            continue
        gate_id = entry.get("gate_id")
        verdict = entry.get("verdict")
        if gate_id not in REQUIRED_GATES:
            reasons.append(f"unexpected gate_id: {gate_id!r}")
            continue
        seen[gate_id] = seen.get(gate_id, 0) + 1
        if verdict != PASS:
            reasons.append(f"{gate_id} verdict is {verdict!r}, not PASS")
        if not entry.get("reason"):
            reasons.append(f"{gate_id} has empty reason")
        if not entry.get("evidence_refs"):
            reasons.append(f"{gate_id} has empty evidence_refs")
    for gate_id in REQUIRED_GATES:
        count = seen.get(gate_id, 0)
        if count == 0:
            reasons.append(f"missing required gate {gate_id}")
        elif count > 1:
            reasons.append(f"duplicated gate {gate_id}")
    if not isinstance(missing_required_capabilities, list):
        reasons.append("missing_required_capabilities is not a list")
    elif len(missing_required_capabilities) != 0:
        reasons.append(
            f"missing_required_capabilities is non-empty: {missing_required_capabilities!r}"
        )
    if not isinstance(capabilities, dict):
        reasons.append("capabilities is not an object")
    else:
        for cap in REQUIRED_CAPABILITIES:
            if capabilities.get(cap) is not True:
                reasons.append(f"required capability {cap} is not true")
    return (len(reasons) == 0, reasons)


def validate_readiness_packet(packet: dict[str, Any]) -> list[str]:
    """Structural check for a WSR24 freeze-readiness packet.

    Verifies the 12-gate skeleton, verdict vocabulary, and the honesty rule:
    a packet that claims ``freeze_eligible=true`` while any gate is non-PASS
    (or any preventer is listed) is an error. Returns a list of errors.
    """
    errors: list[str] = []
    gates = packet.get("gates")
    if not isinstance(gates, list) or len(gates) != len(REQUIRED_GATES):
        return [f"packet has {len(gates) if isinstance(gates, list) else 'non-list'} gates"]
    ids = [g.get("gate") for g in gates]
    if sorted(ids) != sorted(REQUIRED_GATES):
        errors.append(f"gate ids are not exactly AF00-AF11: {ids!r}")
    allowed = {PASS, *NON_PASS_VERDICTS}
    for g in gates:
        verdict = g.get("current_verdict")
        if verdict not in allowed:
            errors.append(f"{g.get('gate')} has out-of-vocabulary verdict {verdict!r}")
        for field in (
            "current_verdict",
            "exact_wsr22_evidence",
            "evidence_identity",
            "missing_proof_or_capability",
            "smallest_bounded_remediation",
            "affected_full107_rows",
            "impacted_production_path",
            "freeze_eligibility_consequence",
        ):
            if field not in g:
                errors.append(f"{g.get('gate')} is missing field {field}")
        if "verdict" in g:
            errors.append(f"{g.get('gate')}: readiness packets use current_verdict, not verdict")
    non_pass = [g["gate"] for g in gates if g.get("current_verdict") != PASS]
    if packet.get("freeze_eligibility", {}).get("freeze_eligible") is True:
        if non_pass:
            errors.append(f"claims freeze_eligible=true with non-PASS gates {non_pass}")
        preventers = packet.get("freeze_eligibility", {}).get("prevented_by", [])
        if preventers:
            errors.append("claims freeze_eligible=true while listing preventers")
    return errors


def packet_shape(
    packet: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[Any, tuple[str, ...]], ...]]:
    """Structural shape used for cross-candidate symmetry checks.

    Two readiness packets are symmetric when their shapes are equal: same
    gate order, same per-gate field set, same top-level keys. Verdict VALUES
    are intentionally excluded (candidates differ honestly).
    """
    gates = packet.get("gates", [])
    gate_shape = tuple((g.get("gate"), tuple(sorted(k for k in g))) for g in gates)
    top_shape = tuple(sorted(packet.keys()))
    elig_shape = tuple(sorted((packet.get("freeze_eligibility") or {}).keys()))
    return (top_shape, elig_shape, gate_shape)


def find_banned_keys(node: Any, banned: tuple[str, ...] = BANNED_RANKING_KEYS) -> list[str]:
    """Recursively collect dotted paths of banned ranking/score keys."""
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in banned:
                hits.append(str(key))
            hits.extend(find_banned_keys(value, banned))
    elif isinstance(node, list):
        for value in node:
            hits.extend(find_banned_keys(value, banned))
    return hits
