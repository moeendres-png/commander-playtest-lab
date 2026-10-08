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
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EPOCH = "ff688b58359f-42c21a3659cd"
PACKET_DIR = REPO_ROOT / "docs" / "provider_readiness_packet_20261007"
PACKET_JSON = PACKET_DIR / "PROVIDER_READINESS.json"
PACKET_MD = PACKET_DIR / "PROVIDER_READINESS.md"

# Provenance of the packet itself: the main commit/tree this workstream started
# from.  Deliberately constants: the generator must not read mutable Git state.
PACKET_SOURCE = {
    "repository": "moeendres-png/commander-playtest-lab",
    "declared_branch": "opencode/issue255-20261008194759",
    "base_main_commit": "ff688b58359f7ec3cbace344322989c18e58886a",
    "base_main_tree": "42c21a3659cdf73ca15d1baaf62bbfed9003c797",
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
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

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

# Explicit, fail-closed evidence requirements for dimensions whose backing gate
# subject is broader than the dimension itself.  A cell may become PASS only when
# these exact sealed facts are present, so a dimension can never inherit PASS
# from an adjacent gate subject without its own dimension-specific evidence.
REQUIRED_GATE_EVIDENCE: dict[str, tuple[dict[str, str], ...]] = {
    "process_isolation": (
        {
            "gate": "AF11",
            "evidence_prefix": (
                "each candidate was driven through its own distinct external adapter"
            ),
            "meaning": "each candidate is reached only through its own external adapter process",
        },
        {
            "gate": "AF11",
            "evidence_prefix": ("no adapter identity resolves to the Lab's in-tree engine package"),
            "meaning": "no engine code is embedded in the Lab process",
        },
    ),
}

# Bounded-6P status derivation from the sealed failure facts.  A fail-closed
# refusal that only proves the record could not be driven stays UNKNOWN with the
# sealed cause; a FAIL-class failure is FAIL; unknown vocabulary fails closed so
# it can never be rendered as a benign NOT_RUN/UNSUPPORTED.
#
# A run with no failure_kind (the 1.0.23 record-declared starting seat run) is a
# success CLAIM, not a success.  It becomes PASS only when the sealed evidence
# positively proves every fact of a completed bounded-6P game, and those facts
# are cited one by one: a successful start status when the provider publishes
# one (Forge publishes "started"; XMage publishes no start status and the
# lifecycle proof carries), a complete Commander lifecycle, an empty AF04
# bounded-secondary gap list for that candidate, and AF02 PASS.  Anything less
# is UNKNOWN with the unmet condition named, never PASS.
BOUNDED_6P_REFUSAL_STATUS = {
    "FAIL_CLOSED_UNSATISFIED": "UNKNOWN",
    "RECORD_REFUSED": "UNKNOWN",
}
BOUNDED_6P_FAILURE_STATUS = {state: "FAIL" for state in FAILING_ROW_STATES}
BOUNDED_6P_FAILURE_STATUS["ENGINE_RUNTIME_ERROR"] = "FAIL"

# The sealed start-status vocabulary: a provider that publishes a start status
# says exactly this on success (the only observed sealed success value).  Any
# other published value, including "completed", fails closed.
BOUNDED_6P_SUCCESS_START_STATUS = frozenset({"started"})

# XMage's sealed positive start fact when no start status is published: the
# engine-confirmed starting-seat channel, and the provider-confirmed seat equal
# to the record-declared starting seat.  Both facts are cited in the cell.
BOUNDED_6P_XMAGE_START_CHANNEL = "PROVIDER_ENGINE_CONFIRMED_STARTING_SEAT"
BOUNDED_6P_PLAYER_COUNT = 6

# The required Commander lifecycle prefix, in order, mirroring
# ``commander_lab.qualification.current_boundary.lifecycle``.  Kept local so the
# generator stays standalone (no package import, no clock, no network).
BOUNDED_6P_REQUIRED_LIFECYCLE_STEPS = (
    "handshake",
    "import_deck",
    "create_commander_game",
    "start_game",
    "decision_drive",
)

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
        if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
            raise FailClosed(f"malformed manifest line {lineno}: {raw!r}")
        digest, relative = parts[0], parts[1]
        if relative in entries:
            raise FailClosed(f"duplicate manifest entry {lineno}: {relative!r}")
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


def _gate_documents(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for gate in document["gates"]:
        gate_id = gate["gate"]
        if gate_id in gates:
            raise FailClosed(f"duplicate AF gate: {gate_id}")
        gates[gate_id] = gate
    return gates


def _gate_row_field(gate: dict[str, Any], field: str) -> list[str]:
    value = gate.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FailClosed(f"gate {gate.get('gate')} lacks a valid {field} list")
    return list(value)


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


ALL_PASS_STATUS_BASIS = "ALL_BACKING_GATES_PASS_AND_ALL_FIXTURES_PASS"
FAIL_STATUS_BASIS = "FAIL_CLASS_EVIDENCE_PRESENT"
NOT_RUN_STATUS_BASIS = "ALL_BACKING_GATES_AND_FIXTURES_NOT_RUN"


def derive_status_basis(
    status: str, gate_verdicts: dict[str, str], fixture_states: list[str]
) -> str:
    """Return an accurate basis string for a non-special dimension cell.

    Only an all-PASS cell carries the all-PASS basis.  FAIL, NOT_RUN and
    UNKNOWN cells state the evidence facts that actually produced the status so
    a non-PASS cell can never claim that every backing gate and fixture passed.
    """

    if status == "PASS":
        return ALL_PASS_STATUS_BASIS
    if status == "NOT_RUN":
        return NOT_RUN_STATUS_BASIS
    unresolved_gates = ",".join(
        f"{gate}={verdict}" for gate, verdict in sorted(gate_verdicts.items()) if verdict != "PASS"
    )
    if status == "FAIL":
        failing_fixtures = sum(1 for state in fixture_states if state in FAILING_ROW_STATES)
        return (
            f"{FAIL_STATUS_BASIS}:gates={unresolved_gates or 'none'}:"
            f"fail_class_fixtures={failing_fixtures}"
        )
    unresolved_fixtures = sum(1 for state in fixture_states if state != "PASS")
    return (
        "NOT_ALL_BACKING_GATES_AND_FIXTURES_PASS:"
        f"gates={unresolved_gates or 'none'}:unresolved_fixtures={unresolved_fixtures}"
    )


def missing_required_gate_evidence(
    gate_documents: dict[str, dict[str, Any]],
    requirements: tuple[dict[str, str], ...],
) -> list[str]:
    """Return the dimension-specific gate evidence facts that are absent."""

    missing: list[str] = []
    for requirement in requirements:
        gate = gate_documents.get(requirement["gate"])
        if gate is None:
            missing.append(f"{requirement['gate']}: gate missing")
            continue
        if not any(
            str(item).startswith(requirement["evidence_prefix"])
            for item in gate.get("evidence", [])
        ):
            missing.append(f"{requirement['gate']}: {requirement['evidence_prefix']!r}")
    return missing


def _is_int(value: Any) -> bool:
    """True only for a real integer (bools are not player counts)."""

    return isinstance(value, int) and not isinstance(value, bool)


def _bounded_6p_start_gaps(candidate: str, terminal_facts: dict[str, Any]) -> list[str]:
    """Return the missing positive start fact(s) for a claimed 6P success.

    Every candidate must positively prove that the bounded-6P game started.
    Forge publishes ``start_status``; it must be exactly the observed sealed
    success value ("started").  XMage publishes no start status (sealed null);
    its positive start fact is the engine-confirmed starting-seat channel plus
    the provider-confirmed seat equalling the record-declared starting seat.
    Any other published start status fails closed.
    """

    if candidate not in CANDIDATES:
        raise FailClosed(f"unknown candidate for bounded-6P start fact: {candidate!r}")

    start_status = terminal_facts.get("start_status")
    if start_status is not None:
        if not isinstance(start_status, str):
            raise FailClosed(
                f"bounded-6P start_status for {candidate} is not a string: "
                f"{start_status!r}; re-adjudicate this cell"
            )
        if start_status not in BOUNDED_6P_SUCCESS_START_STATUS:
            raise FailClosed(
                f"unknown bounded-6P start_status for {candidate}: {start_status!r}; "
                "the cell fails closed rather than granting success credit"
            )

    gaps: list[str] = []
    if candidate == "forge":
        if start_status != "started":
            gaps.append(f"FORGE_START_STATUS_NOT_OBSERVED:{start_status!r}")
        return gaps

    channel = terminal_facts.get("starting_player_channel")
    declared = terminal_facts.get("declared_starting_seat")
    confirmed = terminal_facts.get("starting_player_provider_confirmed_seat")
    if channel != BOUNDED_6P_XMAGE_START_CHANNEL:
        gaps.append(f"XMAGE_STARTING_PLAYER_CHANNEL:{channel!r}")
    if not isinstance(declared, str) or not declared:
        gaps.append(f"XMAGE_DECLARED_STARTING_SEAT:{declared!r}")
    if not isinstance(confirmed, str) or not confirmed:
        gaps.append(f"XMAGE_CONFIRMED_STARTING_SEAT:{confirmed!r}")
    elif isinstance(declared, str) and declared and confirmed != declared:
        gaps.append(f"XMAGE_CONFIRMED_STARTING_SEAT_MISMATCH:{confirmed!r}!={declared!r}")
    return gaps


def _bounded_6p_success_gaps(
    candidate: str,
    result_6p: dict[str, Any],
    af02_verdict: str | None,
    af04_gate: dict[str, Any] | None,
) -> list[str]:
    """Return the unmet positive-success conditions for a claimed 6P success.

    Every condition the packet cites for a bounded-6P PASS is checked here from
    the sealed documents alone.  An empty list is the only state that may become
    PASS; each returned item names the exact missing sealed fact.
    """

    gaps: list[str] = []
    terminal_facts = result_6p.get("terminal_facts")
    if not isinstance(terminal_facts, dict):
        terminal_facts = {}

    gaps.extend(_bounded_6p_start_gaps(candidate, terminal_facts))

    completed = result_6p.get("steps_completed")
    completed_steps = list(completed) if isinstance(completed, list) else []
    missing = [step for step in BOUNDED_6P_REQUIRED_LIFECYCLE_STEPS if step not in completed_steps]
    if missing:
        gaps.append("LIFECYCLE_STEPS_MISSING:" + ",".join(missing))
    elif completed_steps:
        indices = [completed_steps.index(step) for step in BOUNDED_6P_REQUIRED_LIFECYCLE_STEPS]
        if indices != sorted(indices):
            gaps.append("LIFECYCLE_STEPS_OUT_OF_ORDER")
    if terminal_facts.get("priority_reached") is not True:
        gaps.append("PRIORITY_NOT_REACHED")

    declared = result_6p.get("player_count")
    created = terminal_facts.get("created_player_count")
    if not _is_int(declared) or not _is_int(created):
        gaps.append(f"PLAYER_COUNT_FACTS_NOT_INTS:{declared!r}/{created!r}")
    elif declared != created:
        gaps.append(f"PLAYER_COUNT_MISMATCH:{declared!r}!={created!r}")
    elif declared != BOUNDED_6P_PLAYER_COUNT:
        gaps.append(f"PLAYER_COUNT_NOT_BOUNDED_6P:{declared!r}")

    tape = result_6p.get("decision_tape")
    bound_choices = [
        entry for entry in (tape or []) if isinstance(entry, dict) and entry.get("chosen_option_id")
    ]
    if not bound_choices:
        gaps.append("NO_BOUND_EXTERNAL_CHOICE")

    if af02_verdict != "PASS":
        gaps.append(f"AF02_PLAYER_CARDINALITY:{af02_verdict!r}")

    af04_verdict = af04_gate.get("verdict") if isinstance(af04_gate, dict) else None
    af04_blocking = af04_gate.get("blocking_rows") if isinstance(af04_gate, dict) else None
    if af04_verdict != "PASS" or af04_blocking != []:
        gaps.append(f"AF04_BOUNDED_SECONDARY_GAPS:{af04_verdict!r}/{af04_blocking!r}")
    contradictions = None
    if isinstance(af04_gate, dict):
        boundary = af04_gate.get("decision_boundary")
        if isinstance(boundary, dict):
            contradictions = boundary.get("contradictions")
    if isinstance(contradictions, list) and contradictions:
        gaps.append(f"AF04_DECISION_BOUNDARY_CONTRADICTIONS:{len(contradictions)}")

    failure_text = result_6p.get("failure")
    if failure_text:
        gaps.append(f"FAILURE_TEXT_WITHOUT_FAILURE_KIND:{failure_text!r}")
    return gaps


def derive_bounded_6p_status(
    candidate: str,
    result_6p: dict[str, Any],
    *,
    af02_verdict: str | None = None,
    af04_gate: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """Derive the bounded-6P cell status from the sealed failure facts.

    A fail-closed refusal that only proves the record could not be driven stays
    UNKNOWN with the sealed cause.  A FAIL-class failure is FAIL.  A run with no
    failure_kind is PASS only when the sealed evidence positively proves a
    completed bounded-6P lifecycle, a clean AF04 bounded-secondary boundary and
    AF02 PASS, plus the candidate's own positive start fact (Forge
    ``start_status == "started"``; XMage engine-confirmed starting-seat channel
    with the provider-confirmed seat equalling the declared seat).  Unknown
    failure/start vocabulary fails closed; an unproven success claim is UNKNOWN
    with the unmet condition named, never PASS.
    """

    failure_kind = result_6p.get("failure_kind")
    if failure_kind is None:
        gaps = _bounded_6p_success_gaps(candidate, result_6p, af02_verdict, af04_gate)
        if gaps:
            return (
                "UNKNOWN",
                "BOUNDED_6P_SUCCESS_CLAIM_UNPROVEN_" + "_".join(gaps),
                "success_unproven",
            )
        return (
            "PASS",
            "BOUNDED_6P_LIFECYCLE_AND_AF04_BOUNDED_SECONDARY_PROVEN",
            "success",
        )
    if failure_kind in BOUNDED_6P_REFUSAL_STATUS:
        return (
            BOUNDED_6P_REFUSAL_STATUS[failure_kind],
            f"BOUNDED_6P_{failure_kind}_RECORD_AUTHORITY_GAP",
            str(failure_kind),
        )
    if failure_kind in BOUNDED_6P_FAILURE_STATUS:
        return ("FAIL", f"BOUNDED_6P_FAILURE_{failure_kind}", str(failure_kind))
    raise FailClosed(
        f"unknown bounded-6P failure_kind for {candidate}: {failure_kind!r}; "
        "the cell fails closed rather than rendering a benign status"
    )


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
    gate_documents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate_file = f"{epoch_root}/AF00_AF11_{CANDIDATE_FILES[candidate]}.json"
    gate_citations = [
        _citation(
            gate_file,
            f"gates[gate={gate_id}].verdict",
            gate_verdicts[gate_id],
            "AF_GATE_VERDICT",
        )
        for gate_id in dimension["gates"]
    ]
    gate_blocking_rows = {
        gate_id: _gate_row_field(gate_documents[gate_id], "blocking_rows")
        for gate_id in dimension["gates"]
    }
    gate_limitations = {
        gate_id: _gate_row_field(gate_documents[gate_id], "nonblocking_limitations")
        for gate_id in dimension["gates"]
    }
    gate_residuals: list[str] = []
    gate_fact_citations: list[dict[str, str]] = []
    for gate_id in dimension["gates"]:
        gate_residuals.extend(
            f"{gate_id} blocking row: {row}" for row in gate_blocking_rows[gate_id]
        )
        gate_residuals.extend(
            f"{gate_id} limitation: {limitation}" for limitation in gate_limitations[gate_id]
        )
        gate_fact_citations.append(
            _citation(
                gate_file,
                f"gates[gate={gate_id}].blocking_rows",
                gate_blocking_rows[gate_id],
                "AF_GATE_BLOCKING_ROWS",
            )
        )
        gate_fact_citations.append(
            _citation(
                gate_file,
                f"gates[gate={gate_id}].nonblocking_limitations",
                gate_limitations[gate_id],
                "AF_GATE_NONBLOCKING_LIMITATIONS",
            )
        )
    if dimension["special"] == "bounded_6p":
        cardinality = epoch[f"PLAYER_CARDINALITY_{CANDIDATE_FILES[candidate]}.json"]
        result_6p = cardinality["results"]["6P"]
        af02_verdict = gate_verdicts["AF02"]
        af04_gate = gate_documents["AF04"]
        status, status_basis, failure_kind = derive_bounded_6p_status(
            candidate, result_6p, af02_verdict=af02_verdict, af04_gate=af04_gate
        )
        terminal_facts = result_6p.get("terminal_facts") or {}
        start_status = terminal_facts.get("start_status")
        if start_status is not None and not isinstance(start_status, str):
            raise FailClosed("bounded-6P start_status is not a string; re-adjudicate this cell")
        citation_root = f"{epoch_root}/PLAYER_CARDINALITY_{CANDIDATE_FILES[candidate]}.json"
        af04_citations = [
            _citation(
                gate_file,
                "gates[gate=AF04].verdict",
                af04_gate.get("verdict"),
                "AF_GATE_VERDICT",
            ),
            _citation(
                gate_file,
                "gates[gate=AF04].blocking_rows",
                af04_gate.get("blocking_rows"),
                "AF_GATE_BLOCKING_ROWS",
            ),
        ]
        citations = [
            *gate_citations,
            *gate_fact_citations,
            *af04_citations,
            _citation(
                citation_root,
                "results.6P.failure_kind",
                result_6p.get("failure_kind"),
                "BOUNDED_6P_RESULT",
            ),
            _citation(
                citation_root,
                "results.6P.steps_completed",
                result_6p.get("steps_completed"),
                "BOUNDED_6P_RESULT",
            ),
            _citation(
                citation_root,
                "results.6P.terminal_facts.start_status",
                start_status,
                "BOUNDED_6P_RESULT",
            ),
            _citation(
                citation_root,
                "results.6P.terminal_facts.created_player_count",
                terminal_facts.get("created_player_count"),
                "BOUNDED_6P_RESULT",
            ),
            _citation(
                citation_root,
                "results.6P.terminal_facts.priority_reached",
                terminal_facts.get("priority_reached"),
                "BOUNDED_6P_RESULT",
            ),
        ]
        if candidate == "xmage":
            # XMage's positive start fact is the engine-confirmed starting-seat
            # channel plus the provider-confirmed seat equalling the declared
            # seat; both facts are cited beside the (null) start_status.
            citations.extend(
                [
                    _citation(
                        citation_root,
                        "results.6P.terminal_facts.starting_player_channel",
                        terminal_facts.get("starting_player_channel"),
                        "BOUNDED_6P_RESULT",
                    ),
                    _citation(
                        citation_root,
                        "results.6P.terminal_facts.declared_starting_seat",
                        terminal_facts.get("declared_starting_seat"),
                        "BOUNDED_6P_RESULT",
                    ),
                    _citation(
                        citation_root,
                        "results.6P.terminal_facts.starting_player_provider_confirmed_seat",
                        terminal_facts.get("starting_player_provider_confirmed_seat"),
                        "BOUNDED_6P_RESULT",
                    ),
                ]
            )
        if candidate == "forge":
            start_fact_summary = f"start_status={start_status!r}"
        else:
            start_fact_summary = (
                f"channel={terminal_facts.get('starting_player_channel')!r}, "
                "starting_player_provider_confirmed_seat="
                f"{terminal_facts.get('starting_player_provider_confirmed_seat')!r}, "
                f"declared_starting_seat={terminal_facts.get('declared_starting_seat')!r}"
            )
        if status == "PASS":
            residuals = [
                "6P bounded secondary evidence is established by the sealed facts: "
                f"failure_kind={result_6p.get('failure_kind')!r}, sealed "
                f"start_status={start_status!r}, positive start fact: {start_fact_summary}, "
                f"lifecycle steps {BOUNDED_6P_REQUIRED_LIFECYCLE_STEPS}, created_player_count="
                f"{terminal_facts.get('created_player_count')!r}, priority_reached="
                f"{terminal_facts.get('priority_reached')!r}, AF02={af02_verdict}, "
                f"AF04={af04_gate.get('verdict')}, AF04 blocking rows "
                f"{af04_gate.get('blocking_rows')!r}"
            ]
        else:
            failure_text = result_6p.get("failure")
            if result_6p.get("failure_kind") is not None and (
                not isinstance(failure_text, str) or not failure_text
            ):
                raise FailClosed("bounded-6P failure result does not state its sealed cause")
            if not isinstance(failure_text, str) or not failure_text:
                failure_text = status_basis
            residuals = [
                f"6P bounded secondary evidence is not established ({failure_kind}); "
                f"sealed start_status={start_status!r}; sealed cause: {failure_text}"
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
            "gate_blocking_rows": gate_blocking_rows,
            "gate_nonblocking_limitations": gate_limitations,
            "blocking_rows": [],
            "residuals": [*residuals, *gate_residuals],
            "citations": citations,
        }

    fixtures = tuple(sorted(dimension["fixtures"]))
    counts, fixture_blocking = _dimension_fixture_status(fixtures, row_states)
    fixture_states = [row_states[fixture_id] for fixture_id in fixtures]
    status = derive_status(
        {gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]}, fixture_states
    )
    status_basis = derive_status_basis(
        status,
        {gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]},
        fixture_states,
    )
    required_evidence = REQUIRED_GATE_EVIDENCE.get(dimension["key"], ())
    missing_evidence = missing_required_gate_evidence(gate_documents, required_evidence)
    if status == "PASS" and missing_evidence:
        raise FailClosed(
            f"{dimension['key']}/{candidate} would be PASS without required gate evidence: "
            f"{missing_evidence}"
        )

    gate_blocking_flat = [
        row for gate_id in dimension["gates"] for row in gate_blocking_rows[gate_id]
    ]
    blocking = sorted(set(gate_blocking_flat) | set(fixture_blocking))
    cited_fixtures = fixtures if status == "PASS" or not blocking else tuple(blocking)
    citations = [*gate_citations, *gate_fact_citations]
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
    residuals = [f"{fixture_id}: {row_states[fixture_id]}" for fixture_id in fixture_blocking]
    residuals.extend(gate_residuals)
    return {
        "status": status,
        "status_basis": status_basis,
        "backing_af_verdicts": {gate_id: gate_verdicts[gate_id] for gate_id in dimension["gates"]},
        "fixture_count": len(fixtures),
        "fixture_status_counts": counts,
        "fixture_ids": list(fixtures),
        "fixture_classes": {fixture_id: fixture_classes[fixture_id] for fixture_id in fixtures},
        "gate_blocking_rows": gate_blocking_rows,
        "gate_nonblocking_limitations": gate_limitations,
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
    gate_documents = {
        candidate: _gate_documents(epoch[f"AF00_AF11_{CANDIDATE_FILES[candidate]}.json"])
        for candidate in CANDIDATES
    }
    gate_verdicts = {
        candidate: _gate_verdicts(epoch[f"AF00_AF11_{CANDIDATE_FILES[candidate]}.json"])
        for candidate in CANDIDATES
    }
    gate_names: dict[str, str] = {}
    for candidate in CANDIDATES:
        for gate_id, gate in gate_documents[candidate].items():
            name = gate.get("name")
            if not isinstance(name, str) or not name:
                raise FailClosed(f"gate {gate_id} lacks a name")
            if gate_id in gate_names and gate_names[gate_id] != name:
                raise FailClosed(f"gate {gate_id} name differs between candidates")
            gate_names[gate_id] = name
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
                "backing_af_gate_names": {
                    gate_id: gate_names[gate_id] for gate_id in dimension["gates"]
                },
                "required_gate_evidence": [
                    dict(requirement)
                    for requirement in REQUIRED_GATE_EVIDENCE.get(dimension["key"], ())
                ],
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
                        gate_documents[candidate],
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
            backing_gates = set(dimension["backing_af_gates"])
            if set(cell["gate_blocking_rows"]) != backing_gates:
                raise FailClosed(
                    f"gate blocking-row mapping does not match backing gates: "
                    f"{dimension['key']}/{candidate}"
                )
            if set(cell["gate_nonblocking_limitations"]) != backing_gates:
                raise FailClosed(
                    f"gate limitation mapping does not match backing gates: "
                    f"{dimension['key']}/{candidate}"
                )
            gate_rows = {row for rows in cell["gate_blocking_rows"].values() for row in rows}
            if not gate_rows <= set(cell["blocking_rows"]):
                raise FailClosed(
                    f"gate blocking rows are missing from the cell blocking rows: "
                    f"{dimension['key']}/{candidate}"
                )
            for gate_id, rows in cell["gate_blocking_rows"].items():
                for row in rows:
                    if f"{gate_id} blocking row: {row}" not in cell["residuals"]:
                        raise FailClosed(
                            f"gate blocking row missing from residuals: "
                            f"{dimension['key']}/{candidate}/{gate_id}/{row}"
                        )
            for gate_id, limitations in cell["gate_nonblocking_limitations"].items():
                for limitation in limitations:
                    if f"{gate_id} limitation: {limitation}" not in cell["residuals"]:
                        raise FailClosed(
                            f"gate nonblocking limitation missing from residuals: "
                            f"{dimension['key']}/{candidate}/{gate_id}"
                        )
            verdicts = cell["backing_af_verdicts"].values()
            if status == "PASS":
                if any(verdict != "PASS" for verdict in verdicts):
                    raise FailClosed(
                        f"PASS with non-PASS backing AF: {dimension['key']}/{candidate}"
                    )
                if cell["blocking_rows"]:
                    raise FailClosed(f"PASS with blocking rows: {dimension['key']}/{candidate}")
                if any(cell["gate_blocking_rows"].values()):
                    raise FailClosed(
                        f"PASS with gate blocking rows: {dimension['key']}/{candidate}"
                    )
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
                    "AF_GATE_BLOCKING_ROWS",
                    "AF_GATE_NONBLOCKING_LIMITATIONS",
                    "FIXTURE_ROW_STATE",
                    "FIXTURE_CLASS",
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
    lines.append("## Dimension-to-backing-gate mapping")
    lines.append("")
    lines.append(
        "AF10 (RUNTIME_EVIDENCE_RELIABILITY) is cross-cutting and is not a backing gate "
        "of any section-F dimension; its denominator accounting is cited through the "
        "sealed epoch and the optional metrics."
    )
    lines.append("")
    lines.append(
        "| # | Dimension | Backing AF gates | Required dimension-specific evidence facts |"
    )
    lines.append("| --- | --- | --- | --- |")
    for dimension in packet["dimensions"]:
        gates = ", ".join(
            f"{gate_id} ({dimension['backing_af_gate_names'][gate_id]})"
            for gate_id in dimension["backing_af_gates"]
        )
        required = dimension.get("required_gate_evidence") or []
        facts = (
            "; ".join(f"{item['gate']}: {item['meaning']}" for item in required).replace("|", "\\|")
            if required
            else "-"
        )
        lines.append(f"| {dimension['id']} | {dimension['name']} | {gates} | {facts} |")
    lines.append("")
    lines.append("## Backing-gate residuals (blocking rows and nonblocking limitations)")
    lines.append("")
    lines.append(
        "Every backing gate's sealed blocking rows and nonblocking limitations are carried "
        "beside the dimension, including beside PASS cells."
    )
    lines.append("")
    lines.append("| # | Dimension | Candidate | Gate | Blocking rows | Nonblocking limitations |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for dimension in packet["dimensions"]:
        for candidate in CANDIDATES:
            cell = dimension["candidates"][candidate]
            for gate_id in dimension["backing_af_gates"]:
                rows = cell["gate_blocking_rows"][gate_id]
                limitations = cell["gate_nonblocking_limitations"][gate_id]
                if not rows and not limitations:
                    continue
                row_text = ", ".join(rows).replace("|", "\\|") if rows else "-"
                limitation_text = "; ".join(limitations).replace("|", "\\|") if limitations else "-"
                lines.append(
                    f"| {dimension['id']} | {dimension['name']} | {candidate} | {gate_id} | "
                    f"{row_text} | {limitation_text} |"
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
