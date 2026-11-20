"""Per-card evidence behind the tier list (Refs #1185, R3). All data here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, number_contract, roles
from commander_lab.studio.evidence import (
    ABSENT_IN_KNOWN_CORPUS,
    EVIDENCE_SCHEMA,
    NOT_APPLICABLE,
    NOT_COLLECTED,
    PRESENT,
    TIER_POLICY,
    card_evidence,
    mechanical_features,
    pool_evidence,
    role_alternatives,
)
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_roles_import import FILLER, FOREST, RAT, _file

COMMANDER = ("Test Commander",)


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _cards(store: StudioStore, **kwargs: object) -> dict[str, dict[str, object]]:
    result = pool_evidence(store, COMMANDER, **kwargs)  # type: ignore[arg-type]
    cards = result["cards"]
    assert isinstance(cards, list)
    return {str(card["name"]): card for card in cards}


def _layer(card: dict[str, object], name: str) -> dict[str, object]:
    layers = card["layers"]
    assert isinstance(layers, dict)
    return layers[name]  # type: ignore[no-any-return]


def _add_observation(
    store: StudioStore,
    name: str,
    metric: str,
    *,
    numerator: int | None = None,
    denominator: int | None = None,
    value: float | None = 0.5,
    snapshot: str | None = None,
    cohort: str = "edhrec:wug",
) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO observation(card_name, metric, cohort, value, numerator, denominator, "
        "data_class, snapshot, source_id) VALUES (?, ?, ?, ?, ?, ?, 'ORIGINAL_SOURCE', ?, ?)",
        (name, metric, cohort, value, numerator, denominator, snapshot, source),
    )
    store.connection.commit()
    store.bind_unbound("Test Commander")


def test_every_card_is_unrated_and_a_zero_in_a_known_corpus_is_not_weakness(
    studio: StudioStore,
) -> None:
    cards = _cards(studio)
    assert cards["Forest"]["rating"] == {
        "status": "UNRATED",
        "tier": None,
        "reason": "NO_VALIDATED_OUTCOME_MODEL",
        "model_version": None,
    }
    assert {card["rating"]["tier"] for card in cards.values()} == {None}  # type: ignore[index]
    # Forest sits in 2 of 3 source decks, Filler 05 in none; neither gets a tier.
    forest = _layer(cards["Forest"], "observed_deck")
    assert forest["status"] == PRESENT
    filler = _layer(cards["Filler 05"], "observed_deck")
    assert filler["status"] == ABSENT_IN_KNOWN_CORPUS
    coverage = cards["Filler 05"]["coverage"]
    assert isinstance(coverage, dict)
    assert "NOT_OBSERVED_IN_CORPUS" in coverage["needs"]
    assert cards["Filler 05"]["rating"]["status"] == "UNRATED"  # type: ignore[index]
    assert TIER_POLICY["validated_model"] is None


def test_corpus_items_carry_their_denominators_and_cohorts_are_not_added(
    studio: StudioStore,
) -> None:
    items = _layer(_cards(studio)["Forest"], "observed_deck")["items"]
    assert isinstance(items, list)
    corpus = {item["cohort"]: item for item in items if item["kind"] == "corpus"}
    assert corpus["all"]["of"] == 3
    assert corpus["all"]["decks"] == 2
    assert corpus["all"]["small_denominator"] is True  # 3 decks is below 30
    assert corpus["picked"]["of"] == 1
    assert _layer(_cards(studio)["Forest"], "observed_deck")["cohorts_overlap_never_add"] is True


def test_edhrec_inclusion_and_lift_stay_separate_and_unknown_times_are_flagged(
    studio: StudioStore,
) -> None:
    _add_observation(studio, "Forest", "inclusion_pct", numerator=10, denominator=20, value=50.0)
    _add_observation(studio, "Forest", "lift", value=12.0)
    _add_observation(studio, "Forest", "synergy_pct", value=3.0, snapshot="2026-11-01T00:00:00Z")
    forest = _cards(studio)["Forest"]
    edhrec = _layer(forest, "observed_deck")["edhrec"]
    assert isinstance(edhrec, dict)
    assert edhrec["inclusion_views"] == 1
    assert edhrec["lift_views"] == 1
    assert edhrec["synergy_views"] == 1
    assert edhrec["widest_inclusion"]["numerator"] == 10  # type: ignore[index]
    assert edhrec["widest_inclusion"]["denominator"] == 20  # type: ignore[index]
    assert edhrec["widest_inclusion"]["small_denominator"] is True  # type: ignore[index]
    assert edhrec["any_snapshot_unknown"] is True
    coverage = forest["coverage"]
    assert isinstance(coverage, dict)
    assert {"SMALL_DENOMINATOR", "EDHREC_TIME_UNKNOWN"} <= set(coverage["needs"])
    detail = card_evidence(studio, str(forest["card_id"]), COMMANDER)["card"]
    assert isinstance(detail, dict)
    rows = _layer(detail, "observed_deck")["edhrec_rows"]
    assert isinstance(rows, list)
    metrics = {row["metric"]: row for row in rows}
    assert metrics["lift"]["numerator"] is None  # a lift has no count; it is not invented
    assert metrics["lift"]["denominator_known"] is False
    assert metrics["inclusion_pct"]["snapshot_known"] is False
    assert metrics["synergy_pct"]["snapshot"] == "2026-11-01T00:00:00Z"


def _add_atlas(store: StudioStore, name: str, *, insufficient: int = 0) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    row = store.connection.execute(
        "SELECT card_id, oracle_id FROM card_fact WHERE oracle_name = ?", (name,)
    ).fetchone()
    store.connection.execute(
        "INSERT INTO playgroup_card_atlas(oracle_id, card_id, card_name, slug, times_brought, "
        "winrate_when_cast_pct, observed_winrate_gap_pp, insufficient_sample, source_id, "
        "created_at, updated_at) VALUES (?, ?, ?, 'slug', 40, 30.0, 2.5, ?, ?, 'now', 'now')",
        (row["oracle_id"], row["card_id"], name, insufficient, source),
    )


def test_game_combo_and_simulation_layers_say_what_is_missing(studio: StudioStore) -> None:
    forest = _cards(studio)["Forest"]
    game = _layer(forest, "observed_game")
    assert game["status"] == NOT_COLLECTED
    assert game["atlas"] is None
    sim = _layer(forest, "simulated_result")
    assert sim["status"] == NOT_COLLECTED  # no simulation stored at all
    assert sim["groups"] == [] and sim["group_count"] == 0
    assert "totals" not in sim  # no total over all runs exists (#1688)
    _add_atlas(studio, "Forest", insufficient=1)
    cards = _cards(studio)
    game = _layer(cards["Forest"], "observed_game")
    assert game["status"] == PRESENT
    assert game["atlas"]["times_brought"] == 40  # type: ignore[index]
    assert "SMALL_GAME_SAMPLE" in cards["Forest"]["coverage"]["needs"]  # type: ignore[index]
    # the source is now known, so a card without a row is "none recorded", not "not collected"
    assert _layer(cards["Swarm Rat"], "observed_game")["status"] == "NONE_RECORDED"
    # a game figure never becomes a tier and never a deck observation
    assert cards["Forest"]["rating"]["status"] == "UNRATED"  # type: ignore[index]
    assert _layer(cards["Forest"], "observed_deck")["edhrec"]["inclusion_views"] == 0  # type: ignore[index]
    # game events are counted across all commanders, so the global view shows them too
    global_cards = pool_evidence(studio, COMMANDER, view="global")["cards"]
    assert isinstance(global_cards, list)
    by_name = {str(card["name"]): card for card in global_cards}
    assert _layer(by_name["Forest"], "observed_game")["status"] == PRESENT


def test_the_global_view_keeps_only_what_does_not_depend_on_a_commander(
    studio: StudioStore,
) -> None:
    commander_view = _cards(studio)
    global_view = pool_evidence(studio, COMMANDER, view="global")
    cards = {str(card["name"]): card for card in global_view["cards"]}  # type: ignore[attr-defined]
    assert "Red Outsider" not in commander_view  # outside the colour identity
    assert global_view["commander"] == []
    assert _layer(cards["Forest"], "observed_deck")["status"] == NOT_COLLECTED
    assert _layer(cards["Forest"], "observed_deck")["items"] == []
    assert _layer(cards["Forest"], "combo_verified")["status"] == NOT_APPLICABLE
    assert _layer(cards["Forest"], "simulated_result")["status"] == NOT_APPLICABLE
    assert cards["Forest"]["coverage"]["gap_grade"] is None  # type: ignore[index]
    assert cards["Forest"]["rating"]["status"] == "UNRATED"  # type: ignore[index]


def test_role_claims_keep_their_origin(studio: StudioStore, tmp_path: Path) -> None:
    roles.import_roles(
        studio, _file(tmp_path, "wug.json", {"ramp": [FOREST, FILLER], "removal": [RAT]})
    )
    fact = _layer(_cards(studio)["Forest"], "fact")
    claims = fact["roles"]
    assert isinstance(claims, list)
    assert [(claim["role"], claim["origin"]) for claim in claims] == [("ramp", roles.ORIGIN_TAGGER)]
    other = _layer(_cards(studio)["Filler 05"], "fact")["roles"]
    assert other == []
    assert "NO_ROLE_CLAIM" in _cards(studio)["Filler 05"]["coverage"]["needs"]  # type: ignore[index]


def test_marks_never_change_the_evidence(studio: StudioStore) -> None:
    before = json.dumps(pool_evidence(studio, COMMANDER)["cards"], sort_keys=True)
    forest = studio.card_id_by_name("Forest")
    rat = studio.card_id_by_name("Swarm Rat")
    studio.connection.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) VALUES "
        "(?, 1, 0, 'private note text', '2026-11-11'), (?, 0, 1, '', '2026-11-11')",
        (forest, rat),
    )
    after = json.dumps(pool_evidence(studio, COMMANDER)["cards"], sort_keys=True)
    assert after == before
    assert "favorite" not in after
    detail = json.dumps(card_evidence(studio, str(forest), COMMANDER), sort_keys=True)
    assert "private note text" not in detail
    assert set(TIER_POLICY["never_inputs"]) >= {"favorite", "excluded", "note"}  # type: ignore[call-overload]


def test_mechanical_features_state_what_a_card_is_not_how_good_it_is() -> None:
    creature = {
        item["feature"]: item["holds"]
        for item in mechanical_features(
            "Creature — Elf Druid", "When Elf enters, draw a card. {T}: Add {G}.", ""
        )
    }
    assert creature == {
        "creature_spell": True,
        "land": False,
        "enters_trigger_text": True,
        "produces_mana": True,
    }
    land = {
        item["feature"]: item["holds"]
        for item in mechanical_features("Basic Land — Forest", "", "G")
    }
    assert land == {
        "creature_spell": False,
        "land": True,
        "enters_trigger_text": False,
        "produces_mana": True,
    }
    flip = {
        item["feature"]: item["holds"]
        for item in mechanical_features("Creature — Wolf // Land", "Front.", "")
    }
    assert flip["creature_spell"] is True
    assert flip["land"] is False  # only the front face counts


def test_a_card_outside_the_pool_and_a_bad_view_are_refused(studio: StudioStore) -> None:
    outsider = studio.card_id_by_name("Red Outsider")
    assert outsider is not None
    with pytest.raises(KeyError):
        card_evidence(studio, outsider, COMMANDER)
    with pytest.raises(ValueError):
        pool_evidence(studio, COMMANDER, view="everything")


def test_role_alternatives_compare_function_and_never_claim_an_improvement(
    studio: StudioStore, tmp_path: Path
) -> None:
    filler2 = "oracle-filler-02"
    roles.import_roles(
        studio,
        _file(tmp_path, "wug.json", {"ramp": [FOREST, FILLER, filler2], "removal": [RAT, FILLER]}),
    )
    forest = studio.card_id_by_name("Forest")
    filler1 = studio.card_id_by_name("Filler 01")
    assert forest is not None
    assert filler1 is not None
    result = role_alternatives(studio, filler1, COMMANDER)
    assert result["roles"] == ["ramp", "removal"]
    items = result["alternatives"]
    assert isinstance(items, list)
    names = [item["card"]["name"] for item in items]
    # same mana value first (Filler 02), then by name; each shares exactly one role
    assert names == ["Filler 02", "Swarm Rat", "Forest"]
    assert {item["improvement_claimed"] for item in items} == {False}
    assert items[0]["shared_roles"] == ["ramp"]
    assert items[0]["missing_roles"] == ["removal"]
    assert items[2]["mana_value_delta"] == -2.0
    without = role_alternatives(studio, filler1, COMMANDER, in_deck=[forest])
    assert "Forest" not in [item["card"]["name"] for item in without["alternatives"]]  # type: ignore[union-attr]
    # cards the caller does not want listed drop out before the cut, the order stays
    skipped = role_alternatives(studio, filler1, COMMANDER, skip=[forest], limit=2)
    assert [item["card"]["name"] for item in skipped["alternatives"]] == ["Filler 02", "Swarm Rat"]  # type: ignore[union-attr]
    assert skipped["total"] == 2
    none = role_alternatives(studio, str(studio.card_id_by_name("Filler 05")), COMMANDER)
    assert none["status"] == "NO_ROLE_CLAIM"
    assert none["alternatives"] == []
    with pytest.raises(KeyError):
        role_alternatives(studio, "card:project:nope", COMMANDER)


def test_the_web_api_serves_evidence_and_the_tier_list_page(studio: StudioStore) -> None:
    forest = studio.card_id_by_name("Forest")
    folder = studio.path.parent
    studio.close()
    with TestClient(create_app(folder)) as client:
        assert client.get("/tierliste.html").status_code == 200
        commander = {"view": "commander", "commander": "Test Commander"}
        data = client.get("/api/evidence", params=commander).json()
        assert data["summary"]["unrated"] == data["summary"]["cards"]
        assert data["summary"]["cards"] > 0
        assert client.get("/api/evidence", params={"view": "global"}).json()["commander"] == []
        assert client.get("/api/evidence", params={"view": "commander"}).status_code == 422
        assert client.get("/api/evidence", params={"view": "all"}).status_code == 422
        missing = {"view": "commander", "commander": "Nobody"}
        assert client.get("/api/evidence", params=missing).status_code == 404
        one = client.get(f"/api/cards/{forest}/evidence", params=commander).json()
        assert one["card"]["rating"]["status"] == "UNRATED"
        assert client.get("/api/cards/nope/evidence", params=commander).status_code == 404
        body = {"commander": ["Test Commander"], "in_deck": []}
        marker = {"X-Studio": "1"}
        answer = client.post(f"/api/cards/{forest}/alternatives", json=body, headers=marker)
        assert answer.status_code == 200
        assert answer.json()["status"] == "NO_ROLE_CLAIM"
        assert client.post(f"/api/cards/{forest}/alternatives", json=body).status_code == 403


def test_a_global_rank_or_a_row_without_value_is_no_observation_for_the_commander(
    studio: StudioStore,
) -> None:
    # Filler 05 is in none of the three source decks. A global popularity rank and a stored
    # row without a value must not turn that into an observation under this commander.
    with studio.connection as db:
        db.execute("UPDATE scryfall_card SET edhrec_rank = 7 WHERE name = 'Filler 05'")
    _add_observation(studio, "Filler 05", "lift", value=None)
    cards = _cards(studio)
    deck = _layer(cards["Filler 05"], "observed_deck")
    assert [item["rank"] for item in deck["items"] if item["kind"] == "edhrec_rank_global"] == [7]  # type: ignore[union-attr]
    assert deck["status"] == ABSENT_IN_KNOWN_CORPUS
    assert deck["edhrec"]["lift_views"] == 0  # type: ignore[index]
    assert deck["edhrec"]["rows_without_value"] == 1  # type: ignore[index]
    assert "NOT_OBSERVED_IN_CORPUS" in cards["Filler 05"]["coverage"]["needs"]  # type: ignore[index]
    # in the global view the rank is what that view has, so it counts there
    global_cards = pool_evidence(studio, COMMANDER, view="global")["cards"]
    filler = next(c for c in global_cards if c["name"] == "Filler 05")  # type: ignore[union-attr]
    assert _layer(filler, "observed_deck")["status"] == PRESENT
    # without any stored simulation the layer says so instead of "nothing recorded"
    assert _layer(cards["Forest"], "simulated_result")["status"] == NOT_COLLECTED


# --- #1688: the simulated layer per opponent set and table size, never one total ----------


def _add_run(
    store: StudioStore,
    run_id: str,
    *,
    offered: int,
    cast: int,
    opponents: list[str] | None,
    pod: str = "precon",
    deck_hash: str | None = "a" * 64,
) -> None:
    """One stored series under ``pod`` with Forest's counts; ``opponents=None`` is a row of
    before #1688 (no opponent set stored)."""
    from commander_lab.studio.simulations import opponent_table

    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    encoded, set_hash, size = opponent_table(opponents)
    with store.connection as db:
        db.execute(
            "INSERT INTO simulation_run(run_id, deck_id, deck_hash, opponent_ids, "
            "opponent_set_hash, table_size, pod, engine_pin, pilot_policy, seeds, games_planned, "
            "games_completed, games_failed, wins_fractional, hand_dwell_status, source_id) "
            "VALUES (?, 'x', ?, ?, ?, ?, ?, 'pin', 'tuned', '[]', 9, 9, 0, 3.0, 'OK', ?)",
            (run_id, deck_hash, encoded, set_hash, size, pod, source),
        )
        db.execute(
            "INSERT INTO simulation_card(run_id, card_id, card_name, games_completed, "
            "games_offered, games_cast_after_offer, games_rotted, offered_castable, cast_count) "
            "VALUES (?, 'card:project:0002', 'Forest', 9, ?, ?, 0, ?, ?)",
            (run_id, offered, cast, offered, cast),
        )
    store.bind_unbound(COMMANDER[0])


PRESET = ["precon/2026/lorehold_spirit", "precon/2024/animated_army", "precon/2022/token_triumph"]
STAND_IN = ["precon/2026/lorehold_spirit"] * 3


def _groups(store: StudioStore) -> list[dict[str, object]]:
    sim = _layer(_cards(store)["Forest"], "simulated_result")
    groups = sim["groups"]
    assert isinstance(groups, list) and sim["group_count"] == len(groups)
    assert "totals" not in sim
    return groups


def test_two_opponent_sets_under_one_pod_name_give_separate_figures(studio: StudioStore) -> None:
    _add_run(studio, "r-preset-1", offered=10, cast=4, opponents=PRESET)
    _add_run(studio, "r-stand-in", offered=6, cast=6, opponents=STAND_IN)
    _add_run(studio, "r-preset-2", offered=2, cast=1, opponents=PRESET, deck_hash="b" * 64)
    groups = _groups(studio)
    assert pool_evidence(studio, COMMANDER)["schema"] == EVIDENCE_SCHEMA == "studio-evidence-2"
    assert len(groups) == 2  # one pod name, two tables: two groups
    by_ids = {tuple(g["opponent_ids"]): g for g in groups}  # type: ignore[arg-type]
    preset, stand_in = by_ids[tuple(PRESET)], by_ids[tuple(STAND_IN)]
    # runs of one table add up; the other table is never part of that figure
    assert (preset["runs"], preset["games_cast_after_offer"], preset["games_offered"]) == (2, 5, 12)
    assert (stand_in["runs"], stand_in["games_cast_after_offer"], stand_in["games_offered"]) == (
        1,
        6,
        6,
    )
    assert all(g["games_offered"] != 18 for g in groups)  # never the sum over all runs
    assert preset["table_size"] == stand_in["table_size"] == 4
    assert preset["opponent_set_hash"] != stand_in["opponent_set_hash"]
    # each group carries its figure in the number contract: n/N, origin, opponent set
    for group in groups:
        zahl = group["zahl"]
        assert number_contract.check(zahl) == []
        assert isinstance(zahl, dict)
        assert (zahl["n"], zahl["N"]) == (group["games_cast_after_offer"], group["games_offered"])
        assert zahl["klasse"] == "SIMULIERT" and zahl["data_class"] == "SIMULATED_RESULT"
        assert zahl["bezug"] == "Partien (nach dem Angebot gespielt / angeboten)"
        assert "Tisch mit 4 Sitzen" in str(zahl["kohorte"])
    assert preset["zahl"]["wert"] == pytest.approx(5 / 12)  # type: ignore[index]
    # two deck states in the preset group: the state is not claimed
    assert preset["zahl"]["stand_hash"] is None  # type: ignore[index]
    assert stand_in["zahl"]["stand_hash"] == "a" * 64  # type: ignore[index]
    assert len({g["zahl"]["id"] for g in groups}) == 2  # type: ignore[index]


def test_a_run_without_an_opponent_set_is_only_in_the_unknown_group(studio: StudioStore) -> None:
    _add_run(studio, "r-old", offered=5, cast=1, opponents=None)
    groups = _groups(studio)
    assert len(groups) == 1
    unknown = groups[0]
    assert unknown["opponent_set_known"] is False
    assert unknown["opponent_ids"] is None and unknown["opponent_set_hash"] is None
    assert unknown["table_size"] is None
    assert (unknown["games_cast_after_offer"], unknown["games_offered"]) == (1, 5)  # never 0
    zahl = unknown["zahl"]
    assert isinstance(zahl, dict) and number_contract.check(zahl) == []
    assert str(zahl["kohorte"]).startswith("Gegnersatz unbekannt")
    assert any("#1658" in hint for hint in zahl["hinweise"])  # type: ignore[union-attr]
    assert unknown["vorbehalt"] == "Gegnersatz unbekannt: ein Lauf, Gegner nicht gespeichert"
    # next to a known table the unknown group stays its own, is never added and comes last
    _add_run(studio, "r-new", offered=3, cast=3, opponents=PRESET)
    groups = _groups(studio)
    assert [g["opponent_set_known"] for g in groups] == [True, False]
    assert [(g["games_cast_after_offer"], g["games_offered"]) for g in groups] == [(3, 3), (1, 5)]
    assert groups[0]["vorbehalt"] is None


def test_unknown_opponents_are_no_cohort_and_say_so_even_without_a_figure(
    studio: StudioStore,
) -> None:
    """P2-2 (#1706): the group of unknown opponents names its reservation in ``kohorte``,
    ``label`` and ``vorbehalt``; the reservation stays when the figure is left out."""
    caveat = "Gegnersatz unbekannt: mehrere Läufe, möglicherweise verschiedene Gegner"
    _add_run(studio, "r-old-1", offered=5, cast=1, opponents=None)
    _add_run(studio, "r-old-2", offered=4, cast=2, opponents=None)
    (unknown,) = _groups(studio)
    assert unknown["vorbehalt"] == caveat
    assert str(unknown["label"]).startswith(caveat)
    assert str(unknown["zahl"]["kohorte"]).startswith(caveat)  # type: ignore[index]
    # inconsistent rows (more casts than offers): no figure, the reservation stays visible
    _add_run(studio, "r-old-3", offered=1, cast=9, opponents=None)
    (unknown,) = _groups(studio)
    assert unknown["zahl"] is None
    assert unknown["vorbehalt"] == caveat


def test_the_table_size_is_an_axis_of_its_own(studio: StudioStore) -> None:
    _add_run(studio, "r-three", offered=4, cast=2, opponents=PRESET[:2])
    _add_run(studio, "r-four", offered=4, cast=4, opponents=PRESET)
    groups = _groups(studio)
    assert [g["table_size"] for g in groups] == [3, 4]
    assert [(g["games_cast_after_offer"], g["games_offered"]) for g in groups] == [(2, 4), (4, 4)]


def test_unknown_opponents_at_two_table_sizes_stay_two_groups(studio: StudioStore) -> None:
    """A row that names its table size but not its opponents (an import, say): the size is
    still an axis; the unknown set is not merged across sizes, and no size is invented."""
    _add_run(studio, "r-u3", offered=4, cast=1, opponents=None)
    _add_run(studio, "r-u4", offered=6, cast=3, opponents=None)
    _add_run(studio, "r-u?", offered=2, cast=2, opponents=None)
    with studio.connection as db:
        db.execute("UPDATE simulation_run SET table_size = 3 WHERE run_id = 'r-u3'")
        db.execute("UPDATE simulation_run SET table_size = 4 WHERE run_id = 'r-u4'")
    groups = _groups(studio)
    assert [(g["table_size"], g["games_offered"]) for g in groups] == [(3, 4), (4, 6), (None, 2)]
    assert not any(g["opponent_set_known"] for g in groups)
    one = "Gegnersatz unbekannt: ein Lauf, Gegner nicht gespeichert"
    assert [str(g["label"]) for g in groups] == [
        f"{one} · Tisch mit 3 Sitzen",
        f"{one} · Tisch mit 4 Sitzen",
        f"{one} · Tischgröße unbekannt",
    ]


def test_the_evidence_route_shows_the_groups(studio: StudioStore, tmp_path: Path) -> None:
    _add_run(studio, "r-preset", offered=10, cast=4, opponents=PRESET)
    _add_run(studio, "r-old", offered=5, cast=1, opponents=None)
    studio.close()
    client = TestClient(create_app(tmp_path / "studio"))
    body = client.get("/api/evidence", params={"commander": COMMANDER[0]}).json()
    assert body["schema"] == "studio-evidence-2"
    forest = next(c for c in body["cards"] if c["name"] == "Forest")
    groups = forest["layers"]["simulated_result"]["groups"]
    assert [(g["games_cast_after_offer"], g["games_offered"]) for g in groups] == [(4, 10), (1, 5)]


def _sim_cell_text(groups: list[dict[str, object]]) -> str:
    """Run ``simCell`` of tierliste.js in node with a text-only ``h`` and return its text."""
    import re
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    static = Path(__file__).resolve().parents[2] / "src/commander_lab/studio/static"
    script = (static / "tierliste.js").read_text(encoding="utf-8")
    found = re.search(r"^function simCell\(card\) \{.*?^\}$", script, re.M | re.S)
    assert found is not None
    program = (
        "const text = (x) => x === null || x === undefined ? '' : Array.isArray(x) ? "
        "x.map(text).join('') : typeof x === 'object' ? x.t : String(x);\n"
        "const h = (tag, props, ...kids) => ({ t: `<${tag}>` + kids.map(text).join('') });\n"
        "const nf = (n) => String(n);\n"
        "const unknown = (t) => ({ t: `?${t}` });\n"
        "const layer = (card, name) => card.layers[name];\n"
        f"{found.group(0)}\n"
        "const card = { layers: { simulated_result: { status: 'PRESENT', groups: "
        f"{json.dumps(groups)} }} }} }};\n"
        "process.stdout.write(text(simCell(card)));\n"
    )
    done = subprocess.run([node, "-e", program], capture_output=True, text=True, check=True)
    return done.stdout


def test_the_tier_cell_shows_every_group_on_its_own_and_never_a_total() -> None:
    """P2-1 (#1706): simCell lists each group with its own n/N, no sum over the groups."""
    caveat = "Gegnersatz unbekannt: mehrere Läufe, möglicherweise verschiedene Gegner"
    groups: list[dict[str, object]] = [
        {"label": "A", "games_cast_after_offer": 4, "games_offered": 10, "vorbehalt": None},
        {"label": "B", "games_cast_after_offer": 6, "games_offered": 6, "vorbehalt": None},
        {"label": caveat, "games_cast_after_offer": 1, "games_offered": 5, "vorbehalt": caveat},
    ]
    text = _sim_cell_text(groups)
    lines = text.split("<div>")[1:]
    assert lines == [
        "3 Gegnersätze (getrennt)",
        "4/10 Partien",
        "6/6 Partien",
        f"1/5 Partien ({caveat})",
    ]
    assert "11/21" not in text and "10/16" not in text  # never a total
    # a single group of unknown opponents carries its reservation in the cell itself
    one = [{"label": caveat, "games_cast_after_offer": 2, "games_offered": 3, "vorbehalt": caveat}]
    assert _sim_cell_text(one).split("<div>")[1:] == [f"2/3 Partien ({caveat})"]


def test_the_tier_page_shows_the_groups_and_never_adds_them_up() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "src/commander_lab/studio/static/tierliste.js"
    ).read_text(encoding="utf-8")
    assert "sim.totals" not in script  # the total over all runs is gone (#1688)
    assert "Gegnersätze (getrennt)" in script
    assert "StudioZahl.knoten(h, g.zahl)" in script


def test_the_pod_row_of_unknown_opponents_names_its_reservation() -> None:
    """P2-2 (#1706): app.js shows the same reservation as builder.unknown_opponents_caveat."""
    from commander_lab.studio.builder import unknown_opponents_caveat

    script = (
        Path(__file__).resolve().parents[2] / "src/commander_lab/studio/static/app.js"
    ).read_text(encoding="utf-8")
    for runs in (1, 2):
        assert f'"{unknown_opponents_caveat(runs)}"' in script
    assert "agg.known ? agg.table : unknownOpponentsCaveat(agg.runs)" in script
    assert "das ist keine Kohorte" in script
