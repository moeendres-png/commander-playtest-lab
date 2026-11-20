"""The cached and cheaper Studio figures equal the straightforward ones (differential tests).

The reference functions below are the plain implementations the figures had before they were
made cheaper; they stay here only to pin the output."""

from __future__ import annotations

import json
import random
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from statistics import median

import pytest

from commander_lab.studio import StudioStore, builder, cache, land_advisor
from commander_lab.studio.decks import RevisionCard
from commander_lab.studio.store import rebuild_corpus_deck_role

COMMANDER = "Test Commander"


def _big_store(tmp_path: Path, decks: int = 160) -> StudioStore:
    """The builder fixture plus many random source decks bound to the test commander."""
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    db = store.connection
    source_id = str(db.execute("SELECT source_id FROM corpus_deck LIMIT 1").fetchone()[0])
    oracles = [
        (str(row[0]), str(row[1]))
        for row in db.execute("SELECT oracle_id, name FROM scryfall_card ORDER BY oracle_id")
    ]
    assert len(oracles) > 20
    rng = random.Random(1404)
    role_names = ["ramp", "removal", "draw", "wipe"]
    for index, (oracle_id, _name) in enumerate(oracles):
        for role in rng.sample(role_names, rng.randint(0, 2)):
            db.execute(
                "INSERT OR IGNORE INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
                (oracle_id, role, source_id),
            )
        if index % 17 == 0:
            db.execute(
                "INSERT OR IGNORE INTO card_role(oracle_id, role, source_id) VALUES (?, 'wipe', ?)",
                (oracle_id, source_id),
            )
    for number in range(decks):
        deck_id = f"g{number:04d}"
        play_group = rng.choice(["community", "turnier_cedh", "pod_a"])
        db.execute(
            "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags,"
            " fingerprint, duplicate_of, legality_audit, source_id)"
            " VALUES (?, ?, '', 'test', ?, NULL, '', ?, NULL, '', ?)",
            (deck_id, play_group, play_group, f"fp-{deck_id}", source_id),
        )
        db.execute(
            "INSERT INTO commander_binding(kind, key, commander_name, basis)"
            " VALUES ('corpus_deck', ?, ?, 'OWNER_DECLARED')",
            (deck_id, COMMANDER),
        )
        picked = rng.sample(oracles, rng.randint(0, 25))
        total = 0
        for oracle_id, name in picked:
            quantity = rng.randint(1, 4) if rng.random() < 0.2 else 1
            total += quantity
            db.execute(
                "INSERT OR IGNORE INTO corpus_deck_card(deck_id, card_name, oracle_id, quantity,"
                " section, normalization_status) VALUES (?, ?, ?, ?, ?, 'ok')",
                (
                    deck_id,
                    name,
                    oracle_id,
                    quantity,
                    rng.choice(["main", "mainboard", "sideboard"]),
                ),
            )
        complete = rng.random() < 0.8
        db.execute(
            "INSERT INTO corpus_deck_stat(deck_id, cards, resolved, lands, creatures,"
            " nonland_mana_value, nonland_cards) VALUES (?, 99, ?, ?, ?, ?, ?)",
            (
                deck_id,
                99 if complete else 98,
                rng.randint(28, 40),
                rng.randint(5, 40),
                round(rng.random() * 200, 2),
                rng.choice([0, 55, 60, 64]),
            ),
        )
        for cohort in rng.sample(
            ["bracket:3", "bracket:4", "bracket:5", "budget"], rng.randint(0, 2)
        ):
            db.execute(
                "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)", (cohort, deck_id)
            )
    rebuild_corpus_deck_role(db)
    db.commit()
    return store


# -- reference implementations (the plain versions) -------------------------------------


def _ref_percentile(values: Sequence[float], share: float) -> float:
    """Linear-interpolation percentile, written independently of ``builder``."""
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    lower = int(position // 1)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _reference_cohort_shapes(
    store: StudioStore, commander_names: Sequence[str]
) -> list[dict[str, object]]:
    db = store.connection
    if not commander_names:
        return []
    members = builder.cohort_members(store, commander_names)
    role_names = [str(r[0]) for r in db.execute("SELECT DISTINCT role FROM card_role ORDER BY 1")]
    role_cards: dict[tuple[str, str], int] = {
        (str(r["deck_id"]), str(r["role"])): int(r["cards"])
        for r in db.execute("SELECT deck_id, role, cards FROM corpus_deck_role")
    }
    nonland_role_by_deck: dict[str, int] = {}
    if role_names:
        ids = sorted(
            {
                str(row["deck_id"])
                for group in members.values()
                for row in group
                if row["resolved"] == row["cards"]
            }
        )
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            marks = ", ".join("?" for _ in chunk)
            for row in db.execute(
                "SELECT k.deck_id, SUM(k.quantity) AS cnt "
                "FROM corpus_deck_card k "
                "JOIN (SELECT DISTINCT oracle_id FROM card_role) r ON r.oracle_id = k.oracle_id "
                "LEFT JOIN scryfall_card s ON s.oracle_id = k.oracle_id "
                f"WHERE k.deck_id IN ({marks}) AND LOWER(k.section) IN ('main', 'mainboard') "
                "AND k.quantity > 0 "
                "AND SUBSTR(COALESCE(s.type_line, ''), 1, "
                "INSTR(COALESCE(s.type_line, '') || ' // ', ' // ') - 1) NOT LIKE '%Land%' "
                "GROUP BY k.deck_id",
                chunk,
            ):
                nonland_role_by_deck[str(row["deck_id"])] = int(row["cnt"] or 0)
    shapes: list[dict[str, object]] = []
    for cohort, group in members.items():
        complete = [row for row in group if row["resolved"] == row["cards"]]
        shape: dict[str, object] = {
            "cohort": cohort,
            "decks": len(group),
            "decks_counted": len(complete),
        }
        if complete:
            for field, values in (
                ("lands", [float(row["lands"]) for row in complete]),
                ("creatures", [float(row["creatures"]) for row in complete]),
                (
                    "mana_value",
                    [
                        row["nonland_mana_value"] / row["nonland_cards"]
                        for row in complete
                        if row["nonland_cards"]
                    ],
                ),
            ):
                if values:
                    shape[field] = {
                        "median": round(median(values), 2),
                        "p25": round(_ref_percentile(values, 0.25), 2),
                        "p75": round(_ref_percentile(values, 0.75), 2),
                    }
        if complete and role_names:
            spans: dict[str, dict[str, float]] = {}
            for role in role_names:
                counts = [float(role_cards.get((str(row["deck_id"]), role), 0)) for row in complete]
                spans[role] = {
                    "median": round(median(counts), 2),
                    "p25": round(_ref_percentile(counts, 0.25), 2),
                    "p75": round(_ref_percentile(counts, 0.75), 2),
                }
            shape["roles"] = spans
            cov_counts = [
                float(nonland_role_by_deck.get(str(row["deck_id"]), 0)) for row in complete
            ]
            shape["role_coverage_median"] = round(median(cov_counts), 2)
        shapes.append(shape)
    return shapes


def _reference_source_deck_groups(
    store: StudioStore, commander_names: Sequence[str]
) -> list[dict[str, object]]:
    members = builder.cohort_members(store, commander_names)
    if not members:
        return []
    wanted = {str(row["deck_id"]) for group in members.values() for row in group}
    cards: dict[str, list[sqlite3.Row]] = {deck_id: [] for deck_id in wanted}
    ordered = sorted(wanted)
    for start in range(0, len(ordered), 500):
        chunk = ordered[start : start + 500]
        marks = ", ".join("?" for _ in chunk)
        query = (
            "SELECT k.deck_id, k.quantity, s.type_line, s.mana_cost, s.produced_mana, s.layout "
            "FROM corpus_deck_card k JOIN scryfall_card s ON s.oracle_id = k.oracle_id "
            f"WHERE k.deck_id IN ({marks}) AND LOWER(k.section) IN ('main', 'mainboard')"
        )
        for row in store.connection.execute(query, chunk):
            cards[str(row["deck_id"])].append(row)
    compact = {
        deck_id: land_advisor._compact(land_advisor.deck_profile(rows))
        for deck_id, rows in cards.items()
    }
    return [
        land_advisor.group_figures(
            cohort,
            [compact[str(row["deck_id"])] for row in group if row["resolved"] == row["cards"]],
            decks_total=len(group),
        )
        for cohort, group in members.items()
    ]


# -- the tests ----------------------------------------------------------------------------


def test_cohort_shapes_equal_the_plain_computation(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    expected = _reference_cohort_shapes(store, [COMMANDER])
    assert len(expected) >= 4  # all, play groups, named cohorts, tuned
    assert any("roles" in shape for shape in expected)
    assert builder.cohort_shapes(store, [COMMANDER]) == expected
    assert builder.cohort_shapes(store, [COMMANDER]) == expected  # the cached read
    assert builder.cohort_shapes(store, []) == []
    assert builder.cohort_shapes(store, ["Nobody"]) == _reference_cohort_shapes(store, ["Nobody"])


def test_cohort_shapes_float_types_are_unchanged(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    with_roles = [
        shape for shape in builder.cohort_shapes(store, [COMMANDER]) if shape.get("roles")
    ]
    assert with_roles
    values = [
        value
        for shape in with_roles
        for span in shape["roles"].values()  # type: ignore[attr-defined]
        for value in span.values()
    ]
    assert values
    assert {type(value) for value in values} == {float}
    assert {type(shape["role_coverage_median"]) for shape in with_roles} == {float}


def test_cohort_shapes_recompute_after_a_committed_write(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    before = builder.cohort_shapes(store, [COMMANDER])
    store.connection.execute("UPDATE corpus_deck_stat SET lands = lands + 1")
    store.connection.commit()
    after = builder.cohort_shapes(store, [COMMANDER])
    assert after != before
    assert after == _reference_cohort_shapes(store, [COMMANDER])


def test_source_deck_groups_equal_the_plain_computation(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    expected = _reference_source_deck_groups(store, [COMMANDER])
    assert len(expected) >= 4
    assert any(group["colours"] for group in expected)
    assert land_advisor.source_deck_groups(store, [COMMANDER]) == expected
    assert land_advisor.source_deck_groups(store, [COMMANDER]) == expected  # the cached read
    assert land_advisor.source_deck_groups(store, []) == []
    assert land_advisor.source_deck_groups(store, ["Nobody"]) == _reference_source_deck_groups(
        store, ["Nobody"]
    )


def test_source_deck_groups_recompute_after_a_committed_write(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    before = land_advisor.source_deck_groups(store, [COMMANDER])
    store.connection.execute("UPDATE corpus_deck_card SET quantity = quantity + 1")
    store.connection.commit()
    after = land_advisor.source_deck_groups(store, [COMMANDER])
    assert after != before
    assert after == _reference_source_deck_groups(store, [COMMANDER])


def test_source_deck_groups_with_a_null_produced_mana_stay_unknown_not_zero(
    tmp_path: Path,
) -> None:
    """``deck_profile`` tells "no card data" (NULL) from "produces nothing" (empty): the
    per-card reading of the source decks must keep that."""
    row_null = {"type_line": "Land", "mana_cost": None, "produced_mana": None, "layout": "normal"}
    row_empty = {"type_line": "Land", "mana_cost": "", "produced_mana": "", "layout": "normal"}
    for row in (row_null, row_empty):
        plain = land_advisor.deck_profile([{**row, "quantity": 2}])
        traits = land_advisor._card_traits(
            row["type_line"], row["mana_cost"], row["produced_mana"], row["layout"]
        )
        assert traits.kind == 0
        assert plain["lands"] == 2
        assert traits.colours == frozenset()
    assert land_advisor.deck_profile([{**row_null, "quantity": 1}])["lands_unknown_colours"] == 1
    assert land_advisor.deck_profile([{**row_empty, "quantity": 1}])["lands_unknown_colours"] == 0


def _plan_inputs(store: StudioStore) -> list[RevisionCard]:
    rows = store.connection.execute(
        "SELECT f.card_id FROM card_fact f JOIN scryfall_card s ON s.oracle_id = f.oracle_id "
        "WHERE s.type_line NOT LIKE '%Land%' ORDER BY f.card_id LIMIT 40"
    ).fetchall()
    cmd = store.connection.execute(
        "SELECT card_id FROM card_fact WHERE oracle_name = ?", (COMMANDER,)
    ).fetchone()
    cards = [RevisionCard(str(cmd[0]), 1, "commander")]
    cards += [RevisionCard(str(row[0])) for row in rows]
    return cards


def test_packages_and_build_plan_are_the_same_cached_or_not(tmp_path: Path) -> None:
    from commander_lab.studio import packages

    store = _big_store(tmp_path)
    cards = _plan_inputs(store)
    assert len(cards) > 10
    # An open transaction makes the cache stand aside: that is the uncached reference.
    store.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
    assert store.connection.in_transaction
    plain_packages = packages.deck_packages(store, [COMMANDER], cards, cohort="all")
    plain_plan = packages.build_plan(store, [COMMANDER], cards, cohort="all")
    store.connection.rollback()
    assert plain_packages["cohort_decks"] == 163  # the 3 fixture decks and the 160 random ones
    for _ in range(2):  # a cold and a cached read
        assert packages.deck_packages(store, [COMMANDER], cards, cohort="all") == plain_packages
        assert packages.build_plan(store, [COMMANDER], cards, cohort="all") == plain_plan
    for group in ("community", "bracket:4", "tuned"):
        store.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
        plain = packages.deck_packages(store, [COMMANDER], cards, cohort=group)
        store.connection.rollback()
        assert packages.deck_packages(store, [COMMANDER], cards, cohort=group) == plain


def test_the_combo_partner_file_is_read_once_until_it_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "spellbook_combos.json"
    path.write_text(
        json.dumps({"combos": [{"commander": "Cmdr", "cards": ["Alpha", "Beta"]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "_COMBO_PARTNERS_PATH", path)
    builder._combo_partners.clear()
    first = builder._cached_combo_partners(["Cmdr, the Test"])
    assert "alpha||beta" in first
    assert builder._cached_combo_partners(["Cmdr, the Test"]) is first
    path.write_text(
        json.dumps({"combos": [{"commander": "Cmdr", "cards": ["Alpha", "Gamma"]}]}) + "\n",
        encoding="utf-8",
    )
    changed = builder._cached_combo_partners(["Cmdr, the Test"])
    assert "alpha||gamma" in changed
    assert "alpha||beta" not in changed


def test_the_serve_warm_up_fills_the_figures_a_request_then_reads(tmp_path: Path) -> None:
    from commander_lab.studio.__main__ import _warm_caches

    store = _big_store(tmp_path)
    store.close()
    cache.invalidate()
    _warm_caches(str(tmp_path / "studio"))
    warmed = {key[0] for key, _ in cache.snapshot()}
    assert {"cohort_shapes", "land_source_groups", "layer_overview", "corpus_hits"} <= warmed
    reopened = StudioStore.open(tmp_path / "studio")
    calls: list[int] = []
    builder_shapes = builder.cohort_shapes(reopened, [COMMANDER])
    assert builder_shapes == _reference_cohort_shapes(reopened, [COMMANDER])
    assert cache.cached(reopened, ("cohort_shapes", (COMMANDER,)), lambda: calls.append(1)) is (
        builder_shapes
    )
    assert calls == []


def test_the_slow_routes_compute_once_per_store_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio import data_report, import_all
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    counts = {"layers": 0, "report": 0}
    real_layers, real_report = import_all.layer_overview, data_report.data_report

    def counting_layers(store: StudioStore, commander: str) -> dict[str, object]:
        counts["layers"] += 1
        return real_layers(store, commander)

    def counting_report(store: StudioStore, **kwargs: object) -> dict[str, object]:
        counts["report"] += 1
        return real_report(store, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(import_all, "layer_overview", counting_layers)
    monkeypatch.setattr(data_report, "data_report", counting_report)
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    first = client.get("/api/layers", params={"commander": COMMANDER}).json()
    assert client.get("/api/layers", params={"commander": COMMANDER}).json() == first
    report = client.get("/api/data-report").json()
    assert client.get("/api/data-report").json() == report
    assert counts == {"layers": 1, "report": 1}
    other = StudioStore.open(tmp_path / "studio")
    other.connection.execute("INSERT INTO meta(key, value) VALUES ('route-test', 'x')")
    other.connection.commit()
    other.close()
    assert client.get("/api/layers", params={"commander": COMMANDER}).json() == first
    client.get("/api/data-report")
    assert counts == {"layers": 2, "report": 2}  # a committed write: computed again


def test_the_strength_route_is_remembered_per_settings_and_equals_the_plain_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio import strength_view
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    calls: list[int] = []
    real = strength_view.compute

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(strength_view, "compute", counting)
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = {"commander": COMMANDER}
    first = client.post("/api/strength", json=body)
    assert first.status_code == 200
    assert client.post("/api/strength", json=body).json() == first.json()
    assert len(calls) == 1
    other = client.post("/api/strength", json={**body, "settings": {"bracket": "3"}})
    assert other.status_code in (200, 422)
    unknown = client.post("/api/strength", json={"commander": "Nobody"})
    assert unknown.status_code == 404
    assert client.post("/api/strength", json={"commander": "Nobody"}).status_code == 404


def test_cohort_shapes_equal_the_plain_computation_across_chunk_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _big_store(tmp_path)
    expected = _reference_cohort_shapes(store, [COMMANDER])
    monkeypatch.setattr(builder, "_ROLE_CHUNK", 7)  # 163 decks: many statements, uneven last one
    cache.invalidate()
    assert builder.cohort_shapes(store, [COMMANDER]) == expected


def test_the_data_report_route_shows_the_bridge_state_of_every_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    import commander_lab.bridge_qualification as bridge
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    state = ["STATE_1"]
    monkeypatch.setattr(bridge, "bridge_qualification", lambda: {"state": state[0]})
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    first = client.get("/api/data-report").json()
    state[0] = "STATE_2"  # the repository changed, the store did not
    second = client.get("/api/data-report").json()
    assert first["bridge_qualification"] == {"state": "STATE_1"}
    assert second["bridge_qualification"] == {"state": "STATE_2"}
    assert {k: v for k, v in first.items() if k != "bridge_qualification"} == {
        k: v for k, v in second.items() if k != "bridge_qualification"
    }
    assert list(first) == list(second)  # the same key order


def test_changing_the_returned_report_does_not_change_the_cached_one(tmp_path: Path) -> None:
    from commander_lab.studio.web import data_report_cached

    store = _big_store(tmp_path)
    first = data_report_cached(store)
    reference = json.loads(json.dumps(first))
    first["collection"]["cards"] = -1  # type: ignore[index]
    first["extra"] = True
    del first["roles"]
    again = data_report_cached(store)
    assert "extra" not in again
    assert json.loads(json.dumps(again)) == reference


def test_a_read_only_computation_reads_the_cache_but_adds_nothing(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    cache.invalidate()
    cache.cached(store, ("warm", 0), lambda: "kept")
    before = cache.snapshot()
    assert len(before) == 1
    with cache.read_only():
        assert cache.cached(store, ("warm", 0), lambda: "recomputed") == "kept"
        values = [cache.cached(store, ("foreign", n), lambda n=n: n) for n in range(100)]
    assert values == list(range(100))
    assert cache.snapshot() == before
    assert cache.cached(store, ("foreign", 1), lambda: "now stored") == "now stored"


def test_the_warm_up_reports_a_failing_step_in_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio import __main__ as entry

    store = _big_store(tmp_path)
    store.close()

    def broken(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom with a long message")

    monkeypatch.setattr(land_advisor, "source_deck_groups", broken)
    cache.invalidate()
    entry._warm_caches(str(tmp_path / "studio"))
    err = capsys.readouterr().err.strip().splitlines()
    assert [line for line in err if "warm-up" in line and "RuntimeError" in line]
    assert all(len(line) < 200 for line in err)
    assert "strength" in {key[0] for key, _ in cache.snapshot()}  # the route's own key is warmed


def test_a_preset_and_the_same_settings_typed_in_do_not_share_a_remembered_answer(
    tmp_path: Path,
) -> None:
    """The snapshot metadata names the profile (preset or none): the route's cache key must too."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import strength_view
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    presets = strength_view.presets()
    assert presets
    candidates = [item for item in sorted(_preset_items(presets)) if item[0] != "Ausgewogen"]
    assert candidates
    name, preset = candidates[0]
    by_preset = client.post("/api/strength", json={"commander": COMMANDER, "preset": name})
    by_settings = client.post("/api/strength", json={"commander": COMMANDER, "settings": preset})
    assert by_preset.status_code == 200 and by_settings.status_code == 200
    assert by_preset.json()["snapshot"]["profile_name"] == name
    assert by_settings.json()["snapshot"]["profile_name"] != name


def _preset_items(presets: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    for item in presets.get("presets", []):  # type: ignore[attr-defined]
        if isinstance(item, dict) and isinstance(item.get("settings"), dict):
            found.append((str(item["name"]), dict(item["settings"])))
    return found


# -- remembered answers of the read routes (#1563) ---------------------------------------


@pytest.fixture
def _fresh_answers() -> Iterator[None]:
    """Module-level memories must not leak from one test into the next."""
    from commander_lab.studio import answer_cache, sources

    def clear() -> None:
        cache.invalidate()
        answer_cache.clear()
        with sources._combo_cards_lock:
            sources._combo_cards.clear()

    clear()
    yield
    clear()


_ANSWER_ROUTES: list[tuple[str, dict[str, object], str]] = [
    ("/api/pool", {"commander": COMMANDER}, "object"),
    ("/api/pool", {"commander": COMMANDER, "strength_bracket": "3"}, "object"),
    ("/api/evidence", {"view": "commander", "commander": COMMANDER}, "object"),
    ("/api/evidence", {"view": "global"}, "object"),
    ("/api/roles/audit", {"commander": COMMANDER}, "object"),
    ("/api/roles/audit", {}, "object"),
    ("/api/universe/counted", {"commander": COMMANDER}, "list"),
    ("/api/deck-browser", {"commander": COMMANDER}, "object"),
    ("/api/deck-browser", {"q": "d", "origin": "source", "limit_decks": 5}, "object"),
    (
        "/api/deck-browser",
        {"must_contain": ["Sol Ring"], "must_not_contain": ["Forest"], "include_unowned": True},
        "object",
    ),
    ("/api/tournament-conversion", {"commander": "Test Commander"}, "object"),
]


def _plain_bytes(value: object, shape: str) -> bytes:
    """What a FastAPI route with the original return annotation sends for ``value``."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    reference = FastAPI()
    if shape == "list":

        @reference.get("/plain")
        def plain_list() -> list[dict[str, object]]:
            return value  # type: ignore[return-value]

    else:

        @reference.get("/plain")
        def plain_object() -> dict[str, object]:
            return value  # type: ignore[return-value]

    return TestClient(reference).get("/plain").content


def test_remembered_answers_are_the_bytes_the_plain_routes_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _fresh_answers: None
) -> None:
    """Every remembered route answer equals, byte for byte, what the route with its original
    return type sends for the same computed value, on the first call and from memory."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import answer_cache
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    monkeypatch.setenv("COMMANDER_LAB_TOPDECK_DIR", str(tmp_path / "topdeck"))
    computed: list[object] = []
    real_dump = answer_cache.dump

    def recording(value: object, shape: answer_cache.Shape = "object") -> bytes:
        computed.append(value)
        return real_dump(value, shape)

    monkeypatch.setattr(answer_cache, "dump", recording)
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    for path, params, shape in _ANSWER_ROUTES:
        computed.clear()
        first = client.get(path, params=params)
        assert first.status_code == 200, (path, params, first.text[:200])
        assert first.headers["content-type"] == "application/json"
        assert len(computed) == 1, (path, params)
        assert first.content == _plain_bytes(computed[0], shape), (path, params)
        again = client.get(path, params=params)
        assert computed[1:] == [], (path, params)  # served from memory
        assert again.content == first.content, (path, params)
    # Errors are not remembered and keep their status.
    assert client.get("/api/roles/audit", params={"commander": "Nobody"}).status_code == 404
    assert client.get("/api/roles/audit", params={"commander": "Nobody"}).status_code == 404
    assert client.get("/api/evidence", params={"view": "commander"}).status_code == 422


def test_a_remembered_answer_cannot_be_changed_by_what_its_computation_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _fresh_answers: None
) -> None:
    """The answer is kept as bytes: changing the computed object afterwards changes nothing."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import evidence as evidence_model
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    handed_out: list[dict[str, object]] = []
    real = evidence_model.pool_evidence

    def keeping(*args: object, **kwargs: object) -> dict[str, object]:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        handed_out.append(found)
        return found

    monkeypatch.setattr(evidence_model, "pool_evidence", keeping)
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    params = {"view": "commander", "commander": COMMANDER}
    first = client.get("/api/evidence", params=params).content
    handed_out[0]["cards"] = []
    handed_out[0]["extra"] = True
    first_json = client.get("/api/evidence", params=params).json()
    first_json["cards"] = []  # what a reader does with its answer stays its own
    assert client.get("/api/evidence", params=params).content == first
    assert len(handed_out) == 1


def test_the_remembered_figures_hand_out_copies(tmp_path: Path, _fresh_answers: None) -> None:
    """Status part, cohort sizes, combo cards and the slot catalog: changing what a caller got
    back never changes what the next caller gets."""
    from commander_lab.studio import combos, sources
    from commander_lab.studio.web import _status_store_part

    store = _big_store(tmp_path)
    status = _status_store_part(store)
    reference = json.loads(json.dumps(status))
    status["cards"] = -1
    status["source_layers"].append({"x": 1})  # type: ignore[attr-defined]
    status["freshness"]["total_sources"] = -1  # type: ignore[index]
    assert _status_store_part(store) == reference

    sizes = builder.cohort_sizes(store, [COMMANDER])
    expected_sizes = dict(sizes)
    sizes["all"] = -1
    sizes["new"] = 1
    assert builder.cohort_sizes(store, [COMMANDER]) == expected_sizes

    combo_file = tmp_path / "combos.json"
    combo_file.write_text(
        json.dumps({"combos": [{"commander": "Cmdr", "cards": ["Alpha", "Beta"]}]}),
        encoding="utf-8",
    )
    cards = sources.load_spellbook_combo_cards(combo_file, commander="Cmdr")
    cards.add("Intruder")
    cards.discard("Alpha")
    assert sources.load_spellbook_combo_cards(combo_file, commander="Cmdr") == {"Alpha", "Beta"}

    deck_ids = {"card:project:0001"}
    first = combos._card_catalog_for_slots(store, [COMMANDER], deck_ids)
    snapshot = json.loads(json.dumps(first, default=sorted))
    for items in first:
        for item in items:
            item["name"] = "changed"
            item["in_deck"] = None
        items.clear()
    second = combos._card_catalog_for_slots(store, [COMMANDER], deck_ids)
    assert json.loads(json.dumps(second, default=sorted)) == snapshot


def test_the_catalog_equals_the_plain_read(tmp_path: Path, _fresh_answers: None) -> None:
    from commander_lab.studio import combos

    store = _big_store(tmp_path)
    deck_ids = {"card:project:0001", "card:project:0101"}
    store.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
    plain = combos._card_catalog_for_slots(store, [COMMANDER], deck_ids)  # cache stands aside
    store.connection.rollback()
    for _ in range(2):
        assert combos._card_catalog_for_slots(store, [COMMANDER], deck_ids) == plain
    assert combos._card_catalog_for_slots(store, [], set()) != plain


def test_a_write_is_seen_by_the_next_remembered_answer(
    tmp_path: Path, _fresh_answers: None
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio.decks import create_revision
    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _deck

    _big_store(tmp_path).close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()
    card_id = next(card["card_id"] for card in pool["cards"] if not card["favorite"])
    browser = client.get("/api/deck-browser").json()
    status = client.get("/api/status").json()
    assert client.put(f"/api/cards/{card_id}/favorite", json={"favorite": True}).status_code == 200
    after = client.get("/api/pool", params={"commander": COMMANDER}).json()
    assert next(card for card in after["cards"] if card["card_id"] == card_id)["favorite"]
    store = StudioStore.open(tmp_path / "studio")
    create_revision(store, deck_id="cache-test", name="Cache Test", cards=_deck())
    store.close()
    changed = client.get("/api/deck-browser").json()
    assert changed != browser
    assert any(deck["deck_id"] == "cache-test" for deck in changed["decks"])
    assert client.get("/api/status").json()["decks"] == status["decks"] + 1


def test_a_changed_data_file_is_seen_by_the_next_remembered_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _fresh_answers: None
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio import evidence as evidence_model
    from commander_lab.studio.web import create_app
    from tests.unit.test_tournament_conversion_1412 import _write_deck_csv

    _big_store(tmp_path).close()
    combo_file = tmp_path / "spellbook_combos.json"
    combo_file.write_text(json.dumps({"combos": []}), encoding="utf-8")
    monkeypatch.setattr(evidence_model, "_COMBOS_PATH", combo_file)
    monkeypatch.setattr(evidence_model, "ANSWER_FILES", (combo_file,))
    topdeck = tmp_path / "topdeck"
    topdeck.mkdir()
    monkeypatch.setenv("COMMANDER_LAB_TOPDECK_DIR", str(topdeck))
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    params = {"view": "commander", "commander": COMMANDER}
    before = client.get("/api/evidence", params=params).content
    assert client.get("/api/evidence", params=params).content == before
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()
    name = str(pool["cards"][0]["name"])
    combo_file.write_text(
        json.dumps({"combos": [{"commander": COMMANDER, "cards": [name]}]}) + "\n",
        encoding="utf-8",
    )
    assert client.get("/api/evidence", params=params).content != before

    empty = client.get("/api/tournament-conversion", params={"commander": "Test Commander"})
    assert empty.json()["total_decks"] == 0
    _write_deck_csv(
        topdeck / "topdeck_test_decks.csv",
        [{"tournament": "T1", "date": "2026-01-01", "player": "P1", "cards": ["Sol Ring"]}],
    )
    filled = client.get("/api/tournament-conversion", params={"commander": "Test Commander"})
    assert filled.json()["total_decks"] == 1


def test_the_status_route_reads_the_bridge_state_on_every_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _fresh_answers: None
) -> None:
    from fastapi.testclient import TestClient

    import commander_lab.bridge_qualification as bridge
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    state = ["STATE_1"]
    monkeypatch.setattr(bridge, "bridge_qualification", lambda: {"state": state[0]})
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    first = client.get("/api/status").json()
    state[0] = "STATE_2"
    second = client.get("/api/status").json()
    assert first["bridge_qualification"] == {"state": "STATE_1"}
    assert second["bridge_qualification"] == {"state": "STATE_2"}
    assert list(first) == list(second) == [
        "bridge_qualification", "cards", "public_cards", "source_decks", "neutral_board_rows",
        "simulation_runs", "source_data_binding", "decks", "universe_profiles",
        "source_inventory", "freshness", "source_layers", "image_cache", "sources",
    ]  # fmt: skip
    assert {k: v for k, v in first.items() if k != "bridge_qualification"} == {
        k: v for k, v in second.items() if k != "bridge_qualification"
    }


def test_route_answers_have_their_own_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _fresh_answers: None
) -> None:
    """Many distinct answers push out older answers, never the warm figures; a byte budget
    caps their total size."""
    from commander_lab.studio import answer_cache

    store = _big_store(tmp_path)
    monkeypatch.setitem(cache.KIND_LIMITS, "answer", (16, 10_000))
    cache.cached(store, ("figure", 1), lambda: "warm")
    for number in range(17):
        answer_cache.json_answer(store, "probe", (number,), lambda number=number: {"n": number})
    answers = [key for key, _ in cache.snapshot() if key[0] == "answer"]
    assert len(answers) == 16
    assert [key[2] for key in answers] == [(number,) for number in range(1, 17)]
    assert any(key == ("figure", 1) for key, _ in cache.snapshot())
    big = "x" * 4_000
    for number in range(3):
        answer_cache.json_answer(store, "big", (number,), lambda: {"text": big})
    sizes = [len(value) for key, value in cache.snapshot() if key[0] == "answer"]  # type: ignore[arg-type]
    assert sum(sizes) <= 10_000
    assert any(key[:2] == ("answer", "big") and key[2] == (2,) for key, _ in cache.snapshot())
    assert any(key == ("figure", 1) for key, _ in cache.snapshot())


# -- figures kept over a known write of the Studio's own (#1561, D-1 #1612) ------------------

# A view is read through its base tables.
_VIEWS: dict[str, tuple[str, ...]] = {"card_fact": ("card", "scryfall_card")}


def _trace_reads(store: StudioStore, compute: Callable[[], object]) -> dict[str, set[str]]:
    """The tables (and columns) ``compute`` reads on ``store``'s connection, with every cached
    figure dropped first so that nothing is served from memory (SQLite authorizer)."""
    reads: dict[str, set[str]] = {}

    def authorizer(action: int, table: str | None, column: str | None, *_: object) -> int:
        if action == sqlite3.SQLITE_READ and table:
            reads.setdefault(table, set()).add(str(column))
        return sqlite3.SQLITE_OK

    cache.invalidate()
    store.connection.set_authorizer(authorizer)
    try:
        compute()
    finally:
        store.connection.set_authorizer(None)
    return reads


def _tables_by_group(tables: Iterable[str]) -> dict[cache.Group | None, set[str]]:
    """The tables per group (a view counts as its base tables); a table of no group under
    ``None``. SQLite's own tables are left out."""
    found: dict[cache.Group | None, set[str]] = {}
    for table in tables:
        if table.startswith("sqlite_"):
            continue
        for base in _VIEWS.get(table, (table,)):
            found.setdefault(cache.TABLE_GROUP.get(base), set()).add(base)
    return found


def _strength_kind(store: StudioStore) -> object:
    from commander_lab.studio.web import StrengthBody, strength_answer

    return strength_answer(store, StrengthBody(commander=COMMANDER))


# One tracer per kind: what computes exactly that figure. A narrowed kind (one that reads fewer
# than all groups) without a tracer fails ``test_every_narrowed_kind_reads_only_its_groups``.
_KIND_TRACERS: dict[str, Callable[[StudioStore], object]] = {
    "land_source_groups": lambda store: land_advisor.source_deck_groups(store, [COMMANDER]),
    "strength": _strength_kind,
    "answer:pool": lambda store: builder.pool_cards(store, [COMMANDER]),
}


def _declaration_violations(
    store: StudioStore,
    kinds: Mapping[str, cache.Kind],
    tracers: Mapping[str, Callable[[StudioStore], object]],
) -> dict[str, list[str]]:
    """Per narrowed kind: the tables its computation reads outside its declared groups (or
    that it has no tracer). Empty means every declaration is proven."""
    found: dict[str, list[str]] = {}
    for name, kind in sorted(kinds.items()):
        if kind.reads == cache.ALL:
            continue
        tracer = tracers.get(name)
        if tracer is None:
            found[name] = ["<no tracer>"]
            continue
        reads = _trace_reads(store, lambda tracer=tracer: tracer(store))
        assert reads, name  # the tracer really ran SQL
        outside = sorted(
            table
            for group, tables in _tables_by_group(reads).items()
            if group is None or group not in kind.reads
            for table in tables
        )
        if outside:
            found[name] = outside
    return found


def test_every_narrowed_kind_reads_only_its_groups(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    narrowed = {name for name, kind in cache.KINDS.items() if kind.reads != cache.ALL}
    assert narrowed == {"land_source_groups"}  # P1: only the kind proven in #1561
    assert _declaration_violations(store, cache.KINDS, _KIND_TRACERS) == {}


def test_a_kind_wrongly_declared_narrow_is_caught(tmp_path: Path) -> None:
    """Mutation counter-test: ``strength`` and the ``pool`` answer read the marks (through
    ``pool_cards``); declaring them import-only must make the proof fail, and so must a
    declaration without a tracer (#1615: an answer kind is never narrowed unproven)."""
    store = _big_store(tmp_path)
    import_only = cache.Kind(reads=frozenset({cache.Group.IMPORT}))
    kinds = {
        **cache.KINDS,
        "strength": import_only,
        "answer:pool": import_only,
        "undeclared": import_only,
    }
    violations = _declaration_violations(store, kinds, _KIND_TRACERS)
    for name in ("strength", "answer:pool"):
        assert "card_mark" in violations[name], name
        assert "card_label" in violations[name], name
    assert violations["undeclared"] == ["<no tracer>"]
    assert "land_source_groups" not in violations


def _route_writes() -> list[
    tuple[str, frozenset[cache.Group], Callable[[dict[str, object]], tuple[str, str, object]]]
]:
    """Every write route of the Studio (all 18 that reach a store write), in an order that works
    on the builder fixture: name, the groups it must write, and (method, path, body) built
    from what earlier answers returned. Deck ``probe`` is created by the first one."""
    from tests.unit.test_studio_builder import _deck

    commander = "card:project:0001"
    cards = [{"card_id": commander, "quantity": 1, "zone": "commander"}] + [
        {"card_id": f"card:project:{100 + i:04d}", "quantity": 1, "zone": "main"} for i in range(5)
    ]
    full = [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in _deck()]
    marks = frozenset({cache.Group.MARKS})
    decks = frozenset({cache.Group.DECKS})
    profiles = frozenset({cache.Group.PROFILES})
    catalog = frozenset({cache.Group.IMPORT})
    universe = f"/api/universe/profiles/probe?commander={COMMANDER.replace(' ', '%20')}"
    return [
        (
            "new_deck",
            decks,
            lambda _: ("POST", "/api/decks", {"name": "Probe", "commander_card_ids": [commander]}),
        ),
        (
            "favorite",
            marks,
            lambda _: ("PUT", "/api/cards/card:project:0101/favorite", {"favorite": True}),
        ),
        (
            "mark_excluded",
            marks,
            lambda _: (
                "PUT",
                "/api/cards/card:project:0102/mark",
                {"favorite": False, "excluded": True, "note": "probe"},
            ),
        ),
        (
            "card_labels",
            marks,
            lambda _: ("PUT", "/api/cards/card:project:0101/labels", {"labels": ["probe"]}),
        ),
        ("deck_labels", decks, lambda _: ("PUT", "/api/decks/probe/labels", {"labels": ["probe"]})),
        (
            "draft",
            decks,
            lambda _: ("PUT", "/api/decks/probe/branches/main/draft", {"cards": cards}),
        ),
        (
            "draft_card",
            decks,
            lambda _: (
                "POST",
                "/api/decks/probe/branches/main/draft/card",
                {"card_id": "card:project:0110", "delta": 1},
            ),
        ),
        ("draft_drop", decks, lambda _: ("DELETE", "/api/decks/probe/branches/main/draft", None)),
        (
            "draft_again",
            decks,
            lambda _: ("PUT", "/api/decks/probe/branches/main/draft", {"cards": cards}),
        ),
        (
            "revision",
            decks,
            lambda _: ("POST", "/api/decks/probe/revisions", {"cards": cards[:-1], "note": "x"}),
        ),
        (
            "primer",
            decks,
            lambda _: ("PUT", "/api/decks/probe/primer", {"content": "Probe primer."}),
        ),
        (
            "module_seed",
            decks,
            lambda _: ("POST", "/api/decks/probe/modules/seed", {"cards": full}),
        ),
        (
            "module_compile",
            decks,
            lambda found: (
                "POST",
                "/api/decks/probe/modules/compile",
                {
                    "module_ids": [m["module_id"] for m in found["module_seed"]["modules"]],  # type: ignore[index]
                    "save": True,
                },
            ),
        ),
        (
            "module_save",
            decks,
            lambda _: (
                "POST",
                "/api/decks/probe/modules",
                {"name": "Probe-Modul", "cards": cards[1:]},
            ),
        ),
        (
            "module_delete",
            decks,
            lambda found: (
                "DELETE",
                f"/api/decks/probe/modules/{found['module_save']['module']['module_id']}",  # type: ignore[index]
                None,
            ),
        ),
        (
            "strength_profile",
            profiles,
            lambda found: (
                "PUT",
                "/api/strength/profiles/probe",
                {"settings": found["recommended"]},
            ),
        ),
        (
            "strength_profile_delete",
            profiles,
            lambda _: ("DELETE", "/api/strength/profiles/probe", None),
        ),
        ("universe_profile", profiles, lambda _: ("PUT", universe, {})),
        (
            "universe_profile_delete",
            profiles,
            lambda _: ("DELETE", "/api/universe/profiles/probe", None),
        ),
        # An unowned ``scryfall:`` card (Zukauf-Modus): saving it adds its catalog entry to
        # ``card`` first, so these writes also write IMPORT (``_UNOWNED`` in the matrix test).
        (
            "favorite_unowned",
            marks | catalog,
            lambda _: ("PUT", f"/api/cards/{_UNOWNED[0]}/favorite", {"favorite": True}),
        ),
        (
            "mark_unowned",
            marks | catalog,
            lambda _: (
                "PUT",
                f"/api/cards/{_UNOWNED[1]}/mark",
                {"favorite": False, "excluded": True, "note": ""},
            ),
        ),
        (
            "card_labels_unowned",
            marks | catalog,
            lambda _: ("PUT", f"/api/cards/{_UNOWNED[2]}/labels", {"labels": ["probe"]}),
        ),
        (
            "revision_unowned",
            decks | catalog,
            lambda _: (
                "POST",
                "/api/decks/probe/revisions",
                {"cards": [*cards, {"card_id": _UNOWNED[3], "quantity": 1, "zone": "main"}]},
            ),
        ),
    ]


# Unowned cards known only to the Scryfall catalog, one per write of the matrix that adds one.
_UNOWNED = tuple(f"scryfall:probe-unowned-{n}" for n in range(4))


def test_the_write_matrix_keeps_exactly_the_kinds_that_read_no_written_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every write route writes exactly its declared groups (seen by an independent recorder on
    every connection, inside and outside the window) and books one proven window. Afterwards a
    kind is kept (not recomputed, the same object, equal to a plain read) exactly when none of
    its groups was written, in both directions: the narrowed ``land_source_groups`` (IMPORT),
    one probe kind per group (IMPORT through the writes of an unowned ``scryfall:`` card), and
    an undeclared kind (all groups)."""
    from types import MappingProxyType

    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _insert_scryfall

    seeded = _big_store(tmp_path)
    for card_id in _UNOWNED:
        _insert_scryfall(
            seeded,
            oracle_id=card_id.removeprefix("scryfall:"),
            name=f"Unowned {card_id[-1]}",
            colors="G",
            type_line="Creature — Elf",
        )
    seeded.connection.commit()
    seeded.close()
    written: dict[str, set[str]] = {}
    current: list[str | None] = [None]
    recorders: dict[int, Callable[..., int]] = {}
    real_open = StudioStore.open.__func__  # type: ignore[attr-defined]
    writes = (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE)

    def tracing_open(cls: type[StudioStore], folder: object = None) -> StudioStore:
        opened = real_open(cls, folder)

        def recorder(
            action: int, table: str | None, _: object, database: object, *__: object
        ) -> int:
            # every row write to the store file (the connection's temporary tables are not it)
            if (
                current[0]
                and action in writes
                and table
                and database != "temp"
                and not table.startswith("sqlite_")
            ):
                written.setdefault(current[0], set()).add(table)
            return sqlite3.SQLITE_OK

        recorders[id(opened.connection)] = recorder
        opened.connection.set_authorizer(recorder)
        return opened

    real_install = cache._install_observer

    def composed_install(
        connection: sqlite3.Connection, observer: Callable[..., int] | None
    ) -> None:
        recorder = recorders.get(id(connection))
        if observer is None or recorder is None:
            real_install(connection, observer if observer is not None else recorder)
            return

        def both(*args: object) -> int:
            recorder(*args)
            return observer(*args)  # type: ignore[no-any-return]

        real_install(connection, both)

    monkeypatch.setattr(StudioStore, "open", classmethod(tracing_open))
    monkeypatch.setattr(cache, "_install_observer", composed_install)
    probes = {
        f"probe_{group.value}": cache.Kind(reads=frozenset({group}))
        for group in (
            cache.Group.IMPORT,
            cache.Group.MARKS,
            cache.Group.DECKS,
            cache.Group.PROFILES,
            cache.Group.META,
        )
    }
    monkeypatch.setattr(cache, "KINDS", MappingProxyType({**cache.KINDS, **probes}))
    calls: dict[str, int] = {"land": 0}
    real_land = land_advisor._source_deck_groups_uncached

    def counting_land(store: StudioStore, names: Sequence[str]) -> list[dict[str, object]]:
        calls["land"] += 1
        return real_land(store, names)

    monkeypatch.setattr(land_advisor, "_source_deck_groups_uncached", counting_land)
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    found: dict[str, object] = {
        "recommended": client.get("/api/strength/presets").json()["recommended"]
    }
    routes = _route_writes()
    assert len(routes) == 23  # 18 write routes, the draft twice, 4 with an unowned card
    kept_over: dict[str, set[str]] = {}
    for name, groups, request in routes:
        reader = StudioStore.open(tmp_path / "studio")
        land = land_advisor.source_deck_groups(reader, [COMMANDER])
        held = {
            kind: cache.cached(reader, (kind,), lambda kind=kind: [kind])
            for kind in [*probes, "undeclared_probe"]
        }
        reader.close()
        before = calls["land"]
        window = cache.counters().get("* window_proven", 0)
        method, path, body = request(found)
        current[0] = name
        response = client.request(method, path, json=body)
        current[0] = None
        assert response.status_code == 200, (name, response.text[:200])
        found[name] = response.json()
        tables = _tables_by_group(written.get(name, set()))
        assert set(tables) == set(groups), (name, tables)  # exactly the declared groups
        assert cache.counters().get("* window_proven", 0) == window + 1, name
        assert "* window_undeclared" not in cache.counters(), name
        assert "* window_unproven" not in cache.counters(), name
        reader = StudioStore.open(tmp_path / "studio")
        now = land_advisor.source_deck_groups(reader, [COMMANDER])
        if cache.Group.IMPORT in groups:
            assert now is not land and calls["land"] == before + 1, name  # computed again
        else:
            assert now is land, name
            assert calls["land"] == before, name  # kept, not computed again
        kept_over[name] = set()
        for kind, value in held.items():
            again = cache.cached(reader, (kind,), lambda kind=kind: [kind])
            reads = cache.kind_of(kind).reads
            if reads & groups:
                assert again is not value, (name, kind)  # a written group: computed again
            else:
                assert again is value, (name, kind)  # no written group: kept
                kept_over[name].add(kind)
        reader.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
        assert land_advisor.source_deck_groups(reader, [COMMANDER]) == now  # plain read
        reader.connection.rollback()
        reader.close()
    # both directions were exercised: every probe was kept over some write and dropped by another
    for kind in probes:
        assert any(kind in kept for kept in kept_over.values()), kind
        if kind != "probe_meta":
            assert any(kind not in kept for kept in kept_over.values()), kind
    assert not any("undeclared_probe" in kept for kept in kept_over.values())


def _plain_groups(folder: Path) -> list[dict[str, object]]:
    reader = StudioStore.open(folder)
    try:
        reader.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
        return land_advisor.source_deck_groups(reader, [COMMANDER])
    finally:
        reader.connection.rollback()
        reader.close()


def _counting_land(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls = [0]
    real_land = land_advisor._source_deck_groups_uncached

    def counting_land(store: StudioStore, names: Sequence[str]) -> list[dict[str, object]]:
        calls[0] += 1
        return real_land(store, names)

    monkeypatch.setattr(land_advisor, "_source_deck_groups_uncached", counting_land)
    return calls


def _groups(folder: Path) -> list[dict[str, object]]:
    reader = StudioStore.open(folder)
    try:
        return land_advisor.source_deck_groups(reader, [COMMANDER])
    finally:
        reader.close()


def _foreign_sql(folder: Path, statement: str) -> None:
    other = sqlite3.connect(folder / "studio.sqlite3")
    other.execute(statement)
    other.commit()
    other.close()


def test_a_foreign_commit_or_an_import_is_never_served_from_a_kept_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative tests: a direct SQL write from another connection between two requests, one
    inside the write window of a favourite write, one just before that window (I3 a), one the
    counter rule cannot see (only ``data_version`` can), and an import all drop the figure."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import catalog
    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _write_csv

    folder = tmp_path / "studio"
    _big_store(tmp_path).close()
    client = TestClient(create_app(folder), headers={"X-Studio": "1"})
    calls = _counting_land(monkeypatch)
    cache.invalidate()

    def favourite(value: bool) -> None:
        url = "/api/cards/card:project:0101/favorite"
        assert client.put(url, json={"favorite": value}).status_code == 200

    # 1. Direct SQL between two requests: a source deck leaves the commander.
    first = _groups(folder)
    _foreign_sql(
        folder, "DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0000'"
    )
    after_sql = _groups(folder)
    assert calls[0] == 2
    assert after_sql == _plain_groups(folder)
    assert after_sql != first

    # 2. A foreign commit inside the window of a favourite write: nothing is kept.
    _groups(folder)
    real_set = builder.set_favorite

    def favourite_with_a_foreign_write(
        store: StudioStore, card_id: str, favorite: bool
    ) -> dict[str, object]:
        found = real_set(store, card_id, favorite)
        _foreign_sql(
            folder, "DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0001'"
        )
        return found

    monkeypatch.setattr(builder, "set_favorite", favourite_with_a_foreign_write)
    before = calls[0]
    favourite(True)
    window = _groups(folder)
    assert calls[0] == before + 1  # computed again
    assert window == _plain_groups(folder)
    monkeypatch.setattr(builder, "set_favorite", real_set)

    # 3. A foreign commit after the last read and before the window (I3 a): the window's own
    # proof must not cover it.
    kept = _groups(folder)
    _foreign_sql(
        folder, "DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0002'"
    )
    before = calls[0]
    favourite(False)
    fresh = _groups(folder)
    assert calls[0] == before + 1
    assert fresh == _plain_groups(folder) != kept

    # 4. Inside the window: the route's own commit, a second own commit that changes no page
    # (an UPDATE to the same value: counted, file counter +0) and a foreign commit. The counter
    # rule adds up (+2 for 2 counted commits); only ``data_version`` sees the foreign one.
    kept = _groups(folder)

    def favourite_with_a_hidden_foreign_write(
        store: StudioStore, card_id: str, favorite: bool
    ) -> dict[str, object]:
        found = real_set(store, card_id, favorite)
        store.connection.execute(
            "UPDATE card_mark SET favorite = favorite WHERE card_id = ?", (card_id,)
        )
        store.connection.commit()
        _foreign_sql(
            folder, "DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0003'"
        )
        return found

    monkeypatch.setattr(builder, "set_favorite", favourite_with_a_hidden_foreign_write)
    header = (folder / "studio.sqlite3").read_bytes()[24:28]
    before = calls[0]
    cache_counters = cache.counters()
    favourite(True)
    rise = int.from_bytes((folder / "studio.sqlite3").read_bytes()[24:28]) - int.from_bytes(header)
    assert rise == 2  # what the counter rule expects for two counted commits
    assert (
        cache.counters().get("* window_unproven", 0)
        == cache_counters.get("* window_unproven", 0) + 1
    )
    fresh = _groups(folder)
    assert calls[0] == before + 1
    assert fresh == _plain_groups(folder) != kept
    monkeypatch.setattr(builder, "set_favorite", real_set)

    # 5. An import (a cohort over the commander's decks) after a kept write.
    favourite(False)
    kept = _groups(folder)
    importer = StudioStore.open(folder)
    picked = [{"deck_id": f"g{n:04d}"} for n in range(10, 60)]
    catalog.import_cohort(importer, _write_csv(tmp_path / "picked.csv", picked), cohort="bracket:4")
    importer.close()
    imported = _groups(folder)
    assert imported == _plain_groups(folder)
    assert imported != kept


def test_an_update_to_the_same_value_keeps_the_figures_correct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A window whose only commit changes no page (``UPDATE`` to the same value): the figure
    stays equal to a plain read, whichever way the window is booked (and the booking is named)."""
    folder = tmp_path / "studio"
    _big_store(tmp_path).close()
    calls = _counting_land(monkeypatch)
    cache.invalidate()
    kept = _groups(folder)
    writer = StudioStore.open(folder)
    with cache.write(writer, {cache.Group.META}):
        writer.connection.execute("UPDATE meta SET value = value WHERE key = 'schema_version'")
        writer.connection.commit()
    writer.close()
    booked = {key: n for key, n in cache.counters().items() if key.startswith("* window_")}
    assert booked == {"* window_unchanged": 1}  # the file did not change: nothing to do
    assert _groups(folder) is kept
    assert calls[0] == 1
    assert kept == _plain_groups(folder)


def test_nothing_is_kept_from_a_wal_store_or_after_a_failed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app

    folder = tmp_path / "studio"
    _big_store(tmp_path).close()
    client = TestClient(create_app(folder), headers={"X-Studio": "1"})
    calls = _counting_land(monkeypatch)
    cache.invalidate()
    _groups(folder)
    # an unknown card: the write fails, the store is unchanged, the entry simply stays valid
    assert client.put("/api/cards/nope/favorite", json={"favorite": True}).status_code == 404
    _groups(folder)
    assert calls[0] == 1
    # an unknown deck inside the window: nothing written, and still nothing stale
    assert client.put("/api/decks/nope/primer", json={"content": "x"}).status_code == 404
    _groups(folder)
    assert calls[0] == 1
    wal = sqlite3.connect(folder / "studio.sqlite3")
    assert wal.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    wal.close()
    _groups(folder)
    before = calls[0]
    unproven = cache.counters().get("* window_unproven", 0)
    assert (
        client.put("/api/cards/card:project:0101/favorite", json={"favorite": True}).status_code
        == 200
    )
    _groups(folder)
    assert calls[0] == before + 1  # WAL: the origin cannot be proven, everything is dropped
    assert cache.counters().get("* window_unproven", 0) == unproven + 1


def test_the_deck_browser_answer_is_kept_per_label_and_card_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1615 point 1: ``label`` and ``limit_cards`` are part of the remembered answer's key."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import similar_decks
    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    seen: list[tuple[object, object]] = []
    real = similar_decks.browse_decks

    def counting(store: StudioStore, **kwargs: object) -> dict[str, object]:
        seen.append((kwargs.get("label"), kwargs.get("limit_cards")))
        return real(store, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(similar_decks, "browse_decks", counting)
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    asked = [{}, {"label": "probe"}, {"limit_cards": 1}, {"label": "probe", "limit_cards": 1}]
    for params in asked + asked:
        assert client.get("/api/deck-browser", params=params).status_code == 200
    assert seen == [("", 60), ("probe", 60), ("", 1), ("probe", 1)]  # each once, then kept
