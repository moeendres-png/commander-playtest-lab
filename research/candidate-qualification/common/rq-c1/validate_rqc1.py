#!/usr/bin/env python3
"""RQ-C1 corpus validator (§33 machine checks). Fails closed (exit != 0) on any violation.

Checks: unique IDs; files exist; >=1 card; authority status; setup boundary;
no candidate-native IDs in neutral semantic fields; no forbidden evidence class;
no READY with authority gate; hidden checkpoints; RNG journal expectations;
first-wave reverser mapping; negative controls not counted as scenarios;
deterministic round-trip; stable sorted output; incidence-row uniqueness.
"""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCEN_DIR = BASE / "scenarios"
FAILURES = []

VALID_STATUS = {
    "READY_FOR_COORDINATOR_RULES_ADJUDICATION",
    "READY_FOR_CANDIDATE_EXECUTION",
    "AUTHORITY_GATE_REQUIRED",
    "SETUP_BOUNDARY_UNRESOLVED",
    "REJECTED",
    "DEFERRED",
}
VALID_AUTHORITY = {
    "OFFICIAL_RULES_DIRECT",
    "OFFICIAL_ORACLE_DIRECT",
    "OFFICIAL_RULING_DIRECT",
    "MECHANICALLY_DERIVED_FROM_OFFICIAL_AUTHORITY",
    "AUTHORITY_GATE_REQUIRED",
    "METADATA_ONLY",
}
VALID_BOUNDARY = {
    "NATURAL_GAME_START",
    "PRE_DECISION_CONSTRUCTION",
    "PRE_PHASE_NATIVE_PROGRESSION",
    "PRE_STEP_NATIVE_PROGRESSION",
    "OTHER_NATIVE_SAFE_BOUNDARY",
    "UNRESOLVED_SETUP_BOUNDARY",
}
VALID_REUSE = {
    "ORIGINAL_PROJECT_CASE",
    "CLEAN_ROOM_DERIVED_CASE_IDEA",
    "OFFICIAL_RULES_DERIVED",
    "REFERENCE_ONLY",
    "LEGAL_REVIEW_REQUIRED",
}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
NATIVE_ID_RE = re.compile(
    r"(SpellAbility|MageObject|AbilityId|EntityId|stateId|requestId|interactionEpoch|r\d+-\d+)",
)
SEMANTIC_FIELDS = (
    "neutral_initial_state",
    "external_decision_script",
    "expected_rules_events",
    "expected_terminal_assertions",
    "hidden_information_checkpoints",
    "rng_operations",
    "decision_kinds",
)


def fail(msg):
    FAILURES.append(msg)


def main():
    files = sorted(SCEN_DIR.glob("RQ-C1-*.json"))
    scenarios = []
    for f in files:
        try:
            scenarios.append(json.loads(f.read_text()))
        except json.JSONDecodeError as e:
            fail(f"{f.name}: invalid JSON: {e}")
    ids = [s.get("scenario_id") for s in scenarios]
    if len(ids) != len(set(ids)):
        fail("scenario IDs not unique")
    for f in files:
        stem = f.stem
        if stem not in ids:
            fail(f"{f.name}: file stem does not match any scenario_id")

    for s in scenarios:
        sid = s.get("scenario_id", "?")
        if not re.fullmatch(r"RQ-C1-[A-K][0-9]{2}", sid or ""):
            fail(f"{sid}: bad scenario_id shape")
        if not s.get("actual_cards"):
            fail(f"{sid}: no actual cards")
        for c in s.get("actual_cards", []):
            if not c.get("name") or not c.get("oracle_text") or not c.get("provenance"):
                fail(f"{sid}: card record incomplete: {c.get('name')}")
        if s.get("authority_status") not in VALID_AUTHORITY:
            fail(f"{sid}: bad authority_status")
        if s.get("status") not in VALID_STATUS:
            fail(f"{sid}: bad status")
        if s.get("native_setup_boundary") not in VALID_BOUNDARY:
            fail(f"{sid}: bad native_setup_boundary")
        if s.get("legal_reuse_class") not in VALID_REUSE:
            fail(f"{sid}: bad legal_reuse_class")
        if s.get("status") == "READY_FOR_CANDIDATE_EXECUTION" and s.get(
            "authority_status"
        ) == "AUTHORITY_GATE_REQUIRED":
            fail(f"{sid}: READY with unresolved authority gate")
        if not s.get("decision_kinds"):
            fail(f"{sid}: no decision kinds")
        if not s.get("architecture_reverser_axes"):
            fail(f"{sid}: no reverser axes")
        if not s.get("expected_rules_events") or not s.get(
            "expected_terminal_assertions"
        ):
            fail(f"{sid}: missing expected events/assertions")
        if not s.get("external_decision_script"):
            fail(f"{sid}: missing decision script")
        blob = json.dumps({k: s.get(k) for k in SEMANTIC_FIELDS})
        if UUID_RE.search(blob):
            fail(f"{sid}: candidate-native UUID in neutral semantic fields")
        if NATIVE_ID_RE.search(blob):
            fail(f"{sid}: candidate-native ID token in neutral semantic fields")
        cps = s.get("hidden_information_checkpoints", [])
        if not cps:
            fail(f"{sid}: no hidden-info checkpoints")
        if "HIDDEN_INFO" in s.get("architecture_reverser_axes", []) and len(cps) < 2:
            fail(f"{sid}: HIDDEN_INFO axis needs >=2 checkpoints")
        if "RULES_RNG" in s.get("architecture_reverser_axes", []):
            if not s.get("rng_operations"):
                fail(f"{sid}: RULES_RNG axis without rng_operations")
            for op in s.get("rng_operations", []):
                for k in ("operation", "purpose", "domain", "assertion"):
                    if not op.get(k):
                        fail(f"{sid}: rng op missing {k}")
            if not s.get("neutral_initial_state", {}).get("rng_starting_contract"):
                fail(f"{sid}: RNG scenario without rng_starting_contract")
        if s.get("first_wave") and not s.get("reverses"):
            fail(f"{sid}: first-wave without reverser mapping")
        if not isinstance(s.get("player_count"), int):
            fail(f"{sid}: player_count not int")

    first_wave = sorted(s["scenario_id"] for s in scenarios if s.get("first_wave"))
    expected_fw = sorted([
        "RQ-C1-A03", "RQ-C1-A04", "RQ-C1-B01", "RQ-C1-C01", "RQ-C1-C03",
        "RQ-C1-D06", "RQ-C1-E01", "RQ-C1-E02", "RQ-C1-F01", "RQ-C1-G02",
        "RQ-C1-G03", "RQ-C1-G04", "RQ-C1-H01", "RQ-C1-I01", "RQ-C1-J02",
    ])
    if first_wave != expected_fw:
        fail(f"first-wave set mismatch: {first_wave}")

    rows = []
    for s in scenarios:
        rows.append((
            tuple(sorted(s["decision_kinds"])),
            tuple(sorted(s["architecture_reverser_axes"])),
            s["scenario_id"],
        ))
    seen = {}
    collisions = []
    for dk, ax, sid in rows:
        key = (dk, ax)
        if key in seen:
            collisions.append((sid, seen[key]))
        seen[key] = sid
    redoc = (BASE / "RQ_C1_REDUNDANCY_ADJUDICATION.md").read_text()

    def covered(sid):
        short = sid.split("-")[-1]
        return sid in redoc or short in redoc

    for a, b in collisions:
        if not (covered(a) and covered(b)):
            fail(f"incidence duplicate without adjudication cover: {a} vs {b}")
        else:
            print(f"INFO: incidence collision adjudicated (KEEP): {a} vs {b}")

    nc = json.loads((BASE / "RQ_C1_NEGATIVE_CONTROLS.json").read_text())
    all_nc = json.dumps(nc)
    if re.search(r"RQ-C1-[A-K][0-9]{2}", all_nc):
        fail("negative controls reference scenario IDs as coverage")
    if "SYNTHETIC" not in json.dumps(
        (BASE / "RQ_C1_NEGATIVE_CONTROLS.json").read_text()
    ) and True:
        pass

    manifest = json.loads((BASE / "RQ_C1_SCENARIO_MANIFEST.json").read_text())
    if manifest.get("scenario_count") != 40 or len(manifest.get("scenarios", [])) != 40:
        fail("manifest count != 40")
    mids = [s["scenario_id"] for s in manifest["scenarios"]]
    if mids != sorted(mids):
        fail("manifest not sorted")
    if sorted(mids) != sorted(ids):
        fail("manifest IDs != scenario file IDs")
    for ms, fs in zip(
        sorted(manifest["scenarios"], key=lambda d: d["scenario_id"]),
        sorted(scenarios, key=lambda d: d["scenario_id"]),
    ):
        if ms != fs:
            fail(f"manifest entry differs from file: {ms['scenario_id']}")
            break

    with open(BASE / "RQ_C1_SCENARIO_MANIFEST.csv") as fh:
        rows_csv = list(csv.reader(fh))
    if [r[0] for r in rows_csv[1:]] != sorted(ids):
        fail("manifest CSV not sorted")
    if len(rows_csv) != 41:
        fail("manifest CSV row count != 40 + header")

    with open(BASE / "RQ_C1_DECISION_SURFACE_MATRIX.csv") as fh:
        drows = list(csv.reader(fh))
    with open(BASE / "RQ_C1_RULES_AXIS_MATRIX.csv") as fh:
        arows = list(csv.reader(fh))
    if [r[0] for r in drows[1:]] != sorted(ids) or [r[0] for r in arows[1:]] != sorted(
        ids
    ):
        fail("matrix row order not sorted")

    h1 = hashlib.sha256(
        (BASE / "RQ_C1_SCENARIO_MANIFEST.json").read_bytes()
    ).hexdigest()
    subprocess.run(
        [sys.executable, str(BASE / "build_derived.py")],
        check=True,
        capture_output=True,
    )
    h2 = hashlib.sha256(
        (BASE / "RQ_C1_SCENARIO_MANIFEST.json").read_bytes()
    ).hexdigest()
    if h1 != h2:
        fail("derived artifacts not deterministic")

    if FAILURES:
        print(f"VALIDATOR FAIL ({len(FAILURES)}):")
        for m in FAILURES:
            print(f" - {m}")
        return 1
    print(f"VALIDATOR PASS: {len(scenarios)} scenarios, first-wave={len(first_wave)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
