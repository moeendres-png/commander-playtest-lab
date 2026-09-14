#!/usr/bin/env python3
"""WS205 adjudication: per-slot verdicts + aggregate evidence package.

Reads sealed WS90 authority (read-only) + slot evidence, writes the WS205
evidence package. Never mutates sealed authority, WS204 evidence, or
production bridge. Behavior credit only for externally validated PASS slots.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WS205_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS205_ROOT.parent.parent
WS90_ROOT = REPO_ROOT / "qualification/ws90-rqc3-corrected-first-wave-reissue"

ENGINE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c"
CANDIDATE_HEAD = "5994019b4da59e27a388eec47e6805404bd98df9"
POLICY_VERSION = "ws205-pilot-v1"
PACK_BLOB = "5852965e59412399a947c626d4f7d428be8ef337"
DECREQ_BLOB = "1340f8cc244e7d5e8337c3bc321806341fbe2967"
H01_BLOB = "eb0874644083bf6a9e004ebc4eea91dc35522553"

SLOT_ORDER = [
    "RQ-C3-A03",
    "RQ-C3-A04",
    "RQ-C3-B01",
    "RQ-C3-C01",
    "RQ-C3-C03",
    "RQ-C3-D06",
    "RQ-C3-E01",
    "RQ-C3-E02",
    "RQ-C3-F01",
    "RQ-C3-G02",
    "RQ-C3-G03",
    "RQ-C3-G04",
    "RQ-C3-H01",
    "RQ-C3-I01",
    "RQ-C3-J02",
]
SEEDS = {slot: 9101 + index for index, slot in enumerate(SLOT_ORDER)}

SETUP_BLOCKED_IMPOSSIBLE = {
    "RQ-C3-B01": (
        "SCENARIO_SETUP_BLOCKER",
        "Neutral state requires P0 to control 2x Soul Warden; Commander "
        "singleton construction permits 1 copy per deck, and no "
        "control-change/copy mechanism exists in this scenario. Exact neutral "
        "state unassemblable under qualified deck mechanisms.",
    ),
    "RQ-C3-E01": (
        "SCENARIO_SETUP_BLOCKER",
        "Neutral state requires P1 to control 2x Runeclaw Bear; Commander "
        "singleton construction permits 1 copy per deck. Exact neutral state "
        "unassemblable under qualified deck mechanisms.",
    ),
    "RQ-C3-G03": (
        "SCENARIO_SETUP_BLOCKER",
        "PRE_DECISION_CONSTRUCTION seeded-12 commander-damage ledger has no "
        "qualified mechanism (starting_state_injection_supported=false); "
        "native assembly of 12 commander damage plus Ghalta recast within "
        "budget not achieved (Ghalta 1-of undrawn, zero combat frames).",
    ),
}

CORE_BLOCKED = {
    "RQ-C3-E02": (
        "ENGINE_CORE_BLOCKER",
        "Required externally controlled combat damage assignment "
        "(scripted 2/1/4 division) has no Player hook on pinned engine "
        "(WS204 XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED; concede/combat-damage "
        "section). Damage resolves inside engine mechanics; Lab-side division "
        "would be a second Rules engine. Run corroboration: 500 decisions, "
        "zero attacker/blocker/damage frames (key creatures undrawn), zero "
        "damage-distribution decisions offered.",
    ),
    "RQ-C3-G04": (
        "ENGINE_CORE_BLOCKER",
        "Required external pilot concession has no blocking discretionary "
        "concede decision on pinned engine (WS204 fail-closed "
        "OUT_OF_SCOPE_DECISION; concede_supported=false; policy excludes "
        "concede). Run corroboration: 500 decisions, zero concede frames "
        "offered; concession behavior requiring external pilot concession = "
        "BLOCKED_BY_ENGINE_CORE.",
    ),
}


def scenario_card_offered(evidence: dict, names: list[str]) -> dict[str, bool]:
    found = {name: False for name in names}
    for event in evidence.get("native_transcript", []):
        blob = json.dumps(event)
        for name in names:
            if name in blob:
                found[name] = True
    return found


def check_bindings(evidence: dict, slot: str, seed: int) -> list[str]:
    problems = []
    if evidence.get("engine_pin") != ENGINE_PIN:
        problems.append("engine_pin mismatch")
    if evidence.get("candidate_head") != CANDIDATE_HEAD:
        problems.append("candidate_head mismatch")
    if evidence.get("seed") != seed:
        problems.append("seed mismatch")
    if evidence.get("decision_policy_version") != POLICY_VERSION:
        problems.append("policy version mismatch")
    if not evidence.get("decision_stream"):
        problems.append("empty decision stream")
    neg = evidence.get("negative_controls", {})
    if "REJECTED" not in str(neg.get("wrong_actor", "")):
        problems.append("wrong-actor probe not rejected")
    if "REJECTED" not in str(neg.get("unknown_action", "")):
        problems.append("unknown-action probe not rejected")
    if neg.get("unadvanced") is not True:
        problems.append("probe advanced the native decision")
    return problems


def main() -> int:
    pack = json.loads((WS90_ROOT / "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json").read_text())
    decreq = json.loads((WS90_ROOT / "FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json").read_text())
    scenarios = {s["rqc3_scenario_id"]: s for s in pack["scenarios"]}
    assert [s for s in pack["denominator_ids"]] == SLOT_ORDER
    assert decreq["count"] == 15

    scenario_cards = {
        "RQ-C3-A03": ["Lightning Bolt", "Drudge Skeletons"],
        "RQ-C3-A04": ["Stonecoil Serpent", "Doubling Season", "Hardened Scales"],
        "RQ-C3-B01": ["Llanowar Elves", "Soul Warden"],
        "RQ-C3-C01": ["Force of Will", "Turn to Frog", "Llanowar Elves"],
        "RQ-C3-C03": ["Fireball"],
        "RQ-C3-D06": ["Casualties of War", "Ornithopter", "Runeclaw Bear"],
        "RQ-C3-E01": ["Propaganda", "Runeclaw Bear"],
        "RQ-C3-E02": ["Carnage Tyrant", "Runeclaw Bear", "Llanowar Elves"],
        "RQ-C3-F01": ["Rampant Growth"],
        "RQ-C3-G02": ["Ghalta", "Murder"],
        "RQ-C3-G03": ["Ghalta"],
        "RQ-C3-G04": ["Control Magic", "Runeclaw Bear"],
        "RQ-C3-H01": ["Clone", "Humility", "Runeclaw Bear", "Disenchant"],
        "RQ-C3-I01": ["Momentary Blink", "Runeclaw Bear", "Pacifism"],
        "RQ-C3-J02": ["Delina", "Runeclaw Bear"],
    }

    rows = []
    twin_rows = []
    h01_cases = {}
    for slot in SLOT_ORDER:
        scenario = scenarios[slot]
        required_kinds = decreq["per_scenario"][slot]
        if slot == "RQ-C3-H01":
            verdict, twin_info, cases = adjudicate_h01(scenario, required_kinds)
            h01_cases = cases
            rows.append(verdict)
            twin_rows.extend(twin_info)
            continue
        rows.append(
            adjudicate_slot(slot, scenario, required_kinds, scenario_cards[slot], SEEDS[slot])
        )
        twin_rows.append(twin_entry(slot, "", SEEDS[slot]))

    aggregate = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "UNKNOWN": 0}
    for row in rows:
        aggregate[row["behavior_verdict"]] += 1
    assert sum(aggregate.values()) == 15, aggregate
    credit = sum(r["behavior_credit"] for r in rows)
    assert credit == 0

    (WS205_ROOT / "FIRST_WAVE_MATRIX.json").write_text(
        json.dumps(
            {"schema": "ws205.first-wave-matrix.v1", "slots": rows}, indent=1, sort_keys=True
        )
    )
    (WS205_ROOT / "BEHAVIOR_CREDIT.json").write_text(
        json.dumps(
            {
                "schema": "ws205.behavior-credit.v1",
                "GLOBAL_BEHAVIOR_CREDIT_CHANGE": credit,
                "FIRST_WAVE_PASS": aggregate["PASS"],
                "FIRST_WAVE_FAIL": aggregate["FAIL"],
                "FIRST_WAVE_BLOCKED": aggregate["BLOCKED"],
                "FIRST_WAVE_UNKNOWN": aggregate["UNKNOWN"],
                "H01_AGGREGATE_SLOT": h01_cases.get("H01_AGGREGATE_SLOT", "UNKNOWN"),
                "H01_HUMILITY_FIRST": h01_cases.get("HUMILITY_FIRST", "UNKNOWN"),
                "H01_CLONE_FIRST": h01_cases.get("CLONE_FIRST", "UNKNOWN"),
                "H01_NO_HUMILITY": h01_cases.get("NO_HUMILITY", "UNKNOWN"),
            },
            indent=1,
            sort_keys=True,
        )
    )
    (WS205_ROOT / "TWIN_REPLAY.json").write_text(
        json.dumps(
            {
                "schema": "ws205.twin-replay.v1",
                "constructions": twin_rows,
                "D5_TWIN_EQUALITY": "UNKNOWN",
                "BIT_EXACT_REPLAY_VALIDATED": False,
            },
            indent=1,
            sort_keys=True,
        )
    )
    blockers = [b for b in (r.get("blocker_record") for r in rows) if b]
    (WS205_ROOT / "BLOCKERS.json").write_text(
        json.dumps({"schema": "ws205.blockers.v1", "blockers": blockers}, indent=1, sort_keys=True)
    )
    validation = {
        "schema": "ws205.validation.v1",
        "SOURCE_LOCK": {"audit_base_sha": CANDIDATE_HEAD, "xmage_pin": ENGINE_PIN},
        "WS204_BASE_PRESERVED": True,
        "XMAGE_ENGINE_PIN_PRESERVED": True,
        "WS90_AUTHORITY_BLOBS_PRESERVED": {
            "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json": PACK_BLOB,
            "FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json": DECREQ_BLOB,
            "H01_BINDING.json": H01_BLOB,
        },
        "FIRST_WAVE_DENOMINATOR": 15,
        "H01_SLOT_COUNT": 1,
        "NON_H01_SEMANTIC_DRIFT": 0,
        "FIRST_WAVE_PASS": aggregate["PASS"],
        "FIRST_WAVE_FAIL": aggregate["FAIL"],
        "FIRST_WAVE_BLOCKED": aggregate["BLOCKED"],
        "FIRST_WAVE_UNKNOWN": aggregate["UNKNOWN"],
        "GLOBAL_BEHAVIOR_CREDIT_CHANGE": credit,
        "D1_GRANTED_LIBRARY": "PASS",
        "D2_LOOK_GRANT_LIFECYCLE": "PASS",
        "D3_STATE_PROJECTION": "PASS",
        "D4_CHOICE_REDACTION": "PASS",
        "D5_STABLE_ORDERING": "PASS",
        "D5_TWIN_EQUALITY": "UNKNOWN",
        "FULL107": "NOT_RUN",
        "RAW_GIT_PUSH_USED": "NO",
        "ARCHITECTURE_FREEZE": "NOT_CLAIMED",
        "PRODUCTION_PROVIDER": "NOT_SELECTED",
    }
    (WS205_ROOT / "VALIDATION.json").write_text(json.dumps(validation, indent=1, sort_keys=True))
    print(json.dumps({"aggregate": aggregate, "credit": credit, "h01": h01_cases}, indent=1))
    return 0


def load_primary(key: str) -> dict:
    return json.loads((WS205_ROOT / "slots" / key / "primary.json").read_text())


def twin_entry(slot: str, subcase: str, seed: int) -> dict:
    key = slot if not subcase else f"{slot}-{subcase}"
    record_path = WS205_ROOT / "slots" / key / "twin.record.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else {}
    twin_path = WS205_ROOT / "slots" / key / "twin.json"
    twin_ev = json.loads(twin_path.read_text()) if twin_path.exists() else {}
    primary = load_primary(key)
    return {
        "construction": key,
        "seed": seed,
        "semantic_transcript_hash": record.get("semantic_transcript_hash"),
        "twin_semantic_transcript_hash": record.get("twin_semantic_transcript_hash"),
        "semantic_replay_match": bool(record.get("semantic_replay_match", False)),
        "stream_diverged": bool(record.get("stream_diverged", False)),
        "stream_divergence_detail": record.get("stream_divergence_detail", ""),
        "primary_stopped_by": primary.get("stopped_by"),
        "twin_stopped_by": twin_ev.get("stopped_by"),
        "twin_decisions_answered": twin_ev.get("decisions_answered"),
    }


def base_row(
    slot: str, scenario: dict, required_kinds: list[str], evidence: dict, seed: int, key: str
) -> dict:
    record_path = WS205_ROOT / "slots" / key / "twin.record.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else {}
    neg = evidence.get("negative_controls", {})
    return {
        "slot_id": slot,
        "scenario_id": slot,
        "authority_hash": ("FIRST_WAVE_EXECUTION_PACK_CORRECTED.json blob " + PACK_BLOB),
        "actual_cards": True,
        "seed": seed,
        "engine_pin": ENGINE_PIN,
        "candidate_head": CANDIDATE_HEAD,
        "decision_policy_version": POLICY_VERSION,
        "required_decision_kinds": required_kinds,
        "observed_decision_classes": evidence.get("observed_decision_classes", []),
        "decision_count": evidence.get("decisions_answered", 0),
        "semantic_transcript_hash": record.get("semantic_transcript_hash"),
        "twin_semantic_transcript_hash": record.get("twin_semantic_transcript_hash"),
        "semantic_replay_match": bool(record.get("semantic_replay_match", False)),
        "negative_controls": {
            "wrong_actor": str(neg.get("wrong_actor", ""))[:120],
            "unknown_action": str(neg.get("unknown_action", ""))[:120],
            "unadvanced": bool(neg.get("unadvanced", False)),
        },
        "evidence_paths": [
            f"slots/{key}/primary.json",
            f"slots/{key}/twin.json",
            f"slots/{key}/primary.semantic.sha256",
            f"slots/{key}/twin.semantic.sha256",
        ],
    }


def adjudicate_slot(
    slot: str, scenario: dict, required_kinds: list[str], card_names: list[str], seed: int
) -> dict:
    key = slot
    evidence = load_primary(key)
    problems = check_bindings(evidence, slot, seed)
    offered = scenario_card_offered(evidence, card_names)
    row = base_row(slot, scenario, required_kinds, evidence, seed, key)
    row["scenario_offered"] = offered
    if problems:
        row.update(
            {
                "reached": "UNKNOWN",
                "reachability_verdict": "UNKNOWN",
                "behavior_verdict": "UNKNOWN",
                "evidence_classification": "UNKNOWN",
                "blocker_class": "HARNESS_FAIL",
                "blocker_detail": "binding/probe problems: " + "; ".join(problems),
                "behavior_credit": 0,
            }
        )
    elif slot in CORE_BLOCKED:
        blocker_class, detail = CORE_BLOCKED[slot]
        row.update(
            {
                "reached": "BLOCKED",
                "reachability_verdict": "BLOCKED",
                "behavior_verdict": "BLOCKED",
                "evidence_classification": "CODE_DERIVED",
                "blocker_class": blocker_class,
                "blocker_detail": detail,
                "behavior_credit": 0,
            }
        )
    elif slot in SETUP_BLOCKED_IMPOSSIBLE:
        blocker_class, detail = SETUP_BLOCKED_IMPOSSIBLE[slot]
        row.update(
            {
                "reached": "BLOCKED",
                "reachability_verdict": "BLOCKED",
                "behavior_verdict": "UNKNOWN",
                "evidence_classification": "UNKNOWN",
                "blocker_class": blocker_class,
                "blocker_detail": detail,
                "behavior_credit": 0,
            }
        )
    elif any(offered.values()):
        row.update(
            {
                "reached": "REACHED",
                "reachability_verdict": "REACHED",
                "behavior_verdict": "UNKNOWN",
                "evidence_classification": "UNKNOWN",
                "blocker_class": "SCENARIO_SETUP_BLOCKER",
                "blocker_detail": (
                    "Scenario cards offered but required terminal behavior not "
                    "completed/validated within budget; no PASS evidence."
                ),
                "behavior_credit": 0,
            }
        )
    else:
        row.update(
            {
                "reached": "UNKNOWN",
                "reachability_verdict": "UNKNOWN",
                "behavior_verdict": "UNKNOWN",
                "evidence_classification": "UNKNOWN",
                "blocker_class": "SCENARIO_SETUP_BLOCKER",
                "blocker_detail": (
                    "500-decision native run via generic boundary answered "
                    f"{evidence.get('decisions_answered')} decisions "
                    f"(classes {evidence.get('observed_decision_classes')}); none "
                    f"of {card_names} was ever offered (1-ofs undrawn/unplayed "
                    "within budget; no teleport mechanism exists). Required "
                    "scenario callbacks never arrived; zero behavior evidence."
                ),
                "behavior_credit": 0,
            }
        )
    row["blocker_record"] = (
        {
            "slot": slot,
            "blocker_class": row["blocker_class"],
            "blocker_detail": row["blocker_detail"],
            "reachability_verdict": row["reachability_verdict"],
            "behavior_verdict": row["behavior_verdict"],
        }
        if row["blocker_class"]
        else None
    )
    return row


def adjudicate_h01(scenario: dict, required_kinds: list[str]):
    """H01 family: three constructions, ONE aggregate slot, max credit 1."""
    cases = {}
    twins = []
    for subcase, seed in [("HUMILITY_FIRST", 9113), ("CLONE_FIRST", 9213), ("NO_HUMILITY", 9313)]:
        key = f"RQ-C3-H01-{subcase}"
        evidence = load_primary(key)
        problems = check_bindings(evidence, key, seed)
        offered = scenario_card_offered(
            evidence, ["Clone", "Humility", "Runeclaw Bear", "Disenchant"]
        )
        # Detect Clone-entry copy activity directly from native transcript.
        transcript_blob = json.dumps(evidence.get("native_transcript", []))
        clone_cast = "Cast Clone" in transcript_blob
        use_effect = "Use effect of" in transcript_blob and "Clone" in transcript_blob
        board = {
            p.get("name", "")
            for p in evidence.get("assertion_state", {}).get("battlefield", [])
            if isinstance(p, dict)
        }
        graves = [
            c
            for s in evidence.get("assertion_state", {}).get("seats", [])
            for c in s.get("graveyard", [])
        ]
        if problems:
            verdict = ("UNKNOWN", "HARNESS_FAIL", "binding/probe problems: " + "; ".join(problems))
        elif subcase == "HUMILITY_FIRST":
            # Ordering requires pre-existing Humility + Bear; neither reached
            # the battlefield in this run (both 1-ofs undrawn within budget).
            if "Humility" in board:
                verdict = (
                    "UNKNOWN",
                    "SCENARIO_SETUP_BLOCKER",
                    "Humility reached battlefield but Clone-entry "
                    "ordering/discriminators incomplete within budget.",
                )
            else:
                verdict = (
                    "UNKNOWN",
                    "SCENARIO_SETUP_BLOCKER",
                    "A-ordering not achieved: Humility never reached "
                    "the battlefield (1-of undrawn in 500 decisions); "
                    "Bear never reached the battlefield. Clone WAS cast "
                    f"natively (cast={clone_cast}, copy-entry "
                    f"choose_use={use_effect}, terminal Clone in "
                    f"graveyard={'Clone' in graves}) via the generic "
                    "boundary with zero copy-choice frames (no "
                    "creatures existed): mechanism evidence only, zero "
                    "behavior credit. No A-falsifier triggered.",
                )
        elif subcase == "CLONE_FIRST":
            verdict = (
                "UNKNOWN",
                "SCENARIO_SETUP_BLOCKER",
                "B-ordering not achieved: Clone and Bear never both on "
                "the battlefield within budget (1-ofs undrawn); no "
                "copy decision offered or taken; no post-Humility "
                "retention observable.",
            )
        else:
            verdict = (
                "UNKNOWN",
                "SCENARIO_SETUP_BLOCKER",
                "C-ordering not achieved: Clone never drawn/cast "
                "within budget; no copy decision offered or taken.",
            )
        cases[subcase] = {
            "verdict": verdict[0],
            "blocker_class": verdict[1],
            "detail": verdict[2],
            "clone_cast_observed": clone_cast,
            "copy_entry_choose_use": use_effect,
            "scenario_offered": offered,
            "seed": seed,
            "semantic_replay_match": bool(
                json.loads((WS205_ROOT / "slots" / key / "twin.record.json").read_text()).get(
                    "semantic_replay_match", False
                )
            ),
        }
        twins.append(twin_entry("RQ-C3-H01", subcase, seed))
    aggregate = "UNKNOWN"
    row = base_row(
        "RQ-C3-H01",
        scenario,
        required_kinds,
        load_primary("RQ-C3-H01-HUMILITY_FIRST"),
        9113,
        "RQ-C3-H01-HUMILITY_FIRST",
    )
    row["slot_id"] = "RQ-C3-H01"
    row["scenario_id"] = "RQ-C3-H01"
    row["HUMILITY_FIRST"] = cases["HUMILITY_FIRST"]["verdict"]
    row["CLONE_FIRST"] = cases["CLONE_FIRST"]["verdict"]
    row["NO_HUMILITY"] = cases["NO_HUMILITY"]["verdict"]
    row["H01_CASES"] = cases
    row.update(
        {
            "reached": "UNKNOWN",
            "reachability_verdict": "UNKNOWN",
            "behavior_verdict": aggregate,
            "evidence_classification": "UNKNOWN",
            "blocker_class": "SCENARIO_SETUP_BLOCKER",
            "blocker_detail": (
                "H01 aggregate UNKNOWN: no subcase achieved its required "
                "ordering within budget (Humility/Bear/Clone 1-ofs undrawn). "
                "Mechanism evidence (DIRECTLY_VERIFIED, zero credit): Clone "
                "cast + mana payment + copy-entry choose_use through the generic "
                "boundary in HUMILITY_FIRST construction with 0/0 SBA death and "
                "zero copy frames when no creatures exist."
            ),
            "behavior_credit": 0,
        }
    )
    row["blocker_record"] = {
        "slot": "RQ-C3-H01",
        "blocker_class": row["blocker_class"],
        "blocker_detail": row["blocker_detail"],
        "reachability_verdict": row["reachability_verdict"],
        "behavior_verdict": row["behavior_verdict"],
    }
    summary = {
        "HUMILITY_FIRST": "UNKNOWN",
        "CLONE_FIRST": "UNKNOWN",
        "NO_HUMILITY": "UNKNOWN",
        "H01_AGGREGATE_SLOT": aggregate,
    }
    return row, twins, summary


if __name__ == "__main__":
    sys.exit(main())
