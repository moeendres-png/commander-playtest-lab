"""PB-03 exact runtime-execution ledger.

This module does not decide rules conformance and never promotes FULL107 rows.
It only binds each of the 30 PB-03 fixtures to exact native JUnit methods and
records whether those methods actually passed on the current source-bound run.

A green blocker-characterization test is runtime execution, not semantic PASS.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, TypedDict

from .dimension_admission import PB03_FIXTURE_IDS

RESTORATION_PLUS_CAUSAL = "RESTORATION_PLUS_CAUSAL"
GENUINE_CAUSAL_DEVIATION = "GENUINE_CAUSAL_DEVIATION"
TEMPORAL_PROGRESSION = "TEMPORAL_PROGRESSION"


class RuntimeCase(TypedDict):
    class_name: str
    method_name: str
    route: str
    semantic_relation: str


PB03_RUNTIME_CASES: dict[str, RuntimeCase] = {
    "PILOT_DECLARE_ATTACKER": {
        "class_name": "XmagePb03RuntimeGapClosureTest",
        "method_name": "pilotDeclareAttackerUsesExactFrozenRecordAndProviderOffer",
        "route": TEMPORAL_PROGRESSION,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "PILOT_DECLARE_BLOCKER": {
        "class_name": "XmagePb03RuntimeGapClosureTest",
        "method_name": "pilotDeclareBlockerUsesExactFrozenRecordAndProviderOffer",
        "route": TEMPORAL_PROGRESSION,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "MICRO_RULES_RANDOMNESS": {
        "class_name": "XmagePb03Tier2StackTest",
        "method_name": "microRulesRandomnessStitchFlipsHeadsForExtraTurn",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "FAIL_CLOSED_DISCRETION_BLOCKER",
    },
    "WS05-MP-PRIO-3": {
        "class_name": "XmagePb03Tier2StackTest",
        "method_name": "mpPrio3RingOrderWithBoltResponse",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-PRIO-5": {
        "class_name": "XmagePb03Tier2StackTest",
        "method_name": "mpPrio5RingOrderWithBoltResponse",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-TRIG-3": {
        "class_name": "XmageFullGameTrigExecutionTest",
        "method_name": "trig3CastsBearsAndTriggersSoulWardens",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-TRIG-5": {
        "class_name": "XmageFullGameTrigExecutionTest",
        "method_name": "trig5CastsBearsAndTriggersSoulWardens",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-COMBAT-4": {
        "class_name": "XmagePb03Tier1RowsTest",
        "method_name": "mpCombat4AssignsTwoAttackersToTwoDefenders",
        "route": RESTORATION_PLUS_CAUSAL,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "WS05-MP-COMBAT-5": {
        "class_name": "XmagePb03Tier1RowsTest",
        "method_name": "mpCombat5AssignsThreeAttackersToThreeDefenders",
        "route": RESTORATION_PLUS_CAUSAL,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "WS05-MP-BLOCK-4": {
        "class_name": "XmagePb03Tier1RowsTest",
        "method_name": "mpBlock4P2BlocksOnlyItsAttacker",
        "route": RESTORATION_PLUS_CAUSAL,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "WS05-MP-TURN-3": {
        "class_name": "XmagePb03Tier2ControlTurnTest",
        "method_name": "mpTurn3ExtraTurnsRunP3ThenP2",
        "route": TEMPORAL_PROGRESSION,
        "semantic_relation": "EXACT_OBLIGATION_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-TURN-5": {
        "class_name": "XmagePb03Tier2ControlTurnTest",
        "method_name": "mpTurn5ExtraTurnsRunP3ThenP2",
        "route": TEMPORAL_PROGRESSION,
        "semantic_relation": "EXACT_OBLIGATION_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-ELIM-OWNED-3": {
        "class_name": "XmageFullGameElimExecutionTest",
        "method_name": "elimLifeZeroResetsToStartingLife3P",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "BLOCKER_CHARACTERIZATION",
    },
    "WS05-MP-ELIM-CONTROL-3": {
        "class_name": "XmageCausalEliminationReconstructionTest",
        "method_name": "eliminatedOwnersPermanentLeavesEvenWhileControlledByOpponent",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-ELIM-STACK-3": {
        "class_name": "XmageCausalEliminationReconstructionTest",
        "method_name": "departingPlayersOwnedSpellIsRemovedFromStackBeforeItCanResolve",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-ELIM-PRIO-3": {
        "class_name": "XmageCausalEliminationReconstructionTest",
        "method_name": "priorityRingExcludesEliminatedPlayerAndSurvivorContinues",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-ELIM-TURN-3": {
        "class_name": "XmageCausalEliminationReconstructionTest",
        "method_name": "activePlayerSelfLossEndsItsTurnAndNextLivePlayerBecomesActive",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_CAUSAL_RECONSTRUCTION",
    },
    "WS05-MP-ELIM-5": {
        "class_name": "XmageFullGameElimExecutionTest",
        "method_name": "elimLifeZeroResetsToStartingLife5P",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-GY-YES": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneGyYesChoosesCommandZone",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-GY-NO": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneGyNoStaysInGraveyard",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-EXILE-YES": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneExileYesChoosesCommandZone",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-EXILE-NO": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneExileNoStaysInExile",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-HAND-YES": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneHandYesChoosesCommandZone",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-HAND-NO": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneHandNoStaysInHand",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-LIB-YES": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneLibYesChoosesCommandZone",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-ZONE-LIB-NO": {
        "class_name": "XmagePb03Tier2CmdZoneTest",
        "method_name": "cmdZoneLibNoStaysInLibrary",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "COMMANDER_IDENTITY_BLOCKER_CHARACTERIZATION",
    },
    "WS05-CMD-DMG-SAME-21": {
        "class_name": "XmageCausalEliminationReconstructionTest",
        "method_name": "nineteenCommanderDamagePlusRealHastyCommanderCombatCausesLossAndCleanup",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "GENUINE_COMMANDER_COMBAT_FROM_RESTORED_19_DAMAGE",
    },
    "WS05-CMD-DMG-SPLIT": {
        "class_name": "XmageFull107ResidualRequalificationTest",
        "method_name": "exactSplitCommanderDamageRemainsPerCommanderAndDigestMatches",
        "route": RESTORATION_PLUS_CAUSAL,
        "semantic_relation": "EXACT_OBLIGATION",
    },
    "WS05-CMD-DMG-CONTROL": {
        "class_name": "XmageControlDivergenceReconstructionTest",
        "method_name": "stolenCommanderCombatDamageUsesOwnerIdentityAfterControlChange",
        "route": GENUINE_CAUSAL_DEVIATION,
        "semantic_relation": "CONTROLLED_COMMANDER_COMBAT_PRESERVES_OWNER_DAMAGE_IDENTITY",
    },
    "WS05-CMD-ELIM-4": {
        "class_name": "XmagePb03Tier1RowsTest",
        "method_name": "elim4TwentyOneCommanderDamageEliminatesAndCleansUp",
        "route": RESTORATION_PLUS_CAUSAL,
        "semantic_relation": "BLOCKER_CHARACTERIZATION",
    },
}


def _case_passed(report: Path, class_name: str, method_name: str) -> bool:
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError):
        return False
    for testcase in root.iter("testcase"):
        observed_class = str(testcase.attrib.get("classname") or "")
        observed_method = str(testcase.attrib.get("name") or "")
        if not (observed_class == class_name or observed_class.endswith("." + class_name)):
            continue
        if observed_method != method_name:
            continue
        return not any(testcase.find(tag) is not None for tag in ("failure", "error", "skipped"))
    return False


# The exact identity binding a PB-03 runtime ledger must carry before any of its
# rows may be reported as a fresh executed native receipt. The Lab runner digest
# is the post-#344 anchor: a ledger that names the engine but not the runner
# that executed the harness cannot be distinguished from one produced by a
# different harness, so it is never fresh.
PB03_RUNTIME_IDENTITY_FIELDS = (
    "runner_commit",
    "runner_tree",
    "runner_digest",
    "candidate_commit",
)

PB03_RUNTIME_FRESH = "FRESH_EXACT"
PB03_RUNTIME_STALE = "STALE"
PB03_RUNTIME_MISSING = "MISSING"
PB03_RUNTIME_INVALID = "INVALID"


def runtime_execution_freshness(
    document: dict[str, Any] | None,
    *,
    expected_runner_digest: str,
    expected_candidate_commit: str,
) -> str:
    """Classify a PB-03 runtime execution ledger against the assembling head.

    ``FRESH_EXACT`` requires the schema, a complete identity block, the exact
    executing Lab runner digest, the canonical engine candidate commit and an
    all-green execution ledger. Anything else is zero runtime credit: a
    well-formed ledger from another runner or engine epoch is ``STALE``, an
    incomplete one is ``MISSING``, and a malformed, tampered or non-all-green
    one is ``INVALID``. No classification here promotes a FULL107 row.
    """
    if not isinstance(document, dict):
        return PB03_RUNTIME_INVALID
    if document.get("schema_version") != "commander-lab.pb03-runtime-execution/2.0.0":
        return PB03_RUNTIME_INVALID
    recorded = document.get("receipt_digest")
    if not isinstance(recorded, str) or not recorded:
        return PB03_RUNTIME_MISSING
    from . import receipts as receipt_mod

    body = {key: value for key, value in document.items() if key != "receipt_digest"}
    if receipt_mod.document_digest(body) != recorded:
        return PB03_RUNTIME_INVALID
    identity = {field: document.get(field) for field in PB03_RUNTIME_IDENTITY_FIELDS}
    if not all(isinstance(value, str) and value for value in identity.values()):
        return PB03_RUNTIME_MISSING
    if not expected_runner_digest or not expected_candidate_commit:
        # The assembling head cannot name itself; nothing can be verified fresh.
        return PB03_RUNTIME_MISSING
    if (
        identity["runner_digest"] != expected_runner_digest
        or identity["candidate_commit"] != expected_candidate_commit
    ):
        return PB03_RUNTIME_STALE
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        return PB03_RUNTIME_INVALID
    if (
        document.get("classification") != "PASS"
        or document.get("executed_pass") != document.get("rows_total")
        or document.get("not_run_or_failed") != 0
    ):
        return PB03_RUNTIME_INVALID
    if any(not isinstance(row, dict) or row.get("runtime_execution") != "PASS" for row in rows):
        return PB03_RUNTIME_INVALID
    return PB03_RUNTIME_FRESH


def build_runtime_execution_matrix(surefire_dir: Path) -> dict[str, Any]:
    if set(PB03_RUNTIME_CASES) != set(PB03_FIXTURE_IDS):
        missing = sorted(set(PB03_FIXTURE_IDS) - set(PB03_RUNTIME_CASES))
        extra = sorted(set(PB03_RUNTIME_CASES) - set(PB03_FIXTURE_IDS))
        raise ValueError(f"PB-03 runtime ledger mismatch; missing={missing} extra={extra}")

    rows: list[dict[str, Any]] = []
    for fixture_id in PB03_FIXTURE_IDS:
        case = PB03_RUNTIME_CASES[fixture_id]
        report = surefire_dir / f"TEST-org.commanderlab.xmage.{case['class_name']}.xml"
        passed = _case_passed(report, case["class_name"], case["method_name"])
        rows.append(
            {
                "fixture_id": fixture_id,
                "runtime_execution": "PASS" if passed else "NOT_RUN_OR_FAILED",
                "harness_class": case["class_name"],
                "harness_method": case["method_name"],
                "test_identity": f"{case['class_name']}.{case['method_name']}",
                "route": case["route"],
                "semantic_relation": case["semantic_relation"],
                "junit_report": str(report),
                "full107_credit": "NONE_FROM_RUNTIME_EXECUTION_LEDGER",
            }
        )

    passed_count = sum(row["runtime_execution"] == "PASS" for row in rows)
    return {
        "schema_version": "commander-lab.pb03-runtime-execution/2.0.0",
        "classification": "PASS" if passed_count == len(rows) else "PARTIAL",
        "rows_total": len(rows),
        "executed_pass": passed_count,
        "not_run_or_failed": len(rows) - passed_count,
        "rows": rows,
        "credit_boundary": (
            "Runtime execution proves that the bound native harness ran. "
            "GENUINE_CAUSAL_DEVIATION and blocker-characterization rows do not "
            "become FULL107 PASS from this ledger."
        ),
    }
