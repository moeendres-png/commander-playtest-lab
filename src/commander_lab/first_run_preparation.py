from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.engine.structural.batch import derive_match_seed
from commander_lab.models import (
    MatchupBatchInput,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    VariantSwap,
)
from commander_lab.optimization import build_search_candidate, derive_paired_seed
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.storage import sha256_value
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.service import CommanderToolService

DECK_ID = "rogshai/current"
EXPECTED_DECK_HASH = "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
SPEC_SCHEMA_VERSION = "1.0.0"
SEED_ROOTS = {
    "mulligan": 2026082101,
    "baseline": 2026082102,
    "variants": 2026082103,
    "denial": 2026082104,
    "ablation": 2026082105,
    "sensitivity": 2026082106,
}
VARIANTS = (
    {
        "label": "rootborn_for_flare",
        "remove": "Flare of Duplication",
        "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
    },
    {
        "label": "opt_for_preordain",
        "remove": "Preordain",
        "add_candidate_id": "rogshai/opt-smoke",
    },
    {
        "label": "into_the_roil_for_prismari_charm",
        "remove": "Prismari Charm",
        "add_candidate_id": "rogshai/into-the-roil-smoke",
    },
)
SENSITIVITY_PODS = (
    (
        "opponent/blight-curse-precon",
        "kaervek/current",
        "opponent/dance-elements-precon",
    ),
    (
        "opponent/wakanda-forever-precon",
        "opponent/lorehold-spirit-precon",
        "opponent/blight-curse-precon",
    ),
)
CARD_ABLATIONS = ("Flare of Duplication", "Boros Charm", "Whirlwind of Thought")
PACKAGE_ABLATIONS = (
    "rogshai-protection-counter",
    "rogshai-independent-spellslinger",
)
PRELIMINARY_RUN = {
    "classification": "preliminary_noncanonical_decision_support",
    "git_commit": "f481513799bb809501a0aa1fc5ff55e0337c7be0",
    "report_sha256": "82ba3bba8be3eb329937e3e284e86ddbfe92c7b7fac43ceb146921128d3084a2",
    "official_first_run": False,
    "deck_mutation_authority": False,
}


class FirstRunPreparationError(RuntimeError):
    """Raised when the official first-run specification cannot be trusted."""


def child_seed(root: int, label: str) -> int:
    digest = hashlib.sha256(f"{root}|{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FirstRunPreparationError(f"git identity is unavailable: {' '.join(args)}") from exc


def _structural_run_id(prefix: str, request: MatchupBatchInput) -> str:
    payload = request.model_dump(mode="json", exclude={"approval_token"})
    digest = sha256_value({"engine_version": ENGINE_VERSION, "tool": prefix, "request": payload})
    return f"{prefix}-{digest[:16]}"


def _match_seeds(request: MatchupBatchInput) -> tuple[int, ...]:
    run_id = _structural_run_id("matchup", request)
    return tuple(
        derive_match_seed(request.seed, run_id, index) for index in range(request.iterations)
    )


def _seeds_by_seat(seeds: tuple[int, ...], pod_size: int = 4) -> dict[str, list[int]]:
    return {
        f"seat_{seat + 1}": [seed for index, seed in enumerate(seeds) if index % pod_size == seat]
        for seat in range(pod_size)
    }


def _variant_records(
    facade: PriorityWorkflowFacade,
    service: CommanderToolService,
) -> tuple[list[dict[str, Any]], dict[str, tuple[int, ...]], dict[str, str]]:
    baseline = service.decks[DECK_ID]
    baseline_names = {card.oracle_name for card in baseline.cards}
    screen = facade.build_screen(DECK_ID, limit=795)
    screen_by_id = {row["candidate_id"]: row for row in screen["candidates"]}
    records: list[dict[str, Any]] = []
    paired_sets: dict[str, tuple[int, ...]] = {}
    variant_hashes: dict[str, str] = {}
    for raw in VARIANTS:
        remove = str(raw["remove"])
        candidate_id = str(raw["add_candidate_id"])
        label = str(raw["label"])
        if remove not in baseline_names:
            raise FirstRunPreparationError(f"shortlist removal is absent from control: {remove}")
        candidate = service.candidates.get(candidate_id)
        screened = screen_by_id.get(candidate_id)
        if candidate is None or screened is None:
            raise FirstRunPreparationError(
                f"shortlist candidate is not discoverable: {candidate_id}"
            )
        if candidate.physical_status != "canonical_inventory_verified_owned":
            raise FirstRunPreparationError(
                f"shortlist candidate lacks verified physical availability: {candidate_id}"
            )
        if DECK_ID not in candidate.allowed_deck_ids:
            raise FirstRunPreparationError(
                f"shortlist candidate is not RogShai-legal: {candidate_id}"
            )
        if not screened.get("model_dependent_recommendation_ready"):
            raise FirstRunPreparationError(f"shortlist candidate needs profiling: {candidate_id}")
        built = build_search_candidate(
            baseline,
            (VariantSwap(remove=remove, add_candidate_id=candidate_id),),
            service.candidates,
            service._optimization_constraints(DECK_ID),
            inventory=service.candidate_inventory,
            verified_physical_names=service.verified_candidate_names,
        )
        if not built.constraint_report.valid:
            raise FirstRunPreparationError(f"shortlist variant violates constraints: {label}")
        pair_id = f"priority-{DECK_ID}-{built.variant.deck_hash[:12]}"
        master_seed = child_seed(SEED_ROOTS["variants"], label)
        paired_sets[label] = tuple(
            derive_paired_seed(master_seed, pair_id, index) for index in range(128)
        )
        variant_hashes[label] = built.variant.deck_hash
        records.append(
            {
                **raw,
                "add": candidate.card.oracle_name,
                "variant_deck_hash": built.variant.deck_hash,
                "physical_availability": "verified",
                "commander_legality": "verified",
                "constraint_status": "PASS",
                "confidence": screened["confidence"],
                "roles": screened["roles"],
                "mana_value": candidate.card.mana_value,
                "color_requirements": dict(candidate.card.color_requirements),
                "role_coverage_sufficient": bool(screened["roles"]),
                "resource_requirements_sufficient": True,
                "interaction_protection_engine_hooks": [
                    role
                    for role in screened["roles"]
                    if role in {"draw", "enabler", "protection", "removal", "selection"}
                ],
                "package_ids": screened["package_ids"],
                "heuristic_fallback_visible": "heuristic" in (candidate.notes or "").casefold(),
                "evidence_class": candidate.card.source_quality.value,
            }
        )
    return records, paired_sets, variant_hashes


def _seed_plan(
    root: Path,
    primary_pod: tuple[str, ...],
    variant_seeds: dict[str, tuple[int, ...]],
    variant_hashes: dict[str, str],
    service: CommanderToolService,
) -> dict[str, Any]:
    baseline_request = MatchupBatchInput(
        seed=SEED_ROOTS["baseline"],
        iterations=256,
        workers=2,
        pilot_strength=PilotStrength.STRONG,
        pilot_mode=PilotDecisionMode.DETERMINISTIC,
        max_turns=35,
        deck_ids=(DECK_ID, *primary_pod),
    )
    baseline_seeds = _match_seeds(baseline_request)
    sensitivity_baseline_sets: dict[str, dict[str, Any]] = {}
    for index, pod in enumerate(SENSITIVITY_PODS, start=1):
        request = MatchupBatchInput(
            deck_ids=(DECK_ID, *pod),
            iterations=128,
            workers=2,
            seed=child_seed(SEED_ROOTS["sensitivity"], f"baseline-pod-{index}"),
            max_turns=35,
        )
        exact = _match_seeds(request)
        sensitivity_baseline_sets[f"pod_{index}"] = {
            "master_seed": request.seed,
            "exact_seeds": list(exact),
            "by_starting_seat": _seeds_by_seat(exact),
        }

    denied = {
        "ishai": ("Ishai, Ojutai Dragonspeaker",),
        "rograkh": ("Rograkh, Son of Rohgahh",),
        "both": (
            "Ishai, Ojutai Dragonspeaker",
            "Rograkh, Son of Rohgahh",
        ),
    }
    denial_sets = {
        label: list(
            derive_paired_seed(
                child_seed(SEED_ROOTS["denial"], label),
                f"denial-{DECK_ID}-{sha256_value(commanders)[:8]}",
                index,
            )
            for index in range(32)
        )
        for label, commanders in denied.items()
    }
    card_ablation_sets = {
        card: list(
            derive_paired_seed(
                child_seed(SEED_ROOTS["ablation"], f"card:{card}"),
                f"ablation-{card}",
                index,
            )
            for index in range(32)
        )
        for card in CARD_ABLATIONS
    }
    package_ablation_sets: dict[str, list[int]] = {}
    extractor = service._package_extractor()
    for package_id in PACKAGE_ABLATIONS:
        originals = extractor.package_cards_for_ablation(DECK_ID, package_id)
        pair_id = f"package-{sha256_value(list(originals))[:12]}"
        master_seed = child_seed(SEED_ROOTS["ablation"], f"package:{package_id}")
        package_ablation_sets[package_id] = [
            derive_paired_seed(master_seed, pair_id, index) for index in range(32)
        ]
    sensitivity_variant_sets = {
        label: {
            f"pod_{pod_index + 1}": [
                derive_paired_seed(
                    child_seed(SEED_ROOTS["sensitivity"], label) + pod_index,
                    f"holdout-{variant_hash[:8]}-{pod_index}",
                    index,
                )
                for index in range(32)
            ]
            for pod_index in range(2)
        }
        for label, variant_hash in variant_hashes.items()
    }
    plan: dict[str, Any] = {
        "roots": SEED_ROOTS,
        "mulligan_request_seeds": {
            f"seat_{seat}": {
                "seed": child_seed(SEED_ROOTS["mulligan"], f"seat-{seat}"),
                "samples_per_policy": 2500,
                "policies": ["current_pilot", "primer_policy"],
            }
            for seat in range(1, 5)
        },
        "baseline_primary": {
            "master_seed": SEED_ROOTS["baseline"],
            "exact_seeds": list(baseline_seeds),
            "by_starting_seat": _seeds_by_seat(baseline_seeds),
        },
        "baseline_sensitivity": sensitivity_baseline_sets,
        "variants_max_128": {key: list(value) for key, value in variant_seeds.items()},
        "denial_exact_seeds": denial_sets,
        "card_ablation_exact_seeds": card_ablation_sets,
        "package_ablation_exact_seeds": package_ablation_sets,
        "sensitivity_variant_exact_seeds": sensitivity_variant_sets,
    }
    plan["group_hashes"] = {
        key: sha256_run_value(value, root=root)
        for key, value in plan.items()
        if key != "group_hashes"
    }
    plan["full_seed_set_hash"] = sha256_run_value(plan, root=root)
    return plan


def build_official_run_spec(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    context = load_project_context(root_path)
    if context.active_own_deck_ids != (DECK_ID,):
        raise FirstRunPreparationError("RogShai is not the sole active own deck")
    if dict(context.active_deck_hashes) != {DECK_ID: EXPECTED_DECK_HASH}:
        raise FirstRunPreparationError("RogShai does not match the approved unchanged control")
    if context.playstyle_preference_type != "post_build_review_only":
        raise FirstRunPreparationError("playstyle is not restricted to post-build review")
    if "J_FINAL_ACTIVE_SCOPE" in "\n".join(dict(context.source_hashes)):
        raise FirstRunPreparationError("sealed J-FINAL evidence leaked into the live context")

    primary_pod = context.primary_opponent_deck_ids(DECK_ID)
    if not set(deck for pod in SENSITIVITY_PODS for deck in pod).issubset(
        set(context.holdout_deck_ids)
    ):
        raise FirstRunPreparationError("sensitivity pod escaped the canonical sensitivity pool")

    service = CommanderToolService(root_path)
    facade = PriorityWorkflowFacade(root_path)
    shortlist, paired_seeds, variant_hashes = _variant_records(facade, service)
    seed_plan = _seed_plan(root_path, primary_pod, paired_seeds, variant_hashes, service)
    pilot_config = PilotConfig(
        strength=PilotStrength.STRONG,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    payload: dict[str, Any] = {
        "schema_version": SPEC_SCHEMA_VERSION,
        "spec_kind": "official_rogshai_first_serious_run",
        "execution_status": "not_started",
        "official_run_started": False,
        "authorization_required": True,
        "identity": {
            "git_commit": _git(root_path, "rev-parse", "HEAD"),
            "repository_tree": _git(root_path, "rev-parse", "HEAD^{tree}"),
            "package_version": __version__,
            "engine_version": ENGINE_VERSION,
            "deck_id": DECK_ID,
            "rogshai_hash": EXPECTED_DECK_HASH,
            "context_snapshot_hash": context.snapshot_hash,
            "active_deck_hashes": dict(context.active_deck_hashes),
            "policy_config_hashes": dict(context.policy_config_hashes),
            "pilot_config_hash": sha256_run_value(pilot_config, root=root_path),
        },
        "preliminary_run": PRELIMINARY_RUN,
        "control": {
            "cards": 100,
            "library_cards": 98,
            "lands": 36,
            "commanders": [
                "Ishai, Ojutai Dragonspeaker",
                "Rograkh, Son of Rohgahh",
            ],
            "deck_mutation_allowed": False,
        },
        "primary_pod": list(primary_pod),
        "sensitivity_pods": [list(pod) for pod in SENSITIVITY_PODS],
        "sensitivity_frequency_weights": None,
        "shortlist": shortlist,
        "policies": {
            "pilot": pilot_config.model_dump(mode="json"),
            "mulligan_comparison": ["current_pilot", "primer_policy"],
            "mulligan_samples_per_seat": 2500,
            "uncertainty": "Wilson 95%",
            "multiple_comparisons": "Holm",
            "playstyle_mode": "post_build_review_only",
            "playstyle_objective_signal": False,
        },
        "budgets": {
            "workers": 2,
            "baseline_primary_games_per_seat": 64,
            "baseline_sensitivity_games_per_seat_per_pod": 32,
            "variant_paired_seeds": 64,
            "unresolved_variant_single_escalation": 128,
            "commander_denial_paired_seeds_per_case": 32,
            "card_ablation_count_max": 3,
            "package_ablation_count_max": 2,
            "ablation_paired_seeds_each": 32,
            "sensitivity_finalists_max": 2,
            "sensitivity_pods": 2,
            "sensitivity_paired_seeds_per_finalist_pod": 32,
        },
        "seed_plan": seed_plan,
        "stop_rule": {
            "stable_after_64": "stop",
            "unresolved_after_64": "escalate_once_to_128",
            "unresolved_after_128": "diagnose_and_defer",
            "material_profile_sensitivity": "stop_and_improve_profile",
            "blind_795_card_bruteforce": False,
        },
        "required_outputs": [
            "baseline_identity",
            "context_snapshot",
            "physical_legal_validation",
            "candidate_coverage",
            "mana_mulligan_baseline",
            "primary_matchup_and_seats",
            "commander_denial",
            "failure_mode_snapshot",
            "paired_variants",
            "card_package_ablation",
            "sensitivity_worst_case",
            "cache_provenance",
            "simulation_counts_and_stopping_reasons",
            "evidence_classes_and_limitations",
            "objective_recommendation_status",
            "separate_qualitative_playstyle_review",
        ],
        "truth_boundaries": [
            "structural_model_estimates != empirical_winrates",
            "Tactical_Oracle != external_rules_engine",
            "synthetic_opponent_data != real_observation",
            "external_combo_knowledge != tactical_execution_proof",
        ],
    }
    payload["spec_hash"] = sha256_run_value(payload, root=root_path)
    return payload


def validate_official_run_spec(root: str | Path, spec: dict[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    supplied = dict(spec)
    supplied_hash = supplied.pop("spec_hash", None)
    if not isinstance(supplied_hash, str) or len(supplied_hash) != 64:
        raise FirstRunPreparationError("official run spec has no valid spec_hash")
    if sha256_run_value(supplied, root=root_path) != supplied_hash:
        raise FirstRunPreparationError("official run spec was modified after preparation")
    expected = build_official_run_spec(root_path)
    if expected["spec_hash"] != supplied_hash:
        raise FirstRunPreparationError(
            "official run spec no longer matches current Git/context/deck/policy identities"
        )
    if (
        spec.get("execution_status") != "not_started"
        or spec.get("official_run_started") is not False
    ):
        raise FirstRunPreparationError("official run spec is not in a not-started state")
    return expected


def load_and_validate_official_run_spec(root: str | Path, path: str | Path) -> dict[str, Any]:
    spec_path = Path(path).resolve()
    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FirstRunPreparationError(f"official run spec is unreadable: {spec_path}") from exc
    if not isinstance(raw, dict):
        raise FirstRunPreparationError("official run spec must be a JSON object")
    return validate_official_run_spec(root, raw)


def usage_marker_path(spec_path: str | Path) -> Path:
    path = Path(spec_path).resolve()
    return path.with_name(f"{path.stem}.used.json")


def authorize_official_run(
    root: str | Path,
    spec_path: str | Path,
    *,
    authorized: bool,
) -> tuple[dict[str, Any], Path]:
    if not authorized:
        raise FirstRunPreparationError("explicit run authorization is required")
    spec = load_and_validate_official_run_spec(root, spec_path)
    marker = usage_marker_path(spec_path)
    if marker.exists():
        raise FirstRunPreparationError("official run spec has already been consumed")
    marker.write_text(
        json.dumps(
            {
                "spec_hash": spec["spec_hash"],
                "git_commit": spec["identity"]["git_commit"],
                "status": "started",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return spec, marker


__all__ = [
    "CARD_ABLATIONS",
    "DECK_ID",
    "EXPECTED_DECK_HASH",
    "PACKAGE_ABLATIONS",
    "PRELIMINARY_RUN",
    "SEED_ROOTS",
    "SENSITIVITY_PODS",
    "VARIANTS",
    "FirstRunPreparationError",
    "authorize_official_run",
    "build_official_run_spec",
    "child_seed",
    "load_and_validate_official_run_spec",
    "usage_marker_path",
    "validate_official_run_spec",
]
