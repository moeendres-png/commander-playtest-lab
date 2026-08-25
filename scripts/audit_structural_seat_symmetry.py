from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from commander_lab.engine.structural import StructuralSimulator, load_project_structural_decks
from commander_lab.models import StructuralAbortLimits, StructuralMatchConfig

AUDIT_SEEDS = (1103, 2207, 3301, 4409, 5519, 6619, 7727, 8837)
LOGICAL_IDS = ("A", "B", "C", "D")
RELEVANT_EVENTS = {
    "london_mulligan",
    "turn_started",
    "cards_drawn",
    "pilot_decision",
    "combat_damage",
    "counter_resolved",
    "removal_prevented",
    "commander_removed",
    "permanent_removed",
    "player_eliminated",
    "game_ended",
}


def _rotate_players(values: tuple[str, ...], shift: int) -> tuple[str, ...]:
    out = [""] * len(values)
    for old_seat, value in enumerate(values):
        out[(old_seat + shift) % len(values)] = value
    return tuple(out)


def _logical_for_player_id(deck_order: tuple[str, ...], player_id: str) -> str:
    seat = int(player_id.removeprefix("p")) - 1
    return deck_order[seat].rsplit("/", 1)[-1]


def _normalize_value(value: Any, deck_order: tuple[str, ...]) -> Any:
    if isinstance(value, str) and len(value) == 2 and value.startswith("p") and value[1:].isdigit():
        return _logical_for_player_id(deck_order, value)
    if isinstance(value, str):
        result = value
        for seat in range(1, 5):
            pid = f"p{seat}"
            logical = _logical_for_player_id(deck_order, pid)
            result = result.replace(pid, logical)
        return result
    if isinstance(value, list):
        return [_normalize_value(item, deck_order) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item, deck_order) for key, item in value.items()}
    return value


def _metric_signature(result: Any, deck_order: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    signature: dict[str, dict[str, Any]] = {}
    for seat, deck_id in enumerate(deck_order):
        logical = deck_id.rsplit("/", 1)[-1]
        metric = result.player_metrics[f"p{seat + 1}"]
        signature[logical] = {
            "placement": metric.placement,
            "life": round(metric.life, 8),
            "mulligans": metric.mulligans,
            "lands_played": metric.lands_played,
            "ramp_resolved": metric.ramp_resolved,
            "cards_drawn": metric.cards_drawn,
            "commander_casts": metric.commander_casts,
            "hostile_target_events": metric.hostile_target_events,
            "removals_resolved": metric.removals_resolved,
            "counters_resolved": metric.counters_resolved,
            "protections_resolved": metric.protections_resolved,
            "resources_generated": round(metric.resources_generated, 8),
            "normal_damage_dealt": round(metric.normal_damage_dealt, 8),
            "commander_damage_dealt": round(metric.commander_damage_dealt, 8),
            "eliminated_turn": metric.eliminated_turn,
            "elimination_reason": metric.elimination_reason,
        }
    return signature


def _trace_signature(path: Path, deck_order: tuple[str, ...]) -> dict[str, Any]:
    counts: Counter[tuple[Any, ...]] = Counter()
    first_turn_order: tuple[str, ...] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        event_type = event["event_type"]
        payload = _normalize_value(event.get("payload", {}), deck_order)
        actor = event.get("actor_id")
        logical_actor = _logical_for_player_id(deck_order, actor) if actor else None
        if event_type == "game_started":
            first_turn_order = tuple(_normalize_value(payload.get("turn_order", []), deck_order))
        if event_type not in RELEVANT_EVENTS:
            continue
        target = None
        if isinstance(payload, dict):
            target = payload.get("target_player_id", payload.get("target"))
        selected = payload.get("selected_action_id") if isinstance(payload, dict) else None
        counts[(event_type, logical_actor, target, selected)] += 1
    return {
        "turn_order": first_turn_order,
        "event_counts": sorted((list(key), count) for key, count in counts.items()),
    }


def _run_one(
    simulator: StructuralSimulator,
    deck_order: tuple[str, ...],
    *,
    seed: int,
    shift: int,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"seed-{seed}-shift-{shift}.jsonl"
    result = simulator.simulate(
        StructuralMatchConfig(
            match_id=f"seat-symmetry-{seed}",
            seed=seed,
            deck_ids=deck_order,
            starting_player_seat=shift % 4,
            limits=StructuralAbortLimits(
                max_turns=60,
                max_events=80_000,
                max_no_progress_turns=40,
                max_spells_per_turn=8,
            ),
        ),
        run_id="structural-seat-symmetry-audit",
        event_log_path=log_path,
        capture_events=True,
    )
    if result.aborted:
        raise RuntimeError(f"audit game aborted for seed={seed} shift={shift}: {result.abort_reason}")
    winner_logical = sorted(
        _logical_for_player_id(deck_order, player_id) for player_id in result.winner_ids
    )
    return {
        "winner_logical": winner_logical,
        "turns": result.turns,
        "metrics": _metric_signature(result, deck_order),
        "trace": _trace_signature(log_path, deck_order),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/structural-seat-symmetry-audit")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output)
    decks = load_project_structural_decks(
        root,
        include_synthetic_fixtures=True,
        include_current_opponents=True,
    )
    base = decks["rogshai/current"]
    audit_decks = {}
    base_ids = tuple(f"audit/rogshai/{logical}" for logical in LOGICAL_IDS)
    for deck_id in base_ids:
        audit_decks[deck_id] = base.model_copy(update={"deck_id": deck_id})
    simulator = StructuralSimulator(audit_decks)

    mismatches: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for seed in AUDIT_SEEDS:
        baseline_order = base_ids
        baseline = _run_one(
            simulator,
            baseline_order,
            seed=seed,
            shift=0,
            output_dir=output_dir / "events",
        )
        for shift in (1, 2, 3):
            order = _rotate_players(base_ids, shift)
            observed = _run_one(
                simulator,
                order,
                seed=seed,
                shift=shift,
                output_dir=output_dir / "events",
            )
            equal = observed == baseline
            rows.append({"seed": seed, "shift": shift, "equivariant": equal})
            if not equal:
                mismatches.append(
                    {
                        "seed": seed,
                        "shift": shift,
                        "baseline": baseline,
                        "observed": observed,
                    }
                )

    report = {
        "schema_version": "structural-seat-symmetry-audit-1.0.0",
        "engine_scope": "structural_model_estimates",
        "base_deck": "rogshai/current",
        "seeds": list(AUDIT_SEEDS),
        "permutations_per_seed": 4,
        "comparisons": len(rows),
        "equivariant_comparisons": sum(row["equivariant"] for row in rows),
        "mismatch_count": len(mismatches),
        "seat_symmetry": "PASS" if not mismatches else "FAIL",
        "rows": rows,
        "first_mismatch": mismatches[0] if mismatches else None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "SEAT_SYMMETRY_AUDIT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: report[key] for key in ("comparisons", "equivariant_comparisons", "mismatch_count", "seat_symmetry")}, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
