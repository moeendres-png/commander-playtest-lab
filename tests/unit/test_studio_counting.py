"""Numbers of the deck builder and the tier list: one counting rule, honest unknowns.

Synthetic data only. Each test pins one defect the Owner found in the shown numbers.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, evidence, universe, universe_view
from commander_lab.studio import store as store_module
from commander_lab.studio.data_report import data_report
from commander_lab.studio.store import COUNTED_SECTIONS
from commander_lab.studio.web import create_app
from tests.unit.studio_synth import add_card, add_deck, add_signal, make_store

HEADER = {"X-Studio": "1"}
CMD = "Cmd A"
OTHER = "Cmd B"


def _basic_store() -> StudioStore:
    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    add_card(store, OTHER, type_line="Legendary Creature — Test")
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        add_card(store, name)
    return store


# ---------- item 1: cohort families ----------


def _bracket_store() -> StudioStore:
    store = _basic_store()
    for index in range(3):
        add_deck(store, f"b3-{index}", ["Alpha", "Beta"], cohorts=["bracket:3", "source:edhrec"])
    for index in range(2):
        add_deck(
            store,
            f"b4-{index}",
            ["Alpha", "Gamma"],
            cohorts=["bracket:4", "source:moxfield"],
            platform="moxfield",
        )
    return store


def test_cohorts_of_one_family_are_alternatives_different_families_narrow() -> None:
    store = _bracket_store()
    both = universe.resolve_universe(store, {"cohorts": ["bracket:3", "bracket:4"]})
    assert len(both) == 5  # ticking two brackets used to give 0 decks
    assert len(universe.resolve_universe(store, {"cohorts": ["bracket:3"]})) == 3
    narrowed = universe.resolve_universe(
        store, {"cohorts": ["bracket:3", "bracket:4", "source:moxfield"]}
    )
    assert len(narrowed) == 2  # families bracket (OR) and source (AND)
    assert universe.cohort_family("bracket:3") == "bracket"
    assert universe.cohort_family("plain") == "plain"


def test_an_empty_universe_is_an_explicit_state_with_a_reason() -> None:
    store = _bracket_store()
    spec = {"cohorts": ["bracket:3", "source:moxfield"]}  # no deck is in both
    universe.save_profile(store, "leer", spec)
    decks = universe.universe_decks(store, profile="leer", commander_names=[CMD])
    assert decks["denominator"] == 0 and decks["empty"] is True
    assert decks["empty_reason"] == universe.FILTERS_EXCLUDE_ALL
    summary = universe_view.profile_summary(store, "leer", commander_names=[CMD])
    assert summary["empty"] is True and summary["empty_reason"] == universe.FILTERS_EXCLUDE_ALL
    spread = universe_view.pool_spread(store, "leer", commander_names=[CMD])
    assert spread["universe"]["empty"] is True
    assert {card["reason"] for card in spread["cards"]} == {universe_view.UNIVERSE_EMPTY}
    universe.save_profile(store, "voll", {"cohorts": ["bracket:3", "bracket:4"]})
    full = universe_view.profile_summary(store, "voll", commander_names=[CMD])
    assert full["empty"] is False and full["empty_reason"] is None
    no_decks = universe_view.profile_summary(store, "voll", commander_names=["Nobody"])
    assert no_decks["empty"] is True
    assert no_decks["empty_reason"] == universe.NO_COMMANDER_DECKS


# ---------- item 2: report per commander ----------


def test_data_report_counts_universes_per_commander_set_without_a_pooled_figure() -> None:
    store = _basic_store()
    for index in range(3):
        add_deck(store, f"a{index}", ["Alpha"], commanders=[CMD])
    for index in range(2):
        add_deck(store, f"b{index}", ["Beta"], commanders=[OTHER])
    add_deck(store, "loose", ["Gamma"], commanders=[CMD], bind=False)
    universe.save_profile(store, "alle", {})
    report = data_report(store)
    detail = report["universes"]["details"][0]  # type: ignore[index]
    per = detail["per_commander"]
    assert sorted(entry["denominator"] for entry in per) == [2, 3]
    assert len({entry["snapshot_id"] for entry in per}) == 2
    assert "denominator" not in detail and "snapshot_id" not in detail  # no pooled figure


# ---------- item 3: unknown is not zero ----------


def test_pool_distinguishes_zero_hits_from_unknown() -> None:
    store = _basic_store()
    add_deck(store, "d1", ["Alpha"], cohorts=["bracket:3"])
    add_deck(store, "d2", ["Beta"], cohorts=["bracket:4"])
    pool = builder.pool_cards(store, [CMD])
    cards = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert cards["Alpha"]["decks_known"] is True
    assert cards["Alpha"]["decks"] == {"all": 1, "g": 1, "bracket:3": 1, "bracket:4": 0}
    # No deck names Delta: its count is unknown, not 0/2 (``decks`` stays {} for old readers).
    assert cards["Delta"]["decks_known"] is False and cards["Delta"]["decks"] == {}


def test_evidence_corpus_items_flag_an_unknown_card(tmp_path: Path) -> None:
    store = _basic_store()
    add_deck(store, "d1", ["Alpha"])
    result = evidence.pool_evidence(store, [CMD])
    cards = {card["name"]: card for card in result["cards"]}  # type: ignore[union-attr]
    known = [i for i in cards["Alpha"]["layers"]["observed_deck"]["items"] if i["kind"] == "corpus"]
    unknown = [
        i for i in cards["Delta"]["layers"]["observed_deck"]["items"] if i["kind"] == "corpus"
    ]
    assert known[0]["decks"] == 1 and known[0]["decks_known"] is True
    assert unknown[0]["decks_known"] is False and unknown[0]["of"] == 1


# ---------- item 4 and 5: one binding rule, one section list, one co-occurrence ----------


def test_universe_and_builder_apply_the_same_commander_rule() -> None:
    store = _basic_store()
    add_deck(store, "pair", ["Alpha"], commanders=[CMD, OTHER])
    add_deck(store, "solo", ["Alpha"], commanders=[CMD])
    for names in ([CMD], [OTHER], [CMD, OTHER]):
        in_universe = len(universe.resolve_universe(store, {"commanders": names}))
        assert in_universe == builder.cohort_sizes(store, names)["all"], names


def test_all_views_count_the_same_sections() -> None:
    assert COUNTED_SECTIONS == universe.COUNTED_SECTIONS == store_module.COUNTED_SECTIONS
    store = _basic_store()
    add_deck(store, "d1", ["Alpha"], other_sections={"maybeboard": ["Delta"], "cuts": ["Gamma"]})
    pool = builder.pool_cards(store, [CMD])
    cards = {card["name"]: card for card in pool["cards"]}  # type: ignore[union-attr]
    assert cards["Delta"]["decks_known"] is False and cards["Gamma"]["decks_known"] is False
    assert cards["Alpha"]["decks"]["all"] == 1  # type: ignore[index]
    universe.save_profile(store, "alle", {})
    spread = universe_view.pool_spread(store, "alle", commander_names=[CMD])["cards"]
    by_name = {c["name"]: c for c in spread}
    assert by_name["Delta"]["hits"] is None and by_name["Alpha"]["hits"] == 1


def test_role_counts_use_the_counted_sections() -> None:
    store = _basic_store()
    add_deck(store, "d1", ["Alpha"], other_sections={"maybeboard": ["Delta"]})
    db = store.connection
    db.execute("UPDATE corpus_deck_card SET oracle_id = 'o-' || card_name")
    db.execute(
        "INSERT INTO card_role(oracle_id, role, source_id) VALUES ('o-Alpha', 'ramp', 'src:synth')"
    )
    db.execute(
        "INSERT INTO card_role(oracle_id, role, source_id) VALUES ('o-Delta', 'removal', 'src:synth')"
    )
    store_module.rebuild_corpus_deck_role(db)
    roles = {row[0]: row[1] for row in db.execute("SELECT role, cards FROM corpus_deck_role")}
    assert roles == {"ramp": 1}  # the maybeboard card carries no role count


def test_cooccurrence_is_one_implementation_with_merged_spellings() -> None:
    store = _basic_store()
    # "alpha" (other case) and "Alpha" are one card; Beta is listed as its double-faced name.
    add_deck(store, "d1", ["Alpha", "Beta"], cohorts=["bracket:3"])
    add_deck(store, "d2", ["alpha", "Beta"], cohorts=["bracket:3"])
    add_deck(store, "d3", ["Gamma", "Beta"], cohorts=["bracket:3"])
    add_deck(store, "d4", ["Gamma"], cohorts=["bracket:3"])
    universe.save_profile(store, "alle", {})
    alpha = "card:synth:alpha"
    view = universe_view.card_cooccurrence(store, "alle", alpha, commander_names=[CMD])
    in_builder = builder.card_cooccurrence(store, alpha, [CMD])
    assert view["decks_with_card"] == in_builder["card_decks"] == 2
    beta_view = next(p for p in view["pairs"] if p["card_name"] == "Beta")
    beta_builder = next(c for c in in_builder["cards"] if c["name"] == "Beta")  # type: ignore[union-attr]
    assert beta_view["decks_together"] == beta_builder["both_hits"] == 2
    # Lift uses the merged count of the partner in the whole universe: Beta is in 3 of 4
    # decks, P(Beta | Alpha) = 2/2 -> lift 1 / (3/4).
    assert beta_view["lift"] == pytest.approx(1 / (3 / 4))
    # The same card reached through its other spelling: "alpha" in a deck counts like "Alpha".
    gamma = (
        next(p for p in view["pairs"] if p["card_name"] == "Gamma")
        if any(p["card_name"] == "Gamma" for p in view["pairs"])
        else None
    )
    assert gamma is None  # Gamma never shares a deck with Alpha


def test_lift_does_not_use_raw_name_partner_counts() -> None:
    store = _basic_store()
    add_deck(store, "d1", ["Alpha", "Beta"])
    add_deck(store, "d2", ["Alpha", "beta"])  # the partner under a second spelling
    add_deck(store, "d3", ["BETA"])
    add_deck(store, "d4", ["Gamma"])
    universe.save_profile(store, "alle", {})
    view = universe_view.card_cooccurrence(store, "alle", "card:synth:alpha", commander_names=[CMD])
    pair = next(p for p in view["pairs"] if p["card_name"] == "Beta")
    # Beta (all spellings) is in 3 of 4 decks. A raw-name count would give 1 of 4 and a
    # lift of 4.0 instead of 1 / (3/4).
    assert pair["decks_together"] == 2
    assert pair["lift"] == pytest.approx(1 / 0.75)


# ---------- item 7: EDHREC inclusion from card_signal everywhere ----------


@pytest.fixture
def web_store(tmp_path: Path) -> Iterator[tuple[TestClient, StudioStore]]:
    store = make_store(tmp_path / "studio")
    add_card(store, CMD, type_line="Legendary Creature — Test")
    for name in ("Alpha", "Beta"):
        add_card(store, name)
    add_deck(store, "d1", ["Alpha"])
    add_signal(store, CMD, "edhrec_commander_inclusion", "Alpha", 75, 100)
    store.connection.commit()
    with TestClient(create_app(tmp_path / "studio"), headers=HEADER) as client:
        yield client, store


def test_commander_inclusion_is_read_from_card_signal_in_every_view(
    web_store: tuple[TestClient, StudioStore],
) -> None:
    client, _store = web_store
    pool = client.get("/api/pool", params={"commander": CMD}).json()
    alpha = next(card for card in pool["cards"] if card["name"] == "Alpha")
    assert alpha["edhrec"]["pct"] == pytest.approx(75.0)
    assert (alpha["edhrec"]["numerator"], alpha["edhrec"]["denominator"]) == (75, 100)
    assert alpha["edhrec"]["source"] == "card_signal" and alpha["edhrec"]["source_id"]
    beta = next(card for card in pool["cards"] if card["name"] == "Beta")
    assert beta["edhrec"] is None  # no row: unknown
    listing = client.get("/api/evidence", params={"view": "commander", "commander": CMD}).json()
    item = next(c for c in listing["cards"] if c["name"] == "Alpha")
    widest = item["layers"]["observed_deck"]["edhrec"]["widest_inclusion"]
    assert widest["value"] == pytest.approx(75.0) and widest["denominator"] == 100
    assert widest["source"] == "card_signal"
    detail = client.get(
        f"/api/cards/{alpha['card_id']}/evidence", params={"view": "commander", "commander": CMD}
    ).json()["card"]
    rows = detail["layers"]["observed_deck"]["edhrec_rows"]
    assert rows and rows[0]["source"] == "card_signal" and rows[0]["denominator"] == 100
    beta_item = next(c for c in listing["cards"] if c["name"] == "Beta")
    assert beta_item["layers"]["observed_deck"]["edhrec"]["widest_inclusion"] is None


def test_inclusion_falls_back_to_observations_when_no_signal(tmp_path: Path) -> None:
    store = _basic_store()
    add_deck(store, "d1", ["Alpha"])
    db = store.connection
    db.execute(
        "INSERT INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('observation_cohort', 'edhrec:chulane', ?, 'TEST')",
        (CMD,),
    )
    db.execute(
        "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
        "denominator, data_class, snapshot, source_id) VALUES "
        "('card:synth:alpha', 'Alpha', 'inclusion_pct', 'edhrec:chulane', 40.0, 40, 100, "
        "'OBSERVED', '2026-10-01', 'src:synth')"
    )
    pool = builder.pool_cards(store, [CMD])
    alpha = next(c for c in pool["cards"] if c["name"] == "Alpha")  # type: ignore[union-attr]
    assert alpha["edhrec"]["pct"] == 40.0 and alpha["edhrec"]["source"] == "observation"
    add_signal(store, CMD, "edhrec_commander_inclusion", "Alpha", 75, 100)
    pool = builder.pool_cards(store, [CMD])
    alpha = next(c for c in pool["cards"] if c["name"] == "Alpha")  # type: ignore[union-attr]
    assert alpha["edhrec"]["source"] == "card_signal"  # one function, signal first


# ---------- group 3: one tier concept ----------


def test_spread_levels_carry_their_own_names_next_to_the_stable_keys() -> None:
    from commander_lab.studio import tiers

    assert [tiers.LEVEL_NAMES[k] for k in ("S", "A", "B", "C", "D", "U", "F")] == [
        "sehr häufig", "häufig", "gelegentlich", "selten", "sehr selten", "unbekannt", "Filterkarte",
    ]  # fmt: skip
    store = _bracket_store()
    universe.save_profile(store, "alle", {"min_universe": 1})
    spread = universe_view.pool_spread(store, "alle", commander_names=[CMD])
    for card in spread["cards"]:
        assert card["level_name"] == tiers.LEVEL_NAMES[card["level"]]
    rows = tiers.tiers_for_universe(
        universe.inclusion(store, profile="alle", commander_names=[CMD]),
        universe_snapshot="s",
        params=tiers.TierParams(min_universe=1),
    )
    assert all(row["level_name"] == tiers.LEVEL_NAMES[row["tier"]] for row in rows)


def test_the_policy_text_does_not_contradict_the_page() -> None:
    rule = str(evidence.TIER_POLICY["rule"])
    assert "strength index" in rule and "not a measured strength" in rule
    assert "so every card is UNRATED" not in rule


# ---------- item 6: counts describe the shown set ----------


# ---------- light marks route ----------


def test_marks_route_reads_marks_without_the_pool(tmp_path: Path) -> None:
    store = make_store(tmp_path / "studio")
    card_id = add_card(store, "Alpha")
    store.connection.commit()
    store.close()
    with TestClient(create_app(tmp_path / "studio"), headers=HEADER) as client:
        assert client.get("/api/marks").json() == {}
        body = {"favorite": True, "excluded": False, "note": "n"}
        client.put(f"/api/cards/{card_id}/mark", json=body)
        assert client.get("/api/marks").json() == {card_id: body}


# ---------- R1, R4, R5 ----------


@pytest.fixture
def rich(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, str]]]:
    store = make_store(tmp_path / "studio")
    add_card(store, CMD, type_line="Legendary Creature — Test")
    ids = {name: add_card(store, name) for name in ("Alpha", "Beta", "Gamma", "Delta")}
    for index in range(40):
        cards = ["Alpha", "Beta"] + (["Gamma"] if index < 10 else [])
        add_deck(store, f"d{index}", cards, cohorts=["bracket:3"])
    add_deck(store, "other", ["Delta"], commanders=[OTHER], bind=True)
    for index, name in enumerate(("Alpha", "Beta", "Gamma")):
        add_signal(store, CMD, "edhrec_commander_inclusion", name, 80 - 20 * index, 100)
    universe.save_profile(store, "alle", {"min_universe": 5})
    store.connection.commit()
    store.close()
    with TestClient(create_app(tmp_path / "studio"), headers=HEADER) as client:
        yield client, ids


def _numbers(client: TestClient) -> dict[str, object]:
    strength_body = {"commander": CMD, "settings": {"universe_profile": "alle"}}
    pool = client.get("/api/pool", params={"commander": CMD, "profile": "alle"}).json()
    for card in pool["cards"]:  # the marks themselves are of course visible in the pool
        for key in ("favorite", "excluded", "note"):
            card.pop(key)
    return {
        "strength": client.post("/api/strength", json=strength_body).json(),
        "spread": client.get(
            "/api/universe/spread", params={"profile": "alle", "commander": CMD}
        ).json(),
        "pool": pool,
        "evidence": client.get(
            "/api/evidence", params={"view": "commander", "commander": CMD}
        ).json(),
    }


def test_r1_marks_never_change_a_number_or_an_order(
    rich: tuple[TestClient, dict[str, str]],
) -> None:
    client, ids = rich
    before = _numbers(client)
    for name, card_id in ids.items():
        body = {"favorite": name != "Delta", "excluded": name == "Beta", "note": f"Notiz {name}"}
        assert client.put(f"/api/cards/{card_id}/mark", json=body).status_code == 200
    after = _numbers(client)
    assert before == after  # byte-for-byte: values and order of every card


def test_r4_deck_figures_need_a_commander(rich: tuple[TestClient, dict[str, str]]) -> None:
    client, ids = rich
    assert client.get("/api/universe/spread", params={"profile": "alle"}).status_code == 422
    url = f"/api/cards/{ids['Alpha']}/cooccurrence"
    assert client.get(url, params={"profile": "alle"}).status_code == 422
    assert client.get("/api/pool").status_code == 422
    other = client.get(
        "/api/universe/spread", params={"profile": "alle", "commander": OTHER}
    ).json()
    mine = client.get("/api/universe/spread", params={"profile": "alle", "commander": CMD}).json()
    assert other["universe"]["denominator"] == 1 and mine["universe"]["denominator"] == 40
    assert other["universe"]["snapshot_id"] != mine["universe"]["snapshot_id"]


def test_r5_decks_can_be_filtered_by_cards_they_must_contain(
    rich: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ids = rich
    url = "/api/universe/profiles/nur-gamma"
    saved = client.put(
        url, params={"commander": CMD}, json={"must_contain": ["Gamma"], "min_universe": 5}
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["denominator"] == 10 and body["excluded_by_card_filter"] == 30
    assert body["spec"]["must_contain"] == ["Gamma"]
    spread = client.get(
        "/api/universe/spread", params={"profile": "nur-gamma", "commander": CMD}
    ).json()
    by_name = {card["name"]: card for card in spread["cards"]}
    assert by_name["Gamma"]["filter_card"] is True  # the filter card itself is not a figure
    assert by_name["Alpha"]["hits"] == 10 and by_name["Alpha"]["denominator"] == 10


# ---------- group 4: one resolution per request, cache invalidation ----------


def _count_calls(monkeypatch: pytest.MonkeyPatch, module: object, name: str) -> list[int]:
    original = getattr(module, name)
    calls: list[int] = []

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, counting)
    return calls


def test_a_request_resolves_the_universe_once(
    rich: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import cache

    client, _ids = rich
    resolved = _count_calls(monkeypatch, universe, "_resolve")
    built = _count_calls(monkeypatch, universe_view, "_build_context")
    body = {"commander": CMD, "settings": {"universe_profile": "alle"}}
    cache.invalidate()
    assert client.post("/api/strength", json=body).status_code == 200
    # The profile has no date or card filter: its universe is one spec, resolved once, and
    # the context (spread of every card) is built once although the request reads the
    # summary and the spread.
    assert len(resolved) == 1 and len(built) == 1
    assert client.post("/api/strength", json=body).status_code == 200
    assert len(resolved) == 1 and len(built) == 1  # the second request is served from memory
    cache.invalidate()
    resolved.clear()
    built.clear()
    pool = client.get("/api/pool", params={"commander": CMD, "profile": "alle"})
    assert pool.status_code == 200 and len(built) == 1 and len(resolved) == 1


def test_the_cache_follows_every_write(
    rich: tuple[TestClient, dict[str, str]], tmp_path: Path
) -> None:
    client, _ids = rich
    params = {"profile": "alle", "commander": CMD}
    assert client.get("/api/universe/spread", params=params).json()["universe"]["denominator"] == 40
    store = StudioStore.open(tmp_path / "studio")
    add_deck(store, "extra", ["Alpha"], cohorts=["bracket:3"])
    store.connection.commit()
    store.close()
    assert client.get("/api/universe/spread", params=params).json()["universe"]["denominator"] == 41
    # A profile write (through the API) changes the next answer as well.
    client.put("/api/universe/profiles/alle", params={"commander": CMD}, json={"min_universe": 100})
    again = client.get("/api/universe/spread", params=params).json()
    assert again["universe"]["min_universe"] == 100 and again["universe"]["below_min_universe"]


def test_an_uncommitted_change_is_never_served_stale() -> None:
    from commander_lab.studio import cache

    store = StudioStore.in_memory()
    assert cache.store_stamp(store) is None  # an in-memory store is never cached
    calls: list[int] = []
    assert cache.cached(store, ("k",), lambda: calls.append(1) or len(calls)) == 1
    assert cache.cached(store, ("k",), lambda: calls.append(1) or len(calls)) == 2
