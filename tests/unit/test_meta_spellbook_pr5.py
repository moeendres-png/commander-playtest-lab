"""Meta-Lane PR5: Spellbook wiring as metadata-only (design §5.4, §6 PR5).

Combo lines are metadata, never rules knowledge: containment in a deck
says nothing about legality or strength. Snapshot packages become a
scoring input for the first time, with the PR4 veto live (vetoed
packages contribute exactly 0) and band separation enforced (a cEDH
line/package never counts for a casual band). No test here uses games,
collection data, or the network.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROGSHAI_PACKAGES = ROOT / "data/meta/packages/rogshai-2026-10-25.json"
CHULANE_PACKAGES = ROOT / "data/meta/packages/chulane-2026-10-25.json"
COMBOS = ROOT / "data/meta/spellbook_combos.json"
