from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from commander_lab.agents.pilots import BasePilot
from commander_lab.models.meta import FormatBand
from commander_lab.models.pilots import (
    PilotActionView,
    PilotDecision,
    PilotStateView,
    PilotUtilityBreakdown,
)
from commander_lab.models.primer import (
    ActionPreference,
    CompiledPilotPolicy,
    ConditionOperator,
    DecisionPoint,
    PilotRule,
    PilotRuleCondition,
    PolicyActionScore,
    PolicyDecisionTrace,
    PolicyEvalResult,
    PolicyEvalScenario,
    PrimerDocument,
    PrimerEvidenceType,
    PrimerFormat,
    PrimerRegistry,
    PrimerRuleConflict,
    PrimerRuleStatus,
    RuleValidationIssue,
    RuleValidationReport,
)
from commander_lab.models.roles import CardRole
from commander_lab.storage import atomic_write_json


class RuleDslError(ValueError):
    pass


_ALLOWED_STATE_FIELDS = {
    "player_id",
    "deck_id",
    "strategy",
    "turn",
    "pod_size",
    "life",
    "hand_size",
    "mana_available",
    "lands",
    "ramp_mana",
    "resources",
    "tokens",
    "board_power",
    "engine_value",
    "graveyard_size",
    "battlefield_names",
    "hand_names",
    "commander_online",
    "max_opponent_threat",
    "enemy_board_total",
    "lowest_opponent_life",
    "max_graveyard_pressure",
}
_ALLOWED_ACTION_FIELDS = {
    "action_id",
    "action_kind",
    "card_name",
    "mana_cost",
    "roles",
    "floor_value",
    "immediate_impact",
    "turn_cycle_risk",
    "multiplayer_scaling",
    "commander_synergy",
    "base_power",
    "target_player_id",
    "target_threat",
    "threat_score",
    "remaining_mana",
}
_ALLOWED_CONTEXT_FIELDS = {
    "always",
    "land_count",
    "ramp_count",
    "sacrifice_material_count",
    "protection_available",
    "finish_window",
    "boardwipe_resolved",
    "graveyard_hate_visible",
    "package_complete",
    "opponent_can_win_next_turn",
    "commander_immediate_value",
    "spellslinger_axis_available",
    "ishai_online",
    "rograkh_online",
}


def _normalize_card(value: str) -> str:
    return " ".join(value.casefold().split())


def _content_hash(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _resolve_field(
    field: str,
    *,
    state: PilotStateView | None,
    action: PilotActionView | None,
    context: Mapping[str, Any],
    deck_cards: Sequence[str],
    deck_hash: str,
) -> Any:
    if field == "deck.cards":
        return tuple(deck_cards)
    if field == "deck.deck_hash":
        return deck_hash
    if field.startswith("state.role_counts."):
        if state is None:
            return 0
        role_name = field.removeprefix("state.role_counts.")
        try:
            role = CardRole(role_name)
        except ValueError as exc:
            raise RuleDslError(f"unsupported role field: {field}") from exc
        return state.role_counts.get(role, 0)
    if field.startswith("action.metadata."):
        if action is None:
            return None
        key = field.removeprefix("action.metadata.")
        if not key or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
            raise RuleDslError(f"unsafe action metadata field: {field}")
        return action.metadata.get(key)
    if field.startswith("state."):
        if state is None:
            return None
        name = field.removeprefix("state.")
        if name not in _ALLOWED_STATE_FIELDS:
            raise RuleDslError(f"unsupported state field: {field}")
        return getattr(state, name)
    if field.startswith("action."):
        if action is None:
            return None
        name = field.removeprefix("action.")
        if name not in _ALLOWED_ACTION_FIELDS:
            raise RuleDslError(f"unsupported action field: {field}")
        value = getattr(action, name)
        if name == "roles":
            return tuple(sorted(role.value for role in value))
        return value
    if field.startswith("context."):
        name = field.removeprefix("context.")
        if name not in _ALLOWED_CONTEXT_FIELDS:
            raise RuleDslError(f"unsupported context field: {field}")
        return context.get(name)
    raise RuleDslError(f"unsupported DSL field: {field}")


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(value)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def evaluate_condition(
    condition: PilotRuleCondition,
    *,
    state: PilotStateView | None,
    action: PilotActionView | None,
    context: Mapping[str, Any] | None = None,
    deck_cards: Sequence[str] = (),
    deck_hash: str = "",
) -> bool:
    ctx = context or {}
    if condition.op == ConditionOperator.ALL:
        return all(
            evaluate_condition(
                clause,
                state=state,
                action=action,
                context=ctx,
                deck_cards=deck_cards,
                deck_hash=deck_hash,
            )
            for clause in condition.clauses
        )
    if condition.op == ConditionOperator.ANY:
        return any(
            evaluate_condition(
                clause,
                state=state,
                action=action,
                context=ctx,
                deck_cards=deck_cards,
                deck_hash=deck_hash,
            )
            for clause in condition.clauses
        )
    if condition.op == ConditionOperator.NOT:
        return not evaluate_condition(
            condition.clauses[0],
            state=state,
            action=action,
            context=ctx,
            deck_cards=deck_cards,
            deck_hash=deck_hash,
        )

    assert condition.field is not None
    actual = _resolve_field(
        condition.field,
        state=state,
        action=action,
        context=ctx,
        deck_cards=deck_cards,
        deck_hash=deck_hash,
    )
    expected = condition.value
    if condition.op == ConditionOperator.EQ:
        return actual == expected
    if condition.op == ConditionOperator.NE:
        return actual != expected
    if condition.op == ConditionOperator.GT:
        return actual is not None and actual > expected
    if condition.op == ConditionOperator.GE:
        return actual is not None and actual >= expected
    if condition.op == ConditionOperator.LT:
        return actual is not None and actual < expected
    if condition.op == ConditionOperator.LE:
        return actual is not None and actual <= expected
    if condition.op == ConditionOperator.TRUTHY:
        return bool(actual)
    if condition.op == ConditionOperator.FALSY:
        return not bool(actual)

    actual_values = _as_sequence(actual)
    expected_values = _as_sequence(expected)
    if condition.field in {"deck.cards", "state.hand_names", "state.battlefield_names"}:
        actual_values = tuple(_normalize_card(str(item)) for item in actual_values)
        expected_values = tuple(_normalize_card(str(item)) for item in expected_values)
    if condition.op == ConditionOperator.CONTAINS:
        return expected_values[0] in actual_values if expected_values else False
    if condition.op == ConditionOperator.NOT_CONTAINS:
        return expected_values[0] not in actual_values if expected_values else True
    if condition.op == ConditionOperator.CONTAINS_ANY:
        return bool(set(actual_values) & set(expected_values))
    if condition.op == ConditionOperator.CONTAINS_ALL:
        return set(expected_values).issubset(set(actual_values))
    if condition.op == ConditionOperator.INTERSECTS:
        return bool(set(actual_values) & set(expected_values))
    raise RuleDslError(f"unsupported condition operator: {condition.op}")


def _preference_matches(preference: ActionPreference, action: PilotActionView | None) -> bool:
    if preference.decision_point == DecisionPoint.OPENING_HAND:
        return action is None
    if action is None:
        return False
    tests: list[bool] = []
    if preference.action_kinds:
        tests.append(action.action_kind in preference.action_kinds)
    if preference.card_names:
        allowed = {_normalize_card(card) for card in preference.card_names}
        tests.append(_normalize_card(action.card_name) in allowed)
    if preference.roles:
        selected = set(preference.roles)
        tests.append(
            selected.issubset(action.roles)
            if preference.match_mode == "all"
            else bool(selected & action.roles)
        )
    if not tests:
        return False
    return all(tests) if preference.match_mode == "all" else any(tests)


def _rule_scope_matches(
    rule: PilotRule,
    *,
    commander: str,
    deck_hash: str,
    format_band: FormatBand,
    deck_cards: Sequence[str],
) -> bool:
    if (
        rule.commander != commander
        or rule.deck_hash != deck_hash
        or rule.format_band != format_band
    ):
        return False
    cards = {_normalize_card(card) for card in deck_cards}
    return all(_normalize_card(card) in cards for card in rule.requires_cards)


def _rule_matches(
    rule: PilotRule,
    *,
    state: PilotStateView | None,
    action: PilotActionView | None,
    context: Mapping[str, Any],
    commander: str,
    deck_hash: str,
    format_band: FormatBand,
    deck_cards: Sequence[str],
) -> bool:
    if rule.status != PrimerRuleStatus.ACTIVE:
        return False
    if not _rule_scope_matches(
        rule,
        commander=commander,
        deck_hash=deck_hash,
        format_band=format_band,
        deck_cards=deck_cards,
    ):
        return False
    if not _preference_matches(rule.action_preference, action):
        return False
    if not evaluate_condition(
        rule.condition,
        state=state,
        action=action,
        context=context,
        deck_cards=deck_cards,
        deck_hash=deck_hash,
    ):
        return False
    return not any(
        evaluate_condition(
            forbidden,
            state=state,
            action=action,
            context=context,
            deck_cards=deck_cards,
            deck_hash=deck_hash,
        )
        for forbidden in rule.forbidden_when
    )


class PilotPolicyOverlay:
    """Reversible score overlay around an unchanged base pilot."""

    def __init__(
        self,
        base_pilot: BasePilot,
        policy: CompiledPilotPolicy,
        *,
        deck_cards: Sequence[str],
    ) -> None:
        self.base_pilot = base_pilot
        self.policy = policy
        self.deck_cards = tuple(deck_cards)
        self.pilot_name = f"{base_pilot.pilot_name}+{policy.policy_id}"

    def evaluate_action_with_trace(
        self,
        state: PilotStateView,
        action: PilotActionView,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[PilotUtilityBreakdown, tuple[PolicyDecisionTrace, ...]]:
        baseline = self.base_pilot.evaluate_action(state, action)
        traces: list[PolicyDecisionTrace] = []
        for rule in sorted(
            self.policy.rules, key=lambda item: (item.priority, item.rule_id), reverse=True
        ):
            if _rule_matches(
                rule,
                state=state,
                action=action,
                context=context or {},
                commander=self.policy.commander,
                deck_hash=self.policy.deck_hash,
                format_band=self.policy.format_band,
                deck_cards=self.deck_cards,
            ):
                traces.append(
                    PolicyDecisionTrace(
                        rule_id=rule.rule_id,
                        adjustment=rule.score_adjustment,
                        reason=rule.rationale,
                    )
                )
        adjustment = sum(trace.adjustment for trace in traces)
        return (
            baseline.model_copy(
                update={
                    "specialist_bonus": baseline.specialist_bonus + adjustment,
                    "total_utility": baseline.total_utility + adjustment,
                }
            ),
            tuple(traces),
        )

    def opening_hand_score_with_trace(
        self,
        cards: Iterable[PilotActionView],
        *,
        commander_names: tuple[str, ...] = (),
        context: Mapping[str, Any] | None = None,
    ) -> tuple[float, tuple[PolicyDecisionTrace, ...]]:
        card_list = tuple(cards)
        baseline = self.base_pilot.opening_hand_score(card_list, commander_names=commander_names)
        traces: list[PolicyDecisionTrace] = []
        for rule in sorted(
            self.policy.rules, key=lambda item: (item.priority, item.rule_id), reverse=True
        ):
            if rule.action_preference.decision_point != DecisionPoint.OPENING_HAND:
                continue
            if _rule_matches(
                rule,
                state=None,
                action=None,
                context=context or {},
                commander=self.policy.commander,
                deck_hash=self.policy.deck_hash,
                format_band=self.policy.format_band,
                deck_cards=self.deck_cards,
            ):
                traces.append(
                    PolicyDecisionTrace(
                        rule_id=rule.rule_id,
                        adjustment=rule.score_adjustment,
                        reason=rule.rationale,
                    )
                )
        return baseline + sum(trace.adjustment for trace in traces), tuple(traces)

    def choose_action(
        self,
        state: PilotStateView,
        actions: Iterable[PilotActionView],
        rng: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> PilotDecision:
        candidates = list(actions)
        if not candidates:
            return self.base_pilot.choose_action(state, candidates, rng)
        scored = [
            (action, self.evaluate_action_with_trace(state, action, context=context)[0])
            for action in candidates
        ]
        scored.sort(key=lambda item: (item[1].total_utility, item[0].action_id), reverse=True)
        scored = scored[: self.base_pilot.policy.shortlist]
        selected_action, selected_breakdown = self.base_pilot._select(scored, rng)
        return PilotDecision(
            pilot_name=self.pilot_name,
            strength=self.base_pilot.config.strength,
            mode=self.base_pilot.config.mode,
            selected_action_id=selected_action.action_id,
            selected_utility=selected_breakdown.total_utility,
            candidates=tuple(
                (action.action_id, breakdown.total_utility) for action, breakdown in scored
            ),
            selected_breakdown=selected_breakdown,
        )


class PrimerToPilotCompiler:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.data_root = self.root / "data/primer_rules"
        for folder in ("registry", "schemas", "rules", "policies", "evals", "conflicts", "imports"):
            (self.data_root / folder).mkdir(parents=True, exist_ok=True)

    @property
    def registry_path(self) -> Path:
        return self.data_root / "registry/primer_registry.json"

    def load_registry(self) -> PrimerRegistry:
        if not self.registry_path.exists():
            return PrimerRegistry()
        return PrimerRegistry.model_validate_json(self.registry_path.read_text(encoding="utf-8"))

    def write_registry(self, registry: PrimerRegistry) -> Path:
        atomic_write_json(self.registry_path, registry.model_dump(mode="json"))
        return self.registry_path

    def import_primer(
        self,
        *,
        source_path: str | Path,
        primer_id: str,
        source_id: str,
        title: str,
        commander: str,
        deck_hash: str,
        format_band: FormatBand,
        primer_format: PrimerFormat | None = None,
        license_notes: str = "structured extraction only unless the source is user-provided",
    ) -> PrimerDocument:
        path = (
            (self.root / source_path).resolve()
            if not Path(source_path).is_absolute()
            else Path(source_path).resolve()
        )
        if self.root not in path.parents and path != self.root:
            raise RuleDslError("primer import path must remain inside the project root")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)
        fmt = primer_format or {
            ".md": PrimerFormat.MARKDOWN,
            ".markdown": PrimerFormat.MARKDOWN,
            ".txt": PrimerFormat.TEXT,
            ".json": PrimerFormat.JSON,
        }.get(path.suffix.casefold(), PrimerFormat.TEXT)
        raw = path.read_bytes()
        doc = PrimerDocument(
            primer_id=primer_id,
            source_id=source_id,
            title=title,
            commander=commander,
            deck_hash=deck_hash,
            format_band=format_band,
            primer_format=fmt,
            content_sha256=_content_hash(raw),
            imported_at=datetime.now(UTC),
            source_path=str(path.relative_to(self.root)),
            raw_text_stored=False,
            license_notes=license_notes,
        )
        registry = self.load_registry()
        existing = {item.primer_id: item for item in registry.primers}
        if primer_id in existing and existing[primer_id].content_sha256 != doc.content_sha256:
            raise RuleDslError(
                "primer_id already exists with different content; use a versioned primer_id"
            )
        if primer_id not in existing:
            registry = registry.model_copy(update={"primers": (*registry.primers, doc)})
            self.write_registry(registry)
        return doc

    def extract_rules(
        self,
        document: PrimerDocument,
        *,
        content: str,
    ) -> tuple[PilotRule, ...]:
        if document.primer_format == PrimerFormat.JSON:
            payload = json.loads(content)
            rows = payload.get("rules", payload) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise RuleDslError("JSON primer must contain a rules list")
            rules = tuple(PilotRule.model_validate(row) for row in rows)
            return rules

        sentences = []
        for raw_line in content.splitlines():
            line = re.sub(r"^[\s>*#\-\d.)]+", "", raw_line).strip()
            if len(line) >= 18:
                sentences.append(line)
        rules: list[PilotRule] = []
        for index, sentence in enumerate(sentences, start=1):
            candidate = self._heuristic_rule(document, sentence, index)
            if candidate is not None:
                rules.append(candidate)
        return tuple(rules)

    def _heuristic_rule(
        self, document: PrimerDocument, sentence: str, index: int
    ) -> PilotRule | None:
        lower = sentence.casefold()
        condition = PilotRuleCondition(op=ConditionOperator.TRUTHY, field="context.always")
        preference = ActionPreference(
            decision_point=DecisionPoint.MAIN_ACTION,
            action_kinds=("card",),
            description="Conservative candidate extracted from primer prose",
        )
        adjustment = 0.0
        tags: tuple[str, ...] = ()

        if "mulligan" in lower or "opening hand" in lower or "hands with" in lower:
            preference = ActionPreference(
                decision_point=DecisionPoint.OPENING_HAND,
                description="Opening-hand guidance extracted from primer prose",
            )
            if "ramp" in lower and ("no sacrifice" in lower or "without sacrifice" in lower):
                condition = PilotRuleCondition(
                    op=ConditionOperator.ALL,
                    clauses=(
                        PilotRuleCondition(
                            op=ConditionOperator.GE, field="context.ramp_count", value=1
                        ),
                        PilotRuleCondition(
                            op=ConditionOperator.LE,
                            field="context.sacrifice_material_count",
                            value=0,
                        ),
                    ),
                )
                adjustment = -1.5
            tags = ("mulligan",)
        elif "commander" in lower and any(
            token in lower for token in ("empty resources", "immediate value", "sofortwert")
        ):
            condition = PilotRuleCondition(
                op=ConditionOperator.ANY,
                clauses=(
                    PilotRuleCondition(
                        op=ConditionOperator.FALSY, field="context.commander_immediate_value"
                    ),
                    PilotRuleCondition(op=ConditionOperator.LE, field="state.resources", value=0),
                ),
            )
            preference = ActionPreference(
                action_kinds=("commander",),
                description="Avoid exposing the commander without an immediate value window",
            )
            adjustment = -2.0
            tags = ("commander_cast", "exposure")
        elif "protection" in lower or "schutz" in lower:
            condition = PilotRuleCondition(
                op=ConditionOperator.FALSY, field="context.protection_available"
            )
            preference = ActionPreference(
                action_kinds=("commander",),
                description="Prefer a protection window for commander deployment",
            )
            adjustment = -1.0
            tags = ("protection",)
        elif "sacrifice" in lower or "opfer" in lower:
            preference = ActionPreference(
                roles=(CardRole.SACRIFICE_OUTLET, CardRole.TOKEN_SOURCE),
                description="Develop sacrifice material or outlets",
            )
            adjustment = 0.75
            tags = ("sacrifice",)
        elif "counter" in lower:
            preference = ActionPreference(
                action_kinds=("counter",),
                description="Counterspell priority guidance",
            )
            tags = ("interaction", "counter")
        elif "boardwipe" in lower or "wipe" in lower or "rebuild" in lower:
            preference = ActionPreference(
                decision_point=DecisionPoint.REBUILD,
                roles=(CardRole.RECURSION, CardRole.LAND_SYNERGY),
                description="Rebuild after a board wipe",
            )
            tags = ("rebuild",)
        elif "sequence" in lower or "sequenc" in lower:
            preference = ActionPreference(
                decision_point=DecisionPoint.SEQUENCING,
                action_kinds=("card", "commander"),
                description="Sequencing guidance extracted from primer prose",
            )
            tags = ("sequencing",)
        else:
            return None

        digest = _content_hash(f"{document.primer_id}:{index}:{sentence}")[:12]
        return PilotRule(
            rule_id=f"{document.primer_id}.auto.{digest}",
            source_id=document.source_id,
            commander=document.commander,
            deck_hash=document.deck_hash,
            format_band=document.format_band,
            condition=condition,
            action_preference=preference,
            score_adjustment=adjustment,
            priority=25,
            confidence=0.45,
            evidence_type=PrimerEvidenceType.PRIMER_INFERRED,
            status=PrimerRuleStatus.NEEDS_REVIEW,
            manually_approved=False,
            rationale="Automatically extracted candidate; requires human review before activation.",
            source_excerpt=sentence[:400],
            tags=tags,
        )

    def validate_rules(
        self,
        rules: Sequence[PilotRule],
        *,
        commander: str | None = None,
        deck_hash: str | None = None,
        format_band: FormatBand | None = None,
    ) -> RuleValidationReport:
        issues: list[RuleValidationIssue] = []
        seen: set[str] = set()
        for rule in rules:
            if rule.rule_id in seen:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="error",
                        code="duplicate_rule_id",
                        message="rule_id is duplicated",
                    )
                )
            seen.add(rule.rule_id)
            if commander is not None and rule.commander != commander:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="error",
                        code="commander_mismatch",
                        message="rule commander does not match compilation target",
                    )
                )
            if deck_hash is not None and rule.deck_hash != deck_hash:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="error",
                        code="deck_hash_mismatch",
                        message="rule targets a different deck version",
                    )
                )
            if format_band is not None and rule.format_band != format_band:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="error",
                        code="format_band_mismatch",
                        message="rule format band differs from compilation target",
                    )
                )
            try:
                self._validate_condition_fields(rule.condition)
                for forbidden in rule.forbidden_when:
                    self._validate_condition_fields(forbidden)
            except RuleDslError as exc:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="error",
                        code="unsafe_condition",
                        message=str(exc),
                    )
                )
            if rule.status == PrimerRuleStatus.NEEDS_REVIEW:
                issues.append(
                    RuleValidationIssue(
                        rule_id=rule.rule_id,
                        severity="warning",
                        code="manual_review_required",
                        message="rule is not active until explicitly reviewed",
                    )
                )
        return RuleValidationReport(
            valid=not any(issue.severity == "error" for issue in issues),
            rule_count=len(rules),
            active_rule_count=sum(rule.status == PrimerRuleStatus.ACTIVE for rule in rules),
            issues=tuple(issues),
        )

    def _validate_condition_fields(self, condition: PilotRuleCondition) -> None:
        if condition.field is not None:
            _resolve_field(
                condition.field,
                state=None,
                action=None,
                context={},
                deck_cards=(),
                deck_hash="",
            )
        for clause in condition.clauses:
            self._validate_condition_fields(clause)

    def detect_conflicts(self, rules: Sequence[PilotRule]) -> tuple[PrimerRuleConflict, ...]:
        conflicts: list[PrimerRuleConflict] = []
        by_id: dict[str, list[PilotRule]] = {}
        for rule in rules:
            by_id.setdefault(rule.rule_id, []).append(rule)
        for rule_id, duplicates in by_id.items():
            if len(duplicates) > 1:
                conflicts.append(
                    PrimerRuleConflict(
                        conflict_id=f"duplicate:{rule_id}",
                        rule_ids=tuple(rule.rule_id for rule in duplicates),
                        conflict_type="duplicate_rule_id",
                        description="Multiple rule records use the same rule_id.",
                    )
                )
        active = [rule for rule in rules if rule.status == PrimerRuleStatus.ACTIVE]
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                if left.commander != right.commander:
                    continue
                if left.deck_hash != right.deck_hash:
                    continue
                if left.format_band != right.format_band:
                    continue
                same_condition = _canonical(left.condition.model_dump(mode="json")) == _canonical(
                    right.condition.model_dump(mode="json")
                )
                same_preference = _canonical(
                    left.action_preference.model_dump(mode="json")
                ) == _canonical(right.action_preference.model_dump(mode="json"))
                if (
                    same_condition
                    and same_preference
                    and left.score_adjustment * right.score_adjustment < 0
                ):
                    pair = tuple(sorted((left.rule_id, right.rule_id)))
                    conflicts.append(
                        PrimerRuleConflict(
                            conflict_id=f"opposing:{_content_hash(':'.join(pair))[:12]}",
                            rule_ids=pair,
                            conflict_type="opposing_adjustment",
                            description="Rules with the same scope and trigger apply opposing score adjustments.",
                        )
                    )
        return tuple(conflicts)

    def activate_rule(
        self,
        rule: PilotRule,
        *,
        version: str,
        approved_by: str,
        approval_reason: str,
    ) -> PilotRule:
        """Return a new reviewed rule version; never mutate the source record in place."""
        if not approved_by.strip() or not approval_reason.strip():
            raise RuleDslError("rule activation requires named approval and a reason")
        if rule.status == PrimerRuleStatus.REJECTED:
            raise RuleDslError(
                "rejected rules cannot be activated; create a new reviewed rule version"
            )
        return rule.model_copy(
            update={
                "version": version,
                "status": PrimerRuleStatus.ACTIVE,
                "manually_approved": True,
                "rationale": f"{rule.rationale} Approval: {approved_by}: {approval_reason}",
                "tags": tuple(dict.fromkeys((*rule.tags, "manually_approved"))),
            }
        )

    def compile_policy(
        self,
        *,
        policy_id: str,
        version: str,
        commander: str,
        deck_hash: str,
        format_band: FormatBand,
        base_pilot_name: str,
        rules: Sequence[PilotRule],
        conflict_strategy: Literal["reject", "prefer_priority", "prefer_confidence"] = "reject",
    ) -> CompiledPilotPolicy:
        report = self.validate_rules(
            rules, commander=commander, deck_hash=deck_hash, format_band=format_band
        )
        if not report.valid:
            raise RuleDslError(
                "rule validation failed: "
                + "; ".join(issue.message for issue in report.issues if issue.severity == "error")
            )
        active = [rule for rule in rules if rule.status == PrimerRuleStatus.ACTIVE]
        conflicts = self.detect_conflicts(active)
        unresolved = list(conflicts)
        selected = list(active)
        if conflicts and conflict_strategy != "reject":
            remove_ids: set[str] = set()
            for conflict in conflicts:
                candidates = [rule for rule in selected if rule.rule_id in conflict.rule_ids]
                if not candidates:
                    continue
                key = (
                    (lambda item: (item.priority, item.confidence, item.rule_id))
                    if conflict_strategy == "prefer_priority"
                    else (lambda item: (item.confidence, item.priority, item.rule_id))
                )
                winner = max(candidates, key=key)
                remove_ids.update(
                    rule.rule_id for rule in candidates if rule.rule_id != winner.rule_id
                )
            selected = [rule for rule in selected if rule.rule_id not in remove_ids]
            unresolved = []
        if unresolved:
            raise RuleDslError(
                "unresolved rule conflicts: "
                + ", ".join(conflict.conflict_id for conflict in unresolved)
            )
        return CompiledPilotPolicy(
            policy_id=policy_id,
            version=version,
            created_at=datetime.now(UTC),
            commander=commander,
            deck_hash=deck_hash,
            format_band=format_band,
            base_pilot_name=base_pilot_name,
            source_ids=tuple(sorted({rule.source_id for rule in selected})),
            rules=tuple(
                sorted(selected, key=lambda item: (item.priority, item.rule_id), reverse=True)
            ),
            conflicts=conflicts,
            notes=("Policy overlay is reversible and never mutates the base pilot or decklist.",),
        )

    def compile_policy_variants(
        self,
        *,
        policy_id: str,
        version: str,
        commander: str,
        deck_hash: str,
        format_band: FormatBand,
        base_pilot_name: str,
        rules: Sequence[PilotRule],
    ) -> tuple[CompiledPilotPolicy, ...]:
        """Return explicit alternatives for opposing conflicts; never silently combine them."""
        conflicts = tuple(
            conflict
            for conflict in self.detect_conflicts(rules)
            if conflict.conflict_type == "opposing_adjustment"
        )
        if not conflicts:
            return (
                self.compile_policy(
                    policy_id=policy_id,
                    version=version,
                    commander=commander,
                    deck_hash=deck_hash,
                    format_band=format_band,
                    base_pilot_name=base_pilot_name,
                    rules=rules,
                ),
            )
        variants: list[CompiledPilotPolicy] = []
        for conflict_index, conflict in enumerate(conflicts, start=1):
            for choice_index, selected_id in enumerate(conflict.rule_ids, start=1):
                selected_rules = tuple(
                    rule
                    for rule in rules
                    if rule.rule_id == selected_id or rule.rule_id not in conflict.rule_ids
                )
                variants.append(
                    self.compile_policy(
                        policy_id=f"{policy_id}.alternative-{conflict_index}-{choice_index}",
                        version=version,
                        commander=commander,
                        deck_hash=deck_hash,
                        format_band=format_band,
                        base_pilot_name=base_pilot_name,
                        rules=selected_rules,
                    )
                )
        return tuple(variants)

    def write_policy(self, policy: CompiledPilotPolicy, file_name: str | None = None) -> Path:
        target = (
            self.data_root / "policies" / (file_name or f"{policy.policy_id}-{policy.version}.json")
        )
        if target.exists():
            existing = CompiledPilotPolicy.model_validate_json(target.read_text(encoding="utf-8"))
            if existing != policy:
                raise RuleDslError("compiled policy path is immutable; use a new version")
            return target
        atomic_write_json(target, policy.model_dump(mode="json"))
        return target

    def compare_policy_versions(
        self, older: CompiledPilotPolicy, newer: CompiledPilotPolicy
    ) -> dict[str, Any]:
        old = {rule.rule_id: rule for rule in older.rules}
        new = {rule.rule_id: rule for rule in newer.rules}
        changed = sorted(
            rule_id for rule_id in old.keys() & new.keys() if old[rule_id] != new[rule_id]
        )
        return {
            "older_policy_id": older.policy_id,
            "older_version": older.version,
            "newer_policy_id": newer.policy_id,
            "newer_version": newer.version,
            "added_rules": sorted(new.keys() - old.keys()),
            "removed_rules": sorted(old.keys() - new.keys()),
            "changed_rules": changed,
            "automatic_deck_application": False,
        }

    def audit_replay_coverage(
        self,
        *,
        policy: CompiledPilotPolicy,
        replay_path: str | Path,
    ) -> dict[str, Any]:
        """Inspect stored JSONL evidence without pretending it supports counterfactual replays."""
        path = Path(replay_path)
        if not path.is_absolute():
            path = self._project_path(path)
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        estimate_types = sorted({str(row.get("estimate_type", "unknown")) for row in rows})
        decisions = [row for row in rows if row.get("event_type") == "pilot_decision"]
        searchable = _canonical(rows).casefold()
        rule_mentions: dict[str, bool] = {}
        for rule in policy.rules:
            names = rule.action_preference.card_names
            rule_mentions[rule.rule_id] = (
                any(_normalize_card(name) in searchable for name in names) if names else False
            )
        return {
            "replay_path": str(path.relative_to(self.root)),
            "event_count": len(rows),
            "pilot_decision_count": len(decisions),
            "estimate_types": estimate_types,
            "rule_source_mentions": rule_mentions,
            "counterfactual_redecision_status": "not_run_missing_complete_alternative_action_context",
            "limitations": [
                "Stored structural replays preserve selected actions but not every Primer DSL context flag.",
                "Replay inspection is coverage evidence, not proof that the overlay would improve the historical game.",
            ],
        }

    def _project_path(self, relative: str | Path) -> Path:
        path = (self.root / relative).resolve()
        if self.root not in path.parents and path != self.root:
            raise RuleDslError("path escapes project root")
        return path

    def evaluate_policy(
        self,
        *,
        base_pilot: BasePilot,
        policy: CompiledPilotPolicy,
        scenarios: Sequence[PolicyEvalScenario],
        deck_cards: Sequence[str],
        seed: int = 20260806,
    ) -> tuple[PolicyEvalResult, ...]:
        import random

        results: list[PolicyEvalResult] = []
        overlay = PilotPolicyOverlay(base_pilot, policy, deck_cards=deck_cards)
        for scenario_index, scenario in enumerate(scenarios):
            if scenario.deck_hash != policy.deck_hash or scenario.commander != policy.commander:
                raise RuleDslError(f"scenario {scenario.scenario_id} is incompatible with policy")
            baseline = base_pilot.choose_action(
                scenario.state, scenario.actions, random.Random(seed + scenario_index)
            )
            overlay_decision = overlay.choose_action(
                scenario.state,
                scenario.actions,
                random.Random(seed + scenario_index),
                context=scenario.context,
            )
            rows: list[PolicyActionScore] = []
            for action in scenario.actions:
                baseline_score = base_pilot.evaluate_action(scenario.state, action).total_utility
                overlay_score, traces = overlay.evaluate_action_with_trace(
                    scenario.state, action, context=scenario.context
                )
                rows.append(
                    PolicyActionScore(
                        action_id=action.action_id,
                        baseline_score=baseline_score,
                        overlay_score=overlay_score.total_utility,
                        triggered_rules=traces,
                    )
                )
            baseline_correct = baseline.selected_action_id == scenario.expected_action_id
            overlay_correct = overlay_decision.selected_action_id == scenario.expected_action_id
            results.append(
                PolicyEvalResult(
                    scenario_id=scenario.scenario_id,
                    baseline_action_id=baseline.selected_action_id,
                    overlay_action_id=overlay_decision.selected_action_id,
                    expected_action_id=scenario.expected_action_id,
                    baseline_correct=baseline_correct,
                    overlay_correct=overlay_correct,
                    improved=(not baseline_correct and overlay_correct),
                    action_scores=tuple(rows),
                )
            )
        return tuple(results)
