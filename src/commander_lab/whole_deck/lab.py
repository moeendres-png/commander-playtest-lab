from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from commander_lab.models import StructuralDeckProfile
from commander_lab.storage import atomic_write_json, sha256_value

from .discoverability import build_discoverability_report
from .enrichment import ENRICHMENT_VERSION
from .lab_context import (
    WHOLE_DECK_LAB_VERSION,
    EnrichedWholeDeckSearchEngine,
    enriched_context,
)
from .models import PolicyId
from .policies import get_policy
from .search import current_control_mainboard, save_search_result
from .search_models import WholeDeckSearchConfig, WholeDeckSearchResult, WholeDeckVariant


def _dedupe(
    results: Iterable[WholeDeckSearchResult],
    limit: int,
) -> list[WholeDeckVariant]:
    by_hash: dict[str, WholeDeckVariant] = {}
    for result in results:
        finalists = set(result.finalist_variant_ids)
        for variant in result.variants:
            if variant.variant_id not in finalists:
                continue
            previous = by_hash.get(variant.deck_hash)
            if previous is None or variant.objective_prior > previous.objective_prior:
                by_hash[variant.deck_hash] = variant
    return sorted(
        by_hash.values(),
        key=lambda row: (-row.objective_prior, row.deck_hash),
    )[:limit]


class WholeDeckDesignLab:
    """Prepare reproducible Whole-Deck finalists; never applies them automatically."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.context, self.enrichment, self.answer_map = enriched_context(self.root)
        if not self.context.cards:
            raise ValueError("current RogShai candidate universe is empty")
        if (
            self.context.fresh_universe is not None
            and len(self.context.cards) != self.context.fresh_universe.candidate_count
        ):
            raise ValueError(
                "Whole-Deck context does not reconcile to the current fresh candidate universe"
            )

    def prepare(
        self,
        *,
        policies: Iterable[str | PolicyId],
        seed: int,
        diversified_starts: int,
        steps_per_start: int,
        finalists_per_policy: int,
        max_variants: int,
        output_name: str = "whole_deck_design.json",
    ) -> dict[str, object]:
        control = current_control_mainboard(self.root)
        results: list[WholeDeckSearchResult] = []
        policy_rows: list[dict[str, object]] = []
        for index, raw in enumerate(policies):
            policy = get_policy(PolicyId(raw))
            config = WholeDeckSearchConfig(
                seed=seed + index * 1009,
                diversified_starts=diversified_starts,
                max_steps_per_start=steps_per_start,
                finalist_limit=finalists_per_policy,
                archive_limit=max(32, max_variants),
            )
            engine = EnrichedWholeDeckSearchEngine(
                self.context,
                policy,
                config=config,
                enrichment=self.enrichment,
                answer_map=self.answer_map,
            )
            result = engine.run(current_control=control)
            save_search_result(self.root, result)
            results.append(result)
            policy_rows.append(
                {
                    "policy_id": policy.policy_id.value,
                    "campaign_id": result.campaign_id,
                    "explored": len(result.explored_variant_ids),
                    "finalists": list(result.finalist_variant_ids),
                    "control_used_as_search_prior": result.control_used_as_search_prior,
                }
            )

        deck_path = self.root / "data/decks/rogshai_current.json"
        deck_json = json.loads(deck_path.read_text(encoding="utf-8"))
        discoverability = build_discoverability_report(self.context, results)
        payload: dict[str, object] = {
            "schema_version": "1.0.0",
            "lab_version": WHOLE_DECK_LAB_VERSION,
            "enrichment_version": ENRICHMENT_VERSION,
            "enrichment_snapshot_hash": self.enrichment.snapshot_hash,
            "data_snapshot_hash": self.context.snapshot_hash,
            "candidate_count": len(self.context.cards),
            "canonical_control_hash": str(deck_json["deck_hash"]),
            "policies": policy_rows,
            "discoverability": discoverability,
            "variants": [row.model_dump(mode="json") for row in _dedupe(results, max_variants)],
            "mulligan_contract": self.enrichment.mulligan_contract,
            "official_structural_campaign_run": False,
            "automatic_deck_mutation": False,
            "evidence_boundaries": {
                "search_prior_is_simulation_evidence": False,
                "structural_model_estimates_are_empirical_winrates": False,
                "tactical_oracle_is_external_rules_engine": False,
                "old_static_threat_answer_matrix_used": False,
                "old_hash_mulligan_results_used": False,
            },
        }
        payload["design_campaign_id"] = sha256_value(payload)
        target = self.root / ".runtime/whole_deck_design" / Path(output_name).name
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(target, payload)
        return {**payload, "prepared_design_path": str(target.relative_to(self.root))}

    def semantic_unknown_cards_for_variant(
        self, prepared_design_path: str, variant_id: str
    ) -> tuple[str, ...]:
        path = (self.root / prepared_design_path).resolve()
        allowed = (self.root / ".runtime/whole_deck_design").resolve()
        if allowed not in path.parents:
            raise ValueError("prepared design must be under .runtime/whole_deck_design")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("data_snapshot_hash") != self.context.snapshot_hash:
            raise ValueError("prepared Whole-Deck design is stale")
        row = next(
            (item for item in payload.get("variants", []) if item.get("variant_id") == variant_id),
            None,
        )
        if row is None:
            raise ValueError(f"unknown Whole-Deck variant: {variant_id}")
        names = tuple(str(name) for name in row.get("mainboard", []))
        return tuple(
            sorted(
                name
                for name in set(names)
                if name in self.context.cards and not self.context.cards[name].semantic_known
            )
        )

    def materialize_variant(
        self,
        prepared_design_path: str,
        variant_id: str,
    ) -> StructuralDeckProfile:
        path = (self.root / prepared_design_path).resolve()
        allowed = (self.root / ".runtime/whole_deck_design").resolve()
        if allowed not in path.parents:
            raise ValueError("prepared design must be under .runtime/whole_deck_design")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("data_snapshot_hash") != self.context.snapshot_hash:
            raise ValueError("prepared Whole-Deck design is stale")
        row = next(
            (item for item in payload.get("variants", []) if item.get("variant_id") == variant_id),
            None,
        )
        if row is None:
            raise ValueError(f"unknown Whole-Deck variant: {variant_id}")
        variant = WholeDeckVariant.model_validate(row)
        if not variant.hard_gate.valid:
            raise ValueError("prepared variant failed hard gate")
        return self.context.materialize(
            tuple(variant.mainboard),
            label=variant.deck_hash[:12],
        )
