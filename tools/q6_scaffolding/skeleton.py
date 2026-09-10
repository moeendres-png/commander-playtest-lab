"""Valueless scenario-skeleton generation and witness requirements.

A skeleton specifies *what a runtime qualifier must set up and observe*
for a card/capability; it never specifies outcomes. It must NOT fabricate
life totals, permanent states, legal-option lists, outcome values, or
PASS criteria derived from another engine. Those belong to later
Rules-authoritative qualification design.

Witnesses are *requirements* (evidence: null until a runtime qualifier
collects them), never claimed evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import SCHEMA_SCENARIO_SKELETON_V1
from .classify import Classification, primary_capability
from .gate import validate_output
from .states import ScaffoldingState

WITNESS_KINDS = (
    "decision_request_observed",
    "authoritative_option_set_recorded",
    "external_selection_recorded",
    "stack_event_progression",
    "relevant_zone_state_change",
    "hidden_info_boundary",
    "deterministic_replay",
    "terminal_state",
    "official_rules_oracle_reference_required",
)


def _witness(kind: str, detail: str) -> dict:
    if kind not in WITNESS_KINDS:
        raise ValueError(f"unknown witness kind: {kind}")
    return {
        "witness": kind,
        "required": True,
        "evidence": None,
        "authoritative_source": "rules_core_runtime",
        "detail": detail,
    }


@dataclass
class ScenarioSkeleton:
    """Valueless qualification skeleton for one card/capability."""

    intake_id: str
    skeleton_id: str
    card_name_hint: str
    capability_under_test: str
    schema: str = SCHEMA_SCENARIO_SKELETON_V1
    participants_required: str = "2+ (Commander multiplayer per capability)"
    player_count_requirement: str = "4P primary benchmark; 2-5P conformance per mission"
    public_setup_requirements: list = field(default_factory=list)
    hidden_info_adversary_requirements: list = field(default_factory=list)
    minimum_scenario_prerequisites: list = field(default_factory=list)
    expected_decision_pretags: list = field(default_factory=list)
    witness_requirements: list = field(default_factory=list)
    rules_questions: list = field(default_factory=list)
    state: str = ScaffoldingState.SKELETON_GENERATED.value

    def as_dict(self) -> dict:
        return asdict(self)


def skeleton_id_for(intake_id: str, capability: str) -> str:
    """Deterministic skeleton identity: intake + capability, no randomness."""
    safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in capability.upper())
    return f"skel-{intake_id[:16]}-{safe.lower()}"


def _setup_for(features: dict, families: list[str]) -> tuple[list, list, list]:
    public: list[str] = []
    hidden: list[str] = []
    prereqs: list[str] = []
    if features.get("has_targets"):
        public.append("at least one legal target object present on battlefield/stack")
        prereqs.append("target legality determined at runtime by Rules Core")
    if features.get("has_mana_cost"):
        public.append("sufficient mana sources available to the controlling player")
        prereqs.append("payment legality determined at runtime by Rules Core")
    if features.get("has_trigger") or features.get("has_static"):
        public.append("card present in the trigger/static source zone")
        prereqs.append("trigger condition established through legal game actions")
    else:
        public.append("card present in hand (or command zone for commander casts)")
    if features.get("has_hidden"):
        hidden.append("adversarial hidden-state holder (face-down/morph opponent)")
        hidden.append("hidden-info boundary audit required at every observation")
    if features.get("has_random"):
        prereqs.append("Rules-Core-seeded randomness available (no harness RNG)")
    if features.get("has_multiplayer"):
        prereqs.append("multiplayer seating with 2+ opponents for vote/each-player scope")
    if features.get("has_combat"):
        prereqs.append("attacker/blocker declaration context available at runtime")
    if features.get("has_commander"):
        prereqs.append("commander game configuration (command zone + commander tax state)")
    if features.get("nested_svar"):
        prereqs.append("chained sub-ability path reachable through legal game actions")
    if not prereqs:
        prereqs.append("legal game state in which the card can be cast/activated")
    return public, hidden, prereqs


def _witnesses_for(features: dict, families: list[str]) -> list[dict]:
    out = [
        _witness(
            "decision_request_observed",
            "runtime qualifier must record every decision request offered",
        ),
        _witness(
            "authoritative_option_set_recorded",
            "the engine-offered option set at each decision, verbatim",
        ),
        _witness(
            "external_selection_recorded",
            "the external pilot selection among offered options only",
        ),
        _witness(
            "stack_event_progression",
            "stack/event progression around the card's resolution",
        ),
        _witness(
            "relevant_zone_state_change",
            "zone/state changes relevant to the capability, observed not assumed",
        ),
        _witness(
            "deterministic_replay",
            "seed plus decision record sufficient for semantic replay",
        ),
        _witness("terminal_state", "terminal game state after the scenario prefix"),
        _witness(
            "official_rules_oracle_reference_required",
            "Oracle text and Comprehensive Rules citations required before adjudication",
        ),
    ]
    if features.get("has_hidden"):
        out.append(
            _witness(
                "hidden_info_boundary",
                "principal-scoped observations prove no hidden leakage",
            )
        )
    return out


def _rules_questions_for(features: dict, families: list[str], card_name_hint: str) -> list[dict]:
    questions: list[dict] = []

    def ask(key: str, question: str, capability: str) -> None:
        questions.append(
            {
                "question_id": f"rq-{key}",
                "question": question,
                "related_capability": capability,
                "resolving_authority": "human_coordinator_rules_adjudication",
                "status": "OPEN",
            }
        )

    if features.get("has_trigger") or features.get("has_trigger_condition"):
        ask(
            "trigger-timing",
            f"Trigger timing/ordering/intervention for {card_name_hint or 'this card'} "
            "under current Comprehensive Rules.",
            "TRIGGERED_CHOICE",
        )
    if features.get("has_replacement") or features.get("prevention_adjudication_verbs"):
        ask(
            "replacement-application",
            f"Replacement effect application order and scope for {card_name_hint or 'this card'}.",
            "REPLACEMENT_EFFECT",
        )
    if features.get("layer_adjudication_verbs"):
        ask(
            "layers-characteristic",
            f"Layer, timestamp, and characteristic-setting behavior for "
            f"{card_name_hint or 'this card'} "
            f"(verbs: {', '.join(sorted(set(features['layer_adjudication_verbs'])))}).",
            "LAYER_CHARACTERISTIC",
        )
    if features.get("has_copy_control"):
        ask(
            "copy-control-layers",
            f"Copy/control layer, timestamp, and characteristic-setting behavior for "
            f"{card_name_hint or 'this card'}.",
            "COPY_CONTROL",
        )
    if features.get("has_multiplayer"):
        ask(
            "multiplayer-scope",
            f"Multiplayer scope (vote procedure / each-opponent iteration / range) for "
            f"{card_name_hint or 'this card'}.",
            "MULTIPLAYER_OPPONENT_SELECTION",
        )
    if features.get("has_commander"):
        ask(
            "commander-rules",
            f"Commander tax, zone-replacement, and color-identity interactions for "
            f"{card_name_hint or 'this card'}.",
            "COMMANDER_MECHANIC",
        )
    if features.get("has_hidden"):
        ask(
            "hidden-info",
            f"Hidden-information handling and verification procedure for "
            f"{card_name_hint or 'this card'}.",
            "HIDDEN_INFORMATION",
        )
    if features.get("has_random"):
        ask(
            "rng-attribution",
            f"Rules randomness attribution (per-channel seed authority) for "
            f"{card_name_hint or 'this card'}.",
            "RANDOMNESS",
        )
    if features.get("has_x_value"):
        ask(
            "x-value",
            f"X value announcement, payment, and locked-value behavior for "
            f"{card_name_hint or 'this card'}.",
            "X_COST_VALUE",
        )
    return questions


def generate_skeleton(
    intake_id: str,
    card_name_hint: str,
    features: dict,
    classification: Classification,
    capability_override: str | None = None,
) -> ScenarioSkeleton:
    """Generate one valueless skeleton for the primary capability of a card."""
    families = list(classification.capability_families)
    capability = capability_override or primary_capability(families)
    public, hidden, prereqs = _setup_for(features, families)
    skeleton = ScenarioSkeleton(
        intake_id=intake_id,
        skeleton_id=skeleton_id_for(intake_id, capability),
        card_name_hint=card_name_hint,
        capability_under_test=capability,
        public_setup_requirements=public,
        hidden_info_adversary_requirements=hidden,
        minimum_scenario_prerequisites=prereqs,
        expected_decision_pretags=list(classification.expected_decision_pretags),
        witness_requirements=_witnesses_for(features, families),
        rules_questions=_rules_questions_for(features, families, card_name_hint),
    )
    validate_output(skeleton.as_dict(), artifact="scenario-skeleton")
    return skeleton


def route_state(
    *,
    ambiguous: bool,
    unsupported: list,
    features: dict,
    classification: Classification,
    skeleton: ScenarioSkeleton,
    provenance_complete: bool = True,
) -> tuple[ScaffoldingState, list[str]]:
    """Deterministically resolve a skeleton into its terminal routing state.

    Priority (first match wins): AMBIGUOUS > UNSUPPORTED >
    MANUAL_REVIEW (registry-flagged curator-review verbs) >
    RULES_ADJUDICATION_REQUIRED > MANUAL_REVIEW_REQUIRED >
    READY_FOR_RUNTIME_QUALIFICATION. Returns (state, reasons).
    """
    if not provenance_complete:
        return ScaffoldingState.MANUAL_REVIEW_REQUIRED, ["provenance_incomplete"]
    if ambiguous:
        return ScaffoldingState.AMBIGUOUS, ["parser_ambiguity_flags_present"]
    if unsupported:
        return (
            ScaffoldingState.UNSUPPORTED,
            [f"unsupported_construct:{item}" for item in sorted(set(unsupported))],
        )
    manual_verbs = sorted(set(features.get("manual_review_verbs", [])))
    if manual_verbs:
        return (
            ScaffoldingState.MANUAL_REVIEW_REQUIRED,
            [f"verb_manual_review:{verb}" for verb in manual_verbs],
        )
    if skeleton.rules_questions:
        kinds = sorted({q["related_capability"] for q in skeleton.rules_questions})
        return (
            ScaffoldingState.RULES_ADJUDICATION_REQUIRED,
            [f"rules_question:{kind}" for kind in kinds],
        )
    review_reasons: list[str] = []
    if features.get("nested_svar"):
        review_reasons.append("nested_svar_chain")
    if features.get("has_hidden"):
        review_reasons.append("hidden_information")
    if features.get("has_random"):
        review_reasons.append("randomness")
    if features.get("has_copy_control"):
        review_reasons.append("copy_control")
    if features.get("unknown_ability_verbs"):
        review_reasons.append(
            "unknown_ability_verbs:" + ",".join(features["unknown_ability_verbs"])
        )
    if features.get("unknown_trigger_modes"):
        review_reasons.append(
            "unknown_trigger_modes:" + ",".join(features["unknown_trigger_modes"])
        )
    if features.get("unknown_static_modes"):
        review_reasons.append("unknown_static_modes:" + ",".join(features["unknown_static_modes"]))
    if features.get("unknown_ability_modes"):
        review_reasons.append(
            "unknown_ability_modes:" + ",".join(features["unknown_ability_modes"])
        )
    if features.get("has_ability") and not (
        features.get("has_mana_cost") or features.get("has_targets") or features.get("has_choices")
    ):
        review_reasons.append("false_positive_probe:ability_without_typed_signals")
    if review_reasons:
        return ScaffoldingState.MANUAL_REVIEW_REQUIRED, sorted(review_reasons)
    _ = classification
    return ScaffoldingState.READY_FOR_RUNTIME_QUALIFICATION, ["mechanical_prerequisites_complete"]
