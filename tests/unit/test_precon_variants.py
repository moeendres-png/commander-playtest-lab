"""The SYNTHETIC proxy decks stay faithful copies except for the mapped cards, and say so."""

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
# The 9 precons the engine cannot import at the pin 90f5c4d3f8 (docs/PRECON_VALIDATION.md).
UNIMPORTABLE = {
    "2023_blast_from_the_past",
    "2023_masters_of_evil",
    "2023_paradox_power",
    "2023_timey_wimey",
    "2024_blame_game",
    "2024_revenant_recon",
    "2024_tricky_terrain",
    "2024_tricky_terrain_collector_s_edition",
    "2026_odds_and_ends",
}
COMMANDER_STEMS = sorted(MODULE.COMMANDER_PROXIES)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _names(deck: dict[str, Any], zone: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in deck["cards"]:
        if entry["zone"] == zone:
            counts[entry["oracle_name"]] += entry["quantity"]
    return counts


def test_committed_proxies_match_the_generator() -> None:
    assert MODULE.main(["--check"]) == 0


def test_every_deck_the_engine_cannot_import_has_a_proxy_and_no_other_deck_has() -> None:
    assert set(STEMS) == UNIMPORTABLE
    assert {p.stem for p in MODULE.VARIANT_DIR.glob("*.json")} == UNIMPORTABLE


def test_no_deck_needs_a_proxy_commander_since_repin_v13() -> None:
    # The four decks whose commander the engine did not know import with the real commander at
    # the pin 90f5c4d3f8; their proxies are retired and the real decks count.
    assert COMMANDER_STEMS == []
    retired = {
        "2024_death_toll",
        "2024_family_matters",
        "2024_miracle_worker",
        "2026_multiverse_reforged",
    }
    assert not retired & set(STEMS)
    assert not any((MODULE.VARIANT_DIR / f"{stem}.json").exists() for stem in retired)


@pytest.mark.parametrize("stem", STEMS)
def test_proxy_differs_from_the_original_only_in_the_mapped_cards(stem: str) -> None:
    mapping = MODULE.SUBSTITUTIONS[stem]
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    proxy = _load(MODULE.VARIANT_DIR / f"{stem}.json")

    if stem in MODULE.COMMANDER_PROXIES:
        new = MODULE.COMMANDER_PROXIES[stem]
        assert proxy["commander"]["commanders"] == [new]
        assert _names(proxy, "commander") == Counter({new: 1})
        assert new not in _names(original, "main")
        assert new not in original["commander"]["commanders"]
    else:
        assert proxy["commander"] == original["commander"]
        assert _names(proxy, "commander") == _names(original, "commander")
    expected = _names(original, "main")
    for old, new in mapping.items():
        assert expected[old] == 1
        assert new not in expected, f"{new} is already in {stem}"
        del expected[old]
        expected[new] += 1
    assert _names(proxy, "main") == expected
    assert sum(_names(proxy, "main").values()) == sum(_names(original, "main").values())
    assert proxy["format"] == original["format"]


@pytest.mark.parametrize("stem", STEMS)
def test_proxy_is_labelled_synthetic_in_the_deck_data(stem: str) -> None:
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    proxy = _load(MODULE.VARIANT_DIR / f"{stem}.json")
    assert proxy["deck_id"].startswith("precon-synthetic/")
    assert proxy["deck_id"] != original["deck_id"]
    assert proxy["name"].endswith("(SYNTHETIC proxy)")
    assert "SYNTHETIC" in proxy["tags"]
    assert proxy["notes"].startswith(f"SYNTHETIC proxy of {original['deck_id']}")
    notes = [e["notes"] for e in proxy["cards"] if e["notes"]]
    assert len(notes) == len(MODULE.SUBSTITUTIONS[stem]) + (stem in MODULE.COMMANDER_PROXIES)
    assert all(n.startswith("SYNTHETIC: ") for n in notes)


@pytest.mark.parametrize("stem", STEMS)
def test_originals_are_left_untouched(stem: str) -> None:
    original = _load(MODULE.PRECON_DIR / f"{stem}.json")
    assert original["deck_id"].startswith("precon/")
    assert "SYNTHETIC" not in original["name"]
    assert "SYNTHETIC" not in (original.get("tags") or [])
    assert not any((e["notes"] or "").startswith("SYNTHETIC") for e in original["cards"])


def test_the_pool_is_173_with_9_synthetic() -> None:
    listing = _load(MODULE.MANIFEST)
    originals = list(MODULE.PRECON_DIR.glob("*.json"))
    assert listing["pool"] == {
        "decks": len(originals),
        "real": len(originals) - 9,
        "synthetic": 9,
    }
    assert (
        listing["pool"]["decks"] == 173
    )  # 195 until the sort-out of 21 decks on 2026-10-25 and of Nature of the Beast (2013) on 2026-10-26
    assert set(listing["decks"]) == UNIMPORTABLE
    assert listing["evidence_class"] == "SYNTHETIC"


@pytest.mark.parametrize("stem", STEMS)
def test_the_proxy_list_matches_the_deck_files(stem: str) -> None:
    entry = _load(MODULE.MANIFEST)["decks"][stem]
    proxy = _load(MODULE.VARIANT_DIR / f"{stem}.json")
    assert entry["proxy_deck_id"] == proxy["deck_id"]
    assert (MODULE.ROOT / entry["proxy_file"]).is_file()
    assert {r["original"]: r["proxy"] for r in entry["main_deck_replacements"]} == (
        MODULE.SUBSTITUTIONS[stem]
    )
    assert (entry["commander_replacement"] or {}).get("proxy") == MODULE.COMMANDER_PROXIES.get(stem)


def test_a_proxy_commander_is_no_other_precon_s_commander_and_not_in_its_own_deck() -> None:
    commanders: Counter[str] = Counter()
    for path in MODULE.PRECON_DIR.glob("*.json"):
        if path.stem in UNIMPORTABLE:
            continue
        commanders.update(_load(path)["commander"]["commanders"])
    # Every proxy commander (none since repin v13) is no other precon's commander.
    shared = {n for n in MODULE.COMMANDER_PROXIES.values() if commanders[n]}
    assert shared == set()


def test_a_proxy_commander_already_in_the_deck_is_rejected() -> None:
    original = _load(MODULE.PRECON_DIR / "2024_death_toll.json")
    in_deck = next(e["oracle_name"] for e in original["cards"] if e["zone"] == "main")
    with pytest.raises(ValueError, match="already in the deck"):
        MODULE.build_variant(original, {}, in_deck)


def test_a_mapping_for_a_card_not_in_the_main_deck_is_rejected() -> None:
    original = _load(MODULE.PRECON_DIR / f"{STEMS[0]}.json")
    with pytest.raises(ValueError, match="not a main-deck card"):
        MODULE.build_variant(original, {"No Such Card": "Sol Ring"})
