"""Capability clustering and decision-surface pre-tagging.

Cards are grouped into capability families (systemic behavior classes, not
one-card hacks). The taxonomy registry is extensible: new families require
an explicit, provenance-bearing registration via :func:`register_family`.

Decision-surface pre-tags are HYPOTHESES ONLY (D4c proved one mechanic !=
one callback). A pre-tagged kind such as TARGET_SELECTION records that the
static text *suggests* a decision of that kind may occur at runtime; the
live sequence harness may discover additional, fewer, differently ordered,
or no decisions. Pre-tags are never legal-action generation: the runtime's
observed sequence always overwrites them (see :mod:`integration`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import SCHEMA_CLASSIFICATION_V1
from .gate import validate_output

PRETAG_AUTHORITY = "HYPOTHESIS_NON_AUTHORITATIVE"
PRETAG_TRUTH_SOURCE = "rules_core_runtime"


@dataclass(frozen=True)
class CapabilityFamily:
    """One extensible capability family with explicit provenance."""

    name: str
    description: str
    provenance: str  # why this family exists (corpus evidence / D-report / design)

    def as_dict(self) -> dict:
        return asdict(self)


# Seed taxonomy: capability families named by the task contract. Extension
# is explicit via register_family; nothing here is frozen.
_SEED_FAMILIES = (
    CapabilityFamily(
        "TARGET_SELECTION",
        "Effects requiring choice of targets (ValidTgts/ValidTgts$ signals).",
        "task-contract seed; corpus evidence: targets stratum (D3 §4: 225/1000)",
    ),
    CapabilityFamily(
        "MODAL_CHOICE",
        "Modal spells/abilities offering a choice among modes (Charm signals).",
        "task-contract seed; corpus evidence: choices stratum (D3 §4: 438/1000)",
    ),
    CapabilityFamily(
        "MANA_PAYMENT_CHOICE",
        "Mana costs, activated mana abilities, and payment decisions.",
        "task-contract seed; corpus evidence: mana/cost stratum (D3 §4: 939/1000)",
    ),
    CapabilityFamily(
        "X_COST_VALUE",
        "Variable X costs/values requiring a numeric choice at runtime.",
        "task-contract seed; bounded sample: Fireball",
    ),
    CapabilityFamily(
        "ADDITIONAL_ALTERNATIVE_COST",
        "Additional costs (sacrifice/discard/life) and alternative costs.",
        "task-contract seed; bounded sample: Altars Reap, Force of Will",
    ),
    CapabilityFamily(
        "REPLACEMENT_EFFECT",
        "Replacement effects altering events (R: lines, ETB replacement).",
        "task-contract seed; corpus evidence: replacements (D3 §4: 89/1000)",
    ),
    CapabilityFamily(
        "TRIGGERED_CHOICE",
        "Triggered abilities, including optional triggers and trigger ordering.",
        "task-contract seed; corpus evidence: triggers stratum (D3 §4: 183/1000)",
    ),
    CapabilityFamily(
        "COMBAT",
        "Attacker/blocker declaration, evasion, and combat damage behavior.",
        "task-contract seed; D2 corpus: combat area 12 files / 101 tests",
    ),
    CapabilityFamily(
        "COMMANDER_MECHANIC",
        "Commander tax, command-zone replacement, partner, color identity.",
        "task-contract seed; D2 corpus: commander area 33 files / 85 tests",
    ),
    CapabilityFamily(
        "MULTIPLAYER_OPPONENT_SELECTION",
        "Voting, each-player/each-opponent effects, monarch, range effects.",
        "task-contract seed; corpus evidence: multiplayer refs (D3 §4: 47/1000)",
    ),
    CapabilityFamily(
        "HIDDEN_INFORMATION",
        "Face-down/morph/manifest/reveal/look-at interactions.",
        "task-contract seed; corpus evidence: hidden info (D3 §4: 106/1000)",
    ),
    CapabilityFamily(
        "RANDOMNESS",
        "Coin flips, dice rolls, shuffling, and other Rules randomness.",
        "task-contract seed; corpus evidence: randomness (D3 §4: 228/1000)",
    ),
    CapabilityFamily(
        "COPY_CONTROL",
        "Copying spells/permanents and control-change effects (incl. meld).",
        "task-contract seed; corpus evidence: copy/control (D3 §4: 170/1000)",
    ),
    CapabilityFamily(
        "LAYER_CHARACTERISTIC",
        "Characteristic-setting effects needing layer/timestamp adjudication.",
        "Task-2B full-corpus census; Animate/SetState/ChangeText-shape verbs",
    ),
    CapabilityFamily(
        "ZONE_CHANGE",
        "Zone movements with timing/visibility questions (exile, return, SBA).",
        "task-contract seed; D3 family TRIGGER_REPLACEMENT_ZONE_SBA lineage",
    ),
    CapabilityFamily(
        "SBA_SENSITIVE",
        "State-based-action-sensitive behavior (legend rule, counters, leaves).",
        "task-contract seed; D2 corpus: sba area; commander-leaves coverage",
    ),
)

_FAMILY_REGISTRY: dict[str, CapabilityFamily] = {f.name: f for f in _SEED_FAMILIES}


def register_family(name: str, description: str, provenance: str) -> CapabilityFamily:
    """Explicitly extend the taxonomy with a provenance-bearing family.

    Raises ValueError on duplicate names or missing provenance: silent
    taxonomy drift is not allowed.
    """
    key = name.strip().upper()
    if not key:
        raise ValueError("family name must be non-empty")
    if key in _FAMILY_REGISTRY:
        raise ValueError(f"capability family already registered: {key}")
    if not provenance or not provenance.strip():
        raise ValueError(
            f"family {key} requires explicit provenance "
            "(taxonomy extension must be provenance-bearing)"
        )
    family = CapabilityFamily(key, description.strip(), provenance.strip())
    _FAMILY_REGISTRY[key] = family
    return family


def family_names() -> list[str]:
    return sorted(_FAMILY_REGISTRY)


# Primary-capability selection order: most distinctive capability first, so
# the skeleton under test names what makes the card interesting rather than
# the ubiquitous mana-cost family. Order is presentation priority only.
PRIMARY_CAPABILITY_ORDER = (
    "MULTIPLAYER_OPPONENT_SELECTION",
    "COMMANDER_MECHANIC",
    "HIDDEN_INFORMATION",
    "RANDOMNESS",
    "COPY_CONTROL",
    "LAYER_CHARACTERISTIC",
    "TRIGGERED_CHOICE",
    "REPLACEMENT_EFFECT",
    "MODAL_CHOICE",
    "TARGET_SELECTION",
    "X_COST_VALUE",
    "ADDITIONAL_ALTERNATIVE_COST",
    "COMBAT",
    "SBA_SENSITIVE",
    "ZONE_CHANGE",
    "MANA_PAYMENT_CHOICE",
)


def primary_capability(families: list[str]) -> str:
    """Select the skeleton's capability under test from clustered families."""
    ranked = [name for name in PRIMARY_CAPABILITY_ORDER if name in families]
    if ranked:
        return ranked[0]
    if families:
        return sorted(families)[0]
    return "UNCLUSTERED"


# Ordered expected-decision pre-tag vocabulary. Order is presentation order
# only and carries no runtime semantics.
PRETAG_KINDS = (
    "TARGET_SELECTION",
    "MANA_PAYMENT",
    "COMBAT_SELECTION",
    "MODE_CHOICE",
    "TRIGGER_CHOICE",
    "PAYMENT_CHOICE",
    "X_VALUE_CHOICE",
    "VOTE_CHOICE",
    "OPPONENT_CHOICE",
    "SACRIFICE_CHOICE",
)


@dataclass
class Classification:
    """Capability clustering + non-authoritative decision pre-tags for a card."""

    intake_id: str
    schema: str = SCHEMA_CLASSIFICATION_V1
    capability_families: list = field(default_factory=list)
    adversarial_tags: list = field(default_factory=list)
    expected_decision_pretags: list = field(default_factory=list)
    taxonomy_version: str = "q6-taxonomy-0.2.0"

    def as_dict(self) -> dict:
        return asdict(self)


def _pretag(kind: str, basis: str) -> dict:
    if kind not in PRETAG_KINDS:
        raise ValueError(f"unknown pre-tag kind: {kind}")
    return {
        "kind": kind,
        "authority": PRETAG_AUTHORITY,
        "truth_source": PRETAG_TRUTH_SOURCE,
        "basis": basis,
    }


def classify_card(intake_id: str, features: dict) -> Classification:
    """Map parser features to capability families and pre-tagged decisions."""
    families: list[str] = []
    tags: list[str] = []
    pretags: list[dict] = []

    if features.get("has_targets"):
        families.append("TARGET_SELECTION")
        tags.append("targets")
        pretags.append(_pretag("TARGET_SELECTION", "ValidTgts/target signals in text"))
    if features.get("has_modal_choice") or "Charm" in " ".join(features.get("ability_kinds", [])):
        families.append("MODAL_CHOICE")
        tags.append("choices_modes")
        pretags.append(_pretag("MODE_CHOICE", "modal/charm structure in text"))
    elif features.get("has_choices"):
        tags.append("choices_modes")
        if features.get("has_multiplayer"):
            pretags.append(_pretag("VOTE_CHOICE", "vote/council signals in text"))
            pretags.append(_pretag("OPPONENT_CHOICE", "each-opponent signals in text"))
        else:
            pretags.append(_pretag("TRIGGER_CHOICE", "optional/choice signals in text"))
    if features.get("has_mana_cost") or "Mana" in " ".join(features.get("ability_kinds", [])):
        families.append("MANA_PAYMENT_CHOICE")
        tags.append("mana_cost")
        pretags.append(_pretag("MANA_PAYMENT", "mana cost/ability signals in text"))
    if features.get("has_x_value"):
        families.append("X_COST_VALUE")
        pretags.append(_pretag("X_VALUE_CHOICE", "X numeric signals in text"))
    if features.get("has_additional_cost") or features.get("has_alternative_cost"):
        families.append("ADDITIONAL_ALTERNATIVE_COST")
        pretags.append(_pretag("PAYMENT_CHOICE", "additional/alternative cost signals"))
    if features.get("has_replacement"):
        families.append("REPLACEMENT_EFFECT")
        tags.append("replacements")
    if features.get("has_trigger") or features.get("has_trigger_condition"):
        families.append("TRIGGERED_CHOICE")
        tags.append("triggers")
        pretags.append(_pretag("TRIGGER_CHOICE", "trigger line present in text"))
    if features.get("has_combat"):
        families.append("COMBAT")
        tags.append("combat")
        pretags.append(_pretag("COMBAT_SELECTION", "combat-restriction signals in text"))
    if features.get("has_commander"):
        families.append("COMMANDER_MECHANIC")
    if features.get("has_multiplayer"):
        families.append("MULTIPLAYER_OPPONENT_SELECTION")
        tags.append("multiplayer")
    if features.get("has_hidden"):
        families.append("HIDDEN_INFORMATION")
        tags.append("hidden_info")
    if features.get("has_random"):
        families.append("RANDOMNESS")
        tags.append("randomness")
    if features.get("has_copy_control"):
        families.append("COPY_CONTROL")
        tags.append("copy_control")
    if features.get("layer_adjudication_verbs"):
        families.append("LAYER_CHARACTERISTIC")
        tags.append("layers")
    if features.get("has_trigger") or features.get("has_replacement") or features.get("has_static"):
        families.append("ZONE_CHANGE")
    if features.get("has_static") or features.get("has_replacement"):
        families.append("SBA_SENSITIVE")
    if features.get("nested_svar"):
        tags.append("nested_svar")
    if "Sacrifice" in " ".join(features.get("ability_kinds", [])):
        pretags.append(_pretag("SACRIFICE_CHOICE", "sacrifice ability signals in text"))

    # Deduplicate pre-tags by kind, preserving first-seen order.
    seen: set[str] = set()
    ordered: list[dict] = []
    for tag in pretags:
        if tag["kind"] not in seen:
            seen.add(tag["kind"])
            ordered.append(tag)

    unknown = [f for f in families if f not in _FAMILY_REGISTRY]
    if unknown:
        raise ValueError(f"classification references unregistered families: {unknown}")

    classification = Classification(
        intake_id=intake_id,
        capability_families=sorted(set(families)),
        adversarial_tags=sorted(set(tags)),
        expected_decision_pretags=ordered,
    )
    validate_output(classification.as_dict(), artifact="classification")
    return classification
