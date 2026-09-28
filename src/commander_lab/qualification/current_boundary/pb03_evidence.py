"""PB-03 Wave-1 evidence rules (Muse XHIGH).

A row is promoted to PASS only by a fixture-loading, obligation-asserting
native execution bound explicitly below. Name mention in a test source
promotes nothing (that regex defect is retired). Rows whose native harness
proves unexecutability are bound as characterizations and stay BLOCKED (or
UNKNOWN) with the proven mechanism named — a characterization never promotes.
"""

from __future__ import annotations

from typing import Any

# fixture_id -> native classes with obligation-executing tests for that row.
# Audited method-by-method: each class must load the fixture record and assert
# its required events / terminal postconditions as game facts.
POSITIVE_NATIVE_BINDING_XMAGE: dict[str, list[str]] = {
    "CARD_02": ["XmageFullGameCard02ExecutionTest"],
    "MICRO_LAYERS": ["XmageFullGameMicroExecutionTest"],
    "MICRO_TARGETS": ["XmageFullGameMicroExecutionTest"],
    "NEGATIVE_FIRST_OPTION": ["XmageFullGameDecisionExecutionTest"],
    "PILOT_CHOOSE_MODE": ["XmageFullGameDecisionExecutionTest"],
    "PILOT_DECLARE_ATTACKER": ["XmageTemporalProgressionDriverTest"],
    "PILOT_DECLARE_BLOCKER": ["XmageTemporalProgressionDriverTest"],
    "WS05-CMD-DMG-CONTROL": ["XmageCommanderDamageRestorationTest"],
    "WS05-CMD-DMG-SAME-21": ["XmageCommanderDamageRestorationTest"],
    "WS05-CMD-DMG-SPLIT": [
        "XmageFull107ResidualRequalificationTest",
        "XmageCommanderDamageRestorationTest",
    ],
    "WS05-CMD-MULL-2": ["XmageFullGameWs05MulliganTest"],
    "WS05-CMD-MULL-4": ["XmageFullGameWs05MulliganTest"],
    "WS05-CMD-PARTNER-DMG": [
        "XmageFull107ResidualRequalificationTest",
        "XmageCommanderDamageRestorationTest",
    ],
    "WS05-CMD-PARTNER-TAX": ["XmageFullGamePartnerExecutionTest"],
    "WS05-CMD-PARTNER-ZONE": ["XmageFullGamePartnerExecutionTest"],
    "WS05-CMD-START-3": ["XmageFull107ResidualRequalificationTest"],
    "WS05-CMD-TAX-2": ["XmageFullGameTaxExecutionTest"],
    "WS05-CMD-TAX-4": ["XmageFullGameTaxExecutionTest"],
    "WS05-MP-TRIG-3": ["XmageFullGameTrigExecutionTest"],
    "WS05-MP-TRIG-5": ["XmageFullGameTrigExecutionTest"],
    "WS05-MP-TURN-3": ["XmageTemporalProgressionDriverTest"],
    # Wave-1 Tier-1 obligation executions (each method loads its own record
    # and asserts its own required events / postconditions as game facts).
    "MICRO_COMBAT": ["XmagePb03Tier1RowsTest"],
    "MICRO_MODES": ["XmagePb03Tier1RowsTest"],
    "MICRO_PREVENTION": ["XmagePb03Tier1RowsTest"],
    "MICRO_REPLACEMENT": ["XmagePb03Tier1RowsTest"],
    "MICRO_STATE_BASED_ACTIONS": ["XmagePb03Tier1RowsTest"],
    "MICRO_TRIGGERS": ["XmagePb03Tier1RowsTest"],
    "WS05-MP-BLOCK-4": ["XmagePb03Tier1RowsTest"],
    "WS05-MP-COMBAT-4": ["XmagePb03Tier1RowsTest"],
    "WS05-MP-COMBAT-5": ["XmagePb03Tier1RowsTest"],
}

# fixture_id -> proven unexecutability. The cited test pins the mechanism;
# the row keeps the stated non-PASS outcome with the stated reason.
CHARACTERIZATION_XMAGE: dict[str, dict[str, Any]] = {
    "MICRO_CONTINUOUS_EFFECTS": {
        "outcome": "BLOCKED",
        "reason": (
            "obligated 5/5 unproducible: the restored Crawler's draw triggers "
            "fire during game start (opponents 40 -> 32 proven) and P1 holds "
            "opening seven plus turn-1 draw plus five restored Mountains, so "
            "the honestly evaluated Crawler is larger; no seam suppresses "
            "dealt/drawn cards (XmagePb03Tier1RowsTest)."
        ),
        "classes": ["XmagePb03Tier1RowsTest"],
    },
    "MICRO_COSTS": {
        "outcome": "BLOCKED",
        "reason": (
            "P2's Hex is sorcery-speed and the checkpoint sits on P1's "
            "turn-1 precombat main: sorcery timing (CR 307.5) forbids the "
            "cast, so the engine honestly offers no Hex at P2's priority and "
            "the obligated cost determination can never begin; advancing to "
            "P2's turn would overshoot the record's requested temporal point "
            "(XmagePb03Tier1RowsTest)."
        ),
        "classes": ["XmagePb03Tier1RowsTest"],
    },
    "WS05-CMD-ELIM-4": {
        "outcome": "BLOCKED",
        "reason": (
            "commander-identity duality: the record's battlefield commander "
            "is a setup copy that deals plain damage (P2 40 -> 38, total "
            "stays at restored 19, proven), while the damage ledger lives on "
            "the authoritative identity in the command zone; the identity "
            "card, cast turn 1, is summoning sick and cannot attack without "
            "leaving the record's turn-1 checkpoint (XmagePb03Tier1RowsTest)."
        ),
        "classes": ["XmagePb03Tier1RowsTest"],
    },
    # PB-10 demotions: donor PASS rested on non-obligation harnesses.
    "WS05-CMD-ZONE-LIB-YES": {
        "outcome": "BLOCKED",
        "reason": (
            "PB-10 demotion: donor PASS cited only XmageNativeStateRestorationTest "
            "rejectsFrozenStackSpell, which proves the record fail-closes "
            "(UNSUPPORTED_ZONE on its stack causal step) but observes no "
            "obligated fact. Admitted TIER_2 (genuine Doom Blade tuck path); "
            "execution pending in Wave 2."
        ),
        "classes": ["XmageNativeStateRestorationTest"],
    },
    "WS05-MP-ELIM-OWNED-3": {
        "outcome": "BLOCKED",
        "reason": (
            "PB-10 demotion: donor PASS cited only non-credit harnesses "
            "(elimLifeZeroIsNotCredited, characterizeElimBlocker), which prove "
            "the life-0 requested state is not producible pre-start. Missing "
            "dimension LIFE_ZERO_PRESTART; genuine loss causation is L6 "
            "mechanism evidence (SLOT-02), not row credit."
        ),
        "classes": [
            "XmageNativeStateRestorationTest",
            "XmageFullGameElimExecutionTest",
        ],
    },
    "HIDDEN_02": {
        "outcome": "UNKNOWN",
        "reason": (
            "PB-10 demotion: donor PASS cited only "
            "legacyFrozenLibraryAndFaceDownRecordsRemainFailClosed, which proves "
            "the legacy frozen library order is ambiguous and unexecutable. "
            "No honest fixture-corresponding observation path exists."
        ),
        "classes": ["XmageHiddenReplayIntegrationTest"],
    },
}

# PB-10: donor PASS rows whose sole harness was a non-obligation test
# (rejection / non-credit / fail-closed / parse-only). Each entry records the
# proof so the demotion is reviewable. Current standing for LIB-YES and
# ELIM-OWNED-3 lives in CHARACTERIZATION_XMAGE above; ELIM-4's standing is the
# duality characterization above (its donor harness is recorded here).
PB10_DEMOTIONS: dict[str, dict[str, Any]] = {
    "WS05-CMD-ZONE-LIB-YES": {
        "donor_outcome": "PASS",
        "donor_harness": ["XmageNativeStateRestorationTest"],
        "proof": (
            "the only LIB-YES mention in the cited class is "
            "rejectsFrozenStackSpell, which asserts planFromFrozenRecord "
            "THROWS (UNSUPPORTED_ZONE) and observes no obligated fact."
        ),
    },
    "WS05-MP-ELIM-OWNED-3": {
        "donor_outcome": "PASS",
        "donor_harness": ["XmageNativeStateRestorationTest"],
        "proof": (
            "the only OWNED-3 mention in the cited class is "
            "elimLifeZeroIsNotCredited, which asserts the verdict does NOT "
            "match; XmageFullGameElimExecutionTest characterizes the same "
            "row as NOT_RUN_BLOCKED by name."
        ),
    },
    "HIDDEN_02": {
        "donor_outcome": "PASS",
        "donor_harness": ["XmageHiddenReplayIntegrationTest"],
        "proof": (
            "the only HIDDEN_02 mention is "
            "legacyFrozenLibraryAndFaceDownRecordsRemainFailClosed, which "
            "asserts the record THROWS (LEGACY_LIBRARY_ORDER_AMBIGUOUS)."
        ),
    },
    "WS05-CMD-ELIM-4": {
        "donor_outcome": "PASS",
        "donor_harness": ["XmageCommanderDamageRestorationTest"],
        "proof": (
            "the only ELIM-4 mention is "
            "frozenSplitAndControlFixturesNowParseWithoutFabricatingCommanderIdentity, "
            "which asserts the plan parses and damage binds but observes no "
            "loss and no cleanup."
        ),
    },
}

TIER_2_PENDING_REASON = (
    "admitted TIER_2: the requested state needs a dimension reproducible only "
    "via a qualified genuine-causal transaction (STACK_SPELLS via real casts, "
    "CONTROL_DIVERGENCE via a real control effect, EXTRA_TURN_QUEUE via real "
    "extra-turn spells). Routed to the Wave-2 execution seam; promoted "
    "exclusively by a fixture-loading obligation-asserting native test."
)

TIER_3_REASONS: dict[str, str] = {
    "WS05-MP-ELIM-5": "LIFE_ZERO_PRESTART",
    "WS05-MP-ELIM-CONTROL-3": "LIFE_ZERO_PRESTART, CONTROL_DIVERGENCE",
    "WS05-MP-ELIM-PRIO-3": "LIFE_ZERO_PRESTART",
    "WS05-MP-ELIM-TURN-3": "LIFE_ZERO_PRESTART",
    "WS05-MP-ELIM-STACK-3": "LIFE_ZERO_PRESTART, STACK_SPELLS",
}


def characterization_outcome(fixture_id: str) -> dict[str, Any] | None:
    """Return the characterization record, resolving the ELIM-4 alias."""
    if fixture_id == "WS05-CMD-ELIM-4":
        return CHARACTERIZATION_XMAGE["WS05-CMD-ELIM-4"]
    return CHARACTERIZATION_XMAGE.get(fixture_id)
