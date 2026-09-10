"""WS50 integration boundary (specification only, no WS50 implementation).

This module defines the neutral data boundary by which the future live
sequence harness (WS50 surface) may *consume* a scaffolding skeleton. It
is defined here so Task 2A never writes to WS50-owned paths; if WS50 needs
a different boundary, integration happens later after Coordinator
adjudication (marked DEPENDENCY_ON_WS50 where applicable).

Crucial precedence rule (enforced by :func:`apply_runtime_observation` and
documented for the future harness):

* WS50 runtime observations OVERWRITE/CONTRADICT pre-tags without the
  scaffolding layer vetoing them.
* Runtime native options are authoritative. Scaffolding does not provide
  legal options and never vetoes, filters, or narrows runtime observations.

No symbol in this module imports, references, or mutates any WS50-owned
path. The dataclasses below are plain data plus precedence logic; the live
harness remains the sole authority for legal actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

RUNTIME_AUTHORITY = "RUNTIME_AUTHORITATIVE_NATIVE_OPTIONS"
SCAFFOLDING_AUTHORITY = "HYPOTHESIS_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class ExpectedDecisionPretags:
    """Non-authoritative pre-tagged decision kinds from scaffolding."""

    intake_id: str
    skeleton_id: str
    pretags: tuple = ()
    authority: str = SCAFFOLDING_AUTHORITY

    def as_dict(self) -> dict:
        data = asdict(self)
        data["pretags"] = list(data["pretags"])
        return data


@dataclass(frozen=True)
class WitnessRequirements:
    """Witness checklist carried into runtime qualification."""

    intake_id: str
    skeleton_id: str
    witnesses: tuple = ()
    authority: str = SCAFFOLDING_AUTHORITY

    def as_dict(self) -> dict:
        data = asdict(self)
        data["witnesses"] = list(data["witnesses"])
        return data


@dataclass(frozen=True)
class ScaffoldingScenarioInput:
    """Neutral handoff object: everything the harness may read, nothing more."""

    intake_id: str
    skeleton_id: str
    card_name_hint: str
    capability_under_test: str
    public_setup_requirements: tuple = ()
    hidden_info_adversary_requirements: tuple = ()
    minimum_scenario_prerequisites: tuple = ()
    expected_decision_pretags: tuple = ()
    witness_requirements: tuple = ()
    open_rules_questions: tuple = ()
    provenance: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        data = asdict(self)
        for key in (
            "public_setup_requirements",
            "hidden_info_adversary_requirements",
            "minimum_scenario_prerequisites",
            "expected_decision_pretags",
            "witness_requirements",
            "open_rules_questions",
        ):
            data[key] = list(data[key])
        return data


@dataclass(frozen=True)
class ObservedRuntimeDecision:
    """One runtime-observed decision (harness-side shape, defined for contract).

    This shape is specified here so both sides share field names; actual
    instances are produced ONLY by the WS50 runtime, never by scaffolding.
    """

    kind: str
    options_offered: tuple = ()
    selection: str = ""
    authority: str = RUNTIME_AUTHORITY

    def as_dict(self) -> dict:
        data = asdict(self)
        data["options_offered"] = list(data["options_offered"])
        return data


def build_scenario_input(skeleton: dict, provenance: dict) -> ScaffoldingScenarioInput:
    """Project a scenario skeleton into the neutral harness-consumable shape."""
    return ScaffoldingScenarioInput(
        intake_id=skeleton["intake_id"],
        skeleton_id=skeleton["skeleton_id"],
        card_name_hint=skeleton.get("card_name_hint", ""),
        capability_under_test=skeleton.get("capability_under_test", "UNCLUSTERED"),
        public_setup_requirements=tuple(skeleton.get("public_setup_requirements", [])),
        hidden_info_adversary_requirements=tuple(
            skeleton.get("hidden_info_adversary_requirements", [])
        ),
        minimum_scenario_prerequisites=tuple(skeleton.get("minimum_scenario_prerequisites", [])),
        expected_decision_pretags=tuple(skeleton.get("expected_decision_pretags", [])),
        witness_requirements=tuple(skeleton.get("witness_requirements", [])),
        open_rules_questions=tuple(skeleton.get("rules_questions", [])),
        provenance=dict(provenance),
    )


def apply_runtime_observation(
    scenario_input: ScaffoldingScenarioInput,
    observed: list[ObservedRuntimeDecision],
) -> dict:
    """Reconcile pre-tags against authoritative runtime observations.

    The runtime sequence is authoritative unconditionally: pre-tags that the
    runtime contradicts (missing, extra, or reordered kinds) are recorded as
    contradicted hypotheses. Scaffolding never vetoes, filters, or narrows
    the observed sequence. Returns a reconciliation report (not a verdict).
    """
    for decision in observed:
        if decision.authority != RUNTIME_AUTHORITY:
            raise ValueError(
                "observed decisions must carry RUNTIME_AUTHORITATIVE_NATIVE_OPTIONS "
                f"authority (got {decision.authority!r}); scaffolding hypotheses "
                "are never observations"
            )
    pretagged_kinds = [
        tag["kind"] if isinstance(tag, dict) else str(tag)
        for tag in scenario_input.expected_decision_pretags
    ]
    observed_kinds = [d.kind for d in observed]
    return {
        "intake_id": scenario_input.intake_id,
        "skeleton_id": scenario_input.skeleton_id,
        "pretagged_kinds": list(pretagged_kinds),
        "observed_kinds": list(observed_kinds),
        "confirmed_pretags": [k for k in pretagged_kinds if k in observed_kinds],
        "contradicted_pretags": [k for k in pretagged_kinds if k not in observed_kinds],
        "novel_runtime_decisions": [k for k in observed_kinds if k not in pretagged_kinds],
        "precedence": (
            "runtime native options authoritative; pre-tags are hypotheses only; "
            "scaffolding does not provide legal options and exercises no veto"
        ),
    }
