from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralDeckProfile,
)
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler, PodScenario
from commander_lab.repositories.opponents import CurrentOpponentRepository

from .campaign import run_balanced_paired_campaign


@dataclass(frozen=True, slots=True)
class WholeDeckCampaignSpecification:
    """Immutable experimental specification for a paired Whole-Deck benchmark."""

    primary_games: int
    seed: int
    max_turns: int
    workers: int = 1
    holdout_games: int = 0
    pilot_strength: PilotStrength = PilotStrength.STRONG
    pilot_mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC
    politics_regime: str = "structural_default"
    pod_size: int = 4

    def __post_init__(self) -> None:
        if self.pod_size != 4:
            raise ValueError("primary Whole-Deck campaign specification requires pod_size=4")
        if self.primary_games < 1:
            raise ValueError("primary_games must be positive")
        if self.holdout_games < 0:
            raise ValueError("holdout_games must be non-negative")
        if self.max_turns < 1:
            raise ValueError("max_turns must be positive")
        if self.workers < 1:
            raise ValueError("workers must be positive")


class WholeDeckCampaignOrchestrator:
    """Explicitly wires opponent truth, scheduling and isolated paired simulation."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.opponents = CurrentOpponentRepository(self.root)
        self.scheduler = BalancedPodScenarioScheduler(
            self.opponents.records(), opponent_registry_hash=self.opponents.registry_hash
        )

    @staticmethod
    def _holdout_seed(seed: int) -> int:
        # Domain-separated deterministic seed; it is never used by construction/search.
        return seed ^ 0x5F37_9A21

    def run_pair(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        specification: WholeDeckCampaignSpecification,
    ) -> dict[str, object]:
        pilot = PilotConfig(
            strength=specification.pilot_strength,
            mode=specification.pilot_mode,
        )
        primary_scenarios = self.scheduler.schedule(
            specification.primary_games, seed=specification.seed
        )
        primary_campaign = run_balanced_paired_campaign(
            baseline=baseline,
            variant=variant,
            opponent_profiles=self.opponents.profiles(),
            scenarios=primary_scenarios,
            pilot_config=pilot,
            max_turns=specification.max_turns,
            statistics_seed=specification.seed,
            workers=specification.workers,
        )
        holdout: dict[str, object] | None = None
        holdout_scenarios: tuple[PodScenario, ...] = ()
        if specification.holdout_games:
            holdout_seed = self._holdout_seed(specification.seed)
            holdout_scenarios = self.scheduler.schedule(
                specification.holdout_games, seed=holdout_seed
            )
            if {row.seed for row in primary_scenarios} & {row.seed for row in holdout_scenarios}:
                raise RuntimeError("primary and holdout scenario seed sets must be disjoint")
            holdout = {
                "evidence_axis": "holdout",
                "construction_use": False,
                "master_seed": holdout_seed,
                "scenarios": [row.as_dict() for row in holdout_scenarios],
                "coverage_report": self.scheduler.coverage_report(holdout_scenarios),
                "campaign": run_balanced_paired_campaign(
                    baseline=baseline,
                    variant=variant,
                    opponent_profiles=self.opponents.profiles(),
                    scenarios=holdout_scenarios,
                    pilot_config=pilot,
                    max_turns=specification.max_turns,
                    statistics_seed=holdout_seed,
                    workers=specification.workers,
                ),
            }
        return {
            "campaign_specification": {
                "primary_games": specification.primary_games,
                "holdout_games": specification.holdout_games,
                "seed": specification.seed,
                "max_turns": specification.max_turns,
                "workers_requested": specification.workers,
                "workers_effective": specification.workers,
                "pod_size": specification.pod_size,
                "pilot_strength": specification.pilot_strength.value,
                "pilot_mode": specification.pilot_mode.value,
                "politics_regime": specification.politics_regime,
                "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
            },
            "opponent_registry_hash": self.opponents.registry_hash,
            "opponent_deck_ids": list(self.opponents.current_deck_ids()),
            "primary": {
                "evidence_axis": "primary_balanced_4p",
                "scenarios": [row.as_dict() for row in primary_scenarios],
                "coverage_report": self.scheduler.coverage_report(primary_scenarios),
                "campaign": primary_campaign,
            },
            "holdout": holdout,
            "sensitivity_boundary": {
                "three_player": "SEPARATE_ROBUSTNESS_AXIS_NOT_RUN",
                "five_player": "SEPARATE_ROBUSTNESS_AXIS_NOT_RUN",
                "do_not_double_count_primary_results": True,
            },
            "execution_envelope": {
                "requested_workers": specification.workers,
                "effective_workers": specification.workers,
                "worker_fallback_applied": False,
                "reason": "deterministic scenario identities are independent of worker count",
            },
        }
