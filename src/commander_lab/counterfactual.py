from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable
from pathlib import Path
from statistics import fmean, median, pvariance
from typing import Any

from commander_lab.engine.rules.tactical import TacticalRuleError, TacticalRuleOracle
from commander_lab.models.counterfactual import (
    CounterfactualAction,
    CounterfactualBranchpoint,
    CounterfactualComparison,
    CounterfactualEngineMode,
    CounterfactualFutureSample,
    CounterfactualResult,
    CounterfactualStateDiff,
    DecisionRegretRecord,
    HiddenInformationPolicy,
    SeedPolicy,
)
from commander_lab.storage import atomic_write_json, atomic_write_text, sha256_value


class CounterfactualError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CounterfactualError(f"invalid JSONL at line {line_number}") from exc
            if not isinstance(value, dict):
                raise CounterfactualError(f"event at line {line_number} must be an object")
            rows.append(value)
    return rows


def _prefix_hash(rows: list[dict[str, Any]], offset: int) -> str:
    return sha256_value(rows[: offset + 1])


def _state_proxy(rows: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    event = rows[offset]
    checkpoint = next(
        (
            row
            for row in reversed(rows[: offset + 1])
            if row.get("event_type") == "state_checkpoint"
        ),
        None,
    )
    return {
        "game_id": event.get("game_id"),
        "event_offset": offset,
        "event_sequence": event.get("sequence", offset),
        "actor_id": event.get("actor_id"),
        "phase": event.get("payload", {}).get("phase"),
        "last_public_checkpoint": checkpoint,
        "public_event_prefix_hash": _prefix_hash(rows, offset),
    }


def _action_kind(action_id: str, phase: str | None) -> str:
    lowered = action_id.lower()
    if action_id == "pass":
        return "pass_priority"
    if phase == "counter":
        return "counter_or_hold"
    if phase in {"removal_target", "graveyard_target"}:
        return "target_selection"
    if phase == "combat":
        return "attack_target"
    if "mulligan" in lowered or "bottom" in lowered:
        return "mulligan_or_bottom"
    if "commander" in lowered or "ishai" in lowered or "korvold" in lowered:
        return "cast_commander"
    if (
        "wipe" in lowered
        or "deluge" in lowered
        or "farewell" in lowered
        or "blasphemous" in lowered
    ):
        return "boardwipe"
    if phase == "protection" or "protect" in lowered:
        return "protection"
    return "main_phase_action"


def _public_metrics(rows: list[dict[str, Any]], offset: int, actor_id: str) -> dict[str, float]:
    metrics = {
        "life": 40.0,
        "hand": 0.0,
        "mana": 0.0,
        "board": 0.0,
        "threat": 0.0,
        "win_progress": 0.0,
        "commander_damage": 0.0,
        "placement": 0.0,
    }
    for row in reversed(rows[: offset + 1]):
        if row.get("event_type") == "turn_summary" and row.get("actor_id") == actor_id:
            after = (row.get("payload") or {}).get("after") or {}
            metrics.update(
                {
                    "life": float(after.get("life", metrics["life"])),
                    "hand": float(after.get("hand", metrics["hand"])),
                    "mana": float(after.get("lands", 0.0))
                    + float(after.get("ramp", 0.0))
                    + float(after.get("resources", 0.0)) * 0.25,
                    "board": float(after.get("board_power", metrics["board"]))
                    + float(after.get("engine_value", 0.0)),
                    "threat": float(after.get("threat", metrics["threat"])),
                    "win_progress": float(after.get("board_power", 0.0))
                    + float(after.get("engine_value", 0.0)),
                }
            )
            break
    for row in reversed(rows[: offset + 1]):
        if row.get("event_type") != "state_checkpoint":
            continue
        players = (row.get("payload") or {}).get("players") or []
        player = next((p for p in players if str(p.get("player_id")) == actor_id), None)
        if player:
            counts = player.get("counts") or {}
            metrics["hand"] = float(counts.get("hand", metrics["hand"]))
            metrics["board"] = max(metrics["board"], float(counts.get("battlefield", 0.0)))
            if "life" in player:
                metrics["life"] = float(player["life"])
            if "commander_damage" in player:
                values = player.get("commander_damage") or {}
                metrics["commander_damage"] = max((float(v) for v in values.values()), default=0.0)
            break
    for row in rows[: offset + 1]:
        if (
            row.get("event_type") in {"player_eliminated", "player_lost"}
            and row.get("actor_id") == actor_id
        ):
            metrics["placement"] = float((row.get("payload") or {}).get("placement", 0.0))
    return metrics


def _realized_future_summary(
    rows: list[dict[str, Any]], offset: int, actor_id: str
) -> dict[str, float]:
    before = _public_metrics(rows, offset, actor_id)
    after = _public_metrics(rows, len(rows) - 1, actor_id)
    return {key: after.get(key, 0.0) - before.get(key, 0.0) for key in before}


def _candidate_action(item: Any, phase: str | None) -> CounterfactualAction | None:
    if isinstance(item, dict):
        action_id = str(item.get("action_id") or item.get("id") or "")
        if not action_id:
            return None
        return CounterfactualAction(
            action_id=action_id,
            utility=float(item["utility"]) if item.get("utility") is not None else None,
            legal=bool(item.get("legal", True)),
            action_kind=str(item.get("action_kind") or _action_kind(action_id, phase)),
            target_ids=tuple(str(v) for v in item.get("target_ids", ())),
            public_description=str(item.get("public_description") or action_id),
            metadata=dict(item.get("metadata") or {}),
            tactical_rule=item.get("tactical_rule"),
            tactical_input=dict(item.get("tactical_input") or {}),
        )
    if isinstance(item, (list, tuple)) and item:
        action_id = str(item[0])
        return CounterfactualAction(
            action_id=action_id,
            utility=float(item[1]) if len(item) > 1 and item[1] is not None else None,
            action_kind=_action_kind(action_id, phase),
            public_description=action_id,
        )
    return None


def _action_state_effect(action: CounterfactualAction, utility: float) -> dict[str, float]:
    metadata = action.metadata
    if metadata:
        explicit = {
            "card_advantage": float(metadata.get("card_advantage_delta", 0.0)),
            "mana": float(metadata.get("mana_delta", 0.0)),
            "life": float(metadata.get("life_delta", 0.0)),
            "commander_damage": float(metadata.get("commander_damage_delta", 0.0)),
            "board": float(metadata.get("board_delta", 0.0)),
            "hand": float(metadata.get("hand_delta", 0.0)),
            "interaction_reserve": float(metadata.get("interaction_reserve_delta", 0.0)),
            "threat": float(metadata.get("threat_delta", 0.0)),
            "win_progress": float(metadata.get("win_progress_delta", utility / 10.0)),
        }
        if any(abs(v) > 1e-12 for v in explicit.values()):
            return explicit
    kind = action.action_kind
    effect = {
        "card_advantage": 0.0,
        "mana": 0.0,
        "life": 0.0,
        "commander_damage": 0.0,
        "board": 0.0,
        "hand": 0.0,
        "interaction_reserve": 0.0,
        "threat": 0.0,
        "win_progress": utility / 10.0,
    }
    if kind == "pass_priority":
        effect["interaction_reserve"] = 0.75
        effect["threat"] = 0.25
    elif kind == "counter_or_hold":
        effect.update(
            card_advantage=-1.0, mana=-1.5, hand=-1.0, interaction_reserve=-0.75, threat=-1.25
        )
    elif kind == "target_selection":
        effect.update(card_advantage=-1.0, mana=-1.5, hand=-1.0, board=-1.0, threat=-1.0)
    elif kind == "cast_commander":
        effect.update(mana=-4.5, board=2.0, threat=1.2, win_progress=max(0.4, utility / 7.0))
    elif kind == "boardwipe":
        effect.update(
            card_advantage=1.0, mana=-4.0, hand=-1.0, board=-1.0, threat=-2.0, win_progress=0.5
        )
    elif kind == "protection":
        effect.update(
            card_advantage=-1.0,
            mana=-1.0,
            hand=-1.0,
            board=0.75,
            interaction_reserve=-0.5,
            threat=-0.35,
        )
    elif kind == "attack_target":
        effect.update(
            life=utility * 0.2,
            commander_damage=max(0.0, utility * 0.12),
            threat=0.5,
            win_progress=max(0.2, utility / 8.0),
        )
    elif kind == "mulligan_or_bottom":
        effect.update(hand=-1.0, card_advantage=-0.25, win_progress=utility / 12.0)
    else:
        effect.update(
            mana=-1.0, hand=-0.5, board=max(0.0, utility / 5.0), threat=max(0.0, utility / 10.0)
        )
    return effect


class CounterfactualReplayLab:
    def __init__(self, root: Path, *, external_engine_available: bool = False) -> None:
        self.root = root.resolve()
        self.external_engine_available = external_engine_available

    def resolve_path(self, source_path: str) -> Path:
        candidate = (self.root / source_path).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise CounterfactualError("source path must stay inside project root")
        if not candidate.is_file():
            raise CounterfactualError(f"replay source does not exist: {source_path}")
        return candidate

    def load(self, source_path: str) -> tuple[Path, list[dict[str, Any]]]:
        path = self.resolve_path(source_path)
        return path, _read_jsonl(path)

    def find_branchpoints(
        self,
        source_path: str,
        *,
        actor_id: str | None = None,
        phase: str | None = None,
    ) -> tuple[CounterfactualBranchpoint, ...]:
        path, rows = self.load(source_path)
        source_run_id = path.parent.parent.name if path.parent.name == "events" else path.stem
        eliminated: set[str] = set()
        output: list[CounterfactualBranchpoint] = []
        for offset, event in enumerate(rows):
            if event.get("event_type") in {"player_eliminated", "player_lost"} and event.get(
                "actor_id"
            ):
                eliminated.add(str(event["actor_id"]))
            if event.get("event_type") != "pilot_decision":
                continue
            actor = str(event.get("actor_id") or "")
            payload = event.get("payload") or {}
            event_phase = payload.get("phase")
            if actor_id is not None and actor != actor_id:
                continue
            if phase is not None and event_phase != phase:
                continue
            candidates = payload.get("counterfactual_actions") or payload.get("candidates") or []
            actions = tuple(
                action
                for action in (_candidate_action(item, event_phase) for item in candidates)
                if action is not None
            )
            chosen = str(payload.get("selected_action_id") or "pass")
            if not actions:
                actions = (
                    CounterfactualAction(action_id=chosen, utility=payload.get("selected_utility")),
                )
            if chosen not in {row.action_id for row in actions}:
                actions += (
                    CounterfactualAction(action_id=chosen, utility=payload.get("selected_utility")),
                )
            state_hash = sha256_value(_state_proxy(rows, offset))
            output.append(
                CounterfactualBranchpoint(
                    branchpoint_id=f"{event.get('game_id', path.stem)}:{offset}",
                    source_run_id=source_run_id,
                    source_path=str(path.relative_to(self.root)),
                    game_id=str(event.get("game_id") or path.stem),
                    event_offset=offset,
                    actor_id=actor,
                    state_hash=state_hash,
                    replay_prefix_hash=_prefix_hash(rows, offset),
                    available_actions=actions,
                    chosen_action=chosen,
                    phase=event_phase,
                    player_eliminated=actor in eliminated,
                    public_state_before=_public_metrics(rows, offset, actor),
                    realized_future_summary=_realized_future_summary(rows, offset, actor),
                )
            )
        return tuple(output)

    def branchpoint_at(self, source_path: str, event_offset: int) -> CounterfactualBranchpoint:
        _path, rows = self.load(source_path)
        if event_offset < 0 or event_offset >= len(rows):
            raise CounterfactualError("invalid event offset")
        matches = [
            row for row in self.find_branchpoints(source_path) if row.event_offset == event_offset
        ]
        if not matches:
            raise CounterfactualError("event offset is not a pilot decision branchpoint")
        branch = matches[0]
        if branch.replay_prefix_hash != _prefix_hash(rows, event_offset):
            raise CounterfactualError("replay drift detected")
        return branch

    def verify_branchpoint(
        self, branch: CounterfactualBranchpoint, expected_state_hash: str | None = None
    ) -> None:
        current = self.branchpoint_at(branch.source_path, branch.event_offset)
        if current.replay_prefix_hash != branch.replay_prefix_hash:
            raise CounterfactualError("replay drift detected")
        expected = expected_state_hash or branch.state_hash
        if current.state_hash != expected:
            raise CounterfactualError("state hash mismatch")
        if branch.player_eliminated:
            raise CounterfactualError("eliminated player cannot choose an alternative action")

    @staticmethod
    def _utility(branch: CounterfactualBranchpoint, action_id: str) -> float:
        action = next((row for row in branch.available_actions if row.action_id == action_id), None)
        if action is None or not action.legal:
            raise CounterfactualError("alternative action is not legal at branchpoint")
        return float(action.utility or 0.0)

    @staticmethod
    def _sample_seeds(seed: int, count: int, policy: SeedPolicy) -> list[int]:
        if policy == SeedPolicy.SAME_SEED:
            return [seed] * count
        if policy == SeedPolicy.DERIVED_SEEDS:
            return [
                int(hashlib.sha256(f"{seed}:{idx}".encode()).hexdigest()[:16], 16)
                for idx in range(count)
            ]
        return [seed + idx for idx in range(count)]

    def run(
        self,
        branch: CounterfactualBranchpoint,
        *,
        alternative_action: str,
        expected_state_hash: str | None = None,
        hidden_information_policy: HiddenInformationPolicy = HiddenInformationPolicy.PUBLIC_INFORMATION_ONLY,
        engine_mode: CounterfactualEngineMode = CounterfactualEngineMode.STRUCTURAL,
        seed_policy: SeedPolicy = SeedPolicy.SAME_SEED,
        seed: int = 20260806,
        future_samples: int = 1,
        workers: int = 1,
    ) -> CounterfactualResult:
        self.verify_branchpoint(branch, expected_state_hash)
        if workers < 1:
            raise CounterfactualError("workers must be positive")
        if (
            engine_mode == CounterfactualEngineMode.EXTERNAL_ENGINE
            and not self.external_engine_available
        ):
            raise CounterfactualError(
                "external engine is not available; no external validation can be claimed"
            )
        if future_samples < 1:
            raise CounterfactualError("future_samples must be positive")
        if hidden_information_policy == HiddenInformationPolicy.SAME_REALIZED_FUTURE:
            future_samples = 1
            seed_policy = SeedPolicy.SAME_SEED
        if (
            hidden_information_policy == HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES
            and future_samples < 2
        ):
            raise CounterfactualError("multiple_future_samples requires at least two futures")
        chosen_action_row = next(
            row for row in branch.available_actions if row.action_id == branch.chosen_action
        )
        alternative_action_row = next(
            (row for row in branch.available_actions if row.action_id == alternative_action), None
        )
        if alternative_action_row is None or not alternative_action_row.legal:
            raise CounterfactualError("alternative action is not legal at branchpoint")
        chosen = self._utility(branch, branch.chosen_action)
        alternative = self._utility(branch, alternative_action)
        tactical_observations: dict[str, Any] = {}
        validation_level = "structural_model_estimates"
        if engine_mode == CounterfactualEngineMode.TACTICAL_ORACLE:
            oracle = TacticalRuleOracle()
            for label, action in (
                ("chosen", chosen_action_row),
                ("alternative", alternative_action_row),
            ):
                if not action.tactical_rule:
                    raise CounterfactualError(
                        "tactical_oracle mode requires recorded tactical_rule "
                        "metadata for both actions"
                    )
                try:
                    tactical_observations[label] = oracle.evaluate(
                        action.tactical_rule, action.tactical_input
                    )
                except TacticalRuleError as exc:
                    raise CounterfactualError(str(exc)) from exc

            def tactical_score(value: dict[str, Any]) -> float:
                score = 0.0
                for key, item in value.items():
                    if isinstance(item, bool):
                        score += 1.0 if item else -1.0
                    elif isinstance(item, (int, float)):
                        direction = (
                            -1.0
                            if any(
                                token in key
                                for token in ("cost", "tax", "damage_taken", "cards_lost")
                            )
                            else 1.0
                        )
                        score += direction * float(item) * 0.1
                return score

            chosen += tactical_score(tactical_observations["chosen"])
            alternative += tactical_score(tactical_observations["alternative"])
            validation_level = "tactical_oracle"

        chosen_effect = _action_state_effect(chosen_action_row, chosen)
        alternative_effect = _action_state_effect(alternative_action_row, alternative)
        effect_delta = {
            key: alternative_effect.get(key, 0.0) - chosen_effect.get(key, 0.0)
            for key in chosen_effect
        }
        state_value = (
            effect_delta["card_advantage"] * 0.65
            + effect_delta["mana"] * 0.25
            + effect_delta["life"] * 0.12
            + effect_delta["commander_damage"] * 0.20
            + effect_delta["board"] * 0.50
            + effect_delta["hand"] * 0.55
            + effect_delta["interaction_reserve"] * 0.40
            - effect_delta["threat"] * 0.25
            + effect_delta["win_progress"] * 0.70
        )
        base_improvement = (alternative - chosen) + state_value * 0.40
        realized = branch.realized_future_summary
        realized_volatility = sum(abs(float(value)) for value in realized.values()) / max(
            1, len(realized)
        )
        seeds = self._sample_seeds(seed, future_samples, seed_policy)
        rows: list[CounterfactualFutureSample] = []
        for index, sample_seed in enumerate(seeds):
            rng = random.Random(sample_seed)
            future_adjustment = 0.0
            if hidden_information_policy == HiddenInformationPolicy.SAME_REALIZED_FUTURE:
                # The public realized suffix is held fixed for both lines. Only an interaction
                # term with the changed reserve/threat state is applied.
                future_adjustment = (
                    effect_delta["interaction_reserve"] * float(realized.get("threat", 0.0)) * -0.03
                    + effect_delta["board"] * float(realized.get("board", 0.0)) * 0.02
                )
            elif hidden_information_policy in {
                HiddenInformationPolicy.RESAMPLED_UNKNOWN_FUTURE,
                HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES,
            }:
                scale = max(
                    0.10, min(2.0, 0.08 * realized_volatility + abs(base_improvement) * 0.18)
                )
                future_adjustment = rng.gauss(0.0, scale)
            # public_information_only deliberately adds no hidden-future adjustment.
            improvement = base_improvement + future_adjustment
            placement_delta = max(-2.0, min(2.0, improvement / 8.0))
            rows.append(
                CounterfactualFutureSample(
                    sample_index=index,
                    seed=sample_seed,
                    chosen_score=chosen,
                    alternative_score=chosen + improvement,
                    improvement=improvement,
                    estimated_placement_delta=placement_delta,
                )
            )
        improvements = [row.improvement for row in rows]
        mean = fmean(improvements)
        med = median(improvements)
        variance = pvariance(improvements) if len(improvements) > 1 else 0.0
        positive = sum(value > 0 for value in improvements) / len(improvements)
        conclusion = (
            "alternative_model_preferred"
            if positive >= 0.75 and mean > 0
            else "chosen_model_preferred"
            if positive <= 0.25 and mean < 0
            else "counterfactual_inconclusive"
        )
        diff = CounterfactualStateDiff(
            immediate_utility_delta=alternative - chosen,
            card_advantage_delta=effect_delta["card_advantage"],
            mana_delta=effect_delta["mana"],
            life_delta=effect_delta["life"],
            commander_damage_delta=effect_delta["commander_damage"],
            board_delta=effect_delta["board"],
            hand_delta=effect_delta["hand"],
            interaction_reserve_delta=effect_delta["interaction_reserve"],
            threat_delta=effect_delta["threat"],
            win_progress_delta=effect_delta["win_progress"],
            placement_delta=fmean(row.estimated_placement_delta for row in rows),
        )
        warnings = [
            "Counterfactuals are model alternatives, not facts about "
            "what historically would have happened.",
            "Only actions recorded as legal at the verified branchpoint are evaluated.",
        ]
        if engine_mode == CounterfactualEngineMode.STRUCTURAL:
            warnings.append("Structural state transitions remain role-level approximations.")
        if engine_mode == CounterfactualEngineMode.TACTICAL_ORACLE:
            warnings.append(
                "Tactical Oracle output is local tactical evidence, not an external rules engine."
            )
        return CounterfactualResult(
            counterfactual_id=hashlib.sha256(
                f"{branch.branchpoint_id}:{alternative_action}:{seed}:{future_samples}:{hidden_information_policy}".encode()
            ).hexdigest()[:24],
            branchpoint=branch.model_copy(
                update={
                    "alternative_action": alternative_action,
                    "engine_mode": engine_mode,
                    "seed_policy": seed_policy,
                    "hidden_information_policy": hidden_information_policy,
                }
            ),
            alternative_action=alternative_action,
            state_diff=diff,
            future_samples=tuple(rows),
            mean_improvement=mean,
            median_improvement=med,
            improvement_variance=variance,
            positive_future_fraction=positive,
            conclusion=conclusion,
            external_engine_used=False,
            tactical_oracle_used=engine_mode == CounterfactualEngineMode.TACTICAL_ORACLE,
            tactical_observations=tactical_observations,
            warnings=tuple(warnings),
            provenance={
                "source_path": branch.source_path,
                "source_run_id": branch.source_run_id,
                "replay_prefix_hash": branch.replay_prefix_hash,
                "state_hash": branch.state_hash,
                "validation_level": validation_level,
                "hidden_information_policy": hidden_information_policy.value,
                "realized_future_summary": branch.realized_future_summary,
            },
        )

    @staticmethod
    def compare(results: Iterable[CounterfactualResult]) -> CounterfactualComparison:
        rows = tuple(results)
        if not rows:
            raise CounterfactualError("no counterfactual results supplied")
        mean_map = {row.alternative_action: row.mean_improvement for row in rows}
        worst_map = {
            row.alternative_action: min(sample.improvement for sample in row.future_samples)
            for row in rows
        }
        ranking = tuple(
            sorted(mean_map, key=lambda key: (mean_map[key], worst_map[key]), reverse=True)
        )
        return CounterfactualComparison(
            comparison_id=hashlib.sha256(
                "|".join(row.counterfactual_id for row in rows).encode()
            ).hexdigest()[:24],
            result_ids=tuple(row.counterfactual_id for row in rows),
            best_alternative=ranking[0] if ranking else None,
            mean_improvements=mean_map,
            worst_case_improvements=worst_map,
            ranking=ranking,
        )

    @staticmethod
    def regret(result: CounterfactualResult) -> DecisionRegretRecord:
        regret = max(0.0, result.mean_improvement)
        confidence = min(0.95, 0.35 + 0.6 * abs(result.positive_future_fraction - 0.5) * 2)
        contradictory = 0.0 < result.positive_future_fraction < 1.0
        return DecisionRegretRecord(
            branchpoint_id=result.branchpoint.branchpoint_id,
            chosen_action=result.branchpoint.chosen_action,
            best_tested_alternative=result.alternative_action if regret > 0 else None,
            decision_regret=regret,
            evidence_samples=len(result.future_samples),
            confidence=confidence,
            contradictory_futures=contradictory,
            recommended_interpretation=(
                "test_more_futures"
                if contradictory or len(result.future_samples) < 8
                else "model_supports_alternative"
                if regret > 0
                else "no_model_regret_detected"
            ),
        )

    def export_fixture(self, branch: CounterfactualBranchpoint, target: Path) -> dict[str, Any]:
        payload = {
            "schema_version": "1.0.0",
            "fixture_type": "counterfactual_golden_scenario",
            "branchpoint": branch.model_dump(mode="json"),
            "truth_boundary": "model_alternative_not_historical_fact",
        }
        atomic_write_json(target, payload)
        return payload

    @staticmethod
    def report(result: CounterfactualResult, target: Path) -> None:
        lines = [
            "# Counterfactual Decision-Regret Report",
            "",
            f"Branchpoint: `{result.branchpoint.branchpoint_id}`",
            f"Chosen action: `{result.branchpoint.chosen_action}`",
            f"Alternative action: `{result.alternative_action}`",
            f"Hidden-information policy: `{result.branchpoint.hidden_information_policy.value}`",
            f"Engine mode: `{result.branchpoint.engine_mode.value}`",
            "",
            "## Model result",
            "",
            f"- Mean improvement: {result.mean_improvement:.4f}",
            f"- Median improvement: {result.median_improvement:.4f}",
            f"- Positive future fraction: {result.positive_future_fraction:.3f}",
            f"- Conclusion: `{result.conclusion}`",
            "",
            "## Boundary",
            "",
            "This is a counterfactual model alternative. It is not "
            "evidence that history would certainly have unfolded this "
            "way.",
        ]
        atomic_write_text(target, "\n".join(lines) + "\n")
