from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.engine.structural.simulator import StructuralSimulator
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    PilotUtilityWeights,
    StructuralAbortLimits,
    StructuralDeckProfile,
    StructuralMatchConfig,
)

PILOT_PROFILES = (
    "weak",
    "average",
    "strong",
    "near_optimal_heuristic",
    "aggressive",
    "conservative",
    "interaction_holding",
    "commander_focused",
    "engine_focused",
    "anti_leader",
    "anti_combo",
    "rebuild_focused",
    "tempo_focused",
    "politically_low_visibility",
    "politically_aggressive",
    "adversarial_worst_case",
)

POLITICS_REGIMES = (
    "rational_threat_focus",
    "current_leader_focus",
    "commander_reputation_focus",
    "combo_prevention",
    "revenge_bias",
    "random_targeting_noise",
    "open_mana_deterrence",
    "visible_engine_focus",
    "low_visibility_tolerance",
    "table_balance",
)

# The five-dimensional surface is retained for cheap exhaustive stress sweeps.  It is
# explicitly NOT the structural simulator or learned human behaviour.
_BASE: dict[str, tuple[float, float, float, float, float]] = {
    "weak": (0.35, 0.35, 0.35, 0.35, 0.40),
    "average": (0.55, 0.55, 0.55, 0.55, 0.55),
    "strong": (0.72, 0.72, 0.72, 0.72, 0.68),
    "near_optimal_heuristic": (0.86, 0.86, 0.84, 0.86, 0.74),
    "aggressive": (0.82, 0.45, 0.48, 0.42, 0.25),
    "conservative": (0.43, 0.78, 0.68, 0.76, 0.82),
    "interaction_holding": (0.48, 0.86, 0.66, 0.66, 0.72),
    "commander_focused": (0.79, 0.52, 0.45, 0.44, 0.28),
    "engine_focused": (0.62, 0.55, 0.88, 0.58, 0.42),
    "anti_leader": (0.52, 0.83, 0.58, 0.62, 0.56),
    "anti_combo": (0.44, 0.91, 0.60, 0.58, 0.68),
    "rebuild_focused": (0.45, 0.64, 0.70, 0.93, 0.75),
    "tempo_focused": (0.75, 0.70, 0.52, 0.48, 0.45),
    "politically_low_visibility": (0.52, 0.61, 0.63, 0.65, 0.95),
    "politically_aggressive": (0.78, 0.58, 0.60, 0.54, 0.10),
    "adversarial_worst_case": (0.68, 0.92, 0.70, 0.72, 0.38),
}

_POLITICS: dict[str, tuple[float, float, float, float, float]] = {
    "rational_threat_focus": (0.25, 0.80, 0.45, 0.30, 0.55),
    "current_leader_focus": (0.20, 0.74, 0.42, 0.32, 0.50),
    "commander_reputation_focus": (0.44, 0.56, 0.45, 0.28, 0.18),
    "combo_prevention": (0.18, 0.92, 0.58, 0.30, 0.55),
    "revenge_bias": (0.52, 0.45, 0.32, 0.22, 0.18),
    "random_targeting_noise": (0.46, 0.46, 0.46, 0.46, 0.46),
    "open_mana_deterrence": (0.22, 0.72, 0.48, 0.44, 0.70),
    "visible_engine_focus": (0.28, 0.82, 0.76, 0.30, 0.25),
    "low_visibility_tolerance": (0.32, 0.50, 0.42, 0.46, 0.88),
    "table_balance": (0.36, 0.68, 0.58, 0.58, 0.68),
}

# Real structural-pilot parameters: all 11 utility dimensions used by BasePilot.
# Values are scenario hypotheses, not learned observations.
_DEFAULT_WEIGHTS = {
    "survival": 1.20,
    "mana_efficiency": 0.95,
    "card_advantage": 1.15,
    "tempo": 1.00,
    "engine_development": 1.10,
    "interaction_reserve": 1.15,
    "commander_value": 1.10,
    "threat_reduction": 1.20,
    "win_progress": 1.25,
    "political_visibility": -0.70,
    "rebuild_capacity": 1.00,
}

_PROFILE_DELTAS: dict[str, dict[str, float]] = {
    "weak": {
        "survival": -0.45,
        "card_advantage": -0.55,
        "interaction_reserve": -0.75,
        "threat_reduction": -0.55,
        "rebuild_capacity": -0.65,
        "political_visibility": 0.45,
    },
    "average": {
        "survival": -0.20,
        "card_advantage": -0.15,
        "interaction_reserve": -0.30,
        "threat_reduction": -0.20,
        "win_progress": -0.15,
        "rebuild_capacity": -0.25,
        "political_visibility": 0.20,
    },
    "strong": {},
    "near_optimal_heuristic": {
        "survival": 0.15,
        "card_advantage": 0.10,
        "interaction_reserve": 0.20,
        "threat_reduction": 0.10,
        "win_progress": 0.15,
        "rebuild_capacity": 0.15,
        "political_visibility": -0.15,
    },
    "aggressive": {
        "survival": -0.25,
        "tempo": 0.45,
        "interaction_reserve": -0.35,
        "win_progress": 0.55,
        "political_visibility": 0.45,
        "rebuild_capacity": -0.25,
    },
    "conservative": {
        "survival": 0.35,
        "tempo": -0.20,
        "interaction_reserve": 0.30,
        "win_progress": -0.20,
        "political_visibility": -0.35,
        "rebuild_capacity": 0.25,
    },
    "interaction_holding": {
        "interaction_reserve": 0.65,
        "threat_reduction": 0.35,
        "mana_efficiency": -0.15,
        "tempo": -0.10,
    },
    "commander_focused": {
        "commander_value": 0.75,
        "win_progress": 0.25,
        "engine_development": -0.20,
        "political_visibility": 0.25,
    },
    "engine_focused": {
        "engine_development": 0.75,
        "card_advantage": 0.35,
        "tempo": -0.20,
        "political_visibility": 0.20,
    },
    "anti_leader": {"threat_reduction": 0.70, "interaction_reserve": 0.25, "win_progress": -0.10},
    "anti_combo": {
        "interaction_reserve": 0.80,
        "threat_reduction": 0.60,
        "tempo": -0.20,
        "mana_efficiency": -0.10,
    },
    "rebuild_focused": {
        "rebuild_capacity": 0.90,
        "card_advantage": 0.25,
        "survival": 0.20,
        "tempo": -0.25,
    },
    "tempo_focused": {
        "tempo": 0.70,
        "mana_efficiency": 0.25,
        "interaction_reserve": 0.20,
        "rebuild_capacity": -0.30,
    },
    "politically_low_visibility": {
        "political_visibility": -0.95,
        "win_progress": -0.10,
        "survival": 0.20,
    },
    "politically_aggressive": {
        "political_visibility": 0.65,
        "win_progress": 0.45,
        "tempo": 0.25,
        "survival": -0.15,
    },
    "adversarial_worst_case": {
        "survival": 0.30,
        "interaction_reserve": 0.55,
        "threat_reduction": 0.55,
        "rebuild_capacity": 0.40,
        "win_progress": 0.10,
    },
}

_POLITICS_DELTAS: dict[str, dict[str, float]] = {
    "rational_threat_focus": {"threat_reduction": 0.25, "interaction_reserve": 0.10},
    "current_leader_focus": {"threat_reduction": 0.35, "tempo": 0.05},
    "commander_reputation_focus": {
        "commander_value": -0.10,
        "political_visibility": -0.20,
        "survival": 0.10,
    },
    "combo_prevention": {"interaction_reserve": 0.45, "threat_reduction": 0.35, "tempo": -0.10},
    "revenge_bias": {"threat_reduction": 0.10, "win_progress": 0.10, "political_visibility": 0.15},
    "random_targeting_noise": {"threat_reduction": -0.15, "survival": -0.05},
    "open_mana_deterrence": {"interaction_reserve": 0.30, "political_visibility": -0.15},
    "visible_engine_focus": {
        "engine_development": -0.10,
        "political_visibility": -0.30,
        "threat_reduction": 0.25,
    },
    "low_visibility_tolerance": {"political_visibility": -0.35, "engine_development": 0.10},
    "table_balance": {"survival": 0.10, "threat_reduction": 0.20, "rebuild_capacity": 0.10},
}

_STRENGTH = {
    "weak": PilotStrength.WEAK,
    "average": PilotStrength.AVERAGE,
    "strong": PilotStrength.STRONG,
    "near_optimal_heuristic": PilotStrength.NEAR_OPTIMAL_HEURISTIC,
}


@dataclass(frozen=True)
class PolicyTournamentConfig:
    seed: int = 20260807
    rounds: int = 128
    pod_sizes: tuple[int, ...] = (4,)
    iterations_per_scenario: int = 1
    max_turns: int = 24
    workers: int = 1

    def __post_init__(self) -> None:
        if self.pod_sizes != (4,):
            raise ValueError(
                "Operational Commander Playtest Lab simulations are 4-player only; "
                "3P/5P pod sensitivity is out of project scope."
            )


def _hash_float(*parts: object) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _hash_int(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def pilot_config_for(profile: str, politics: str) -> PilotConfig:
    """Create a real Structural Simulator PilotConfig from a synthetic scenario policy.

    The mapping only changes visible-state utility weights. It never gives hidden cards,
    library order, future draws, or empirical opponent knowledge to the pilot.
    """
    if profile not in _PROFILE_DELTAS:
        raise KeyError(f"unknown pilot profile: {profile}")
    if politics not in _POLITICS_DELTAS:
        raise KeyError(f"unknown politics regime: {politics}")
    values = dict(_DEFAULT_WEIGHTS)
    for source in (_PROFILE_DELTAS[profile], _POLITICS_DELTAS[politics]):
        for key, delta in source.items():
            values[key] = max(-5.0, min(5.0, values[key] + delta))
    weights = PilotUtilityWeights(**values)
    parameter_hash = hashlib.sha256(
        json.dumps(
            {"profile": profile, "politics": politics, "weights": weights.model_dump(mode="json")},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return PilotConfig(
        pilot_name="auto",
        strength=_STRENGTH.get(profile, PilotStrength.STRONG),
        mode=PilotDecisionMode.DETERMINISTIC,
        weights=weights,
        profile_version="1.0.0",
        parameter_hash=parameter_hash,
        source_rule_ids=(f"phase12.15.profile.{profile}", f"phase12.15.politics.{politics}"),
        allowed_deviation=0.5,
    )


def policy_score(
    pilot: str, politics: str, pod_size: int, opponent_pressure: float, *, seed: int
) -> float:
    """Cheap synthetic stress-surface score, never an empirical or simulator result."""
    p = _BASE[pilot]
    r = _POLITICS[politics]
    scale = 1.0 + max(0, pod_size - 3) * 0.12
    base = (
        p[0] * (0.75 - r[1] * 0.18)
        + p[1] * (0.55 + opponent_pressure * 0.35)
        + p[2] * (0.70 - r[2] * 0.22)
        + p[3] * (0.45 + (pod_size - 3) * 0.16)
        + p[4] * (0.35 + r[4] * 0.35)
    ) / scale
    jitter = (_hash_float(seed, pilot, politics, pod_size, opponent_pressure) - 0.5) * 0.03
    return round(base + jitter, 6)


def _multiplicative_weights(
    rows: list[dict[str, Any]], rounds: int, seed: int, *, value_key: str
) -> dict[str, Any]:
    weights = {name: 1.0 / len(PILOT_PROFILES) for name in PILOT_PROFILES}
    if not rows:
        return {"method": "multiplicative_weights", "final_weights": weights, "trace": []}
    contexts: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        contexts[
            (row.get("deck_id"), row["politics"], row["pod_size"], row.get("scenario_index", 0))
        ].append(row)
    usable = [
        group for group in contexts.values() if {r["pilot"] for r in group} == set(PILOT_PROFILES)
    ]
    if not usable:
        return {
            "method": "multiplicative_weights",
            "final_weights": weights,
            "trace": [],
            "contexts": 0,
        }
    eta = 0.08
    rng = random.Random(seed)
    trace: list[dict[str, Any]] = []
    for round_index in range(rounds):
        group = usable[rng.randrange(len(usable))]
        best = max(float(r[value_key]) for r in group)
        by_pilot = {r["pilot"]: float(r[value_key]) for r in group}
        for pilot in weights:
            loss = best - by_pilot[pilot]
            weights[pilot] *= math.exp(-eta * loss)
        total = sum(weights.values()) or 1.0
        for pilot in weights:
            weights[pilot] /= total
        if round_index in {0, rounds - 1}:
            trace.append({"round": round_index + 1, "weights": dict(sorted(weights.items()))})
    return {
        "method": "multiplicative_weights",
        "final_weights": dict(sorted(weights.items())),
        "trace": trace,
        "contexts": len(usable),
    }


def run_policy_tournament(
    opponent_variants: Iterable[dict[str, Any]],
    config: PolicyTournamentConfig = PolicyTournamentConfig(),
) -> dict[str, Any]:
    """Exhaustive cheap stress surface retained for fast search, not self-play."""
    variants = tuple(opponent_variants)
    rows: list[dict[str, Any]] = []
    for pilot in PILOT_PROFILES:
        values: list[float] = []
        for politics in POLITICS_REGIMES:
            for pod_size in config.pod_sizes:
                for variant in variants:
                    pressure = float(variant.get("pressure", 0.5))
                    score = policy_score(pilot, politics, pod_size, pressure, seed=config.seed)
                    values.append(score)
                    rows.append(
                        {
                            "pilot": pilot,
                            "politics": politics,
                            "pod_size": pod_size,
                            "opponent_variant": variant["variant_id"],
                            "score": score,
                        }
                    )
        ordered = sorted(values)
        rows.append(
            {
                "summary": {
                    "pilot": pilot,
                    "mean_score": round(sum(values) / len(values), 6),
                    "worst_case_score": ordered[0],
                    "q10_score": ordered[max(0, math.ceil(len(ordered) * 0.10) - 1)],
                    "scenario_count": len(values),
                }
            }
        )
    summaries = [r["summary"] for r in rows if "summary" in r]
    rankings = sorted(
        summaries, key=lambda x: (x["worst_case_score"], x["mean_score"]), reverse=True
    )
    scenario_rows = [r for r in rows if "score" in r]
    # This synthetic grid is not suitable for paired regret contexts because opponent
    # variants differ by pilot iteration order; keep its optimizer explicitly synthetic.
    return {
        "schema_version": 2,
        "validation_level": "structural_only",
        "estimate_type": "synthetic_policy_stress_surface",
        "self_play_executed": False,
        "hidden_information_access": False,
        "empirical_weights_used": False,
        "config": {"seed": config.seed, "rounds": config.rounds, "pod_sizes": config.pod_sizes},
        "rankings": rankings,
        "scenario_rows": scenario_rows,
    }


def _variant_deck(base: StructuralDeckProfile, variant: dict[str, Any]) -> StructuralDeckProfile:
    pressure = float(variant.get("pressure", 0.5))
    multiplier = 0.82 + pressure * 0.36
    cards = []
    for card in base.cards:
        if card.is_land:
            cards.append(card)
            continue
        strengths = {
            role: max(0.05, value * multiplier) for role, value in card.role_strengths.items()
        }
        cards.append(
            card.model_copy(
                update={
                    "role_strengths": strengths,
                    "base_power": card.base_power * multiplier,
                    "immediate_impact": min(2.0, card.immediate_impact * multiplier),
                }
            )
        )
    variant_id = str(variant["variant_id"])
    return base.model_copy(
        update={
            "deck_id": variant_id,
            "deck_hash": hashlib.sha256(
                f"{base.deck_hash}|{variant_id}|{pressure}".encode()
            ).hexdigest(),
            "cards": tuple(cards),
        }
    )


def _policy_worker(
    payload: tuple[str, list[dict[str, Any]], tuple[str, ...], int],
) -> list[dict[str, Any]]:
    """Execute a deterministic slice of policy tournament scenarios in one process."""
    root_text, tasks, pilot_profiles, max_turns = payload
    root = Path(root_text)
    decks = load_project_structural_decks(root, include_current_opponents=True)
    registry = build_registry(root)
    variant_decks: dict[str, StructuralDeckProfile] = {}
    for variant in registry["opponent_variants"]:
        base_id = str(variant["deck_id"])
        if base_id in decks:
            variant_decks[str(variant["variant_id"])] = _variant_deck(decks[base_id], variant)
    all_decks = dict(decks)
    all_decks.update(variant_decks)
    simulator = StructuralSimulator(all_decks)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        deck_id = str(task["deck_id"])
        politics = str(task["politics"])
        pod_size = int(task["pod_size"])
        scenario_index = int(task["scenario_index"])
        iteration = int(task["iteration"])
        selected = list(task["selected"])
        match_seed = int(task["match_seed"])
        start = int(task["start"])
        opponent_config = pilot_config_for("strong", politics)
        for pilot in pilot_profiles:
            controlled = pilot_config_for(pilot, politics)
            match = simulator.simulate(
                StructuralMatchConfig(
                    match_id=f"phase1215-{scenario_index:06d}-{pilot}",
                    seed=match_seed,
                    deck_ids=(deck_id, *selected),
                    starting_player_seat=start,
                    pilot_configs=(controlled, *(opponent_config for _ in selected)),
                    limits=StructuralAbortLimits(max_turns=max_turns),
                ),
                run_id="phase12.15-structural-policy-tournament",
                capture_events=False,
            )
            own = next(m for m in match.player_metrics.values() if m.deck_id == deck_id)
            rows.append(
                {
                    "deck_id": deck_id,
                    "pilot": pilot,
                    "politics": politics,
                    "pod_size": pod_size,
                    "scenario_index": scenario_index,
                    "iteration": iteration,
                    "match_seed": match_seed,
                    "opponent_variants": selected,
                    "completed": bool(match.completed),
                    "aborted": bool(match.aborted),
                    "placement": int(own.placement),
                    "place_1": own.placement == 1,
                    "archenemy": bool(own.was_archenemy),
                    "commander_casts": int(own.commander_casts),
                    "cards_drawn": int(own.cards_drawn),
                    "utility": -float(own.placement),
                }
            )
    return rows


def run_structural_policy_tournament(
    root: str | Path,
    *,
    config: PolicyTournamentConfig = PolicyTournamentConfig(),
    deck_ids: tuple[str, ...] = ("rogshai/current",),
    pilot_profiles: tuple[str, ...] = PILOT_PROFILES,
    politics_regimes: tuple[str, ...] = POLITICS_REGIMES,
) -> dict[str, Any]:
    """Execute real Structural Simulator games for the policy/uncertainty matrix.

    Common random numbers are used within each scenario context: all pilot policies see
    the same deck ensemble, start seat and match seed. Opponent uncertainty is expressed
    only by role-strength perturbations of known structural profiles; no unknown card name
    is fabricated or promoted to confirmed data.
    """
    if config.iterations_per_scenario < 1:
        raise ValueError("iterations_per_scenario must be at least 1")
    if not set(pilot_profiles) <= set(PILOT_PROFILES):
        raise ValueError("unknown pilot profile requested")
    if not set(politics_regimes) <= set(POLITICS_REGIMES):
        raise ValueError("unknown politics regime requested")
    root = Path(root)
    decks = load_project_structural_decks(root, include_current_opponents=True)
    registry = build_registry(root)
    variants_by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for variant in registry["opponent_variants"]:
        base_id = str(variant["deck_id"])
        if base_id in decks:
            variants_by_base[base_id].append(variant)
    opponent_bases = sorted(variants_by_base)
    tasks: list[dict[str, Any]] = []
    scenario_index = 0
    for deck_id in deck_ids:
        if deck_id not in decks:
            raise KeyError(f"unknown structural deck: {deck_id}")
        for politics in politics_regimes:
            for pod_size in config.pod_sizes:
                needed = pod_size - 1
                if needed > len(opponent_bases):
                    raise ValueError(
                        f"not enough distinct opponent profiles for pod size {pod_size}"
                    )
                for iteration in range(config.iterations_per_scenario):
                    order = sorted(
                        opponent_bases,
                        key=lambda d: _hash_int(
                            config.seed, deck_id, politics, pod_size, iteration, d
                        ),
                    )
                    selected: list[str] = []
                    for base_id in order[:needed]:
                        options = sorted(
                            variants_by_base[base_id], key=lambda row: str(row["variant_id"])
                        )
                        option = options[
                            _hash_int(config.seed, deck_id, politics, pod_size, iteration, base_id)
                            % len(options)
                        ]
                        selected.append(str(option["variant_id"]))
                    match_seed = _hash_int(config.seed, deck_id, politics, pod_size, iteration) % (
                        2**63 - 1
                    )
                    tasks.append(
                        {
                            "deck_id": deck_id,
                            "politics": politics,
                            "pod_size": pod_size,
                            "scenario_index": scenario_index,
                            "iteration": iteration,
                            "selected": selected,
                            "match_seed": match_seed,
                            "start": scenario_index % pod_size,
                        }
                    )
                    scenario_index += 1
    workers = max(1, min(int(config.workers), len(tasks) or 1))
    if workers == 1:
        rows = _policy_worker((str(root.resolve()), tasks, tuple(pilot_profiles), config.max_turns))
    else:
        chunks = [tasks[index::workers] for index in range(workers)]
        payloads = [
            (str(root.resolve()), chunk, tuple(pilot_profiles), config.max_turns)
            for chunk in chunks
            if chunk
        ]
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            rows = [row for part in executor.map(_policy_worker, payloads) for row in part]
    pilot_order = {name: index for index, name in enumerate(pilot_profiles)}
    rows.sort(key=lambda row: (int(row["scenario_index"]), pilot_order[str(row["pilot"])]))
    summaries = []
    for pilot in pilot_profiles:
        values = [r for r in rows if r["pilot"] == pilot]
        utilities = sorted(float(r["utility"]) for r in values)
        summaries.append(
            {
                "pilot": pilot,
                "games": len(values),
                "average_placement": round(fmean(float(r["placement"]) for r in values), 6),
                "place_1_share": round(fmean(1.0 if r["place_1"] else 0.0 for r in values), 6),
                "archenemy_share": round(fmean(1.0 if r["archenemy"] else 0.0 for r in values), 6),
                "mean_utility": round(fmean(utilities), 6),
                "worst_case_utility": min(utilities),
                "q10_utility": utilities[max(0, math.ceil(len(utilities) * 0.10) - 1)],
            }
        )
    rankings = sorted(
        summaries, key=lambda r: (r["worst_case_utility"], r["mean_utility"]), reverse=True
    )
    context_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        context_groups[
            (row["deck_id"], row["politics"], row["pod_size"], row["scenario_index"])
        ].append(row)
    best_responses = []
    for context, group in sorted(context_groups.items(), key=lambda item: str(item[0])):
        best = min(group, key=lambda r: (r["placement"], -r["cards_drawn"], r["pilot"]))
        best_responses.append(
            {
                "deck_id": context[0],
                "politics": context[1],
                "pod_size": context[2],
                "scenario_index": context[3],
                "pilot": best["pilot"],
                "placement": best["placement"],
            }
        )
    mw_rows = rows if tuple(pilot_profiles) == tuple(PILOT_PROFILES) else []
    regret = _multiplicative_weights(mw_rows, config.rounds, config.seed, value_key="utility")
    return {
        "schema_version": 1,
        "validation_level": "structural_only",
        "estimate_type": "structural_model_estimates",
        "execution_status": "passed",
        "self_play_status": "structural_policy_tournament_executed",
        "hidden_information_access": False,
        "empirical_weights_used": False,
        "unknown_cards_invented": False,
        "common_random_numbers": True,
        "config": {
            "seed": config.seed,
            "rounds": config.rounds,
            "pod_sizes": list(config.pod_sizes),
            "iterations_per_scenario": config.iterations_per_scenario,
            "max_turns": config.max_turns,
            "workers": config.workers,
        },
        "scenario_count": scenario_index,
        "game_count": len(rows),
        "rankings": rankings,
        "best_response": best_responses,
        "adversarial_worst_case": rankings[0] if rankings else None,
        "regret_minimization": regret,
        "rows": rows,
    }


def build_registry(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    profiles = json.loads(
        (root / "data/opponents/current_structural_profiles.json").read_text(encoding="utf-8")
    )["profiles"]
    variants: list[dict[str, Any]] = []
    for p in profiles:
        quality = p.get("data_quality", "project_inferred")
        base_pressure = min(
            1.0,
            (sum(float(v) for v in p.get("roles", {}).values()) / max(1, len(p.get("roles", {}))))
            / 15.0,
        )
        status = p.get("source_status")
        bands: tuple[tuple[str, float], ...]
        if status in {
            "partially_known",
            "synthetic_completion",
            "official_precon_plus_unknown_upgrades",
        } or p.get("upgrade_slots_unknown", False):
            bands = (("best_case", -0.15), ("median", 0.0), ("worst_case", 0.18))
        else:
            bands = (("fixed_reference", 0.0),)
        for label, delta in bands:
            variants.append(
                {
                    "variant_id": f"{p['deck_id'].replace('/', '-')}-{label}",
                    "deck_id": p["deck_id"],
                    "commander": p["commander"],
                    "variant_kind": label,
                    "pressure": round(max(0.05, min(1.0, base_pressure + delta)), 4),
                    "source_status": status,
                    "data_quality": quality,
                    "confirmed_card_count": p.get("confirmed_card_count"),
                    "unknown_slot_count": p.get("unknown_slot_count"),
                    "baseline_precon_cards": p.get("baseline_precon_cards"),
                    "upgrade_slots_unknown": bool(p.get("upgrade_slots_unknown", False)),
                    "assumed_cards_confirmed": False,
                    "unknown_slots_remain_unknown": True,
                    "uncertainty": p.get("uncertainty", []),
                }
            )
    return {
        "schema_version": 2,
        "validation_level": "structural_only",
        "pilot_profiles": [
            {
                "pilot_id": name,
                "utility_weights": (
                    weights.model_dump(mode="json")
                    if (weights := pilot_config_for(name, "rational_threat_focus").weights)
                    is not None
                    else {}
                ),
                "hidden_information_access": False,
                "empirical_fit": False,
            }
            for name in PILOT_PROFILES
        ],
        "politics_regimes": [
            {
                "regime_id": name,
                "scenario_axis_only": True,
                "predicted_truth": False,
                "empirical_fit": False,
            }
            for name in POLITICS_REGIMES
        ],
        "opponent_variants": variants,
    }


def run_structural_self_play(
    root: str | Path,
    *,
    seed: int = 20260807,
    deck_ids: tuple[str, ...] = ("rogshai/current",),
    pilot_profiles: tuple[str, ...] = PILOT_PROFILES,
    politics: str = "rational_threat_focus",
    pod_sizes: tuple[int, ...] = (4,),
    max_turns: int = 20,
) -> dict[str, Any]:
    """Run actual Structural Simulator self-play with one policy profile on every seat.

    This is behavioural policy self-play, not mirror-deck play: each seat keeps its own
    strategy-specific deck/pilot implementation while sharing the same visible-state
    utility profile. Unknown opponent cards are never fabricated.
    """
    if pod_sizes != (4,):
        raise ValueError(
            "Operational Commander Playtest Lab self-play is 4-player only; "
            "3P/5P pod sensitivity is out of project scope."
        )
    if politics not in POLITICS_REGIMES:
        raise KeyError(f"unknown politics regime: {politics}")
    if not set(pilot_profiles) <= set(PILOT_PROFILES):
        raise ValueError("unknown pilot profile requested")
    root_path = Path(root)
    decks = load_project_structural_decks(root_path, include_current_opponents=True)
    registry = build_registry(root_path)
    variants_by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    variant_decks: dict[str, StructuralDeckProfile] = {}
    for variant in registry["opponent_variants"]:
        base_id = str(variant["deck_id"])
        if base_id not in decks:
            continue
        variants_by_base[base_id].append(variant)
        variant_decks[str(variant["variant_id"])] = _variant_deck(decks[base_id], variant)
    all_decks = dict(decks)
    all_decks.update(variant_decks)
    simulator = StructuralSimulator(all_decks)
    opponent_bases = sorted(variants_by_base)
    rows: list[dict[str, Any]] = []
    scenario_index = 0
    for deck_id in deck_ids:
        if deck_id not in decks:
            raise KeyError(f"unknown structural deck: {deck_id}")
        for pod_size in pod_sizes:
            needed = pod_size - 1
            if needed > len(opponent_bases):
                raise ValueError(f"not enough distinct opponent profiles for pod size {pod_size}")
            order = sorted(
                opponent_bases,
                key=lambda item: _hash_int(seed, "self-play", deck_id, pod_size, item),
            )
            selected: list[str] = []
            for base_id in order[:needed]:
                options = sorted(
                    variants_by_base[base_id],
                    key=lambda row: (row["variant_kind"] != "median", row["variant_id"]),
                )
                selected.append(str(options[0]["variant_id"]))
            match_seed = _hash_int(seed, "self-play", deck_id, pod_size) % (2**63 - 1)
            for profile in pilot_profiles:
                config = pilot_config_for(profile, politics)
                match = simulator.simulate(
                    StructuralMatchConfig(
                        match_id=f"phase1215-selfplay-{scenario_index:03d}-{profile}",
                        seed=match_seed,
                        deck_ids=(deck_id, *selected),
                        starting_player_seat=scenario_index % pod_size,
                        pilot_configs=tuple(config for _ in range(pod_size)),
                        limits=StructuralAbortLimits(max_turns=max_turns),
                    ),
                    run_id="phase12.15-structural-self-play",
                    capture_events=False,
                )
                own = next(
                    metric for metric in match.player_metrics.values() if metric.deck_id == deck_id
                )
                rows.append(
                    {
                        "deck_id": deck_id,
                        "pilot": profile,
                        "politics": politics,
                        "pod_size": pod_size,
                        "scenario_index": scenario_index,
                        "match_seed": match_seed,
                        "opponent_variants": selected,
                        "all_seats_same_policy_profile": True,
                        "completed": bool(match.completed),
                        "aborted": bool(match.aborted),
                        "placement": int(own.placement),
                        "place_1": own.placement == 1,
                    }
                )
            scenario_index += 1
    summaries = []
    for profile in pilot_profiles:
        group = [row for row in rows if row["pilot"] == profile]
        summaries.append(
            {
                "pilot": profile,
                "games": len(group),
                "average_placement": round(fmean(float(row["placement"]) for row in group), 6),
                "place_1_share": round(fmean(1.0 if row["place_1"] else 0.0 for row in group), 6),
            }
        )
    return {
        "schema_version": 1,
        "execution_status": "passed",
        "validation_level": "structural_only",
        "estimate_type": "structural_model_estimates",
        "self_play_status": "structural_same_policy_all_seats_executed",
        "game_count": len(rows),
        "scenario_count": scenario_index,
        "common_random_numbers_across_profiles": True,
        "hidden_information_access": False,
        "empirical_weights_used": False,
        "unknown_cards_invented": False,
        "rows": rows,
        "summaries": sorted(
            summaries,
            key=lambda row: (row["average_placement"], -row["place_1_share"], row["pilot"]),
        ),
    }
