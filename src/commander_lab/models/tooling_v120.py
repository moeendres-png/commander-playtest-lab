from __future__ import annotations

from .tooling import (
    ComparePilotsInput as _ComparePilotsInput,
)
from .tooling import (
    RunPilotBenchmarkInput as _RunPilotBenchmarkInput,
)
from .tooling import (
    RunPilotEnsembleInput as _RunPilotEnsembleInput,
)
from .tooling import (
    TestVariantAcrossPilotsInput as _TestVariantAcrossPilotsInput,
)


class RunPilotBenchmarkInput(_RunPilotBenchmarkInput):
    opponent_deck_ids: tuple[str, ...] = ()


class ComparePilotsInput(_ComparePilotsInput):
    opponent_deck_ids: tuple[str, ...] = ()


class RunPilotEnsembleInput(_RunPilotEnsembleInput):
    opponent_deck_ids: tuple[str, ...] = ()


class TestVariantAcrossPilotsInput(_TestVariantAcrossPilotsInput):
    __test__ = False
    opponent_deck_ids: tuple[str, ...] = ()


__all__ = [
    "ComparePilotsInput",
    "RunPilotBenchmarkInput",
    "RunPilotEnsembleInput",
    "TestVariantAcrossPilotsInput",
]
