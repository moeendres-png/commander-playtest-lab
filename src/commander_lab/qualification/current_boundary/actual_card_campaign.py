"""AF07 actual-card current-boundary campaign producer (dedicated, Phase 1).

This module owns one question: for each of the frozen twenty-nine actual-card
identities, can the *current production boundary* causally reach that identity's
own mandatory obligation, and if so, is the obligation directly proven by
source-bound runtime evidence?

Derivation discipline (nothing about the corpus is restated here)
-----------------------------------------------------------------

* the identity list comes from ``ACTUAL_CARD_DOMAIN_v1.json``
  (``regression_corpus_29``), in manifest order;
* fixture ownership comes from ``COMMON_FIXTURE_MANIFEST_v1.json``; the map must
  be a bijection with the frozen corpus or derivation fails closed;
* the effective requested state / obligation for each identity comes from the
  current effective materialization (``materialization.load_effective_materialization``),
  which resolves the active successor contract; the frozen record digests are
  bound into every row and every receipt;
* denominator membership and the frozen exclusion decision come from the
  effective materialization and ``WS47_PROVIDER_DENOMINATOR_107.json``.

Execution discipline
--------------------

The campaign never implements a Rules engine and never reconstructs legality:

* state construction, legal options, decision frames, the public event tape and
  the principal-neutral observation are the engine's;
* an answer is submitted only when the record's own ``decision_script`` names it
  and the engine offers it (the generic production executor in
  ``midgame_rows.execute_row`` enforces exactly-one matching);
* a row is reported ``DIRECT_PASS`` only when *all* of the following hold:
  the engine accepted the requested state, the engine's construction verdict is
  accepted, the engine-reported build equals the canonical candidate pin, the
  generic executor consumed the complete script, every required event token was
  positively observed, and every one of the record's ``terminal_postconditions``
  has an explicit proof declared in this module's obligation plan that held on
  the engine's own observation or tape;
* rows without a complete obligation plan are *measured*, never credited: the
  campaign reports the exact first blocker and leaves the row unverdicted rather
  than promoting partial evidence.

Blocker vocabulary (exactly one per non-PASS row)
-------------------------------------------------

``DEPENDENCY_WAITING``    the first blocker is on a surface currently owned by
                          another active writer (PR #450 / PR #452); not edited.
``FIXTURE_DEFECT``        the frozen record itself cannot yield the declared
                          obligation (e.g. an obligation with no executable
                          event vocabulary at all).
``HARNESS_DEFECT``        the Lab qualification harness/executor cannot yet
                          express the obligation, and the surface is free now.
``PROVIDER_ADAPTER_DEFECT`` the Lab-owned XMage bridge restoration cannot
                          construct a dimension the record requires.
``ENGINE_DEFECT``         the pinned engine violated a rules obligation that the
                          record's own evidence demonstrates.
``UNKNOWN``               the evidence is insufficient to attribute the blocker;
                          never upgraded.

The ``blocker_surface`` and ``blocker_owner`` fields carry the exact path and
owner so a newer source lock can re-adjudicate without re-running the campaign.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import materialization as materialization_mod
from . import midgame_lane as ml
from . import midgame_rows as midgame_rows_mod
from . import receipts as receipt_mod
from .source_lock import repo_root

EXECUTION_MODE = "AF07_ACTUAL_CARD_CURRENT_BOUNDARY"
TEST_IDENTITY_PREFIX = "af07-actual-card-campaign#"
MATRIX_SCHEMA = "commander-lab.af07-actual-card-campaign-matrix/1.0.0"
MEASUREMENT_SCHEMA = "commander-lab.af07-actual-card-row-measurement/1.0.0"
SEED = 424242

CORPUS_COUNT = 29

BLOCKER_DEPENDENCY_WAITING = "DEPENDENCY_WAITING"
BLOCKER_FIXTURE_DEFECT = "FIXTURE_DEFECT"
BLOCKER_HARNESS_DEFECT = "HARNESS_DEFECT"
BLOCKER_PROVIDER_ADAPTER_DEFECT = "PROVIDER_ADAPTER_DEFECT"
BLOCKER_ENGINE_DEFECT = "ENGINE_DEFECT"
BLOCKER_UNKNOWN = "UNKNOWN"

BLOCKER_CLASSES = (
    BLOCKER_DEPENDENCY_WAITING,
    BLOCKER_FIXTURE_DEFECT,
    BLOCKER_HARNESS_DEFECT,
    BLOCKER_PROVIDER_ADAPTER_DEFECT,
    BLOCKER_ENGINE_DEFECT,
    BLOCKER_UNKNOWN,
)

OUTCOME_DIRECT_PASS = "DIRECT_PASS"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_MEASURED = "MEASURED"
OUTCOME_FAIL = "FAIL"
OUTCOME_UNKNOWN = "UNKNOWN"

# Surfaces that currently belong to another active writer. A blocker whose fix
# would have to change one of these is DEPENDENCY_WAITING instead of a free
# HARNESS_DEFECT. The mapping is campaign data, not a statement about the
# repository forever: Phase 2 (after both PRs are terminal and their bytes are
# impact-adjudicated) rebuilds it from live ownership.
DEFAULT_FOREIGN_OWNED_SURFACES: Mapping[str, str] = {
    "src/commander_lab/qualification/current_boundary/midgame_rows.py": "PR #450",
    "scripts/run_midgame_capability_probe.py": "PR #450",
    "tests/qualification/test_current_boundary_midgame_rows.py": "PR #450",
    "qualification/CURRENT_PRE_FREEZE_CONTRACT.json": "PR #452",
    "qualification/pre-freeze-successor/": "PR #452",
    "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_9.json": "PR #452",
    "src/commander_lab/qualification/current_boundary/knowledge_projection.py": "PR #452",
    "src/commander_lab/qualification/current_boundary/source_lock.py": "PR #452",
}

SURFACE_CAMPAIGN = "src/commander_lab/qualification/current_boundary/actual_card_campaign.py"
SURFACE_MIDGAME_ROWS = "src/commander_lab/qualification/current_boundary/midgame_rows.py"
SURFACE_MIDGAME_PROBE = "scripts/run_midgame_capability_probe.py"
SURFACE_NATIVE_RESTORATION = (
    "engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java"
)
# A missing script step is a fixture-contract gap; the effective successor
# contract surface is where a correction has to land.
SURFACE_SUCCESSOR_CONTRACT = "qualification/pre-freeze-successor/"

# Decision classes whose answering machinery belongs to the generic production
# executor surface: priority passes, mana payment from declared sources, and the
# two combat declaration classes (attackers are driven by the record's own
# assignment steps; blockers are not answered by the executor at all). A frame
# in this set is an executor gap, never a fixture-contract gap.
EXECUTOR_SURFACE_DECISION_CLASSES = frozenset(
    {"priority", "mana_payment", "declare_attacker", "declare_blocker"}
)

STANDARD_OBJECT_ZONES = frozenset(
    {"battlefield", "hand", "library", "graveyard", "exile", "command", "stack", "sideboard"}
)

# The bridge's own published qualified turn-1 checkpoint allow-list, as the
# temporal restoration dimension names it. A record outside this set requires a
# temporal dimension the restoration does not construct.
QUALIFIED_TEMPORAL_POINTS = frozenset(
    {
        ("beginning", "upkeep"),
        ("beginning", "draw"),
        ("precombat_main", "main"),
        ("combat", "declare_attackers"),
        ("combat", "declare_blockers"),
        ("combat", "combat_damage"),
        ("postcombat_main", "main"),
    }
)

# The generic production executor's supported scripted action kinds. Derived by
# reading the executor's own dispatch (``midgame_rows._scripted_priority_action``
# and ``_scripted_answer``): this is a capability statement about the executor,
# not a rules statement, and it is re-derived in ``executor_requirements`` from
# the record so a drifted executor shows up as a measurement mismatch.
EXECUTOR_SUPPORTED_PRIORITY_ACTIONS = frozenset({"cast", "cast_commander"})
EXECUTOR_UNSUPPORTED_SELECTOR_PREFIX = "selector:"


class ActualCardCampaignError(RuntimeError):
    """The campaign cannot proceed without producing false evidence."""


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ActualCardCampaignError(f"cannot read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ActualCardCampaignError(f"{path} is not a JSON object")
    return document


def _required_events(record: Mapping[str, Any]) -> tuple[str, ...]:
    expected = record.get("expected_events")
    if isinstance(expected, Mapping):
        return tuple(str(token) for token in expected.get("required_events") or ())
    if isinstance(expected, list):
        return tuple(str(token) for token in expected)
    return ()


def _forbidden_events(record: Mapping[str, Any]) -> tuple[str, ...]:
    expected = record.get("expected_events")
    if isinstance(expected, Mapping):
        return tuple(str(token) for token in expected.get("forbidden_events") or ())
    return ()


def _terminal_postconditions(record: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in record.get("terminal_postconditions") or ())


@dataclass(frozen=True)
class CardRow:
    """One frozen actual-card identity and its effective obligation record."""

    fixture_id: str
    card_identity: str
    record: Mapping[str, Any]
    in_effective_denominator: bool
    excluded_by_frozen_denominator: bool
    requested_state_digest: str | None
    obligation_digest: str | None
    materialization_version: str | None
    materialization_digest: str | None

    @property
    def required_events(self) -> tuple[str, ...]:
        return _required_events(self.record)

    @property
    def forbidden_events(self) -> tuple[str, ...]:
        return _forbidden_events(self.record)

    @property
    def terminal_postconditions(self) -> tuple[str, ...]:
        return _terminal_postconditions(self.record)

    @property
    def execution_entry_mode(self) -> str | None:
        value = self.record.get("execution_entry_mode")
        return str(value) if value else None

    def identity_document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "card_identity": self.card_identity,
            "requested_state_digest": self.requested_state_digest,
            "obligation_digest": self.obligation_digest,
            "materialization_version": self.materialization_version,
            "materialization_digest": self.materialization_digest,
            "execution_entry_mode": self.execution_entry_mode,
            "required_events": list(self.required_events),
            "forbidden_events": list(self.forbidden_events),
            "terminal_postconditions": list(self.terminal_postconditions),
            "in_effective_denominator": self.in_effective_denominator,
            "excluded_by_frozen_denominator": self.excluded_by_frozen_denominator,
        }


@dataclass(frozen=True)
class ActualCardCorpus:
    """The frozen 29-card corpus, fully derived and cross-checked."""

    rows: tuple[CardRow, ...]
    identities: tuple[str, ...]
    fixture_identities: Mapping[str, str]
    materialization_receipt: Mapping[str, Any]
    domain_manifest: str
    fixture_manifest: str
    denominator_artifact: str

    def row(self, fixture_id: str) -> CardRow:
        for row in self.rows:
            if row.fixture_id == fixture_id:
                return row
        raise KeyError(f"fixture not in AF07 corpus: {fixture_id}")

    @property
    def direct_rows(self) -> tuple[CardRow, ...]:
        return tuple(row for row in self.rows if row.in_effective_denominator)


def derive_corpus(root: Path | None = None) -> ActualCardCorpus:
    """Derive and cross-check the frozen 29-card corpus. Fails closed."""
    resolved = Path(root) if root is not None else repo_root()
    domain_path = resolved / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json"
    fixture_path = resolved / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
    denominator_path = resolved / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"

    domain = _load_json(domain_path)
    fixtures_document = _load_json(fixture_path)
    denominator_document = _load_json(denominator_path)

    identities = tuple(str(name) for name in domain.get("regression_corpus_29") or ())
    if len(identities) != CORPUS_COUNT:
        raise ActualCardCampaignError(
            f"{domain_path} carries {len(identities)} regression identities, "
            f"expected {CORPUS_COUNT}"
        )
    if len(set(identities)) != len(identities):
        raise ActualCardCampaignError("the frozen corpus carries duplicate identities")

    fixture_identities: dict[str, str] = {}
    for fixture in fixtures_document.get("fixtures") or ():
        fixture_id = str(fixture.get("fixture_id") or "")
        identity = fixture.get("card_identity")
        if fixture_id.startswith("CARD_") and identity:
            if fixture_id in fixture_identities:
                raise ActualCardCampaignError(f"duplicate CARD fixture id {fixture_id}")
            fixture_identities[fixture_id] = str(identity)
    if len(fixture_identities) != CORPUS_COUNT:
        raise ActualCardCampaignError(
            f"{fixture_path} assigns {len(fixture_identities)} CARD fixtures, "
            f"expected {CORPUS_COUNT}"
        )
    if set(fixture_identities.values()) != set(identities):
        missing = sorted(set(identities) - set(fixture_identities.values()))
        extra = sorted(set(fixture_identities.values()) - set(identities))
        raise ActualCardCampaignError(
            f"the CARD fixture identities are not a bijection with the frozen corpus; "
            f"missing={missing} extra={extra}"
        )

    effective = materialization_mod.load_effective_materialization(resolved)
    denominator = set(effective.denominator)
    frozen_excluded = {str(item) for item in denominator_document.get("excluded_fixture_ids") or ()}

    rows: list[CardRow] = []
    for fixture_id in sorted(fixture_identities):
        record = effective.record(fixture_id)
        family = str(record.get("fixture_family") or "")
        if family != "actual_card":
            raise ActualCardCampaignError(
                f"{fixture_id} is {family!r} in the effective materialization, not actual_card"
            )
        binding = record.get("card_authority_binding") or {}
        bound_identity = str(binding.get("card_identity") or "")
        if bound_identity != fixture_identities[fixture_id]:
            raise ActualCardCampaignError(
                f"{fixture_id} identity drift: manifest says {fixture_identities[fixture_id]!r}, "
                f"record says {bound_identity!r}"
            )
        in_denominator = fixture_id in denominator
        if not in_denominator and fixture_id not in frozen_excluded:
            raise ActualCardCampaignError(
                f"{fixture_id} is neither in the effective denominator nor in the frozen "
                "exclusion list; the credit route cannot be derived"
            )
        rows.append(
            CardRow(
                fixture_id=fixture_id,
                card_identity=bound_identity,
                record=record,
                in_effective_denominator=in_denominator,
                excluded_by_frozen_denominator=fixture_id in frozen_excluded,
                requested_state_digest=record.get("requested_state_digest"),
                obligation_digest=record.get("obligation_digest"),
                materialization_version=record.get("materialization_version"),
                materialization_digest=record.get("materialization_digest"),
            )
        )

    covered = {row.card_identity for row in rows}
    if covered != set(identities):
        raise ActualCardCampaignError("the derived rows do not cover the frozen corpus exactly")

    return ActualCardCorpus(
        rows=tuple(rows),
        identities=identities,
        fixture_identities=dict(sorted(fixture_identities.items())),
        materialization_receipt=effective.receipt(),
        domain_manifest=str(domain_path.relative_to(resolved)),
        fixture_manifest=str(fixture_path.relative_to(resolved)),
        denominator_artifact=str(denominator_path.relative_to(resolved)),
    )


# --------------------------------------------------------------------------- #
# Requirement derivation (pure; no engine, no rules)
# --------------------------------------------------------------------------- #


def required_state_dimensions(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Starting-state dimensions this record requires, derived from the record.

    The names are mechanism names, not fixture-id prefixes: a future record is
    classified by what it needs. Whether the current provider adapter supports a
    dimension is answered by the engine's own live dimension manifest and by the
    engine's own construction verdict, never by this list.
    """
    dimensions: list[str] = []
    if record.get("stack_state"):
        dimensions.append("stack_objects")
    objects = list(record.get("semantic_objects") or ())
    if any(obj.get("counters") for obj in objects):
        dimensions.append("counters")
    if any(obj.get("tapped") is True for obj in objects):
        dimensions.append("tapped_permanents")
    if any(obj.get("face_down") is True for obj in objects):
        dimensions.append("face_down")
    if any(
        obj.get("owner")
        and obj.get("controller")
        and str(obj.get("owner")) != str(obj.get("controller"))
        for obj in objects
    ):
        dimensions.append("control_divergence")
    if any(str(obj.get("zone")) not in STANDARD_OBJECT_ZONES for obj in objects):
        dimensions.append("revealed_zone")
    if any(str(obj.get("zone")) == "library" for obj in objects):
        # A specific object at a specific library position is frozen partial
        # library identity: the bridge's own manifest refuses it without a
        # complete permutation ("legacy/frozen partial library identity").
        dimensions.append("library_identity_objects")
    commander_state = record.get("commander_state") or {}
    if commander_state.get("multiple_commander_relations"):
        dimensions.append("commander_relations")
    for viewer in (record.get("knowledge_state") or {}).get("viewer_states") or ():
        if (
            viewer.get("known_library_ranges")
            or viewer.get("known_object_identities")
            or viewer.get("face_down_look_permissions")
        ):
            dimensions.append("hidden_library_identity")
            break
    temporal = record.get("temporal_state") or {}
    point = (str(temporal.get("phase") or ""), str(temporal.get("step") or ""))
    if point != ("", "") and point not in QUALIFIED_TEMPORAL_POINTS:
        dimensions.append("temporal_checkpoint_unqualified")
    return tuple(dimensions)


def executor_requirements(record: Mapping[str, Any]) -> tuple[str, ...]:
    """What the generic production executor would have to express for this row.

    Derived from the record's own ``decision_script`` selectors and
    ``native_procedure`` operations. The generic executor's dispatch is the
    authority for whether a requirement is met; this list makes the requirement
    auditable before execution and explains a measured stop.
    """
    requirements: list[str] = []
    for step in record.get("decision_script") or ():
        family = str(step.get("decision_family") or "")
        selection = step.get("selection") or {}
        selector = selection.get("selector_kind")
        if family == "priority":
            value = selection.get("semantic_value") or {}
            action = str(value.get("action") or "")
            requirements.append(f"priority_action:{action}")
            if "target" in value or "targets" in value:
                requirements.append("inline_target")
            if value.get("delve_objects"):
                requirements.append("inline_delve")
            if value.get("mana_payment"):
                requirements.append("inline_mana_payment")
            if value.get("alternative_cost"):
                requirements.append(f"alternative_cost:{value['alternative_cost']}")
            if value.get("x") is not None:
                requirements.append("inline_x")
        else:
            requirements.append(f"selector:{selector}")
    for procedure in record.get("native_procedure") or ():
        requirements.append(f"native_op:{procedure.get('operation')}")
    return tuple(requirements)


def derivation_requirement_labels(corpus: ActualCardCorpus) -> dict[str, Any]:
    """Per-row derived requirement labels for the machine-readable matrix."""
    return {
        row.fixture_id: {
            "required_state_dimensions": list(required_state_dimensions(row.record)),
            "executor_requirements": list(executor_requirements(row.record)),
        }
        for row in corpus.rows
    }


# --------------------------------------------------------------------------- #
# Obligation plans
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PostconditionProof:
    """How one terminal postcondition of a record is proven.

    Exactly one of ``event_token`` (a token that must appear in the record's own
    ``required_events`` and be positively observed on the engine tape) or
    ``terminal_check`` (a check evaluated against the engine's own observation)
    is set. The proof binds to the record's exact postcondition string so a
    record change makes the plan stale instead of silently proving something
    else.
    """

    postcondition: str
    event_token: str | None = None
    terminal_check: Any | None = None

    def __post_init__(self) -> None:
        if (self.event_token is None) == (self.terminal_check is None):
            raise ActualCardCampaignError(
                f"proof for {self.postcondition!r} must set exactly one of "
                "event_token/terminal_check"
            )

    def document(self) -> dict[str, Any]:
        if self.event_token is not None:
            return {"postcondition": self.postcondition, "event_token": self.event_token}
        check = self.terminal_check
        return {
            "postcondition": self.postcondition,
            "terminal_check": {
                "kind": check.kind,
                "principal": check.principal,
                "value": check.value,
                "source_name": check.source_name,
                "card_identity": check.card_identity,
            },
        }


@dataclass(frozen=True)
class ObligationPlan:
    """Declarative obligation interpretation for one fixture.

    A plan is *not* legality code and never names a card in generic logic; it
    declares how the record's own prose postconditions are observed. It is
    valid only while it covers exactly the record's effective postconditions.
    """

    fixture_id: str
    proofs: tuple[PostconditionProof, ...] = ()
    mode_bindings: tuple[tuple[str, str], ...] = ()
    commander_printed_mana_value: int | None = None
    max_decisions: int = 120

    @property
    def terminal_checks(self) -> tuple[Any, ...]:
        return tuple(
            proof.terminal_check for proof in self.proofs if proof.terminal_check is not None
        )

    @property
    def event_tokens(self) -> tuple[str, ...]:
        return tuple(proof.event_token for proof in self.proofs if proof.event_token is not None)

    def stale_reasons(self, record: Mapping[str, Any]) -> tuple[str, ...]:
        """Why this plan no longer matches the effective record (empty = valid)."""
        expected = _terminal_postconditions(record)
        declared = tuple(proof.postcondition for proof in self.proofs)
        reasons: list[str] = []
        if not expected:
            reasons.append("the record declares no terminal postcondition to cover")
        if len(declared) != len(set(declared)):
            reasons.append("the plan declares a postcondition more than once")
        if set(declared) != set(expected):
            reasons.append(
                "the plan's postconditions do not equal the record's: "
                f"declared={sorted(set(declared))} expected={sorted(set(expected))} "
                f"uncovered={sorted(set(expected) - set(declared))}"
            )
        required = set(_required_events(record))
        for proof in self.proofs:
            if proof.event_token is not None and proof.event_token not in required:
                reasons.append(
                    f"proof token {proof.event_token!r} is not one of the record's required events"
                )
        return tuple(reasons)

    def document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "proofs": [proof.document() for proof in self.proofs],
            "mode_bindings": [list(binding) for binding in self.mode_bindings],
            "commander_printed_mana_value": self.commander_printed_mana_value,
        }


def _life(principal: str, value: int) -> Any:
    return midgame_rows_mod.TerminalCheck("life", principal=principal, value=value)


def _commander_prior_casts(principal: str, value: int) -> Any:
    return midgame_rows_mod.TerminalCheck("commander_prior_casts", principal=principal, value=value)


def _on_battlefield(principal: str, identity: str) -> Any:
    return midgame_rows_mod.TerminalCheck(
        "on_battlefield", principal=principal, card_identity=identity
    )


# Plans are onboarded fixture by fixture. Each one covers the effective
# record's own postconditions exactly; ``stale_reasons`` fails the plan closed
# the moment the record's postconditions or required events change. A row with
# no plan is measured and classified, never credited.
PLANS: dict[str, ObligationPlan] = {
    # Rograkh costs {0}: the engine's cast and resolve are read from the tape,
    # the battlefield presence and the commander cast count from the engine's
    # own observation, and the absence of a mana payment from the decision
    # trace. The record's own postconditions name exactly those three facts.
    "CARD_02": ObligationPlan(
        fixture_id="CARD_02",
        proofs=(
            PostconditionProof(
                "Rograkh is on P1 battlefield.",
                terminal_check=_on_battlefield("P1", "Rograkh, Son of Rohgahh"),
            ),
            PostconditionProof(
                "commander cast count cmd:P1-A = 1.",
                terminal_check=_commander_prior_casts("P1", 1),
            ),
            PostconditionProof(
                "No commander-tax increment was charged.",
                terminal_check=midgame_rows_mod.TerminalCheck("no_mana_payment"),
            ),
        ),
    ),
    # Warstorm Surge's trigger is the required event ``entering_creature_damage:P2:2``
    # (a DAMAGED_PLAYER tape event), and the postcondition is the resulting life
    # total, read from the engine's own observation.
    "CARD_24": ObligationPlan(
        fixture_id="CARD_24",
        proofs=(
            PostconditionProof(
                "P2 is at 18 life after trigger resolves.",
                terminal_check=_life("P2", 18),
            ),
        ),
    ),
    # Kaervek's obligation is the triggered damage itself; the record's required
    # event ``damage:P2:4`` is the exact obligated fact, so the proof binds to
    # the tape rather than to an arithmetic total the record never states.
    "CARD_17": ObligationPlan(
        fixture_id="CARD_17",
        proofs=(
            PostconditionProof(
                "P2 is dealt 4 damage by Kaervek before the triggering spell resolves "
                "if no responses intervene.",
                event_token="damage:P2:4",
            ),
        ),
    ),
}


def plan_for(fixture_id: str) -> ObligationPlan | None:
    return PLANS.get(fixture_id)


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


def derive_row_spec(record: Mapping[str, Any], plan: ObligationPlan | None) -> Any:
    """The generic executor's ``RowSpec`` for one record, derived from the record.

    Mana sources are the record's own declared explicit payment sources, in the
    record's order; the executor taps only what the charged cost needs. Terminal
    checks and mode bindings come from the obligation plan. A row with no plan
    gets a spec with no terminal checks, so it can never verify: measurement
    output is diagnostic, not credit.
    """
    sources: list[str] = []
    for cost in record.get("action_cost_state") or ():
        for source in cost.get("explicit_payment_sources") or ():
            source = str(source)
            if source not in sources:
                sources.append(source)
    return midgame_rows_mod.RowSpec(
        mana_sources=tuple(sources),
        terminal_checks=plan.terminal_checks if plan else (),
        max_decisions=plan.max_decisions if plan else 120,
        commander_printed_mana_value=(
            plan.commander_printed_mana_value if plan is not None else None
        ),
        mode_bindings=plan.mode_bindings if plan is not None else (),
    )


def _engine_error_documents(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    errors = (payload or {}).get("errors") or []
    documents: list[dict[str, Any]] = []
    for error in errors:
        if isinstance(error, Mapping):
            documents.append(
                {
                    "code": error.get("code"),
                    "message": error.get("message"),
                }
            )
        else:
            documents.append({"code": None, "message": str(error)})
    return documents


@dataclass
class RowMeasurement:
    """What one live-lane attempt at one row observed."""

    fixture_id: str
    phase: str
    engine_commit: str | None = None
    engine_artifact: Mapping[str, Any] | None = None
    creation_errors: list[dict[str, Any]] = field(default_factory=list)
    start_errors: list[dict[str, Any]] = field(default_factory=list)
    construction_verdict: str | None = None
    construction_mismatches: list[str] = field(default_factory=list)
    arrival_detail: str | None = None
    execution: Mapping[str, Any] | None = None
    dimension_manifest: Mapping[str, Any] | None = None
    elapsed_s: float | None = None
    runtime_error: str | None = None

    def document(self) -> dict[str, Any]:
        return {
            "schema_version": MEASUREMENT_SCHEMA,
            "fixture_id": self.fixture_id,
            "phase": self.phase,
            "engine_commit": self.engine_commit,
            "engine_artifact": dict(self.engine_artifact) if self.engine_artifact else None,
            "creation_errors": self.creation_errors,
            "start_errors": self.start_errors,
            "construction_verdict": self.construction_verdict,
            "construction_mismatches": self.construction_mismatches,
            "arrival_detail": self.arrival_detail,
            "execution": self.execution,
            "starting_state_dimensions_manifest": self.dimension_manifest,
            "elapsed_s": self.elapsed_s,
            "runtime_error": self.runtime_error,
        }


def measure_row(
    client: ml.MidgameLaneClient,
    row: CardRow,
    plan: ObligationPlan | None,
    *,
    seed: int = SEED,
) -> RowMeasurement:
    """Execute one record on a fresh production midgame lane. Never fabricates.

    The engine decides construction, offers the options and reports the events;
    the generic production executor answers only from the record's own script.
    """
    import time

    started = time.time()
    record = dict(row.record)
    game_id = f"af07-{row.fixture_id}"
    request = {
        "game_id": game_id,
        "plan_id": game_id,
        "seed": seed,
        "requested_starting_state": record,
    }
    dimension_manifest: Mapping[str, Any] | None = None
    try:
        client.request("get_provider_version", None)
        manifest = client.read_dimension_manifest()
        dimension_manifest = manifest.as_dict()
        created = client.request("create_midgame_game", request)
    except ml.MidgameLaneError as exc:
        return RowMeasurement(
            fixture_id=row.fixture_id,
            phase="LANE_FAILED",
            engine_commit=client.engine_commit,
            engine_artifact=client.engine_artifact,
            arrival_detail=str(exc),
            elapsed_s=round(time.time() - started, 3),
        )
    if not created.get("success"):
        return RowMeasurement(
            fixture_id=row.fixture_id,
            phase="CREATION_REFUSED",
            engine_commit=client.engine_commit,
            engine_artifact=client.engine_artifact,
            creation_errors=_engine_error_documents(created),
            dimension_manifest=dimension_manifest,
            elapsed_s=round(time.time() - started, 3),
        )
    started_response = client.request("start_midgame_game", None)
    if not started_response.get("success"):
        return RowMeasurement(
            fixture_id=row.fixture_id,
            phase="START_REFUSED",
            engine_commit=client.engine_commit,
            engine_artifact=client.engine_artifact,
            start_errors=_engine_error_documents(started_response),
            dimension_manifest=dimension_manifest,
            elapsed_s=round(time.time() - started, 3),
        )
    spec = derive_row_spec(record, plan)
    execution = midgame_rows_mod.execute_row(client, record, created.get("payload") or {}, spec)
    document = execution.document()
    return RowMeasurement(
        fixture_id=row.fixture_id,
        phase="EXECUTED",
        engine_commit=client.engine_commit,
        engine_artifact=client.engine_artifact,
        construction_verdict=execution.construction_verdict,
        execution=document,
        dimension_manifest=dimension_manifest,
        elapsed_s=round(time.time() - started, 3),
    )


# --------------------------------------------------------------------------- #
# Evaluation and classification
# --------------------------------------------------------------------------- #


def plan_proof_status(row: CardRow, execution: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Evaluate every declared proof against the execution's own evidence."""
    plan = plan_for(row.fixture_id)
    if plan is None:
        return []
    token_evidence = execution.get("token_evidence") or {}
    terminal_facts = execution.get("terminal_facts") or {}
    statuses: list[dict[str, Any]] = []
    for proof in plan.proofs:
        if proof.event_token is not None:
            held = proof.event_token in token_evidence
            statuses.append(
                {
                    "postcondition": proof.postcondition,
                    "kind": "event_token",
                    "token": proof.event_token,
                    "held": bool(held),
                }
            )
        else:
            description = proof.terminal_check.describe()
            held = bool(terminal_facts.get(description))
            statuses.append(
                {
                    "postcondition": proof.postcondition,
                    "kind": "terminal_check",
                    "check": description,
                    "held": held,
                }
            )
    return statuses


def _first_error_detail(measurement: RowMeasurement) -> str:
    for error in [*measurement.creation_errors, *measurement.start_errors]:
        if error.get("message"):
            return str(error["message"])
    return ""


# The restoration's own refusal tokens and the record-side dimension each one
# corresponds to. The mapping is only consulted together with the record's
# derived dimensions, so an engine token cannot attribute a blocker the record
# does not declare.
_ENGINE_REFUSAL_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("COMMANDER_ZONE", "stack_objects"),
    ("COUNTERS", "counters"),
    ("ATTACHMENTS", "tapped_permanents"),
    ("TAPPED", "tapped_permanents"),
    ("FACE_DOWN", "face_down"),
    ("CONTROL", "control_divergence"),
)

_ENGINE_REFUSAL_ZONE_DIMENSIONS: Mapping[str, str] = {
    "stack": "stack_objects",
    "library": "library_identity_objects",
}


def engine_named_refusal_dimension(
    detail: str, derived_dimensions: tuple[str, ...]
) -> tuple[str | None, str | None]:
    """The dimension the engine's own refusal message names, if any.

    Returns ``(dimension, engine_token)``. A dimension is returned only when the
    record actually declares it, so the attribution always has two independent
    sides: the engine refused it, and the record requires it.
    """
    zone_match = re.search(
        r"UNSUPPORTED_ZONE:\s*\S+\s+\S+\s+requests\s+([a-z_]+)", detail, re.IGNORECASE
    )
    if zone_match:
        zone = zone_match.group(1).lower()
        token = f"UNSUPPORTED_ZONE:{zone}"
        dimension = _ENGINE_REFUSAL_ZONE_DIMENSIONS.get(zone)
        if dimension is not None and dimension in derived_dimensions:
            return dimension, token
        return None, token
    for token_name, dimension in _ENGINE_REFUSAL_DIMENSIONS:
        if f"UNSUPPORTED_{token_name}" in detail and dimension in derived_dimensions:
            return dimension, f"UNSUPPORTED_{token_name}"
    return None, None


def classify(
    row: CardRow,
    measurement: RowMeasurement,
    *,
    expected_engine_commit: str | None,
    foreign_owned_surfaces: Mapping[str, str] | None = None,
    causal_entry_rows: Collection[str] = (),
) -> dict[str, Any]:
    """Deterministic classification of one measured row.

    Returns the row's outcome plus, for every non-PASS row, exactly one blocker
    class with the exact surface and owner. No branch here can produce
    ``DIRECT_PASS``; that is decided only by :func:`evaluate_row`.
    """
    surfaces = dict(foreign_owned_surfaces or {})

    def dependency(surface: str, detail: str) -> dict[str, Any]:
        owner = surfaces.get(surface)
        if owner:
            return {
                "outcome": OUTCOME_BLOCKED,
                "blocker_class": BLOCKER_DEPENDENCY_WAITING,
                "blocker_surface": surface,
                "blocker_owner": owner,
                "blocker_detail": detail,
            }
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_HARNESS_DEFECT,
            "blocker_surface": surface,
            "blocker_owner": None,
            "blocker_detail": detail,
        }

    if measurement.phase == "CREATION_REFUSED":
        codes = [str(error.get("code") or "") for error in measurement.creation_errors]
        detail = _first_error_detail(measurement)
        dimensions = required_state_dimensions(row.record)
        unsupported = [
            dimension
            for dimension in dimensions
            if dimension
            in {
                "stack_objects",
                "counters",
                "tapped_permanents",
                "face_down",
                "control_divergence",
                "library_identity_objects",
            }
        ]
        named_dimension, engine_token = engine_named_refusal_dimension(detail, dimensions)
        if "midgame_starting_state_rejected" in codes:
            if named_dimension == "stack_objects" and row.fixture_id in causal_entry_rows:
                # The direct native load refuses the stack, but the current
                # production probe declares a causal entry for this row and can
                # reach the position; the causal driver is where the remaining
                # work lives.
                return dependency(
                    SURFACE_MIDGAME_PROBE,
                    "the direct native state load refuses the record's stack object "
                    f"({engine_token}); the current production probe declares a causal-entry "
                    f"route for this row but its driver is owned by the foreign writer and does "
                    f"not execute the obligation yet; engine detail: {detail}",
                )
            if named_dimension:
                manifest = measurement.dimension_manifest or {}
                keyword = named_dimension.split("_")[0]
                named_text = [
                    str(item)
                    for item in manifest.get("unsupported_dimensions") or ()
                    if keyword in str(item).lower()
                ]
                return {
                    "outcome": OUTCOME_BLOCKED,
                    "blocker_class": BLOCKER_PROVIDER_ADAPTER_DEFECT,
                    "blocker_surface": SURFACE_NATIVE_RESTORATION,
                    "blocker_owner": None,
                    "blocker_detail": (
                        f"the engine refused the requested starting state ({engine_token}); its "
                        f"own manifest names the dimension as unsupported: {named_text[:1]}; "
                        f"engine detail: {detail}"
                    ),
                }
            if unsupported:
                return {
                    "outcome": OUTCOME_BLOCKED,
                    "blocker_class": BLOCKER_PROVIDER_ADAPTER_DEFECT,
                    "blocker_surface": SURFACE_NATIVE_RESTORATION,
                    "blocker_owner": None,
                    "blocker_detail": (
                        "the engine refused to construct the requested starting state; the record "
                        f"requires dimension(s) {unsupported} that the bridge restoration does not "
                        f"construct; engine detail: {detail}"
                    ),
                }
        if "midgame_causal_preparation_rejected" in codes:
            return {
                "outcome": OUTCOME_BLOCKED,
                "blocker_class": BLOCKER_PROVIDER_ADAPTER_DEFECT,
                "blocker_surface": SURFACE_NATIVE_RESTORATION,
                "blocker_owner": None,
                "blocker_detail": (
                    "the engine refused the causal preparation of the requested position; "
                    f"engine detail: {detail}"
                ),
            }
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": (
                f"the engine refused construction with codes {codes}; no attribution rule "
                f"matches this refusal; engine detail: {detail}"
            ),
        }

    if measurement.phase in {"START_REFUSED", "LANE_FAILED"}:
        detail = _first_error_detail(measurement) or measurement.arrival_detail or "no detail"
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": f"the lane did not reach an executable state: {detail}",
        }

    if measurement.phase != "EXECUTED" or not measurement.execution:
        return {
            "outcome": OUTCOME_UNKNOWN,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": f"measurement phase {measurement.phase!r} has no executable evidence",
        }

    execution = measurement.execution
    detail = str(execution.get("detail") or "")
    if measurement.engine_commit is None or (
        expected_engine_commit is not None and measurement.engine_commit != expected_engine_commit
    ):
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": (
                f"engine reported build {measurement.engine_commit!r}, expected "
                f"{expected_engine_commit!r}; the row cannot be bound to the pinned candidate"
            ),
        }
    if "is not executed by this lane" in detail:
        return dependency(
            SURFACE_MIDGAME_ROWS,
            f"the generic production executor cannot express the record's scripted step: {detail}",
        )
    if detail.startswith("unscripted "):
        # Which surface owns the fix is decided by whether the effective record
        # declares a step for the offered decision family at all. A scripted
        # family the executor failed to answer is an executor gap; a family the
        # record never scripts is a fixture-contract gap.
        frame_match = re.match(r"unscripted ([a-z_]+) for (P\d+)", detail)
        scripted_classes = {
            midgame_rows_mod.engine_decision_class(str(step.get("decision_family") or ""))
            for step in row.record.get("decision_script") or ()
        }
        frame_class = frame_match.group(1) if frame_match else None
        if (
            frame_class in scripted_classes
            or frame_class in EXECUTOR_SURFACE_DECISION_CLASSES
            or frame_class is None
        ):
            return dependency(
                SURFACE_MIDGAME_ROWS,
                "the engine offered a decision the generic production executor cannot answer "
                f"from the record's declared script: {detail}",
            )
        return dependency(
            SURFACE_SUCCESSOR_CONTRACT,
            "the engine offered a discretionary decision class the effective record does not "
            f"script ({frame_class!r}; the record scripts {sorted(scripted_classes)}); recorded "
            "by the engine as: " + detail,
        )
    if detail.startswith("arrival failed closed"):
        return dependency(
            SURFACE_MIDGAME_PROBE,
            f"the record-aware arrival driver refused the row: {detail}",
        )
    if detail.startswith("the engine did not reach the record's checkpoint"):
        return dependency(
            SURFACE_MIDGAME_PROBE,
            f"the arrival driver never reached the record's temporal checkpoint: {detail}",
        )
    if detail.startswith("construction "):
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": SURFACE_NATIVE_RESTORATION,
            "blocker_owner": None,
            "blocker_detail": (
                f"the engine's field-level readback did not accept the construction: {detail}"
            ),
        }
    if detail.startswith("a declared mana source was not placed"):
        return dependency(
            SURFACE_MIDGAME_ROWS,
            f"the record's declared mana sources are not in the constructed state: {detail}",
        )
    if detail.startswith("the obligation names no required event and no terminal check"):
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_FIXTURE_DEFECT,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": detail,
        }

    missing = list(execution.get("missing_tokens") or ())
    if missing:
        return {
            "outcome": OUTCOME_BLOCKED,
            "blocker_class": BLOCKER_UNKNOWN,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": (
                "the required event tokens were not positively observed and no plan-declared "
                f"proof covers them: {missing}"
            ),
        }
    if plan_for(row.fixture_id) is None:
        return {
            "outcome": OUTCOME_MEASURED,
            "blocker_class": BLOCKER_HARNESS_DEFECT,
            "blocker_surface": SURFACE_CAMPAIGN,
            "blocker_owner": None,
            "blocker_detail": (
                "the row consumed its script and its required events were observed, but this "
                "campaign has not onboarded an obligation plan covering the record's terminal "
                "postconditions; partial evidence earns no verdict"
            ),
        }
    return {
        "outcome": OUTCOME_MEASURED,
        "blocker_class": BLOCKER_HARNESS_DEFECT,
        "blocker_surface": SURFACE_CAMPAIGN,
        "blocker_owner": None,
        "blocker_detail": (
            f"the row executed but did not reach a verified obligation: {detail or 'no detail'}"
        ),
    }


def evaluate_row(
    row: CardRow,
    measurement: RowMeasurement,
    *,
    expected_engine_commit: str | None,
    foreign_owned_surfaces: Mapping[str, str] | None = None,
    causal_entry_rows: Collection[str] = (),
) -> dict[str, Any]:
    """The row's verdict. ``DIRECT_PASS`` requires complete, bound evidence."""
    plan = plan_for(row.fixture_id)
    stale = plan.stale_reasons(row.record) if plan is not None else ()
    execution = measurement.execution or {}
    classification = classify(
        row,
        measurement,
        expected_engine_commit=expected_engine_commit,
        foreign_owned_surfaces=foreign_owned_surfaces,
        causal_entry_rows=causal_entry_rows,
    )
    proofs = plan_proof_status(row, execution) if plan is not None else []
    verified = bool(execution.get("verified"))
    construction = measurement.construction_verdict or execution.get("construction_verdict")
    construction_accepted = construction in set(midgame_rows_mod.ACCEPTED_CONSTRUCTION)
    complete_plan = bool(plan is not None and proofs and all(item["held"] for item in proofs))
    direct_pass = bool(
        measurement.phase == "EXECUTED"
        and verified
        and construction_accepted
        and plan is not None
        and not stale
        and complete_plan
        and measurement.engine_commit == expected_engine_commit
    )
    document = classification
    if direct_pass:
        document = {
            "outcome": OUTCOME_DIRECT_PASS,
            "blocker_class": None,
            "blocker_surface": None,
            "blocker_owner": None,
            "blocker_detail": None,
        }
    document.update(
        {
            "fixture_id": row.fixture_id,
            "card_identity": row.card_identity,
            "construction_verdict": construction,
            "engine_verified": verified,
            "plan": plan.document() if plan is not None else None,
            "plan_stale_reasons": list(stale),
            "postcondition_proofs": proofs,
            "direct_receipt_eligible": direct_pass,
            "credit_route": (
                "effective_provider_denominator"
                if row.in_effective_denominator
                else "frozen_denominator_exclusion"
            ),
        }
    )
    return document


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


def positive_receipt(
    row: CardRow,
    evaluation: Mapping[str, Any],
    measurement: RowMeasurement,
    *,
    candidate: str,
    candidate_commit: str,
    runner_digest: str,
) -> dict[str, Any]:
    """The runner-bound positive receipt for a directly proven row.

    Shaped exactly like the current positive-fixture receipt contract so the
    Phase 2 assembler can credit it without a second receipt dialect; the
    campaign's identity prefix keeps the producing route auditable.
    """
    if evaluation.get("outcome") != OUTCOME_DIRECT_PASS:
        raise ActualCardCampaignError(
            f"{row.fixture_id} is not directly proven; no positive receipt"
        )
    execution = measurement.execution or {}
    document: dict[str, Any] = {
        "schema_version": receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": candidate,
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": row.fixture_id,
        "test_identity": TEST_IDENTITY_PREFIX + row.fixture_id,
        "execution_mode": EXECUTION_MODE,
        "construction_verdict": evaluation.get("construction_verdict"),
        "obligation_exercised": {
            "required_events": list(row.required_events),
            "terminal_postconditions": list(row.terminal_postconditions),
            "terminal_checks": sorted(execution.get("terminal_facts") or {}),
            "requested_state_digest": row.requested_state_digest,
            "obligation_digest": row.obligation_digest,
        },
        "observed_assertion": {
            "token_evidence": execution.get("token_evidence") or {},
            "terminal_facts": execution.get("terminal_facts") or {},
            "typed_refusals": execution.get("refusals") or [],
            "postcondition_proofs": evaluation.get("postcondition_proofs") or [],
            "engine_artifact": measurement.engine_artifact,
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "assertion_class": (
            "TYPED_FAIL_CLOSED_REFUSAL" if execution.get("refusals") else "BEHAVIOUR_OBSERVED"
        ),
        "outcome": "PASS",
        "runtime_receipt_digest": receipt_mod.document_digest(dict(execution)),
    }
    document["receipt_digest"] = receipt_mod.document_digest(document)
    return document


# --------------------------------------------------------------------------- #
# Machine-readable matrix
# --------------------------------------------------------------------------- #


def matrix_row(
    row: CardRow,
    evaluation: Mapping[str, Any],
    measurement: RowMeasurement | None,
) -> dict[str, Any]:
    execution = (measurement.execution if measurement is not None else None) or {}
    trace = [
        {
            "decision_class": frame.get("decision_class"),
            "principal": frame.get("principal"),
            "offered_labels": len(frame.get("offered_labels") or ()),
            "scripted": frame.get("scripted"),
            "selected_key": frame.get("selected_key"),
            "refused": frame.get("refused"),
        }
        for frame in execution.get("decision_trace") or ()
    ]
    return {
        "fixture_id": row.fixture_id,
        "card_identity": row.card_identity,
        "record": row.identity_document(),
        "derived_requirements": {
            "required_state_dimensions": list(required_state_dimensions(row.record)),
            "executor_requirements": list(executor_requirements(row.record)),
        },
        "verdict": dict(evaluation),
        "measurement": {
            "phase": measurement.phase if measurement is not None else None,
            "engine_commit": measurement.engine_commit if measurement is not None else None,
            "engine_artifact": (
                dict(measurement.engine_artifact)
                if measurement is not None and measurement.engine_artifact
                else None
            ),
            "creation_errors": measurement.creation_errors if measurement is not None else [],
            "start_errors": measurement.start_errors if measurement is not None else [],
            "elapsed_s": measurement.elapsed_s if measurement is not None else None,
            "execution_detail": execution.get("detail"),
            "missing_tokens": execution.get("missing_tokens") or [],
            "token_evidence": execution.get("token_evidence") or {},
            "terminal_facts": execution.get("terminal_facts") or {},
            "decision_trace": trace,
        },
        "receipt_digest": evaluation.get("receipt_digest"),
    }


def build_matrix(
    corpus: ActualCardCorpus,
    evaluations: Mapping[str, Mapping[str, Any]],
    measurements: Mapping[str, RowMeasurement] | None = None,
    *,
    campaign_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The machine-readable 29-row ledger. Every frozen identity appears."""
    measurements = measurements or {}
    rows: list[dict[str, Any]] = []
    for row in corpus.rows:
        evaluation = dict(evaluations.get(row.fixture_id) or {})
        if not evaluation:
            evaluation = {
                "outcome": OUTCOME_UNKNOWN,
                "blocker_class": BLOCKER_UNKNOWN,
                "blocker_surface": None,
                "blocker_owner": None,
                "blocker_detail": "the row was not executed in this campaign run",
                "direct_receipt_eligible": False,
            }
        rows.append(matrix_row(row, evaluation, measurements.get(row.fixture_id)))
    outcomes = [str(row["verdict"].get("outcome")) for row in rows]
    classes = [
        str(row["verdict"].get("blocker_class"))
        for row in rows
        if row["verdict"].get("blocker_class")
    ]
    direct: list[str] = []
    inconsistent: list[str] = []
    for row in rows:
        verdict = row["verdict"]
        if verdict.get("outcome") != OUTCOME_DIRECT_PASS:
            continue
        if verdict.get("direct_receipt_eligible") is True:
            direct.append(row["fixture_id"])
        else:
            inconsistent.append(row["fixture_id"])
    if inconsistent:
        raise ActualCardCampaignError(
            "a DIRECT_PASS row carries no receipt eligibility; the matrix refuses to "
            f"report a pass it cannot receipt: {inconsistent}"
        )
    receipt_eligible = [
        row["fixture_id"] for row in rows if row["verdict"].get("direct_receipt_eligible")
    ]
    if len(rows) != CORPUS_COUNT:
        raise ActualCardCampaignError(
            f"the matrix must carry exactly {CORPUS_COUNT} identities, got {len(rows)}"
        )
    return {
        "schema_version": MATRIX_SCHEMA,
        "campaign": dict(campaign_identity or {}),
        "corpus": {
            "required_count": CORPUS_COUNT,
            "identities_source": corpus.domain_manifest,
            "fixture_source": corpus.fixture_manifest,
            "denominator_artifact": corpus.denominator_artifact,
            "identities": list(corpus.identities),
            "fixture_identities": dict(corpus.fixture_identities),
            "materialization": dict(corpus.materialization_receipt),
        },
        "summary": {
            "row_count": len(rows),
            "outcomes": {state: outcomes.count(state) for state in sorted(set(outcomes))},
            "blockers": {state: classes.count(state) for state in sorted(set(classes))},
            "direct_pass": direct,
            "direct_receipt_eligible": receipt_eligible,
            "in_effective_provider_denominator": [
                row.fixture_id for row in corpus.rows if row.in_effective_denominator
            ],
            "excluded_by_frozen_denominator": [
                row.fixture_id for row in corpus.rows if row.excluded_by_frozen_denominator
            ],
        },
        "rows": rows,
    }


def write_matrix(path: Path, matrix: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(matrix, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def write_measurement(path: Path, measurement: RowMeasurement) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(measurement.document(), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def matrix_digest(matrix: Mapping[str, Any]) -> str:
    return receipt_mod.document_digest(dict(matrix))
