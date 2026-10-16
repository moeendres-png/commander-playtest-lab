from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from commander_lab.decision_statistics import holm_adjust
from commander_lab.models import (
    CreateDeckImprovementReportInput,
    CreateReportInput,
    ExplainRecommendationInput,
    ExportRecommendationEvidenceInput,
    RankVariantsInput,
    ToolResponse,
)
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    sha256_value,
)

if TYPE_CHECKING:
    pass

from .service_core import (
    ServiceCore,
)


class ServiceReportsMixin(ServiceCore):
    def rank_variants(self, request: RankVariantsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            def score(row: dict[str, Any]) -> tuple[float, float, float]:
                worst = float(row.get("worst_case_effect", -999.0) or 0.0)
                paired = float(
                    (row.get("paired_structural_effect") or {}).get(
                        "placement_improvement", row.get("effect_size", 0.0)
                    )
                    or 0.0
                )
                coverage_key = str(row.get("rules_coverage") or "")
                coverage = {
                    "external_rules_engine": 3,
                    "tactical_oracle": 2,
                    "structural_only": 1,
                }.get(coverage_key, 0)
                return (worst if request.prefer_worst_case else paired, paired, float(coverage))

            ranked = sorted((dict(row) for row in request.variants), key=score, reverse=True)
            p_rows: list[tuple[int, float]] = []
            for index, row in enumerate(ranked):
                raw_p = row.get("p_value")
                if raw_p is None:
                    raw_p = (row.get("paired_structural_effect") or {}).get(
                        "paired_randomization_p_value"
                    )
                if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool):
                    row["raw_model_internal_p_value"] = float(raw_p)
                    p_rows.append((index, float(raw_p)))
            if p_rows:
                adjusted = holm_adjust(value for _, value in p_rows)
                for (index, _), value in zip(p_rows, adjusted, strict=True):
                    ranked[index]["holm_adjusted_p_value"] = value
            for index, row in enumerate(ranked, start=1):
                row["rank"] = index
            return {
                "ranked_variants": ranked,
                "method": "worst_case_then_paired_then_coverage",
                "multiple_testing_method": "Holm family-wise correction over the ranked variant family using paired model-internal randomization p-values when available",
                "selection_policy": "constraint gate -> staged structural preselection -> robust/worst-case ranking -> Holm-adjusted family -> independent optimizer holdout",
                "automatic_application": False,
            }

        return self._invoke("rank_variants", request, work)

    def explain_recommendation(self, request: ExplainRecommendationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            evidence = request.evidence
            return {
                "recommendation_status": evidence.get(
                    "recommendation_status", "insufficient_evidence"
                ),
                "summary": (
                    f"{evidence.get('current_card', 'current card')} → "
                    f"{evidence.get('candidate_card', 'candidate card')}"
                ),
                "why": evidence.get("role_changes", []),
                "tradeoffs": {
                    "worst_case_effect": evidence.get("worst_case_effect"),
                    "remaining_uncertainty": evidence.get("remaining_uncertainty", []),
                    "provider_disagreement": evidence.get("provider_disagreement", False),
                },
                "truth_boundary": (
                    "Structural results are model estimates; Tactical Oracle is not an external "
                    "rules engine."
                ),
                "automatic_application": False,
            }

        return self._invoke("explain_recommendation", request, work)

    def export_recommendation_evidence(
        self, request: ExportRecommendationEvidenceInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target_dir = self.root / "data/runs/recommendations"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / Path(request.output_name).name
            atomic_write_json(
                target,
                {"schema_version": 1, "automatic_application": False, "evidence": request.evidence},
            )
            return {
                "path": str(target),
                "sha256": sha256_value(request.evidence),
                "canonical_files_modified": False,
            }

        return self._invoke("export_recommendation_evidence", request, work)

    def create_deck_improvement_report(
        self, request: CreateDeckImprovementReportInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target = self.report_dir / Path(request.output_name).name
            lines = [
                f"# Deck improvement report — {request.deck_id}",
                "",
                "Validation boundary: structural model estimates unless an individual "
                "evidence item explicitly records a higher executed level.",
                "",
                "No deck, inventory, or allocation change was applied.",
                "",
            ]
            for index, item in enumerate(request.evidence_items, start=1):
                lines += [
                    f"## Candidate {index}",
                    "",
                    f"- Status: `{item.get('recommendation_status', 'insufficient_evidence')}`",
                    f"- Swap: `{item.get('current_card')}` → `{item.get('candidate_card')}`",
                    f"- Worst-case effect: `{item.get('worst_case_effect')}`",
                    f"- Rules coverage: `{item.get('rules_coverage', 'structural_only')}`",
                    "",
                ]
            atomic_write_text(target, "\n".join(lines))
            return {
                "report_path": str(target),
                "evidence_items": len(request.evidence_items),
                "automatic_application": False,
            }

        return self._invoke(
            "create_deck_improvement_report", request, work, deck_ids=(request.deck_id,)
        )

    def create_report(self, request: CreateReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            safe_name = Path(request.output_name).name
            output = self.report_dir / safe_name
            lines = [
                f"# {request.title}",
                "",
                "All numerical simulation outputs are `structural_model_estimates`.",
                "",
                "## Evidence summary",
                "",
                "| # | Tool | Status | Invocation |",
                "|---:|---|---|---|",
            ]
            for index, response in enumerate(request.tool_responses, start=1):
                metadata = response.get("metadata", {})
                lines.append(
                    f"| {index} | {metadata.get('tool_name', 'unknown')} | "
                    f"{response.get('status', 'unknown')} | {metadata.get('invocation_id', '')} |"
                )
            decisions = [
                response.get("result", {}).get("decision")
                for response in request.tool_responses
                if response.get("result", {}).get("decision")
            ]
            if decisions:
                lines.extend(["", "## Validation decision", "", f"**{decisions[-1]}**", ""])
            for index, response in enumerate(request.tool_responses, start=1):
                lines.extend(
                    [
                        f"## Evidence {index}",
                        "",
                        "```json",
                        json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True),
                        "```",
                        "",
                    ]
                )
            output.write_text("\n".join(lines), encoding="utf-8")
            return {
                "report_path": str(output),
                "evidence_items": len(request.tool_responses),
                "decisions": decisions,
            }

        return self._invoke("create_report", request, work)
