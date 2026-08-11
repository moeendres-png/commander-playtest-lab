from __future__ import annotations

from commander_lab.models.mulligan import MulliganContext
from commander_lab.project_context import ProjectContextError, load_project_context

from .lab import MulliganLab as _LegacyMulliganLab
from .lab import MulliganLabError


class MulliganLab(_LegacyMulliganLab):
    """Mulligan Lab with fail-closed current project-context resolution.

    The inherited hand and follow-up simulation model is intentionally unchanged. Only opponent
    context selection is replaced so current pod membership is not duplicated in Python code.
    """

    def __init__(self, root):  # type annotation inherited through the public constructor contract
        super().__init__(root)
        try:
            self.project_context = load_project_context(self.root)
        except ProjectContextError as exc:
            raise MulliganLabError(str(exc)) from exc

    def _opponent_ids(self, context: MulliganContext, *, holdout: int = 0) -> tuple[str, ...]:
        need = max(1, context.pod_size - 1)
        if holdout:
            # The canonical source defines a holdout/sensitivity *pool*, not fixed pods or
            # frequencies. Deterministic slices are model test contexts only and never promoted
            # to canonical opponent frequencies.
            holdout_ids = self.project_context.holdout_deck_ids
            if not holdout_ids:
                raise MulliganLabError("canonical holdout/sensitivity opponent pool is empty")
            start = ((holdout - 1) * need) % len(holdout_ids)
            return tuple(holdout_ids[(start + index) % len(holdout_ids)] for index in range(need))

        if context.pod_size != 4:
            raise MulliganLabError(
                "canonical 3P/5P sensitivity contexts require explicit opponent composition; "
                "the MulliganContext does not carry opponent deck ids, so the lab refuses to "
                "invent them"
            )
        return self.project_context.primary_opponent_deck_ids(context.deck_id)


__all__ = ["MulliganLab", "MulliganLabError"]
