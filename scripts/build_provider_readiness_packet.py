#!/usr/bin/env python3
"""Build the section-F provider-readiness packet from one sealed evidence epoch.

The packet is evidence presentation, not adjudication: it selects no provider,
ranks no candidate and makes no recommendation.  Every emitted status is derived
mechanically from sealed artifacts only:

* the sealed current-boundary epoch's ``CURRENT_BOUNDARY_SHA256SUMS`` is fully
  verified before any artifact is read; every file in the epoch must be covered
  and every digest must match, otherwise the build fails closed;
* a dimension is ``PASS`` only when every backing AF gate verdict is ``PASS``
  and every fixture row that carries the dimension is ``PASS``; a ``FAIL``
  anywhere makes the dimension ``FAIL``; anything else is ``UNKNOWN`` (or the
  explicitly declared ``NOT_RUN`` / ``UNSUPPORTED`` special case);
* results, effective manifest, comparison and gate files must agree on the
  107-row denominator, or the build fails closed;
* unknown vocabulary (row state, gate verdict, fixture class) fails closed.

The generator reads no clock, uses no network and invokes no engine.  Running it
twice on the same sealed epoch produces byte-identical output.

Usage:
    python3 scripts/build_provider_readiness_packet.py
    python3 scripts/build_provider_readiness_packet.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EPOCH = "b1c8f54a999a-2d13b953a82c"
PACKET_DIR = REPO_ROOT / "docs" / "provider_readiness_packet_20261007"
PACKET_JSON = PACKET_DIR / "PROVIDER_READINESS.json"
PACKET_MD = PACKET_DIR / "PROVIDER_READINESS.md"

# Provenance of the packet itself: the main commit/tree this workstream started
# from.  Deliberately constants: the generator must not read mutable Git state.
PACKET_SOURCE = {
    "repository": "moeendres-png/commander-playtest-lab",
    "declared_branch": "evidence/provider-readiness-packet-20261007",
    "base_main_commit": "1d605a5883c1a8dd1de87d5a9261c74768c65f16",
    "base_main_tree": "34bc6cef608dec6ca2c0ae470932c709ea28b1eb",
    "basis": "origin/main at workstream start",
}

SCHEMA_VERSION = "commander-lab.provider-readiness-section-f/1.0.0"

DIMENSION_STATUS_VOCABULARY = ("PASS", "FAIL", "UNKNOWN", "NOT_RUN", "UNSUPPORTED")
ROW_STATE_VOCABULARY = (
    "PASS",
    "FAIL",
    "UNKNOWN",
    "NOT_RUN",
    "BLOCKED",
    "CRASH",
    "TIMEOUT",
    "PROTOCOL_FAILURE",
)
GATE_VERDICT_VOCABULARY = ("PASS", "FAIL", "UNKNOWN", "NOT_RUN")
FIXTURE_CLASS_VOCABULARY = (
    "SAME_SEMANTICS",
    "NON_COMPARABLE",
    "ENGINE_CAPABILITY_GAP",
    "UNKNOWN_PENDING_RULES_ADJUDICATION",
)
FAILING_ROW_STATES = ("FAIL", "CRASH", "TIMEOUT", "PROTOCOL_FAILURE")
UNRESOLVED_ROW_STATES = ("UNKNOWN", "BLOCKED")

# Section-F dimensions of issue #255.  Fixture ids are explicit so that coverage
# is auditable; a fixture may inform more than one dimension.
DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "key": "rules_authority_separation",
        "name": "Rules authority separation",
        "gates": ("AF00", "AF03"),
        "fixtures": (),
        "special": None,
    },
    {
        "id": 2,
        "key": "legal_actions_submission",
        "name": "Legal actions / submission",
        "gates": ("AF04",),
        "fixtures": (
            "PILOT_PRIORITY",
            "PILOT_TARGET",
            "PILOT_CHOOSE_OBJECT",
            "PILOT_TARGET_AMOUNT",
            "PILOT_MULLIGAN",
            "PILOT_CHOOSE_USE",
            "PILOT_CHOICE",
            "PILOT_PILE",
            "PILOT_MANA_PAYMENT",
            "PILOT_ANNOUNCE_X",
            "PILOT_MULTI_AMOUNT",
            "PILOT_REPLACEMENT_EFFECT",
            "PILOT_TRIGGER_ORDER",
            "PILOT_CHOOSE_MODE",
            "PILOT_CHOOSE_ABILITY",
            "PILOT_DECLARE_ATTACKER",
            "PILOT_DECLARE_BLOCKER",
        ),
        "special": None,
    },
    {
        "id": 3,
        "key": "costs_mana",
        "name": "Costs / mana",
        "gates": ("AF06",),
        "fixtures": ("MICRO_COSTS", "MICRO_MANA_PAYMENT", "PILOT_MANA_PAYMENT"),
        "special": None,
    },
    {
        "id": 4,
        "key": "stack_priority",
        "name": "Stack / priority",
        "gates": ("AF06",),
        "fixtures": ("MICRO_PRIORITY", "MICRO_STACK", "WS05-MP-PRIO-3", "WS05-MP-PRIO-5"),
        "special": None,
    },
    {
        "id": 5,
        "key": "targets_modes_choices",
        "name": "Targets / modes / choices",
        "gates": ("AF06",),
        "fixtures": (
            "MICRO_TARGETS",
            "MICRO_MODES",
            "PILOT_TARGET",
            "PILOT_TARGET_AMOUNT",
            "PILOT_MULTI_AMOUNT",
            "PILOT_CHOOSE_OBJECT",
            "PILOT_CHOOSE_USE",
            "PILOT_CHOICE",
            "PILOT_PILE",
            "PILOT_CHOOSE_MODE",
            "PILOT_CHOOSE_ABILITY",
            "PILOT_ANNOUNCE_X",
        ),
        "special": None,
    },
    {
        "id": 6,
        "key": "triggers",
        "name": "Triggers",
        "gates": ("AF06",),
        "fixtures": ("MICRO_TRIGGERS", "WS05-MP-TRIG-3", "WS05-MP-TRIG-5", "PILOT_TRIGGER_ORDER"),
        "special": None,
    },
    {
        "id": 7,
        "key": "replacement_prevention",
        "name": "Replacement / prevention",
        "gates": ("AF06",),
        "fixtures": ("MICRO_REPLACEMENT", "MICRO_PREVENTION", "PILOT_REPLACEMENT_EFFECT"),
        "special": None,
    },
    {
        "id": 8,
        "key": "continuous_effects_layers",
        "name": "Continuous effects / layers",
        "gates": ("AF06",),
        "fixtures": ("MICRO_CONTINUOUS_EFFECTS", "MICRO_LAYERS"),
        "special": None,
    },
    {
        "id": 9,
        "key": "state_based_actions",
        "name": "State-based actions",
        "gates": ("AF06",),
        "fixtures": ("MICRO_STATE_BASED_ACTIONS",),
        "special": None,
    },
    {
        "id": 10,
        "key": "zones",
        "name": "Zones",
        "gates": ("AF06",),
        "fixtures": (
            "MICRO_ZONE_CHANGES",
            "WS05-CMD-ZONE-GY-YES",
            "WS05-CMD-ZONE-GY-NO",
            "WS05-CMD-ZONE-EXILE-YES",
            "WS05-CMD-ZONE-EXILE-NO",
            "WS05-CMD-ZONE-HAND-YES",
            "WS05-CMD-ZONE-HAND-NO",
            "WS05-CMD-ZONE-LIB-YES",
            "WS05-CMD-ZONE-LIB-NO",
        ),
        "special": None,
    },
    {
        "id": 11,
        "key": "copy_control",
        "name": "Copy / control",
        "gates": ("AF06",),
        "fixtures": ("MICRO_COPY", "MICRO_CONTROL", "WS05-CMD-DMG-CONTROL"),
        "special": None,
    },
    {
        "id": 12,
        "key": "combat",
        "name": "Combat",
        "gates": ("AF06",),
        "fixtures": (
            "MICRO_COMBAT",
            "PILOT_DECLARE_ATTACKER",
            "PILOT_DECLARE_BLOCKER",
            "WS05-MP-COMBAT-4",
            "WS05-MP-COMBAT-5",
            "WS05-MP-BLOCK-4",
        ),
        "special": None,
    },
    {
        "id": 13,
        "key": "commander_rules",
        "name": "Commander rules",
        "gates": ("AF08",),
        "fixtures": (
            "WS05-CMD-TAX-2",
            "WS05-CMD-TAX-4",
            "WS05-CMD-ZONE-GY-YES",
            "WS05-CMD-ZONE-GY-NO",
            "WS05-CMD-ZONE-EXILE-YES",
            "WS05-CMD-ZONE-EXILE-NO",
            "WS05-CMD-ZONE-HAND-YES",
            "WS05-CMD-ZONE-HAND-NO",
            "WS05-CMD-ZONE-LIB-YES",
            "WS05-CMD-ZONE-LIB-NO",
            "WS05-CMD-DMG-SAME-21",
            "WS05-CMD-DMG-SPLIT",
            "WS05-CMD-DMG-CONTROL",
            "WS05-CMD-PARTNER-TAX",
            "WS05-CMD-PARTNER-DMG",
            "WS05-CMD-PARTNER-ZONE",
            "WS05-CMD-MULL-2",
            "WS05-CMD-MULL-4",
            "WS05-CMD-START-2",
            "WS05-CMD-START-3",
            "WS05-CMD-ELIM-4",
        ),
        "special": None,
    },
    {
        "id": 14,
        "key": "multiplayer_2_5p",
        "name": "Multiplayer 2-5P",
        "gates": ("AF02", "AF08"),
        "fixtures": (
            "PLAYER_COUNT_2P",
            "PLAYER_COUNT_3P",
            "PLAYER_COUNT_4P",
            "PLAYER_COUNT_5P",
            "WS05-MP-PRIO-3",
            "WS05-MP-PRIO-5",
            "WS05-MP-TRIG-3",
            "WS05-MP-TRIG-5",
            "WS05-MP-COMBAT-4",
            "WS05-MP-COMBAT-5",
            "WS05-MP-BLOCK-4",
            "WS05-MP-TURN-3",
            "WS05-MP-TURN-5",
            "WS05-MP-ELIM-OWNED-3",
            "WS05-MP-ELIM-CONTROL-3",
            "WS05-MP-ELIM-STACK-3",
            "WS05-MP-ELIM-PRIO-3",
            "WS05-MP-ELIM-TURN-3",
            "WS05-MP-ELIM-5",
        ),
        "special": None,
    },
    {
        "id": 15,
        "key": "bounded_6p",
        "name": "Bounded 6P",
        "gates": ("AF02",),
        "fixtures": (),
        "special": "bounded_6p",
    },
    {
        "id": 16,
        "key": "hidden_information",
        "name": "Hidden information",
        "gates": ("AF05",),
        "fixtures": (
            "HIDDEN_01",
            "HIDDEN_02",
            "HIDDEN_03",
            "HIDDEN_04",
            "HIDDEN_05",
            "HIDDEN_06",
            "HIDDEN_07",
            "HIDDEN_08",
            "HIDDEN_09",
            "HIDDEN_10",
            "HIDDEN_11",
            "HIDDEN_12",
            "HIDDEN_13",
            "HIDDEN_14",
            "HIDDEN_15",
            "HIDDEN_16",
            "HIDDEN_17",
            "HIDDEN_18",
            "HIDDEN_19",
            "HIDDEN_HONEYCARD_SENTINEL",
        ),
        "special": None,
    },
    {
        "id": 17,
        "key": "rules_rng",
        "name": "Rules RNG",
        "gates": ("AF09",),
        "fixtures": ("RNG_RULES_TAPE", "MICRO_RULES_RANDOMNESS"),
        "special": None,
    },
    {
        "id": 18,
        "key": "semantic_replay",
        "name": "Semantic replay",
        "gates": ("AF09",),
        "fixtures": (
            "REPLAY_CLEAN_PROCESS",
            "REPLAY_DECISION_TAPE",
            "REPLAY_EVENT_TAPE",
            "REPLAY_STATE_HASHES",
        ),
        "special": None,
    },
    {
        "id": 19,
        "key": "process_isolation",
        "name": "Process isolation",
        "gates": ("AF11",),
        "fixtures": (),
        "special": None,
    },
    {
        "id": 20,
        "key": "fail_closed_unsupported_paths",
        "name": "Fail-closed unsupported paths",
        "gates": ("AF01", "AF04"),
        "fixtures": (
            "NEGATIVE_FIRST_OPTION",
            "NEGATIVE_RANDOM_OPTION",
            "NEGATIVE_DEFAULT_YES_NO",
            "NEGATIVE_INTERNAL_AI",
            "NEGATIVE_GUI_DEFAULT",
            "NEGATIVE_SILENT_SKIP",
            "NEGATIVE_PARENT_CLASS_FALLBACK",
        ),
        "special": None,
    },
    {
        "id": 21,
        "key": "actual_card_runtime_coverage",
        "name": "Actual-card runtime coverage",
        "gates": ("AF07",),
        "fixtures": ("CARD_02",),
        "special": None,
    },
)

CANDIDATES = ("xmage", "forge")
CANDIDATE_FILES = {"xmage": "XMAGE", "forge": "FORGE"}

# Known residuals named by issue #255, kept explicitly beside the current sealed
# state.  The sealed state is read from the epoch; only the issue-recorded label
# is a constant.
KNOWN_RESIDUALS: tuple[dict[str, str], ...] = (
    {
        "residual": "HIDDEN_05",
        "candidate": "forge",
        "issue_recorded_state": "UNKNOWN - face-down exile permission persistence",
    },
    {
        "residual": "HIDDEN_06",
        "candidate": "forge",
        "issue_recorded_state": "UNKNOWN - face-down exile invalidation on zone change",
    },
    {
        "residual": "HIDDEN_08",
        "candidate": "forge",
        "issue_recorded_state": "NOT_RUN_BLOCKED - look-audience seam",
    },
    {
        "residual": "HIDDEN_11",
        "candidate": "forge",
        "issue_recorded_state": "UNKNOWN - shuffle/order-knowledge invalidation",
    },
    {
        "residual": "HIDDEN_12",
        "candidate": "forge",
        "issue_recorded_state": "NOT_RUN_BLOCKED - controlled-player decision seam",
    },
    {
        "residual": "WS05-CMD-MULL-2",
        "candidate": "forge",
        "issue_recorded_state": "NOT_RUN_BLOCKED - London bottom-choice seam",
    },
    {
        "residual": "WS05-CMD-MULL-2",
        "candidate": "xmage",
        "issue_recorded_state": "AF08 residual - no external London-bottom decision",
    },
    {
        "residual": "NEGATIVE_PARENT_CLASS_FALLBACK",
        "candidate": "xmage",
        "issue_recorded_state": "NOT_NAMED_BY_ISSUE - observed UNKNOWN in the current sealed epoch",
    },
)


class FailClosed(RuntimeError):
    """Raised when sealed evidence is missing, inconsistent or tampered with."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FailClosed(f"sealed artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FailClosed(f"sealed artifact is not valid JSON: {path}: {exc}") from exc


def verify_epoch(epoch_root: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify CURRENT_BOUNDARY_SHA256SUMS fully and return manifest metadata."""

    manifest_path = epoch_root / "CURRENT_BOUNDARY_SHA256SUMS"
    if not manifest_path.is_file():
        raise FailClosed(f"epoch manifest missing: {manifest_path}")
    entries: dict[str, str] = {}
    for lineno, raw in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        parts = raw.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise FailClosed(f"malformed manifest line {lineno}: {raw!r}")
        digest, relative = parts[0], parts[1]
        entries[relative] = digest
    if entries == {}:
        raise FailClosed(f"epoch manifest is empty: {manifest_path}")

    actual_files = {
        str(path.relative_to(repo_root))
        for path in epoch_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_files != set(entries):
        missing = sorted(actual_files - set(entries))
        extra = sorted(set(entries) - actual_files)
        raise FailClosed(
            "epoch manifest coverage mismatch: "
            f"uncovered files={missing[:5]} stale entries={extra[:5]}"
        )

    for relative, expected in entries.items():
        path = repo_root / relative
        actual = _sha256(path)
        if actual != expected:
            raise FailClosed(f"digest mismatch: {relative}: expected {expected} actual {actual}")

    return {
        "path": str(manifest_path.relative_to(repo_root)),
        "sha256": _sha256(manifest_path),
        "entries": len(entries),
        "verified": len(entries),
        "mismatches": 0,
        "coverage": "EXACT_ALL_FILES_EXCEPT_MANIFEST",
    }


def _json_files(epoch_root: Path) -> dict[str, Any]:
    return {
        name: _load_json(epoch_root / name)
        for name in (
            "AF00_AF11_XMAGE.json",
            "AF00_AF11_FORGE.json",
            "FULL107_XMAGE_RESULTS.json",
            "FULL107_FORGE_RESULTS.json",
            "EFFECTIVE_FULL107_MANIFEST.json",
            "CURRENT_BOUNDARY_COMPARISON.json",
            "DIVERGENCE_PACKET.json",
            "PLAYER_CARDINALITY_XMAGE.json",
            "PLAYER_CARDINALITY_FORGE.json",
            "NATIVE_SUITE_RECEIPTS.json",
            "PB03_RUNTIME_EXECUTION.json",
            "EPOCH_IDENTITY.json",
        )
    }


def _gate_verdicts(document: dict[str, Any]) -> dict[str, str]:
    verdicts: dict[str, str] = {}
    for gate in document["gates"]:
        gate_id = gate["gate"]
        verdict = gate["verdict"]
        if verdict not in GATE_VERDICT_VOCABULARY:
            raise FailClosed(f"unknown AF verdict vocabulary: {gate_id}={verdict!r}")
        verdicts[gate_id] = verdict
    for required in (f"AF{index:02d}" for index in range(12)):
        if required not in verdicts:
            raise FailClosed(f"AF matrix is missing gate {required}")
    return verdicts


def _row_states(document: dict[str, Any]) -> dict[str, str]:
    states: dict[str, str] = {}
    for row in document["rows"]:
        state = row["exit_state"]
        if state not in ROW_STATE_VOCABULARY:
            raise FailClosed(f"unknown FULL107 row state vocabulary: {state!r}")
        fixture_id = row["fixture_id"]
        if fixture_id in states:
            raise FailClosed(f"duplicate FULL107 row: {fixture_id}")
        states[fixture_id] = state
    return states


def _af_evidence_value(document: dict[str, Any], gate_id: str, prefix: str) -> str:
    for gate in document["gates"]:
        if gate["gate"] != gate_id:
            continue
        for item in gate.get("evidence", []):
            if item.startswith(prefix):
                return str(item[len(prefix) :]).strip()
    raise FailClosed(f"AF {gate_id} evidence does not state {prefix!r}")


def _read_pin_section() -> dict[str, Any]:
    config = _load_json(REPO_ROOT / "config" / "rules_engines.json")
    pins = {
        "xmage": {
            "commit": config["primary_engine"]["commit"],
            "pin_source": "config/rules_engines.json#primary_engine.commit",
        },
        "forge_rules_core": {
            "commit": config["secondary_engine"]["commit"],
            "tree": config["secondary_engine"]["engine_identity_pb09"]["current_candidate"]["tree"],
            "pin_source": "config/rules_engines.json#secondary_engine.commit",
        },
        "forge_bridge_source": {
            "commit": config["secondary_engine"]["bridge_source"]["commit"],
            "tree": config["secondary_engine"]["engine_identity_pb09"]["bridge_source"]["tree"],
            "pin_source": "config/rules_engines.json#secondary_engine.bridge_source.commit",
        },
    }
    if (
        config["secondary_engine"]["bridge_source"]["commit"]
        != config["secondary_engine"]["engine_identity_pb09"]["bridge_source"]["commit"]
    ):
        raise FailClosed("config/rules_engines.json records two different Forge bridge commits")
    return {"config": config, "pins": pins}


def _xmage_pin_tree() -> dict[str, str]:
    lock = _load_json(
        REPO_ROOT
        / "qualification"
        / "xmage-sba-priority-repin-v4-20261003"
        / "SUCCESSOR_SOURCE_LOCK.json"
    )
    candidate = lock["lineage"]["final_integrated_candidate"]
    return {"commit": candidate["commit"], "tree": candidate["tree"]}


def _effective_contract_binding(epoch: dict[str, Any]) -> dict[str, Any]:
    pointer = _load_json(REPO_ROOT / "qualification" / "CURRENT_PRE_FREEZE_CONTRACT.json")
    successor_rel = pointer["full107"]["successor_contract"]
    successor = _load_json(REPO_ROOT / successor_rel)
    schema_rel = pointer["full107"]["effective_materialization_schema"]
    return {
        "pointer": "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
        "pointer_sha256": _sha256(REPO_ROOT / "qualification" / "CURRENT_PRE_FREEZE_CONTRACT.json"),
        "successor_contract": successor_rel,
        "successor_sha256": _sha256(REPO_ROOT / successor_rel),
        "successor_id": successor.get("contract_id") or successor.get("schema_version"),
        "schema": schema_rel,
        "schema_sha256": _sha256(REPO_ROOT / schema_rel),
        "effective_manifest_contract_id": epoch["EFFECTIVE_FULL107_MANIFEST.json"]["contract_id"],
    }


def _drift_records(
    pins: dict[str, Any], evidence: dict[str, str], contract: dict[str, Any], epoch: dict[str, Any]
) -> list[dict[str, str]]:
    manifest_contract = epoch["EFFECTIVE_FULL107_MANIFEST.json"]["contract_id"]
    comparisons = (
        (
            "xmage engine commit",
            pins["xmage"]["commit"],
            evidence["xmage_candidate_commit"],
            "config#primary_engine.commit",
            "AF00_AF11_XMAGE.json#gates[AF00].evidence",
        ),
        (
            "forge Rules-Core commit",
            pins["forge_rules_core"]["commit"],
            evidence["forge_rules_core_commit"],
            "config#secondary_engine.commit",
            "AF00_AF11_FORGE.json#gates[AF00].evidence",
        ),
        (
            "forge bridge/materialization commit",
            pins["forge_bridge_source"]["commit"],
            evidence["forge_build_commit"],
            "config#secondary_engine.bridge_source.commit",
            "AF00_AF11_FORGE.json#gates[AF00].evidence",
        ),
        (
            "effective fixture contract",
            contract["successor_id"],
            manifest_contract,
            "qualification/CURRENT_PRE_FREEZE_CONTRACT.json#full107.successor_contract",
            "EFFECTIVE_FULL107_MANIFEST.json#contract_id",
        ),
    )
    records: list[dict[str, str]] = []
    for subject, pinned, sealed, pin_source, evidence_source in comparisons:
        verdict = "IDENTICAL" if pinned == sealed else "DIFFERS"
        records.append(
            {
                "subject": subject,
                "pin": pinned,
                "sealed_evidence": sealed,
                "verdict": verdict,
                "pin_source": pin_source,
                "evidence_source": evidence_source,
                "note": (
                    "no drift: the sealed epoch was produced from this exact pin"
                    if verdict == "IDENTICAL"
                    else "PIN_ADVANCED_AFTER_SEALED_EPOCH: the sealed evidence is not promoted and no "
                    "credit is transferred to the newer pin"
                ),
            }
        )
    return records


def _fixture_classes(epoch: dict[str, Any]) -> dict[str, str]:
    classes: dict[str, str] = {}
    for row in epoch["CURRENT_BOUNDARY_COMPARISON.json"]["rows"]:
        disposition = row["disposition"]
        if disposition not in FIXTURE_CLASS_VOCABULARY:
            raise FailClosed(f"unknown fixture class vocabulary: {disposition!r}")
        classes[row["fixture_id"]] = disposition
    return classes


def _dimension_fixture_status(
    fixtures: tuple[str, ...], row_states: dict[str, str]
) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    blocking: list[str] = []
    for fixture_id in sorted(fixtures):
        state = row_states[fixture_id]
        counts[state] = counts.get(state, 0) + 1
        if state != "PASS":
            blocking.append(fixture_id)
    return counts, blocking


def derive_status(gate_verdicts: dict[str, str], fixture_states: list[str]) -> str:
    """Strict, fail-closed dimension aggregation.

    PASS requires every backing gate verdict and every backing fixture state to
    be PASS.  Any FAIL-class state makes the dimension FAIL.  A mixed or
    unresolved set is UNKNOWN; an all-NOT_RUN set is NOT_RUN.  The caller
    handles the declared special cases separately.
    """

    if any(verdict == "FAIL" for verdict in gate_verdicts.values()) or any(
        state in FAILING_ROW_STATES for state in fixture_states
    ):
        return "FAIL"
    if all(verdict == "PASS" for verdict in gate_verdicts.values()) and all(
        state == "PASS" for state in fixture_states
    ):
        return "PASS"
    if (
        fixture_states
        and all(state == "NOT_RUN" for state in fixture_states)
        and all(verdict == "NOT_RUN" for verdict in gate_verdicts.values())
    ):
        return "NOT_RUN"
    return "UNKNOWN"


def _citation(file: str, field: str, value: Any, kind: str) -> dict[str, str]:
    return {"file": file, "field": field, "value": str(value), "kind": kind}


def _candidate_dimension(
    candidate: str,
    dimension: dict[str, Any],
    gate_verdicts: dict[str, str],
    row_states: dict[str, str],
    fixture_classes: dict[str, str],
    epoch_root: str,
    epoch: dict[str, Any],
) -> dict[str, Any]:
    gate_citations = [
        _citation(
            f"{epoch_root}/AF00_AF11_{CANDIDATE_FILES[candidate]}.json",
            f"gates[gate={gate_id}].verdict",
            gate_verdicts[gate_id],
            "AF_GATE_VERDICT",
        )
        for gate_id in dimension["gates"]
    ]
    status_basis = "ALL_BACKING_GATES_PASS_AND_ALL_FIXTURES_PASS"

    if dimension["special"] == "bounded_6p":
        cardinality = epoch[f"PLAYER_CARDINALITY_{CANDIDATE_FILES[candidate]}.json"]
        result_6p = cardinality["results"]["6P"]
        if candidate == "xmage":
            capabilities = cardinality["runtime_identity"]["capabilities_provider_reported"]
            if capabilities.get("max_players") != 5:
                raise FailClosed("XMage bounded-6P declaration changed; re-adjudicate this cell")
            status = "UNSUPPORTED"
            status_basis = "PROVIDER_DECLARED_MAX_PLAYERS_5"
            residuals = [
                "declared capability max_players=5; the 6P attempt is additionally recorded "
                f"fail-closed: {result_6p['failure_kind']}",
            ]
            citations = [
                *gate_citations,
                _citation(
                    f"{epoch_root}/PLAYER_CARDINALITY_XMAGE.json",
                    "runtime_identity.capabilities_provider_reported.max_players",
                    5,
                    "PROVIDER_CAPABILITY_DECLARATION",
                ),
                _citation(
                    f"{epoch_root}/PLAYER_CARDINALITY_XMAGE.json",
                    "results.6P.failure_kind",
                    result_6p["failure_kind"],
                    "BOUNDED_6P_RESULT",
                ),
            ]
        else:
            if result_6p.get("terminal_facts", {}).get("created_player_count") != 6:
                raise FailClosed(
                    "Forge bounded-6P construction fact changed; re-adjudicate this cell"
                )
            status = "NOT_RUN"
            status_basis = "BOUNDED_6P_LIFECYCLE_NOT_COMPLETED_RECORD_AUTHORITY_GAP"
            residuals = [
                f"6P construction reached, lifecycle not completed: {result_6p['failure_kind']}",
            ]
            citations = [
                *gate_citations,
                _citation(
                    f"{epoch_root}/PLAYER_CARDINALITY_FORGE.json",
                    "results.6P.failure_kind",
                    result_6p["failure_kind"],
                    "BOUNDED_6P_RESULT",
                ),
                _citation(
                    f"{epoch_root}/PLAYER_CARDINALITY_FORGE.json",
                    "results.6P.terminal_facts.created_player_count",
                    6,
                    "BOUNDED_6P_RESULT",
                ),
            ]
        return {
            "status": status,
            "status_basis": status_basis,
            "backing_af_verdicts": {
                gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]
            },
            "fixture_count": 0,
            "fixture_status_counts": {},
            "fixture_ids": [],
            "fixture_classes": {},
            "blocking_rows": [],
            "residuals": residuals,
            "citations": citations,
        }

    fixtures = tuple(sorted(dimension["fixtures"]))
    counts, blocking = _dimension_fixture_status(fixtures, row_states)
    fixture_states = [row_states[fixture_id] for fixture_id in fixtures]
    status = derive_status(
        {gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]}, fixture_states
    )

    cited_fixtures = fixtures if status == "PASS" or not blocking else tuple(blocking)
    citations = list(gate_citations)
    for fixture_id in cited_fixtures:
        citations.append(
            _citation(
                f"{epoch_root}/FULL107_{CANDIDATE_FILES[candidate]}_RESULTS.json",
                f"rows[fixture_id={fixture_id}].exit_state",
                row_states[fixture_id],
                "FIXTURE_ROW_STATE",
            )
        )
    for fixture_id in fixtures:
        citations.append(
            _citation(
                f"{epoch_root}/CURRENT_BOUNDARY_COMPARISON.json",
                f"rows[fixture_id={fixture_id}].disposition",
                fixture_classes[fixture_id],
                "FIXTURE_CLASS",
            )
        )
    residuals = [f"{fixture_id}: {row_states[fixture_id]}" for fixture_id in blocking]
    return {
        "status": status,
        "status_basis": status_basis,
        "backing_af_verdicts": {gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]},
        "fixture_count": len(fixtures),
        "fixture_status_counts": counts,
        "fixture_ids": list(fixtures),
        "fixture_classes": {fixture_id: fixture_classes[fixture_id] for fixture_id in fixtures},
        "blocking_rows": blocking,
        "residuals": residuals,
        "citations": citations,
    }


def build_packet(repo_root: Path = REPO_ROOT, epoch_name: str = DEFAULT_EPOCH) -> dict[str, Any]:
    """Build the packet in memory; reads only sealed artifacts and config pins."""

    epoch_root_path = repo_root / "qualification" / "current-boundary-epochs" / epoch_name
    manifest = verify_epoch(epoch_root_path, repo_root)
    epoch = _json_files(epoch_root_path)
    epoch_root = f"qualification/current-boundary-epochs/{epoch_root_path.name}"

    identity = epoch["EFFECTIVE_FULL107_MANIFEST.json"]
    gate_verdicts = {
        candidate: _gate_verdicts(epoch[f"AF00_AF11_{CANDIDATE_FILES[candidate]}.json"])
        for candidate in CANDIDATES
    }
    row_states = {
        candidate: _row_states(epoch[f"FULL107_{CANDIDATE_FILES[candidate]}_RESULTS.json"])
        for candidate in CANDIDATES
    }
    fixture_classes = _fixture_classes(epoch)

    manifest_ids = {row["fixture_id"] for row in identity["rows"]}
    if identity["provider_denominator_count"] != 107 or len(manifest_ids) != 107:
        raise FailClosed(
            f"effective manifest denominator is not the frozen 107: {identity['provider_denominator_count']}"
        )
    for candidate in CANDIDATES:
        if set(row_states[candidate]) != manifest_ids:
            raise FailClosed(f"{candidate} FULL107 row set does not match the effective manifest")
    if set(fixture_classes) != manifest_ids:
        raise FailClosed("comparison row set does not match the effective manifest")

    mapped = {fixture_id for dimension in DIMENSIONS for fixture_id in dimension["fixtures"]}
    unknown_mapped = sorted(mapped - manifest_ids)
    if unknown_mapped:
        raise FailClosed(f"dimension mapping names unknown fixtures: {unknown_mapped[:5]}")
    uncovered = sorted(manifest_ids - mapped)
    if uncovered:
        raise FailClosed(f"effective denominator rows uncovered by section F: {uncovered[:5]}")
    dimension_ids = [dimension["id"] for dimension in DIMENSIONS]
    if dimension_ids != list(range(1, 22)):
        raise FailClosed("section F must contain exactly the 21 ordered dimensions")

    pin_section = _read_pin_section()
    config_digest = _sha256(repo_root / "config" / "rules_engines.json")
    xmage_lock = _xmage_pin_tree()
    if xmage_lock["commit"] != pin_section["pins"]["xmage"]["commit"]:
        raise FailClosed("XMage successor source lock disagrees with the current pin")

    forge_gates = epoch["AF00_AF11_FORGE.json"]
    xmage_gates = epoch["AF00_AF11_XMAGE.json"]
    evidence_identity = {
        "xmage_candidate_commit": _af_evidence_value(
            xmage_gates, "AF00", "candidate commit reported by the provider at handshake:"
        ),
        "forge_build_commit": _af_evidence_value(
            forge_gates, "AF00", "provider/build source commit:"
        ),
        "forge_build_tree": _af_evidence_value(forge_gates, "AF00", "provider/build source tree:"),
        "forge_rules_core_commit": _af_evidence_value(
            forge_gates, "AF00", "R-1 Rules-Core candidate commit:"
        ),
        "forge_rules_core_tree": _af_evidence_value(
            forge_gates, "AF00", "R-1 Rules-Core candidate tree:"
        ),
        "forge_rules_core_equivalence": _af_evidence_value(
            forge_gates, "AF00", "Rules-Core equivalence:"
        ),
    }
    contract_binding = _effective_contract_binding(epoch)
    drift = _drift_records(pin_section["pins"], evidence_identity, contract_binding, epoch)

    dimensions: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        dimensions.append(
            {
                "id": dimension["id"],
                "key": dimension["key"],
                "name": dimension["name"],
                "backing_af_gates": list(dimension["gates"]),
                "section_f_source": "issue-255 section F",
                "candidates": {
                    candidate: _candidate_dimension(
                        candidate,
                        dimension,
                        gate_verdicts[candidate],
                        row_states[candidate],
                        fixture_classes,
                        epoch_root,
                        epoch,
                    )
                    for candidate in CANDIDATES
                },
            }
        )

    residuals: list[dict[str, Any]] = []
    for known in KNOWN_RESIDUALS:
        candidate = known["candidate"]
        state = row_states[candidate][known["residual"]]
        residuals.append(
            {
                "residual": known["residual"],
                "candidate": candidate,
                "issue_recorded_state": known["issue_recorded_state"],
                "sealed_state": state,
                "sealed_citation": _citation(
                    f"{epoch_root}/FULL107_{CANDIDATE_FILES[candidate]}_RESULTS.json",
                    f"rows[fixture_id={known['residual']}].exit_state",
                    state,
                    "FIXTURE_ROW_STATE",
                ),
                "disposition": "REPORTED_NOT_REMEDIATED_IN_THIS_PACKET",
            }
        )

    native_receipts = epoch["NATIVE_SUITE_RECEIPTS.json"]
    pb03 = epoch["PB03_RUNTIME_EXECUTION.json"]
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": (
            "Evidence summary only. It selects no provider, ranks no candidate and makes no "
            "recommendation. Provider adjudication is Coordinator-owned in issue #255; provider "
            "selection and Architecture Freeze are Owner-reserved."
        ),
        "non_claims": {
            "production_provider": "NOT_SELECTED",
            "architecture_freeze": "NOT_CLAIMED",
            "production_repository": "NOT_CREATED",
            "ranking": "NONE",
            "recommendation": "NONE",
            "provider_selection": "RESERVED_TO_OWNER",
        },
        "source_lock": {
            "packet_source": dict(PACKET_SOURCE),
            "sealed_epoch": {
                "epoch_id": epoch_root_path.name,
                "epoch_root": epoch_root,
                "identity": epoch["EPOCH_IDENTITY.json"],
                "manifest": manifest,
            },
            "effective_contract": contract_binding,
            "engine_pins": {
                "config_file": "config/rules_engines.json",
                "config_sha256": config_digest,
                **pin_section["pins"],
                "xmage": {
                    **pin_section["pins"]["xmage"],
                    "tree": xmage_lock["tree"],
                    "tree_source": (
                        "qualification/xmage-sba-priority-repin-v4-20261003/"
                        "SUCCESSOR_SOURCE_LOCK.json#lineage.final_integrated_candidate.tree"
                    ),
                },
            },
            "evidence_identity_bindings": {
                **evidence_identity,
                "xmage_pb03_candidate_commit": pb03["candidate_commit"],
                "xmage_pb03_runner_commit": pb03["runner_commit"],
                "xmage_pb03_runner_tree": pb03["runner_tree"],
                "xmage_pb03_receipt_digest": pb03["receipt_digest"],
                "forge_bridge_identity_verified": bool(
                    epoch["AF00_AF11_FORGE.json"]["gates"][0]
                    .get("bridge_identity_proof", {})
                    .get("identical")
                ),
            },
            "drift_records": drift,
        },
        "sealed_evidence_root": epoch_root,
        "dimension_status_vocabulary": list(DIMENSION_STATUS_VOCABULARY),
        "fixture_class_vocabulary": list(FIXTURE_CLASS_VOCABULARY),
        "dimensions": dimensions,
        "known_residuals": residuals,
        "optional_metrics": {
            "authority": (
                "Informational only. Maintenance, integration and performance metrics never "
                "override Rules-correctness gates and are not selection criteria."
            ),
            "entries": [
                {
                    "metric": "native_suite_receipts",
                    "value": native_receipts["receipt_count"],
                    "citation": _citation(
                        f"{epoch_root}/NATIVE_SUITE_RECEIPTS.json",
                        "receipt_count",
                        native_receipts["receipt_count"],
                        "OPTIONAL_METRIC",
                    ),
                },
                {
                    "metric": "pb03_executed_pass",
                    "value": pb03["executed_pass"],
                    "citation": _citation(
                        f"{epoch_root}/PB03_RUNTIME_EXECUTION.json",
                        "executed_pass",
                        pb03["executed_pass"],
                        "OPTIONAL_METRIC",
                    ),
                },
            ],
        },
        "generation": {
            "deterministic": True,
            "clock": "NOT_READ",
            "network": "NOT_USED",
            "engine": "NOT_INVOKED",
            "inputs": [
                f"{epoch_root}/CURRENT_BOUNDARY_SHA256SUMS",
                f"{epoch_root}/EPOCH_IDENTITY.json",
                f"{epoch_root}/AF00_AF11_XMAGE.json",
                f"{epoch_root}/AF00_AF11_FORGE.json",
                f"{epoch_root}/FULL107_XMAGE_RESULTS.json",
                f"{epoch_root}/FULL107_FORGE_RESULTS.json",
                f"{epoch_root}/EFFECTIVE_FULL107_MANIFEST.json",
                f"{epoch_root}/CURRENT_BOUNDARY_COMPARISON.json",
                f"{epoch_root}/PLAYER_CARDINALITY_XMAGE.json",
                f"{epoch_root}/PLAYER_CARDINALITY_FORGE.json",
                f"{epoch_root}/NATIVE_SUITE_RECEIPTS.json",
                f"{epoch_root}/PB03_RUNTIME_EXECUTION.json",
                "config/rules_engines.json",
                "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
                "qualification/xmage-sba-priority-repin-v4-20261003/SUCCESSOR_SOURCE_LOCK.json",
            ],
        },
    }


def validate_packet(packet: dict[str, Any]) -> None:
    """Raise FailClosed when a packet violates the section-F rules."""

    if packet.get("schema_version") != SCHEMA_VERSION:
        raise FailClosed("unexpected packet schema_version")
    dimensions = packet.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != 21:
        raise FailClosed("packet must carry exactly the 21 section-F dimensions")
    for dimension in dimensions:
        for candidate, cell in dimension["candidates"].items():
            status = cell["status"]
            if status not in DIMENSION_STATUS_VOCABULARY:
                raise FailClosed(
                    f"unknown dimension status: {dimension['key']}/{candidate}={status}"
                )
            verdicts = cell["backing_af_verdicts"].values()
            if status == "PASS":
                if any(verdict != "PASS" for verdict in verdicts):
                    raise FailClosed(
                        f"PASS with non-PASS backing AF: {dimension['key']}/{candidate}"
                    )
                if cell["blocking_rows"]:
                    raise FailClosed(f"PASS with blocking rows: {dimension['key']}/{candidate}")
                for citation in cell["citations"]:
                    if citation["kind"] == "FIXTURE_ROW_STATE" and citation["value"] != "PASS":
                        raise FailClosed(
                            f"PASS cell cites a non-PASS sealed row: {citation['field']}"
                        )
                for state, count in cell["fixture_status_counts"].items():
                    if state != "PASS" and count:
                        raise FailClosed(
                            f"PASS with non-PASS fixture count: {dimension['key']}/{candidate}"
                        )
            for citation in cell["citations"]:
                if citation["kind"] not in {
                    "AF_GATE_VERDICT",
                    "FIXTURE_ROW_STATE",
                    "FIXTURE_CLASS",
                    "PROVIDER_CAPABILITY_DECLARATION",
                    "BOUNDED_6P_RESULT",
                }:
                    raise FailClosed(f"unknown citation kind: {citation['kind']}")
                if not citation["file"].startswith(packet["sealed_evidence_root"]):
                    raise FailClosed(
                        f"citation does not point into the sealed epoch: {citation['file']}"
                    )


def render_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Provider-readiness packet - section F (issue #255)")
    lines.append("")
    lines.append(packet["authority"])
    lines.append("")
    lines.append(
        "`PRODUCTION_PROVIDER = NOT_SELECTED` | `ARCHITECTURE_FREEZE = NOT_CLAIMED` | "
        "`PRODUCTION_REPOSITORY = NOT_CREATED`"
    )
    lines.append("")
    lines.append("## Source lock")
    lines.append("")
    lock = packet["source_lock"]
    lines.append(
        f"- Packet branch: `{lock['packet_source']['declared_branch']}` from "
        f"`{lock['packet_source']['base_main_commit']}` (tree "
        f"`{lock['packet_source']['base_main_tree']}`)."
    )
    epoch = lock["sealed_epoch"]
    lines.append(
        f"- Sealed epoch: `{epoch['epoch_id']}`; manifest "
        f"`{epoch['manifest']['path']}` sha256 `{epoch['manifest']['sha256']}`; "
        f"{epoch['manifest']['verified']}/{epoch['manifest']['entries']} digests verified "
        f"({epoch['manifest']['coverage']})."
    )
    contract = lock["effective_contract"]
    lines.append(
        f"- Effective contract: `{contract['successor_id']}` "
        f"(`{contract['successor_contract']}` sha256 `{contract['successor_sha256']}`); "
        f"pointer sha256 `{contract['pointer_sha256']}`."
    )
    pins = lock["engine_pins"]
    lines.append(
        f"- Engine pins (`{pins['config_file']}` sha256 `{pins['config_sha256']}`): "
        f"XMage `{pins['xmage']['commit'][:8]}` / tree `{pins['xmage']['tree'][:8]}`; "
        f"Forge Rules-Core `{pins['forge_rules_core']['commit'][:8]}` / tree "
        f"`{pins['forge_rules_core']['tree'][:8]}`; Forge bridge "
        f"`{pins['forge_bridge_source']['commit'][:8]}` / tree "
        f"`{pins['forge_bridge_source']['tree'][:8]}`."
    )
    lines.append("")
    lines.append("## Drift records")
    lines.append("")
    lines.append("| Subject | Pin | Sealed evidence | Verdict |")
    lines.append("| --- | --- | --- | --- |")
    for record in lock["drift_records"]:
        lines.append(
            f"| {record['subject']} | `{record['pin']}` | `{record['sealed_evidence']}` | "
            f"{record['verdict']} |"
        )
    lines.append("")
    lines.append("## Dimensions")
    lines.append("")
    lines.append(
        "| # | Dimension | XMage | XMage non-PASS fixtures | Forge | Forge non-PASS fixtures |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for dimension in packet["dimensions"]:
        cells = []
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            blocking = ", ".join(cell["blocking_rows"]) if cell["blocking_rows"] else "-"
            cells.append(f"{cell['status']} | {blocking}")
        lines.append(f"| {dimension['id']} | {dimension['name']} | {cells[0]} | {cells[1]} |")
    lines.append("")
    lines.append("Backing AF verdicts per dimension:")
    lines.append("")
    lines.append("| # | Dimension | XMage AFs | Forge AFs |")
    lines.append("| --- | --- | --- | --- |")
    for dimension in packet["dimensions"]:
        gate_summaries = []
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            gate_summaries.append(
                ", ".join(
                    f"{gate}={cell['backing_af_verdicts'][gate]}"
                    for gate in cell["backing_af_verdicts"]
                )
            )
        lines.append(
            f"| {dimension['id']} | {dimension['name']} | {gate_summaries[0]} | {gate_summaries[1]} |"
        )
    lines.append("")
    lines.append("## Known residuals (issue-recorded state beside current sealed state)")
    lines.append("")
    lines.append("| Residual | Candidate | Issue-recorded state | Sealed state |")
    lines.append("| --- | --- | --- | --- |")
    for residual in packet["known_residuals"]:
        lines.append(
            f"| {residual['residual']} | {residual['candidate']} | "
            f"{residual['issue_recorded_state']} | {residual['sealed_state']} |"
        )
    lines.append("")
    lines.append("## Optional metrics (never a Rules-correctness gate)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for entry in packet["optional_metrics"]["entries"]:
        lines.append(f"| {entry['metric']} | {entry['value']} |")
    lines.append("")
    lines.append(
        "Every status above is derived from the sealed artifacts cited in "
        "`PROVIDER_READINESS.json`; `UNKNOWN != PASS`. Regenerate with "
        "`python3 scripts/build_provider_readiness_packet.py`; verify with `--check`."
    )
    lines.append("")
    return "\n".join(lines)


def render_outputs(repo_root: Path = REPO_ROOT, epoch: str = DEFAULT_EPOCH) -> tuple[str, str]:
    packet = build_packet(repo_root=repo_root, epoch_name=epoch)
    validate_packet(packet)
    json_text = json.dumps(packet, indent=2, sort_keys=False) + "\n"
    return json_text, render_markdown(packet)


def write_outputs(repo_root: Path = REPO_ROOT, epoch: str = DEFAULT_EPOCH) -> int:
    json_text, markdown = render_outputs(repo_root=repo_root, epoch=epoch)
    PACKET_JSON.write_text(json_text, encoding="utf-8")
    PACKET_MD.write_text(markdown, encoding="utf-8")
    print(f"wrote {PACKET_JSON.relative_to(repo_root)}")
    print(f"wrote {PACKET_MD.relative_to(repo_root)}")
    return 0


def check_outputs(repo_root: Path = REPO_ROOT, epoch: str = DEFAULT_EPOCH) -> int:
    json_text, markdown = render_outputs(repo_root=repo_root, epoch=epoch)
    failures: list[str] = []
    for path, expected in ((PACKET_JSON, json_text), (PACKET_MD, markdown)):
        if not path.is_file():
            failures.append(f"missing committed output: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            failures.append(f"committed output differs from regeneration: {path}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        print(
            "ERROR: --check failed; regenerate with "
            "python3 scripts/build_provider_readiness_packet.py",
            file=sys.stderr,
        )
        return 1
    print("provider-readiness packet is byte-identical to a fresh deterministic regeneration")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="verify committed output is byte-identical"
    )
    parser.add_argument("--epoch", default=DEFAULT_EPOCH, help="sealed epoch directory name")
    args = parser.parse_args(argv)
    try:
        if args.check:
            return check_outputs(epoch=args.epoch)
        return write_outputs(epoch=args.epoch)
    except FailClosed as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
