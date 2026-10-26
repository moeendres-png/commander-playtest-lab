from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from commander_lab.agents.pilots import build_pilot
from commander_lab.meta.store import stable_deck_hash
from commander_lab.models import (
    AddOpponentVariantInput,
    AuditUnreferencedClaimsInput,
    BudgetBand,
    CompareDeckToMetaInput,
    CompareMetaPeriodsInput,
    ComparePackageVersionsInput,
    ComparePolicyVersionsInput,
    CompareVariantSensitivityInput,
    CompiledPilotPolicy,
    CompilePilotPolicyInput,
    CreateMetaSnapshotInput,
    CreateOpponentEnsembleInput,
    DetectOrphanedCardsInput,
    EvaluatePackageDensityInput,
    EvaluateRobustUpgradeInput,
    ExtractArchetypesInput,
    ExtractPackagesInput,
    ExtractPrimerRulesInput,
    GenerateEnsembleReportInput,
    GenerateMetaReportInput,
    GeneratePackageReportInput,
    GeneratePrimerConflictReportInput,
    GenerateProvenanceReportInput,
    ImportMetaDeckInput,
    ImportPrimerInput,
    ImportPrimerReferenceInput,
    ImportTournamentResultInput,
    InspectPackageInput,
    ListSupersededSourcesInput,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaSource,
    PilotConfig,
    PilotRule,
    PolicyEvalScenario,
    PrimerReference,
    QueryMetaCardsInput,
    QueryMetaPackagesInput,
    RunEnsembleMatchupsInput,
    RunPolicyEvalInput,
    ToolResponse,
    TournamentResult,
    TraceArtifactProvenanceInput,
    TraceRecommendationSourcesInput,
    ValidateEnsembleInput,
    ValidatePilotRulesInput,
    VerifySourceHashInput,
)
from commander_lab.models.opponent_ensembles import OpponentEnsemble, OpponentVariant
from commander_lab.primer import PrimerToPilotCompiler
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


class ServiceKnowledgeMixin(ServiceCore):
    def _primer_compiler(self) -> PrimerToPilotCompiler:
        return PrimerToPilotCompiler(self.root)

    def _load_primer_rules(self, relative: str) -> tuple[PilotRule, ...]:
        path = self._project_path(relative)
        if not path.exists():
            raise ToolExecutionError(f"pilot rule file missing: {relative}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rules", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ToolExecutionError(f"pilot rule file must contain a list: {relative}")
        return tuple(PilotRule.model_validate(row) for row in rows)

    def import_primer(self, request: ImportPrimerInput) -> ToolResponse:
        def work() -> dict[str, object]:
            document = self._primer_compiler().import_primer(
                source_path=request.source_path,
                primer_id=request.primer_id,
                source_id=request.source_id,
                title=request.title,
                commander=request.commander,
                deck_hash=request.deck_hash,
                format_band=request.format_band,
                primer_format=request.primer_format,
                license_notes=request.license_notes,
            )
            return {
                "primer": document.model_dump(mode="json"),
                "automatic_execution": False,
                "automatic_deck_application": False,
            }

        return self._invoke("import_primer", request, work)

    def extract_primer_rules(self, request: ExtractPrimerRulesInput) -> ToolResponse:
        def work() -> dict[str, object]:
            compiler = self._primer_compiler()
            registry = compiler.load_registry()
            document = next(
                (item for item in registry.primers if item.primer_id == request.primer_id), None
            )
            if document is None or document.source_path is None:
                raise ToolExecutionError(f"registered primer not found: {request.primer_id}")
            content = self._project_path(document.source_path).read_text(encoding="utf-8")
            rules = compiler.extract_rules(document, content=content)
            output_name = request.output_name or f"{request.primer_id}-automatic-candidates.json"
            target = self.root / "data/primer_rules/rules" / output_name
            atomic_write_json(
                target,
                {
                    "rules": [rule.model_dump(mode="json") for rule in rules],
                    "status": "needs_review",
                    "automatic_deck_application": False,
                },
            )
            return {
                "rules_path": str(target.relative_to(self.root)),
                "rule_count": len(rules),
                "active_rule_count": 0,
                "manual_review_required": True,
                "automatic_deck_application": False,
            }

        return self._invoke("extract_primer_rules", request, work)

    def validate_pilot_rules(self, request: ValidatePilotRulesInput) -> ToolResponse:
        def work() -> dict[str, object]:
            rules = self._load_primer_rules(request.rules_path)
            report = self._primer_compiler().validate_rules(
                rules,
                commander=request.commander,
                deck_hash=request.deck_hash,
                format_band=request.format_band,
            )
            return {
                "validation": report.model_dump(mode="json"),
                "automatic_deck_application": False,
            }

        return self._invoke("validate_pilot_rules", request, work)

    def compile_pilot_policy(self, request: CompilePilotPolicyInput) -> ToolResponse:
        def work() -> dict[str, object]:
            rules = tuple(
                rule for path in request.rule_paths for rule in self._load_primer_rules(path)
            )
            compiler = self._primer_compiler()
            policy = compiler.compile_policy(
                policy_id=request.policy_id,
                version=request.version,
                commander=request.commander,
                deck_hash=request.deck_hash,
                format_band=request.format_band,
                base_pilot_name=request.base_pilot_name,
                rules=rules,
                conflict_strategy=request.conflict_strategy,
            )
            path = compiler.write_policy(policy, request.output_name)
            return {
                "policy_path": str(path.relative_to(self.root)),
                "policy": policy.model_dump(mode="json"),
                "automatic_deck_application": False,
                "base_pilot_mutated": False,
            }

        return self._invoke("compile_pilot_policy", request, work)

    def compare_policy_versions(self, request: ComparePolicyVersionsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            older = CompiledPilotPolicy.model_validate_json(
                self._project_path(request.older_policy_path).read_text(encoding="utf-8")
            )
            newer = CompiledPilotPolicy.model_validate_json(
                self._project_path(request.newer_policy_path).read_text(encoding="utf-8")
            )
            return self._primer_compiler().compare_policy_versions(older, newer)

        return self._invoke("compare_policy_versions", request, work)

    def run_policy_eval(self, request: RunPolicyEvalInput) -> ToolResponse:
        def work() -> dict[str, object]:
            policy = CompiledPilotPolicy.model_validate_json(
                self._project_path(request.policy_path).read_text(encoding="utf-8")
            )
            deck = self._deck(request.deck_id)
            if policy.deck_hash != deck.deck_hash:
                raise ToolExecutionError(
                    f"policy deck_hash {policy.deck_hash} does not match current deck "
                    f"{deck.deck_hash}"
                )
            payload = json.loads(
                self._project_path(request.scenario_path).read_text(encoding="utf-8")
            )
            rows = payload.get("scenarios", payload) if isinstance(payload, dict) else payload
            parsed_scenarios = tuple(PolicyEvalScenario.model_validate(row) for row in rows)
            scenarios = tuple(
                scenario
                for scenario in parsed_scenarios
                if scenario.commander == policy.commander
                and scenario.deck_hash == policy.deck_hash
                and scenario.format_band == policy.format_band
            )
            if not scenarios:
                raise ToolExecutionError(
                    "scenario file contains no entries compatible with the selected policy"
                )
            pilot = build_pilot(
                PilotConfig(pilot_name=policy.base_pilot_name), strategy=request.strategy
            )
            results = self._primer_compiler().evaluate_policy(
                base_pilot=pilot,
                policy=policy,
                scenarios=scenarios,
                deck_cards=tuple(card.oracle_name for card in deck.cards),
                seed=request.seed,
            )
            target = self.root / "data/primer_rules/evals" / request.output_name
            atomic_write_json(
                target,
                {
                    "policy_id": policy.policy_id,
                    "results": [result.model_dump(mode="json") for result in results],
                    "improved_count": sum(result.improved for result in results),
                    "overlay_correct_count": sum(result.overlay_correct for result in results),
                    "scenario_count": len(results),
                    "automatic_deck_application": False,
                },
            )
            return {
                "eval_path": str(target.relative_to(self.root)),
                "scenario_count": len(results),
                "improved_count": sum(result.improved for result in results),
                "overlay_correct_count": sum(result.overlay_correct for result in results),
                "automatic_deck_application": False,
            }

        return self._invoke("run_policy_eval", request, work)

    def generate_primer_conflict_report(
        self, request: GeneratePrimerConflictReportInput
    ) -> ToolResponse:
        def work() -> dict[str, object]:
            rules = tuple(
                rule for path in request.rule_paths for rule in self._load_primer_rules(path)
            )
            conflicts = self._primer_compiler().detect_conflicts(rules)
            target = self.root / "data/primer_rules/conflicts" / request.output_name
            atomic_write_json(
                target,
                {
                    "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
                    "conflict_count": len(conflicts),
                    "resolution": "manual_or_explicit_strategy_required",
                    "automatic_deck_application": False,
                },
            )
            return {
                "report_path": str(target.relative_to(self.root)),
                "conflict_count": len(conflicts),
                "automatic_merge": False,
            }

        return self._invoke("generate_primer_conflict_report", request, work)

    def import_meta_deck(self, request: ImportMetaDeckInput) -> ToolResponse:
        def work() -> dict[str, object]:
            # Validate via the production snapshot model; write only to data/meta/provenance.
            deck = MetaDeckSnapshot(
                source_id=request.source_id,
                commander=request.commander,
                deck_hash=stable_deck_hash(request.decklist),
                retrieved_at=datetime.now(UTC),
                format_band=request.format_band,
                categories=request.categories,
                pod_size=request.pod_size,
                budget_band=BudgetBand(request.budget_band),
                event_name=request.event_name,
                placement=request.placement,
                player_count=request.player_count,
                decklist=request.decklist,
                provenance={"imported_by_tool": True, "source_path": request.snapshot_path},
            )
            path = self._stage_meta_record("staged_meta_decks.json", deck.model_dump(mode="json"))
            return {
                "staged_path": str(path.relative_to(self.root)),
                "deck_hash": deck.deck_hash,
                "automatic_deck_application": False,
            }

        return self._invoke(
            "import_meta_deck", request, work, estimate_type="structural_model_estimates"
        )

    def import_tournament_result(self, request: ImportTournamentResultInput) -> ToolResponse:
        def work() -> dict[str, object]:
            result = TournamentResult(
                source_id=request.source_id,
                event_name=request.event_name,
                format_band=request.format_band,
                pod_size=request.pod_size,
                placement=request.placement,
                player_count=request.player_count,
            )
            path = self._stage_meta_record(
                "staged_tournament_results.json", result.model_dump(mode="json")
            )
            return {
                "staged_path": str(path.relative_to(self.root)),
                "automatic_deck_application": False,
            }

        return self._invoke("import_tournament_result", request, work)

    def import_primer_reference(self, request: ImportPrimerReferenceInput) -> ToolResponse:
        def work() -> dict[str, object]:
            primer = PrimerReference(
                source_id=request.source_id,
                commander=request.commander,
                title=request.title,
                key_points=request.key_points,
                categories=request.categories,
                evidence_quality=MetaEvidenceRating.ESTABLISHED_PRIMER,
                transfer_limitations=(
                    "Primer notes are advisory only and never update decklists automatically.",
                ),
            )
            path = self._stage_meta_record(
                "staged_primer_references.json", primer.model_dump(mode="json")
            )
            return {
                "staged_path": str(path.relative_to(self.root)),
                "automatic_deck_application": False,
            }

        return self._invoke("import_primer_reference", request, work)

    def create_meta_snapshot(self, request: CreateMetaSnapshotInput) -> ToolResponse:
        def work() -> dict[str, object]:
            kb = self._meta_kb()
            seed_path = self.root / request.seed_file
            if not seed_path.exists():
                raise ToolExecutionError(f"meta seed file missing: {request.seed_file}")
            out_path = kb.snapshot_path(request.snapshot_id)
            if out_path.exists() and not request.allow_overwrite:
                raise ToolExecutionError(
                    f"immutable snapshot already exists: {request.snapshot_id}"
                )
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
            sources = tuple(MetaSource.model_validate(x) for x in payload.get("sources", []))
            decks = tuple(
                MetaDeckSnapshot.model_validate(x) for x in payload.get("deck_snapshots", [])
            )
            tournaments = tuple(
                TournamentResult.model_validate(x) for x in payload.get("tournament_results", [])
            )
            primers = tuple(
                PrimerReference.model_validate(x) for x in payload.get("primer_references", [])
            )
            from commander_lab.models import MetaArchetype, MetaPackage

            archetypes = tuple(
                MetaArchetype.model_validate(x) for x in payload.get("archetypes", [])
            )
            packages = tuple(MetaPackage.model_validate(x) for x in payload.get("packages", []))
            snapshot = kb.create_snapshot(
                snapshot_id=request.snapshot_id,
                sources=sources,
                deck_snapshots=decks,
                tournament_results=tournaments,
                primer_references=primers,
                archetypes=archetypes,
                packages=packages,
                notes=payload.get("notes"),
            )
            if out_path.exists() and request.allow_overwrite:
                out_path.rename(out_path.with_suffix(".superseded-local.json"))
            path = kb.write_snapshot(snapshot)
            return {
                "snapshot_id": snapshot.manifest.snapshot_id,
                "path": str(path.relative_to(self.root)),
                "source_count": len(snapshot.sources),
                "deck_snapshot_count": len(snapshot.deck_snapshots),
                "primer_count": len(snapshot.primer_references),
                "archetype_count": len(snapshot.archetypes),
                "card_frequency_count": len(snapshot.card_frequencies),
                "automatic_deck_application": False,
            }

        return self._invoke("create_meta_snapshot", request, work)

    def query_meta_cards(self, request: QueryMetaCardsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._meta_kb().query_cards(
                request.commander, request.format_band, request.min_frequency
            )

        return self._invoke("query_meta_cards", request, work)

    def query_meta_packages(self, request: QueryMetaPackagesInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._meta_kb().query_packages(request.commander, request.category)

        return self._invoke("query_meta_packages", request, work)

    def compare_deck_to_meta(self, request: CompareDeckToMetaInput) -> ToolResponse:
        def work() -> dict[str, object]:
            deck = self._deck(request.deck_id)
            cards = tuple(
                card.oracle_name
                for card in deck.cards
                if card.oracle_name not in deck.commander_names
            )
            result = self._meta_kb().compare_deck_to_meta(
                cards, commander=request.commander, format_band=request.format_band
            )
            result["local_deck_id"] = request.deck_id
            result["local_deck_hash"] = deck.deck_hash
            if request.deck_id in self.ACTIVE_OWN_DECK_IDS:
                package_result = self._package_extractor().packages_for_deck(
                    request.deck_id, include_machine_candidates=True
                )
                result["local_package_evaluations"] = package_result["evaluations"]
                result["machine_package_candidates"] = package_result["machine_candidates"]
            result["automatic_deck_application"] = False
            return result

        return self._invoke("compare_deck_to_meta", request, work, deck_ids=(request.deck_id,))

    def compare_meta_periods(self, request: CompareMetaPeriodsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._meta_kb().compare_periods(
                request.older_snapshot_id, request.newer_snapshot_id, commander=request.commander
            )

        return self._invoke("compare_meta_periods", request, work)

    def generate_meta_report(self, request: GenerateMetaReportInput) -> ToolResponse:
        def work() -> dict[str, object]:
            snapshot = self._meta_kb().load_snapshot()
            lines = [
                "# Meta Knowledge Base Report",
                "",
                f"Snapshot: `{snapshot.manifest.snapshot_id}`",
                f"Sources: {len(snapshot.sources)}",
                f"Deck snapshots: {len(snapshot.deck_snapshots)}",
                f"Primer references: {len(snapshot.primer_references)}",
                f"Archetypes: {len(snapshot.archetypes)}",
                "",
                "## Transfer policy",
                "",
                "Meta records are evidence only. They do not replace decklists, inventory, "
                "allocation, or local-opponent data.",
                "cEDH records are structure, package, sequencing and interaction benchmarks "
                "unless a matching local context is explicitly established.",
                "",
                "## Sources",
            ]
            for source in snapshot.sources:
                lines.append(f"- `{source.source_id}` — {source.title} ({source.evidence_quality})")
            lines.append("\n## Small-sample flags")
            for freq in snapshot.card_frequencies:
                if freq.small_sample:
                    lines.append(
                        f"- {freq.commander} / {freq.format_band}: sample_size={freq.sample_size}"
                    )
            target = self.root / "data/runs/meta_reports" / request.output_name
            atomic_write_text(target, "\n".join(lines) + "\n")
            return {
                "report_path": str(target.relative_to(self.root)),
                "snapshot_id": snapshot.manifest.snapshot_id,
                "automatic_deck_application": False,
            }

        return self._invoke("generate_meta_report", request, work)

    def extract_archetypes(self, request: ExtractArchetypesInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return (
                self._package_extractor()
                .extract_archetypes(request.deck_id)
                .model_dump(mode="json")
            )

        return self._invoke("extract_archetypes", request, work, deck_ids=(request.deck_id,))

    def extract_packages(self, request: ExtractPackagesInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._package_extractor().packages_for_deck(
                request.deck_id, include_machine_candidates=request.include_machine_candidates
            )

        return self._invoke("extract_packages", request, work, deck_ids=(request.deck_id,))

    def inspect_package(self, request: InspectPackageInput) -> ToolResponse:
        def work() -> dict[str, object]:
            extractor = self._package_extractor()
            package = extractor.inspect(request.package_id, request.version)
            payload = {
                "package": package.model_dump(mode="json"),
                "automatic_deck_application": False,
            }
            if request.deck_id:
                payload["evaluation"] = extractor.evaluate(
                    request.deck_id, request.package_id, version=request.version
                ).model_dump(mode="json")
            return payload

        return self._invoke(
            "inspect_package",
            request,
            work,
            deck_ids=((request.deck_id,) if request.deck_id else ()),
        )

    def compare_package_versions(self, request: ComparePackageVersionsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return (
                self._package_extractor()
                .compare_versions(request.package_id, request.older_version, request.newer_version)
                .model_dump(mode="json")
            )

        return self._invoke("compare_package_versions", request, work)

    def evaluate_package_density(self, request: EvaluatePackageDensityInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return (
                self._package_extractor()
                .evaluate(request.deck_id, request.package_id, version=request.version)
                .model_dump(mode="json")
            )

        return self._invoke("evaluate_package_density", request, work, deck_ids=(request.deck_id,))

    def detect_orphaned_cards(self, request: DetectOrphanedCardsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._package_extractor().detect_orphans(request.deck_id)

        return self._invoke("detect_orphaned_cards", request, work, deck_ids=(request.deck_id,))

    def generate_package_report(self, request: GeneratePackageReportInput) -> ToolResponse:
        def work() -> dict[str, object]:
            report = self._package_extractor().generate_report(request.deck_id)
            target = self.root / "data/runs/package_reports" / request.output_name
            atomic_write_text(target, report)
            return {
                "report_path": str(target.relative_to(self.root)),
                "automatic_deck_application": False,
                "estimate_type": "structural_model_estimates",
            }

        return self._invoke("generate_package_report", request, work, deck_ids=(request.deck_id,))

    def create_opponent_ensemble(self, request: CreateOpponentEnsembleInput) -> ToolResponse:
        def work() -> dict[str, object]:
            ensemble = OpponentEnsemble.model_validate_json(
                self._project_path(request.source_path).read_text(encoding="utf-8")
            )
            path = self._opponent_ensembles().save(ensemble)
            return {
                "ensemble_id": ensemble.ensemble_id,
                "path": str(path.relative_to(self.root)),
                "variant_count": len(ensemble.variants),
                "automatic_profile_overwrite": False,
            }

        return self._invoke("create_opponent_ensemble", request, work)

    def add_opponent_variant(self, request: AddOpponentVariantInput) -> ToolResponse:
        def work() -> dict[str, object]:
            variant = OpponentVariant.model_validate_json(
                self._project_path(request.variant_path).read_text(encoding="utf-8")
            )
            e = self._opponent_ensembles().add_variant(
                request.ensemble_id, variant, request.new_ensemble_id
            )
            return {
                "ensemble_id": e.ensemble_id,
                "version": e.version,
                "variant_count": len(e.variants),
                "automatic_profile_overwrite": False,
            }

        return self._invoke("add_opponent_variant", request, work)

    def validate_ensemble(self, request: ValidateEnsembleInput) -> ToolResponse:
        return self._invoke(
            "validate_ensemble",
            request,
            lambda: self._opponent_ensembles().validate(request.ensemble_id),
        )

    def run_ensemble_matchups(self, request: RunEnsembleMatchupsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return (
                self._opponent_ensembles()
                .run_matchups(self._deck(request.deck_id), request.ensemble_id, request.seed)
                .model_dump(mode="json")
            )

        return self._invoke(
            "run_ensemble_matchups",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            estimate_type="structural_model_estimates",
        )

    def compare_variant_sensitivity(self, request: CompareVariantSensitivityInput) -> ToolResponse:
        return self._invoke(
            "compare_variant_sensitivity",
            request,
            lambda: self._opponent_ensembles().compare_sensitivity(
                self._deck(request.deck_id), request.ensemble_id, request.seed
            ),
            deck_ids=(request.deck_id,),
            seed=request.seed,
        )

    def evaluate_robust_upgrade(self, request: EvaluateRobustUpgradeInput) -> ToolResponse:
        def work() -> dict[str, object]:
            return self._opponent_ensembles().evaluate_robust_upgrade(
                self._deck(request.baseline_deck_id),
                self._deck(request.candidate_deck_id),
                request.ensemble_id,
                request.seed,
            )

        return self._invoke(
            "evaluate_robust_upgrade",
            request,
            work,
            deck_ids=(request.baseline_deck_id, request.candidate_deck_id),
            seed=request.seed,
        )

    def generate_ensemble_report(self, request: GenerateEnsembleReportInput) -> ToolResponse:
        def work() -> dict[str, object]:
            target = self.root / "data/opponent_ensembles" / Path(request.output_name).name
            atomic_write_text(target, self._opponent_ensembles().report(request.ensemble_id))
            return {
                "report_path": str(target.relative_to(self.root)),
                "ensemble_id": request.ensemble_id,
                "automatic_profile_overwrite": False,
            }

        return self._invoke("generate_ensemble_report", request, work)

    def trace_artifact_provenance(self, request: TraceArtifactProvenanceInput) -> ToolResponse:
        return self._invoke(
            "trace_artifact_provenance",
            request,
            lambda: self._provenance().trace(request.artifact_id),
        )

    def trace_recommendation_sources(
        self, request: TraceRecommendationSourcesInput
    ) -> ToolResponse:
        return self._invoke(
            "trace_recommendation_sources",
            request,
            lambda: self._provenance().recommendation_sources(request.recommendation_id),
        )

    def list_superseded_sources(self, request: ListSupersededSourcesInput) -> ToolResponse:
        return self._invoke(
            "list_superseded_sources",
            request,
            lambda: {
                "supersessions": self._provenance().list_superseded(),
                "historical_sources_retained": True,
            },
        )

    def verify_source_hash(self, request: VerifySourceHashInput) -> ToolResponse:
        return self._invoke(
            "verify_source_hash",
            request,
            lambda: self._provenance().verify_source_hash(
                request.source_id, request.candidate_path
            ),
        )

    def generate_provenance_report(self, request: GenerateProvenanceReportInput) -> ToolResponse:
        def work() -> dict[str, object]:
            store = self._provenance()
            graph = store.load()
            store.validate(graph)
            audit = store.audit_claims()
            target = self.root / "data/runs/provenance_reports" / Path(request.output_name).name
            lines = [
                "# Provenance Report",
                "",
                f"Graph: `{graph.graph_id}`",
                f"Sources: {len(graph.sources)}",
                f"Artifacts: {len(graph.artifacts)}",
                f"Derived records: {len(graph.derived_data)}",
                f"Transformations: {len(graph.transformations)}",
                f"Citations: {len(graph.citations)}",
                f"Supersessions: {len(graph.supersessions)}",
                "",
                f"Unreferenced claims: {len(audit['unreferenced_claims'])}",
                "",
                "Historical sources are retained and superseded records remain traceable.",
            ]
            atomic_write_text(target, "\n".join(lines) + "\n")
            return {
                "report_path": str(target.relative_to(self.root)),
                "graph_hash": sha256_value(graph.model_dump(mode="json")),
                "audit": audit,
            }

        return self._invoke("generate_provenance_report", request, work)

    def audit_unreferenced_claims(self, request: AuditUnreferencedClaimsInput) -> ToolResponse:
        def work() -> dict[str, object]:
            result = self._provenance().audit_claims()
            if request.fail_on_unreferenced and not result["passed"]:
                raise ToolExecutionError("unreferenced claims detected")
            return result

        return self._invoke("audit_unreferenced_claims", request, work)
