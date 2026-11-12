"""Strength index of the tier list: signal import, Wilson bound, percentile ranks, tiers.

All data here is synthetic. The index is an estimate from usage signals; the Owner's marks
never enter it, and the figures of two commanders are never combined.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, signals, strength, strength_view
from commander_lab.studio.strength import Observation, StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_universe_web import _deck

HEADER = {"X-Studio": "1"}
COMMANDER = "Test Commander"
OTHER = "Other Commander"
PLAYER = "Zed Playerson"
CARDS = [f"Filler {index:02d}" for index in range(10)]


def _write(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _commander_rows(
    commander: str, decks: dict[str, int], potential: int, **extra: object
) -> list[dict[str, object]]:
    return [
        {
            "commander_name": commander,
            "card_name": name,
            "num_decks": count,
            "potential_decks": potential,
            "synergy": "" if name == "Filler 00" else 0.01 * index,
            "lift": 1.0,
            **extra,
        }
        for index, (name, count) in enumerate(decks.items())
    ]


CARD_FIELDS = ["commander_name", "card_name", "num_decks", "potential_decks", "synergy", "lift"]
BRACKET_FIELDS = [*CARD_FIELDS, "variant"]


def _write_signals(folder: Path) -> None:
    """Filler 09 is listed nowhere (a missing observation); Filler 00 has no synergy."""
    folder.mkdir()
    inclusion = {name: 90 - 10 * index for index, name in enumerate(CARDS[:9])}
    rows = _commander_rows(COMMANDER, inclusion, 100)
    # The same card under a second heading of the page: the first row is kept.
    rows.append({**rows[0], "num_decks": 1})
    rows += _commander_rows(OTHER, {"Filler 00": 1, "Filler 08": 9}, 10)
    _write(folder / "commander_card_signals_1.csv", rows[:5], CARD_FIELDS)
    _write(folder / "commander_card_signals_2.csv", rows[5:], CARD_FIELDS)
    core = {name: 5 + index for index, name in enumerate(CARDS[:9])}
    cedh = {name: 5 + (8 - index) for index, name in enumerate(CARDS[:9])}
    for variant, counts in (("core", core), ("cedh", cedh)):
        brackets = _commander_rows(COMMANDER, counts, 50, variant=variant, bracket=2)
        _write(folder / f"commander_bracket_signals_{variant}_1.csv", brackets, BRACKET_FIELDS)
    global_rows = [
        {
            "card_name": name,
            "fetch_status": "PARTIAL" if name == "Filler 03" else "AVAILABLE",
            "num_decks": 1000 * (index + 1),
            "potential_decks": 100000,
            "price_cardmarket": 9.99,
        }
        for index, name in enumerate(CARDS)
    ]
    _write(
        folder / "card_global_signals.csv",
        global_rows,
        ["card_name", "fetch_status", "num_decks", "potential_decks", "price_cardmarket"],
    )
    links = [
        {
            "card_name": name,
            "fetch_status": "AVAILABLE",
            "variant_count": index,
            "partners_in_collection": index // 2,
        }
        for index, name in enumerate(CARDS)
    ]
    _write(
        folder / "spellbook_card_links.csv",
        links,
        ["card_name", "fetch_status", "variant_count", "partners_in_collection"],
    )
    lists = []
    for tournament, date, player, others in (
        ("Cup A", "2026-10-01", PLAYER, ["Filler 00", "Filler 01"]),
        ("Cup A", "2026-10-01", "Second Person", ["Filler 00"]),
        ("Cup B", "2026-10-08", "Third Person", ["Filler 00", "Filler 02"]),
    ):
        lists.append(_list_row(tournament, date, player, COMMANDER, "commander"))
        lists += [_list_row(tournament, date, player, card, "main") for card in others]
        lists.append(_list_row(tournament, date, player, "Sideboard Card", "sideboard"))
    lists.append(_list_row("Cup C", "2026-10-09", "Fourth Person", OTHER, "commander"))
    lists.append(_list_row("Cup C", "2026-10-09", "Fourth Person", "Filler 05", "main"))
    _write(
        folder / "topdeck_chulane_decks.csv",
        lists,
        [
            "tournament",
            "date",
            "player",
            "wins",
            "draws",
            "losses",
            "card_name",
            "quantity",
            "section",
        ],
    )


def _list_row(
    tournament: str, date: str, player: str, card: str, section: str
) -> dict[str, object]:
    return {
        "tournament": tournament,
        "date": date,
        "player": player,
        "wins": 1,
        "draws": 0,
        "losses": 1,
        "card_name": card,
        "quantity": 1,
        "section": section,
    }


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_signals(tmp_path / "signals")
    yield opened
    opened.close()


def _import(store: StudioStore, tmp_path: Path) -> dict[str, object]:
    return signals.import_signals(store, tmp_path / "signals", commander=COMMANDER)


def _signal(
    store: StudioStore, signal: str, card: str, commander: str = COMMANDER
) -> sqlite3.Row | None:
    return store.connection.execute(  # type: ignore[no-any-return]
        "SELECT * FROM card_signal WHERE commander_name = ? AND signal = ? AND card_name = ?",
        (commander, signal, card),
    ).fetchone()


def _by_name(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def _component(card: strength_view.StrengthCard, name: str) -> strength.ComponentResult:
    return next(item for item in card["components"] if item["component"] == name)


# ---------- importer ----------


def test_import_reads_split_parts_and_reports_every_file(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    files = report["files"]
    assert isinstance(files, dict)
    card_file = files[signals.CARD_FILE]
    assert card_file["parts"] == ["commander_card_signals_1.csv", "commander_card_signals_2.csv"]
    assert card_file["rows_read"] == 12  # 9 + the duplicate heading + 2 of the other commander
    assert card_file["skipped_reasons"] == {"DUPLICATE_CONFLICT": 1, "DUPLICATE_SAME_FIGURES": 2}
    assert files[f"{signals.BRACKET_FILE}_upgraded"]["status"] == "ABSENT"
    assert files[signals.GLOBAL_FILE]["skipped_reasons"] == {"FETCH_STATUS_NOT_AVAILABLE": 1}
    first = _signal(store, signals.SIGNAL_INCLUSION, "Filler 00")
    assert first is not None
    assert (first["numerator"], first["denominator"], first["value"]) == (90, 100, 0.9)
    assert store.count("source") >= 1
    assert first["source_id"].startswith("src:")


def test_unpublished_values_stay_unknown_never_zero(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    synergy = _signal(store, signals.SIGNAL_SYNERGY, "Filler 00")
    assert synergy is not None and synergy["value"] is None
    # A card that no source lists has no row at all; PARTIAL global rows are not stored.
    assert _signal(store, signals.SIGNAL_INCLUSION, "Filler 09") is None
    assert _signal(store, signals.SIGNAL_GLOBAL, "Filler 03", commander="") is None
    assert _signal(store, signals.SIGNAL_GLOBAL, "Filler 04", commander="") is not None


def test_no_player_name_and_no_price_is_stored(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    db = store.connection
    tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    for table in tables:
        for column in db.execute(f'PRAGMA table_info("{table}")').fetchall():
            for (value,) in db.execute(f'SELECT "{column[1]}" FROM "{table}"'):
                assert not isinstance(value, str) or PLAYER not in value
    assert {row[0] for row in db.execute("SELECT DISTINCT signal FROM card_signal")} >= {
        "tournament_lists",
        "edhrec_global_inclusion",
    }
    assert not any("price" in str(row[0]) for row in db.execute("SELECT signal FROM card_signal"))
    assert store.path is not None
    assert PLAYER.encode() not in store.path.read_bytes()


def test_tournament_lists_are_counted_per_list_for_their_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    row = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 00")
    assert row is not None and (row["numerator"], row["denominator"]) == (3, 3)
    single = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 01")
    assert single is not None and (single["numerator"], single["denominator"]) == (1, 3)
    assert _signal(store, signals.SIGNAL_TOURNAMENT, "Sideboard Card") is None
    assert _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 05") is None  # other commander
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.TOURNAMENT_FILE]["skipped_reasons"]["LIST_OF_OTHER_COMMANDER"] == 1


def test_import_is_idempotent(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    before = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    sources = store.count("source")
    _import(store, tmp_path)
    after = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    assert [tuple(row) for row in before] == [tuple(row) for row in after]
    assert store.count("source") == sources
    assert store.count("card_signal") == len(before)


def test_import_rejects_a_file_without_its_columns(store: StudioStore, tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    _write(broken / "spellbook_card_links.csv", [{"card_name": "x"}], ["card_name"])
    with pytest.raises(ValueError, match="missing column"):
        signals.import_signals(store, broken, commander=COMMANDER)


# ---------- pure scoring ----------


def test_wilson_lower_bound_matches_a_hand_calculation() -> None:
    # n = 10, k = 5: (0.5 + 3.8416/20 - 1.96 * sqrt(0.025 + 3.8416/400)) / (1 + 0.38416)
    bound = strength.wilson_lower(5, 10)
    assert bound is not None and bound == pytest.approx(0.2366, abs=5e-4)
    assert strength.wilson_lower(0, 10) == 0.0
    assert strength.wilson_lower(1, 0) is None
    small, large = strength.wilson_lower(1, 1), strength.wilson_lower(50, 100)
    assert small is not None and large is not None and small < large  # a tiny sample ranks lower


def test_percentile_ranks_share_the_mean_rank_on_ties() -> None:
    ranks = strength.percentile_ranks({"a": 1.0, "b": 2.0, "c": 2.0, "d": 3.0})
    assert ranks == {"a": 0.0, "b": 0.5, "c": 0.5, "d": 1.0}
    assert strength.percentile_ranks({"only": 7.0}) == {"only": 0.5}


def _share(taken: int, of: int) -> Observation:
    return Observation(taken / of, taken, of)


def test_missing_components_renormalise_the_weights_and_lower_coverage() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS}
        | {strength.COMMANDER_INCLUSION: 3.0, strength.SYNERGY: 1.0},
        min_coverage=0.0,
        min_components=1,
    )
    observations = {
        "a": {"commander_inclusion": _share(900, 1000), "synergy": Observation(0.2)},
        "b": {"commander_inclusion": _share(500, 1000)},
        "c": {"commander_inclusion": _share(100, 1000), "synergy": Observation(0.1)},
    }
    scored = strength.score_pool(
        settings, observations, {strength.COMMANDER_INCLUSION, strength.SYNERGY}
    )
    assert scored["a"]["index"] == 100.0 and scored["a"]["coverage"] == 1.0
    assert scored["b"]["index"] == 50.0  # only its own component, weights renormalised
    assert scored["b"]["coverage"] == 0.75
    assert scored["c"]["index"] == 0.0
    synergy = next(c for c in scored["b"]["components"] if c["component"] == "synergy")
    assert synergy["status"] == strength.NO_VALUE and synergy["percentile"] is None
    simulation = next(c for c in scored["b"]["components"] if c["component"] == "simulation")
    assert simulation["status"] == strength.NOT_COLLECTED


def test_low_coverage_or_few_components_give_tier_u_not_a_weak_tier() -> None:
    weights = {name: 0.0 for name in strength.COMPONENTS}
    weights |= {strength.COMMANDER_INCLUSION: 3.0, strength.SYNERGY: 1.0}
    observations = {
        "a": {"commander_inclusion": _share(900, 1000), "synergy": Observation(0.2)},
        "b": {"commander_inclusion": _share(500, 1000)},
        "c": {"commander_inclusion": _share(100, 1000), "synergy": Observation(0.1)},
    }
    collected = {strength.COMMANDER_INCLUSION, strength.SYNERGY}
    lax = StrengthSettings(weights=weights, min_coverage=0.5, min_components=1)
    assert strength.score_pool(lax, observations, collected)["b"]["tier"] == "C"
    strict_coverage = StrengthSettings(weights=weights, min_coverage=0.8, min_components=1)
    result = strength.score_pool(strict_coverage, observations, collected)["b"]
    assert result["tier"] == "U" and result["index"] == 50.0
    strict_count = StrengthSettings(weights=weights, min_coverage=0.0, min_components=2)
    assert strength.score_pool(strict_count, observations, collected)["b"]["tier"] == "U"
    assert strength.score_pool(strict_count, observations, collected)["a"]["tier"] == "S"
    assert strength.score_pool(strict_count, observations, collected)["c"]["tier"] == "D"


def test_settings_are_validated_and_round_trip() -> None:
    settings = StrengthSettings.from_dict({"weights": {"synergy": 4}, "bracket": "cedh"})
    assert StrengthSettings.from_dict(settings.to_dict()) == settings
    for bad in (
        {"weights": {"salt": 1}},
        {"weights": {"synergy": -1}},
        {"weights": {"synergy": True}},
        {"bracket": "bracket 9"},
        {"min_coverage": 2},
        {"min_components": 1.5},
        {"tier_cuts": {"S": 50, "A": 60, "B": 40, "C": 30}},
        {"unknown": 1},
    ):
        with pytest.raises(ValueError):
            StrengthSettings.from_dict(bad)
    assert set(strength.PRESETS) == {"Ausgewogen", "Commander-nah", "Turniernah"}
    assert strength.PRESETS["Commander-nah"].weights[strength.GLOBAL_INCLUSION] == 0.0
    assert strength.PRESETS["Turniernah"].bracket == "cedh"


# ---------- store side ----------


def test_missing_card_lowers_coverage_not_the_percentile(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    cards = _by_name(strength_view.compute(store, COMMANDER, StrengthSettings()))
    absent = _component(cards["Filler 09"], "commander_inclusion")
    assert absent["status"] == strength.NO_VALUE and absent["percentile"] is None
    listed = _component(cards["Filler 08"], "commander_inclusion")
    assert listed["status"] == strength.PRESENT and listed["percentile"] == 0.0
    assert listed["wilson"] is not None and listed["numerator"] == 10
    assert cards["Filler 09"]["coverage"] < cards["Filler 00"]["coverage"]
    assert _component(cards["Filler 00"], "synergy")["status"] == strength.NO_VALUE
    assert _component(cards["Filler 00"], "deck_universe")["status"] == strength.NOT_COLLECTED


def test_bracket_choice_changes_the_result(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    only_bracket = {name: 0.0 for name in strength.COMPONENTS} | {strength.BRACKET_INCLUSION: 1.0}

    def index(bracket: str) -> dict[str, float | None]:
        settings = StrengthSettings(
            weights=only_bracket, bracket=bracket, min_coverage=0.0, min_components=1
        )
        return {
            n: c["index"]
            for n, c in _by_name(strength_view.compute(store, COMMANDER, settings)).items()
        }

    core, cedh = index("core"), index("cedh")
    assert core["Filler 08"] == 100.0 and cedh["Filler 08"] == 0.0
    assert core["Filler 00"] == 0.0 and cedh["Filler 00"] == 100.0
    assert index("upgraded")["Filler 08"] is None  # no upgraded file imported: no value
    none = strength_view.compute(
        store, COMMANDER, StrengthSettings(bracket="none", min_coverage=0.0, min_components=1)
    )
    names = [item["component"] for item in none["cards"][0]["components"]]
    assert "bracket_inclusion" not in names


def test_marks_never_change_the_index(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    before = strength_view.compute(store, COMMANDER, StrengthSettings())
    pool = builder.pool_cards(store, [COMMANDER])["cards"]
    assert isinstance(pool, list)
    for card in pool[:6]:
        builder.set_mark(
            store, str(card["card_id"]), favorite=True, excluded=True, note="mein Liebling"
        )
    after = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert before == after


def test_two_commanders_never_share_figures(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    other = _signal(store, signals.SIGNAL_INCLUSION, "Filler 00", commander=OTHER)
    assert other is not None and (other["numerator"], other["denominator"]) == (1, 10)
    cards = _by_name(strength_view.compute(store, COMMANDER, StrengthSettings()))
    own = _component(cards["Filler 00"], "commander_inclusion")
    assert (own["numerator"], own["denominator"]) == (90, 100)
    store.connection.execute("DELETE FROM card_signal WHERE commander_name = ?", (OTHER,))
    store.connection.commit()
    assert _by_name(strength_view.compute(store, COMMANDER, StrengthSettings())) == cards
    # Another commander without any signal row has nothing collected.
    store.connection.execute(
        "UPDATE card_signal SET commander_name = ? WHERE commander_name = ? AND signal != ?",
        ("Nobody", COMMANDER, signals.SIGNAL_GLOBAL),
    )
    store.connection.commit()
    empty = _by_name(strength_view.compute(store, COMMANDER, StrengthSettings()))
    assert _component(empty["Filler 00"], "commander_inclusion")["status"] == strength.NOT_COLLECTED


def test_deck_list_universe_is_a_counted_component(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    for index in range(10):
        _deck(store, f"s{index}", "edhrec", 3, ["Filler 01"] + (["Filler 02"] if index < 3 else []))
    store.connection.commit()
    from commander_lab.studio import universe

    universe.save_profile(store, "alle", {})
    settings = StrengthSettings(universe_profile="alle")
    result = strength_view.compute(store, COMMANDER, settings)
    cards = _by_name(result)
    one = _component(cards["Filler 01"], "deck_universe")
    two = _component(cards["Filler 02"], "deck_universe")
    assert one["status"] == strength.PRESENT and one["denominator"] == two["denominator"]
    assert two["numerator"] == 3 and one["percentile"] == 1.0 and two["percentile"] == 0.0
    assert result["universe"] is not None
    assert _component(cards["Filler 05"], "deck_universe")["status"] == strength.NO_VALUE
    with pytest.raises(KeyError):
        strength_view.compute(store, COMMANDER, StrengthSettings(universe_profile="gibt es nicht"))


# ---------- web ----------


@pytest.fixture
def client(store: StudioStore, tmp_path: Path) -> Iterator[TestClient]:
    _import(store, tmp_path)
    store.close()
    with TestClient(create_app(tmp_path / "studio")) as test_client:
        yield test_client


def test_strength_needs_a_commander_and_the_marker(client: TestClient) -> None:
    assert client.post("/api/strength", json={}, headers=HEADER).status_code == 422
    assert client.post("/api/strength", json={"commander": ""}, headers=HEADER).status_code == 422
    assert client.post("/api/strength", json={"commander": COMMANDER}).status_code == 403
    assert client.put("/api/strength/profiles/x", json={"settings": {}}).status_code == 403


def test_strength_route_sources_and_errors(client: TestClient) -> None:
    answer = client.post("/api/strength", json={"commander": COMMANDER}, headers=HEADER)
    assert answer.status_code == 200
    body = answer.json()
    assert (
        body["data_class"] == "DERIVED_DESCRIPTIVE"
        and "keine gemessene Siegrate" in body["meaning"]
    )
    assert body["commander"] == COMMANDER and sum(body["tier_counts"].values()) == len(
        body["cards"]
    )
    preset = client.post(
        "/api/strength", json={"commander": COMMANDER, "preset": "Turniernah"}, headers=HEADER
    )
    assert preset.json()["settings"]["bracket"] == "cedh"
    post = client.post
    both = post(
        "/api/strength",
        json={"commander": COMMANDER, "preset": "Turniernah", "settings": {}},
        headers=HEADER,
    )
    assert both.status_code == 422
    bad = post(
        "/api/strength", json={"commander": COMMANDER, "settings": {"bracket": "x"}}, headers=HEADER
    )
    assert bad.status_code == 422
    unknown = post("/api/strength", json={"commander": COMMANDER, "preset": "Nope"}, headers=HEADER)
    assert unknown.status_code == 404
    other = post("/api/strength", json={"commander": "Not In Collection"}, headers=HEADER)
    assert other.status_code == 404
    universe = post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": {"universe_profile": "x"}},
        headers=HEADER,
    )
    assert universe.status_code == 404


def test_presets_and_profile_round_trip(client: TestClient) -> None:
    presets = client.get("/api/strength/presets").json()
    assert [item["name"] for item in presets["presets"]] == [
        "Ausgewogen",
        "Commander-nah",
        "Turniernah",
    ]
    assert [item["key"] for item in presets["components"]] == list(strength.COMPONENTS)
    assert client.get("/api/strength/profiles").json() == []
    assert client.get("/api/strength/profiles/mein").status_code == 404
    saved = client.put(
        "/api/strength/profiles/mein",
        json={"settings": {"weights": {"synergy": 5}, "bracket": "cedh", "min_coverage": 0.2}},
        headers=HEADER,
    )
    assert saved.status_code == 200
    assert saved.json()["settings"]["weights"]["synergy"] == 5.0
    assert client.get("/api/strength/profiles/mein").json()["settings"]["bracket"] == "cedh"
    listed = client.get("/api/strength/profiles").json()
    assert [item["name"] for item in listed] == ["mein"]
    computed = client.post(
        "/api/strength", json={"commander": COMMANDER, "profile": "mein"}, headers=HEADER
    ).json()
    assert computed["settings"]["min_coverage"] == 0.2
    invalid = client.put(
        "/api/strength/profiles/schlecht",
        json={"settings": {"weights": {"synergy": -3}}},
        headers=HEADER,
    )
    assert invalid.status_code == 422
    assert client.delete("/api/strength/profiles/mein", headers=HEADER).status_code == 200
    assert client.delete("/api/strength/profiles/mein", headers=HEADER).status_code == 404
    assert client.get("/api/strength/profiles").json() == []
