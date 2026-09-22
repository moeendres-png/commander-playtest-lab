#!/usr/bin/env python3
"""FULL107 denominator mapping generator (Phase B, reproducible).

Reads the exact frozen WS47 v1.0.5 materialization + 107-record provider
denominator (imported byte-identical under qualification/ws47/) and maps
each denominator fixture to current-lineage evidence WITHOUT awarding
behavioral PASS/FAIL (Phase C executes and classifies).

Mapping statuses:
  DIRECT            sealed run executes a fixture-corresponding scenario
                    (exact count/fixture correspondence, pointer + SHA).
  SUPPORTING        related component/lane evidence, not a fixture rerun.
  UNKNOWN           no corresponding evidence; residual stated.
  NOT_RUN_BLOCKED   entry mode unsupported by current bridge capability.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NS = REPO_ROOT / "qualification/ws47"


def gate_evidence(player_count: int) -> dict:
    path = (
        REPO_ROOT
        / "docs/workstream_successor_integration_20260919/gate-evidence"
        / f"gate-{player_count}p.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS", path
    assert payload["player_count"] == player_count, path
    return payload


GATE_CLASSES: dict[int, list[str]] = {}
for _n in (2, 3, 4, 5):
    GATE_CLASSES[_n] = gate_evidence(_n)["observed_decision_classes"]

PILOT_FAMILY_OBSERVED = set().union(*GATE_CLASSES.values())
print("live-observed decision classes:", sorted(PILOT_FAMILY_OBSERVED))

PILOT_FAMILY_TO_OBSERVED = {
    "PILOT_PRIORITY": "priority",
    "PILOT_TARGET": "target",
    "PILOT_CHOOSE_OBJECT": "choose_object",
    "PILOT_TARGET_AMOUNT": "target",
    "PILOT_MULLIGAN": "mulligan",
    "PILOT_CHOOSE_USE": "choose_use",
    "PILOT_CHOICE": None,
    "PILOT_PILE": None,
    "PILOT_MANA_PAYMENT": "mana_payment",
    "PILOT_ANNOUNCE_X": None,
    "PILOT_MULTI_AMOUNT": None,
    "PILOT_REPLACEMENT_EFFECT": None,
    "PILOT_TRIGGER_ORDER": None,
    "PILOT_CHOOSE_MODE": None,
    "PILOT_CHOOSE_ABILITY": None,
    "PILOT_DECLARE_ATTACKER": "declare_attacker",
    "PILOT_DECLARE_BLOCKER": "declare_blocker",
}


def map_fixture(fixture_id: str, record: dict) -> dict:
    entry = record.get("execution_entry_mode", "?")
    if fixture_id.startswith("PLAYER_COUNT_"):
        count = int(fixture_id.rsplit("_", 1)[1].rstrip("P"))
        return {
            "status": "SUPPORTING",
            "pointer": (
                f"docs/workstream_successor_integration_20260919/gate-evidence/gate-{count}p.json"
            ),
            "reason": (
                f"per-count live lane evidence at matching count {count}P "
                f"(status PASS, replay MATCH); not a fixture rerun: gates run "
                f"technical Isamaru+Plains decks at cardinality seeds, not the "
                f"bound Rograkh+Mountain fixture at seed 424242, and assert none "
                f"of the required events; residual: exact keep-hand runs"
            ),
        }
    if fixture_id in PILOT_FAMILY_TO_OBSERVED:
        observed = PILOT_FAMILY_TO_OBSERVED[fixture_id]
        if observed in PILOT_FAMILY_OBSERVED:
            return {
                "status": "SUPPORTING",
                "pointer": (
                    "engine-bridge/src/test/java/org/commanderlab/xmage/"
                    "XmageFullGameActionProjectionTest.java"
                ),
                "reason": (
                    f"projection unit coverage + live-observed class "
                    f"'{observed}' in 2/3/4/5P gates; not a fixture rerun"
                ),
            }
        return {
            "status": "UNKNOWN",
            "reason": (
                "decision family not observed in sealed live gates and no "
                "live fixture rerun exists; residual: family live campaign"
            ),
        }
    if fixture_id == "NEGATIVE_SILENT":
        return {
            "status": "SUPPORTING",
            "pointer": (
                "engine-bridge/src/test/java/org/commanderlab/xmage/"
                "XmageFullGameNextActionsProjectionTest.java"
            ),
            "reason": (
                "explicit projection-failure signaling regression + "
                "wrong-actor/unknown-option submission negatives; "
                "not a fixture rerun"
            ),
        }
    if fixture_id.startswith("NEGATIVE_"):
        return {
            "status": "UNKNOWN",
            "reason": (
                "fallback-prohibition behavior has no dedicated live "
                "fixture rerun; residual: negative-behavior campaign"
            ),
        }
    if fixture_id.startswith("HIDDEN_"):
        return {
            "status": "UNKNOWN",
            "reason": (
                "no per-scenario hidden-information rerun; supporting only: "
                "HIDDEN_INFORMATION_BOUNDARY_REPORT + "
                "XmageFullGameHiddenInformationTest"
            ),
        }
    if fixture_id.startswith(("RNG_", "REPLAY_")):
        return {
            "status": "UNKNOWN",
            "reason": (
                "no N-scoped replay-match rerun for this fixture; supporting "
                "only: replay unit suites + per-count replay MATCH in "
                "sealed gates (other scope)"
            ),
        }
    if fixture_id.startswith("MICRO_"):
        return {
            "status": "UNKNOWN",
            "reason": (
                "no per-fixture mechanism rerun (WS232-consistent); "
                "supporting only: per-count lane gates"
            ),
        }
    if fixture_id in ("WS05-CMD-MULL-2", "WS05-CMD-MULL-4"):
        return {
            "status": "DIRECT",
            "pointer": (
                "engine-bridge/src/test/java/org/commanderlab/xmage/"
                "XmageFullGameWs05MulliganTest.java"
            ),
            "reason": (
                "fixture-faithful live run PASS locally and on CI "
                "(PR #213 h4-xmage): exact Rograkh/Mountain decks, "
                "scripted mulligan_once, bottom counts verified "
                "(2P lib 93/hand 6, 4P lib 92/hand 7); digest equality "
                "verified (requested_state_digest) locally and on CI"
            ),
        }
    if fixture_id in ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4"):
        return {
            "status": "DIRECT",
            "pointer": (
                "engine-bridge/src/test/java/org/commanderlab/xmage/"
                "XmageFullGameTaxExecutionTest.java"
            ),
            "reason": (
                "fixture-faithful live run PASS locally and on CI "
                "(PR #220 conformance): restored requested state with "
                "readback MATCH, scripted cast_commander P1 exact-one "
                "match, engine-owned {4} tax payment, required events "
                "and terminal postconditions verified; digest equality "
                "verified (requested_state_digest) locally and on CI"
            ),
        }
    if fixture_id in ("WS05-CMD-PARTNER-ZONE", "WS05-CMD-PARTNER-TAX"):
        return {
            "status": "DIRECT",
            "pointer": (
                "engine-bridge/src/test/java/org/commanderlab/xmage/"
                "XmageFullGamePartnerExecutionTest.java"
            ),
            "reason": (
                "fixture-faithful live run PASS locally and on CI "
                "(PR #224 conformance): exact two-commander construction "
                "with readback MATCH (Partner legality engine-proven at "
                "import), histories restored, per-commander tax figures "
                "through the engine cost pipeline, required events and "
                "terminal postconditions verified; digest equality "
                "verified (requested_state_digest) locally and on CI"
            ),
        }
    if entry == "NATIVE_STATE_LOAD":
        return {
            "status": "NOT_RUN_BLOCKED",
            "reason": (
                "bridge reports starting_state_injection_supported=false "
                "(contract-locked); residual: injection-capability workstream"
            ),
        }
    if fixture_id.startswith("WS05_"):
        return {
            "status": "UNKNOWN",
            "reason": (
                "no WS05 scenario runner on current lineage; residual: WS05 execution campaign"
            ),
        }
    return {"status": "UNKNOWN", "reason": "unclassified family; residual: triage"}


def main() -> int:
    mat = json.loads((NS / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json").read_text())
    den = json.loads((NS / "WS47_PROVIDER_DENOMINATOR_107.json").read_text())
    assert mat["record_count"] == 135 and len(mat["records"]) == 135
    assert den["provider_denominator_count"] == 107
    assert len(den["fixture_ids"]) == 107
    records = {r["fixture_id"]: r for r in mat["records"]}
    entries = []
    for fid in den["fixture_ids"]:
        assert fid in records, f"denominator fixture missing from materialization: {fid}"
        entries.append({"fixture_id": fid, **map_fixture(fid, records[fid])})
    out = {
        "schema_version": "full107-denominator-mapping-1.0.0",
        "frozen_source": "origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46",
        "materialization": "commander-lab.semantic-fixture-materialization/1.0.5",
        "mapping_rule": (
            "DIRECT requires a sealed fixture-corresponding run; mapping "
            "awards no PASS/FAIL (Phase C executes and classifies)"
        ),
        "counts": {},
        "entries": entries,
    }
    from collections import Counter

    out["counts"] = dict(Counter(e["status"] for e in entries))
    dest = REPO_ROOT / "docs/workstream_full107_definition_20260921/FULL107_MAPPING.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print("mapping counts:", out["counts"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
