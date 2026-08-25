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
RUN_ID = "rogshai-morcant-balanced-post-seatfix-2026-08-25"
MORCANT_KEY = "morcant"
MORCANT_DECK_ID = "opponent/morcant-elves"
COSMIC_DECK_ID = "opponent/cosmic-spiderman-midbudget"
ROTATING_OPPONENT_IDS = {
    "scions": "opponent/scions-spellcraft-precon",
    "counter": "opponent/counter-intelligence-precon",
    "turtle": "opponent/turtle-power-precon",
    "silverquill": "opponent/silverquill-influence-precon",
    "fantastic": "opponent/fantastic-four-precon",
    "avengers": "opponent/avengers-assemble-precon",
}
OPPONENT_IDS = {MORCANT_KEY: MORCANT_DECK_ID, **ROTATING_OPPONENT_IDS}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schedule(payload: dict) -> list[dict]:
    rows = payload.get("schedule")
    if not isinstance(rows, list) or len(rows) != 12:
        raise SystemExit("block seed schedule must contain exactly 12 rows")
    seeds = [int(row["master_seed"]) for row in rows]
    if len(set(seeds)) != 12:
        raise SystemExit("master seeds must be unique within block")
    seed_indices = [int(row["seed_index"]) for row in rows]
    if seed_indices != list(range(1, 13)):
        raise SystemExit("block seed_index must be exactly 1..12")
    candidate_seats = Counter(int(row["candidate_seat"]) for row in rows)
    if candidate_seats != Counter({1: 3, 2: 3, 3: 3, 4: 3}):
        raise SystemExit(f"candidate seat balance failed: {dict(candidate_seats)}")
    starting_seats = Counter(int(row["xmage_starting_player_seat_0_based"]) + 1 for row in rows)
    if starting_seats != Counter({1: 3, 2: 3, 3: 3, 4: 3}):
        raise SystemExit(f"starting-player seat balance failed: {dict(starting_seats)}")

    appearances: Counter[str] = Counter()
    physical_seats: Counter[tuple[str, int]] = Counter()
    for row in rows:
        candidate_seat = int(row["candidate_seat"])
        by_seat = {int(k): str(v) for k, v in row["opponent_by_seat"].items()}
        if set(by_seat) != ({1, 2, 3, 4} - {candidate_seat}):
            raise SystemExit(f"opponent seat map malformed for seed {row['master_seed']}")
        if len(set(by_seat.values())) != 3:
            raise SystemExit(f"opponents must be distinct for seed {row['master_seed']}")
        if MORCANT_KEY not in by_seat.values():
            raise SystemExit(f"Morcant missing from seed {row['master_seed']}")
        if any(key not in OPPONENT_IDS for key in by_seat.values()):
            raise SystemExit(f"unknown opponent key in seed {row['master_seed']}")
        if COSMIC_DECK_ID in by_seat.values() or "cosmic" in by_seat.values():
            raise SystemExit("Cosmic is forbidden in this campaign")
        for seat, key in by_seat.items():
            appearances[key] += 1
            physical_seats[(key, seat)] += 1

    expected = Counter({MORCANT_KEY: 12, **{key: 4 for key in ROTATING_OPPONENT_IDS}})
    if appearances != expected:
        raise SystemExit(f"opponent appearance balance failed: {dict(appearances)}")
    for seat in range(1, 5):
        if physical_seats[(MORCANT_KEY, seat)] != 3:
            raise SystemExit(f"Morcant seat balance failed at seat {seat}")
    for key in ROTATING_OPPONENT_IDS:
        for seat in range(1, 5):
            if physical_seats[(key, seat)] != 1:
                raise SystemExit(f"{key} seat balance failed at seat {seat}")
    return rows


def materialize_candidates(root: Path, payload: dict):
    rows = payload.get("candidates")
    if not isinstance(rows, list) or len(rows) != 48:
        raise SystemExit("candidate input must contain exactly 48 candidates")
    ids = [str(row["candidate_id"]) for row in rows]
    if ids != [f"C{i:03d}" for i in range(1, 49)]:
        raise SystemExit("candidate ids are not exactly C001..C048 in order")
    context = WholeDeckSearchContext.from_project(root)
    materialized = {}
    structural_hashes = set()
    for row in rows:
        mainboard = tuple(str(name) for name in row["mainboard"])
        if len(mainboard) != 98:
            raise SystemExit(f"{row['candidate_id']} mainboard has {len(mainboard)} cards, expected 98")
        deck = context.materialize(mainboard, label=f"morcant-screen-{row['candidate_id'].lower()}")
        if len(deck.cards) != 100:
            raise SystemExit(f"{row['candidate_id']} materialized to {len(deck.cards)} cards")
        if deck.deck_hash in structural_hashes:
            raise SystemExit(f"duplicate structural deck hash at {row['candidate_id']}")
        structural_hashes.add(deck.deck_hash)
        materialized[str(row["candidate_id"])] = deck
    return materialized


def main() -> None:
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

    candidate_payload = load_json(candidate_path)
    schedule = validate_schedule(load_json(schedule_path))
    candidates = materialize_candidates(root, candidate_payload)

    all_project = load_project_structural_decks(root, include_current_opponents=True)
    missing = [deck_id for deck_id in OPPONENT_IDS.values() if deck_id not in all_project]
    if missing:
        raise SystemExit(f"missing opponent profiles: {missing}")
    opponents = {key: all_project[deck_id] for key, deck_id in OPPONENT_IDS.items()}
    for key, deck in opponents.items():
        if len(deck.cards) != 100:
            raise SystemExit(f"opponent {key} has {len(deck.cards)} cards, expected 100")
    if COSMIC_DECK_ID in {deck.deck_id for deck in opponents.values()}:
        raise SystemExit("Cosmic unexpectedly entered campaign opponent set")

    results_path = output / "GAME_RESULTS.jsonl"
    observations: dict[str, list[dict]] = {candidate_id: [] for candidate_id in candidates}
    with results_path.open("w", encoding="utf-8", newline="\n") as fh:
        for candidate_id, own in candidates.items():
            source_row = next(
                row for row in candidate_payload["candidates"] if row["candidate_id"] == candidate_id
            )
            for row in schedule:
                candidate_seat = int(row["candidate_seat"])
                seats = [None, None, None, None]
                seats[candidate_seat - 1] = own
                opponent_by_seat = {int(k): str(v) for k, v in row["opponent_by_seat"].items()}
                for seat, key in opponent_by_seat.items():
                    seats[seat - 1] = opponents[key]
                if any(deck is None for deck in seats):
                    raise SystemExit("empty seat produced")
                seated = tuple(seats)
                deck_ids = tuple(deck.deck_id for deck in seated)
                if len(set(deck_ids)) != 4:
                    raise SystemExit("pod contains duplicate deck ids")
                simulator = StructuralSimulator({deck.deck_id: deck for deck in seated})
                result = simulator.simulate(
                    StructuralMatchConfig(
                        match_id=f"{candidate_id}-B{int(row['block']):02d}-S{int(row['seed_index']):02d}",
                        seed=int(row["master_seed"]),
                        deck_ids=deck_ids,
                        starting_player_seat=int(row["xmage_starting_player_seat_0_based"]),
                        pilot_configs=(PilotConfig(),) * 4,
                        limits=StructuralAbortLimits(max_turns=args.max_turns),
                    ),
                    run_id=RUN_ID,
                )
                own_metrics = result.player_metrics[f"p{candidate_seat}"]
                obs = {
                    "candidate_id": candidate_id,
                    "candidate_structural_deck_hash": own.deck_hash,
                    "source_v3_deck_hash": str(source_row["source_v3_deck_hash"]),
                    "v5_patch_applied": bool(source_row.get("v5_patch_applied")),
                    "block": int(row["block"]),
                    "seed_index": int(row["seed_index"]),
                    "global_seed_index": int(row["global_seed_index"]),
                    "master_seed": int(row["master_seed"]),
                    "candidate_seat": candidate_seat,
                    "starting_player_seat_0_based": int(row["xmage_starting_player_seat_0_based"]),
                    "opponent_triplet": list(row["opponent_triplet"]),
                    "opponent_by_seat": {str(k): v for k, v in sorted(opponent_by_seat.items())},
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
                    "evidence_class": EVIDENCE_CLASS,
                    "opponent_information_class": "morcant_partially_observed_synthetic_completion",
                    "truth_boundary": (
                        "Structural model sample; Morcant completion is synthetic for unknown slots; "
                        "not empirical gameplay or external-rules evidence."
                    ),
                }
                observations[candidate_id].append(obs)
                fh.write(json.dumps(obs, sort_keys=True, ensure_ascii=False) + "\n")

    summaries = []
    for candidate_id in sorted(observations):
        rows = observations[candidate_id]
        completed = [r for r in rows if r["completed"] and not r["aborted"]]
        summaries.append(
            {
                "candidate_id": candidate_id,
                "games_scheduled": len(rows),
                "games_completed": len(completed),
                "games_aborted": sum(int(r["aborted"]) for r in rows),
                "structural_first_place_count": sum(int(r["candidate_first_place"]) for r in completed),
                "structural_first_place_fraction": (
                    fmean(float(r["candidate_first_place"]) for r in completed) if completed else None
                ),
                "mean_placement": (
                    fmean(float(r["candidate_placement"]) for r in completed) if completed else None
                ),
                "mean_damage": (
                    fmean(float(r["candidate_damage"]) for r in completed) if completed else None
                ),
                "mean_cards_drawn": (
                    fmean(float(r["candidate_cards_drawn"]) for r in completed) if completed else None
                ),
                "mean_turns": fmean(float(r["turns"]) for r in completed) if completed else None,
                "evidence_class": EVIDENCE_CLASS,
            }
        )

    with (output / "CANDIDATE_SUMMARY.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    pairwise = []
    ids = sorted(observations)
    for i, a in enumerate(ids):
        by_seed_a = {int(r["seed_index"]): r for r in observations[a]}
        for b in ids[i + 1 :]:
            by_seed_b = {int(r["seed_index"]): r for r in observations[b]}
            paired = []
            for seed_index in range(1, 13):
                ra, rb = by_seed_a[seed_index], by_seed_b[seed_index]
                if ra["completed"] and rb["completed"] and not ra["aborted"] and not rb["aborted"]:
                    paired.append((ra, rb))
            pairwise.append(
                {
                    "candidate_a": a,
                    "candidate_b": b,
                    "paired_completed": len(paired),
                    "a_minus_b_first_place": (
                        fmean(float(ra["candidate_first_place"] - rb["candidate_first_place"]) for ra, rb in paired)
                        if paired
                        else None
                    ),
                    "a_minus_b_placement": (
                        fmean(float(ra["candidate_placement"] - rb["candidate_placement"]) for ra, rb in paired)
                        if paired
                        else None
                    ),
                    "a_minus_b_damage": (
                        fmean(float(ra["candidate_damage"] - rb["candidate_damage"]) for ra, rb in paired)
                        if paired
                        else None
                    ),
                    "evidence_class": EVIDENCE_CLASS,
                }
            )
    if len(pairwise) != 1128:
        raise SystemExit(f"pairwise matrix has {len(pairwise)} rows, expected 1128")
    with (output / "PAIRWISE_MATRIX.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(pairwise[0]))
        writer.writeheader()
        writer.writerows(pairwise)

    completed_total = sum(row["games_completed"] for row in summaries)
    aborted_total = sum(row["games_aborted"] for row in summaries)
    rankable = [row for row in summaries if row["games_completed"] == 12]
    rankable.sort(
        key=lambda row: (
            -float(row["structural_first_place_fraction"]),
            float(row["mean_placement"]),
            -float(row["mean_damage"]),
            row["candidate_id"],
        )
    )
    report = {
        "schema_version": "rogshai-morcant-structural-block-report-1.0.0",
        "run_id": RUN_ID,
        "evidence_class": EVIDENCE_CLASS,
        "opponent_information_class": "morcant_partially_observed_synthetic_completion",
        "engine_version": ENGINE_VERSION,
        "fidelity_engine_version": FIDELITY_ENGINE_VERSION,
        "candidate_count": 48,
        "games_per_candidate": 12,
        "target_game_count": 576,
        "completed_game_count": completed_total,
        "aborted_game_count": aborted_total,
        "pod_size": 4,
        "candidate_input_sha256": sha256_file(candidate_path),
        "seed_schedule_sha256": sha256_file(schedule_path),
        "opponent_ids": OPPONENT_IDS,
        "morcant_required_every_game": True,
        "cosmic_excluded": True,
        "opponent_weighting": "cumulative_coverage_equalization_not_meta_prior",
        "pre_gameplay_candidate_elimination": 0,
        "pairwise_rows": len(pairwise),
        "structural_order": [row["candidate_id"] for row in rankable],
        "top_structural_rows": rankable[:10],
        "truth_boundaries": [
            "Structural Simulation is model evidence, not empirical Commander gameplay.",
            "Morcant has a partially observed, synthetic-completion working profile.",
            "Cosmic is excluded from the campaign.",
            "Equalized co-opponent coverage is experimental design, not a meta-frequency claim.",
            "No canonical deck, inventory, allocation, purchase, or opponent truth is mutated.",
        ],
    }
    (output / "RUN_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
