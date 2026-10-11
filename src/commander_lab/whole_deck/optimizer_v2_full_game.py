"""Optimizer-v2 full-game route for candidates the Structural model cannot judge (#733).

Optimizer-v2 routes a candidate whose changed cards need tactical or external
rules evidence to ``TACTICAL_OR_FAIL_CLOSED`` / ``EXTERNAL_RULES_OR_FAIL_CLOSED``
and lists it in ``ROUTED_HYPOTHESIS_QUEUES.json``. Until now nothing executed
those queues, so the most interesting swaps (the ones with real rules
interactions) never got any evidence at all.

This module turns the top routed hypotheses into a paired XMage full-game
comparison (#731): the control deck and every hypothesis deck play the same
seeds, seats and opponents, and XMage alone decides what happens. The result is
attached to each hypothesis as exploratory full-game evidence. It does not make
a hypothesis Structural-confirmatory, does not change its fidelity tier, does
not consume holdout data and never mutates a deck.

Every input is checked before a game is planned: a hypothesis without a ledger
row, a ledger row whose exact list does not reconstruct from the control deck
plus its diff, or a deck that is not 100 cards fails closed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonReport,
    DeckComparisonSpec,
    PairedVariantResult,
)
from commander_lab.models import RulesDeckInput

FULL_GAME_ROUTE_SCHEMA_VERSION: Literal["optimizer-v2-full-game-route-1.0.0"] = (
    "optimizer-v2-full-game-route-1.0.0"
)
ROUTE_GROUPS: tuple[str, ...] = (
    "TOP_TACTICAL_REQUIRED_HYPOTHESES",
    "TOP_EXTERNAL_RULES_REQUIRED_HYPOTHESES",
)
OPTIONAL_ROUTE_GROUPS: tuple[str, ...] = (
    *ROUTE_GROUPS,
    "TOP_STRUCTURAL_SCREENING_ONLY_HYPOTHESES",
)


class FullGameRouteError(ValueError):
    """The optimizer artifacts cannot be turned into a sound comparison."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RouteHypothesis(_StrictModel):
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    queue: str
    required_next_evidence_layer: str
    hypothesis_priority: float
    removed_cards: tuple[str, ...]
    added_cards: tuple[str, ...]
    blocked_cards: tuple[str, ...]
    deck: RulesDeckInput


class RoutedHypothesisResult(_StrictModel):
    deck_hash: str
    deck_id: str
    queue: str
    required_next_evidence_layer: str
    removed_cards: tuple[str, ...]
    added_cards: tuple[str, ...]
    blocked_cards: tuple[str, ...]
    full_game_verdict: Literal[
        "VARIANT_BETTER", "BASELINE_BETTER", "NO_CLEAR_DIFFERENCE", "INSUFFICIENT"
    ]
    paired: PairedVariantResult
    route_status: Literal["FULL_GAME_EXPLORATORY_EVIDENCE", "FULL_GAME_NOT_DECIDED"]
    # The route adds evidence; it never upgrades the candidate's standing.
    confirmatory_eligible: Literal[False] = False
    fidelity_tier_changed: Literal[False] = False


class FullGameRouteReport(_StrictModel):
    schema_version: Literal["optimizer-v2-full-game-route-1.0.0"] = FULL_GAME_ROUTE_SCHEMA_VERSION
    candidate_ledger_hash: str | None
    control_deck_id: str
    control_deck_hash: str
    queues: tuple[str, ...]
    hypotheses: tuple[RoutedHypothesisResult, ...]
    comparison: DeckComparisonReport
    evidence_class: Literal["exploratory_xmage_full_game"] = "exploratory_xmage_full_game"
    structural_decision_authority: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    holdout_consumed: Literal[False] = False
    canonical_data_mutated: Literal[False] = False
    truth_boundary: str = (
        "Paired XMage full games for optimizer hypotheses the Structural model routed "
        "to tactical or external rules evidence. Exploratory deck-building evidence for "
        "this pilot policy and engine pin; not Structural confirmatory evidence and not "
        "a deck change."
    )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def variant_deck(control: RulesDeckInput, row: Mapping[str, Any]) -> RulesDeckInput:
    """The candidate deck of one ledger row, checked against the control deck."""
    deck_hash = str(row.get("deck_hash", ""))
    mainboard = _strings(row.get("exact_mainboard"))
    commanders = _strings(row.get("commander_names"))
    if not mainboard:
        raise FullGameRouteError(f"ledger row has no exact mainboard: {deck_hash}")
    if commanders and tuple(commanders) != tuple(control.commander_names):
        raise FullGameRouteError(f"ledger row changes the commanders: {deck_hash}")
    reconstructed = Counter(control.mainboard)
    reconstructed.subtract(Counter(_strings(row.get("removed_cards"))))
    reconstructed.update(_strings(row.get("added_cards")))
    if +reconstructed != Counter(mainboard) or any(n < 0 for n in reconstructed.values()):
        raise FullGameRouteError(
            "ledger row does not reconstruct from the control deck plus its diff "
            f"(was the optimizer run on a different control?): {deck_hash}"
        )
    try:
        return RulesDeckInput(
            deck_id=f"{control.deck_id}@{deck_hash[:12]}",
            name=f"{control.name} (optimizer hypothesis {deck_hash[:12]})",
            commander_names=control.commander_names,
            mainboard=mainboard,
            deck_hash=deck_hash,
        )
    except ValueError as exc:
        raise FullGameRouteError(f"ledger row is not a legal deck input: {exc}") from exc


def select_route_hypotheses(
    queues: Mapping[str, Any],
    ledger: Mapping[str, Any],
    control: RulesDeckInput,
    *,
    groups: Sequence[str] = ROUTE_GROUPS,
    limit: int = 4,
) -> tuple[RouteHypothesis, ...]:
    """Top routed hypotheses, best priority first, de-duplicated across queues."""
    if limit < 1:
        raise FullGameRouteError("limit must be at least 1")
    unknown = [group for group in groups if group not in OPTIONAL_ROUTE_GROUPS]
    if unknown:
        raise FullGameRouteError(f"unknown hypothesis queues: {unknown}")
    ledger_hash = ledger.get("ledger_hash")
    queue_ledger = queues.get("candidate_ledger_hash")
    if ledger_hash is None or queue_ledger != ledger_hash:
        raise FullGameRouteError("hypothesis queues were not built from this candidate ledger")
    rows_raw = ledger.get("rows")
    rows = {
        str(row.get("deck_hash")): row
        for row in (rows_raw if isinstance(rows_raw, list) else [])
        if isinstance(row, Mapping)
    }
    candidates: list[tuple[float, str, str, Mapping[str, Any]]] = []
    for group in groups:
        entries = queues.get(group)
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, Mapping):
                raise FullGameRouteError(f"malformed hypothesis entry in {group}")
            priority = entry.get("hypothesis_priority")
            if not isinstance(priority, int | float):
                raise FullGameRouteError(f"hypothesis without priority in {group}")
            candidates.append((float(priority), str(entry.get("deck_hash")), group, entry))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected: list[RouteHypothesis] = []
    seen: set[str] = set()
    for priority, deck_hash, group, entry in candidates:
        if deck_hash in seen:
            continue
        if deck_hash in {control.deck_hash, ledger.get("control_deck_hash")}:
            continue  # the control itself is the baseline, not a hypothesis
        row = rows.get(deck_hash)
        if row is None:
            raise FullGameRouteError(f"hypothesis has no candidate ledger row: {deck_hash}")
        seen.add(deck_hash)
        selected.append(
            RouteHypothesis(
                deck_hash=deck_hash,
                queue=group,
                required_next_evidence_layer=str(entry.get("required_next_evidence_layer", "")),
                hypothesis_priority=priority,
                removed_cards=_strings(row.get("removed_cards")),
                added_cards=_strings(row.get("added_cards")),
                blocked_cards=_strings(row.get("blocked_cards")),
                deck=variant_deck(control, row),
            )
        )
        if len(selected) == limit:
            break
    return tuple(selected)


def build_route_spec(
    control: RulesDeckInput,
    hypotheses: Sequence[RouteHypothesis],
    opponents: Sequence[RulesDeckInput],
    *,
    seeds: Sequence[int],
    xmage_commit: str,
    rotate_seats: bool = True,
    comparison_id: str | None = None,
) -> DeckComparisonSpec:
    if not hypotheses:
        raise FullGameRouteError("no routed hypotheses to evaluate")
    return DeckComparisonSpec(
        comparison_id=comparison_id or f"optimizer-v2-full-game-route:{control.deck_id}",
        contenders=(control, *(hypothesis.deck for hypothesis in hypotheses)),
        opponents=tuple(opponents),
        seeds=tuple(seeds),
        rotate_seats=rotate_seats,
        xmage_commit=xmage_commit,
    )


def route_report(
    *,
    control: RulesDeckInput,
    hypotheses: Sequence[RouteHypothesis],
    comparison: DeckComparisonReport,
    candidate_ledger_hash: str | None,
    queues: Sequence[str],
) -> FullGameRouteReport:
    paired = {row.variant_deck_id: row for row in comparison.paired}
    results: list[RoutedHypothesisResult] = []
    for hypothesis in hypotheses:
        row = paired.get(hypothesis.deck.deck_id)
        if row is None:
            raise FullGameRouteError(
                f"comparison has no paired result for hypothesis {hypothesis.deck_hash}"
            )
        results.append(
            RoutedHypothesisResult(
                deck_hash=hypothesis.deck_hash,
                deck_id=hypothesis.deck.deck_id,
                queue=hypothesis.queue,
                required_next_evidence_layer=hypothesis.required_next_evidence_layer,
                removed_cards=hypothesis.removed_cards,
                added_cards=hypothesis.added_cards,
                blocked_cards=hypothesis.blocked_cards,
                full_game_verdict=row.verdict,
                paired=row,
                route_status=(
                    "FULL_GAME_NOT_DECIDED"
                    if row.verdict == "INSUFFICIENT"
                    else "FULL_GAME_EXPLORATORY_EVIDENCE"
                ),
            )
        )
    if control.deck_hash is None:
        raise FullGameRouteError("control deck needs a deck_hash")
    return FullGameRouteReport(
        candidate_ledger_hash=candidate_ledger_hash,
        control_deck_id=control.deck_id,
        control_deck_hash=control.deck_hash,
        queues=tuple(queues),
        hypotheses=tuple(results),
        comparison=comparison,
    )


__all__ = [
    "FULL_GAME_ROUTE_SCHEMA_VERSION",
    "OPTIONAL_ROUTE_GROUPS",
    "ROUTE_GROUPS",
    "FullGameRouteError",
    "FullGameRouteReport",
    "RouteHypothesis",
    "RoutedHypothesisResult",
    "build_route_spec",
    "route_report",
    "select_route_hypotheses",
    "variant_deck",
]
