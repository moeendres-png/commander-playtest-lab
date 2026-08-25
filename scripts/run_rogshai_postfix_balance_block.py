from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import fmean

from commander_lab.engine.structural import (
    ENGINE_VERSION,
    FIDELITY_ENGINE_VERSION,
    StructuralSimulator,
    load_project_structural_decks,
)
from commander_lab.models import PilotConfig, StructuralAbortLimits, StructuralMatchConfig
from commander_lab.whole_deck.search_context import WholeDeckSearchContext

EVIDENCE_CLASS = "structural_model_estimates"
RUN_ID = "rogshai-postfix-opponent-balance-7680-2026-08-25-v1"
OPPONENT_IDS = {
    "kaervek": "kaervek/current",
    "blight": "opponent/blight-curse-precon",
    "dance": "opponent/dance-elements-precon",
    "lorehold": "opponent/lorehold-spirit-precon",
    "doom": "opponent/doom-prevails-precon",
    "wakanda": "opponent/wakanda-forever-precon",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schedule(payload: dict) -> list[dict]:
    rows = payload.get("schedule")
    if not isinstance(rows, list) or len(rows) != 16:
        raise SystemExit("block schedule must contain exactly 16 rows")
    seeds = [int(row["master_seed"]) for row in rows]
    if len(set(seeds)) != 16:
        raise SystemExit("block master seeds must be unique")
    candidate_seats = Counter(int(row["candidate_seat"]) for row in rows)
    starting_seats = Counter(int(row["starting_player_seat_0_based"]) + 1 for row in rows)
    expected = Counter({1: 4, 2: 4, 3: 4, 4: 4})
    if candidate_seats != expected:
        raise SystemExit(f"candidate seat balance failed: {dict(candidate_seats)}")
    if starting_seats != expected:
        raise SystemExit(f"starting seat balance failed: {dict(starting_seats)}")
    for row in rows:
        candidate_seat = int(row["candidate_seat"])
        triplet = tuple(str(value) for value in row["opponent_triplet"])
        if len(triplet) != 3 or len(set(triplet)) != 3:
            raise SystemExit("opponent triplet must contain three distinct opponents")
        if any(key not in OPPONENT_IDS for key in triplet):
            raise SystemExit(f"unexpected opponent triplet {triplet}")
        seat_map = {int(seat): str(value) for seat, value in row["opponent_by_seat"].items()}
        if set(seat_map) != ({1, 2, 3, 4} - {candidate_seat}):
            raise SystemExit("opponent seat map malformed")
        if set(seat_map.values()) != set(triplet):
            raise SystemExit("opponent seat map does not match triplet")
        if "morcant" in triplet or "cosmic" in triplet:
            raise SystemExit("Morcant/Cosmic are prohibited in this balance lane")
    return rows


def materialize_candidates(root: Path, payload: dict):
    rows = payload.get("candidates")
    if not isinstance(rows, list) or len(rows) != 48:
        raise SystemExit("candidate input must contain exactly 48 candidates")
    ids = [str(row["candidate_id"]) for row in rows]
    expected_ids = [f"C{i:03d}" for i in range(1, 49)]
    if ids != expected_ids:
        raise SystemExit("candidate ids are not exactly C001..C048 in order")
    if sum(bool(row.get("v5_patch_applied")) for row in rows) != 1:
        raise SystemExit("exactly one candidate must carry the v5 patch")
    c011 = rows[10]
    if c011["candidate_id"] != "C011" or not c011.get("v5_patch_applied"):
        raise SystemExit("C011 must be the v5-patched candidate")
    if "Ruin Ghost" in c011["mainboard"] or "Swiftfoot Boots" not in c011["mainboard"]:
        raise SystemExit("C011 v5 patch content mismatch")

    context = WholeDeckSearchContext.from_project(root)
    materialized = {}
    structural_hashes = set()
    for row in rows:
        mainboard = tuple(str(name) for name in row["mainboard"])
        if len(mainboard) != 98:
            raise SystemExit(
                f"{row['candidate_id']} mainboard has {len(mainboard)} cards, expected 98"
            )
        deck = context.materialize(
            mainboard, label=f"postfix-balance-{row['candidate_id'].lower()}"
        )
        if len(deck.cards) != 100:
            raise SystemExit(f"{row['candidate_id']} materialized to {len(deck.cards)} cards")
        if deck.deck_hash in structural_hashes:
            raise SystemExit(f"structural duplicate deck hash detected at {row['candidate_id']}")
        structural_hashes.add(deck.deck_hash)
        materialized[str(row["candidate_id"])] = deck
    return materialized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-turns", type=int, default=50)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    candidate_path = Path(args.candidates).resolve()
    schedule_path = Path(args.schedule).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    if ENGINE_VERSION != "structural-0.6.2":
        raise SystemExit(f"unexpected structural engine version {ENGINE_VERSION}")
    if FIDELITY_ENGINE_VERSION != "structural-fidelity-overlay-2026-08-25-v2":
        raise SystemExit(f"unexpected fidelity engine version {FIDELITY_ENGINE_VERSION}")

    candidate_payload = load_json(candidate_path)
    schedule_payload = load_json(schedule_path)
    schedule = validate_schedule(schedule_payload)
    candidates = materialize_candidates(root, candidate_payload)

    all_project = load_project_structural_decks(root, include_current_opponents=True)
    missing = [deck_id for deck_id in OPPONENT_IDS.values() if deck_id not in all_project]
    if missing:
        raise SystemExit(f"missing structural opponent profiles: {missing}")
    opponents = {key: all_project[deck_id] for key, deck_id in OPPONENT_IDS.items()}
    for key, deck in opponents.items():
        if len(deck.cards) != 100:
            raise SystemExit(f"opponent {key} has {len(deck.cards)} cards, expected 100")

    observations: dict[str, list[dict]] = {candidate_id: [] for candidate_id in candidates}
    results_path = output / "GAME_RESULTS.jsonl"
    with results_path.open("w", encoding="utf-8", newline="\n") as results_file:
        for candidate_id, own in candidates.items():
            source_row = next(
                row
                for row in candidate_payload["candidates"]
                if row["candidate_id"] == candidate_id
            )
            for row in schedule:
                candidate_seat = int(row["candidate_seat"])
                seats = [None, None, None, None]
                seats[candidate_seat - 1] = own
                opponent_by_seat = {
                    int(seat): str(value) for seat, value in row["opponent_by_seat"].items()
                }
                for seat, key in opponent_by_seat.items():
                    seats[seat - 1] = opponents[key]
                if any(deck is None for deck in seats):
                    raise SystemExit("seat construction produced an empty seat")
                seated = tuple(seats)
                deck_ids = tuple(deck.deck_id for deck in seated)
                if len(set(deck_ids)) != 4:
                    raise SystemExit("4P pod contains duplicate deck ids")
                simulator = StructuralSimulator({deck.deck_id: deck for deck in seated})
                result = simulator.simulate(
                    StructuralMatchConfig(
                        match_id=f"{candidate_id}-B{int(row['block']):02d}-S{int(row['scenario_index']):03d}",
                        seed=int(row["master_seed"]),
                        deck_ids=deck_ids,
                        starting_player_seat=int(row["starting_player_seat_0_based"]),
                        pilot_configs=(PilotConfig(),) * 4,
                        limits=StructuralAbortLimits(max_turns=args.max_turns),
                    ),
                    run_id=RUN_ID,
                )
                own_metrics = result.player_metrics[f"p{candidate_seat}"]
                observation = {
                    "candidate_id": candidate_id,
                    "candidate_structural_deck_hash": own.deck_hash,
                    "source_v3_deck_hash": str(source_row["source_v3_deck_hash"]),
                    "v5_patch_applied": bool(source_row.get("v5_patch_applied")),
                    "block": int(row["block"]),
                    "scenario_index": int(row["scenario_index"]),
                    "master_seed": int(row["master_seed"]),
                    "candidate_seat": candidate_seat,
                    "starting_player_seat_0_based": int(row["starting_player_seat_0_based"]),
                    "opponent_triplet": list(row["opponent_triplet"]),
                    "opponent_by_seat": {
                        str(key): value for key, value in sorted(opponent_by_seat.items())
                    },
                    "completed": bool(result.completed),
                    "aborted": bool(result.aborted),
                    "abort_reason": result.abort_reason,
                    "turns": int(result.turns),
                    "candidate_placement": int(own_metrics.placement),
                    "candidate_first_place": int(own_metrics.placement == 1),
                    "candidate_damage": float(
                        own_metrics.normal_damage_dealt + own_metrics.commander_damage_dealt
                    ),
                    "candidate_cards_drawn": int(own_metrics.cards_drawn),
                    "winner_ids": list(result.winner_ids),
                    "event_count": int(result.event_count),
                    "log_sha256": result.log_sha256,
                    "engine_version": ENGINE_VERSION,
                    "fidelity_engine_version": FIDELITY_ENGINE_VERSION,
                    "evidence_class": EVIDENCE_CLASS,
                    "opponent_information_class": "well_supported_real_current_complete_or_official_precon",
                    "truth_boundary": "Structural model sample only; not empirical Commander win rate or external-rules evidence.",
                }
                observations[candidate_id].append(observation)
                results_file.write(
                    json.dumps(observation, sort_keys=True, ensure_ascii=False) + "\n"
                )

    summaries = []
    for candidate_id in sorted(observations):
        rows = observations[candidate_id]
        completed = [row for row in rows if row["completed"] and not row["aborted"]]
        summaries.append(
            {
                "candidate_id": candidate_id,
                "games_scheduled": len(rows),
                "games_completed": len(completed),
                "games_aborted": sum(int(row["aborted"]) for row in rows),
                "structural_first_place_count": sum(
                    int(row["candidate_first_place"]) for row in completed
                ),
                "structural_first_place_fraction": fmean(
                    float(row["candidate_first_place"]) for row in completed
                )
                if completed
                else None,
                "mean_placement": fmean(float(row["candidate_placement"]) for row in completed)
                if completed
                else None,
                "mean_damage": fmean(float(row["candidate_damage"]) for row in completed)
                if completed
                else None,
                "mean_cards_drawn": fmean(float(row["candidate_cards_drawn"]) for row in completed)
                if completed
                else None,
                "mean_turns": fmean(float(row["turns"]) for row in completed)
                if completed
                else None,
                "evidence_class": EVIDENCE_CLASS,
            }
        )

    summary_path = output / "CANDIDATE_SUMMARY.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    completed_total = sum(int(row["games_completed"]) for row in summaries)
    aborted_total = sum(int(row["games_aborted"]) for row in summaries)
    report = {
        "schema_version": "rogshai-postfix-opponent-balance-block-report-1.0.0",
        "run_id": RUN_ID,
        "evidence_class": EVIDENCE_CLASS,
        "opponent_information_class": "well_supported_real_current_complete_or_official_precon",
        "engine_version": ENGINE_VERSION,
        "fidelity_engine_version": FIDELITY_ENGINE_VERSION,
        "candidate_count": 48,
        "games_per_candidate": 16,
        "target_game_count": 768,
        "completed_game_count": completed_total,
        "aborted_game_count": aborted_total,
        "pod_size": 4,
        "candidate_input_sha256": sha256_file(candidate_path),
        "seed_schedule_sha256": sha256_file(schedule_path),
        "opponents": OPPONENT_IDS,
        "morcant_excluded": True,
        "cosmic_excluded": True,
        "pre_gameplay_candidate_elimination": 0,
        "truth_boundaries": [
            "Structural Simulation is model evidence, not empirical Commander gameplay.",
            "All 48 hard-valid unique candidates were admitted before gameplay.",
            "Cosmic and Morcant are excluded from this opponent-equalization lane.",
            "No canonical deck, inventory, allocation, purchase, or opponent truth was mutated.",
        ],
    }
    (output / "RUN_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if completed_total != 768 or aborted_total != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
