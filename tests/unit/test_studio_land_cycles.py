"""Tests for the pinned Land Cycles overview in the Deckbuilder (#1452).

Verifies that:
- ``LAND_CYCLES`` is a pinned, named 14-cycle inventory with exact card counts and no runtime
  heuristics.
- ``land_cycles_summary`` filters each cycle to the commander's colour identity and reports
  explicit ``n / N`` counts for deck and pool (including front-face MDFC matching for Pathways).
- Mono-colour commanders report ``0 / 0 in Farbidentität`` cleanly.
- Neither the backend payload nor the UI rendering uses recommendation, upgrade, or purchase
  language.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, land_advisor
from commander_lab.studio.web import STATIC, create_app


def _row(
    name: str,
    *,
    card_id: str = "",
    zone: str = "main",
    quantity: int = 1,
    identity: str = "",
) -> dict[str, object]:
    return {
        "card_id": card_id,
        "oracle_name": name,
        "zone": zone,
        "quantity": quantity,
        "type_line": "Land",
        "mana_cost": "",
        "produced_mana": "",
        "layout": "normal",
        "color_identity": identity,
    }


def _insert_pool_land(
    store: StudioStore,
    *,
    card_id: str,
    oracle_name: str,
    color_identity: str,
    total_owned: int,
    available: int,
    source_id: str,
) -> None:
    with store.connection as db:
        db.execute(
            "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
            "legality_verified_at, identity_evidence, source_id) "
            "VALUES (?, ?, ?, ?, '', 0, 'Land', '', 0, 1, '2026-11-17', 'scryfall', ?)",
            (card_id, f"oid-{card_id}", oracle_name, color_identity, source_id),
        )
        db.execute(
            "INSERT INTO inventory VALUES (?, ?, ?, 0, ?, 1, 1, '2026-11-17', ?)",
            (card_id, total_owned, total_owned, available, source_id),
        )


def test_pinned_land_cycles_inventory_is_complete_and_unique() -> None:
    cycles = land_advisor.LAND_CYCLES
    assert len(cycles) == 14
    keys = tuple(str(c["key"]) for c in cycles)
    assert keys == (
        "fetch",
        "shock",
        "original_dual",
        "crowd",
        "slow",
        "fast",
        "pain",
        "check",
        "filter",
        "pathway",
        "horizon",
        "surveil",
        "triome",
        "verge",
    )
    seen_names: set[str] = set()
    for cycle in cycles:
        cards = cycle["cards"]
        assert isinstance(cards, tuple)
        expected_len = 6 if cycle["key"] == "horizon" else 10
        assert len(cards) == expected_len
        for name, colours in cards:
            assert isinstance(name, str) and name
            assert name not in seen_names
            seen_names.add(name)
            assert isinstance(colours, tuple)
            assert len(colours) in (2, 3)
            for col in colours:
                assert col in ("W", "U", "B", "R", "G")
    assert len(seen_names) == 136


def test_land_cycles_summary_for_bant_commander_counts_deck_and_pool_with_denominators(
    tmp_path: Path,
) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])

    _insert_pool_land(
        store,
        card_id="land-breeding-pool",
        oracle_name="Breeding Pool",
        color_identity="G,U",
        total_owned=1,
        available=1,
        source_id=source_id,
    )
    _insert_pool_land(
        store,
        card_id="land-temple-garden",
        oracle_name="Temple Garden",
        color_identity="G,W",
        total_owned=1,
        available=1,
        source_id=source_id,
    )
    _insert_pool_land(
        store,
        card_id="land-hallowed-fountain",
        oracle_name="Hallowed Fountain",
        color_identity="W,U",
        total_owned=1,
        available=0,
        source_id=source_id,
    )
    _insert_pool_land(
        store,
        card_id="land-watery-grave",
        oracle_name="Watery Grave",
        color_identity="U,B",
        total_owned=1,
        available=1,
        source_id=source_id,
    )
    # MDFC Pathway stored by front face in collection
    _insert_pool_land(
        store,
        card_id="land-barkchannel",
        oracle_name="Barkchannel Pathway",
        color_identity="G,U",
        total_owned=1,
        available=1,
        source_id=source_id,
    )
    _insert_pool_land(
        store,
        card_id="land-spara",
        oracle_name="Spara's Headquarters",
        color_identity="G,W,U",
        total_owned=1,
        available=1,
        source_id=source_id,
    )

    rows = [
        _row("Chulane, Teller of Tales", zone="commander", identity="GWU"),
        _row("Breeding Pool", card_id="land-breeding-pool"),
        _row("Branchloft Pathway // Boulderloft Pathway"),
        _row("Spara's Headquarters", card_id="land-spara"),
    ]
    summary = land_advisor.land_cycles_summary(store, rows)
    store.close()

    assert summary["schema"] == "studio-land-cycles-1"
    assert summary["data_class"] == "derived_descriptive"
    assert summary["identity"] == ["W", "U", "G"]
    assert summary["cycles_total"] == 14
    # 12 two-colour cycles * 3 pairs + 1 horizon cycle * 2 pairs + 1 triome cycle * 1 triple = 39
    assert summary["legal_lands_total"] == 39
    assert summary["in_deck_total"] == 3
    assert summary["in_pool_extra_total"] == 2
    assert summary["in_pool_total"] == 6

    cycles_list = summary["cycles"]
    assert isinstance(cycles_list, list)
    assert len(cycles_list) == 14
    by_key = {str(c["key"]): c for c in cycles_list}

    shock = by_key["shock"]
    assert shock["cycle_size"] == 10
    assert shock["total"] == 3
    assert shock["in_deck"] == 1
    assert shock["in_pool_extra"] == 1
    assert shock["in_pool_total"] == 3
    assert shock["summary"] == "1 / 3 im Deck, 1 weitere von 3 im Pool"
    shock_cards = shock["cards"]
    assert isinstance(shock_cards, list)
    assert len(shock_cards) == 3
    shock_by_name = {str(c["name"]): c for c in shock_cards}
    assert shock_by_name["Breeding Pool"]["status"] == "im Deck"
    assert shock_by_name["Breeding Pool"]["in_deck"] is True
    assert shock_by_name["Temple Garden"]["status"] == "im Pool (frei)"
    assert shock_by_name["Temple Garden"]["in_pool_extra"] is True
    assert shock_by_name["Hallowed Fountain"]["status"] == "im Pool (0 frei)"
    assert shock_by_name["Hallowed Fountain"]["in_pool"] is True
    assert shock_by_name["Hallowed Fountain"]["in_pool_extra"] is False

    pathway = by_key["pathway"]
    assert pathway["total"] == 3
    assert pathway["in_deck"] == 1
    assert pathway["in_pool_extra"] == 1
    pathway_cards = pathway["cards"]
    assert isinstance(pathway_cards, list)
    assert len(pathway_cards) == 3
    pathway_by_name = {str(c["name"]): c for c in pathway_cards}
    assert pathway_by_name["Branchloft Pathway // Boulderloft Pathway"]["status"] == "im Deck"
    assert (
        pathway_by_name["Barkchannel Pathway // Tidechannel Pathway"]["status"] == "im Pool (frei)"
    )
    assert (
        pathway_by_name["Barkchannel Pathway // Tidechannel Pathway"]["card_id"]
        == "land-barkchannel"
    )
    assert pathway_by_name["Hengegate Pathway // Mistgate Pathway"]["status"] == "nicht in Sammlung"

    triome = by_key["triome"]
    assert triome["total"] == 1
    assert triome["in_deck"] == 1
    assert triome["in_pool_extra"] == 0
    assert triome["summary"] == "1 / 1 im Deck, 0 weitere von 1 im Pool"

    horizon = by_key["horizon"]
    assert horizon["cycle_size"] == 6
    assert horizon["total"] == 2


def test_mono_colour_commander_reports_zero_over_zero_without_division_error(
    tmp_path: Path,
) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    rows = [_row("Test Commander", zone="commander", identity="G")]
    summary = land_advisor.land_cycles_summary(store, rows)
    store.close()

    assert summary["identity"] == ["G"]
    assert summary["legal_lands_total"] == 0
    assert summary["in_deck_total"] == 0
    assert summary["in_pool_extra_total"] == 0
    cycles = summary["cycles"]
    assert isinstance(cycles, list)
    assert len(cycles) == 14
    for cycle in cycles:
        assert cycle["total"] == 0
        assert cycle["in_deck"] == 0
        assert cycle["in_pool_extra"] == 0
        assert cycle["summary"] == "0 / 0 in Farbidentität"


def test_land_cycles_holds_no_recommendation_or_purchase_language(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    rows = [_row("Chulane, Teller of Tales", zone="commander", identity="GWU")]
    summary = land_advisor.land_cycles_summary(store, rows)
    store.close()

    text = str(summary).casefold()
    forbidden = (
        "empfehl",
        "sollte",
        "kauf",
        "preis",
        "euro",
        "dollar",
        "upgrade",
        "pflicht",
        "fehlt",
    )
    assert len(forbidden) == 9
    for word in forbidden:
        assert word not in text


def test_land_advisor_route_and_ui_expose_land_cycles(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _deck, _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    resp = client.post("/api/land-advisor", json={"cards": [c.__dict__ for c in _deck()]})
    assert resp.status_code == 200
    payload = resp.json()
    assert "land_cycles" in payload
    lc = payload["land_cycles"]
    assert lc["schema"] == "studio-land-cycles-1"
    assert lc["cycles_total"] == 14
    assert isinstance(lc["cycles"], list)
    assert len(lc["cycles"]) == 14

    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "land-advisor-cycles" in app_js
    assert "land-advisor-cycles-summary" in app_js
    assert "Länder-Zyklen in Farbidentität (Deck & Pool)" in app_js
