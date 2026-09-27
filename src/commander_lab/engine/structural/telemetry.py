from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean
from typing import Literal

from commander_lab.models import CardRole, Color, StructuralCardProfile

T1TelemetryStatus = Literal["NOT_MEASURED", "PARTIAL", "MEASURED"]
PaymentBlocker = Literal["insufficient_total_mana", "missing_color"]
DisruptionClass = Literal["commander_removal", "engine_loss", "board_wipe"]

_REACTION_ONLY_ROLES = frozenset({CardRole.COUNTER, CardRole.PROTECTION})


@dataclass(frozen=True, slots=True)
class RebuildEpisode:
    """One explicitly observed Structural disruption episode.

    Recovery thresholds are bound to the exact pre-disruption Structural state. No abstract rebuild
    score or inferred rules semantics are introduced.
    """

    disruption_class: DisruptionClass
    started_turn: int
    commander_name: str | None = None
    baseline_board_power: float = 0.0
    baseline_engine_value: float = 0.0


@dataclass(slots=True)
class T1TelemetryAccumulator:
    """Read-only counters for decision-relevant Structural telemetry.

    These counters observe the state already used by Structural action legality. They never feed
    pilot choice, scoring, search, promotion, or holdout logic. T2 rebuild diagnostics live here as
    additional observation-only state so they share the same non-interference boundary.
    """

    decision_windows: int = 0
    unused_mana: float = 0.0
    colored_mana_failures: int = 0
    stranded_spells: int = 0
    stranded_reasons: Counter[str] = field(default_factory=Counter)
    commander_recast_opportunities: dict[str, int] = field(default_factory=dict)
    commander_recast_affordable: dict[str, int] = field(default_factory=dict)
    open_rebuild_episodes: dict[str, RebuildEpisode] = field(default_factory=dict)
    rebuild_disruption_counts: Counter[str] = field(default_factory=Counter)
    rebuild_completed_counts: Counter[str] = field(default_factory=Counter)
    rebuild_completed_turns: list[float] = field(default_factory=list)

    def record_recast(self, commander_name: str, *, affordable: bool) -> None:
        self.commander_recast_opportunities[commander_name] = (
            self.commander_recast_opportunities.get(commander_name, 0) + 1
        )
        if affordable:
            self.commander_recast_affordable[commander_name] = (
                self.commander_recast_affordable.get(commander_name, 0) + 1
            )

    def recast_affordability(self) -> float | None:
        """Return pooled affordability after evaluating every commander independently."""

        opportunities = sum(self.commander_recast_opportunities.values())
        if opportunities == 0:
            return None
        return sum(self.commander_recast_affordable.values()) / opportunities

    @staticmethod
    def _episode_key(disruption_class: DisruptionClass, commander_name: str | None) -> str:
        if disruption_class == "commander_removal":
            if not commander_name:
                raise ValueError("commander_removal requires commander_name")
            return f"commander_removal:{commander_name}"
        return disruption_class

    def record_disruption(
        self,
        disruption_class: DisruptionClass,
        *,
        turn: int,
        commander_name: str | None = None,
        baseline_board_power: float = 0.0,
        baseline_engine_value: float = 0.0,
    ) -> bool:
        """Start one non-overlapping measured episode for a distinguishable disruption class."""

        key = self._episode_key(disruption_class, commander_name)
        if key in self.open_rebuild_episodes:
            return False
        self.open_rebuild_episodes[key] = RebuildEpisode(
            disruption_class=disruption_class,
            started_turn=turn,
            commander_name=commander_name,
            baseline_board_power=max(0.0, baseline_board_power),
            baseline_engine_value=max(0.0, baseline_engine_value),
        )
        self.rebuild_disruption_counts[disruption_class] += 1
        return True

    def observe_recovery(
        self,
        *,
        turn: int,
        commander_names_on_battlefield: set[str],
        board_power: float,
        engine_value: float,
    ) -> None:
        """Close episodes only when their exact Structural recovery invariant is observable."""

        completed: list[str] = []
        for key, episode in self.open_rebuild_episodes.items():
            recovered = False
            if episode.disruption_class == "commander_removal":
                recovered = bool(
                    episode.commander_name
                    and episode.commander_name in commander_names_on_battlefield
                )
            elif episode.disruption_class == "engine_loss":
                recovered = (
                    episode.baseline_engine_value > 0.0
                    and engine_value + 1e-9 >= episode.baseline_engine_value
                )
            elif episode.disruption_class == "board_wipe":
                recovered_axes: list[bool] = []
                if episode.baseline_board_power > 0.0:
                    recovered_axes.append(board_power + 1e-9 >= episode.baseline_board_power)
                if episode.baseline_engine_value > 0.0:
                    recovered_axes.append(engine_value + 1e-9 >= episode.baseline_engine_value)
                recovered = any(recovered_axes)
            if not recovered:
                continue
            elapsed = float(max(0, turn - episode.started_turn))
            self.rebuild_completed_turns.append(elapsed)
            self.rebuild_completed_counts[episode.disruption_class] += 1
            completed.append(key)
        for key in completed:
            del self.open_rebuild_episodes[key]

    def rebuild_mean_turns(self) -> float | None:
        if not self.rebuild_completed_turns:
            return None
        return fmean(self.rebuild_completed_turns)

    def rebuild_open_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter(
            episode.disruption_class for episode in self.open_rebuild_episodes.values()
        )
        return dict(sorted(counts.items()))


def is_structural_reaction_only(card: StructuralCardProfile) -> bool:
    """Return whether Structural deliberately withholds this spell from proactive main actions."""

    return bool(not card.is_permanent and card.roles and card.roles.issubset(_REACTION_ONLY_ROLES))


def classify_payment_blocker(
    *,
    mana_available: float,
    available_colors: set[Color],
    card: StructuralCardProfile,
) -> PaymentBlocker | None:
    """Classify only payment blockers the current Structural state can actually observe.

    Color fidelity is intentionally presence-only because the current Structural payer checks
    whether each required color is available, not exact colored-pip source quantities. The caller
    must therefore report T1 as PARTIAL rather than rules-complete telemetry.
    """

    if mana_available + 1e-9 < card.mana_value:
        return "insufficient_total_mana"
    if any(color not in available_colors for color in card.color_requirements):
        return "missing_color"
    return None
