from __future__ import annotations

import builtins
import json
import math
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Any

from commander_lab.models.opponent_ensembles import (
    EnsembleMatchupResult,
    OpponentEnsemble,
    OpponentVariant,
)
from commander_lab.storage.hashing import sha256_value


class EnsembleConflictError(RuntimeError):
    """Raised when an append-only ensemble identifier is reused with new content."""


class OpponentEnsembleStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.base = self.root / "data" / "opponent_ensembles"
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, ensemble_id: str) -> Path:
        return self.base / f"{ensemble_id}.json"

    def save(
        self,
        ensemble: OpponentEnsemble,
        *,
        allow_existing_identical: bool = True,
    ) -> Path:
        target = self.path(ensemble.ensemble_id)
        payload = (
            json.dumps(
                ensemble.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if target.exists():
            if allow_existing_identical and target.read_text(encoding="utf-8") == payload:
                return target
            raise EnsembleConflictError("ensemble ID already exists with different content")
        target.write_text(payload, encoding="utf-8")
        return target

    def load(self, ensemble_id: str) -> OpponentEnsemble:
        target = self.path(ensemble_id)
        if not target.exists():
            raise KeyError(ensemble_id)
        return OpponentEnsemble.model_validate_json(target.read_text(encoding="utf-8"))

    def list(self) -> list[OpponentEnsemble]:
        """List only versioned ensemble documents, never generated reports."""
        results: list[OpponentEnsemble] = []
        for target in sorted(self.base.glob("*-ensemble-v*.json")):
            results.append(OpponentEnsemble.model_validate_json(target.read_text(encoding="utf-8")))
        return results

    def add_variant(
        self,
        ensemble_id: str,
        variant: OpponentVariant,
        new_ensemble_id: str,
    ) -> OpponentEnsemble:
        old = self.load(ensemble_id)
        new = old.model_copy(deep=True)
        new.ensemble_id = new_ensemble_id
        new.version = old.version + 1
        new.supersedes_ensemble_id = old.ensemble_id
        new.variants.append(variant)
        self.save(new)
        return new

    def validate(self, ensemble_id: str) -> dict[str, Any]:
        ensemble = self.load(ensemble_id)
        OpponentEnsemble.model_validate(ensemble.model_dump())
        return {
            "ensemble_id": ensemble.ensemble_id,
            "variant_count": len(ensemble.variants),
            "weight_mode": ensemble.weight_mode,
            "synthetic_variants": sum(v.synthetic for v in ensemble.variants),
            "known_cards_by_variant": {
                variant.variant_id: [card.card_name for card in variant.known_cards]
                for variant in ensemble.variants
            },
            "assumed_cards_by_variant": {
                variant.variant_id: [card.card_name for card in variant.assumed_cards]
                for variant in ensemble.variants
            },
            "automatic_profile_overwrite": False,
            "valid": True,
        }

    @staticmethod
    def _deck_resilience(deck: Any) -> float:
        cards = [card for card in deck.cards if not card.is_land]
        if not cards:
            return 0.0
        role_score = 0
        for card in cards:
            roles = {role.value for role in card.roles}
            role_score += int("protection" in roles)
            role_score += int("recursion" in roles)
            role_score += int("removal" in roles)
        return min(1.0, role_score / max(1, len(cards) * 1.5))

    @staticmethod
    def _variant_pressure(variant: OpponentVariant) -> tuple[float, str]:
        speed = 0.5
        if variant.speed_turn_range is not None:
            speed = max(0.0, min(1.0, (10.0 - variant.speed_turn_range.minimum) / 7.0))
        interaction = (
            variant.interaction_density.maximum if variant.interaction_density is not None else 0.25
        )
        wipes = (
            variant.wipe_count_range.maximum / 8.0 if variant.wipe_count_range is not None else 0.15
        )
        role_concentration = max(variant.role_distribution.values(), default=0.2)
        dimensions = {
            "speed": speed,
            "interaction": interaction,
            "wipes": wipes,
            "role_concentration": role_concentration,
        }
        pressure = min(
            1.5,
            0.38 * speed + 0.28 * interaction + 0.18 * wipes + 0.16 * role_concentration,
        )
        return pressure, max(dimensions, key=lambda name: dimensions[name])

    @staticmethod
    def _normalized_weights(ensemble: OpponentEnsemble) -> builtins.list[float]:
        if ensemble.weight_mode.value in {"unweighted", "equal", "worst_case"}:
            return [1.0 / len(ensemble.variants)] * len(ensemble.variants)
        values = [variant.weight.value for variant in ensemble.variants]
        if any(value is None for value in values):
            raise ValueError("weighted ensemble contains missing weight")
        return [float(value) for value in values if value is not None]

    def run_matchups(
        self,
        deck: Any,
        ensemble_id: str,
        seed: int = 20260806,
    ) -> EnsembleMatchupResult:
        ensemble = self.load(ensemble_id)
        resilience = self._deck_resilience(deck)
        rows: list[dict[str, Any]] = []
        values: list[float] = []
        sensitivities: dict[str, float] = {}
        weights = self._normalized_weights(ensemble)

        for variant in ensemble.variants:
            pressure, dimension = self._variant_pressure(variant)
            jitter_source = sha256_value({"seed": seed, "variant": variant.variant_id})
            jitter = (int(jitter_source[:8], 16) % 2001 - 1000) / 100000.0
            score = max(-1.0, min(1.0, resilience - pressure + jitter))
            values.append(score)
            sensitivities[dimension] = sensitivities.get(dimension, 0.0) + abs(score)
            rows.append(
                {
                    "variant_id": variant.variant_id,
                    "score": score,
                    "synthetic": variant.synthetic,
                    "confidence": variant.confidence,
                    "known_cards": [card.card_name for card in variant.known_cards],
                    "assumed_cards": [card.card_name for card in variant.assumed_cards],
                    "sensitive_dimension": dimension,
                }
            )

        weighted_average = sum(
            value * weight for value, weight in zip(values, weights, strict=False)
        )
        positive_share = sum(
            weight for value, weight in zip(values, weights, strict=False) if value > 0
        )
        return EnsembleMatchupResult(
            deck_id=deck.deck_id,
            deck_hash=deck.deck_hash,
            ensemble_id=ensemble.ensemble_id,
            per_variant=tuple(rows),
            average=weighted_average,
            median=median(values),
            worst=min(values),
            best=max(values),
            spread=pstdev(values) if len(values) > 1 else 0.0,
            positive_variant_share=positive_share,
            most_sensitive_assumption=(
                max(sensitivities, key=lambda name: sensitivities[name]) if sensitivities else None
            ),
            weight_mode=ensemble.weight_mode,
            aggregate_interpretation=(
                "worst_variant_is_primary"
                if ensemble.weight_mode.value == "worst_case"
                else "equal_weight_reference"
                if ensemble.weight_mode.value in {"unweighted", "equal"}
                else "weighted_reference"
            ),
        )

    def compare_sensitivity(
        self,
        deck: Any,
        ensemble_id: str,
        seed: int = 20260806,
    ) -> dict[str, Any]:
        return self.run_matchups(deck, ensemble_id, seed).model_dump(mode="json")

    def evaluate_robust_upgrade(
        self,
        baseline: Any,
        candidate: Any,
        ensemble_id: str,
        seed: int = 20260806,
    ) -> dict[str, Any]:
        baseline_result = self.run_matchups(baseline, ensemble_id, seed)
        candidate_result = self.run_matchups(candidate, ensemble_id, seed)
        deltas = [
            candidate_row["score"] - baseline_row["score"]
            for baseline_row, candidate_row in zip(
                baseline_result.per_variant,
                candidate_result.per_variant,
                strict=True,
            )
        ]
        positive_count = sum(delta > 0 for delta in deltas)
        return {
            "ensemble_id": ensemble_id,
            "baseline_deck_hash": baseline.deck_hash,
            "candidate_deck_hash": candidate.deck_hash,
            "average_delta": fmean(deltas),
            "median_delta": median(deltas),
            "worst_delta": min(deltas),
            "best_delta": max(deltas),
            "positive_variant_share": positive_count / len(deltas),
            "robust": (min(deltas) >= 0 and positive_count >= max(2, math.ceil(len(deltas) / 2))),
            "automatic_deck_application": False,
            "estimate_type": "structural_model_estimates",
        }

    def report(self, ensemble_id: str) -> str:
        ensemble = self.load(ensemble_id)
        lines = [
            "# Opponent Ensemble Report",
            "",
            f"Ensemble: `{ensemble.ensemble_id}`",
            f"Commander: {ensemble.commander}",
            f"Variants: {len(ensemble.variants)}",
            f"Weight mode: {ensemble.weight_mode}",
            "",
            "Known cards and synthetic assumptions are stored separately.",
        ]
        for variant in ensemble.variants:
            known = ", ".join(card.card_name for card in variant.known_cards) or "none"
            assumed = ", ".join(card.card_name for card in variant.assumed_cards) or "none"
            assumptions = "; ".join(variant.assumptions) or "none"
            lines.extend(
                [
                    "",
                    f"## {variant.name}",
                    f"- Synthetic: {variant.synthetic}",
                    f"- Confidence: {variant.confidence}",
                    f"- Known cards: {known}",
                    f"- Assumed cards: {assumed}",
                    f"- Roles: {json.dumps(variant.role_distribution, sort_keys=True)}",
                    f"- Speed range: {variant.speed_turn_range}",
                    f"- Interaction density: {variant.interaction_density}",
                    f"- Wipe range: {variant.wipe_count_range}",
                    f"- Win axes: {', '.join(variant.win_axes) or 'none'}",
                    f"- Sources: {', '.join(variant.source_ids) or 'none'}",
                    f"- Assumptions: {assumptions}",
                ]
            )
        return "\n".join(lines) + "\n"
