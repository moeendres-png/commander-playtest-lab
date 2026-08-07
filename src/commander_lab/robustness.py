from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PILOT_PROFILES = (
    "weak", "average", "strong", "near_optimal_heuristic", "aggressive",
    "conservative", "interaction_holding", "commander_focused", "engine_focused",
    "anti_leader", "anti_combo", "rebuild_focused", "tempo_focused",
    "politically_low_visibility", "politically_aggressive", "adversarial_worst_case",
)

POLITICS_REGIMES = (
    "rational_threat_focus", "current_leader_focus", "commander_reputation_focus",
    "combo_prevention", "revenge_bias", "random_targeting_noise",
    "open_mana_deterrence", "visible_engine_focus", "low_visibility_tolerance",
    "table_balance",
)

# Dimensions are synthetic policy parameters, not learned local weights.
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


@dataclass(frozen=True)
class PolicyTournamentConfig:
    seed: int = 20260807
    rounds: int = 128
    pod_sizes: tuple[int, ...] = (3, 4, 5)


def _hash_float(*parts: object) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def policy_score(pilot: str, politics: str, pod_size: int, opponent_pressure: float, *, seed: int) -> float:
    """Synthetic, visible-information-only utility score.

    Dimensions: pressure, interaction, engine, rebuild, low visibility. The score is
    a structural scenario result, never an empirical win probability.
    """
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


def run_policy_tournament(
    opponent_variants: Iterable[dict[str, Any]],
    config: PolicyTournamentConfig = PolicyTournamentConfig(),
) -> dict[str, Any]:
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
                    rows.append({
                        "pilot": pilot,
                        "politics": politics,
                        "pod_size": pod_size,
                        "opponent_variant": variant["variant_id"],
                        "score": score,
                    })
        ordered = sorted(values)
        summary = {
            "pilot": pilot,
            "mean_score": round(sum(values) / len(values), 6),
            "worst_case_score": ordered[0],
            "q10_score": ordered[max(0, math.ceil(len(ordered) * 0.10) - 1)],
            "scenario_count": len(values),
        }
        rows.append({"summary": summary})

    summaries = [r["summary"] for r in rows if "summary" in r]
    # Multiplicative-weights regret minimization over policy choices. This is a
    # bounded synthetic policy search, not hidden-information game solving.
    weights = {name: 1.0 for name in PILOT_PROFILES}
    eta = 0.08
    rng = random.Random(config.seed)
    regret_trace: list[dict[str, Any]] = []
    scenarios = [r for r in rows if "score" in r]
    for round_index in range(config.rounds):
        scenario = scenarios[rng.randrange(len(scenarios))]
        same = [r for r in scenarios if r["politics"] == scenario["politics"] and r["pod_size"] == scenario["pod_size"] and r["opponent_variant"] == scenario["opponent_variant"]]
        max_score = max(r["score"] for r in same)
        for row in same:
            loss = max_score - row["score"]
            weights[row["pilot"]] *= math.exp(-eta * loss)
        total = sum(weights.values())
        for key in weights:
            weights[key] /= total
        if round_index in {0, config.rounds - 1}:
            regret_trace.append({"round": round_index + 1, "weights": dict(sorted(weights.items()))})

    rankings = sorted(summaries, key=lambda x: (x["worst_case_score"], x["mean_score"]), reverse=True)
    return {
        "schema_version": 1,
        "validation_level": "structural_only",
        "estimate_type": "synthetic_policy_tournament",
        "hidden_information_access": False,
        "empirical_weights_used": False,
        "config": {"seed": config.seed, "rounds": config.rounds, "pod_sizes": config.pod_sizes},
        "rankings": rankings,
        "regret_minimization": {"method": "multiplicative_weights", "final_weights": dict(sorted(weights.items())), "trace": regret_trace},
        "scenario_rows": [r for r in rows if "score" in r],
    }


def build_registry(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    profiles = json.loads((root / "data/opponents/current_structural_profiles.json").read_text())["profiles"]
    variants: list[dict[str, Any]] = []
    for p in profiles:
        quality = p.get("data_quality", "project_inferred")
        base_pressure = min(1.0, (sum(float(v) for v in p.get("roles", {}).values()) / max(1, len(p.get("roles", {})))) / 15.0)
        if p.get("source_status") in {"partially_known", "synthetic_completion"}:
            bands = (("best_case", -0.15), ("median", 0.0), ("worst_case", 0.18))
        else:
            bands = (("fixed_reference", 0.0),)
        for label, delta in bands:
            variants.append({
                "variant_id": f"{p['deck_id'].replace('/', '-')}-{label}",
                "deck_id": p["deck_id"],
                "commander": p["commander"],
                "variant_kind": label,
                "pressure": round(max(0.05, min(1.0, base_pressure + delta)), 4),
                "source_status": p.get("source_status"),
                "data_quality": quality,
                "assumed_cards_confirmed": False,
                "unknown_slots_remain_unknown": True,
                "uncertainty": p.get("uncertainty", []),
            })
    return {
        "schema_version": 1,
        "validation_level": "structural_only",
        "pilot_profiles": [
            {"pilot_id": name, "dimensions": {"pressure": _BASE[name][0], "interaction": _BASE[name][1], "engine": _BASE[name][2], "rebuild": _BASE[name][3], "low_visibility": _BASE[name][4]}, "hidden_information_access": False}
            for name in PILOT_PROFILES
        ],
        "politics_regimes": [
            {"regime_id": name, "scenario_axis_only": True, "predicted_truth": False}
            for name in POLITICS_REGIMES
        ],
        "opponent_variants": variants,
    }
