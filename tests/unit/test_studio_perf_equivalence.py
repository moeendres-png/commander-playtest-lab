"""The cached and cheaper Studio figures equal the straightforward ones (differential tests).

The reference functions below are the plain implementations the figures had before they were
made cheaper; they stay here only to pin the output."""

from __future__ import annotations

import json
import random
import sqlite3
from collections.abc import Callable, Sequence
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
    warmed = {key[1] for key in cache._entries}
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
    before = dict(cache._entries)
    assert len(before) == 1
    with cache.read_only():
        assert cache.cached(store, ("warm", 0), lambda: "recomputed") == "kept"
        values = [cache.cached(store, ("foreign", n), lambda n=n: n) for n in range(100)]
    assert values == list(range(100))
    assert dict(cache._entries) == before
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
    assert "strength" in {key[1] for key in cache._entries}  # the route's own key is warmed


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


# -- figures carried over a known user-state write (#1561) -------------------------------


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


def _strength_kind(store: StudioStore) -> object:
    from commander_lab.studio.web import StrengthBody, strength_answer

    return strength_answer(store, StrengthBody(commander=COMMANDER))


# One tracer per declared kind: what computes exactly that figure. A declared kind without a
# tracer fails ``test_every_import_only_kind_reads_no_user_state``.
_IMPORT_ONLY_TRACERS: dict[str, Callable[[StudioStore], object]] = {
    "land_source_groups": lambda store: land_advisor.source_deck_groups(store, [COMMANDER]),
}


def _import_only_violations(
    store: StudioStore,
    kinds: frozenset[str],
    tracers: dict[str, Callable[[StudioStore], object]],
) -> dict[str, list[str]]:
    """Per declared kind: the user-state tables its computation reads (or that it has no
    tracer). Empty means every declaration is proven."""
    found: dict[str, list[str]] = {}
    for kind in sorted(kinds):
        tracer = tracers.get(kind)
        if tracer is None:
            found[kind] = ["<no tracer>"]
            continue
        reads = _trace_reads(store, lambda tracer=tracer: tracer(store))
        assert reads, kind  # the tracer really ran SQL
        touched = sorted(set(reads) & cache.USER_STATE_TABLES)
        if touched:
            found[kind] = touched
    return found


def test_every_import_only_kind_reads_no_user_state(tmp_path: Path) -> None:
    store = _big_store(tmp_path)
    assert cache.IMPORT_ONLY  # the whitelist is not empty by accident
    assert _import_only_violations(store, cache.IMPORT_ONLY, _IMPORT_ONLY_TRACERS) == {}


def test_a_kind_wrongly_declared_import_only_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation counter-test: ``strength`` reads the marks (through ``pool_cards``); declaring
    it import-only must make the proof fail, and so must a declaration without a tracer."""
    store = _big_store(tmp_path)
    monkeypatch.setattr(cache, "IMPORT_ONLY", cache.IMPORT_ONLY | {"strength", "undeclared"})
    tracers = {**_IMPORT_ONLY_TRACERS, "strength": _strength_kind}
    violations = _import_only_violations(store, cache.IMPORT_ONLY, tracers)
    assert "card_mark" in violations["strength"]
    assert "card_label" in violations["strength"]
    assert violations["undeclared"] == ["<no tracer>"]
    assert "land_source_groups" not in violations


def _wrapped_writes() -> list[tuple[str, str, str, dict[str, object] | None]]:
    """Every write route that runs inside ``cache.user_state_write``, with a valid body for the
    builder fixture (deck ``probe`` is created by the first one)."""
    commander = "card:project:0001"
    cards = [{"card_id": commander, "quantity": 1, "zone": "commander"}] + [
        {"card_id": f"card:project:{100 + i:04d}", "quantity": 1, "zone": "main"} for i in range(5)
    ]
    return [
        ("new_deck", "POST", "/api/decks", {"name": "Probe", "commander_card_ids": [commander]}),
        ("favorite", "PUT", "/api/cards/card:project:0101/favorite", {"favorite": True}),
        (
            "mark_excluded",
            "PUT",
            "/api/cards/card:project:0102/mark",
            {"favorite": False, "excluded": True, "note": "probe"},
        ),
        ("card_labels", "PUT", "/api/cards/card:project:0101/labels", {"labels": ["probe"]}),
        ("deck_labels", "PUT", "/api/decks/probe/labels", {"labels": ["probe"]}),
        ("draft", "PUT", "/api/decks/probe/branches/main/draft", {"cards": cards}),
        (
            "draft_card",
            "POST",
            "/api/decks/probe/branches/main/draft/card",
            {"card_id": "card:project:0110", "delta": 1},
        ),
        ("draft_drop", "DELETE", "/api/decks/probe/branches/main/draft", None),
        ("draft_again", "PUT", "/api/decks/probe/branches/main/draft", {"cards": cards}),
        ("revision", "POST", "/api/decks/probe/revisions", {"cards": cards[:-1], "note": "x"}),
        ("primer", "PUT", "/api/decks/probe/primer", {"content": "Probe primer."}),
    ]


def test_the_write_matrix_carries_only_the_declared_figures_and_stays_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each wrapped write writes only user-state tables, none of them read by a declared kind;
    afterwards the declared figure is carried (not recomputed) and equals a fresh computation,
    while every undeclared figure is computed again."""
    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    written: dict[str, set[str]] = {}
    current: list[str | None] = [None]
    real_open = StudioStore.open.__func__  # type: ignore[attr-defined]

    def tracing_open(cls: type[StudioStore], folder: object = None) -> StudioStore:
        opened = real_open(cls, folder)

        def authorizer(action: int, table: str | None, *_: object) -> int:
            writes = (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE)
            if current[0] and action in writes and table and not table.startswith("sqlite_"):
                written.setdefault(current[0], set()).add(table)
            return sqlite3.SQLITE_OK

        opened.connection.set_authorizer(authorizer)
        return opened

    monkeypatch.setattr(StudioStore, "open", classmethod(tracing_open))
    calls = {"land": 0, "strength": 0}
    real_land = land_advisor._source_deck_groups_uncached

    def counting_land(store: StudioStore, names: Sequence[str]) -> list[dict[str, object]]:
        calls["land"] += 1
        return real_land(store, names)

    monkeypatch.setattr(land_advisor, "_source_deck_groups_uncached", counting_land)
    cache.invalidate()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    declared_reads: set[str] = set()
    probe = StudioStore.open(tmp_path / "studio")
    for kind in cache.IMPORT_ONLY:
        declared_reads |= set(
            _trace_reads(probe, lambda kind=kind: _IMPORT_ONLY_TRACERS[kind](probe))
        )
    probe.close()
    cache.invalidate()
    for name, method, path, body in _wrapped_writes():
        reader = StudioStore.open(tmp_path / "studio")
        groups = land_advisor.source_deck_groups(reader, [COMMANDER])
        cache.cached(reader, ("undeclared_probe",), lambda: calls.__setitem__("strength", 1))
        reader.close()
        before = calls["land"]
        current[0] = name
        response = client.request(method, path, json=body)
        current[0] = None
        assert response.status_code == 200, (name, response.text[:200])
        assert written.get(name), name
        assert written[name] <= cache.USER_STATE_TABLES, (name, written[name])
        assert not written[name] & declared_reads, (name, written[name] & declared_reads)
        reader = StudioStore.open(tmp_path / "studio")
        carried = land_advisor.source_deck_groups(reader, [COMMANDER])
        assert calls["land"] == before, name  # carried over, not computed again
        assert carried is groups
        calls["strength"] = 0
        cache.cached(reader, ("undeclared_probe",), lambda: calls.__setitem__("strength", 1))
        assert calls["strength"] == 1, name  # an undeclared figure is computed again
        reader.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
        assert land_advisor.source_deck_groups(reader, [COMMANDER]) == carried  # plain read
        reader.connection.rollback()
        reader.close()


def test_a_foreign_commit_or_an_import_is_never_served_from_a_carried_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative tests: a direct SQL write from another connection between two requests, one
    inside the write window of a user-state write, and an import all drop the figure."""
    from fastapi.testclient import TestClient

    from commander_lab.studio import catalog
    from commander_lab.studio.web import create_app
    from tests.unit.test_studio_builder import _write_csv

    _big_store(tmp_path).close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    calls = [0]
    real_land = land_advisor._source_deck_groups_uncached

    def counting_land(store: StudioStore, names: Sequence[str]) -> list[dict[str, object]]:
        calls[0] += 1
        return real_land(store, names)

    monkeypatch.setattr(land_advisor, "_source_deck_groups_uncached", counting_land)
    cache.invalidate()

    def groups() -> list[dict[str, object]]:
        reader = StudioStore.open(tmp_path / "studio")
        try:
            return land_advisor.source_deck_groups(reader, [COMMANDER])
        finally:
            reader.close()

    def plain() -> list[dict[str, object]]:
        reader = StudioStore.open(tmp_path / "studio")
        try:
            reader.connection.execute("INSERT INTO meta(key, value) VALUES ('pending', 'x')")
            return land_advisor.source_deck_groups(reader, [COMMANDER])
        finally:
            reader.connection.rollback()
            reader.close()

    # 1. Direct SQL between two requests: a source deck leaves the commander.
    first = groups()
    other = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
    other.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0000'")
    other.commit()
    other.close()
    after_sql = groups()
    assert calls[0] == 2
    assert after_sql == plain()
    assert after_sql != first

    # 2. A foreign commit inside the window of a favourite write: nothing is carried.
    groups()
    real_set = builder.set_favorite

    def favourite_with_a_foreign_write(
        store: StudioStore, card_id: str, favorite: bool
    ) -> dict[str, object]:
        found = real_set(store, card_id, favorite)
        foreign = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
        foreign.execute(
            "DELETE FROM commander_binding WHERE kind = 'corpus_deck' AND key = 'g0001'"
        )
        foreign.commit()
        foreign.close()
        return found

    monkeypatch.setattr(builder, "set_favorite", favourite_with_a_foreign_write)
    before = calls[0]
    assert (
        client.put("/api/cards/card:project:0101/favorite", json={"favorite": True}).status_code
        == 200
    )
    window = groups()
    assert calls[0] == before + 1  # computed again
    assert window == plain()
    monkeypatch.setattr(builder, "set_favorite", real_set)

    # 3. An import (a cohort over the commander's decks) after a carried write.
    assert (
        client.put("/api/cards/card:project:0101/favorite", json={"favorite": False}).status_code
        == 200
    )
    carried = groups()
    importer = StudioStore.open(tmp_path / "studio")
    picked = [{"deck_id": f"g{n:04d}"} for n in range(10, 60)]
    catalog.import_cohort(importer, _write_csv(tmp_path / "picked.csv", picked), cohort="bracket:4")
    importer.close()
    imported = groups()
    assert imported == plain()
    assert imported != carried


def test_nothing_is_carried_from_a_wal_store_or_after_a_failed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app

    _big_store(tmp_path).close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    calls = [0]
    real_land = land_advisor._source_deck_groups_uncached

    def counting_land(store: StudioStore, names: Sequence[str]) -> list[dict[str, object]]:
        calls[0] += 1
        return real_land(store, names)

    monkeypatch.setattr(land_advisor, "_source_deck_groups_uncached", counting_land)
    cache.invalidate()

    def groups() -> None:
        reader = StudioStore.open(tmp_path / "studio")
        land_advisor.source_deck_groups(reader, [COMMANDER])
        reader.close()

    groups()
    # an unknown card: the write fails, the store is unchanged, the entry simply stays valid
    assert client.put("/api/cards/nope/favorite", json={"favorite": True}).status_code == 404
    groups()
    assert calls[0] == 1
    # an unknown deck inside the wrapped block: no carry, and still nothing stale
    assert client.put("/api/decks/nope/primer", json={"content": "x"}).status_code == 404
    groups()
    assert calls[0] == 1
    wal = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
    assert wal.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    wal.close()
    groups()
    before = calls[0]
    assert (
        client.put("/api/cards/card:project:0101/favorite", json={"favorite": True}).status_code
        == 200
    )
    groups()
    assert calls[0] == before + 1  # WAL: the origin cannot be proven, everything is dropped
