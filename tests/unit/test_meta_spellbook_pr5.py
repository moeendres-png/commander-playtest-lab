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

import pytest
from pydantic import ValidationError

from commander_lab.models import FormatBand, MetaCategory, MetaComboLine, MetaPackage

ROOT = Path(__file__).resolve().parents[2]
ROGSHAI_PACKAGES = ROOT / "data/meta/packages/rogshai-2026-10-25.json"
CHULANE_PACKAGES = ROOT / "data/meta/packages/chulane-2026-10-25.json"
COMBOS = ROOT / "data/meta/spellbook_combos.json"


def _package(package_id: str, cards: tuple[str, ...], bands: tuple[str, ...]) -> MetaPackage:
    return MetaPackage(
        package_id=package_id,
        name=package_id,
        cards=cards,
        roles=("engine",),
        categories=tuple(MetaCategory(band) for band in bands),
        description="test package",
    )


def _combo(
    combo_id: str,
    cards: tuple[str, ...],
    bands: tuple[FormatBand, ...],
    any_of: tuple[tuple[str, ...], ...] = (),
) -> MetaComboLine:
    return MetaComboLine(
        combo_id=combo_id,
        commander="Test Commander",
        cards=cards,
        any_of=any_of,
        bands=bands,
        source="test",
        result="test result",
    )


def test_scoring_path_never_imports_spellbook_sync() -> None:
    src = ROOT / "src/commander_lab/whole_deck"
    for name in ("meta.py", "search_meta_score.py", "search_construct.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert "commander_spellbook" not in text
        assert "sync_commander_spellbook_snapshot" not in text


def test_combo_model_rejects_empty_cards_and_groups() -> None:
    with pytest.raises(ValidationError):
        _combo("bad", (), (FormatBand.HIGH_POWER,))
    with pytest.raises(ValidationError):
        _combo("bad", ("A",), (FormatBand.HIGH_POWER,), any_of=((),))
