"""Strength index of the tier list: signal import, Wilson bound, percentile ranks, tiers.

All data here is synthetic. The index is an estimate from usage signals; the Owner's marks
never enter it, and the figures of two commanders are never combined.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, signals, strength, strength_view
from commander_lab.studio.store import DataClass
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings
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
BRACKET_FIELDS = [*CARD_FIELDS, "variant", "bracket"]


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
    # The duplicate heading row yields one conflicting (inclusion) and one identical
    # (synergy) pair; a third pair (lift) is no longer produced.
    assert card_file["skipped_reasons"] == {"DUPLICATE_CONFLICT": 1, "DUPLICATE_SAME_FIGURES": 1}
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


def test_import_stores_no_dead_signals(store: StudioStore, tmp_path: Path) -> None:
    # The fixture files still carry the lift column (as the real dataset files do); the
    # importer must ignore it, because no strength component reads it. The spellbook
    # file's partners_in_collection column IS stored since #1261 P3.7: the combos
    # component reads it as one of its quality parts. The fixture carries no
    # variant_ids column, so no two-card rows are stored for it.
    report = _import(store, tmp_path)
    stored = {row[0] for row in store.connection.execute("SELECT DISTINCT signal FROM card_signal")}
    assert stored == {
        "edhrec_commander_inclusion",
        "edhrec_commander_synergy",
        "edhrec_bracket_inclusion:core",
        "edhrec_bracket_inclusion:cedh",
        "edhrec_global_inclusion",
        "spellbook_variants",
        "spellbook_partners_in_collection",
        "tournament_lists",
    }
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.CARD_FILE]["rows_written"] == 22  # 11 cards x inclusion + synergy
    assert files[signals.SPELLBOOK_FILE]["rows_written"] == 20  # variants + partners


def test_import_does_not_require_the_dead_columns(store: StudioStore, tmp_path: Path) -> None:
    lean = tmp_path / "lean"
    lean.mkdir()
    _write(
        lean / "commander_card_signals.csv",
        [
            {
                "commander_name": COMMANDER,
                "card_name": "Filler 00",
                "num_decks": 5,
                "potential_decks": 10,
                "synergy": 0.5,
            }
        ],
        ["commander_name", "card_name", "num_decks", "potential_decks", "synergy"],
    )
    _write(
        lean / "spellbook_card_links.csv",
        [{"card_name": "Filler 00", "fetch_status": "AVAILABLE", "variant_count": 3}],
        ["card_name", "fetch_status", "variant_count"],
    )
    report = signals.import_signals(store, lean, commander=COMMANDER)
    assert report["rows_written"] == 3
    assert _signal(store, signals.SIGNAL_VARIANTS, "Filler 00", commander="") is not None


# ---------- pure scoring ----------


def test_wilson_lower_bound_matches_a_hand_calculation() -> None:
    # n = 10, k = 5: (0.5 + 3.8416/20 - 1.96 * sqrt(0.025 + 3.8416/400)) / (1 + 0.38416)
    bound = strength.wilson_lower(5, 10)
    assert bound is not None and bound == pytest.approx(0.2366, abs=5e-4)
    assert strength.wilson_lower(0, 10) == 0.0
    assert strength.wilson_lower(1, 0) is None
    # (the old assertion "a tiny sample ranks lower" proved nothing about protection: it is
    # replaced by the tests of the minimum denominator and of the shared denominator below)


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
    assert strength.PRESETS["Ausgewogen"] == StrengthSettings()
    near = strength.PRESETS["Commander-nah"]
    assert near.weights == {
        strength.COMMANDER_INCLUSION: 3.0,
        strength.BRACKET_INCLUSION: 2.0,
        strength.DECK_UNIVERSE: 3.0,
        strength.SYNERGY: 2.0,
        strength.TOURNAMENT_LISTS: 1.0,
        strength.TOURNAMENT_CONVERSION: 1.0,
        strength.GLOBAL_INCLUSION: 1.0,
        strength.COMBOS: 0.0,
        strength.PLAYGROUP_OBSERVED: 0.0,
        strength.SIMULATION: 0.0,
    }
    tournament = strength.PRESETS["Turniernah"]
    assert tournament.bracket == "cedh"
    assert tournament.weights == {
        strength.TOURNAMENT_LISTS: 3.0,
        strength.BRACKET_INCLUSION: 2.0,
        strength.DECK_UNIVERSE: 2.0,
        strength.COMMANDER_INCLUSION: 1.0,
        strength.SYNERGY: 0.0,
        strength.TOURNAMENT_CONVERSION: 1.0,
        strength.GLOBAL_INCLUSION: 1.0,
        strength.COMBOS: 1.0,
        strength.PLAYGROUP_OBSERVED: 1.0,
        strength.SIMULATION: 0.0,
    }
    assert strength.DEFAULT_WEIGHTS[strength.PLAYGROUP_OBSERVED] == 1.0
    # The Playgroup observation is commander independent: it never satisfies the rule
    # "require_commander_signal" and is not in the set of commander-specific components.
    assert strength.PLAYGROUP_OBSERVED not in strength.COMMANDER_SPECIFIC
    # Every preset keeps the deck universe, the most commander-specific source, in the index.
    for name, preset in strength.PRESETS.items():
        assert preset.weights[strength.DECK_UNIVERSE] > 0, name


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

    # Changed with the minimum-denominator rule (Refs #1205): ten decks are below the
    # default minimum universe of 30, so this test names the minimum it counts with.
    universe.save_profile(store, "alle", {"min_universe": 10})
    settings = StrengthSettings(universe_profile="alle")
    result = strength_view.compute(store, COMMANDER, settings)
    cards = _by_name(result)
    one = _component(cards["Filler 01"], "deck_universe")
    two = _component(cards["Filler 02"], "deck_universe")
    assert one["status"] == strength.PRESENT and one["denominator"] == two["denominator"]
    assert two["numerator"] == 3 and one["percentile"] == 1.0 and two["percentile"] < 1.0
    assert result["universe"] is not None
    # Filler 05 is in none of the complete deck lists of the universe: a counted zero (0 of N), ranked
    # below every listed card (ties share the mean rank) and labelled as counted.
    zero = _component(cards["Filler 05"], "deck_universe")
    assert zero["status"] == strength.ZERO_COUNT and zero["percentile"] < two["percentile"]
    assert (zero["numerator"], zero["denominator"]) == (0, one["denominator"])
    assert "gezählt" in zero["note"]
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


def test_tier_list_page_has_the_strength_panel_without_inline_code() -> None:
    from commander_lab.studio.web import STATIC

    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert 'id="strength-panel"' in html and "<script>" not in html and "style=" not in html
    assert "innerHTML" not in script and "/api/strength" in script
    assert "zu wenig Daten" in script and "keine gemessene Siegrate" in script


# ---------- review of the merged tier list (Refs #1205) ----------


def _only(*components: str, **extra: object) -> StrengthSettings:
    weights = {name: 0.0 for name in strength.COMPONENTS} | {name: 1.0 for name in components}
    return StrengthSettings(weights=weights, min_coverage=0.0, min_components=1, **extra)  # type: ignore[arg-type]


def _row(card: dict[str, strength.CardStrength], key: str, name: str) -> strength.ComponentResult:
    return next(item for item in card[key]["components"] if item["component"] == name)


def test_wilson_is_exactly_zero_without_successes_and_keeps_the_order_of_one_denominator() -> None:
    for denominator in (1, 3, 10, 755, 10**6):
        assert strength.wilson_lower(0, denominator) == 0.0
    bounds = [strength.wilson_lower(k, 40) for k in range(41)]
    assert all(a is not None and b is not None and a < b for a, b in pairwise(bounds))
    # Wilson reorders only across denominators: 1 of 1 sits below 50 of 100
    one, fifty = strength.wilson_lower(1, 1), strength.wilson_lower(50, 100)
    assert one is not None and fifty is not None and one < fifty


def test_without_a_minimum_three_lists_still_spread_percentiles_over_zero_to_one() -> None:
    """The reviewed defect: one shared denominator, so Wilson cannot protect."""
    observations = {
        key: {"tournament_lists": Observation(n / 3, n, 3)}
        for key, n in (("a", 3), ("b", 2), ("c", 1), ("d", 1))
    }
    open_settings = _only("tournament_lists", min_denominators={"edhrec": 30, "tournament": 0})
    scored = strength.score_pool(open_settings, observations, {"tournament_lists"})
    assert scored["a"]["index"] == 100.0 and scored["c"]["index"] == 16.7  # spread from 3 lists
    guarded = strength.score_pool(_only("tournament_lists"), observations, {"tournament_lists"})
    for card in observations:
        row = _row(guarded, card, "tournament_lists")
        assert row["status"] == strength.NO_VALUE and row["percentile"] is None
        assert row["reason"] == strength.BELOW_MIN_DENOMINATOR
        assert "Mindest-Nenner 5" in row["note"] and "Nenner 3" in row["note"]
        assert guarded[card]["index"] is None and guarded[card]["tier"] == "U"


def test_below_minimum_is_the_reason_for_every_card_even_an_unlisted_one() -> None:
    observations = {
        "a": {"commander_inclusion": Observation(20 / 25, 20, 25)},
        "b": {},
    }
    scored = strength.score_pool(
        _only("commander_inclusion"), observations, {"commander_inclusion"}
    )
    assert {_row(scored, key, "commander_inclusion")["reason"] for key in "ab"} == {
        strength.BELOW_MIN_DENOMINATOR
    }
    enough = {"a": {"commander_inclusion": Observation(0.8, 24, 30)}, "b": {}}
    scored = strength.score_pool(_only("commander_inclusion"), enough, {"commander_inclusion"})
    assert _row(scored, "a", "commander_inclusion")["status"] == strength.PRESENT
    assert _row(scored, "b", "commander_inclusion")["reason"] == strength.NOT_LISTED


def test_the_deck_universe_minimum_comes_from_the_profile() -> None:
    observations = {"a": {"deck_universe": _share(8, 10)}, "b": {"deck_universe": _share(2, 10)}}
    settings = _only("deck_universe")
    low = strength.score_pool(
        settings, observations, {"deck_universe"}, context=PoolContext(universe_minimum=30)
    )
    assert _row(low, "a", "deck_universe")["reason"] == strength.BELOW_MIN_DENOMINATOR
    assert _row(low, "a", "deck_universe")["min_denominator"] == 30
    ok = strength.score_pool(
        settings, observations, {"deck_universe"}, context=PoolContext(universe_minimum=10)
    )
    assert _row(ok, "a", "deck_universe")["status"] == strength.PRESENT


def _grouped(
    count_type_a: int, count_type_b: int
) -> tuple[dict[str, dict[str, Observation]], PoolContext]:
    observations: dict[str, dict[str, Observation]] = {}
    groups: dict[str, str] = {}
    for index in range(count_type_a):
        observations[f"a{index}"] = {"synergy": Observation(float(index))}
        groups[f"a{index}"] = "Creature"
    for index in range(count_type_b):
        observations[f"b{index}"] = {"synergy": Observation(100.0 + index)}
        groups[f"b{index}"] = "Instant"
    return observations, PoolContext(type_group=groups, mana_band=groups)


def test_percentiles_are_taken_within_the_chosen_group_with_a_pool_fallback() -> None:
    observations, context = _grouped(6, 3)
    pool = strength.score_pool(_only("synergy"), observations, {"synergy"}, context=context)
    typed = strength.score_pool(
        _only("synergy", rank_group="type"), observations, {"synergy"}, context=context
    )
    # in the pool every Instant outranks every Creature; within the type the best Creature is 1.0
    assert _row(pool, "a5", "synergy")["percentile"] < 0.7
    assert _row(typed, "a5", "synergy")["percentile"] == 1.0
    assert _row(typed, "a5", "synergy")["group"] == "Creature"
    assert _row(typed, "a5", "synergy")["group_size"] == 6
    # three Instants are fewer than five: they keep their pool rank and the row says so
    fallback = _row(typed, "b2", "synergy")
    assert fallback["group_fallback"] is True and fallback["reason"] == strength.GROUP_TOO_SMALL
    assert fallback["percentile"] == _row(pool, "b2", "synergy")["percentile"]
    assert "weniger als 5" in fallback["note"] and "ganzen Pool" in fallback["note"]
    banded = strength.score_pool(
        _only("synergy", rank_group="mana_band"), observations, {"synergy"}, context=context
    )
    assert _row(banded, "a5", "synergy")["percentile"] == 1.0


def _function_grouped() -> tuple[dict[str, dict[str, Observation]], PoolContext]:
    observations: dict[str, dict[str, Observation]] = {}
    groups: dict[str, tuple[str, ...]] = {}
    for index in range(6):
        observations[f"r{index}"] = {"synergy": Observation(float(index))}
        groups[f"r{index}"] = ("ramp",)
    for index in range(6):
        observations[f"d{index}"] = {"synergy": Observation(100.0 + index)}
        groups[f"d{index}"] = ("card_draw",)
    # one card in both groups: midfield among the ramp cards, last among the draw cards
    observations["both"] = {"synergy": Observation(2.5)}
    groups["both"] = ("ramp", "card_draw")
    # a role with too few valued cards, and a card without any role
    for index in range(3):
        observations[f"f{index}"] = {"synergy": Observation(200.0 + index)}
        groups[f"f{index}"] = ("flicker",)
    observations["none"] = {"synergy": Observation(50.0)}
    return observations, PoolContext(function_group=groups)


def test_percentiles_are_taken_within_the_function_groups() -> None:
    observations, context = _function_grouped()
    pool = strength.score_pool(_only("synergy"), observations, {"synergy"}, context=context)
    func = strength.score_pool(
        _only("synergy", rank_group="function"), observations, {"synergy"}, context=context
    )
    # one role: ranked inside the role group only (seven cards: the six and "both")
    row = _row(func, "r5", "synergy")
    assert row["percentile"] == 1.0 and row["group"] == "ramp" and row["group_size"] == 7
    assert _row(func, "r0", "synergy")["percentile"] == 0.0
    assert _row(func, "d5", "synergy")["group"] == "card_draw"
    # several roles: the rank is the mean of the ranks in its role groups, all of them named
    both = _row(func, "both", "synergy")
    assert both["percentile"] == 0.25
    assert both["group"] == "ramp + card_draw" and both["group_size"] is None
    # a role group below the minimum keeps the pool rank and the row says so
    small = _row(func, "f1", "synergy")
    assert small["group_fallback"] is True and small["reason"] == strength.GROUP_TOO_SMALL
    assert small["group"] == "flicker" and "nur 3 Karten mit Wert" in small["note"]
    assert small["percentile"] == _row(pool, "f1", "synergy")["percentile"]
    # no role at all: pool rank, named as an unknown function, never as a group of its own
    unknown = _row(func, "none", "synergy")
    assert unknown["group_fallback"] is True and unknown["group"] is None
    assert "Keine Funktion bekannt" in unknown["note"]
    assert unknown["percentile"] == _row(pool, "none", "synergy")["percentile"]


def test_function_is_a_rank_group_setting() -> None:
    settings = StrengthSettings.from_dict({"rank_group": "function"})
    assert settings.rank_group == strength.GROUP_FUNCTION == "function"
    assert StrengthSettings.from_dict(settings.to_dict()) == settings
    assert StrengthSettings().rank_group == "pool"  # the recommendation stays the pool


def test_mana_value_bands_and_lands() -> None:
    bands = [strength.mana_band(value, is_land=False) for value in (0, 1, 2, 3, 4, 5, 9)]
    assert bands == ["0-1", "0-1", "2", "3", "4", "5+", "5+"]
    assert strength.mana_band(3, is_land=True) == "Land"
    assert strength.mana_band(None, is_land=False) == "unbekannt"  # unknown, never band 0


def test_raw_share_and_wilson_differ_across_denominators() -> None:
    observations = {
        "tiny": {"deck_universe": Observation(1.0, 1, 1)},
        "big": {"deck_universe": Observation(0.5, 50, 100)},
    }
    context = PoolContext(universe_minimum=0)
    wilson = strength.score_pool(
        _only("deck_universe"), observations, {"deck_universe"}, context=context
    )
    raw = strength.score_pool(
        _only("deck_universe", share_measure="raw"),
        observations,
        {"deck_universe"},
        context=context,
    )
    assert wilson["big"]["index"] == 100.0 and wilson["tiny"]["index"] == 0.0
    assert raw["tiny"]["index"] == 100.0 and raw["big"]["index"] == 0.0
    assert _row(raw, "big", "deck_universe")["wilson"] is None
    assert _row(wilson, "big", "deck_universe")["wilson"] is not None


def test_missing_as_lowest_is_a_setting_for_three_signals_and_named_in_the_row() -> None:
    observations = {
        "a": {"commander_inclusion": Observation(0.9, 900, 1000)},
        "b": {"commander_inclusion": Observation(0.1, 100, 1000)},
        "c": {},
    }
    collected = {"commander_inclusion"}
    default = strength.score_pool(_only("commander_inclusion"), observations, collected)
    assert _row(default, "c", "commander_inclusion")["status"] == strength.NO_VALUE
    assert default["c"]["index"] is None  # absent is a missing observation (B5)
    lowest = strength.score_pool(
        _only("commander_inclusion", missing_value={"commander_inclusion": "lowest"}),
        observations,
        collected,
    )
    row = _row(lowest, "c", "commander_inclusion")
    assert row["status"] == strength.MISSING_AS_LOWEST and row["percentile"] == 0.0
    assert row["note"] == "nicht gelistet, als niedrigster Rang gezählt (Einstellung)"
    assert lowest["c"]["index"] == 0.0
    for component in ("synergy", "tournament_lists", "global_inclusion", "combos"):
        with pytest.raises(ValueError, match="missing_value"):
            StrengthSettings(missing_value={component: "lowest"})
    with pytest.raises(ValueError):
        StrengthSettings(missing_value={"commander_inclusion": "zero"})
    # a signal that is not usable (below the minimum) is not turned into ranks
    small = {"a": {"commander_inclusion": Observation(0.9, 9, 10)}, "c": {}}
    scored = strength.score_pool(
        _only("commander_inclusion", missing_value={"commander_inclusion": "lowest"}),
        small,
        collected,
    )
    assert _row(scored, "c", "commander_inclusion")["status"] == strength.NO_VALUE


def test_commander_and_basic_lands_are_not_ranked_unless_switched_on() -> None:
    observations = {
        "boss": {"synergy": Observation(99.0)},
        "land": {"synergy": Observation(98.0)},
        "x": {"synergy": Observation(1.0)},
        "y": {"synergy": Observation(2.0)},
    }
    context = PoolContext(
        unranked={
            "boss": strength.NOT_RANKED_COMMANDER,
            "land": strength.NOT_RANKED_BASIC_LAND,
        }
    )
    off = strength.score_pool(_only("synergy"), observations, {"synergy"}, context=context)
    assert off["boss"]["tier"] == "N" and off["boss"]["note"] == "nicht bewertet (Commander)"
    assert off["land"]["note"] == "nicht bewertet (Standardland)"
    assert off["boss"]["index"] is None and off["boss"]["coverage"] is None
    assert off["y"]["index"] == 100.0 and off["x"]["index"] == 0.0  # they take no top rank
    on = strength.score_pool(
        _only("synergy", rank_commander_and_basics=True),
        observations,
        {"synergy"},
        context=context,
    )
    assert on["boss"]["index"] == 100.0 and on["y"]["index"] == 33.3


def test_filter_cards_are_marked_not_ranked_and_do_not_move_the_others() -> None:
    observations = {
        "need": {"deck_universe": _share(2, 2)},
        "p": {"deck_universe": _share(2, 2)},
        "q": {"deck_universe": _share(1, 2)},
    }
    settings = _only("deck_universe")
    base = PoolContext(universe_minimum=0)
    marked = PoolContext(universe_minimum=0, filter_cards={"need"})
    without = strength.score_pool(settings, observations, {"deck_universe"}, context=base)
    with_filter = strength.score_pool(settings, observations, {"deck_universe"}, context=marked)
    assert _row(without, "need", "deck_universe")["percentile"] == 0.75  # the defect
    row = _row(with_filter, "need", "deck_universe")
    assert row["status"] == strength.FILTER_CARD and row["percentile"] is None
    assert row["reason"] == strength.FILTER_CARD and "Filterkarte" in row["note"]
    assert with_filter["need"]["index"] is None
    assert _row(with_filter, "p", "deck_universe")["percentile"] == 1.0
    assert _row(with_filter, "q", "deck_universe")["percentile"] == 0.0


def test_new_settings_are_validated_serialised_and_round_trip() -> None:
    settings = StrengthSettings.from_dict(
        {
            "rank_group": "type",
            "share_measure": "raw",
            "min_denominators": {"edhrec": 50, "tournament": 8},
            "missing_value": {"deck_universe": "lowest"},
            "rank_commander_and_basics": True,
            "tier_cuts": {"S": 95, "A": 80, "B": 60, "C": 40},
        }
    )
    assert StrengthSettings.from_dict(settings.to_dict()) == settings
    assert settings.to_dict()["missing_value"] == {
        "commander_inclusion": "skip",
        "bracket_inclusion": "skip",
        "deck_universe": "lowest",
    }
    for bad in (
        {"rank_group": "colour"},
        {"share_measure": "mean"},
        {"min_denominators": {"edhrec": -1}},
        {"min_denominators": {"edhrec": 1.5}},
        {"min_denominators": {"universe": 3}},
        {"rank_commander_and_basics": "yes"},
        {"tier_cuts": {"S": 50, "A": 50, "B": 40, "C": 30}},
        {"missing_value": {"synergy": "lowest"}},
    ):
        with pytest.raises(ValueError):
            StrengthSettings.from_dict(bad)
    default = StrengthSettings()
    assert (default.rank_group, default.share_measure) == ("pool", "wilson")
    assert default.min_denominators == {"edhrec": 30, "tournament": 5, "conversion": 20}
    assert default.rank_commander_and_basics is False
    assert set(default.missing_value.values()) == {"skip"}


# ---------- store side of the review ----------


def _add_pool_card(
    store: StudioStore, card_id: str, name: str, type_line: str = "Creature", mv: float = 2.0
) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_value, type_line, "
        "commander_legal, source_id) VALUES (?, NULL, ?, 'C', ?, ?, 1, ?)",
        (card_id, name, mv, type_line, source),
    )
    store.connection.execute(
        "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
        "available_lower_bound, quantity_exact, source_id) VALUES (?, 1, 1, 0, 1, 1, ?)",
        (card_id, source),
    )


def _put_signal(
    store: StudioStore, signal: str, card: str, num: int, den: int, commander: str = COMMANDER
) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT OR REPLACE INTO card_signal VALUES (?, ?, ?, ?, ?, ?, ?)",
        (commander, signal, card, num / den, num, den, source),
    )


def test_a_name_two_cards_claim_is_reported_not_dropped_and_exact_names_win(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    _add_pool_card(store, "card:test:twin1", "Twin Moon // Left Half")
    _add_pool_card(store, "card:test:twin2", "Twin Moon // Right Half")
    _add_pool_card(store, "card:test:solo1", "Solo Card")
    _add_pool_card(store, "card:test:solo2", "Solo Card // Back Face")
    for name in ("Twin Moon", "Solo Card", "Solo Card // Back Face"):
        _put_signal(store, signals.SIGNAL_INCLUSION, name, 40, 100)
    _put_signal(store, signals.SIGNAL_INCLUSION, "Solo Card // Back Face", 10, 100)
    store.connection.commit()
    result = strength_view.compute(store, COMMANDER, StrengthSettings())
    cards = _by_name(result)
    assert result["ambiguous_names"] == [
        {
            "signal": signals.SIGNAL_INCLUSION,
            "name": "Twin Moon",
            "candidates": ["Twin Moon // Left Half", "Twin Moon // Right Half"],
        }
    ]
    for name in ("Twin Moon // Left Half", "Twin Moon // Right Half"):
        assert _component(cards[name], "commander_inclusion")["status"] == strength.NO_VALUE
    # "Solo Card" is the exact name of one card; the double-faced card keeps its own row
    assert _component(cards["Solo Card"], "commander_inclusion")["numerator"] == 40
    assert _component(cards["Solo Card // Back Face"], "commander_inclusion")["numerator"] == 10
    again = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert again["ambiguous_names"] == result["ambiguous_names"]  # deterministic


def test_commander_and_basic_land_get_no_stage_and_no_rank(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    for name in (COMMANDER, "Forest"):
        _put_signal(store, signals.SIGNAL_INCLUSION, name, 99, 100)
    store.connection.commit()
    off = _by_name(strength_view.compute(store, COMMANDER, StrengthSettings()))
    assert off[COMMANDER]["tier"] == "N" and off[COMMANDER]["note"] == "nicht bewertet (Commander)"
    assert off["Forest"]["tier"] == "N" and off["Forest"]["note"] == "nicht bewertet (Standardland)"
    assert _component(off["Filler 00"], "commander_inclusion")["percentile"] == 1.0
    on = _by_name(
        strength_view.compute(store, COMMANDER, StrengthSettings(rank_commander_and_basics=True))
    )
    assert on[COMMANDER]["tier"] != "N"
    assert _component(on["Filler 00"], "commander_inclusion")["percentile"] < 1.0


def test_a_universe_below_its_minimum_is_not_used_and_says_why(
    store: StudioStore, tmp_path: Path
) -> None:
    from commander_lab.studio import universe

    _import(store, tmp_path)
    for index in range(10):
        _deck(store, f"s{index}", "edhrec", 3, ["Filler 01"] + (["Filler 02"] if index < 3 else []))
    store.connection.commit()
    universe.save_profile(store, "klein", {})  # default minimum universe: 30 decks
    result = strength_view.compute(store, COMMANDER, StrengthSettings(universe_profile="klein"))
    row = _component(_by_name(result)["Filler 01"], "deck_universe")
    assert row["status"] == strength.NO_VALUE and row["reason"] == strength.BELOW_MIN_DENOMINATOR
    assert (row["numerator"], row["denominator"], row["min_denominator"]) == (10, 13, 30)
    assert result["universe"] is not None and result["universe"]["below_min_universe"] is True
    universe.save_profile(store, "klein", {"min_universe": 10})
    ok = strength_view.compute(store, COMMANDER, StrengthSettings(universe_profile="klein"))
    assert _component(_by_name(ok)["Filler 01"], "deck_universe")["status"] == strength.PRESENT


def test_card_filter_marks_the_required_cards_and_names_the_subset(
    store: StudioStore, tmp_path: Path
) -> None:
    from commander_lab.studio import universe, universe_view

    _import(store, tmp_path)
    for index in range(10):
        _deck(store, f"s{index}", "edhrec", 3, ["Filler 01"] + (["Filler 02"] if index < 6 else []))
    for index in range(4):
        _deck(store, f"t{index}", "edhrec", 3, ["Filler 03"])
    store.connection.commit()
    universe.save_profile(store, "filter", {"must_contain": ["Filler 01"], "min_universe": 5})
    result = strength_view.compute(store, COMMANDER, StrengthSettings(universe_profile="filter"))
    cards = _by_name(result)
    need = _component(cards["Filler 01"], "deck_universe")
    assert need["status"] == strength.FILTER_CARD and need["percentile"] is None
    assert need["numerator"] is None  # no 10/10 shown as if it were a finding
    assert _component(cards["Filler 02"], "deck_universe")["status"] == strength.PRESENT
    summary = result["universe"]
    assert summary is not None and summary["denominator"] == 10
    assert summary["subset_note"] == (
        "Teilmenge: nur Decks mit Filler 01 (7 Decks durch den Kartenfilter ausgeschlossen)"
    )
    spread = universe_view.pool_spread(store, "filter", commander_names=[COMMANDER])
    flagged = {item["name"]: item for item in spread["cards"] if item["filter_card"]}
    assert set(flagged) == {"Filler 01"}
    assert flagged["Filler 01"]["level"] == "F" and flagged["Filler 01"]["share"] is None
    assert spread["universe"]["subset_note"] == summary["subset_note"]
    assert spread["universe"]["must_contain"] == ["Filler 01"]
    co = universe_view.card_cooccurrence(
        store, "filter", flagged["Filler 01"]["card_id"], commander_names=[COMMANDER]
    )
    assert co["subset_note"] == summary["subset_note"] and co["filter_card"] is True
    unfiltered = universe.save_profile(store, "alle", {})
    assert unfiltered["name"] == "alle"
    plain = universe_view.profile_summary(store, "alle", commander_names=[COMMANDER])
    assert plain["subset_note"] is None


def test_the_group_setting_reaches_the_component_rows_of_a_real_pool(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    pool = strength_view.compute(store, COMMANDER, StrengthSettings())
    typed = strength_view.compute(store, COMMANDER, StrengthSettings(rank_group="type"))
    row = _component(_by_name(typed)["Filler 00"], "commander_inclusion")
    assert (row["group"], row["group_size"], row["group_fallback"]) == ("Creature", 9, False)
    assert pool["settings"]["rank_group"] == "pool" and typed["settings"]["rank_group"] == "type"
    banded = strength_view.compute(store, COMMANDER, StrengthSettings(rank_group="mana_band"))
    band = _component(_by_name(banded)["Filler 01"], "commander_inclusion")
    assert (band["group"], band["group_size"]) == ("2", 8)  # Filler 01 to 08 have mana value 2
    lone = _component(_by_name(banded)["Filler 00"], "commander_inclusion")
    assert lone["group"] == "3" and lone["group_fallback"] is True  # the only card of its band


def test_the_function_group_setting_reaches_the_component_rows_of_a_real_pool(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE, title="Rollen (Test)", sha256="f" * 64
    )
    with store.connection as db:
        oracle = {
            str(row["oracle_name"]): str(row["oracle_id"])
            for row in db.execute("SELECT oracle_name, oracle_id FROM card")
        }
        db.executemany(
            "INSERT INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
            [(oracle[f"Filler {index:02d}"], "ramp", source_id) for index in range(6)],
        )
    result = strength_view.compute(store, COMMANDER, StrengthSettings(rank_group="function"))
    assert result["settings"]["rank_group"] == "function"
    by_name = _by_name(result)
    row = _component(by_name["Filler 02"], "commander_inclusion")
    assert (row["group"], row["group_size"], row["group_fallback"]) == ("ramp", 6, False)
    assert row["percentile"] == pytest.approx(0.6)  # three of the six ramp cards below it
    # Filler 07 has a value but no role: pool rank, and the row says no function is known
    pool = strength_view.compute(store, COMMANDER, StrengthSettings())
    func_row = _component(by_name["Filler 07"], "commander_inclusion")
    pool_row = _component(_by_name(pool)["Filler 07"], "commander_inclusion")
    assert func_row["group_fallback"] is True and "Keine Funktion bekannt" in func_row["note"]
    assert func_row["percentile"] == pool_row["percentile"]


def test_panel_offers_the_function_rank_group(client: TestClient) -> None:
    meta = client.get("/api/strength/presets").json()
    values = [choice["value"] for choice in meta["panel"]["choices"]["rank_group"]]
    assert values == ["pool", "type", "mana_band", "function"]


def test_recommended_values_come_from_one_place_and_the_panel_texts_name_them(
    client: TestClient,
) -> None:
    meta = client.get("/api/strength/presets").json()
    assert meta["recommended"] == StrengthSettings().to_dict() == meta["defaults"]
    labels = meta["panel"]["labels"]
    assert "(empfohlen: 3)" in labels["weights.commander_inclusion"]
    assert "empfohlen: upgraded" in labels["bracket"] and "Chulane" not in labels["bracket"]
    edhrec_help = meta["panel"]["help"]["min_denominators.edhrec"]
    assert "für alle Karten" in edhrec_help and "einzelnen Karte" in edhrec_help
    assert "(empfohlen: ganzer Pool)" in labels["rank_group"]
    assert "(empfohlen: Wilson-Untergrenze)" in labels["share_measure"]
    assert "30 Decks" in labels["min_denominators.edhrec"]
    assert "5 Listen" in labels["min_denominators.tournament"]
    assert "Mindest-Universum" in labels["min_denominators.deck_universe"]
    assert "(empfohlen: auslassen)" in labels["missing_value.commander_inclusion"]
    assert "(empfohlen: aus)" in labels["rank_commander_and_basics"]
    assert "(empfohlen: 30)" in labels["min_coverage"]  # the page field is in percent
    assert "(empfohlen: 2)" in labels["min_components"]
    assert [group["title"] for group in meta["panel"]["groups"]][-1].endswith(
        "(empfohlen: 90 / 75 / 55 / 35)"
    )
    for group in meta["panel"]["groups"]:
        assert all(key in labels and key in meta["panel"]["help"] for key in group["keys"])


def test_a_dangling_universe_reference_falls_back_visibly(
    client: TestClient, tmp_path: Path
) -> None:
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    try:
        universe.save_profile(store, "weg", {})
    finally:
        store.close()
    saved = client.put(
        "/api/strength/profiles/mit-universum",
        json={"settings": {"universe_profile": "weg"}},
        headers=HEADER,
    )
    assert saved.status_code == 200
    assert client.delete("/api/universe/profiles/weg", headers=HEADER).status_code == 200
    listed = {item["name"]: item for item in client.get("/api/strength/profiles").json()}
    assert listed["mit-universum"]["valid"] is True
    assert listed["mit-universum"]["universe_missing"] == "weg"
    computed = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "profile": "mit-universum"},
        headers=HEADER,
    )
    assert computed.status_code == 200
    body = computed.json()
    assert body["universe"] is None and body["universe_missing"] == "weg"
    assert body["settings"]["universe_profile"] is None
    assert "„weg“" in body["notices"][0] and "kein Universum" in body["notices"][0]
    # explicit settings still name a real universe
    explicit = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": {"universe_profile": "weg"}},
        headers=HEADER,
    )
    assert explicit.status_code == 404


def test_an_invalid_stored_profile_is_listed_with_a_reason_not_a_500(
    client: TestClient, tmp_path: Path
) -> None:
    client.put("/api/strength/profiles/gut", json={"settings": {"bracket": "cedh"}}, headers=HEADER)
    store = StudioStore.open(tmp_path / "studio")
    try:
        store.connection.execute(
            "INSERT INTO strength_profile(name, spec, created_at) VALUES (?, ?, 'x')",
            ("kaputt", '{"bracket": "bracket 9"}'),
        )
        store.connection.execute(
            "INSERT INTO strength_profile(name, spec, created_at) VALUES (?, ?, 'x')",
            ("kein-json", "not json"),
        )
        store.connection.commit()
    finally:
        store.close()
    answer = client.get("/api/strength/profiles")
    assert answer.status_code == 200
    listed = {item["name"]: item for item in answer.json()}
    assert listed["gut"]["valid"] is True and listed["gut"]["settings"]["bracket"] == "cedh"
    assert listed["kaputt"]["valid"] is False and listed["kaputt"]["settings"] is None
    assert "bracket" in listed["kaputt"]["reason"]
    assert listed["kein-json"]["valid"] is False
    one = client.get("/api/strength/profiles/kaputt")
    assert one.status_code == 200 and one.json()["valid"] is False
    used = client.post(
        "/api/strength", json={"commander": COMMANDER, "profile": "kaputt"}, headers=HEADER
    )
    assert used.status_code == 422 and "kaputt" in used.json()["detail"]


# ---------- import report and commander names (Refs #1205) ----------


def _tournament_file(path: Path, commander: str, lists: int, player_prefix: str) -> None:
    rows: list[dict[str, object]] = []
    for index in range(lists):
        player = f"{player_prefix} {index + 1}"
        rows.append(_list_row("Cup Z", "2026-11-01", player, commander, "commander"))
        rows.append(_list_row("Cup Z", "2026-11-01", player, "Filler 01", "main"))
        if index == 0:
            rows.append(_list_row("Cup Z", "2026-11-01", player, "Filler 02", "main"))
    _write(
        path,
        rows,
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


def test_a_reimport_without_valid_rows_says_that_nothing_was_replaced(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    before = store.count("card_signal")
    # the same global file, but no card is AVAILABLE any more: zero valid rows
    broken = tmp_path / "broken_global"
    broken.mkdir()
    _write(
        broken / "card_global_signals.csv",
        [
            {
                "card_name": "Filler 00",
                "fetch_status": "FAILED",
                "num_decks": 1,
                "potential_decks": 2,
            }
        ],
        ["card_name", "fetch_status", "num_decks", "potential_decks"],
    )
    report = signals.import_signals(store, broken, commander=COMMANDER)
    entry = report["files"][signals.GLOBAL_FILE]  # type: ignore[index]
    assert entry["status"] == "NOTHING_REPLACED"
    assert entry["rows_written"] == 0 and entry["rows_replaced"] == 0
    assert entry["rows_kept"] == 9  # the nine stored global rows stay
    assert report["rows_kept"] == 9 and report["rows_written"] == 0
    assert store.count("card_signal") == before  # old rows kept, as reported
    # a real re-import replaces and says how many
    again = _import(store, tmp_path)
    replaced = again["files"][signals.GLOBAL_FILE]  # type: ignore[index]
    assert replaced["status"] == "IMPORTED" and replaced["rows_replaced"] == 9
    assert replaced["rows_written"] == 9 and replaced["rows_kept"] == 0
    absent = again["files"][f"{signals.BRACKET_FILE}_upgraded"]  # type: ignore[index]
    assert absent["status"] == "ABSENT"


def test_commander_names_are_matched_against_the_store_and_reported(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "names"
    folder.mkdir()
    rows = _commander_rows("test commander", {"Filler 00": 5}, 10)  # lower case
    rows += _commander_rows("Mystery Commander", {"Filler 00": 1}, 10)  # unknown
    _write(folder / "commander_card_signals.csv", rows, CARD_FIELDS)
    report = signals.import_signals(store, folder, commander=COMMANDER)
    assert report["commanders_imported"] == ["Mystery Commander", COMMANDER]
    assert report["commanders_not_recognised"] == ["Mystery Commander"]
    assert report["commanders_normalised"] == [{"from": "test commander", "to": COMMANDER}]
    own = _signal(store, signals.SIGNAL_INCLUSION, "Filler 00", COMMANDER)
    assert own is not None and own["numerator"] == 5
    assert _signal(store, signals.SIGNAL_INCLUSION, "Filler 00", "test commander") is None
    mystery = _signal(store, signals.SIGNAL_INCLUSION, "Filler 00", "Mystery Commander")
    assert mystery is not None  # imported as written, never mixed into another commander


def test_any_topdeck_decks_file_belongs_to_the_commander_of_its_commander_section(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "tournaments"
    folder.mkdir()
    _tournament_file(folder / "topdeck_alpha_decks.csv", "Test Commander", 3, "Liste")
    _tournament_file(folder / "topdeck_beta_decks_1.csv", "Beta Hero", 2, "Zed Secretperson")
    report = signals.import_signals(store, folder, commander=COMMANDER)
    files = report["files"]
    assert isinstance(files, dict)
    assert files["topdeck_alpha_decks"]["commander"] == COMMANDER
    assert files["topdeck_beta_decks"]["commander"] == "Beta Hero"
    assert files["topdeck_beta_decks"]["parts"] == ["topdeck_beta_decks_1.csv"]
    assert files[signals.TOURNAMENT_FILE]["status"] == "ABSENT"
    alpha = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 02", COMMANDER)
    assert alpha is not None and (alpha["numerator"], alpha["denominator"]) == (1, 3)
    beta = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 01", "Beta Hero")
    assert beta is not None and (beta["numerator"], beta["denominator"]) == (2, 2)
    # the player column is only an in-memory grouping key: never stored, never reported
    assert store.path is not None and b"Secretperson" not in store.path.read_bytes()
    assert "Secretperson" not in repr(report)


def test_tier_page_text_filters_and_recommendations_are_wired() -> None:
    import re

    from commander_lab.studio.web import STATIC

    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    builder = (STATIC / "app.js").read_text(encoding="utf-8")
    for source in (script, builder):
        assert "innerHTML" not in source
        assert not re.search(r"\bon[a-z]+=\s*[\"']", source)  # no inline handler attributes
        assert 'setAttribute("style"' not in source and "style=" not in source
    assert "style=" not in html and not re.search(r"\son[a-z]+=", html)
    # recommended values come from the server, never from a copy in the page
    assert "/api/strength/presets" in script and "Empfohlene Werte" in script
    # two named things, never one mixed "strength"
    assert "Stärke-Index (Schätzung aus Nutzungsdaten)" in script
    assert "Ergebnis aus Partien (noch nicht bewertet)" in script
    # filter cards and subset denominators are labelled
    assert "Filterkarte" in script and "Teilmenge" in script and "Filterkarte" in builder
    assert "Teilmenge" in builder
    # tier filter and a percentile sort per component
    for tier in ("S", "A", "B", "C", "D", "U"):
        assert f'"{tier}"' in script
    assert "PERCENTILE_SORT" in script and "visibleCards" in script
    # an empty weight field means "recommended value"; it is never read as 0
    assert "empfohlen" in script
    assert "Number(" in script and '=== ""' in script
    # "rarely played in the deck" sorts unknown values last
    assert "if (x === null) return 1;" in builder


def test_the_server_serves_the_recommendations_the_page_shows(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "studio.db"))
    meta = client.get("/api/strength/presets").json()
    assert meta["recommended"]["weights"]["simulation"] == 0.0
    assert meta["panel"]["labels"]["min_coverage"] == "Mindest-Datenlage in % (empfohlen: 30)"
    assert (
        meta["panel"]["labels"]["weights.simulation"]
        == "Simulation (empfohlen: 0, derzeit ohne Daten)"
    )
    assert all(item["settings"]["weights"]["simulation"] == 0.0 for item in meta["presets"])


# ---------- pooled tournament files and the exact commander set (Refs #1205) ----------

LIST_FIELDS = [
    "tournament",
    "date",
    "player",
    "wins",
    "draws",
    "losses",
    "card_name",
    "quantity",
    "section",
]


def _lists_file(path: Path, lists: list[tuple[str, str, str, list[str], list[str]]]) -> None:
    """One list = (tournament, date, player key, commander section, main-deck cards)."""
    rows: list[dict[str, object]] = []
    for tournament, date, player, commander_section, cards in lists:
        rows += [_list_row(tournament, date, player, c, "commander") for c in commander_section]
        rows += [_list_row(tournament, date, player, card, "main") for card in cards]
    _write(path, rows, LIST_FIELDS)


def _tournament_rows(store: StudioStore, commander: str = COMMANDER) -> int:
    return int(
        store.connection.execute(
            "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?",
            (commander, signals.SIGNAL_TOURNAMENT),
        ).fetchone()[0]
    )


def test_two_tournament_files_of_one_commander_are_pooled_not_overwritten(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "pooled"
    folder.mkdir()
    first = [("Cup P", "2026-11-01", f"Key {n}", [COMMANDER], ["Filler 01"]) for n in range(6)]
    second = [("Cup Q", "2026-11-02", f"Key {n}", [COMMANDER], ["Filler 02"]) for n in range(3)]
    # the very same list (tournament, date, player key, cards) read from a second file
    second.append(first[0])
    _lists_file(folder / "topdeck_aaa_decks.csv", first)
    _lists_file(folder / "topdeck_bbb_decks.csv", second)
    report = signals.import_signals(store, folder, commander=COMMANDER)
    files = report["files"]
    assert isinstance(files, dict)
    one = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 01")
    two = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 02")
    assert one is not None and (one["numerator"], one["denominator"]) == (6, 9)
    assert two is not None and (two["numerator"], two["denominator"]) == (3, 9)
    assert files["topdeck_aaa_decks"]["lists_read"] == 6
    assert files["topdeck_bbb_decks"]["lists_read"] == 4
    assert files["topdeck_aaa_decks"]["commander"] == COMMANDER
    assert files["topdeck_bbb_decks"]["commander"] == COMMANDER
    stored = _tournament_rows(store)
    assert stored == 2
    assert report["rows_written"] == stored and report["rows_replaced"] == 0
    # a second import replaces exactly what the first one stored, not rows it just wrote
    again = signals.import_signals(store, folder, commander=COMMANDER)
    assert again["rows_written"] == stored and again["rows_replaced"] == stored
    assert sum(entry["rows_written"] for entry in again["files"].values()) == stored  # type: ignore[attr-defined]
    assert sum(entry["rows_replaced"] for entry in again["files"].values()) == stored  # type: ignore[attr-defined]
    assert _tournament_rows(store) == stored


def test_only_lists_with_exactly_the_commander_count_and_pairs_are_reported(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "pairs"
    folder.mkdir()
    lists = [
        ("Cup R", "2026-11-03", f"Pair {n}", [COMMANDER, "Pair Mate"], ["Filler 03"])
        for n in range(3)
    ]
    lists += [("Cup R", "2026-11-03", f"Solo {n}", [COMMANDER], ["Filler 04"]) for n in range(4)]
    _lists_file(folder / "topdeck_mixed_decks.csv", lists)
    report = signals.import_signals(store, folder, commander=COMMANDER)
    entry = report["files"]["topdeck_mixed_decks"]  # type: ignore[index]
    assert entry["commander"] == COMMANDER and entry["lists_read"] == 7
    assert entry["skipped_reasons"]["OTHER_COMMANDER_SET"] == 3
    solo = _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 04")
    assert solo is not None and (solo["numerator"], solo["denominator"]) == (4, 4)
    assert _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 03") is None  # pair-only card
    assert _signal(store, signals.SIGNAL_TOURNAMENT, "Pair Mate") is None
    assert _signal(store, signals.SIGNAL_TOURNAMENT, COMMANDER) is None  # never a deck card
    names = {
        row[0]
        for row in store.connection.execute(
            "SELECT card_name FROM card_signal WHERE signal = ?", (signals.SIGNAL_TOURNAMENT,)
        )
    }
    assert "Pair Mate" not in names and COMMANDER not in names


def test_a_file_with_only_pair_lists_stores_nothing_for_a_single_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "onlypairs"
    folder.mkdir()
    lists = [
        ("Cup S", "2026-11-04", f"Pair {n}", [COMMANDER, "Pair Mate"], ["Filler 03"])
        for n in range(3)
    ]
    _lists_file(folder / "topdeck_pairs_decks.csv", lists)
    report = signals.import_signals(store, folder, commander=COMMANDER)
    entry = report["files"]["topdeck_pairs_decks"]  # type: ignore[index]
    assert entry["status"] == "NOTHING_REPLACED"
    assert entry["rows_written"] == 0 and entry["commander"] is None
    assert entry["skipped_reasons"] == {"OTHER_COMMANDER_SET": 3}
    assert store.count("card_signal") == 0


# ---------- loading a saved strength profile (Refs #1205) ----------


def test_a_saved_profile_is_computed_with_its_own_universe_not_the_selected_one(
    client: TestClient, tmp_path: Path
) -> None:
    """The page loads a saved profile through ``profile=``: the server answers with the
    universe the profile names (and echoes it in ``settings``), so the page can select that
    universe and show exactly what was computed."""
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    try:
        universe.save_profile(store, "uni-a", {})
        universe.save_profile(store, "uni-b", {})
    finally:
        store.close()
    saved = client.put(
        "/api/strength/profiles/mit-a",
        json={"settings": {"universe_profile": "uni-a"}},
        headers=HEADER,
    )
    assert saved.status_code == 200
    computed = client.post(
        "/api/strength", json={"commander": COMMANDER, "profile": "mit-a"}, headers=HEADER
    )
    assert computed.status_code == 200
    body = computed.json()
    assert body["settings"]["universe_profile"] == "uni-a"
    assert body["universe"]["profile"] == "uni-a" and body["universe_missing"] is None
    assert body["notices"] == []
    # the page's settings of the same profile with the OTHER universe selected differ
    other = client.post(
        "/api/strength",
        json={
            "commander": COMMANDER,
            "settings": {**body["settings"], "universe_profile": "uni-b"},
        },
        headers=HEADER,
    )
    assert other.status_code == 200 and other.json()["universe"]["profile"] == "uni-b"


def test_the_page_loads_a_saved_profile_through_the_server_and_keeps_drafts() -> None:
    from commander_lab.studio.web import STATIC

    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    # a saved profile is computed by the server's profile= path, never by applyStrength
    # (which would overwrite its universe with the one selected at the top)
    assert "loadSavedProfile(p)" in script and "profile: profile.name" in script
    assert "loadSavedProfile(p).catch" in script
    assert "fillUniverseSelect(wanted)" in script
    # the page says which universe the index was computed with
    assert "Index berechnet mit:" in script and "kein Decklisten-Universum" in script
    # form edits and the profile name survive a re-render
    assert (
        "s.draft.fields[key] = input.value" in script
        and "s.draft.name = event.target.value" in script
    )
    assert '$("s-name").value = p.name' not in script


# ---------- a weight that cannot act does not lower coverage (Refs #1205) ----------


def test_a_component_without_any_data_is_not_part_of_the_coverage_denominator() -> None:
    weights = {name: 0.0 for name in strength.COMPONENTS}
    weights |= {strength.COMMANDER_INCLUSION: 3.0, strength.SYNERGY: 1.0}
    observations = {
        "a": {"commander_inclusion": _share(900, 1000), "synergy": Observation(0.2)},
        "b": {"commander_inclusion": _share(500, 1000)},
    }
    collected = {strength.COMMANDER_INCLUSION, strength.SYNERGY}
    plain = strength.score_pool(
        StrengthSettings(weights=weights, min_coverage=0.0, min_components=1),
        observations,
        collected,
    )
    weighted = strength.score_pool(
        StrengthSettings(
            weights={**weights, strength.SIMULATION: 5.0}, min_coverage=0.0, min_components=1
        ),
        observations,
        collected,
    )
    assert plain["b"]["coverage"] == 0.75
    for card in ("a", "b"):  # a positive weight on a never-collected source changes nothing
        assert (weighted[card]["coverage"], weighted[card]["index"]) == (
            plain[card]["coverage"],
            plain[card]["index"],
        )
    # once the source has data the weight counts in the denominator again
    with_data = strength.score_pool(
        StrengthSettings(
            weights={**weights, strength.SIMULATION: 5.0}, min_coverage=0.0, min_components=1
        ),
        {**observations, "a": {**observations["a"], "simulation": Observation(1.0)}},
        {*collected, strength.SIMULATION},
    )
    assert with_data["b"]["coverage"] < plain["b"]["coverage"]


def test_the_result_notes_name_a_weight_without_data(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    weighted = StrengthSettings(weights={**strength.DEFAULT_WEIGHTS, strength.SIMULATION: 4.0})
    result = strength_view.compute(store, COMMANDER, weighted)
    assert "Simulation: keine Daten, Gewicht ohne Wirkung" in result["notices"]
    default = strength_view.compute(store, COMMANDER, StrengthSettings())
    assert not any("Gewicht ohne Wirkung" in text for text in default["notices"])


def test_a_stored_profile_with_unknown_keys_is_accepted_and_names_them(
    client: TestClient, tmp_path: Path
) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        for name, spec in (
            ("neuer", '{"bracket": "cedh", "zukunft": 1, "weights": {"synergy": 2}}'),
            ("neuer-kaputt", '{"zukunft": 1, "bracket": "bracket 9"}'),
        ):
            store.connection.execute(
                "INSERT INTO strength_profile(name, spec, created_at) VALUES (?, ?, 'x')",
                (name, spec),
            )
        store.connection.commit()
    finally:
        store.close()
    listed = {item["name"]: item for item in client.get("/api/strength/profiles").json()}
    assert listed["neuer"]["valid"] is True and listed["neuer"]["reason"] is None
    assert listed["neuer"]["ignored_keys"] == ["zukunft"]
    assert listed["neuer"]["settings"]["bracket"] == "cedh"
    assert "zukunft" not in listed["neuer"]["settings"]
    # invalid VALUES stay invalid, with or without extra keys
    assert (
        listed["neuer-kaputt"]["valid"] is False and "bracket" in listed["neuer-kaputt"]["reason"]
    )
    used = client.post(
        "/api/strength", json={"commander": COMMANDER, "profile": "neuer"}, headers=HEADER
    )
    assert used.status_code == 200
    body = used.json()
    assert body["settings"]["bracket"] == "cedh" and body["settings"]["weights"]["synergy"] == 2
    assert any("zukunft" in text and "ignoriert" in text for text in body["notices"])
    # explicit settings with an unknown key are still refused
    explicit = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": {"zukunft": 1}},
        headers=HEADER,
    )
    assert explicit.status_code == 422
    plain = client.post(
        "/api/strength", json={"commander": COMMANDER, "profile": "neuer-kaputt"}, headers=HEADER
    )
    assert plain.status_code == 422


def test_the_page_names_a_pool_fallback_instead_of_a_null_group_size() -> None:
    from commander_lab.studio.web import STATIC

    script = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "c.group_fallback ?" in script
    assert "Rang im ganzen Pool (Gruppe zu klein)" in script


# ---------- behaviours pinned after surviving mutants (Refs #1205) ----------


def test_missing_as_lowest_applies_to_unlisted_cards_not_to_an_unknown_value() -> None:
    observations = {
        "a": {"commander_inclusion": Observation(0.9, 900, 1000)},
        "b": {"commander_inclusion": Observation(0.1, 100, 1000)},
        "unknown": {"commander_inclusion": Observation(None)},  # listed, value not published
        "unlisted": {},
    }
    scored = strength.score_pool(
        _only("commander_inclusion", missing_value={"commander_inclusion": "lowest"}),
        observations,
        {"commander_inclusion"},
    )
    unknown = _row(scored, "unknown", "commander_inclusion")
    assert unknown["reason"] == strength.VALUE_UNKNOWN
    assert unknown["status"] == strength.NO_VALUE and unknown["percentile"] is None
    assert scored["unknown"]["index"] is None  # unknown is never turned into the lowest rank
    unlisted = _row(scored, "unlisted", "commander_inclusion")
    assert unlisted["status"] == strength.MISSING_AS_LOWEST and unlisted["percentile"] == 0.0


def test_the_minimum_denominator_is_checked_per_card_with_mixed_denominators() -> None:
    observations = {
        "big": {"commander_inclusion": Observation(0.9, 90, 100)},
        "other": {"commander_inclusion": Observation(0.5, 50, 100)},
        "small": {"commander_inclusion": Observation(1.0, 10, 10)},  # own denominator 10 < 30
    }
    scored = strength.score_pool(
        _only("commander_inclusion"), observations, {"commander_inclusion"}
    )
    small = _row(scored, "small", "commander_inclusion")
    assert small["reason"] == strength.BELOW_MIN_DENOMINATOR and small["percentile"] is None
    assert "Nenner 10" in small["note"]
    assert _row(scored, "big", "commander_inclusion")["status"] == strength.PRESENT
    assert _row(scored, "other", "commander_inclusion")["percentile"] == 0.0
    assert _row(scored, "big", "commander_inclusion")["percentile"] == 1.0


def test_the_reference_denominator_is_the_largest_one_of_the_signal() -> None:
    # one card with a denominator below the minimum must not switch the signal off for the
    # others: the reference is the MAX (100), not the MIN (10)
    observations = {
        "big": {"commander_inclusion": Observation(0.9, 90, 100)},
        "small": {"commander_inclusion": Observation(1.0, 10, 10)},
        "unlisted": {},
    }
    scored = strength.score_pool(
        _only("commander_inclusion"), observations, {"commander_inclusion"}
    )
    assert _row(scored, "big", "commander_inclusion")["status"] == strength.PRESENT
    assert _row(scored, "unlisted", "commander_inclusion")["reason"] == strength.NOT_LISTED
    # when even the largest denominator is below the minimum the whole signal is off
    low = {"x": {"commander_inclusion": Observation(0.5, 5, 10)}, "y": {}}
    off = strength.score_pool(_only("commander_inclusion"), low, {"commander_inclusion"})
    assert {_row(off, key, "commander_inclusion")["reason"] for key in "xy"} == {
        strength.BELOW_MIN_DENOMINATOR
    }


def test_the_preferred_commander_breaks_a_tie_between_tournament_commanders(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "tie"
    folder.mkdir()
    lists = [
        ("Cup T", "2026-11-05", f"Key {n}", [name], ["Filler 06"])
        for n, name in enumerate(["Test Commander", "Test Commander", "Zed Hero", "Zed Hero"])
    ]
    _lists_file(folder / "topdeck_tie_decks.csv", lists)
    zed = signals.import_signals(store, folder, commander="Zed Hero")
    assert zed["files"]["topdeck_tie_decks"]["commander"] == "Zed Hero"  # type: ignore[index]
    assert _signal(store, signals.SIGNAL_TOURNAMENT, "Filler 06", "Zed Hero") is not None
    first = signals.import_signals(store, folder, commander="Test Commander")
    assert first["files"]["topdeck_tie_decks"]["commander"] == "Test Commander"  # type: ignore[index]
    # a preferred name that is not among the tied commanders changes nothing: the first by name
    neither = signals.import_signals(store, folder, commander="Somebody Else")
    assert neither["files"]["topdeck_tie_decks"]["commander"] == "Test Commander"  # type: ignore[index]


def test_a_mana_value_of_five_is_the_last_band_and_four_is_not() -> None:
    assert strength.mana_band(5, is_land=False) == "5+"
    assert strength.mana_band(4, is_land=False) == "4"
    assert strength.mana_band(4.5, is_land=False) == "4"
    assert strength.mana_band(1.5, is_land=False) == "0-1"
    assert strength.mana_band(2, is_land=False) == "2"


# ---------- combo quality (#1261 P3.7) ----------

QUALITY_FIELDS = [
    "card_name",
    "fetch_status",
    "variant_count",
    "distinct_partner_cards",
    "partners_in_collection",
    "variant_ids",
]


def _quality_folder(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    folder = tmp_path / "quality"
    folder.mkdir(exist_ok=True)
    _write(folder / "spellbook_card_links.csv", rows, QUALITY_FIELDS)
    return folder


def _quality_row(name: str, variants: int, partners: object, ids: str) -> dict[str, object]:
    return {
        "card_name": name,
        "fetch_status": "AVAILABLE",
        "variant_count": variants,
        "distinct_partner_cards": 0,
        "partners_in_collection": partners,
        "variant_ids": ids,
    }


def test_variant_id_token_count_is_the_card_count_of_the_combo() -> None:
    # The id of a spellbook variant joins the card ids of the combo (it is the combo's
    # page address); a template slot is a negative id and counts as one card.
    assert signals._variant_card_slots("147-1235") == 2
    assert signals._variant_card_slots("1368-3518-4856") == 3
    assert signals._variant_card_slots("1486-3734-4231-4452--108--119") == 6
    assert signals._variant_card_slots("10--108") == 2


def test_spellbook_import_stores_the_combo_quality_signals(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = _quality_folder(
        tmp_path,
        [
            # three variants: one of two cards, one of three, one of four
            _quality_row("Filler 00", 3, 1, "1-2;1-2-3;1-2-3-4"),
            # a two-card variant whose partner is a template slot
            _quality_row("Filler 01", 1, 0, "10--108"),
            # no variants at all: the two-card count is a counted 0, not unknown
            _quality_row("Filler 02", 0, 0, ""),
            # partners not numeric and no variant ids: both quality figures unknown
            _quality_row("Filler 03", 4, "many", ""),
        ],
    )
    report = signals.import_signals(store, folder, commander=COMMANDER)
    two = _signal(store, signals.SIGNAL_TWO_CARD, "Filler 00", commander="")
    assert two is not None and two["value"] == 1.0
    partners = _signal(store, signals.SIGNAL_PARTNERS, "Filler 00", commander="")
    assert partners is not None and partners["value"] == 1.0
    template = _signal(store, signals.SIGNAL_TWO_CARD, "Filler 01", commander="")
    assert template is not None and template["value"] == 1.0
    empty = _signal(store, signals.SIGNAL_TWO_CARD, "Filler 02", commander="")
    assert empty is not None and empty["value"] == 0.0
    unknown_partners = _signal(store, signals.SIGNAL_PARTNERS, "Filler 03", commander="")
    assert unknown_partners is not None and unknown_partners["value"] is None
    unknown_two = _signal(store, signals.SIGNAL_TWO_CARD, "Filler 03", commander="")
    assert unknown_two is not None and unknown_two["value"] is None
    files = report["files"]
    assert isinstance(files, dict)
    reasons = files[signals.SPELLBOOK_FILE]["null_value_reasons"]
    assert reasons == {"PARTNER_COUNT_NOT_NUMERIC": 1, "VARIANT_IDS_MISSING": 1}
    # the quality signals are commander independent, like the variant count
    assert _signal(store, signals.SIGNAL_TWO_CARD, "Filler 00", commander=COMMANDER) is None


def test_combo_quality_mixes_the_parts_and_keeps_unlisted_cards_out() -> None:
    parts = {
        strength.COMBO_PART_VARIANTS: {"a": 1.0, "b": 9.0},
        strength.COMBO_PART_TWO_CARD: {"a": 1.0, "b": 0.0},
        strength.COMBO_PART_PARTNERS: {"a": 1.0, "b": 0.0},
    }
    quality = strength.combo_quality(parts)
    # one two-card combo with its partner in the collection outranks nine variants
    # without either quality mark
    assert quality == {"a": pytest.approx(2 / 3), "b": pytest.approx(1 / 3)}
    # a card the primary part does not list gets no value, however good its parts are
    parts[strength.COMBO_PART_TWO_CARD]["unlisted"] = 5.0
    assert "unlisted" not in strength.combo_quality(parts)
    # a listed card without a value in a later part is averaged over the parts it has
    partial = {
        strength.COMBO_PART_VARIANTS: {"a": 1.0, "b": 9.0},
        strength.COMBO_PART_TWO_CARD: {"a": 3.0},
    }
    assert strength.combo_quality(partial) == {"a": 0.25, "b": 1.0}
    assert strength.combo_quality({}) == {}


def _combos_only() -> StrengthSettings:
    weights = {name: 0.0 for name in strength.COMPONENTS} | {strength.COMBOS: 1.0}
    return StrengthSettings(
        weights=weights, min_coverage=0.0, min_components=1, require_commander_signal=False
    )


def test_combo_quality_outranks_the_raw_variant_count(store: StudioStore, tmp_path: Path) -> None:
    rows = [
        # one variant, but a two-card combo whose partner is in the collection
        _quality_row("Filler 00", 1, 1, "1-2"),
        # nine variants, none of two cards, every partner outside the collection
        {
            **_quality_row("Filler 01", 9, 0, ";".join(["1-2-3"] * 9)),
            "distinct_partner_cards": 4,
        },
        *[_quality_row(name, 0, 0, "") for name in CARDS[2:]],
    ]
    signals.import_signals(store, _quality_folder(tmp_path, rows), commander=COMMANDER)
    cards = _by_name(strength_view.compute(store, COMMANDER, _combos_only()))
    quality = _component(cards["Filler 00"], "combos")
    bulk = _component(cards["Filler 01"], "combos")
    none = _component(cards["Filler 02"], "combos")
    assert quality["percentile"] == 1.0
    assert bulk["percentile"] is not None and none["percentile"] is not None
    assert bulk["percentile"] > none["percentile"]  # the variant count still counts
    assert quality["percentile"] > bulk["percentile"]  # but quality outranks it
    assert cards["Filler 00"]["index"] == 100.0


def test_combo_quality_falls_back_to_the_variant_count_without_the_new_columns(
    store: StudioStore, tmp_path: Path
) -> None:
    # A spellbook file of the old shape (no partner and no variant-id column) ranks
    # exactly as the variant count alone did before P3.7.
    folder = tmp_path / "lean_quality"
    folder.mkdir()
    _write(
        folder / "spellbook_card_links.csv",
        [
            {"card_name": "Filler 00", "fetch_status": "AVAILABLE", "variant_count": 1},
            {"card_name": "Filler 01", "fetch_status": "AVAILABLE", "variant_count": 9},
        ],
        ["card_name", "fetch_status", "variant_count"],
    )
    signals.import_signals(store, folder, commander=COMMANDER)
    cards = _by_name(strength_view.compute(store, COMMANDER, _combos_only()))
    assert _component(cards["Filler 01"], "combos")["percentile"] == 1.0
    assert _component(cards["Filler 00"], "combos")["percentile"] == 0.0


def test_spellbook_downgrade_import_drops_the_stale_quality_rows(
    store: StudioStore, tmp_path: Path
) -> None:
    # A replacing import of a spellbook file of the old shape into a store that
    # already holds the quality signals: the file declares all three signals, so
    # the rows of the two it does not write go with the import instead of staying
    # behind as stale rows, and the ranking is the variant count's alone again.
    signals.import_signals(
        store,
        _quality_folder(
            tmp_path,
            [
                _quality_row("Filler 00", 1, 1, "1-2"),
                _quality_row("Filler 01", 9, 0, ";".join(["1-2-3"] * 9)),
            ],
        ),
        commander=COMMANDER,
    )
    assert _signal(store, signals.SIGNAL_PARTNERS, "Filler 00", commander="") is not None
    assert _signal(store, signals.SIGNAL_TWO_CARD, "Filler 00", commander="") is not None

    folder = tmp_path / "lean_downgrade"
    folder.mkdir()
    _write(
        folder / "spellbook_card_links.csv",
        [
            {"card_name": "Filler 00", "fetch_status": "AVAILABLE", "variant_count": 1},
            {"card_name": "Filler 01", "fetch_status": "AVAILABLE", "variant_count": 9},
        ],
        ["card_name", "fetch_status", "variant_count"],
    )
    report = signals.import_signals(store, folder, commander=COMMANDER)

    for name in ("Filler 00", "Filler 01"):
        assert _signal(store, signals.SIGNAL_PARTNERS, name, commander="") is None
        assert _signal(store, signals.SIGNAL_TWO_CARD, name, commander="") is None
        assert _signal(store, signals.SIGNAL_VARIANTS, name, commander="") is not None
    files = report["files"]
    assert isinstance(files, dict)
    # both cards held three signal rows: the report counts all six as replaced
    assert files[signals.SPELLBOOK_FILE]["rows_replaced"] == 6
    cards = _by_name(strength_view.compute(store, COMMANDER, _combos_only()))
    assert _component(cards["Filler 01"], "combos")["percentile"] == 1.0
    assert _component(cards["Filler 00"], "combos")["percentile"] == 0.0


# ---------- tournament conversion (#1261 P1.1) ----------


def test_conversion_below_the_minimum_denominator_is_not_used() -> None:
    """Thin data of the Chulane shape (every base <= 3): the rows exist, and the
    minimum denominator of 20 keeps the component out of the index for every card,
    listed or not — the same protection the tournament lists have."""
    observations = {
        "a": {"tournament_conversion": Observation(1 / 3, 1, 3)},
        "b": {"tournament_conversion": Observation(0.0, 0, 3)},
        "c": {},
    }
    scored = strength.score_pool(
        _only("tournament_conversion"), observations, {"tournament_conversion"}
    )
    for card in observations:
        row = _row(scored, card, "tournament_conversion")
        assert row["status"] == strength.NO_VALUE and row["percentile"] is None
        assert row["reason"] == strength.BELOW_MIN_DENOMINATOR
        assert "Mindest-Nenner 20" in row["note"]
    assert scored["a"]["index"] is None and scored["a"]["tier"] == "U"


def test_conversion_ranks_by_the_wilson_bound_of_its_base() -> None:
    observations = {
        "high": {"tournament_conversion": Observation(0.5, 20, 40)},
        "mid": {"tournament_conversion": Observation(0.25, 10, 40)},
    }
    scored = strength.score_pool(
        _only("tournament_conversion"), observations, {"tournament_conversion"}
    )
    row = _row(scored, "high", "tournament_conversion")
    assert row["status"] == strength.PRESENT
    assert row["wilson"] == strength.wilson_lower(20, 40)
    assert scored["high"]["index"] == 100.0 and scored["mid"]["index"] == 0.0


def test_conversion_the_same_rate_ranks_higher_on_the_larger_base() -> None:
    observations = {
        "wide": {"tournament_conversion": Observation(0.5, 50, 100)},
        "narrow": {"tournament_conversion": Observation(0.5, 10, 20)},
    }
    scored = strength.score_pool(
        _only("tournament_conversion"), observations, {"tournament_conversion"}
    )
    assert scored["wide"]["index"] == 100.0 and scored["narrow"]["index"] == 0.0


def test_conversion_a_card_below_the_minimum_drops_out_alone() -> None:
    """The gate is per card once the signal as a whole clears it: a perfect rate on
    a base of 19 counts nothing while a base of exactly 20 counts."""
    observations = {
        "in": {"tournament_conversion": Observation(0.5, 10, 20)},
        "out": {"tournament_conversion": Observation(1.0, 19, 19)},
    }
    scored = strength.score_pool(
        _only("tournament_conversion"), observations, {"tournament_conversion"}
    )
    assert _row(scored, "in", "tournament_conversion")["status"] == strength.PRESENT
    out = _row(scored, "out", "tournament_conversion")
    assert out["status"] == strength.NO_VALUE
    assert out["reason"] == strength.BELOW_MIN_DENOMINATOR


def test_conversion_a_counted_zero_is_a_value_not_an_unknown() -> None:
    observations = {
        "zero": {"tournament_conversion": Observation(0.0, 0, 25)},
        "some": {"tournament_conversion": Observation(0.25, 10, 40)},
    }
    scored = strength.score_pool(
        _only("tournament_conversion", require_commander_signal=False),
        observations,
        {"tournament_conversion"},
    )
    row = _row(scored, "zero", "tournament_conversion")
    assert row["status"] == strength.PRESENT and row["percentile"] == 0.0
    assert scored["zero"]["index"] == 0.0 and scored["zero"]["tier"] == "D"


def test_conversion_alone_does_not_satisfy_the_commander_signal_rule() -> None:
    """The conversion rows of a commander are that commander's tournament figures,
    but the component is not in COMMANDER_SPECIFIC: it never earns a tier alone."""
    observations = {"a": {"tournament_conversion": Observation(0.5, 20, 40)}}
    scored = strength.score_pool(
        _only("tournament_conversion"), observations, {"tournament_conversion"}
    )
    assert scored["a"]["index"] == 50.0  # the only valued card takes the mean rank
    assert scored["a"]["tier"] == "U"
    assert scored["a"]["reason"] == strength.NO_COMMANDER_SIGNAL


def test_conversion_weight_counts_in_coverage_only_once_its_rows_exist() -> None:
    """The A/B of the new default weight (1.0, total weight 12 -> 13): without
    conversion rows a card's coverage drops by exactly the new share; with rows
    the share is earned back and the component ranks."""
    observations = {
        "a": {"commander_inclusion": _share(90, 100)},
        "b": {"commander_inclusion": _share(50, 100)},
    }
    before = StrengthSettings(
        weights={**strength.DEFAULT_WEIGHTS, strength.TOURNAMENT_CONVERSION: 0.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
    )
    after = StrengthSettings(min_coverage=0.0, min_components=1, require_commander_signal=False)
    scored_before = strength.score_pool(before, observations, {"commander_inclusion"})
    scored_after = strength.score_pool(after, observations, {"commander_inclusion"})
    assert scored_before["a"]["coverage"] == 0.25  # 3 of a total weight of 12
    assert scored_after["a"]["coverage"] == round(3 / 13, 4)
    assert scored_after["a"]["index"] == scored_before["a"]["index"] == 100.0
    with_rows = {
        "a": {
            "commander_inclusion": _share(90, 100),
            "tournament_conversion": Observation(0.5, 20, 40),
        },
        "b": {"commander_inclusion": _share(50, 100)},
    }
    scored_rows = strength.score_pool(
        after, with_rows, {"commander_inclusion", "tournament_conversion"}
    )
    assert scored_rows["a"]["coverage"] == round(4 / 13, 4)
    row = _row(scored_rows, "a", "tournament_conversion")
    assert row["status"] == strength.PRESENT and row["percentile"] == 0.5


def test_settings_without_the_conversion_key_use_the_default_minimum() -> None:
    settings = StrengthSettings(min_denominators={"edhrec": 30, "tournament": 5})
    assert settings.min_denominators == {"edhrec": 30, "tournament": 5, "conversion": 20}
    assert settings.minimum_denominator(strength.TOURNAMENT_CONVERSION, 0) == 20
    loaded = StrengthSettings.from_dict({"min_denominators": {"tournament": 7}})
    assert loaded.min_denominators["conversion"] == 20
    with pytest.raises(ValueError):
        StrengthSettings(min_denominators={"bogus": 1})
