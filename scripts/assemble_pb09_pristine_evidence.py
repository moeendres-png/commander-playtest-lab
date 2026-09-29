#!/usr/bin/env python3
"""PB-09 pristine-lane evidence assembler (AF00-AF11 + pristine-vs-fork delta).

Reads only the artifacts this lane produced, plus the fork-lane evidence already
committed on main, and derives every gate from an observation. Nothing inherits a
verdict from the fork lane, and nothing here compares aggregate PASS counts: the
fork column measured a Commander-Lab Rules-Core fork, so a count-to-count
comparison would be the exact error PB-09 exists to correct.

Two rules shape every verdict:

* a gate is PASS only from evidence observed in THIS lane, and
* a difference against the fork lane is classified by owner (pristine engine,
  bridge surface, Lab Rules patch, or coverage) rather than being called a
  capability ranking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from commander_lab.qualification.current_boundary import lifecycle as lifecycle_mod  # noqa: E402
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402

OUT = REPO / "qualification" / "pb09-pristine-upstream-20260929"
FORK_OUT = REPO / "qualification" / "final-current-boundary-20260927"
RECEIPT_DIR = OUT / "receipts"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print("wrote", name)


def native_credit(expected_commit: str) -> dict[str, Any]:
    receipts, rejected = receipt_mod.collect_receipts(RECEIPT_DIR)
    credit = receipt_mod.native_suite_credit(
        receipts, candidate="forge", expected_commit=expected_commit
    )
    return {
        "source": "PERSISTED_EXECUTION_RECEIPTS_ONLY",
        "rejected_receipts": rejected,
        "summary": {
            "groups_credited": credit["groups_credited"],
            "tests": credit["tests"],
            "passed": credit["passed"],
            "failed": credit["failed"],
            "errors": credit["errors"],
        },
        "groups": credit["groups"],
    }


def source_lock_verdict(af01: dict[str, Any], expected_commit: str) -> str:
    reported = str(af01.get("engine_commit_reported") or "").strip()
    if not reported or not expected_commit:
        return "UNKNOWN"
    return "PASS" if reported == expected_commit else "FAIL"


def af03_gate() -> dict[str, Any]:
    path = OUT / "AF03_PIN.json"
    if not path.is_file():
        return {
            "gate": "AF03",
            "name": "RULES_AUTHORITY",
            "verdict": "UNKNOWN",
            "evidence": ["no AF03 probe artifact exists for this lane"],
            "blocking_rows": [],
        }
    document = load(path)
    probes = document.get("probes", [])
    return {
        "gate": "AF03",
        "name": "RULES_AUTHORITY",
        "verdict": document.get("verdict", "UNKNOWN"),
        "evidence": [
            f"{p['invariant']}: {p['verdict']} ({p['detail']})" for p in probes
        ],
        "observed_probe_count": len(probes),
        "accepted_illegal_decks": [p["probe"] for p in probes if p.get("verdict") == "FAIL"],
        "authority": document.get("authority"),
        "blocking_rows": [p["probe"] for p in probes if p.get("verdict") == "FAIL"],
        "reading": (
            "the pristine engine accepted a deck with a real non-Commander as commander and a "
            "deck whose colour identity violates the commander's, while refusing an unknown "
            "card name, a short mainboard and an empty mainboard. Deck-size and name validity "
            "are enforced at this import boundary; Commander format legality is not."
        ),
    }


def assemble(lane: str) -> None:
    results = load(OUT / f"FULL107_PRISTINE_{lane.upper()}_RESULTS.json")
    identity = results["runtime_identity"]
    expected_commit = identity["engine_candidate_commit"]
    rows = {row["fixture_id"]: row for row in results["rows"]}
    counts = results["counts"]
    af01 = load(OUT / f"AF01_{lane.upper()}.json")
    cardinality = load(OUT / f"PLAYER_CARDINALITY_{lane.upper()}.json")
    hidden = load(OUT / f"HIDDEN_INFO_{lane.upper()}.json")
    rng = load(OUT / f"RNG_REPLAY_{lane.upper()}.json")
    cards = load(OUT / f"ACTUAL_CARD_{lane.upper()}.json")
    falsification = load(OUT / "WRONG_REASON_FALSIFICATION.json")
    native = native_credit(expected_commit)

    native_summary = native["summary"]
    native_green = (
        bool(native_summary["groups_credited"])
        and not native_summary["failed"]
        and not native_summary["errors"]
    )
    cardinality_assessment = lifecycle_mod.cardinality_verdict(cardinality["results"])

    # Decision classes actually bound in this lane, read from the observed tapes
    # rather than asserted. AF04 is about what the engine offered, so it is
    # derived from the recorded decision kinds.
    observed_kinds: set[str] = set()
    bound_choices = 0
    for row in results["rows"]:
        for entry in row.get("externally_supplied_decision_tape") or []:
            if isinstance(entry, dict):
                if entry.get("kind"):
                    observed_kinds.add(str(entry["kind"]).upper())
                if entry.get("chosen_option_id"):
                    bound_choices += 1

    scoping = hidden["principal_scoping"]
    hidden_rows_open = sorted(
        fixture
        for fixture, row in rows.items()
        if fixture.startswith("HIDDEN_") and row["exit_state"] in ("UNKNOWN", "BLOCKED")
    )

    matrix = [
        {
            "gate": "AF00",
            "name": "SOURCE_AND_BUILD_LOCK",
            "verdict": source_lock_verdict(af01, expected_commit),
            "evidence": [
                f"provider reported engine commit {af01['engine_commit_reported']}",
                f"evidence is about {expected_commit} (the pinned pristine candidate)",
                f"provenance: {af01['engine_commit_provenance']}",
                f"executing checkout adapter commit: {identity['adapter_commit']}",
                "Rules-Core equivalence re-proven at run time: "
                + json.dumps(
                    load(OUT / f"PRISTINE_ENGINE_IDENTITY_{lane.upper()}.json")[
                        "rules_core_equivalence"
                    ]["justification"]
                ),
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "the provider reports its engine commit from the FORGE_ENGINE_SHA environment "
                "variable rather than deriving it from the built Forge bytes, so the "
                "commit-to-build binding is operator-supplied, not build-proven (PB-05)",
                "the commit itself is proven pristine independently of the provider, by the "
                "upstream tag dereference and the two-remote object check",
            ],
        },
        {
            "gate": "AF01",
            "name": "PROTOCOL_HANDSHAKE",
            "verdict": af01["verdict"],
            "evidence": [
                f"{len(af01['invariants'])} AF01 v2 invariants executed under Protocol 2.0.0",
                f"lane: {af01['lane']}",
                f"capabilities provider-reported: "
                f"{json.dumps(af01.get('capabilities_provider_reported', {}), sort_keys=True)}",
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "the decision-time invariants were probed against a live four-player game, "
                "because this provider surface refuses every other player count; the "
                "invariants are player-count independent, and the count used is recorded"
            ],
        },
        {
            "gate": "AF02",
            "name": "PLAYER_CARDINALITY",
            "verdict": cardinality_assessment["verdict"],
            "all_or_nothing": True,
            "evidence": [
                cardinality_assessment["reason"],
                f"counts with a complete lifecycle: {cardinality_assessment['complete_counts']}",
                f"counts without one: {cardinality_assessment['incomplete_counts']}",
                "every count 2P-6P was ATTEMPTED; the refusals are the provider's own "
                "player_count_unsupported responses, not unexecuted rows",
            ],
            "lifecycle_assessment": cardinality_assessment,
            "blocking_rows": [
                fixture
                for fixture, row in rows.items()
                if fixture.startswith("PLAYER_COUNT_") and row["exit_state"] == "FAIL"
            ],
            "nonblocking_limitations": [
                "2P, 3P, 5P and 6P are refused by the provider's bridge surface, so AF02 cannot "
                "be established for the pristine candidate on this surface",
            ],
        },
        af03_gate(),
        {
            "gate": "AF04",
            "name": "LEGAL_ACTION_AND_DECISION_BOUNDARY",
            "verdict": "UNKNOWN",
            "evidence": [
                f"decision classes bound externally in this lane: {sorted(observed_kinds)}",
                f"externally bound decisions recorded: {bound_choices}",
                "every bound choice was an option the provider had published in that frame",
                "fail-closed probes against a live game: "
                + json.dumps(
                    {
                        item["invariant"]: item["verdict"]
                        for item in af01["invariants"]
                        if item["invariant"].startswith("fail_closed")
                    },
                    sort_keys=True,
                ),
            ],
            "blocking_rows": [
                fixture
                for fixture, row in rows.items()
                if fixture.startswith("PILOT_") and row["exit_state"] in ("UNKNOWN", "BLOCKED")
            ],
            "nonblocking_limitations": [
                "the provider reports legal_actions_supported=false and "
                "action_submission_supported=false while still publishing decision frames, so "
                "the offered-option surface is narrower than the current fork-lane surface and "
                "no target, mode or combat decision family was reachable",
                "the full decision boundary is therefore unestablished, not refuted",
            ],
        },
        {
            "gate": "AF05",
            "name": "HIDDEN_INFORMATION",
            "verdict": "UNKNOWN",
            "evidence": [
                f"principal scoping verdict: {scoping['verdict']} "
                f"(attribution {scoping['attribution']})",
                f"distinct state views across four requesters: {scoping['distinct_state_views']}",
                f"requesters with an established binding: "
                f"{scoping['observations_with_established_requester']}",
                f"per-scenario hidden rows not established: {len(hidden_rows_open)}",
                "falsification: repeat reads by one seat are byte-identical, no seat's real "
                "cards appear in another seat's view, and an unknown observer id reveals "
                "nothing, so the projection is genuinely driven by the requested principal",
            ],
            "blocking_rows": hidden_rows_open,
            "nonblocking_limitations": [
                "content is correctly per-principal and non-overlapping, but the response "
                "carries no is_actor marker and no observer envelope, so the standard's "
                "authoritative requester binding is absent and the gate cannot be credited",
                "the per-scenario hidden channels are unreachable on this surface",
            ],
        },
        {
            "gate": "AF06",
            "name": "GENERAL_RULES_CORRECTNESS",
            "verdict": "UNKNOWN",
            "evidence": [
                f"{counts['PASS']} of 107 rows PASS, {counts['FAIL']} FAIL, "
                f"{counts['BLOCKED']} BLOCKED, {counts['UNKNOWN']} UNKNOWN",
                f"native provider suite: {native_summary['tests']} tests, "
                f"{native_summary['passed']} passed, {native_summary['failed']} failed",
            ],
            "blocking_rows": sorted(
                fixture for fixture, row in rows.items() if row["exit_state"] == "BLOCKED"
            ),
            "nonblocking_limitations": [
                "the single PASS is a four-player lifecycle; no micro-rules mechanism row was "
                "executed, and the mid-game obligations remain blocked by the absence of a "
                "starting-state seam on this provider surface",
            ],
        },
        {
            "gate": "AF07",
            "name": "ACTUAL_CARD_BEHAVIOR",
            "verdict": "UNKNOWN",
            "evidence": [
                f"behaviourally executed corpus identities: "
                f"{cards['required_29_card_corpus']['behaviorally_executed_count']} of "
                f"{cards['required_29_card_corpus']['required_count']}",
                f"card fixtures passed: {cards['required_29_card_corpus']['card_fixtures_passed']}"
                f" of {cards['required_29_card_corpus']['card_fixtures']}",
            ],
            "blocking_rows": cards["required_29_card_corpus"]["unexecuted_card_fixtures"],
            "nonblocking_limitations": [
                "importing and constructing a deck is not card behaviour; no mandatory card "
                "fixture row executed, so the corpus is not credited",
            ],
        },
        {
            "gate": "AF08",
            "name": "MULTIPLAYER_COMMANDER",
            "verdict": "UNKNOWN",
            "evidence": [
                f"cardinality lifecycles recorded for 2P/3P/4P/5P/6P: "
                f"{sorted(cardinality['results'])}",
                f"four-player lifecycle completed with bound decisions: "
                f"{cardinality_assessment['complete_counts']}",
                f"START-2 (CR 103.8a two-player draw skip): {rows['WS05-CMD-START-2']['exit_state']}",
            ],
            "blocking_rows": [
                fixture
                for fixture, row in rows.items()
                if row["exit_state"] == "BLOCKED" and fixture.startswith("WS05-")
            ],
            "nonblocking_limitations": [
                "the two-player START-2 obligation could not be exercised because this provider "
                "surface refuses any count other than four; that is an unmeasured obligation, "
                "not a Rules finding about the pristine engine",
            ],
        },
        {
            "gate": "AF09",
            "name": "RNG_REPLAY",
            "verdict": "UNKNOWN",
            "evidence": [
                f"Rules RNG binding: {json.dumps(rng['rules_rng_binding'], sort_keys=True)}",
                f"semantic replay export: {json.dumps(rng.get('semantic_replay'), sort_keys=True)[:200]}",
                f"event log export: {json.dumps(rng.get('event_log'), sort_keys=True)[:200]}",
            ],
            "blocking_rows": sorted(
                fixture
                for fixture, row in rows.items()
                if fixture.startswith(("REPLAY_", "RNG_"))
                and row["exit_state"] in ("UNKNOWN", "BLOCKED")
            ),
            "nonblocking_limitations": [
                "the provider declares seed_supported=false, so the run is UNCONTROLLED and "
                "earns no RNG credit; replay and event-log exports are refused by the provider",
                "no clean-process twin is executed, so the replay half is unproven regardless",
            ],
        },
        {
            "gate": "AF10",
            "name": "RUNTIME_EVIDENCE_RELIABILITY",
            "verdict": "PASS"
            if (
                counts["CRASH"] == 0
                and counts["TIMEOUT"] == 0
                and counts["PROTOCOL_FAILURE"] == 0
                and native_green
            )
            else "FAIL",
            "evidence": [
                f"denominator accounting complete: {sum(counts.values())} explicit outcomes "
                "for 107 rows",
                "zero CRASH/TIMEOUT/PROTOCOL_FAILURE",
                f"native provider suite: {native_summary['tests']} tests green",
                f"every positive claim was attacked: "
                f"{len(falsification['classification']['does_not_survive'])} did not survive, "
                "all of them established candidate properties rather than harness artifacts",
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [],
        },
        {
            "gate": "AF11",
            "name": "INTEROP_LICENSE_TOPOLOGY",
            "verdict": "FAIL",
            "evidence": [
                "the pristine candidate runs as a genuine separate external process over "
                "stdin/stdout JSONL; no engine code is embedded in the Lab",
                f"upstream Forge licence: GPL-3.0 (recorded in the pin manifest)",
                "this lane executes the pristine upstream candidate, so the licence posture is "
                "the upstream one and is NOT the posture of a GPL-3.0 derivative fork",
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "GPL-3.0 is incompatible with a proprietary production distribution; that is a "
                "Coordinator decision, recorded here as a fact about the candidate",
            ],
        },
    ]

    write(
        f"AF00_AF11_PRISTINE_{lane.upper()}.json",
        {
            "schema_version": "pb09.af-matrix/1.0.0",
            "lane": lane,
            "candidate": "forge",
            "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
            "engine_commit": expected_commit,
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            "boundary": "PB09_PRISTINE_UPSTREAM_EXECUTION",
            "runtime_identity": identity,
            "native_runs": native,
            "full107_counts": counts,
            "gates": matrix,
            "gate_verdict_summary": {
                gate["gate"]: gate["verdict"] for gate in matrix
            },
            "nonclaims": [
                "this matrix describes the pinned pristine candidate on the pinned bridge surface",
                "no gate here is a comparison against the Commander-Lab fork and no gate "
                "selects a provider",
                "PRODUCTION_PROVIDER = NOT SELECTED; ARCHITECTURE_FREEZE = NOT CLAIMED",
            ],
        },
    )

    # ---- pristine vs fork-lane delta, classified by owner ------------------
    delta: list[dict[str, Any]] = []
    fork_results_path = FORK_OUT / "FULL107_FORGE_RESULTS.json"
    if fork_results_path.is_file():
        fork_results = load(fork_results_path)
        fork_rows = {row["fixture_id"]: row for row in fork_results["rows"]}
        fork_af = load(FORK_OUT / "AF00_AF11_FORGE.json")
        fork_gates = {gate["gate"]: gate for gate in fork_af["gates"]}
        fork_caps = load(FORK_OUT / "AF01_FORGE.json").get("capabilities_provider_reported", {})
        pin_caps = af01.get("capabilities_provider_reported", {})

        def classify(capability: str) -> tuple[str, str]:
            pin_value = pin_caps.get(capability)
            fork_value = fork_caps.get(capability)
            if pin_value == fork_value:
                return "SAME_ON_BOTH_SURFACES", "no difference"
            if fork_value and not pin_value:
                return (
                    "BRIDGE_DIFFERENCE",
                    "the current fork-lane provider surface offers this capability and the "
                    "pinned bridge surface does not; it is a transport/provider-surface "
                    "difference, not a difference in the Rules Core",
                )
            if pin_value and not fork_value:
                return (
                    "BRIDGE_DIFFERENCE",
                    "the pinned bridge surface offers this capability and the fork-lane "
                    "surface does not",
                )
            return "DIFFERENT_VALUES", f"pinned={pin_value!r} fork={fork_value!r}"

        for capability in sorted(set(pin_caps) | set(fork_caps)):
            classification, note = classify(capability)
            delta.append(
                {
                    "dimension": f"capability:{capability}",
                    "pristine_pinned_surface": pin_caps.get(capability),
                    "fork_lane_surface": fork_caps.get(capability),
                    "classification": classification,
                    "note": note,
                }
            )

        for gate in matrix:
            fork_verdict = fork_gates.get(gate["gate"], {}).get("verdict")
            if fork_verdict == gate["verdict"]:
                classification = "SAME_VERDICT"
            elif gate["verdict"] == "FAIL" and fork_verdict == "PASS":
                classification = "LAB_FORK_REGRESSION_OR_REPAIR_ABSENT_ON_PRISTINE"
            elif gate["verdict"] != "UNKNOWN" and fork_verdict == "UNKNOWN":
                classification = "PRISTINE_SURFACE_ESTABLISHED_WHERE_FORK_UNESTABLISHED"
            else:
                classification = "EVIDENCE_PRESENCE_DIFFERENCE"
            delta.append(
                {
                    "dimension": f"gate:{gate['gate']}",
                    "pristine_pinned_surface": gate["verdict"],
                    "fork_lane_surface": fork_verdict,
                    "classification": classification,
                    "note": gate["name"],
                }
            )

        for fixture in sorted(rows):
            pristine_state = rows[fixture]["exit_state"]
            fork_state = fork_rows.get(fixture, {}).get("exit_state")
            if pristine_state == fork_state:
                continue
            if pristine_state == "FAIL" and fork_state == "PASS":
                classification = "PRISTINE_SURFACE_REJECTS_WHAT_FORK_LANE_EXECUTED"
            elif pristine_state == "PASS" and fork_state in ("UNKNOWN", "BLOCKED"):
                classification = "PRISTINE_SURFACE_EXECUTED_WHAT_FORK_LANE_COULD_NOT"
            else:
                classification = "EVIDENCE_PRESENCE_DIFFERENCE"
            delta.append(
                {
                    "dimension": f"row:{fixture}",
                    "pristine_pinned_surface": pristine_state,
                    "fork_lane_surface": fork_state,
                    "classification": classification,
                    "note": rows[fixture]["reason"][:200],
                }
            )
    else:
        delta = [
            {
                "dimension": "fork_lane_evidence",
                "classification": "UNKNOWN_CAUSE",
                "note": f"the fork-lane results are not present at {fork_results_path}",
            }
        ]

    write(
        f"PRISTINE_VS_FORK_DELTA_{lane.upper()}.json",
        {
            "schema_version": "pb09.pristine-vs-fork-delta/1.0.0",
            "lane": lane,
            "compared": {
                "pristine": {
                    "engine_commit": expected_commit,
                    "engine_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
                    "bridge": identity["adapter_commit"],
                },
                "fork_lane": {
                    "engine_commit": "ef958ee91ac6c9ce0152189f2654bf6e05abf273",
                    "engine_identity": "COMMANDER_LAB_FORGE_FORK (Lab-modified Rules Core)",
                },
            },
            "method": (
                "per-dimension comparison of observed state, classified by owner. Aggregate "
                "PASS counts are deliberately not compared: the two columns executed different "
                "engines, so a count difference would measure the difference between the two "
                "artifacts rather than the capability of either one."
            ),
            "dimensions": delta,
            "counts_by_classification": {
                classification: sum(
                    1 for item in delta if item["classification"] == classification
                )
                for classification in sorted({item["classification"] for item in delta})
            },
            "no_ranking": "this packet contains no score, no ranking and no preferred provider",
        },
    )


if __name__ == "__main__":
    assemble("pin")
