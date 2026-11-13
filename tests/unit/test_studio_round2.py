"""Round 2 of the Studio: deck filter by cards, EDHREC share from stored signals, universe
card suggestions. All data is synthetic."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, signals
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_universe_web import _deck, folder  # noqa: F401

COMMANDER = "Test Commander"


@pytest.fixture
def client(folder: Path) -> Iterator[TestClient]:  # noqa: F811
    with TestClient(create_app(folder)) as test_client:
        yield test_client


def _filter(client: TestClient, *cards: str, profile: str | None = None) -> dict[str, object]:
    params: dict[str, object] = {"commander": COMMANDER, "card": list(cards)}
    if profile:
        params["profile"] = profile
    answer = client.get("/api/deck-filter", params=params)
    assert answer.status_code == 200, answer.text
    return answer.json()  # type: ignore[no-any-return]


def _by_name(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {card["name"]: card for card in result["cards"]}  # type: ignore[index, union-attr]


def test_deck_filter_counts_only_decks_with_all_chosen_cards(client: TestClient) -> None:
    everything = _filter(client)
    assert everything["decks"] == everything["of"] == 43
    one = _filter(client, "Swarm Rat")
    assert one["of"] == 43
    assert one["decks"] == 27  # 25 listed in lower case, plus two decks of the register import
    assert one["label"] == "Teilmenge: 27 von 43 Decks"
    both = _filter(client, "Swarm Rat", "Filler 01 // Back Side")
    assert both["decks"] == 20  # all of them are among the first 25 decks
    assert both["label"] == "Teilmenge: 20 von 43 Decks"


def test_deck_filter_marks_chosen_cards_and_counts_the_others_in_the_subset(
    client: TestClient,
) -> None:
    cards = _by_name(_filter(client, "Swarm Rat"))
    chosen = cards["Swarm Rat"]
    assert chosen["filter_card"] is True
    assert chosen["hits"] is None and chosen["share"] is None  # not ranked
    other = cards["Filler 03"]
    assert other["filter_card"] is False
    assert other["denominator"] == 27
    assert other["hits"] == 25  # 25 of the 27 decks list it
    assert other["share"] == pytest.approx(25 / 27)
    # a card no deck of the subset lists is unknown, never 0
    assert cards["Filler 05"]["hits"] is None and cards["Filler 05"]["share"] is None


def test_deck_filter_stays_inside_the_commander(client: TestClient, folder: Path) -> None:  # noqa: F811
    store = StudioStore.open(folder)
    try:
        _deck(store, "foreign", "edhrec", 3, ["Swarm Rat", "Filler 03"])
        store.connection.execute(
            "UPDATE commander_binding SET commander_name = 'Other Commander' WHERE key = 'foreign'"
        )
        store.connection.commit()
    finally:
        store.close()
    result = _filter(client, "Swarm Rat")
    assert result["decks"] == 27 and result["of"] == 43
    assert result["commander"] == [COMMANDER]


def test_deck_filter_refuses_unknown_cards_and_cards_outside_the_pool(
    client: TestClient,
) -> None:
    unknown = client.get("/api/deck-filter", params={"commander": COMMANDER, "card": ["Sol"]})
    assert unknown.status_code == 422
    assert "Sol" in unknown.json()["detail"]
    assert "Vorschlagsliste" in unknown.json()["detail"]
    outside = client.get(
        "/api/deck-filter", params={"commander": COMMANDER, "card": ["Red Outsider"]}
    )
    assert outside.status_code == 422
    assert "Kartenpool" in outside.json()["detail"]
    missing = client.get("/api/deck-filter", params={"commander": "Nobody"})
    assert missing.status_code == 404


def test_deck_filter_refuses_a_blank_card_and_the_commander_itself(client: TestClient) -> None:
    blank = client.get("/api/deck-filter", params={"commander": COMMANDER, "card": [" "]})
    assert blank.status_code == 422
    assert "Leerer Kartenname" in blank.json()["detail"]
    own = client.get("/api/deck-filter", params={"commander": COMMANDER, "card": [COMMANDER]})
    assert own.status_code == 422
    assert "steckt in jedem Deck" in own.json()["detail"]


def test_unknown_card_names_with_an_apostrophe_come_out_right(client: TestClient) -> None:
    name = "Sol's Ring, the 'Odd' One"
    answer = client.put(
        "/api/universe/profiles/x",
        params={"commander": COMMANDER},
        json={"must_contain": [name, "Zed"]},
        headers={"X-Studio": "1"},
    )
    assert answer.status_code == 422
    assert f"Diese Karte kennt das Studio nicht: {name}, Zed." in answer.json()["detail"]


def _bind_partner_deck(folder_: Path) -> None:
    store = StudioStore.open(folder_)
    try:
        _deck(store, "pair1", "edhrec", 3, ["Swarm Rat", "Filler 03"])
        store.connection.execute(
            "INSERT INTO commander_binding(kind, key, commander_name, basis) "
            "VALUES ('corpus_deck', 'pair1', 'Second Partner', 'TEST')"
        )
        store.connection.commit()
    finally:
        store.close()


def test_a_partner_pair_deck_is_not_counted_for_a_single_commander(
    client: TestClient,
    folder: Path,  # noqa: F811
) -> None:
    _bind_partner_deck(folder)
    result = _filter(client, "Swarm Rat")
    assert result["decks"] == 27 and result["of"] == 43
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()["cards"]
    ids = {card["name"]: card["card_id"] for card in pool}
    answer = client.get(
        f"/api/cards/{ids['Filler 03']}/cooccurrence",
        params={"commander": COMMANDER, "must_contain": ["Swarm Rat"]},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["denominator"] == 27
    assert answer.json()["decks_with_card"] == 25


def _import_two_commanders(store: StudioStore, folder_: Path) -> None:
    folder_.mkdir()
    (folder_ / "commander_card_signals.csv").write_text(
        "commander_name,card_name,num_decks,potential_decks,synergy\n"
        f"{COMMANDER},Filler 03,40,100,0.12\n"
        "Other Commander,Filler 04,90,100,0.9\n",
        encoding="utf-8",
    )
    with store.importing_for(COMMANDER):
        signals.import_signals(store, folder_, commander=COMMANDER)


def test_another_commanders_signal_rows_never_appear_in_the_builder_pool(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    _import_two_commanders(store, tmp_path / "signals")
    cards = {card["name"]: card for card in builder.pool_cards(store, [COMMANDER])["cards"]}  # type: ignore[union-attr]
    store.close()
    assert cards["Filler 03"]["signals"]["synergy"]["value"] == pytest.approx(0.12)
    assert cards["Filler 04"]["signals"] == {}
    assert cards["Filler 04"]["edhrec"] is None


def test_a_partner_pair_gets_no_commander_signal(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    _import_two_commanders(store, tmp_path / "signals")
    pair = builder.pool_cards(store, [COMMANDER, "Filler 03"])["cards"]
    store.close()
    assert pair  # type: ignore[truthy-bool]
    assert all(card["signals"] == {} and card["edhrec"] is None for card in pair)  # type: ignore[index, union-attr]


def test_cooccurrence_over_the_filtered_decks(client: TestClient) -> None:
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()["cards"]
    ids = {card["name"]: card["card_id"] for card in pool}
    answer = client.get(
        f"/api/cards/{ids['Filler 03']}/cooccurrence",
        params={"commander": COMMANDER, "must_contain": ["Swarm Rat"]},
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["denominator"] == 27
    assert body["decks_with_card"] == 25
    assert body["subset_note"].startswith("Teilmenge: nur Decks mit Swarm Rat")
    assert (
        client.get(
            f"/api/cards/{ids['Filler 03']}/cooccurrence", params={"commander": COMMANDER}
        ).status_code
        == 422
    )


def test_universe_options_offer_the_pool_cards_even_without_decks(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.connection.execute("PRAGMA foreign_keys = OFF")
    store.connection.execute("DELETE FROM commander_binding")
    store.connection.execute("DELETE FROM corpus_deck_card")
    store.connection.execute("DELETE FROM corpus_cohort")
    store.connection.execute("DELETE FROM corpus_deck")
    store.connection.commit()
    store.close()
    with TestClient(create_app(tmp_path / "studio")) as test_client:
        cards = test_client.get("/api/universe/options", params={"commander": COMMANDER}).json()[
            "cards"
        ]
    names = {item["value"]: item["decks"] for item in cards}
    assert "Filler 04" in names and names["Filler 04"] == 0
    assert "Red Outsider" not in names  # outside the colour identity
    assert "Banned Relic" not in names  # not legal
    assert COMMANDER not in names


def test_unknown_universe_card_is_reported_in_german(client: TestClient) -> None:
    answer = client.put(
        "/api/universe/profiles/x",
        params={"commander": COMMANDER},
        json={"must_contain": ["Sol"]},
        headers={"X-Studio": "1"},
    )
    assert answer.status_code == 422
    assert "unknown" not in answer.json()["detail"]
    assert "Sol" in answer.json()["detail"]


def test_builder_reads_the_stored_inclusion_signal(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    folder_ = tmp_path / "signals"
    folder_.mkdir()
    (folder_ / "commander_card_signals.csv").write_text(
        "commander_name,card_name,num_decks,potential_decks,synergy\n"
        f"{COMMANDER},Filler 03,40,100,0.12\n"
        f"{COMMANDER},Filler 04,,,\n",
        encoding="utf-8",
    )
    with store.importing_for(COMMANDER):
        signals.import_signals(store, folder_, commander=COMMANDER)
    cards = {card["name"]: card for card in builder.pool_cards(store, [COMMANDER])["cards"]}  # type: ignore[union-attr]
    known = cards["Filler 03"]["edhrec"]
    assert known["numerator"] == 40 and known["denominator"] == 100
    assert known["pct"] == pytest.approx(40.0)
    assert known["origin"] == "signal"
    assert cards["Filler 03"]["signals"]["synergy"]["value"] == pytest.approx(0.12)
    assert cards["Filler 04"]["edhrec"] is None  # a row without a value stays unknown
    assert cards["Filler 05"]["edhrec"] is None
    assert cards["Filler 05"]["signals"] == {}


def _node(script: str) -> str:
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    static = Path(__file__).resolve().parents[2] / "src/commander_lab/studio/static"
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=static
    )
    return done.stdout.strip()


def test_builder_search_ranks_exact_then_prefix_then_word_then_contains_then_text() -> None:
    script = """
const S = require('./search.js');
const cards = [
  {name: 'Arcane Sol Ringer', type_line: 'Creature', text: ''},
  {name: 'Ring of Sol', type_line: 'Artifact', text: ''},
  {name: 'Sol Ring', type_line: 'Artifact', text: 'Tap: add two.'},
  {name: 'Sol Ringlet', type_line: 'Artifact', text: ''},
  {name: 'Thran Dynamo', type_line: 'Artifact', text: 'Like a sol ring but bigger'},
  {name: 'Wall', type_line: 'Creature', text: ''},
  {name: 'Awesol Ring Pack', type_line: 'Artifact', text: ''},
];
console.log(JSON.stringify(S.sortByRank(cards, 'Sol Ring').map(c => c.name)));
"""
    names = json.loads(_node(script))
    assert names == [
        "Sol Ring",
        "Sol Ringlet",
        "Arcane Sol Ringer",
        "Awesol Ring Pack",
        "Ring of Sol",
        "Thran Dynamo",
    ]


def test_a_multi_word_query_reaches_rank_two_before_rank_three() -> None:
    script = """
const S = require('./search.js');
const cards = [
  {name: 'Awesol Ring Pack', type_line: 'Artifact', text: ''},
  {name: 'Zealous Sol Ringer', type_line: 'Creature', text: ''},
];
console.log(JSON.stringify([cards.map(c => S.rank(c, 'sol r')), S.sortByRank(cards, 'sol r').map(c => c.name)]));
"""
    ranks, names = json.loads(_node(script))
    assert ranks == [3, 2]
    assert names == ["Zealous Sol Ringer", "Awesol Ring Pack"]  # alphabetical order would differ


def test_pages_load_the_shared_files_and_keep_inline_code_out() -> None:
    from commander_lab.studio.web import STATIC

    for page in ("index.html", "tierliste.html", "partie.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert 'src="ui.js"' in html and 'id="areas"' in html and 'id="theme-toggle"' in html
        assert "Deckbau" in html and "Tierliste" in html and "Partien" in html
    assert 'src="search.js"' in (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="data-state"' in (STATIC / "tierliste.html").read_text(encoding="utf-8")
    for script in ("ui.js", "search.js"):
        source = (STATIC / script).read_text(encoding="utf-8")
        assert "innerHTML" not in source and "style=" not in source
