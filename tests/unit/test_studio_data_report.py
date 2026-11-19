"""Counts-only data report (Refs #1182). All data here is synthetic."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, roles
from commander_lab.studio.__main__ import main
from commander_lab.studio.data_report import data_report, role_fingerprint
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_roles_import import FILLER, FOREST, RAT, _file

TODAY = date(2026, 11, 11)


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _section(report: dict[str, object], name: str) -> dict[str, object]:
    section = report[name]
    assert isinstance(section, dict)
    return section


def test_report_counts_the_filled_store_with_denominators(studio: StudioStore) -> None:
    report = data_report(studio, today=TODAY)
    collection = _section(report, "collection")
    identities = collection["identities"]
    assert isinstance(identities, int)
    assert identities > 0
    assert collection["with_scryfall_facts"] == {"count": 77, "of": identities}
    corpus = _section(report, "corpus")
    assert corpus["decks"] == 4
    assert corpus["marked_duplicate_of_another"] == {"count": 1, "of": 4}
    assert corpus["card_rows_without_oracle_id"] == {"count": 1, "of": corpus["card_rows"]}
    assert corpus["decks_without_card_rows"] == {"count": 0, "of": 4}
    assert corpus["decks_without_recorded_part"] == {"count": 0, "of": 4}
    assert corpus["mainboard_not_99_cards"] == {"count": 4, "of": 4}  # synthetic decks are short
    assert _section(report, "observations")["rows"] == 0
    assert _section(report, "roles")["collection_with_any_role"] == {
        "count": 0,
        "of": collection["with_oracle_id"]["count"],  # type: ignore[index]
    }
    assert "pilot_knowledge_for_collection" in report["not_measured_here"]  # type: ignore[operator]


def test_report_contains_no_names_or_notes(studio: StudioStore) -> None:
    studio.connection.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
        "SELECT card_id, 1, 0, 'private note text', '2026-11-11' FROM card LIMIT 1"
    )
    text = json.dumps(data_report(studio, today=TODAY))
    # Changed with the commanders section (Refs #1205): the commander name is the key every
    # pool size and signal count is bound to, so it appears; no other card name does.
    for forbidden in ("Forest", "Swarm Rat", "private note text", "http"):
        assert forbidden not in text
    marks = _section(data_report(studio, today=TODAY), "marks")
    assert marks["favorites"]["count"] == 1  # type: ignore[index]
    assert marks["with_note"]["count"] == 1  # type: ignore[index]


def test_an_unknown_snapshot_time_is_unknown_not_fresh(studio: StudioStore) -> None:
    facts = _section(data_report(studio, today=TODAY), "scryfall_facts")
    assert facts["age_days"] is None
    assert facts["stale"] is None
    studio.connection.execute(
        "UPDATE source SET snapshot_date = '2026-10-01' "
        "WHERE source_id IN (SELECT source_id FROM scryfall_card)"
    )
    facts = _section(data_report(studio, today=TODAY), "scryfall_facts")
    assert facts["snapshot_date"] == "2026-10-01"
    assert facts["age_days"] == 41
    assert facts["stale"] is True


def test_unknown_observation_times_and_small_denominators_are_counted(
    studio: StudioStore,
) -> None:
    source = studio.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    rows = [
        ("Forest", None, 10, "EDHREC"),
        ("Forest", "2026-11-01T00:00:00Z", 500, "EDHREC"),
        ("Forest", "", None, "EDHREC"),
    ]
    for name, snapshot, denominator, data_class in rows:
        studio.connection.execute(
            "INSERT INTO observation(card_name, metric, cohort, value, numerator, denominator, "
            "data_class, snapshot, source_id) VALUES (?, 'inclusion', 'c', 0.5, 1, ?, ?, ?, ?)",
            (name, denominator, data_class, snapshot, source),
        )
    observations = _section(data_report(studio, today=TODAY), "observations")
    assert observations["rows"] == 3
    assert observations["time_unknown"] == {"count": 2, "of": 3}
    assert observations["denominator_missing"] == {"count": 1, "of": 3}
    assert observations["denominator_below_threshold"] == {"threshold": 30, "count": 1, "of": 2}


def test_role_fingerprint_shows_an_import_and_ignores_a_repeat(
    studio: StudioStore, tmp_path: Path
) -> None:
    empty = role_fingerprint(studio.connection)
    full = _file(tmp_path, "wug.json", {"ramp": [FOREST, FILLER], "removal": [RAT]})
    roles.import_roles(studio, full)
    after_first = role_fingerprint(studio.connection)
    assert after_first != empty
    roles.import_roles(studio, full)
    assert role_fingerprint(studio.connection) == after_first
    report_roles = _section(data_report(studio, today=TODAY), "roles")
    assert report_roles["fingerprint"] == after_first
    assert report_roles["by_origin"] == {roles.ORIGIN_TAGGER: {"claims": 3, "cards": 3}}
    assert report_roles["collection_with_tagger_based_role"]["count"] == 3  # type: ignore[index]
    partial = _file(
        tmp_path,
        "part.json",
        {"ramp": [RAT]},
        mode=roles.PARTIAL_INCREMENTAL,
        key="extra",
    )
    roles.import_roles(studio, partial)
    after_partial = role_fingerprint(studio.connection)
    assert after_partial != after_first
    scopes_before = after_first["card_role_claim_by_scope"]
    scopes_after = after_partial["card_role_claim_by_scope"]
    assert isinstance(scopes_before, dict)
    assert isinstance(scopes_after, dict)
    assert set(scopes_after) == set(scopes_before) | {f"{roles.ORIGIN_TAGGER}/extra"}
    assert {k: v for k, v in scopes_after.items() if k in scopes_before} == scopes_before
    assert (
        _section(data_report(studio, today=TODAY), "roles")["collection_cards_per_role"][  # type: ignore[index]
            "ramp"
        ]
        == 3
    )


def test_command_prints_json_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    store = StudioStore.open(data)
    _fill(store, tmp_path)
    before = role_fingerprint(store.connection)
    store.close()
    assert main(["--data", str(data), "data-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "studio-data-report-1"
    assert report["roles"]["fingerprint"] == before


def test_report_counts_universes_without_naming_profiles_or_cards(
    studio: StudioStore,
) -> None:
    from commander_lab.studio import universe

    universe.save_profile(studio, "geheim-profil", {"must_contain": ["Forest"]})
    universe.save_profile(studio, "geheim-profil", {"must_contain": ["Forest"]})
    universe.save_profile(studio, "zweites", {})
    report = data_report(studio, today=TODAY)
    section = _section(report, "universes")
    assert section["profiles"] == 2
    assert section["model_version"] == "counted-spread-1"
    details = section["details"]
    assert isinstance(details, list) and len(details) == 2
    by_version = sorted(details, key=lambda entry: entry["version"])  # type: ignore[index]
    assert by_version[-1]["version"] == 2  # the re-saved profile
    filtered = next(
        entry
        for entry in details
        if entry["spec_dimensions"]["must_contain_cards"] == 1  # type: ignore[index]
    )
    # Deliberately changed with the per-commander report (Refs #1205): a profile is counted
    # once per commander that has bound decks, never over all commanders at once.
    (entry,) = filtered["per_commander"]  # type: ignore[index]
    counted = universe.inclusion(
        studio, profile="geheim-profil", card_names=[], commander_names=entry["commanders"]
    )
    assert entry["denominator"] == counted["denominator"]
    assert entry["excluded_by_card_filter"] == counted["excluded_by_card_filter"]
    assert entry["snapshot_id"] == universe.snapshot_id(
        studio, profile="geheim-profil", commander_names=entry["commanders"]
    )
    text = json.dumps(report)
    for forbidden in ("geheim-profil", "zweites", "Forest"):
        assert forbidden not in text


def test_report_gives_pool_sizes_unknown_legality_and_signal_coverage_per_commander(
    studio: StudioStore, tmp_path: Path
) -> None:
    from commander_lab.studio import builder, signals
    from tests.unit.test_studio_strength import COMMANDER, _write_signals

    _write_signals(tmp_path / "signals")
    signals.import_signals(studio, tmp_path / "signals", commander=COMMANDER)
    pool = builder.pool_cards(studio, [COMMANDER])["cards"]
    assert isinstance(pool, list)
    before = data_report(studio, today=TODAY)
    section = _section(before, "commanders")
    entry = next(item for item in section["details"] if item["commander"] == COMMANDER)  # type: ignore[attr-defined]
    assert entry["pool"]["legal_cards"] == len(pool)
    assert entry["pool"]["excluded_legality_unknown"] == 0
    # one scryfall-linked card without a legality and one collection card of unknown
    # legality: both leave the pool and are reported as unknown, not as illegal
    studio.connection.execute(
        "UPDATE scryfall_card SET commander_legality = 'unknown' WHERE name = 'Filler 05'"
    )
    source = studio.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    studio.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, commander_legal, "
        "source_id) VALUES ('card:test:unk', NULL, 'Unchecked Card', 'C', NULL, ?)",
        (source,),
    )
    studio.connection.execute(
        "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
        "available_lower_bound, quantity_exact, source_id) VALUES ('card:test:unk', 1, 1, 0, 1, 1, ?)",
        (source,),
    )
    studio.connection.commit()
    after = data_report(studio, today=TODAY)
    commanders = _section(after, "commanders")
    entry = next(item for item in commanders["details"] if item["commander"] == COMMANDER)  # type: ignore[attr-defined]
    assert entry["pool"]["legal_cards"] == len(pool) - 1
    assert entry["pool"]["excluded_legality_unknown"] == 2
    assert commanders["legality_unknown_in_collection"] == 2
    signal_rows = entry["signals"]
    inclusion = signal_rows["edhrec_commander_inclusion"]
    assert inclusion["scope"] == "commander" and inclusion["rows"] == 9
    assert inclusion["pool_cards_with_value"] == 8  # Filler 05 left the pool: unknown legality
    assert inclusion["pool_size"] == entry["pool"]["legal_cards"]
    assert signal_rows["edhrec_commander_synergy"]["rows"] == 9
    assert (
        signal_rows["edhrec_commander_synergy"]["pool_cards_with_value"] == 7
    )  # no value for one more
    assert signal_rows["edhrec_global_inclusion"]["scope"] == "independent"
    # the second commander of the signal files has rows but no collection card: no pool
    other = next(item for item in commanders["details"] if item["commander"] == "Other Commander")  # type: ignore[attr-defined]
    assert other["in_collection"] is False and other["pool"] is None
    assert other["signals"]["edhrec_commander_inclusion"]["rows"] == 2
    text = json.dumps(after)
    for card_name in ("Filler 00", "Forest", "Swarm Rat", "Unchecked Card"):
        assert card_name not in text  # counts only, no collection card name


def test_commander_sweep_reads_the_light_pool_and_the_signal_rows_once(
    studio: StudioStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1562: the per-commander sweep gives the same figures without rebuilding the builder
    pool or re-reading the signal rows per commander."""
    from commander_lab.studio import builder, signals, strength_view
    from tests.unit.test_studio_strength import COMMANDER, _write_signals

    _write_signals(tmp_path / "signals")
    signals.import_signals(studio, tmp_path / "signals", commander=COMMANDER)
    db = studio.connection
    source = db.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    # Rows that raise alarms: a commander-scoped signal without values, an independent one
    # whose counts are all zero, and a commander only reachable with surrounding spaces.
    db.executemany(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, numerator, "
        "denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            *(
                (COMMANDER, signals.SIGNAL_SYNERGY, f"Nul {i}", None, None, None, source)
                for i in range(12)
            ),
            *(("", signals.SIGNAL_GLOBAL, f"Zero {i}", 0.0, 0, 50, source) for i in range(120)),
            *(
                ("Spaced One", signals.SIGNAL_INCLUSION, f"Nul {i}", None, None, 9, source)
                for i in range(3)
            ),
        ],
    )
    db.commit()

    # The light pool is the builder pool's card set (ids, names, order) and commander ids.
    full = builder.pool_cards(studio, [COMMANDER], with_signals=False)
    light = builder.pool_members(studio, [COMMANDER])
    cards = full["cards"]
    assert isinstance(cards, list) and cards
    assert [(c["card_id"], c["name"]) for c in cards] == [
        (row["card_id"], row["oracle_name"]) for row in light
    ]
    assert full["commander_ids"] == builder.commander_identity(studio, [COMMANDER])[1]

    # The shared rows give the alarms the per-commander read gives, for every name.
    shared = signals.store_signal_rows_by_commander(studio)
    names = [*report_names(studio), " Spaced One ", "", "  ", "Nobody"]
    fired = 0
    for name in names:
        alone = signals.compute_store_signal_rate_alarms(studio, commander=name)
        assert (
            signals.compute_store_signal_rate_alarms(
                studio, commander=name, rows_by_commander=shared
            )
            == alone
        ), name
        fired += len(alone)
    assert fired > len(names)  # the independent alarm for every name, plus own ones

    expected = data_report(studio, today=TODAY)
    sent: list[str] = []
    db.set_trace_callback(sent.append)

    def no_full_pool(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("signal_coverage must not build the builder pool")

    monkeypatch.setattr(strength_view, "pool_cards", no_full_pool)
    try:
        again = data_report(studio, today=TODAY)
    finally:
        db.set_trace_callback(None)
    assert json.dumps(again, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert not [sql for sql in sent if "FROM card_signal WHERE commander_name IN" in sql]
    assert not [sql for sql in sent if "FROM card_role ORDER BY role" in sql]


def report_names(store: StudioStore) -> list[str]:
    from commander_lab.studio.data_report import _commander_names

    return _commander_names(store.connection)


def test_data_report_includes_exact_gc_band_crosstab_and_declared_bracket_origins(
    studio: StudioStore,
) -> None:
    db = studio.connection
    # Stamp a Scryfall snapshot date and mark 4 cards as Game Changers.
    db.execute(
        "UPDATE source SET snapshot_date = '2026-11-16' "
        "WHERE source_id IN (SELECT DISTINCT source_id FROM scryfall_card)"
    )
    # A complete list: every card is marked (0 or 1), so no deck is unknown for NULLs.
    db.execute("UPDATE scryfall_card SET game_changer = 0")
    db.execute(
        "UPDATE scryfall_card SET game_changer = 1 "
        "WHERE name IN ('Filler 01', 'Filler 02', 'Filler 03', 'Filler 04')"
    )
    # Attach explicit bracket cohorts to two of the deduplicated corpus decks.
    deck_ids = [
        str(row[0])
        for row in db.execute(
            "SELECT deck_id FROM corpus_deck WHERE duplicate_of IS NULL ORDER BY deck_id"
        )
    ]
    assert len(deck_ids) == 3
    db.execute("DELETE FROM corpus_cohort WHERE cohort LIKE 'bracket:%'")
    db.execute("INSERT INTO corpus_cohort(cohort, deck_id) VALUES ('bracket:2', ?)", (deck_ids[0],))
    db.execute("INSERT INTO corpus_cohort(cohort, deck_id) VALUES ('bracket:4', ?)", (deck_ids[1],))
    # Give deck_ids[1] two Game Changers and deck_ids[2] (no bracket) four Game Changers.
    db.executemany(
        "INSERT OR REPLACE INTO corpus_deck_card"
        "(deck_id, card_name, oracle_id, quantity, section, normalization_status) "
        "VALUES (?, ?, NULL, 1, 'mainboard', 'UNRESOLVED')",
        [
            (deck_ids[1], "Filler 01"),
            (deck_ids[1], "Filler 02"),
            (deck_ids[2], "Filler 01"),
            (deck_ids[2], "Filler 02"),
            (deck_ids[2], "Filler 03"),
            (deck_ids[2], "Filler 04"),
        ],
    )
    db.commit()

    report = data_report(studio, today=TODAY)
    ct = _section(report, "gc_band_crosstab")
    assert ct["total_decks"] == 3
    assert ct["list_date"] == "2026-11-16"
    assert ct["provenance"] == (
        "regelabgeleitet aus Deckliste und Game-Changer-Liste (Markierung vom 2026-11-16)"
    )
    assert ct["marking_status"] == "complete"
    assert "kein Bracket" in str(ct["disclaimer"])
    rows = ct["rows"]
    assert isinstance(rows, dict)
    every_row = ("gc_band:0", "gc_band:1-3", "gc_band:4+", "gc_band:unknown")
    assert sum(int(rows[band]["total"]) for band in every_row) == 3
    assert rows["gc_band:0"]["total"] == 1
    assert rows["gc_band:0"]["by_bracket"]["bracket:2"] == 1
    assert rows["gc_band:1-3"]["total"] == 1
    assert rows["gc_band:1-3"]["by_bracket"]["bracket:4"] == 1
    # deck_ids[2] holds four Game Changers but also the fixture's "Unknown Card", which no
    # scryfall row resolves: its band is unknown (counted as unresolved), never silently 4+.
    assert rows["gc_band:4+"]["total"] == 0
    assert rows["gc_band:unknown"]["total"] == 1
    assert rows["gc_band:unknown"]["by_bracket"]["ohne_bracket"] == 1
    assert rows["gc_band:unknown"]["decks_with_unresolved"] == 1
    assert rows["gc_band:unknown"]["unresolved_cards"] == 1
    assert ct["decks_with_unresolved"] == 1 and ct["unresolved_cards"] == 1
    origins = ct["declared_bracket_origins"]
    assert isinstance(origins, dict) and origins
    assert sum(int(item["decks_total"]) for item in origins.values()) == 3
    assert sum(int(item["decks_with_bracket"]) for item in origins.values()) == 2
    assert sum(int(item["decks_without_bracket"]) for item in origins.values()) == 1
    # Strictly counts only: no card names or URLs leak into the report.
    text = json.dumps(report)
    for forbidden in ("Filler 00", "Filler 01", "http"):
        assert forbidden not in text

    # NULL markings (an older cache): every deck is unknown in the report, never gc_band:0.
    db.execute("UPDATE scryfall_card SET game_changer = NULL")
    db.commit()
    unknown = _section(data_report(studio, today=TODAY), "gc_band_crosstab")
    assert unknown["marking_status"] == "missing"
    assert unknown["rows"]["gc_band:unknown"]["total"] == 3  # type: ignore[index]
    assert unknown["rows"]["gc_band:0"]["total"] == 0  # type: ignore[index]
    assert "keine Game-Changer-Markierung" in str(unknown["provenance"])
