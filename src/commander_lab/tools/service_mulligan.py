from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from commander_lab.models import (
    ToolResponse,
)
from commander_lab.models.mulligan import (
    GeneratedKeepRule,
    MulliganContext,
    MulliganGamePlan,
    MulliganLabResult,
    MulliganPolicyName,
)
from commander_lab.models.tooling import (
    CompareMulliganPoliciesInput,
    CreateMulliganReportInput,
    EvaluateOpeningHandInput,
    GenerateKeepRulesInput,
    RunMulliganLabInput,
    SampleOpeningHandsInput,
    TestKeepRuleInput,
)
from commander_lab.mulligan import MulliganLab
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    sha256_value,
)

if TYPE_CHECKING:
    pass

from .service_core import (
    ServiceCore,
    ToolExecutionError,
)


class ServiceMulliganMixin(ServiceCore):
    def _mulligan_lab(self) -> MulliganLab:
        return MulliganLab(self.root)

    def _mulligan_context_from_request(self, request: Any) -> MulliganContext:
        deck = self._deck(request.deck_id)
        ensemble_hash = None
        ensemble_id = getattr(request, "opponent_ensemble_id", None)
        if ensemble_id:
            ensemble = self._opponent_ensembles().load(ensemble_id)
            ensemble_hash = sha256_value(ensemble.model_dump(mode="json"))
        return MulliganContext(
            deck_id=request.deck_id,
            deck_hash=deck.deck_hash,
            opponent_ensemble_id=ensemble_id,
            opponent_ensemble_hash=ensemble_hash,
            seat_position=getattr(request, "seat_position", 1),
            starting_player=getattr(request, "starting_player", False),
            pod_size=getattr(request, "pod_size", 4),
            pilot_profile_id=getattr(request, "pilot_profile_id", "baseline"),
            pilot_version=getattr(request, "pilot_version", "unspecified"),
            game_plan=MulliganGamePlan(getattr(request, "game_plan", "balanced")),
            seed=getattr(request, "seed", 20260806),
        )

    def sample_opening_hands(self, request: SampleOpeningHandsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.samples, None)
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            target = (
                self.root
                / "data/runs/mulligan_lab"
                / f"{request.deck_id.replace('/', '_')}-{request.seed}-hands.jsonl"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            first_samples = []
            with target.open("w", encoding="utf-8") as handle:
                for index, attempts in enumerate(
                    lab.iter_draw_sequences(
                        deck,
                        samples=request.samples,
                        seed=request.seed,
                        max_mulligans=request.max_mulligans,
                    )
                ):
                    serialized = [[card.oracle_name for card in hand] for hand in attempts]
                    if index < 10:
                        first_samples.append(serialized)
                    handle.write(
                        json.dumps(
                            {
                                "sample_id": index,
                                "deck_id": request.deck_id,
                                "deck_hash": deck.deck_hash,
                                "attempts": serialized,
                                "seed": request.seed,
                                "common_random_numbers_ready": True,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
            return {
                "dataset_path": str(target.relative_to(self.root)),
                "samples": request.samples,
                "attempts_per_sample": request.max_mulligans + 1,
                "first_samples": first_samples,
                "commander_in_command_zone": list(deck.commander_names),
                "estimate_type": "structural_model_estimates",
            }

        return self._invoke(
            "sample_opening_hands",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
        )

    def evaluate_opening_hand(self, request: EvaluateOpeningHandInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            pool: dict[str, list[Any]] = {}
            for card in lab._library(deck):
                pool.setdefault(card.oracle_name, []).append(card)
            used: Counter[str] = Counter()
            selected = []
            for name in request.card_names:
                rows = pool.get(name, [])
                index = used[name]
                if index >= len(rows):
                    raise ToolExecutionError(f"card not available in current deck library: {name}")
                selected.append(rows[index])
                used[name] += 1
            context = self._mulligan_context_from_request(request)
            evaluation = lab.evaluate(deck, selected, MulliganPolicyName(request.policy), context)
            return evaluation.model_dump(mode="json") | {
                "deck_hash": deck.deck_hash,
                "commander_in_command_zone": list(deck.commander_names),
                "absolute_rule": False,
            }

        return self._invoke(
            "evaluate_opening_hand", request, work, deck_ids=(request.deck_id,), seed=request.seed
        )

    def compare_mulligan_policies(self, request: CompareMulliganPoliciesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.samples * max(1, len(request.policies)), request.approval_token
            )
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
                generate_keep_rules=request.generate_keep_rules,
            )
            return result.model_dump(mode="json")

        return self._invoke(
            "compare_mulligan_policies",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
        )

    def run_mulligan_lab(self, request: RunMulliganLabInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.samples * max(1, len(request.policies)), request.approval_token
            )
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
                generate_keep_rules=request.generate_keep_rules,
            )
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke(
            "run_mulligan_lab",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
        )

    def generate_keep_rules(self, request: GenerateKeepRulesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            source = self._project_path(request.result_path)
            result = MulliganLabResult.model_validate_json(source.read_text(encoding="utf-8"))
            payload = {
                "schema_version": result.schema_version,
                "deck_id": result.context.deck_id,
                "deck_hash": result.context.deck_hash,
                "rules": [rule.model_dump(mode="json") for rule in result.generated_rules],
                "model_based": True,
                "absolute_rules": False,
            }
            target = self.root / "data/mulligan_lab/policies" / Path(request.output_name).name
            atomic_write_json(target, payload)
            return payload | {"path": str(target.relative_to(self.root))}

        return self._invoke("generate_keep_rules", request, work)

    def test_keep_rule(self, request: TestKeepRuleInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            payload = json.loads(self._project_path(request.rule_path).read_text(encoding="utf-8"))
            rows = payload.get("rules", payload)
            if not rows:
                raise ToolExecutionError("no keep rules found")
            rule = GeneratedKeepRule.model_validate(rows[0])
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            if rule.deck_hash != deck.deck_hash:
                raise ToolExecutionError("keep rule deck hash does not match current deck")
            pool: dict[str, list[Any]] = {}
            for card in lab._library(deck):
                pool.setdefault(card.oracle_name, []).append(card)
            used: Counter[str] = Counter()
            cards = []
            for name in request.card_names:
                idx = used[name]
                choices = pool.get(name, [])
                if idx >= len(choices):
                    raise ToolExecutionError(f"card not available in deck: {name}")
                cards.append(choices[idx])
                used[name] += 1
            features = lab.features(deck, cards)
            return lab.test_rule(rule, features) | {"features": features.model_dump(mode="json")}

        return self._invoke("test_keep_rule", request, work, deck_ids=(request.deck_id,))

    def create_mulligan_report(self, request: CreateMulliganReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = MulliganLabResult.model_validate_json(
                self._project_path(request.result_path).read_text(encoding="utf-8")
            )
            lines = [
                "# Mulligan Lab Report",
                "",
                f"Deck: `{result.context.deck_id}`",
                f"Deck hash: `{result.context.deck_hash}`",
                f"Samples: {result.sample_count}",
                "",
                "All keep rules and follow-up outcomes are model-based structural estimates.",
                "",
                "## Policy comparison",
                "",
                "| Policy | First-seven keep | Mulligan rate | Avg mulligans | "
                "Color issues | Structural placement |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for row in result.policies:
                placement = (
                    "n/a"
                    if row.structural_placement_mean is None
                    else f"{row.structural_placement_mean:.3f}"
                )
                lines.append(
                    f"| {row.policy.value} | {row.keep_rate_first_seven:.3f} | "
                    f"{row.mulligan_rate:.3f} | "
                    f"{row.average_mulligans:.3f} | {row.color_problem_rate:.3f} | {placement} |"
                )
            lines.extend(
                [
                    "",
                    "## Boundaries",
                    "",
                    "- Hand quality is separated from complete matchup performance.",
                    "- No rule is universal or empirically proven.",
                    "- No external rules engine was used.",
                ]
            )
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_text(target, "\n".join(lines) + "\n")
            return {
                "report_path": str(target.relative_to(self.root)),
                "model_based": True,
                "automatic_deck_changes": False,
            }

        return self._invoke("create_mulligan_report", request, work)
