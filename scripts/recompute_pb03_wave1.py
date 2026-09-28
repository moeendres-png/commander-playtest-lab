#!/usr/bin/env python3
"""PB-03 Wave-1 XMage column recomputation (Muse XHIGH).

Reads the transplanted donor column (immutable provenance, never modified)
and produces the recomputed Wave-1 column in a NEW evidence directory:

- 9 Tier-1 obligation executions -> PASS (fresh native evidence, this lane).
- 3 Tier-1 characterizations -> BLOCKED with the proven mechanism.
- 4 PB-10 demotions (LIB-YES, OWNED-3, HIDDEN_02, ELIM-4).
- 17 Tier-2 admitted rows -> BLOCKED admitted-pending-Wave-2.
- 5 Tier-3 rows -> BLOCKED with named missing dimensions.
- All other rows -> donor bytes verbatim.

Usage:
  python3 scripts/recompute_pb03_wave1.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    TIER_3_REASONS,
    XMAGE_CANDIDATE_COMMIT,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    admit_row,
    characterization_outcome,
)

DONOR_DIR = REPO_ROOT / "qualification" / "final-current-boundary-20260927"
OUT_DIR = REPO_ROOT / "qualification" / "pb03-wave1-20260928"

# Tier-1 rows whose obligation was observed in XmagePb03Tier1RowsTest.
# Method + the observed terminal facts (audited against the test source).
OBLIGATION_EXECUTIONS: dict[str, dict[str, str]] = {
    "MICRO_COMBAT": {
        "method": "microCombatBearsTradeAndBothDie",
        "observed": "P1 attacker declared at P2, P2 Bears blocks, both 2/2 in owners graveyards after damage and SBA",
    },
    "MICRO_MODES": {
        "method": "microModesDevilTokensWithoutDamageMode",
        "observed": "genuine Burn Down the House, Devil mode selected by label, 3 Devil tokens, no damage mode",
    },
    "MICRO_PREVENTION": {
        "method": "microPreventionFogPreventsTwoCombatDamage",
        "observed": "genuine Fog resolved, unblocked attack at damage step, P2 life unchanged",
    },
    "MICRO_REPLACEMENT": {
        "method": "microReplacementDoublesThreeDamageToSix",
        "observed": "Hill Giant attacks P2 unblocked, Gratuitous Violence doubles 3 to 6",
    },
    "MICRO_STATE_BASED_ACTIONS": {
        "method": "microStateBasedMemniteDiesAsZeroZero",
        "observed": "genuine Memnite cast resolves, 0/0 in owner graveyard via SBA before priority",
    },
    "MICRO_TRIGGERS": {
        "method": "microTriggersWarstormSurgeDealsTwoToP2",
        "observed": "genuine Bears cast resolves, Warstorm Surge triggers, P2 targeted, 2 damage on resolution",
    },
    "WS05-MP-BLOCK-4": {
        "method": "mpBlock4P2BlocksOnlyItsAttacker",
        "observed": "a2 declared at P2 (a3 holds per documented setup), P2 options contain only P2-attacked attacker, Runeclaw blocks a2",
    },
    "WS05-MP-COMBAT-4": {
        "method": "mpCombat4AssignsTwoAttackersToTwoDefenders",
        "observed": "single declare-attackers action assigns a0 to P2 and a1 to P3",
    },
    "WS05-MP-COMBAT-5": {
        "method": "mpCombat5AssignsThreeAttackersToThreeDefenders",
        "observed": "single declare-attackers action assigns a0 to P2, a1 to P3 and a2 to P4",
    },
    # Wave-2b Tier-2 obligation executions via L4 genuine reconstruction.
    "MICRO_COPY": {
        "method": "microCopyFlareDuplicatesBoltOnStack",
        "observed": "genuine Bolt then Flare reconstructed bottom-to-top; Flare resolution creates a Bolt copy as a distinct stack object",
    },
    "MICRO_MANA_PAYMENT": {
        "method": "microManaPaymentCounterspellPaidWithTwoBlue",
        "observed": "genuine Bolt reconstructed; genuine Counterspell cast with exactly two blue mana counters it, no damage",
    },
    "MICRO_PRIORITY": {
        "method": "microPriorityGrowthSavesBearsFromBolt",
        "observed": "genuine Bolt reconstructed; genuine Giant Growth resolves first, Bears survives, stack empties",
    },
    "MICRO_STACK": {
        "method": "microStackGrowthSavesBearsFromBolt",
        "observed": "genuine Bolt reconstructed; genuine Giant Growth resolves first, Bears survives, stack empties",
    },
    "MICRO_ZONE_CHANGES": {
        "method": "microZoneChangesBoltBecomesNewGraveyardObject",
        "observed": "genuine Bolt reconstructed and resolved; graveyard object is a new incarnation with continuous lineage",
    },
    "WS05-MP-PRIO-3": {
        "method": "mpPrio3RingOrderWithBoltResponse",
        "observed": "genuine Bolt reconstructed; priority traverses live ring order with the response persisting on stack",
    },
    "WS05-MP-PRIO-5": {
        "method": "mpPrio5RingOrderWithBoltResponse",
        "observed": "genuine Bolt reconstructed; priority traverses live ring order with the response persisting on stack",
    },
    # Wave-2c Tier-2 obligation executions.
    "MICRO_CONTROL": {
        "method": "microControlMagicTransfersBearsToP1",
        "observed": "genuine Control Magic cast and resolved; Bears owner P2 controller P1 through the real effect only",
    },
    "WS05-MP-TURN-5": {
        "method": "mpTurn5ExtraTurnsRunP3ThenP2",
        "observed": "genuine Time Warp (P2) resolved then genuine Nexus of Fate (P3) resolved; extra turns run P3 then P2",
    },
}

TIER_2_PENDING_REASON = (
    "PB-03 Wave-1 admission TIER_2: requested state needs a dimension "
    "reproducible only via a qualified genuine-causal transaction (STACK_SPELLS "
    "via real casts, CONTROL_DIVERGENCE via a real control effect, "
    "EXTRA_TURN_QUEUE via real extra-turn spells). Routed to the Wave-2 "
    "execution seam; promotion exclusively by a fixture-loading "
    "obligation-asserting native test, never by name mention. "
    "Runner fallback BLOCKED applies until that execution binds."
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False
    ).stdout.strip()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


def fresh_identity() -> dict[str, Any]:
    return {
        "runner_commit": git("rev-parse", "HEAD"),
        "runner_tree": git("rev-parse", "HEAD^{tree}"),
        "runner_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "engine_candidate_commit": XMAGE_CANDIDATE_COMMIT,
        "lab_runtime_authority": XMAGE_LAB_RUNTIME_AUTHORITY,
        "adapter": "engine-bridge/src/main/java/org/commanderlab/xmage",
        "lane": "native current-boundary runtime (PB-03 Wave-1)",
        "native_evidence": [
            "XmagePb03DimensionAdmissionTest (5 tests: seam/table mirror over all 36 rows)",
            "XmagePb03Tier1RowsTest (12 tests: 9 obligation executions + 3 characterizations)",
        ],
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    }


def recompute_row(
    donor: dict[str, Any], identity: dict[str, Any], transforms: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply Wave-1 evidence rules to one donor row. Records every change."""
    fixture = donor["fixture_id"]
    row = dict(donor)

    def note(donor_outcome: str, action: str, basis: str) -> None:
        transforms.append(
            {
                "fixture_id": fixture,
                "donor_outcome": donor_outcome,
                "new_outcome": row["exit_state"],
                "action": action,
                "basis": basis,
            }
        )

    donor_outcome = donor["exit_state"]
    if fixture in OBLIGATION_EXECUTIONS:
        info = OBLIGATION_EXECUTIONS[fixture]
        row["exit_state"] = "PASS"
        row["execution_mode"] = "NATIVE_CURRENT_BOUNDARY_RUNTIME"
        row["failure_reason"] = None
        row["reason"] = (
            "PB-03 Wave-1 positive native execution: "
            f"XmagePb03Tier1RowsTest.{info['method']} loaded the row's own "
            f"frozen record and observed as game facts: {info['observed']}."
        )
        row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
        row["native_harness_classes"] = ["XmagePb03Tier1RowsTest"]
        row["runtime_identity"] = identity
        row.setdefault("terminal_facts", {})
        row["terminal_facts"]["pb03_wave1_method"] = info["method"]
        note(donor_outcome, "PROMOTE", f"XmagePb03Tier1RowsTest.{info['method']}")
        return row

    characterization = characterization_outcome(fixture)
    if characterization is not None:
        row["exit_state"] = characterization["outcome"]
        row["execution_mode"] = "NATIVE_CURRENT_BOUNDARY_RUNTIME"
        row["failure_reason"] = characterization["reason"]
        row["reason"] = characterization["reason"]
        row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
        row["native_harness_classes"] = characterization["classes"]
        row["runtime_identity"] = identity
        note(donor_outcome, "CHARACTERIZE", ",".join(characterization["classes"]))
        return row

    tier, missing = admit_row(fixture)
    if tier == "TIER_2":
        row["exit_state"] = "BLOCKED"
        row["execution_mode"] = "NO_CURRENT_BOUNDARY_EXECUTION_SEAM"
        row["failure_reason"] = TIER_2_PENDING_REASON + f" Missing: {', '.join(missing)}."
        row["reason"] = row["failure_reason"]
        note(donor_outcome, "ADMIT_TIER_2_PENDING", f"missing={','.join(missing)}")
        return row
    if tier == "TIER_3":
        missing_text = ", ".join(missing)
        if fixture in TIER_3_REASONS:
            assert set(missing) == set(TIER_3_REASONS[fixture].split(", ")), fixture
        row["exit_state"] = "BLOCKED"
        row["execution_mode"] = "NO_CURRENT_BOUNDARY_EXECUTION_SEAM"
        row["failure_reason"] = (
            "PB-03 Wave-1 admission TIER_3: no genuine engine path for the "
            f"required starting state. Missing dimension(s): {missing_text}. "
            "Genuine loss/divergence mechanisms are qualified separately "
            "(L5/L6) but their credit is not transferred to this row."
        )
        row["reason"] = row["failure_reason"]
        note(donor_outcome, "ADMIT_TIER_3_BLOCKED", f"missing={missing_text}")
        return row
    return row


def main() -> int:
    donor = load(DONOR_DIR / "FULL107_XMAGE_RESULTS.json")
    identity = fresh_identity()
    transforms: list[dict[str, Any]] = []
    rows = [recompute_row(dict(r), identity, transforms) for r in donor["rows"]]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["exit_state"]] = counts.get(row["exit_state"], 0) + 1
    assert sum(counts.values()) == 107, counts
    assert len(rows) == 107

    write(
        "FULL107_XMAGE_RECOMPUTED.json",
        {
            "schema_version": "pb03.wave1-recomputed/1.0.0",
            "candidate": "xmage",
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            "evidence_class": "FRESH_CURRENT_BOUNDARY_RUNTIME",
            "donor_column": {
                "directory": "qualification/final-current-boundary-20260927",
                "results": "FULL107_XMAGE_RESULTS.json",
                "counts": donor["counts"],
                "note": "post-convergence input is main's re-executed column "
                "(receipt-gated assembly); donor transplant bytes preserved in history",
            },
            "runtime_identity": identity,
            "counts": counts,
            "total": len(rows),
            "rows": rows,
        },
    )
    write(
        "RECOMPUTATION_RECEIPT.json",
        {
            "schema_version": "pb03.wave1-receipt/1.0.0",
            "input_column": {
                "directory": "qualification/final-current-boundary-20260927",
                "results": "FULL107_XMAGE_RESULTS.json",
                "counts": donor["counts"],
                "runtime_identity": donor.get("runtime_identity", {}),
            },
            "runtime_identity": identity,
            "transform_count": len(transforms),
            "transforms": transforms,
            "counts": counts,
            "terminal_states": {
                "ARCHITECTURE_FREEZE": "NOT CLAIMED",
                "PRODUCTION_PROVIDER": "NOT SELECTED",
            },
        },
    )
    print(json.dumps(counts, indent=1))
    print(f"transforms: {len(transforms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
