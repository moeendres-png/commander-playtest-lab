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
from commander_lab.pod_scheduling_5p import (
    BalancedFivePlayerSensitivityScheduler,
    FivePlayerPodScenario,
)
from commander_lab.repositories.opponents import CurrentOpponentRepository

from .campaign import run_balanced_paired_campaign
from .multiplayer import multiplayer_pod_response


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


@dataclass(frozen=True, slots=True)
class FivePlayerSensitivitySpecification:
    """Separate 5-player sensitivity specification; never primary campaign evidence."""

    games: int
    seed: int
    max_turns: int
    workers: int = 1
    pilot_strength: PilotStrength = PilotStrength.STRONG
    pilot_mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC
    politics_regime: str = "structural_default"

    def __post_init__(self) -> None:
        if self.games < 1:
            raise ValueError("five-player sensitivity games must be positive")
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
        self.five_player_scheduler = BalancedFivePlayerSensitivityScheduler(
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

    def run_five_player_sensitivity_pair(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        specification: FivePlayerSensitivitySpecification,
    ) -> dict[str, object]:
        """Run a separate balanced 5P sensitivity axis using current opponent truth."""
        pilot = PilotConfig(
            strength=specification.pilot_strength,
            mode=specification.pilot_mode,
        )
        scenarios: tuple[FivePlayerPodScenario, ...] = self.five_player_scheduler.schedule(
            specification.games, seed=specification.seed
        )
        campaign = run_balanced_paired_campaign(
            baseline=baseline,
            variant=variant,
            opponent_profiles=self.opponents.profiles(),
            scenarios=scenarios,
            pilot_config=pilot,
            max_turns=specification.max_turns,
            statistics_seed=specification.seed,
            workers=specification.workers,
        )
        return {
            "evidence_axis": "five_player_sensitivity",
            "primary_evidence": False,
            "construction_use": False,
            "pod_size": 5,
            "games": specification.games,
            "seed": specification.seed,
            "pilot_strength": specification.pilot_strength.value,
            "pilot_mode": specification.pilot_mode.value,
            "politics_regime": specification.politics_regime,
            "scenarios": [row.as_dict() for row in scenarios],
            "coverage_report": self.five_player_scheduler.coverage_report(scenarios),
            "campaign": campaign,
            "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
            "evidence_boundary": (
                "5P sensitivity is a separate structural robustness axis and is never counted as "
                "primary 4P evidence or an estimate of real local opponent frequency."
            ),
        }

    def run_primary_with_five_player_sensitivity(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        primary_specification: WholeDeckCampaignSpecification,
        five_player_specification: FivePlayerSensitivitySpecification,
    ) -> dict[str, object]:
        primary = self.run_pair(
            baseline=baseline, variant=variant, specification=primary_specification
        )
        five = self.run_five_player_sensitivity_pair(
            baseline=baseline, variant=variant, specification=five_player_specification
        )
        primary_axis = primary["primary"]
        if not isinstance(primary_axis, dict):
            raise TypeError("primary campaign bundle is malformed")
        primary_campaign = primary_axis.get("campaign")
        if not isinstance(primary_campaign, dict):
            raise TypeError("primary campaign bundle is malformed")
        five_campaign = five.get("campaign")
        if not isinstance(five_campaign, dict):
            raise TypeError("five-player campaign bundle is malformed")
        response = multiplayer_pod_response(
            primary_campaign,
            five_campaign,
            seed=five_player_specification.seed ^ 0x4F50_3550,
        )
        return {
            "primary_4p": primary,
            "five_player_sensitivity": five,
            "multiplayer_response": response,
            "do_not_double_count_sensitivity_as_primary": True,
        }
