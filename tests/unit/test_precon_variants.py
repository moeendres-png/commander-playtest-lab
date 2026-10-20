"""The precon variant decks stay faithful copies except for the mapped replacement cards."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_precon_variants", ROOT / "scripts/build_precon_variants.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()
STEMS = sorted(MODULE.SUBSTITUTIONS)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _names(deck: dict[str, Any], zone: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in deck["cards"]:
        if entry["zone"] == zone:
            counts[entry["oracle_name"]] += entry["quantity"]
    return counts


def test_committed_variants_match_the_generator() -> None:
    assert MODULE.main(["--check"]) == 0


def test_four_decks_without_a_known_commander_get_no_variant() -> None:
    assert not {
        "2024_death_toll",
        "2024_family_matters",
        "2024_miracle_worker",
        "2026_multiverse_reforged",
    } & set(STEMS)


@pytest.mark.parametrize("stem", STEMS)
def test_variant_differs_from_the_original_only_in_the_mapped_cards(stem: str) -> None:
    mapping = MODULE.SUBSTITUTIONS[stem]
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    variant = _load(MODULE.VARIANT_DIR / f"{stem}.json")

    assert variant["commander"] == original["commander"]
    assert _names(variant, "commander") == _names(original, "commander")
    expected = _names(original, "main")
    for old, new in mapping.items():
        assert expected[old] == 1
        assert new not in expected, f"{new} is already in {stem}"
        del expected[old]
        expected[new] += 1
    assert _names(variant, "main") == expected
    assert sum(_names(variant, "main").values()) == sum(_names(original, "main").values())


@pytest.mark.parametrize("stem", STEMS)
def test_variant_is_labelled_and_not_the_precon_id(stem: str) -> None:
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    variant = _load(MODULE.VARIANT_DIR / f"{stem}.json")
    assert variant["deck_id"].startswith("precon-variant/")
    assert variant["deck_id"] != original["deck_id"]
    assert variant["name"].endswith("(variant, replacement cards)")
    notes = [e["notes"] for e in variant["cards"] if e["notes"]]
    assert len(notes) == len(MODULE.SUBSTITUTIONS[stem])
    assert all(n.startswith("VARIANT: replaces ") for n in notes)


@pytest.mark.parametrize("stem", STEMS)
def test_originals_are_left_untouched(stem: str) -> None:
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    assert original["deck_id"].startswith("precon/")
    assert "variant" not in original["name"]
    assert not any((e["notes"] or "").startswith("VARIANT") for e in original["cards"])


def test_a_mapping_for_a_card_not_in_the_main_deck_is_rejected() -> None:
    original = _load(MODULE.PRECON_DIR / f"{STEMS[0]}.json")
    with pytest.raises(ValueError, match="not a main-deck card"):
        MODULE.build_variant(original, {"No Such Card": "Sol Ring"})
