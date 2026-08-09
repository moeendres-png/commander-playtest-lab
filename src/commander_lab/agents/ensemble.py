from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median
from typing import Any, Iterable

from commander_lab.engine.structural import run_structural_batch
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotEnsembleDefinition,
    PilotEnsembleMember,
    PilotInformationPolicy,
    PilotProfile,
    PilotStrength,
    StructuralAbortLimits,
    StructuralBatchConfig,
    StructuralDeckProfile,
)
from commander_lab.storage import atomic_write_json

from .pilots import build_pilot

ESTIMATE_TYPE = "structural_model_estimates"
REGISTRY_SCHEMA_VERSION = "1.0.0"


def _canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _profile(
    pilot_name: str,
    family: str,
    deck_hash: str,
    source_rules: tuple[str, ...],
    description: str,
    *,
    baseline: bool = False,
) -> PilotProfile:
    pilot = build_pilot(
        PilotConfig(pilot_name=pilot_name, strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC),
        strategy=family,
    )
    body = {
        "pilot_name": pilot_name,
        "commander_family": family,
        "version": "1.0.0",
        "source_rule_ids": source_rules,
        "weights": pilot.weights.model_dump(mode="json"),
        "mode": PilotDecisionMode.DETERMINISTIC.value,
        "allowed_deviation": 0.25 if not baseline else 0.0,
        "supported_deck_hashes": [deck_hash],
        "information_policy": PilotInformationPolicy().model_dump(mode="json"),
        "description": description,
        "is_baseline": baseline,
    }
    return PilotProfile.model_validate(
        {
            "profile_id": f"{family}.{pilot_name.casefold()}.v1",
            "parameter_hash": _canonical_hash(body),
            **body,
        }
    )


def default_pilot_profiles() -> tuple[PilotProfile, ...]:
    korvold_hash = "72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f"
    rogshai_hash = "3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932"
    return (
        _profile("KorvoldPilot", "korvold", korvold_hash, ("korvold.current.commander-immediate-value",), "Phase-12.2 baseline Korvold pilot.", baseline=True),
        _profile("KorvoldValuePilot", "korvold", korvold_hash, ("korvold.current.commander-immediate-value", "korvold.current.motor-vs-finisher"), "Maximizes independent value and card advantage."),
        _profile("KorvoldSacrificePilot", "korvold", korvold_hash, ("korvold.current.prepare-sacrifice-resources",), "Prioritizes sacrifice outlets and renewable material."),
        _profile("KorvoldLandRebuildPilot", "korvold", korvold_hash, ("korvold.current.graveyard-hate-risk", "korvold.current.rebuild-after-wipe"), "Preserves and converts land/graveyard rebuild lines."),
        _profile("KorvoldAggressivePilot", "korvold", korvold_hash, ("korvold.current.table-damage-window",), "Accepts visibility to advance table damage and commander pressure."),
        _profile("KorvoldConservativePilot", "korvold", korvold_hash, ("korvold.current.commander-immediate-value", "korvold.current.rebuild-after-wipe"), "Reserves protection and minimizes exposed commander casts."),
        _profile("RogShaiPilot", "rogshai", rogshai_hash, ("rogshai.current.ishai-protection-window",), "Phase-12.2 baseline RogShai pilot.", baseline=True),
        _profile("RogShaiTempoPilot", "rogshai", rogshai_hash, ("rogshai.current.ishai-protection-window", "rogshai.current.counter-priority"), "Develops Ishai while preserving cheap tempo interaction."),
        _profile("RogShaiVoltronPilot", "rogshai", rogshai_hash, ("rogshai.current.aura-exposure", "rogshai.current.kediss-not-commander-damage"), "Concentrates on combat draw and commander-damage pressure."),
        _profile("RogShaiSpellslingerPilot", "rogshai", rogshai_hash, ("rogshai.current.independent-spellslinger-axis",), "Builds independent Kykar/Veyran/Storm-Kiln/Guttersnipe axes."),
        _profile("RogShaiControlPilot", "rogshai", rogshai_hash, ("rogshai.current.counter-priority",), "Reserves interaction for engines and real win attempts."),
        _profile("RogShaiProtectedFinishPilot", "rogshai", rogshai_hash, ("rogshai.current.jeska-finish-window", "rogshai.current.silence-window"), "Waits for protected Jeska, double-strike or Silence finish windows."),
    )


def default_ensembles() -> tuple[PilotEnsembleDefinition, ...]:
    korvold = (
        "KorvoldValuePilot", "KorvoldSacrificePilot", "KorvoldLandRebuildPilot",
        "KorvoldAggressivePilot", "KorvoldConservativePilot",
    )
    rogshai = (
        "RogShaiTempoPilot", "RogShaiVoltronPilot", "RogShaiSpellslingerPilot",
        "RogShaiControlPilot", "RogShaiProtectedFinishPilot",
    )
    return (
        PilotEnsembleDefinition(
            ensemble_id="korvold.equal.v1", version="1.0.0", deck_id="korvold/current",
            members=tuple(PilotEnsembleMember(pilot_name=name, weight=0.2) for name in korvold),
        ),
        PilotEnsembleDefinition(
            ensemble_id="rogshai.equal.v1", version="1.0.0", deck_id="rogshai/current",
            members=tuple(PilotEnsembleMember(pilot_name=name, weight=0.2) for name in rogshai),
        ),
    )


class PilotRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.registry_path = self.root / "data/pilots/pilot_registry.json"
        self.ensemble_path = self.root / "config/pilot_ensembles.json"

    def profiles(self) -> tuple[PilotProfile, ...]:
        if not self.registry_path.exists():
            return default_pilot_profiles()
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return tuple(PilotProfile.model_validate(row) for row in payload["profiles"])

    def ensembles(self) -> tuple[PilotEnsembleDefinition, ...]:
        if not self.ensemble_path.exists():
            return default_ensembles()
        payload = json.loads(self.ensemble_path.read_text(encoding="utf-8"))
        return tuple(PilotEnsembleDefinition.model_validate(row) for row in payload["ensembles"])

    def profile(self, pilot_name: str) -> PilotProfile:
        for profile in self.profiles():
            if profile.pilot_name.casefold() == pilot_name.casefold():
                return profile
        raise KeyError(f"unknown pilot profile: {pilot_name}")

    def ensemble(self, ensemble_id: str) -> PilotEnsembleDefinition:
        for ensemble in self.ensembles():
            if ensemble.ensemble_id == ensemble_id:
                return ensemble
        raise KeyError(f"unknown pilot ensemble: {ensemble_id}")

    def write_defaults(self) -> None:
        atomic_write_json(self.registry_path, {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "estimate_type": ESTIMATE_TYPE,
            "profiles": [p.model_dump(mode="json") for p in default_pilot_profiles()],
            "truth_boundaries": {
                "legal_actions_only": True,
                "hidden_information_access": False,
                "automatic_deck_changes": False,
            },
        })
        atomic_write_json(self.ensemble_path, {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "ensembles": [e.model_dump(mode="json") for e in default_ensembles()],
        })


class PilotEnsembleRunner:
    def __init__(self, root: str | Path, decks: dict[str, StructuralDeckProfile]) -> None:
        self.root = Path(root).resolve()
        self.decks = decks
        self.registry = PilotRegistry(self.root)

    def _validate_profile_scope(self, profile: PilotProfile, deck: StructuralDeckProfile) -> None:
        if profile.supported_deck_hashes and deck.deck_hash not in profile.supported_deck_hashes:
            raise ValueError(f"pilot {profile.pilot_name} does not support deck hash {deck.deck_hash}")
        policy = profile.information_policy
        if policy.hidden_opponent_hands or policy.random_library_order or policy.exact_future_draws:
            raise ValueError("omniscient pilot profile rejected")

    def benchmark(
        self,
        *,
        deck_id: str,
        pilot_names: Iterable[str],
        opponent_deck_ids: tuple[str, ...],
        iterations: int,
        seed: int,
        max_turns: int = 24,
        output_name: str | None = None,
    ) -> dict[str, Any]:
        deck = self.decks[deck_id]
        names = tuple(pilot_names)
        if not names:
            names = tuple(p.pilot_name for p in self.registry.profiles() if p.commander_family == deck.commander_strategy)
        results: dict[str, dict[str, Any]] = {}
        output_root = self.root / "data/runs/pilot_ensembles" / (output_name or f"benchmark-{deck_id.replace('/', '-')}-{seed}")
        for index, name in enumerate(names):
            profile = self.registry.profile(name)
            self._validate_profile_scope(profile, deck)
            run_dir = output_root / name
            configs = (
                PilotConfig(
                    pilot_name=name,
                    strength=PilotStrength.STRONG,
                    mode=profile.mode,
                    weights=profile.weights,
                    profile_version=profile.version,
                    parameter_hash=profile.parameter_hash,
                    source_rule_ids=profile.source_rule_ids,
                    allowed_deviation=profile.allowed_deviation,
                    supported_deck_hashes=profile.supported_deck_hashes,
                    information_policy=profile.information_policy,
                ),
                *(PilotConfig() for _ in opponent_deck_ids),
            )
            batch = run_structural_batch(
                StructuralBatchConfig(
                    run_id=f"pilot-benchmark-{name.casefold()}-{seed}",
                    seed=seed,
                    iterations=iterations,
                    deck_ids=(deck_id, *opponent_deck_ids),
                    workers=1,
                    pilot_configs=configs,
                    limits=StructuralAbortLimits(max_turns=max_turns),
                    output_directory=str(run_dir),
                ),
                self.decks,
            )
            rows = [
                metrics for match in batch.match_results for metrics in match.player_metrics.values()
                if metrics.deck_id == deck_id and metrics.pilot_name == name
            ]
            if not rows:
                raise RuntimeError(f"no structural metrics returned for pilot {name}")
            decision = self._decision_summary(run_dir, name)
            results[name] = {
                "profile": profile.model_dump(mode="json"),
                "games": len(rows),
                "average_placement": fmean(float(row.placement) for row in rows),
                "place_1_share": fmean(1.0 if row.placement == 1 else 0.0 for row in rows),
                "average_first_commander_cast_turn": self._nullable_mean(row.first_commander_cast_turn for row in rows),
                "average_commander_casts": fmean(float(row.commander_casts) for row in rows),
                "average_commander_damage": fmean(float(row.commander_damage_dealt) for row in rows),
                "average_normal_damage": fmean(float(row.normal_damage_dealt) for row in rows),
                "average_counters": fmean(float(row.counters_resolved) for row in rows),
                "average_protections": fmean(float(row.protections_resolved) for row in rows),
                "average_wipes": fmean(float(row.wipes_resolved) for row in rows),
                "average_recursions": fmean(float(row.recursions_resolved) for row in rows),
                "average_engine_value": fmean(float(row.engine_value) for row in rows),
                "political_visibility": fmean((1.0 if row.was_archenemy else 0.0) + row.hostile_target_events / 20.0 for row in rows),
                "interaction_usage": {
                    "average_counters": fmean(float(row.counters_resolved) for row in rows),
                    "average_protections": fmean(float(row.protections_resolved) for row in rows),
                    "average_removals": fmean(float(row.removals_resolved) for row in rows),
                    "average_wipes": fmean(float(row.wipes_resolved) for row in rows),
                },
                "win_axes": self._win_axes(rows),
                "errors": [],
                "aborted_games": batch.aborted_games,
                "decision_summary": decision,
                "estimate_type": ESTIMATE_TYPE,
            }
        self._add_baseline_deviations(results, deck.commander_strategy)
        payload = {
            "schema_version": "1.0.0",
            "deck_id": deck_id,
            "deck_hash": deck.deck_hash,
            "opponent_deck_ids": opponent_deck_ids,
            "iterations_per_pilot": iterations,
            "seed": seed,
            "estimate_type": ESTIMATE_TYPE,
            "results": results,
            "legal_actions_only": True,
            "omniscient_information_used": False,
            "automatic_deck_changes": False,
        }
        atomic_write_json(output_root / "pilot_benchmark.json", payload)
        return payload

    def ensemble_summary(self, benchmark: dict[str, Any], ensemble: PilotEnsembleDefinition) -> dict[str, Any]:
        rows = benchmark["results"]
        selected = [(member, rows[member.pilot_name]) for member in ensemble.members]
        metrics = ("average_placement", "place_1_share", "average_commander_damage", "average_normal_damage", "average_engine_value", "political_visibility")
        weighted = {
            metric: sum(member.weight * float(row[metric]) for member, row in selected)
            for metric in metrics
        }
        ordered = sorted(selected, key=lambda item: float(item[1]["average_placement"]))
        worst_member, worst_row = max(selected, key=lambda item: float(item[1]["average_placement"]))
        median_member, median_row = ordered[len(ordered) // 2]
        placement_spread = max(float(row["average_placement"]) for _, row in selected) - min(float(row["average_placement"]) for _, row in selected)
        return {
            "ensemble": ensemble.model_dump(mode="json"),
            "weighted_metrics": weighted,
            "worst_pilot": {"pilot_name": worst_member.pilot_name, "average_placement": worst_row["average_placement"]},
            "median_pilot": {"pilot_name": median_member.pilot_name, "average_placement": median_row["average_placement"]},
            "pilot_robustness": {
                "placement_spread": placement_spread,
                "robust": placement_spread <= 0.75,
                "criterion": "structural placement spread <= 0.75 across the ensemble",
            },
            "deck_pilot_interaction": {
                name: row["deviation_from_baseline"] for name, row in rows.items()
                if any(member.pilot_name == name for member in ensemble.members)
            },
            "estimate_type": ESTIMATE_TYPE,
            "automatic_deck_changes": False,
        }

    @staticmethod
    def compare(benchmark: dict[str, Any], pilot_names: tuple[str, ...]) -> dict[str, Any]:
        rows = benchmark["results"]
        return {
            "deck_id": benchmark["deck_id"],
            "pilots": {name: rows[name] for name in pilot_names},
            "pairwise": [
                {
                    "left": left,
                    "right": right,
                    "average_placement_delta_left_minus_right": float(rows[left]["average_placement"]) - float(rows[right]["average_placement"]),
                    "win_share_delta_left_minus_right": float(rows[left]["place_1_share"]) - float(rows[right]["place_1_share"]),
                }
                for index, left in enumerate(pilot_names) for right in pilot_names[index + 1:]
            ],
            "estimate_type": ESTIMATE_TYPE,
        }

    @staticmethod
    def variant_robustness(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        shared = sorted(set(baseline["results"]) & set(variant["results"]))
        rows = []
        for name in shared:
            before = baseline["results"][name]
            after = variant["results"][name]
            rows.append({
                "pilot_name": name,
                "placement_improvement": float(before["average_placement"]) - float(after["average_placement"]),
                "win_share_improvement": float(after["place_1_share"]) - float(before["place_1_share"]),
            })
        placement = [row["placement_improvement"] for row in rows]
        return {
            "pilots": rows,
            "median_placement_improvement": median(placement) if placement else 0.0,
            "worst_pilot_placement_improvement": min(placement) if placement else 0.0,
            "robust": bool(placement) and median(placement) > 0 and min(placement) >= -0.05,
            "criterion": "median improvement > 0 and no pilot worse than -0.05 placement",
            "estimate_type": ESTIMATE_TYPE,
            "automatic_deck_changes": False,
        }

    @staticmethod
    def markdown_report(payload: dict[str, Any]) -> str:
        lines = ["# Pilot Robustness Report", "", f"Estimate type: `{ESTIMATE_TYPE}`", ""]
        if "weighted_metrics" in payload:
            lines += ["## Ensemble", "", f"- Worst pilot: `{payload['worst_pilot']['pilot_name']}`", f"- Median pilot: `{payload['median_pilot']['pilot_name']}`", f"- Robust: `{payload['pilot_robustness']['robust']}`", ""]
        elif "pilots" in payload:
            lines += ["## Variant across pilots", "", f"- Median placement improvement: `{payload['median_placement_improvement']:.4f}`", f"- Worst-pilot improvement: `{payload['worst_pilot_placement_improvement']:.4f}`", f"- Robust: `{payload['robust']}`", ""]
        lines += ["All values are Structural Estimates. No deck change is applied automatically.", ""]
        return "\n".join(lines)

    @staticmethod
    def _nullable_mean(values: Iterable[int | None]) -> float | None:
        present = [float(value) for value in values if value is not None]
        return fmean(present) if present else None

    @staticmethod
    def _decision_summary(run_dir: Path, pilot_name: str) -> dict[str, Any]:
        phase_counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        components: dict[str, list[float]] = defaultdict(list)
        total = 0
        for path in sorted((run_dir / "events").glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event_type") != "pilot_decision":
                    continue
                payload = event.get("payload", {})
                if payload.get("pilot_name") != pilot_name:
                    continue
                total += 1
                phase_counts[str(payload.get("phase", "unknown"))] += 1
                action_counts[str(payload.get("selected_action_id", "none"))] += 1
                breakdown = payload.get("breakdown") or {}
                for key, value in breakdown.items():
                    if isinstance(value, (int, float)):
                        components[key].append(float(value))
        return {
            "decision_count": total,
            "trigger_phases": dict(phase_counts.most_common()),
            "selected_actions": dict(action_counts.most_common(20)),
            "average_utility_decomposition": {key: fmean(values) for key, values in sorted(components.items()) if values},
        }

    @staticmethod
    def _win_axes(rows: list[Any]) -> list[dict[str, float | str]]:
        axes = {
            "commander_damage": fmean(float(row.commander_damage_dealt) for row in rows),
            "normal_damage": fmean(float(row.normal_damage_dealt) for row in rows),
            "engine_value": fmean(float(row.engine_value) for row in rows),
            "rebuild_recursion": fmean(float(row.recursions_resolved) for row in rows),
        }
        return [
            {"axis": name, "structural_signal": value}
            for name, value in sorted(axes.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def _add_baseline_deviations(results: dict[str, dict[str, Any]], family: str) -> None:
        baseline_name = "KorvoldPilot" if family == "korvold" else "RogShaiPilot"
        baseline = results.get(baseline_name)
        if baseline is None:
            return
        for row in results.values():
            row["deviation_from_baseline"] = {
                "average_placement": float(row["average_placement"]) - float(baseline["average_placement"]),
                "place_1_share": float(row["place_1_share"]) - float(baseline["place_1_share"]),
                "commander_damage": float(row["average_commander_damage"]) - float(baseline["average_commander_damage"]),
                "engine_value": float(row["average_engine_value"]) - float(baseline["average_engine_value"]),
                "political_visibility": float(row["political_visibility"]) - float(baseline["political_visibility"]),
            }
