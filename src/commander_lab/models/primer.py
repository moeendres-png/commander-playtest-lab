from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel
from .meta import FormatBand
from .pilots import PilotActionView, PilotStateView
from .roles import CardRole

PRIMER_RULE_SCHEMA_VERSION = "1.0.0"


class PrimerFormat(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"
    CURATED = "curated"


class PrimerEvidenceType(StrEnum):
    PRIMER_EXPLICIT = "primer_explicit"
    PRIMER_INFERRED = "primer_inferred"
    LOCAL_USER_INSTRUCTION = "local_user_instruction"
    GOLDEN_SCENARIO = "golden_scenario"
    TACTICAL_ORACLE = "tactical_oracle"
    STRUCTURAL_EVALUATION = "structural_evaluation"


class PrimerRuleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class DecisionPoint(StrEnum):
    OPENING_HAND = "opening_hand"
    MAIN_ACTION = "main_action"
    REACTION = "reaction"
    COMBAT_TARGET = "combat_target"
    SEQUENCING = "sequencing"
    REBUILD = "rebuild"


class ConditionOperator(StrEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"
    INTERSECTS = "intersects"
    TRUTHY = "truthy"
    FALSY = "falsy"


class PilotRuleCondition(FrozenModel):
    op: ConditionOperator
    field: str | None = None
    value: Any = None
    clauses: tuple[PilotRuleCondition, ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> PilotRuleCondition:
        logical = {ConditionOperator.ALL, ConditionOperator.ANY, ConditionOperator.NOT}
        if self.op in logical:
            if self.field is not None:
                raise ValueError("logical conditions cannot define field")
            if self.op == ConditionOperator.NOT and len(self.clauses) != 1:
                raise ValueError("not condition requires exactly one clause")
            if self.op != ConditionOperator.NOT and not self.clauses:
                raise ValueError(f"{self.op} condition requires clauses")
        else:
            if not self.field:
                raise ValueError(f"{self.op} condition requires field")
            if self.clauses:
                raise ValueError("leaf conditions cannot define clauses")
        return self


class ActionPreference(FrozenModel):
    decision_point: DecisionPoint = DecisionPoint.MAIN_ACTION
    action_kinds: tuple[str, ...] = ()
    card_names: tuple[str, ...] = ()
    roles: tuple[CardRole, ...] = ()
    match_mode: Literal["any", "all"] = "any"
    description: str

    @model_validator(mode="after")
    def require_selector_or_opening_hand(self) -> ActionPreference:
        if self.decision_point != DecisionPoint.OPENING_HAND and not (
            self.action_kinds or self.card_names or self.roles
        ):
            raise ValueError("action preference requires at least one selector")
        return self


class PilotRule(FrozenModel):
    rule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    source_id: str
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    condition: PilotRuleCondition
    action_preference: ActionPreference
    score_adjustment: float = Field(ge=-20.0, le=20.0)
    priority: int = Field(default=50, ge=0, le=1000)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    requires_cards: tuple[str, ...] = ()
    forbidden_when: tuple[PilotRuleCondition, ...] = ()
    evidence_type: PrimerEvidenceType
    status: PrimerRuleStatus = PrimerRuleStatus.NEEDS_REVIEW
    manually_approved: bool = False
    rationale: str
    source_excerpt: str | None = Field(default=None, max_length=400)
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_approval_for_inferred_active_rule(self) -> PilotRule:
        if (
            self.status == PrimerRuleStatus.ACTIVE
            and self.evidence_type
            in {
                PrimerEvidenceType.PRIMER_EXPLICIT,
                PrimerEvidenceType.PRIMER_INFERRED,
            }
            and not self.manually_approved
        ):
            raise ValueError("primer-derived rules require manual approval before activation")
        return self


class PrimerDocument(FrozenModel):
    primer_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    source_id: str
    title: str
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    primer_format: PrimerFormat
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    imported_at: datetime
    source_path: str | None = None
    raw_text_stored: bool = False
    license_notes: str = "structured extraction only unless the source is user-provided"
    notes: str | None = None


class PrimerRegistry(MutableModel):
    schema_version: str = PRIMER_RULE_SCHEMA_VERSION
    primers: tuple[PrimerDocument, ...] = ()
    rules: tuple[PilotRule, ...] = ()


class RuleValidationIssue(FrozenModel):
    rule_id: str
    severity: Literal["error", "warning"]
    code: str
    message: str


class RuleValidationReport(FrozenModel):
    valid: bool
    rule_count: int
    active_rule_count: int
    issues: tuple[RuleValidationIssue, ...] = ()


class PrimerRuleConflict(FrozenModel):
    conflict_id: str
    rule_ids: tuple[str, ...]
    conflict_type: Literal[
        "opposing_adjustment",
        "duplicate_rule_id",
        "deck_version_mismatch",
        "format_band_mismatch",
        "source_disagreement",
    ]
    description: str
    resolution_required: bool = True


class CompiledPilotPolicy(FrozenModel):
    policy_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    created_at: datetime
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    base_pilot_name: str
    source_ids: tuple[str, ...]
    rules: tuple[PilotRule, ...]
    conflicts: tuple[PrimerRuleConflict, ...] = ()
    immutable: bool = True
    automatic_deck_application: bool = False
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_policy(self) -> CompiledPilotPolicy:
        if not self.immutable:
            raise ValueError("compiled pilot policies must be immutable")
        if self.automatic_deck_application:
            raise ValueError("primer policies must never apply deck changes")
        for rule in self.rules:
            if rule.commander != self.commander or rule.deck_hash != self.deck_hash:
                raise ValueError("policy contains an incompatible rule")
            if rule.format_band != self.format_band:
                raise ValueError("policy contains a mismatched format band")
        return self


class PolicyDecisionTrace(FrozenModel):
    rule_id: str
    adjustment: float
    reason: str


class PolicyActionScore(FrozenModel):
    action_id: str
    baseline_score: float
    overlay_score: float
    triggered_rules: tuple[PolicyDecisionTrace, ...] = ()


class PolicyEvalScenario(FrozenModel):
    scenario_id: str
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    state: PilotStateView
    actions: tuple[PilotActionView, ...]
    expected_action_id: str
    context: dict[str, Any] = Field(default_factory=dict)
    evidence_type: PrimerEvidenceType
    notes: str | None = None


class PolicyEvalResult(FrozenModel):
    scenario_id: str
    baseline_action_id: str | None
    overlay_action_id: str | None
    expected_action_id: str
    baseline_correct: bool
    overlay_correct: bool
    improved: bool
    action_scores: tuple[PolicyActionScore, ...]
    conflicts: tuple[str, ...] = ()


PilotRuleCondition.model_rebuild()
