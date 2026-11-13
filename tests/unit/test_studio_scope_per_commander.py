"""One commander, one denominator: the data report, the options route and partner pairs.

Review findings of the merged deck builder / tier list (Refs #1205). All data is synthetic.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, universe, universe_view
from commander_lab.studio.data_report import data_report
from commander_lab.studio.web import create_app
from tests.unit.test_studio_universe_web import _deck

ALPHA = "Alpha Commander"
BETA = "Beta Commander"
PARTNER = "Partner Commander"


def _bind(store: StudioStore, deck_id: str, *names: str) -> None:
    db = store.connection
    db.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = ?", (deck_id,))
    db.executemany(
        "INSERT INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('corpus_deck', ?, ?, 'TEST')",
        [(deck_id, name) for name in names],
    )


@pytest.fixture
def store(tmp_path: Path) -> StudioStore:
    """Three decks of Alpha, one of Beta, two of the pair Alpha + Partner."""
    opened = StudioStore.open(tmp_path / "studio")
    for index in range(3):
        _deck(opened, f"a{index}", "edhrec", 3, ["Sol Ring", f"Alpha Only {index}"])
        _bind(opened, f"a{index}", ALPHA)
    _deck(opened, "b0", "edhrec", 3, ["Sol Ring"])
    _bind(opened, "b0", BETA)
    for index in range(2):
        _deck(opened, f"p{index}", "edhrec", 3, ["Sol Ring", f"Pair Only {index}"])
        _bind(opened, f"p{index}", ALPHA, PARTNER)
    opened.connection.commit()
    return opened


def test_report_counts_each_profile_per_commander_never_mixed(store: StudioStore) -> None:
    universe.save_profile(store, "alle", {"min_universe": 3})
    section = data_report(store, today=date(2026, 11, 12))["universes"]
    assert isinstance(section, dict)
    entries = {
        tuple(entry["commanders"]): entry for entry in section["details"][0]["per_commander"]
    }
    assert set(entries) == {(ALPHA,), (BETA,), (ALPHA, PARTNER)}
    assert entries[(ALPHA,)]["denominator"] == 3
    assert entries[(BETA,)]["denominator"] == 1
    assert entries[(ALPHA, PARTNER)]["denominator"] == 2
    # a mixed denominator (6 decks) would have passed the minimum of 3: each commander is
    # judged on its own count
    assert entries[(ALPHA,)]["below_min_universe"] is False
    assert entries[(BETA,)]["below_min_universe"] is True
    assert entries[(ALPHA, PARTNER)]["below_min_universe"] is True
    assert section["below_min_universe"] == 2 and section["commander_sets"] == 3
    snapshots = {entry["snapshot_id"] for entry in entries.values()}
    assert len(snapshots) == 3
    assert "denominator" not in section["details"][0]  # no figure over all commanders


def test_report_of_a_profile_with_named_commanders_counts_only_that_set(
    store: StudioStore,
) -> None:
    universe.save_profile(store, "nur-beta", {"commanders": [BETA]})
    section = data_report(store, today=date(2026, 11, 12))["universes"]
    assert isinstance(section, dict)
    per_commander = section["details"][0]["per_commander"]
    assert [(item["commanders"], item["denominator"]) for item in per_commander] == [([BETA], 1)]


def test_options_route_needs_a_commander_and_counts_only_its_decks(
    store: StudioStore, tmp_path: Path
) -> None:
    store.close()
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert client.get("/api/universe/options").status_code == 422
        alpha = client.get("/api/universe/options", params={"commander": ALPHA}).json()
        beta = client.get("/api/universe/options", params={"commander": BETA}).json()
        pair = client.get("/api/universe/options", params={"commander": [ALPHA, PARTNER]}).json()
    assert alpha["platforms"] == [{"value": "edhrec", "decks": 3}]
    assert alpha["commanders"] == [{"value": ALPHA, "decks": 3}]
    assert beta["platforms"] == [{"value": "edhrec", "decks": 1}]
    assert pair["platforms"] == [{"value": "edhrec", "decks": 2}]
    cards = {item["value"]: item["decks"] for item in alpha["cards"]} if alpha["cards"] else {}
    assert "Pair Only 0" not in cards


def test_partner_decks_belong_to_the_pair_not_to_either_partner(store: StudioStore) -> None:
    alpha = universe.resolve_universe(store, {"commanders": [ALPHA]})
    pair = universe.resolve_universe(store, {"commanders": [ALPHA, PARTNER]})
    assert alpha == ["a0", "a1", "a2"]
    assert pair == ["p0", "p1"]
    assert universe.resolve_universe(store, {"commanders": [PARTNER]}) == []


def test_universe_and_builder_show_one_denominator_for_every_commander_set(
    store: StudioStore,
) -> None:
    """The exact-set rule of ``builder.bound_to`` and of the universe agree."""
    universe.save_profile(store, "alle", {})
    for names in ([ALPHA], [BETA], [ALPHA, PARTNER], [PARTNER]):
        counted = universe_view.profile_summary(store, "alle", commander_names=names)
        bound = builder.corpus_binding(store, names)["bound_decks"]
        assert counted["denominator"] == bound, names
        spread = universe_view.pool_spread(store, "alle", [], commander_names=names)
        assert spread["universe"]["denominator"] == bound, names
