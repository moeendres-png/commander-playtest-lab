from __future__ import annotations

from pathlib import Path

from commander_lab.models import RulesBackend, RulesEngineProbe

from .base import RulesEngineAdapter
from .bridge import XMageRulesAdapter
from .tactical import TacticalRulesAdapter


class RulesEngineManager:
    """Construct and probe the bounded tactical backend plus the optional XMage bridge."""

    def __init__(self, *, root: str | Path | None = None) -> None:
        self.root = None if root is None else Path(root)
        self.tactical = TacticalRulesAdapter()
        self.xmage = XMageRulesAdapter(cwd=self.root)

    def probes(self) -> dict[RulesBackend, RulesEngineProbe]:
        return {
            RulesBackend.TACTICAL: self.tactical.probe(),
            RulesBackend.XMAGE: self.xmage.probe(),
        }

    def available_external(self) -> tuple[RulesEngineAdapter, ...]:
        available: list[RulesEngineAdapter] = []
        for adapter in (self.xmage,):
            if adapter.probe().availability.value == "available":
                available.append(adapter)
        return tuple(available)

    def close(self) -> None:
        self.xmage.close()
        self.tactical.close()


__all__ = ["RulesEngineManager"]
