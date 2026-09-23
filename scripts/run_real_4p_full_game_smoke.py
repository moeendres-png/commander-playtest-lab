from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceError,
    FullGamePilotBinding,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)
from commander_lab.storage import sha256_value


ROOT = Path(__file__).resolve().parents[1]
XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
SCENARIO_ID = "real-existing-decks-4p-technical-smoke-v1"
SEED = 20260923
DEFAULT_SMOKE_DECISIONS = 40

REAL_DECK_PATHS = (
    Path("data/decks/rogshai_current.json"),
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/opponents/hosts_of_mordor_precon.json"),
    Path("data/opponents/lorehold_spirit_precon.json"),
)


def _derived_rules_hash(deck: RulesDeckInput) -> str:
    return sha256_value(
        {
            "deck_id": deck.deck_id,
            "commander_names": list(deck.commander_names),
            "mainboard": list(deck.mainboard),
            "sideboard": list(deck.sideboard),
        }
    )


def _ensure_deck_hash(deck: RulesDeckInput) -> tuple[RulesDeckInput, str]:
    if deck.deck_hash is not None:
        return deck, "source_snapshot"
    return (
        deck.model_copy(update={"deck_hash": _derived_rules_hash(deck)}),
        "derived_rules_identity",
    )


def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBinding:
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck.deck_id,
        strategy="generic",
        commander_names=deck.commander_names,
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def build_real_4p_setup(
    root: Path = ROOT,
) -> tuple[
    FutureXmageScenario,
    tuple[RulesDeckInput, ...],
    tuple[FullGamePilotBinding, ...],
    tuple[dict[str, Any], ...],
]:
    decks: list[RulesDeckInput] = []
    provenance: list[dict[str, Any]] = []

    for relative in REAL_DECK_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"real-deck source missing: {relative}")
        loaded = load_rules_deck_snapshot(path)
        deck, hash_source = _ensure_deck_hash(loaded)
        if deck.deck_hash is None:
            raise AssertionError("deck hash materialization failed")
        decks.append(deck)
        provenance.append(
            {
                "deck_id": deck.deck_id,
                "source_path": relative.as_posix(),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "deck_hash": deck.deck_hash,
                "deck_hash_source": hash_source,
                "commander_names": list(deck.commander_names),
                "mainboard_cards": len(deck.mainboard),
                "total_cards": len(deck.mainboard) + len(deck.commander_names),
            }
        )

    deck_tuple = tuple(decks)
    if len(deck_tuple) != 4:
        raise AssertionError("real technical pod must contain exactly four decks")

    own = deck_tuple[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in deck_tuple[1:]),
        player_count=4,
        seat=1,
        scenario_id=SCENARIO_ID,
        seed=SEED,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    pilots = tuple(_binding(seat, deck_tuple[seat - 1]) for seat in range(1, 5))
    return scenario, deck_tuple, pilots, tuple(provenance)


def _artifact_path(root: Path) -> Path:
    path = root / "artifacts/xmage-full-game/REAL_4P_TECHNICAL_SMOKE.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _base_report(
    scenario: FutureXmageScenario,
    provenance: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "schema_version": "xmage-real-4p-technical-smoke-1.0.0",
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "xmage_commit": scenario.xmage_commit,
        "player_count": scenario.player_count,
        "deck_provenance": list(provenance),
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "rules_authority": "xmage",
        "decision_authority": "commander_lab_external_pilots",
        "canonical_data_mutated": False,
        "official_campaign_eligible": False,
        "deck_strength_evidence": False,
        "actual_card_behavior_coverage_claim": False,
        "note": (
            "A passing bounded smoke proves exact source deck construction, XMage deck import, "
            "4P game creation, authoritative external decision progression and clean shutdown. "
            "It does not prove every card in the decks was exercised or semantically correct."
        ),
    }


def run_preflight(root: Path = ROOT) -> dict[str, Any]:
    scenario, _decks, _pilots, provenance = build_real_4p_setup(root)
    report = _base_report(scenario, provenance)
    report.update({"mode": "preflight", "status": "PASS"})
    _artifact_path(root).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def run_live_smoke(
    root: Path = ROOT,
    *,
    smoke_decisions: int = DEFAULT_SMOKE_DECISIONS,
) -> dict[str, Any]:
    scenario, decks, pilots, provenance = build_real_4p_setup(root)
    report = _base_report(scenario, provenance)
    report["mode"] = "bounded_live_smoke"
    report["smoke_decision_target"] = smoke_decisions

    env_commit = os.environ.get("XMAGE_COMMIT")
    if env_commit is not None and env_commit != XMAGE_COMMIT:
        raise SystemExit(
            f"XMAGE_COMMIT mismatch: expected {XMAGE_COMMIT}, observed {env_commit}"
        )

    try:
        result = XmageFullGameRunner(
            cwd=root,
            request_timeout_seconds=120.0,
            max_decisions=max(smoke_decisions + 10, 100),
        ).run_smoke(
            scenario=scenario,
            decks=decks,
            pilots=pilots,
            smoke_decision_target=smoke_decisions,
        )
    except Exception as exc:
        report.update(
            {
                "status": "FAIL",
                "failure_class": type(exc).__name__,
                "failure_message": str(exc),
            }
        )
        _artifact_path(root).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        raise

    if result.evidence_class != FULL_GAME_EVIDENCE_CLASS:
        raise FullGameConformanceError("real 4P smoke returned unsafe evidence class")
    if result.player_count != 4 or not result.player_count_preserved:
        raise FullGameConformanceError(
            "real 4P smoke did not preserve four-player cardinality"
        )
    if not result.seed_preserved or not result.clean_shutdown:
        raise FullGameConformanceError("real 4P smoke did not preserve seed/clean shutdown")
    if (
        result.fallback_used
        or result.consumed_gameplay_evidence
        or result.holdout_consumed
    ):
        raise FullGameConformanceError(
            "real 4P smoke crossed technical-evidence boundary"
        )

    report.update(
        {
            "status": "PASS",
            "all_four_decks_imported_by_xmage": True,
            "bounded_criterion_met": result.bounded_criterion_met,
            "decision_count": result.decision_count,
            "observed_decision_classes": list(result.observed_decision_classes),
            "terminal_reached": result.terminal_reached,
            "clean_shutdown": result.clean_shutdown,
        }
    )
    _artifact_path(root).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a technical 4P XMage smoke with four existing real 100-card decks."
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate and materialize the exact four deck inputs without starting XMage.",
    )
    parser.add_argument(
        "--smoke-decisions",
        type=int,
        default=DEFAULT_SMOKE_DECISIONS,
        help="Number of authoritative decisions to answer before bounded clean shutdown.",
    )
    args = parser.parse_args()
    if args.smoke_decisions < 1:
        parser.error("--smoke-decisions must be positive")

    report = (
        run_preflight(ROOT)
        if args.preflight_only
        else run_live_smoke(ROOT, smoke_decisions=args.smoke_decisions)
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
