"""Tierliste v3 package 3 (#1365), server side: confidence, borderline mark, the U breakdown and
the spells/lands tier counts. One synthetic commander (see ``test_studio_strength_v3_view``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import strength, strength_view
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_strength_v3_view import CMD, LAND, _cards, _compute, _store

HEADER = {"X-Studio": "1"}


def _expected_confidence(card: strength_view.StrengthCard, *, by_count: bool = True) -> float:
    """The documented formula (D4): coverage x the weighted mean of k / (k + 30) over the weighted
    components that have a value and a denominator, k the numerator (a counted zero uses the
    denominator, a row without a numerator has reliability 0). ``by_count=False`` is the earlier formula with the
    denominator for every row, kept as ``confidence_by_denominator``."""
    rows = [
        row
        for row in card["components"]
        if row["weight"] > 0 and row["percentile"] is not None and row["denominator"]
    ]
    assert card["coverage"] is not None
    total = sum(row["weight"] for row in rows)
    reliability = 0.0
    for row in rows:
        count = row["denominator"] or 0
        if by_count and row["numerator"] is None:
            continue
        if by_count and row["numerator"]:
            count = row["numerator"]
        reliability += row["weight"] * count / (count + 30)
    return round(card["coverage"] * reliability / total, 4)


def test_confidence_follows_the_documented_formula() -> None:
    cards = _cards(_compute(_store()))
    checked = 0
    for card in cards.values():
        if card["tier"] == "N":
            continue
        if card["index"] is None:
            assert card["confidence"] is None
            continue
        assert card["confidence"] == pytest.approx(_expected_confidence(card))
        assert card["confidence_by_denominator"] == pytest.approx(
            _expected_confidence(card, by_count=False)
        )
        assert 0.0 <= card["confidence"] <= 1.0
        checked += 1
    assert checked >= 5


def test_confidence_is_higher_with_more_coverage_and_has_a_level() -> None:
    cards = _cards(_compute(_store()))
    rich, thin = cards["Card 00"], cards["Card 07"]
    assert rich["confidence"] is not None and thin["confidence"] is not None
    assert rich["confidence"] > thin["confidence"]
    assert rich["confidence_level"] == strength.confidence_level(rich["confidence"])
    assert thin["confidence_level"] == strength.confidence_level(thin["confidence"])
    assert strength.confidence_level(0.6) == "high"
    assert strength.confidence_level(0.35) == "medium"
    assert strength.confidence_level(0.3499) == "low"


def test_a_card_without_a_tier_has_no_confidence() -> None:
    cards = _cards(_compute(_store(), rank_commander_and_basics=False, rank_other_commanders=False))
    unranked = [card for card in cards.values() if card["tier"] == "N"]
    assert unranked
    for card in unranked:
        assert card["confidence"] is None and card["confidence_level"] is None
        assert card["borderline"] is False


def test_borderline_is_the_distance_to_the_nearest_cut() -> None:
    cuts = {"S": 72.0, "A": 50.0, "B": 28.0, "C": 14.0}
    assert strength.borderline_info(51.5, cuts, 2.0) == (True, "A", 1.5)
    assert strength.borderline_info(52.0, cuts, 2.0) == (False, "A", 2.0)  # exactly 2: not closer
    assert strength.borderline_info(13.0, cuts, 2.0) == (True, "C", 1.0)
    assert strength.borderline_info(40.0, cuts, 2.0)[0] is False
    assert strength.borderline_info(50.0, cuts, 0.0)[0] is False  # 0 switches the mark off
    assert strength.borderline_info(None, cuts, 2.0) == (False, None, None)


def test_the_cards_carry_the_borderline_mark_and_the_setting_changes_it() -> None:
    store = _store()
    default = _compute(store)
    assert default["settings"]["borderline_distance"] == 2.0
    for card in default["cards"]:
        if card["tier"] not in strength.TIERS:
            assert card["borderline"] is False
            continue
        nearest = min(abs(card["index"] - cut) for cut in default["settings"]["tier_cuts"].values())
        assert card["borderline"] is (nearest < 2.0)
        assert card["cut_distance"] == pytest.approx(nearest, abs=0.05)
    off = _compute(store, borderline_distance=0.0)
    assert not any(card["borderline"] for card in off["cards"])
    wide = _compute(store, borderline_distance=50.0)
    assert all(card["borderline"] for card in wide["cards"] if card["tier"] in strength.TIERS)


def test_the_borderline_setting_is_validated_stored_and_explained() -> None:
    assert StrengthSettings().borderline_distance == 2.0
    assert StrengthSettings.from_dict(StrengthSettings().to_dict()) == StrengthSettings()
    for bad in (-1, 51, "x", True):
        with pytest.raises(ValueError):
            StrengthSettings.from_dict({"borderline_distance": bad})
    panel = strength_view.presets()["panel"]
    assert isinstance(panel, dict)
    assert "(empfohlen: 2)" in panel["labels"]["borderline_distance"]
    assert panel["help"]["borderline_distance"]
    keys = [key for group in panel["groups"] for key in group["keys"]]
    assert "borderline_distance" in keys


def test_the_unknown_breakdown_separates_counted_zero_from_missing_data() -> None:
    result = _compute(_store(), zero_count_tier="U")
    breakdown = result["unknown_breakdown"]
    unknown = [card for card in result["cards"] if card["tier"] == "U"]
    assert breakdown["total"] == len(unknown) == result["tier_counts"]["U"]
    assert breakdown["zero_count"] == sum(card["reason"] == "ZERO_COUNT_ONLY" for card in unknown)
    assert breakdown["zero_count"] >= 1
    assert breakdown["zero_count"] + breakdown["missing_data"] == breakdown["total"]
    assert sum(breakdown["by_reason"].values()) == breakdown["total"]
    assert breakdown["denominator"] == result["corpus"]["decks"]
    for card in unknown:
        assert card["confidence"] is None and card["confidence_level"] is None
        assert card["borderline"] is False
    default = _compute(_store())["unknown_breakdown"]
    assert default["zero_count"] == 0


def test_the_tier_counts_are_split_into_spells_and_lands() -> None:
    result = _compute(_store())
    by_kind = result["tier_counts_by_kind"]
    for tier, count in result["tier_counts"].items():
        assert by_kind["spells"][tier] + by_kind["lands"][tier] == count
    land = next(card for card in result["cards"] if card["name"] == LAND)
    assert land["is_land"] is True
    assert sum(by_kind["lands"].values()) == 1  # only the one synthetic land is in the pool
    assert next(card for card in result["cards"] if card["name"] == "Card 00")["is_land"] is False


def test_the_route_returns_the_new_fields(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    store = _store(folder=folder)
    store.close()
    with TestClient(create_app(folder)) as client:
        response = client.post(
            "/api/strength",
            json={"commander": CMD, "settings": {"borderline_distance": 5}},
            headers=HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        card = next(item for item in data["cards"] if item["name"] == "Card 00")
        for key in ("confidence", "confidence_level", "borderline", "cut_distance", "is_land"):
            assert key in card
        assert data["settings"]["borderline_distance"] == 5
        assert {"total", "zero_count", "missing_data", "by_reason"} <= set(
            data["unknown_breakdown"]
        )
        assert set(data["tier_counts_by_kind"]) == {"spells", "lands"}
        zero = next(item for item in card["components"] if item["component"] == "deck_universe")
        assert zero["status"] in ("PRESENT", "ZERO_COUNT", "NO_VALUE", "NOT_COLLECTED")


def test_the_borderline_setting_never_changes_index_or_tier() -> None:
    store = _store()
    runs = [_compute(store, borderline_distance=d)["cards"] for d in (0.0, 2.0, 50.0)]
    assert runs[0]
    keyed = [{c["name"]: (c["index"], c["tier"], c["coverage"]) for c in run} for run in runs]
    assert keyed[0] == keyed[1] == keyed[2]
