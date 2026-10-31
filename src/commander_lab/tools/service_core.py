from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from commander_lab import __version__
from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import (
    ENGINE_VERSION,
    load_project_structural_decks,
)
from commander_lab.meta import MetaKnowledgeBase
from commander_lab.models import (
    CandidateProfile,
    CardRole,
    Collection,
    CostLimits,
    Deck,
    OptimizationConstraints,
    OptimizationVariant,
    PairedVariantInput,
    PilotConfig,
    StructuralDeckProfile,
    ToolExecutionMetadata,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
)
from commander_lab.models.run_identity import CanonicalInputStatus, IdentityStatus, RunIdentity
from commander_lab.opponent_ensembles import OpponentEnsembleStore
from commander_lab.optimization import (
    DEFAULT_CONSTRAINTS,
    PairedMetrics,
    default_constraints,
    load_candidate_inventory,
    objective_vector,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.owner_data import (
    is_owner_data,
    owner_data_path,
    owner_data_root,
)
from commander_lab.packages import ArchetypePackageExtractor
from commander_lab.provenance import ProvenanceStore
from commander_lab.storage import (
    atomic_write_json,
    load_model,
    sha256_value,
)
from commander_lab.storage.run_identity import normalize_run_paths, sha256_run_value

from .candidates import (
    load_candidate_profiles,
    load_canonical_inventory_quantities,
    load_current_candidate_eligibility,
    load_current_optimization_availability,
)

if TYPE_CHECKING:
    pass

EstimateType = Literal[
    "structural_model_estimates",
    "tactical_oracle_results",
    "external_rules_engine_results",
]


class ToolExecutionError(RuntimeError):
    pass


class ApprovalRequired(ToolExecutionError):
    pass


def _deterministic_structural_run_id(prefix: str, request: Any) -> str:
    """Separate deterministic simulation identity from unique artifact storage."""
    payload = (
        request.model_dump(mode="json", exclude={"approval_token"})
        if hasattr(request, "model_dump")
        else request
    )
    digest = sha256_value({"engine_version": ENGINE_VERSION, "tool": prefix, "request": payload})
    return f"{prefix}-{digest[:16]}"


class ServiceCore:
    """Shared state and helpers of the deterministic local Function Tool service."""

    if TYPE_CHECKING:

        @property
        def git_commit(self) -> str | None: ...
        @property
        def git_tree(self) -> str | None: ...
        @property
        def tracked_worktree_dirty(self) -> bool: ...

    ACTIVE_OWN_DECK_IDS = ("rogshai/current",)

    FROZEN_OPPONENT_ONLY_DECK_IDS = frozenset({"kaervek/current"})

    COVERAGE_VERSION_PREFIXES: ClassVar[dict[str, tuple[str, ...]]] = {
        "korvold/current": ("korvold/current-",),
        "rogshai/current": ("rogshai/current-",),
        "kaervek/current": ("kaervek/maintained-",),
        "opponent/morcant-elves": ("opponent/alen___high_perfect_morcant/",),
        "opponent/cosmic-spiderman-midbudget": ("opponent/cosmic_spider_man/",),
        "opponent/blight-curse-precon": ("opponent/blight_curse/",),
        "opponent/doom-prevails-precon": ("opponent/doom_prevails/",),
        "opponent/dance-elements-precon": ("opponent/dance_of_the_elements/",),
        "opponent/wakanda-forever-precon": ("opponent/wakanda_forever/",),
    }

    def __init__(self, root: str | Path, *, limits: CostLimits | None = None) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or self._load_limits()
        self.decks = load_project_structural_decks(
            self.root,
            include_synthetic_fixtures=True,
            include_current_opponents=True,
        )
        self.candidates = load_candidate_profiles(self.root)
        current_availability = load_current_optimization_availability(self.root)
        current_eligibility = load_current_candidate_eligibility(self.root)
        if current_availability:
            # Current Drive projection already subtracts canonical own-deck allocations and
            # opponent reservations. Do not subtract baseline cards a second time.
            self.candidate_inventory = current_availability
        else:
            canonical_inventory = load_canonical_inventory_quantities(self.root)
            if canonical_inventory:
                baseline_required: Counter[str] = Counter()
                for deck_id in self.ACTIVE_OWN_DECK_IDS:
                    deck = self.decks.get(deck_id)
                    if deck is None:
                        continue
                    baseline_required.update(
                        card.oracle_name
                        for card in deck.cards
                        if card.oracle_name
                        not in {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
                    )
                self.candidate_inventory = {
                    name: max(0, quantity - baseline_required.get(name, 0))
                    for name, quantity in canonical_inventory.items()
                }
            else:
                self.candidate_inventory = load_candidate_inventory(self.root)
        filtered_candidates = {}
        for candidate_id, candidate in self.candidates.items():
            if self.candidate_inventory.get(candidate.card.oracle_name, 0) <= 0:
                continue
            allowed = tuple(
                deck_id
                for deck_id in candidate.allowed_deck_ids
                if (
                    not current_eligibility
                    or candidate.card.oracle_name in current_eligibility.get(deck_id, set())
                )
                and (
                    deck_id not in self.decks
                    or candidate.card.oracle_name
                    not in {card.oracle_name for card in self.decks[deck_id].cards}
                )
            )
            if not allowed:
                continue
            filtered_candidates[candidate_id] = candidate.model_copy(
                update={"allowed_deck_ids": allowed}
            )
        self.candidates = filtered_candidates
        self.verified_candidate_names = {
            candidate.card.oracle_name
            for candidate in self.candidates.values()
            if candidate.physical_status
            in {"local_project_verified_owned", "canonical_inventory_verified_owned"}
            and self.candidate_inventory.get(candidate.card.oracle_name, 0) > 0
        }
        protected_path = self.root / "config/protected_cards.json"
        self.protected_cards = (
            json.loads(protected_path.read_text(encoding="utf-8"))
            if protected_path.exists()
            else {}
        )
        stale_protected: dict[str, list[str]] = {}
        for deck_id, protected in self.protected_cards.items():
            deck = self.decks.get(deck_id)
            if deck is None:
                stale_protected[deck_id] = list(protected)
                continue
            current_names = {card.oracle_name for card in deck.cards}
            missing = sorted(str(name) for name in protected if str(name) not in current_names)
            if missing:
                stale_protected[deck_id] = missing
        if stale_protected:
            raise ValueError(f"protected-card metadata is stale: {stale_protected}")
        self.manifest = json.loads(
            (self.root / "data/decks/manifest.json").read_text(encoding="utf-8")
        )
        self.trace_dir = self.root / "data/runs/openai_traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.root / "data/runs/reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _provenance(self) -> ProvenanceStore:
        return ProvenanceStore(self.root)

    def _opponent_ensembles(self) -> OpponentEnsembleStore:
        return OpponentEnsembleStore(self.root)

    def _load_limits(self) -> CostLimits:
        path = self.root / "config/openai_workflow.json"
        if not path.exists():
            return CostLimits()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CostLimits.model_validate(payload.get("budgets", payload))

    @staticmethod
    def _raw_file_hash(path: Path) -> str:
        if not path.is_file():
            raise ToolExecutionError(f"run identity source is missing: {path}")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _aggregate_file_hash(self, paths: tuple[Path, ...]) -> str:
        rows = []
        for path in sorted(paths, key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            rows.append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": self._raw_file_hash(path),
                }
            )
        if not rows:
            raise ToolExecutionError("run identity requires at least one existing source file")
        return sha256_value(rows)

    def _run_identity(
        self,
        scenario: object,
        deck_ids: tuple[str, ...],
        *,
        tool_name: str = "unspecified",
        estimate_type: EstimateType = "structural_model_estimates",
    ) -> dict[str, Any]:
        scenario_payload = (
            scenario.model_dump(mode="python", exclude_none=False)
            if hasattr(scenario, "model_dump")
            else scenario
        )
        if not isinstance(scenario_payload, dict):
            scenario_payload = {"value": scenario_payload}
        scenario_payload = normalize_run_paths(scenario_payload, root=self.root)

        source_registry = owner_data_path(self.root, "data/sync/current_sources.json")
        source_payload = json.loads(source_registry.read_text(encoding="utf-8"))
        inventory_spec = source_payload.get("sources", {}).get("inventory", {})
        inventory_import_path = inventory_spec.get("import_path")
        inventory_source_id = inventory_spec.get("drive_file_id")
        if not inventory_import_path:
            raise ToolExecutionError("canonical inventory source has no import_path")
        if not inventory_source_id:
            raise ToolExecutionError("canonical inventory source has no drive_file_id")
        inventory_path = self._project_path(str(inventory_import_path))

        pilot_registry = self.root / "data/pilots/pilot_registry.json"
        robustness_registry = self.root / "data/robustness/pilot_and_politics_registry.json"
        opponent_registry = self.root / "data/opponents/opponent_registry.json"
        opponent_profiles = self.root / "data/opponents/current_structural_profiles.json"
        deck_manifest = self.root / "data/decks/manifest.json"
        allocation_snapshot = owner_data_path(
            self.root, "data/collections/current_deck_allocations.json"
        )
        structural_profiles = self.root / "data/cards/structural_role_profiles.json"
        candidate_snapshot = self.root / "data/cards/phase5_upgrade_candidates.json"
        meta_latest = self.root / "data/meta/manifests/latest.json"
        mulligan_registry = self.root / "data/mulligan_lab/policies/policy_registry.json"
        robustness_policy = self.root / "data/robustness/policy_tournament_result.json"

        meta_pointer = json.loads(meta_latest.read_text(encoding="utf-8"))
        meta_path = self._project_path(str(meta_pointer["path"]))
        pilot_payload = json.loads(pilot_registry.read_text(encoding="utf-8"))
        pilot_parameter_hashes = {
            str(row["profile_id"]): str(row["parameter_hash"])
            for row in pilot_payload.get("profiles", [])
            if row.get("profile_id") and row.get("parameter_hash")
        }
        if not pilot_parameter_hashes:
            raise ToolExecutionError("pilot registry contains no parameter hashes")

        policy_paths = (
            *tuple((self.root / "data/primer_rules/policies").glob("*.json")),
            mulligan_registry,
            robustness_policy,
        )
        policy_hash = self._aggregate_file_hash(policy_paths)
        ensemble_paths = tuple((self.root / "data/opponent_ensembles").glob("*.json"))
        ensemble_registry_hash = self._aggregate_file_hash(ensemble_paths)
        data_snapshot_hashes = {
            "deck_manifest": self._raw_file_hash(deck_manifest),
            "allocation_snapshot": self._raw_file_hash(allocation_snapshot),
            "structural_profiles": self._raw_file_hash(structural_profiles),
            "candidate_snapshot": self._raw_file_hash(candidate_snapshot),
            "source_registry": self._raw_file_hash(source_registry),
            "pilot_registry": self._raw_file_hash(pilot_registry),
            "robustness_registry": self._raw_file_hash(robustness_registry),
            "opponent_registry": self._raw_file_hash(opponent_registry),
            "opponent_profiles": self._raw_file_hash(opponent_profiles),
            "opponent_ensembles": ensemble_registry_hash,
            "meta_manifest": self._raw_file_hash(meta_latest),
            "meta_snapshot": self._raw_file_hash(meta_path),
            "policy_set": policy_hash,
        }
        for source_name, spec in source_payload.get("sources", {}).items():
            import_path = spec.get("import_path") if isinstance(spec, dict) else None
            if import_path:
                data_snapshot_hashes[f"source:{source_name}"] = self._raw_file_hash(
                    self._project_path(str(import_path))
                )

        referenced_ids: list[str] = list(deck_ids)
        for key in ("deck_ids", "opponent_deck_ids"):
            value = scenario_payload.get(key)
            if isinstance(value, list):
                referenced_ids.extend(str(item) for item in value)
        for key in ("deck_id", "baseline_deck_id", "candidate_deck_id", "variant_deck_id"):
            value = scenario_payload.get(key)
            if isinstance(value, str):
                referenced_ids.append(value)
        unique_ids = tuple(dict.fromkeys(referenced_ids))
        known_ids = tuple(deck_id for deck_id in unique_ids if deck_id in self.decks)

        deck_hashes = {deck_id: self._deck(deck_id).deck_hash for deck_id in known_ids}
        primary_id = next((deck_id for deck_id in unique_ids if deck_id in self.decks), None)
        explicit_opponents = scenario_payload.get("opponent_deck_ids")
        implicit_pod_tools = {
            "run_matchup_batch",
            "run_sensitivity",
            "run_engine_backed_matchup",
        }
        if isinstance(explicit_opponents, list):
            opponent_profile_ids = tuple(
                str(deck_id) for deck_id in explicit_opponents if str(deck_id) in self.decks
            )
        elif tool_name in implicit_pod_tools:
            opponent_profile_ids = tuple(
                deck_id for deck_id in known_ids if primary_id is not None and deck_id != primary_id
            )
        else:
            opponent_profile_ids = ()
        opponent_hashes = {
            deck_id: self._deck(deck_id).deck_hash for deck_id in opponent_profile_ids
        }

        commander_payload = {
            deck_id: {
                "commanders": self._deck(deck_id).commander_names,
                "base_costs": self._deck(deck_id).commander_base_costs,
            }
            for deck_id in known_ids
        }
        commander_configuration_hash = (
            sha256_run_value(commander_payload, root=self.root) if commander_payload else None
        )

        opponent_ensemble_tools = {
            "add_opponent_variant",
            "validate_ensemble",
            "run_ensemble_matchups",
            "compare_variant_sensitivity",
            "evaluate_robust_upgrade",
            "generate_ensemble_report",
        }
        ensemble_id = scenario_payload.get("opponent_ensemble_id")
        if ensemble_id is None and tool_name in opponent_ensemble_tools:
            ensemble_id = scenario_payload.get("ensemble_id")
        opponent_ensemble_hash: str | None = None
        if isinstance(ensemble_id, str) and ensemble_id:
            ensemble_path = self.root / "data/opponent_ensembles" / f"{ensemble_id}.json"
            if ensemble_path.is_file():
                opponent_ensemble_hash = self._raw_file_hash(ensemble_path)

        selected_profiles: list[dict[str, Any]] = []
        requested_pilot_names = scenario_payload.get("pilot_names")
        requested_profile_id = scenario_payload.get("pilot_profile_id")
        if isinstance(requested_pilot_names, list):
            wanted = {str(name) for name in requested_pilot_names}
            selected_profiles.extend(
                row for row in pilot_payload.get("profiles", []) if row.get("pilot_name") in wanted
            )
        elif isinstance(requested_profile_id, str) and requested_profile_id not in {"", "baseline"}:
            selected_profiles.extend(
                row
                for row in pilot_payload.get("profiles", [])
                if row.get("profile_id") == requested_profile_id
            )
        else:
            families = {
                deck_id.split("/", 1)[0]
                for deck_id in known_ids
                if deck_id.startswith(("korvold/", "rogshai/"))
            }
            selected_profiles.extend(
                row
                for row in pilot_payload.get("profiles", [])
                if row.get("is_baseline") and row.get("commander_family") in families
            )
        selected_profiles = list(
            {str(row.get("profile_id")): row for row in selected_profiles}.values()
        )
        if selected_profiles:
            pilot_name = ",".join(sorted(str(row.get("pilot_name")) for row in selected_profiles))
            pilot_version = ",".join(sorted(str(row.get("version")) for row in selected_profiles))
            pilot_parameter_hash = sha256_run_value(
                [
                    {
                        "profile_id": row.get("profile_id"),
                        "parameter_hash": row.get("parameter_hash"),
                    }
                    for row in sorted(
                        selected_profiles,
                        key=lambda item: str(item.get("profile_id")),
                    )
                ],
                root=self.root,
            )
        elif scenario_payload.get("pilot_strength") or scenario_payload.get("pilot_mode"):
            pilot_name = "structural_configured_pilot"
            pilot_version = str(scenario_payload.get("pilot_strength") or "unspecified")
            pilot_parameter_hash = sha256_run_value(
                {
                    "pilot_strength": scenario_payload.get("pilot_strength"),
                    "pilot_mode": scenario_payload.get("pilot_mode"),
                },
                root=self.root,
            )
        else:
            pilot_name = None
            pilot_version = None
            pilot_parameter_hash = None

        scenario_set_id: str | None = None
        scenario_set_hash: str | None = None
        scenario_path_value = scenario_payload.get("scenario_path")
        if isinstance(scenario_path_value, str) and scenario_path_value:
            scenario_path = self._project_path(scenario_path_value.replace("project://", ""))
            if scenario_path.is_file():
                scenario_set_id = scenario_path.relative_to(self.root).as_posix()
                scenario_set_hash = self._raw_file_hash(scenario_path)
        elif (
            tool_name.startswith("run_")
            or tool_name.startswith("compare_")
            or tool_name.startswith("validate_")
        ):
            scenario_set_id = f"inline:{tool_name}"
            scenario_set_hash = sha256_run_value(scenario_payload, root=self.root)

        seed_value = scenario_payload.get("seed")
        seed = int(seed_value) if isinstance(seed_value, int) and seed_value >= 0 else None
        seed_values: list[int] = []
        for key in ("seeds", "sensitivity_seeds"):
            value = scenario_payload.get(key)
            if isinstance(value, list):
                seed_values.extend(
                    int(item) for item in value if isinstance(item, int) and item >= 0
                )
        if seed is not None and not seed_values:
            seed_values = [seed]
        seed_set_hash = sha256_run_value(seed_values, root=self.root) if seed_values else None

        pod_size_value = scenario_payload.get("pod_size")
        if isinstance(pod_size_value, int):
            pod_size = pod_size_value
        elif isinstance(explicit_opponents, list) and primary_id is not None:
            pod_size = 1 + len(opponent_profile_ids)
        elif tool_name in implicit_pod_tools and known_ids:
            pod_size = len(known_ids)
        elif tool_name in {"run_goldfish"}:
            pod_size = 1
        else:
            pod_size = None
        seat_value = scenario_payload.get("starting_player_seat")
        if not isinstance(seat_value, int):
            seat_value = scenario_payload.get("seat")
        if not isinstance(seat_value, int):
            seat_position = scenario_payload.get("seat_position")
            seat_value = int(seat_position) if isinstance(seat_position, int) else None
        if scenario_payload.get("starting_player_rotation") is True or (
            seed is not None and pod_size
        ):
            turn_order_policy = "deterministic_rotation_or_explicit_seat"
        elif seat_value is not None:
            turn_order_policy = "explicit_seat"
        else:
            turn_order_policy = None

        engine_mode: str | None
        engine_provider: str | None
        engine_provider_version_or_pin: str | None
        if tool_name == "run_engine_backed_matchup":
            engine_mode = "external"
            provider_value = scenario_payload.get("provider")
            engine_provider = str(provider_value) if provider_value else None
            engine_provider_version_or_pin = None
        elif "tactical" in tool_name or estimate_type == "tactical_oracle_results":
            engine_mode = "tactical_oracle"
            engine_provider = "tactical_oracle"
            engine_provider_version_or_pin = "project_tactical_oracle"
        elif seed is not None or tool_name in {"run_goldfish", "run_matchup_batch"}:
            engine_mode = "structural"
            engine_provider = "commander_lab_structural"
            engine_provider_version_or_pin = ENGINE_VERSION
        else:
            engine_mode = None
            engine_provider = None
            engine_provider_version_or_pin = None

        rules_paths = (
            self.root / "data/rules/golden_rules_scenarios.json",
            self.root / "data/rules/project_critical_interactions.json",
            self.root / "data/evals/differential/rules_cases.json",
        )
        tactical_fixture_version = self._aggregate_file_hash(rules_paths)

        stale_reasons: list[str] = []
        for source_name, spec in source_payload.get("sources", {}).items():
            if not isinstance(spec, dict) or not spec.get("import_path"):
                continue
            imported_path = self._project_path(str(spec["import_path"]))
            imported_payload = json.loads(imported_path.read_text(encoding="utf-8"))
            if imported_payload.get("source_drive_file_id") != spec.get("drive_file_id"):
                stale_reasons.append(f"canonical source id mismatch: {source_name}")
            if imported_payload.get("source_sha256") != spec.get("sha256"):
                stale_reasons.append(f"canonical source hash mismatch: {source_name}")

        deck_manifest_payload = json.loads(deck_manifest.read_text(encoding="utf-8"))
        expected_decks = deck_manifest_payload.get("decks", {})
        source_deck_hashes = (
            source_payload.get("sources", {})
            .get("korvold_rogshai_decks", {})
            .get("deck_hashes", {})
        )
        for deck_id, actual_hash in deck_hashes.items():
            manifest_row = expected_decks.get(deck_id)
            if isinstance(manifest_row, dict) and manifest_row.get("deck_hash") != actual_hash:
                stale_reasons.append(f"deck manifest hash mismatch: {deck_id}")
            if deck_id in source_deck_hashes and source_deck_hashes.get(deck_id) != actual_hash:
                stale_reasons.append(f"canonical source deck hash mismatch: {deck_id}")
        if ensemble_id and opponent_ensemble_hash is None:
            stale_reasons.append(f"opponent ensemble missing: {ensemble_id}")
        for row in selected_profiles:
            supported = set(row.get("supported_deck_hashes", []))
            family = str(row.get("commander_family", ""))
            relevant = [
                deck_hashes[deck_id] for deck_id in deck_hashes if deck_id.startswith(f"{family}/")
            ]
            if relevant and not any(deck_hash in supported for deck_hash in relevant):
                stale_reasons.append(
                    f"pilot profile stale for current deck: {row.get('profile_id')}"
                )
        if self.tracked_worktree_dirty:
            stale_reasons.append("tracked software worktree differs from recorded git tree")

        historical_replay = bool(scenario_payload.get("historical_replay", False))
        canonical_required = bool(scenario_payload.get("canonical_inputs_required", True))
        if historical_replay:
            canonical_status = CanonicalInputStatus.HISTORICAL_REPLAY
        elif stale_reasons:
            canonical_status = CanonicalInputStatus.STALE
        else:
            canonical_status = CanonicalInputStatus.CURRENT
        if stale_reasons and canonical_required and not historical_replay:
            raise ToolExecutionError(
                "stale canonical inputs rejected: " + "; ".join(sorted(set(stale_reasons)))
            )

        software_commit = self.git_commit
        software_tree = self.git_tree
        component_status: dict[str, IdentityStatus] = {}

        def status(
            name: str,
            value: Any,
            *,
            required: bool = False,
            applicable: bool = True,
        ) -> None:
            if not applicable:
                component_status[name] = IdentityStatus.NOT_APPLICABLE
            elif value is None or value == () or value == {}:
                component_status[name] = (
                    IdentityStatus.MISSING_REQUIRED if required else IdentityStatus.UNKNOWN
                )
            else:
                component_status[name] = IdentityStatus.PRESENT

        status("software_commit", software_commit, required=True)
        status("software_tree", software_tree, required=True)
        status("package_version", __version__, required=True)
        status("deck_hashes", deck_hashes, required=bool(known_ids), applicable=bool(known_ids))
        status(
            "commander_configuration_hash",
            commander_configuration_hash,
            required=bool(known_ids),
            applicable=bool(known_ids),
        )
        status("inventory_source_id", inventory_source_id, required=True)
        inventory_hash = self._raw_file_hash(inventory_path)
        status("inventory_hash", inventory_hash, required=True)
        status(
            "opponent_profile_ids",
            opponent_profile_ids,
            required=bool(opponent_profile_ids),
            applicable=bool(opponent_profile_ids),
        )
        status(
            "opponent_profile_hashes",
            opponent_hashes,
            required=bool(opponent_profile_ids),
            applicable=bool(opponent_profile_ids),
        )
        status(
            "opponent_ensemble_hash",
            opponent_ensemble_hash,
            required=bool(ensemble_id),
            applicable=bool(ensemble_id),
        )
        status("pilot_name", pilot_name, applicable=pilot_name is not None)
        status("pilot_version", pilot_version, applicable=pilot_name is not None)
        status("pilot_parameter_hash", pilot_parameter_hash, applicable=pilot_name is not None)
        status("policy_hash", policy_hash, required=True)
        status("scenario_set_id", scenario_set_id, applicable=scenario_set_id is not None)
        status("scenario_set_hash", scenario_set_hash, applicable=scenario_set_id is not None)
        status("pod_size", pod_size, applicable=pod_size is not None)
        status("seat", seat_value, applicable=seat_value is not None)
        status("turn_order_policy", turn_order_policy, applicable=turn_order_policy is not None)
        status("seed", seed, applicable=seed is not None)
        status("seed_set_hash", seed_set_hash, applicable=seed is not None or bool(seed_values))
        simulation_config_hash = sha256_run_value(scenario_payload, root=self.root)
        status("simulation_config_hash", simulation_config_hash, required=True)
        status("model_version", ENGINE_VERSION, required=True)
        status("engine_mode", engine_mode, applicable=engine_mode is not None)
        status("engine_provider", engine_provider, applicable=engine_mode is not None)
        status(
            "engine_provider_version_or_pin",
            engine_provider_version_or_pin,
            required=engine_mode == "external" and not stale_reasons,
            applicable=engine_mode is not None,
        )
        engine_capability_hash = None
        status(
            "engine_capability_hash",
            engine_capability_hash,
            applicable=engine_mode in {"external", "tactical_oracle"},
        )
        status(
            "tactical_fixture_version",
            tactical_fixture_version,
            applicable=engine_mode in {"external", "tactical_oracle"},
        )
        data_source_manifest_hash = data_snapshot_hashes["source_registry"]
        status("data_source_manifest_hash", data_source_manifest_hash, required=True)

        # External provider version/capability are intentionally unknown before a real provider
        # handshake. They may not be promoted to external validation by this metadata alone.
        if engine_mode == "external":
            component_status["engine_provider_version_or_pin"] = IdentityStatus.UNKNOWN
            component_status["engine_capability_hash"] = IdentityStatus.UNKNOWN

        run_payload = {
            "schema_version": "1.0.0",
            "software_commit": software_commit,
            "software_tree": software_tree,
            "package_version": __version__,
            "deck_hashes": deck_hashes,
            "commander_configuration_hash": commander_configuration_hash,
            "inventory_source_id": str(inventory_source_id),
            "inventory_hash": inventory_hash,
            "opponent_profile_ids": opponent_profile_ids,
            "opponent_profile_hashes": opponent_hashes,
            "opponent_ensemble_hash": opponent_ensemble_hash,
            "pilot_name": pilot_name,
            "pilot_version": pilot_version,
            "pilot_parameter_hash": pilot_parameter_hash,
            "policy_hash": policy_hash,
            "scenario_set_id": scenario_set_id,
            "scenario_set_hash": scenario_set_hash,
            "pod_size": pod_size,
            "seat": seat_value,
            "turn_order_policy": turn_order_policy,
            "seed": seed,
            "seed_set_hash": seed_set_hash,
            "simulation_config_hash": simulation_config_hash,
            "model_version": ENGINE_VERSION,
            "engine_mode": engine_mode,
            "engine_provider": engine_provider,
            "engine_provider_version_or_pin": engine_provider_version_or_pin,
            "engine_capability_hash": engine_capability_hash,
            "tactical_fixture_version": tactical_fixture_version
            if engine_mode in {"external", "tactical_oracle"}
            else None,
            "data_source_manifest_hash": data_source_manifest_hash,
            "component_status": component_status,
            "canonical_input_status": canonical_status,
            "stale_reasons": tuple(sorted(set(stale_reasons))),
            "historical_replay": historical_replay,
        }
        semantic_hash = sha256_run_value(run_payload, root=self.root)
        run_identity = RunIdentity(**run_payload, run_identity_hash=semantic_hash)

        identity = {
            "git_commit": software_commit,
            "software_tree": software_tree,
            "package_version": __version__,
            "engine_version": ENGINE_VERSION,
            "data_snapshot_hash": str(self.manifest["data_snapshot_hash"]),
            "data_snapshot_hashes": data_snapshot_hashes,
            "inventory_source_id": str(inventory_source_id),
            "inventory_hash": inventory_hash,
            "deck_hashes": deck_hashes,
            "commander_configuration_hash": commander_configuration_hash,
            "opponent_profile_ids": opponent_profile_ids,
            "opponent_hashes": opponent_hashes,
            "opponent_registry_hash": data_snapshot_hashes["opponent_registry"],
            "opponent_ensemble_hash": opponent_ensemble_hash,
            "pilot_hashes": {
                "pilot_registry": data_snapshot_hashes["pilot_registry"],
                "robustness_registry": data_snapshot_hashes["robustness_registry"],
            },
            "pilot_parameter_hashes": pilot_parameter_hashes,
            "pilot_parameter_hash": pilot_parameter_hash,
            "policy_hash": policy_hash,
            "meta_snapshot_hash": data_snapshot_hashes["meta_snapshot"],
            "scenario_hash": sha256_run_value(scenario_payload, root=self.root),
            "scenario_set_id": scenario_set_id,
            "scenario_set_hash": scenario_set_hash,
            "data_source_manifest_hash": data_source_manifest_hash,
            "canonical_input_status": canonical_status.value,
            "stale_reasons": tuple(sorted(set(stale_reasons))),
            "run_identity_hash": semantic_hash,
            "run_identity": run_identity,
        }
        return identity

    def build_run_identity(
        self,
        scenario: object,
        deck_ids: tuple[str, ...] = (),
        *,
        tool_name: str = "python_api",
        estimate_type: EstimateType = "structural_model_estimates",
    ) -> RunIdentity:
        """Build the canonical fail-closed identity for a decision-level project run."""
        value = self._run_identity(
            scenario,
            deck_ids,
            tool_name=tool_name,
            estimate_type=estimate_type,
        )["run_identity"]
        if not isinstance(value, RunIdentity):
            raise ToolExecutionError("RunIdentity builder returned an invalid identity object")
        return value

    def _check_iterations(self, iterations: int, approval_token: str | None) -> None:
        if iterations > self.limits.hard_max_iterations:
            raise ToolExecutionError(
                f"iterations {iterations} exceed hard maximum {self.limits.hard_max_iterations}"
            )
        if (
            iterations > self.limits.approval_threshold_iterations
            and approval_token != "APPROVED_LARGE_RUN"
        ):
            raise ApprovalRequired(
                f"iterations {iterations} require approval token APPROVED_LARGE_RUN"
            )

    def _deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.decks[deck_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown structural deck: {deck_id}") from exc

    def _is_protected(self, deck_id: str, card_name: str) -> bool:
        return card_name in set(self.protected_cards.get(deck_id, []))

    def _validate_swap_policy(self, deck_id: str, remove: str, candidate_card: Any) -> None:
        if not self._is_protected(deck_id, remove):
            return
        deck = self._deck(deck_id)
        original = next((card for card in deck.cards if card.oracle_name == remove), None)
        if original is None:
            raise ToolExecutionError(f"protected card not found in deck: {remove}")
        raise ToolExecutionError(
            f"{remove} is locked by the current deckbuilding policy and cannot be cut by optimizer/search"
        )

    def _candidate(self, candidate_id: str, deck_id: str) -> CandidateProfile:
        try:
            candidate = self.candidates[candidate_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown upgrade candidate: {candidate_id}") from exc
        if candidate.allowed_deck_ids and deck_id not in candidate.allowed_deck_ids:
            raise ToolExecutionError(f"candidate {candidate_id} is not allowed for {deck_id}")
        return candidate

    def _optimization_constraints(
        self, deck_id: str, supplied: OptimizationConstraints | None = None
    ) -> OptimizationConstraints:
        if supplied is not None:
            return supplied
        path = self.root / "config/phase7_optimization.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if deck_id in payload.get("constraints", {}):
                loaded = OptimizationConstraints.model_validate(payload["constraints"][deck_id])
                canonical = default_constraints(deck_id, None, DEFAULT_CONSTRAINTS)
                return loaded.model_copy(
                    update={
                        "required_commanders": canonical.required_commanders,
                        "require_partner_configuration": canonical.require_partner_configuration,
                        "locked_cards": canonical.locked_cards,
                    }
                )
        return default_constraints(deck_id, None, DEFAULT_CONSTRAINTS)

    def _eligible_candidate_ids(
        self, deck_id: str, requested: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        ids = requested or tuple(self.candidates)
        return tuple(
            candidate_id
            for candidate_id in ids
            if candidate_id in self.candidates
            and (
                not self.candidates[candidate_id].allowed_deck_ids
                or deck_id in self.candidates[candidate_id].allowed_deck_ids
            )
        )

    def _paired_variant_metrics(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        opponent_deck_ids: tuple[str, ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        pair_id: str,
        workers: int = 1,
    ) -> tuple[PairedMetrics, list[dict[str, object]]]:
        return run_paired_structural_comparison(
            baseline=baseline,
            variant=variant,
            opponents=tuple(self._deck(deck_id) for deck_id in opponent_deck_ids),
            iterations=iterations,
            seed=seed,
            pilot_config=PilotConfig(strength=pilot_strength, mode=pilot_mode),
            max_turns=max_turns,
            pair_id=pair_id,
            workers=workers,
        )

    @staticmethod
    def _commander_dependency_penalty(deck: StructuralDeckProfile) -> float:
        nonlands = [card for card in deck.cards if not card.is_land]
        if not nonlands:
            return 0.0
        synergy = fmean(card.commander_synergy for card in nonlands) / 2.0
        floor = fmean(card.floor_value for card in nonlands) / 2.0
        return max(0.0, min(1.0, synergy * (1.0 - 0.35 * floor)))

    def _holdout_improvements(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, pod in enumerate(holdout_pods):
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline,
                variant=variant,
                opponent_deck_ids=pod,
                iterations=iterations,
                seed=seed + index + 1,
                pilot_strength=pilot_strength,
                pilot_mode=pilot_mode,
                max_turns=max_turns,
                pair_id=f"holdout-{variant.deck_hash[:10]}-{index}",
            )
            rows.append(
                {
                    "pod": pod,
                    "comparison": metrics.as_dict(),
                    "pair_count": len(pairs),
                }
            )
        return rows

    def _red_team_review(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        swaps: tuple[Any, ...],
        constraint_report: Any,
        paired: dict[str, Any],
        holdouts: list[dict[str, Any]],
        sensitivity: list[dict[str, Any]],
    ) -> dict[str, Any]:
        concerns: list[str] = []
        alternatives: list[str] = []
        if not constraint_report.valid:
            concerns.append("The variant violates one or more hard deck constraints.")
        if paired.get("placement_improvement", 0.0) <= 0:
            concerns.append("The primary paired comparison does not improve average placement.")
        if paired.get("paired_win_count", 0) <= paired.get("paired_loss_count", 0):
            concerns.append("Paired game outcomes do not favor the variant over the baseline.")
        negative_holdouts = [
            row for row in holdouts if row["comparison"].get("placement_improvement", 0.0) < 0
        ]
        if negative_holdouts:
            concerns.append("At least one holdout matchup becomes worse.")
        sensitivity_values = [row["placement_improvement"] for row in sensitivity]
        if sensitivity_values and min(sensitivity_values) < 0:
            concerns.append("The result changes sign across sensitivity settings.")
        if (
            len(sensitivity_values) >= 2
            and max(sensitivity_values) - min(sensitivity_values) > 0.20
        ):
            concerns.append("The estimated effect is highly sensitive to seed or pilot strength.")
        removed_roles: Counter[CardRole] = Counter()
        added_roles: Counter[CardRole] = Counter()
        for swap in swaps:
            original = next((c for c in baseline.cards if c.oracle_name == swap.remove), None)
            candidate = self.candidates.get(swap.add_candidate_id)
            if original:
                removed_roles.update(original.roles)
            if candidate:
                added_roles.update(candidate.card.roles)
        for role, count in removed_roles.items():
            if added_roles[role] < count:
                concerns.append(f"Net role loss detected: {role.value}.")
        if len(swaps) > 1:
            alternatives.append(
                "Validate each swap separately to distinguish package synergy from a weak "
                "component."
            )
        alternatives.append(
            "Retain the baseline when the effect is small relative to holdout or "
            "sensitivity variation."
        )
        passed = not concerns
        return {
            "passed": passed,
            "concerns": concerns,
            "alternative_explanations": alternatives,
            "automatic_application_allowed": False,
        }

    def _evaluate_search_candidate(
        self,
        *,
        baseline: StructuralDeckProfile,
        candidate: Any,
        opponent_deck_ids: tuple[str, ...],
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        search_method: str,
    ) -> tuple[OptimizationVariant, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        metrics, pairs = self._paired_variant_metrics(
            baseline=baseline,
            variant=candidate.variant,
            opponent_deck_ids=opponent_deck_ids,
            iterations=iterations,
            seed=seed,
            pilot_strength=pilot_strength,
            pilot_mode=pilot_mode,
            max_turns=max_turns,
            pair_id=f"phase7-{search_method}-{candidate.variant.deck_hash[:10]}",
        )
        holdouts = self._holdout_improvements(
            baseline=baseline,
            variant=candidate.variant,
            holdout_pods=holdout_pods,
            iterations=iterations,
            seed=seed,
            pilot_strength=pilot_strength,
            pilot_mode=pilot_mode,
            max_turns=max_turns,
        )
        holdout_values = [row["comparison"]["placement_improvement"] for row in holdouts]
        objectives = objective_vector(
            metrics=metrics,
            pairs=pairs,
            variant=candidate.variant,
            commander_dependency_penalty=self._commander_dependency_penalty(candidate.variant),
            holdout_improvements=holdout_values,
            physical_valid=candidate.constraint_report.valid,
        )
        result = OptimizationVariant(
            variant_id=candidate.variant.deck_id,
            deck_id=baseline.deck_id,
            deck_hash=candidate.variant.deck_hash,
            swaps=candidate.swaps,
            structural_rationale=candidate.rationale,
            affected_matchups=candidate.affected_matchups,
            constraint_report=candidate.constraint_report,
            objectives=objectives,
            screening_score=candidate.screening_score,
            search_method=search_method,
            parent_variant_id=candidate.parent_variant_id,
        )
        return result, {"comparison": metrics.as_dict(), "pairs": pairs}, holdouts, []

    def _metadata(
        self,
        *,
        tool_name: str,
        invocation_id: str,
        started: float,
        scenario: object,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
        estimate_type: EstimateType = "structural_model_estimates",
        run_identity: dict[str, Any] | None = None,
    ) -> ToolExecutionMetadata:
        identity = run_identity or self._run_identity(
            scenario,
            deck_ids,
            tool_name=tool_name,
            estimate_type=estimate_type,
        )
        return ToolExecutionMetadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            created_at=datetime.now(UTC),
            git_commit=self.git_commit,
            engine_version=ENGINE_VERSION,
            data_snapshot_hash=identity["data_snapshot_hash"],
            data_snapshot_hashes=identity["data_snapshot_hashes"],
            inventory_hash=identity["inventory_hash"],
            deck_hashes=identity["deck_hashes"],
            opponent_hashes=identity["opponent_hashes"],
            opponent_registry_hash=identity["opponent_registry_hash"],
            pilot_hashes=identity["pilot_hashes"],
            pilot_parameter_hashes=identity["pilot_parameter_hashes"],
            policy_hash=identity["policy_hash"],
            meta_snapshot_hash=identity["meta_snapshot_hash"],
            scenario_hash=identity["scenario_hash"],
            configuration_hash=sha256_value(scenario),
            run_identity_hash=identity["run_identity_hash"],
            run_identity=identity["run_identity"],
            pilot_version=(scenario.get("pilot_version") if isinstance(scenario, dict) else None)
            or (
                str(scenario.get("pilot_strength"))
                if isinstance(scenario, dict) and scenario.get("pilot_strength")
                else "unspecified"
            ),
            seed=seed,
            iterations=iterations,
            estimate_type=estimate_type,
            elapsed_seconds=time.monotonic() - started,
            deterministic_game_log_directory=log_dir,
            openai_trace_directory=str(self.trace_dir),
        )

    def _invoke(
        self,
        tool_name: str,
        request: Any,
        fn: Callable[[], dict[str, Any]],
        *,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
        estimate_type: EstimateType = "structural_model_estimates",
    ) -> ToolResponse:
        started = time.monotonic()
        invocation_id = f"{tool_name}-{uuid.uuid4().hex[:12]}"
        execution_limit = float(self.limits.max_simulation_seconds)
        requested_execution_limit = getattr(request, "max_simulation_seconds", None)
        if tool_name == "deck_decision_run" and requested_execution_limit is not None:
            execution_limit = float(requested_execution_limit)
        scenario = request.model_dump(mode="json") if hasattr(request, "model_dump") else request
        if tool_name == "deck_decision_run" and isinstance(scenario, dict):
            scenario = dict(scenario)
            scenario.pop("max_simulation_seconds", None)
            scenario["workers"] = 1
        identity_before = self._run_identity(
            scenario,
            deck_ids,
            tool_name=tool_name,
            estimate_type=estimate_type,
        )
        identity_mutators = {"create_meta_snapshot", "compile_pilot_policy"}
        workflow_session_guarded = tool_name.startswith("deck_decision_")
        try:
            result = fn()
            if tool_name not in identity_mutators and not workflow_session_guarded:
                identity_after = self._run_identity(
                    scenario,
                    deck_ids,
                    tool_name=tool_name,
                    estimate_type=estimate_type,
                )
                if identity_after["run_identity_hash"] != identity_before["run_identity_hash"]:
                    raise ToolExecutionError(
                        "run identity drift detected during tool execution; result rejected"
                    )
            elapsed = time.monotonic() - started
            if elapsed > execution_limit:
                raise ToolExecutionError(
                    f"tool exceeded simulation budget: {elapsed:.3f}s > {execution_limit:.3f}s"
                )
            status = ToolStatus.COMPLETED
            warnings: list[str] = []
            errors: list[str] = []
        except ApprovalRequired as exc:
            result = {}
            status = ToolStatus.REQUIRES_APPROVAL
            warnings = [str(exc)]
            errors = []
        except Exception as exc:  # Tool boundary intentionally converts failures.
            result = {}
            status = ToolStatus.FAILED
            warnings = []
            errors = [f"{type(exc).__name__}: {exc}"]
        metadata = self._metadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            started=started,
            scenario=scenario,
            deck_ids=deck_ids,
            seed=seed,
            iterations=iterations,
            log_dir=log_dir,
            estimate_type=estimate_type,
            run_identity=identity_before,
        )
        return ToolResponse(
            status=status, metadata=metadata, result=result, warnings=warnings, errors=errors
        )

    def _validate_deck_payload(self, request: ValidateDeckInput) -> dict[str, Any]:
        spec = self.manifest["decks"].get(request.deck_id)
        if spec is None:
            raise ToolExecutionError(
                f"validation is available only for local current decks: {request.deck_id}"
            )
        filename = spec["normalized_file"]
        deck = load_model(self.root / "data/decks" / filename, Deck)
        catalog = CardCatalog.from_json(self.root / "data/cards/oracle_subset.json")
        overlay_path = (self.root / "data/decks" / filename).with_name(
            f"{Path(filename).stem}_card_catalog_overrides.json"
        )
        if overlay_path.is_file():
            for card in CardCatalog.from_json(overlay_path).cards:
                catalog.add(card)
        report = DeckValidator(catalog).validate(deck)
        allocation = None
        if request.include_physical_allocation:
            collection = Collection.model_validate_json(
                owner_data_path(
                    self.root, "data/collections/current_deck_allocations.json"
                ).read_text(encoding="utf-8")
            )
            allocation = validate_collection_quantities(collection, [deck]).model_dump(mode="json")
        return {
            "deck_id": request.deck_id,
            "deck_hash": deck.deck_hash,
            "validation": report.model_dump(mode="json"),
            "physical_allocation": allocation,
        }

    def _build_variant(
        self, request: PairedVariantInput
    ) -> tuple[StructuralDeckProfile, StructuralDeckProfile, list[dict[str, Any]]]:
        self._require_active_optimization_target(request.deck_id)
        baseline = self._deck(request.deck_id)
        additions = []
        removals = []
        swap_rows = []
        for swap in request.swaps:
            candidate = self._candidate(swap.add_candidate_id, request.deck_id)
            self._validate_swap_policy(request.deck_id, swap.remove, candidate.card)
            removals.append(swap.remove)
            additions.append(candidate.card)
            swap_rows.append(
                {
                    "remove": swap.remove,
                    "add": candidate.card.oracle_name,
                    "candidate_id": candidate.candidate_id,
                    "physical_status": candidate.physical_status,
                }
            )
        variant = variant_deck(
            baseline,
            variant_id=f"{request.deck_id}/variant/{sha256_value(swap_rows)[:12]}",
            removals=removals,
            additions=additions,
        )
        return baseline, variant, swap_rows

    def _meta_kb(self) -> MetaKnowledgeBase:
        return MetaKnowledgeBase(self.root)

    def _package_extractor(self) -> ArchetypePackageExtractor:
        return ArchetypePackageExtractor(self.root)

    def _stage_meta_record(self, filename: str, payload: dict[str, Any]) -> Path:
        target = self.root / "data/meta/provenance" / filename
        existing = []
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        if not isinstance(existing, list):
            existing = [existing]
        existing.append(payload)
        atomic_write_json(target, existing)
        return target

    def _project_path(self, relative: str) -> Path:
        private = owner_data_root()
        base = private.resolve() if private is not None and is_owner_data(relative) else self.root
        path = (base / relative).resolve()
        if base not in path.parents and path != base:
            raise ToolExecutionError("path escapes project root")
        return path

    def _require_active_optimization_target(self, deck_id: str) -> None:
        if deck_id in self.FROZEN_OPPONENT_ONLY_DECK_IDS:
            raise ToolExecutionError(
                f"{deck_id} is frozen opponent-only and cannot be used as an optimization target"
            )
        if deck_id not in self.ACTIVE_OWN_DECK_IDS:
            raise ToolExecutionError(f"{deck_id} is not an active own-deck optimization target")

    def _coverage_version_prefixes(self, deck_id: str) -> tuple[str, ...]:
        prefixes = self.COVERAGE_VERSION_PREFIXES.get(deck_id)
        if prefixes is not None:
            return prefixes
        return (f"{deck_id}/", f"{deck_id}-")

    def _read_optional_json(self, relative: str, default: Any) -> Any:
        path = self.root / relative
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
