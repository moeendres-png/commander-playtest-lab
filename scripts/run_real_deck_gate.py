"""Real-deck 4-player end-to-end usability gate (technical only).

Runs actual verified Commander decks (2x RogShai + 2x Kaervek) through the
existing full-game runner under external deterministic pilots: single game,
same-seed replay, and an isolated batch. Result class is
REAL_CARD_TECHNICAL_USABILITY_GATE -- never matchup evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FullGamePilotBinding,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    XmageFullGameBatchRunner,
)
from commander_lab.engine.rules.project import load_project_rules_decks
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)

ROOT = Path(__file__).resolve().parents[1]
XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
GATE_LABEL = "REAL_CARD_TECHNICAL_USABILITY_GATE"

# Seat plan: two verified decks, each fielded twice (only two distinct
# verified real decks exist; repeated copies are declared, not hidden).
SEAT_DECKS = ("rogshai", "kaervek", "rogshai", "kaervek")
BASE_SEED = 20260923


def _material_hash(deck_id: str, commanders: tuple[str, ...], mainboard: tuple[str, ...]) -> str:
    material = json.dumps(
        {"deck_id": deck_id, "commander_names": commanders, "mainboard": mainboard},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(material).hexdigest()


def load_gate_decks(root: Path) -> dict[str, RulesDeckInput]:
    """Load canonical decks: rogshai via manifest loader, kaervek via adapter.

    Kaervek's snapshot file uses the same card-entry shape as rogshai
    (oracle_name/quantity/zone) but carries a scalar commander field, so it
    is adapted without altering any card content.
    """
    decks = load_project_rules_decks(root)
    rogshai = decks["rogshai/current"]
    kaervek_path = root / "data/decks/opponents/kaervek/current/deck.json"
    payload = json.loads(kaervek_path.read_text(encoding="utf-8"))
    commanders = (str(payload["commander"]),)
    mainboard: list[str] = []
    for entry in payload["cards"]:
        if entry.get("zone") != "main":
            continue
        mainboard.extend([str(entry["oracle_name"])] * int(entry.get("quantity", 1)))
    kaervek = RulesDeckInput(
        deck_id="kaervek/current",
        name=str(payload["name"]),
        commander_names=commanders,
        mainboard=tuple(mainboard),
        deck_hash=str(payload["deck_hash"]),
        source_path=str(kaervek_path),
    )
    return {"rogshai": rogshai, "kaervek": kaervek}


def build_gate_setup(
    root: Path, seed: int
) -> tuple[FutureXmageScenario, tuple[RulesDeckInput, ...], tuple[FullGamePilotBinding, ...]]:
    """Build seat decks/pilots/scenario for one 4P real-deck game."""
    canonical = load_gate_decks(root)
    decks: list[RulesDeckInput] = []
    pilots: list[FullGamePilotBinding] = []
    for index, family in enumerate(SEAT_DECKS, start=1):
        base = canonical[family]
        seat_deck_id = f"{family}/seat-{index}"
        seat_deck = RulesDeckInput(
            deck_id=seat_deck_id,
            name=base.name,
            commander_names=base.commander_names,
            mainboard=base.mainboard,
            sideboard=base.sideboard,
            deck_hash=_material_hash(seat_deck_id, base.commander_names, base.mainboard),
            source_path=base.source_path,
        )
        decks.append(seat_deck)
        pilots.append(
            FullGamePilotBinding(
                seat=index,
                deck_id=seat_deck_id,
                strategy="generic",
                commander_names=seat_deck.commander_names,
                config=PilotConfig(
                    pilot_name="auto",
                    strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                pilot_identity="GenericCommanderPilot",
                pilot_version="1.0.0",
                decision_policy_version="xmage-full-game-policy-1.0.0",
            )
        )
    own = decks[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=4,
        seat=1,
        scenario_id=f"real-deck-technical-gate-4p-{seed}",
        seed=seed,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    return scenario, tuple(decks), tuple(pilots)


def summarize_result(result, gate: str) -> dict:
    return {
        "gate": gate,
        "evidence_class": result.evidence_class,
        "engine_version": result.engine_version,
        "xmage_commit": result.xmage_commit,
        "player_count": result.scenario.player_count,
        "seed": result.scenario.seed,
        "scenario_id": result.scenario.scenario_id,
        "candidate_id": result.scenario.candidate_id,
        "opponent_deck_ids": list(result.scenario.opponent_deck_ids),
        "decision_count": result.decision_count,
        "terminal": result.terminal,
        "winner_seats": list(result.winner_seats),
        "observed_decision_classes": sorted(
            {
                str(event.get("decision_class"))
                for event in result.result_payload.get("transcript", [])
                if isinstance(event, dict) and event.get("kind") == "decision_accepted"
            }
        ),
        "semantic_transcript_sha256": result.semantic_transcript_sha256,
        "raw_result_sha256": result.raw_result_sha256,
        "consumed_gameplay_evidence": result.consumed_gameplay_evidence,
        "holdout_consumed": result.holdout_consumed,
        "fallback_used": result.fallback_used,
        "hidden_information_actor_scoped": result.hidden_information_actor_scoped,
        "rules_authority": result.xmage_rules_authority,
        "decision_authority": result.commander_lab_pilot_decision_authority,
    }


def cmd_single(args: argparse.Namespace) -> int:
    root = Path(args.root)
    scenario, decks, pilots = build_gate_setup(root, args.seed)
    runner = XmageFullGameRunner(cwd=root)
    result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    summary = summarize_result(result, GATE_LABEL)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    root = Path(args.root)
    runner = XmageFullGameRunner(cwd=root)
    runs = []
    for _ in range(2):
        scenario, decks, pilots = build_gate_setup(root, args.seed)
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        runs.append(summarize_result(result, GATE_LABEL))
    semantic_match = runs[0]["semantic_transcript_sha256"] == runs[1]["semantic_transcript_sha256"]
    raw_match = runs[0]["raw_result_sha256"] == runs[1]["raw_result_sha256"]
    payload = {
        "gate": GATE_LABEL,
        "seed": args.seed,
        "semantic_replay_match": semantic_match,
        "raw_result_match": raw_match,
        "bit_exact_replay_validated": False,
        "runs": runs,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if semantic_match else 1


def cmd_batch(args: argparse.Namespace) -> int:
    root = Path(args.root)
    runner = XmageFullGameRunner(cwd=root)
    batch = XmageFullGameBatchRunner(runner, Path(args.out_dir))
    cases: list[FullGameBatchCase] = []
    for offset in range(args.count):
        seed = args.base_seed + offset
        scenario, decks, pilots = build_gate_setup(root, seed)
        cases.append(
            FullGameBatchCase(
                case_id=f"real-deck-technical-gate-4p-{seed}",
                scenario=scenario,
                decks=decks,
                pilots=pilots,
            )
        )
    report = batch.run(tuple(cases), resume=True, retry_failed=False)
    summary = {
        "gate": GATE_LABEL,
        "total_cases": report.total_cases,
        "completed_cases": report.completed_cases,
        "failed_cases": report.failed_cases,
        "resumed_cases": report.resumed_cases,
        "records": [
            {
                "case_id": record.case_id,
                "status": record.status,
                "elapsed_seconds": record.elapsed_seconds,
                "failure_class": (
                    str(record.failure_class) if record.failure_class is not None else None
                ),
                "failure_message": record.failure_message,
                "decision_count": (
                    record.result.decision_count if record.result is not None else None
                ),
                "terminal": record.result.terminal if record.result is not None else None,
                "winner_seats": (
                    list(record.result.winner_seats) if record.result is not None else None
                ),
            }
            for record in report.records
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report.failed_cases == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real-deck 4P technical usability gate")
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("single")
    single.add_argument("--seed", type=int, default=BASE_SEED)
    single.add_argument("--out", required=True)
    single.set_defaults(func=cmd_single)
    replay = sub.add_parser("replay")
    replay.add_argument("--seed", type=int, default=BASE_SEED)
    replay.add_argument("--out", required=True)
    replay.set_defaults(func=cmd_replay)
    batch = sub.add_parser("batch")
    batch.add_argument("--base-seed", type=int, default=BASE_SEED)
    batch.add_argument("--count", type=int, default=10)
    batch.add_argument("--out-dir", required=True)
    batch.set_defaults(func=cmd_batch)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
