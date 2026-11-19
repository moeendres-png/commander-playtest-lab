"""Counts-only data report (Refs #1182). All data here is synthetic."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, roles
from commander_lab.studio.__main__ import main
from commander_lab.studio.data_report import data_report, role_fingerprint
from commander_lab.studio.store import DataClass
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


def test_source_status_shows_each_non_deck_source_with_a_date_or_unknown(
    studio: StudioStore,
) -> None:
    """#1545: every source that is not a single deck file shows a date and age or "unbekannt"."""
    studio.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="dated.csv",
        sha256="a" * 64,
        snapshot_date="2026-11-01",
    )
    studio.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="undated.csv", sha256="b" * 64
    )
    studio.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="not-a-date.csv",
        sha256="c" * 64,
        snapshot_date="universe:abc:12",
    )
    studio.connection.commit()
    status = _section(data_report(studio, today=TODAY), "source_status")
    details = {str(item["title"]): item for item in status["details"]}  # type: ignore[attr-defined]
    assert details["dated.csv"]["snapshot_date"] == "2026-11-01"
    assert details["dated.csv"]["age_days"] == 10
    assert details["undated.csv"]["snapshot_date"] == "unbekannt"
    assert details["undated.csv"]["age_days"] == "unbekannt"
    assert details["not-a-date.csv"]["snapshot_date"] == "unbekannt"
    assert details["not-a-date.csv"]["snapshot_value_not_a_date"] is True
    for item in status["details"]:  # type: ignore[attr-defined]
        assert item["snapshot_date"] and item["age_days"] != ""  # never an empty output
    total = status["date_known"]["of"]  # type: ignore[index]
    assert total == len(status["details"])  # type: ignore[arg-type]
    assert status["date_known"]["count"] + status["date_unknown"] == total  # type: ignore[index,operator]
    assert {"undated.csv", "not-a-date.csv"} <= set(status["date_unknown_titles"])  # type: ignore[arg-type]
    deck_sources = studio.connection.execute(
        "SELECT COUNT(DISTINCT source_id) FROM corpus_deck"
    ).fetchone()[0]
    assert status["deck_file_sources"]["total"] == deck_sources > 0  # type: ignore[index]
    # deck-file sources are a group of their own: none of them is a detail row, the rest is
    deck_titles = {
        str(r[0])
        for r in studio.connection.execute(
            "SELECT title FROM source WHERE source_id IN (SELECT source_id FROM corpus_deck)"
        )
    }
    assert not deck_titles & {str(i["title"]) for i in status["details"]}  # type: ignore[attr-defined]
    all_sources = studio.connection.execute("SELECT COUNT(*) FROM source").fetchone()[0]
    assert len(status["details"]) + deck_sources == all_sources  # type: ignore[arg-type]
    # their stored date is the author's save date: never reported as a retrieval date
    decks = status["deck_file_sources"]
    assert decks["retrieval_date"] == "unbekannt"  # type: ignore[index]
    assert "author's save date" in str(decks["note"])  # type: ignore[index]
    assert "date_known" not in decks  # type: ignore[operator]
    assert "nicht im Store erfasst" in str(status["licence_and_access"])
    assert "url" not in json.dumps(status).lower().replace("address_stored", "")


def test_readme_retrieval_date_is_read_from_the_folder_readme(tmp_path: Path) -> None:
    from commander_lab.studio.provenance import README_NAME, readme_retrieval_date

    (tmp_path / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n"
        "| `sig_{1..2}.csv` | 5 Zeilen, Stand 2026-01-01 | Abruf 2026-11-11/12 |\n"
        "| `glob_{core,cedh}_*.csv` | x | Abruf 2026-11-15 (Erneuerung; Erstabruf 2026-11-11/12) |\n"
        "| `count.csv` | x | Zählung über alle Schichten, 2026-11-12 |\n"
        "| `build.jsonl` | x | MTGJSON AllPrintings (Build 2026-11-11) |\n"
        "| `filtered.jsonl` | x | Bulk, gefiltert auf die Sammlung, 2026-11-12 |\n"
        "| `two.csv` | x | Abruf 2026-11-11, Abruf 2026-11-15 |\n"
        "| `bad.csv` | x | Abruf 2026-13-45 |\n"
        "| `nodate.csv` | x | Seite ohne Datum |\n",
        encoding="utf-8",
    )
    # a window yields its first day: everything in the file is at least that fresh
    assert readme_retrieval_date(tmp_path / "sig_2.csv") == "2026-11-11"
    assert readme_retrieval_date(tmp_path / "sig_3.csv") is None
    # the current retrieval counts, the first retrieval ("Erstabruf") does not
    assert readme_retrieval_date(tmp_path / "glob_cedh_2.csv") == "2026-11-15"
    # a count, build or filter date is not a retrieval date
    assert readme_retrieval_date(tmp_path / "count.csv") is None
    assert readme_retrieval_date(tmp_path / "build.jsonl") is None
    assert readme_retrieval_date(tmp_path / "filtered.jsonl") is None
    assert readme_retrieval_date(tmp_path / "two.csv") is None  # ambiguous
    assert readme_retrieval_date(tmp_path / "bad.csv") is None  # not a calendar date
    assert readme_retrieval_date(tmp_path / "nodate.csv") is None
    assert readme_retrieval_date(tmp_path / "unlisted.csv") is None
    assert readme_retrieval_date(tmp_path / "sub" / "sig_1.csv") is None  # no README there


def test_committed_readme_dates_are_retrieval_dates_only() -> None:
    from commander_lab.studio.provenance import readme_retrieval_date

    folder = Path(__file__).resolve().parents[2] / "data" / "research" / "deckbuilder_1655"
    expected = {
        "commander_card_signals_2.csv": "2026-11-11",
        "commander_bracket_signals_core_1.csv": "2026-11-12",
        "card_global_signals.csv": "2026-11-15",
        "spellbook_card_links.csv": "2026-11-11",
        "coverage_matrix_1655.csv": None,  # "Zählung", not a retrieval
        "mtgjson_printings_1655_1.jsonl": None,  # "Build", not a retrieval
        "card_rulings_1655.jsonl": None,  # filter date without "Abruf"
    }
    assert {name: readme_retrieval_date(folder / name) for name in expected} == expected


def test_gap_matrix_classes_sum_to_the_pool_and_name_denominators(
    studio: StudioStore, tmp_path: Path
) -> None:
    from commander_lab.studio.gap_matrix import build_gap_matrix, classify
    from tests.unit.test_studio_strength import COMMANDER

    assert classify([0, 1, 4, 5, 29, 30, 99, 100, None]) == {
        "in_no_deck": 1,
        "in_1_to_4_decks": 2,
        "in_5_to_29_decks": 2,
        "in_30_to_99_decks": 2,
        "in_100_or_more_decks": 1,
        "unknown": 1,
    }
    matrix = build_gap_matrix(studio, COMMANDER, now=datetime(2026, 11, 19, 12, tzinfo=UTC))
    assert matrix["generated_at_utc"] == "2026-11-19T12:00:00Z"
    assert len(str(matrix["store_fingerprint"])) == 64
    pool = matrix["pool_size"]
    assert isinstance(pool, int) and pool > 0
    parts = [matrix["all_local_decks"], *matrix["cohort_groups_not_added_together"].values()]  # type: ignore[union-attr]
    for part in parts:
        assert part["pool"] == pool and part["classes_sum"] == pool  # type: ignore[index]
        assert isinstance(part["denominator_decks"], int)  # type: ignore[index]
    assert matrix == build_gap_matrix(studio, COMMANDER, now=datetime(2026, 11, 19, 12, tzinfo=UTC))
    assert "Filler 00" not in json.dumps(matrix)  # counts only


def test_signal_source_dates_come_from_the_readme_never_from_an_id_fragment(
    tmp_path: Path,
) -> None:
    from commander_lab.studio.provenance import README_NAME
    from commander_lab.studio.signals import _decklist_snapshot_date, _snapshot_from_signal_path

    (tmp_path / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n| `card_x.csv` | x | Abruf 2026-11-12 |\n",
        encoding="utf-8",
    )
    path = tmp_path / "card_x.csv"
    path.write_text("card_name\nA\n", encoding="utf-8")
    assert _snapshot_from_signal_path(path) == "2026-11-12"
    other = tmp_path / "card_y.csv"
    other.write_text("card_name\nA\n", encoding="utf-8")
    assert _snapshot_from_signal_path(other) is None  # unlisted: stays unknown
    assert _decklist_snapshot_date("universe:abc:12", other) is None
    assert _decklist_snapshot_date("2026-13-45", other) is None  # not a calendar date
    # a date in the name of a deck-list file is when it was generated, not a retrieval date
    named = tmp_path / "chulane_corpus_decklist_inclusion_20261115.csv"
    named.write_text("card_name\nA\n", encoding="utf-8")
    assert _decklist_snapshot_date("universe:abc:12", named) is None
    assert _decklist_snapshot_date("universe:abc:12", path) == "2026-11-12"
    assert _decklist_snapshot_date("2026-11-15T10:00", other) == "2026-11-15"


def _source_with_token_rows_only(studio: StudioStore) -> str:
    source_id = studio.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="tokens-only.json", sha256="d" * 64
    )
    studio.connection.execute(
        "INSERT INTO scryfall_token(scryfall_id, name, source_id) VALUES ('t1', 'Token', ?)",
        (source_id,),
    )
    studio.connection.commit()
    return source_id


def test_source_rows_are_counted_over_every_table_that_points_at_the_source(
    studio: StudioStore,
) -> None:
    """#1545: a source whose only rows sit in a rarely used table is not shown with 0 rows."""
    from commander_lab.studio.data_report import source_row_columns

    _source_with_token_rows_only(studio)
    details = {
        str(i["title"]): i
        for i in _section(data_report(studio, today=TODAY), "source_status")["details"]  # type: ignore[attr-defined]
    }
    assert details["tokens-only.json"]["rows_in_store"] == 1
    db = studio.connection
    # an independent reading of the schema text: every table that names source_id, except
    # ``source`` itself, must be counted; the list can never lag behind the schema
    named = {
        str(r[0])
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE '%source_id%' "
            "AND name <> 'source'"
        )
    }
    counted = {table for table, _column in source_row_columns(db)}
    assert named <= counted
    assert {
        "scryfall_token",
        "scryfall_card_token",
        "card_ruling",
        "corpus_deck_part",
        "source_capture_event",
        "simulation_run",
        "neutral_board_row",
    } <= counted
    # a table added later is picked up without touching the report code
    db.execute("CREATE TABLE zz_later(x INTEGER, source_id TEXT REFERENCES source(source_id))")
    db.execute("CREATE TABLE zz_fk(x INTEGER, origin TEXT REFERENCES source(source_id))")
    source_id = studio.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="later.csv", sha256="e" * 64
    )
    db.execute("INSERT INTO zz_later VALUES (1, ?)", (source_id,))
    db.execute("INSERT INTO zz_fk VALUES (1, ?)", (source_id,))
    db.commit()
    status = _section(data_report(studio, today=TODAY), "source_status")
    later = next(i for i in status["details"] if i["title"] == "later.csv")  # type: ignore[attr-defined]
    assert later["rows_in_store"] == 2
    assert {"zz_later.source_id", "zz_fk.origin"} <= set(status["tables_counted"])  # type: ignore[arg-type]


def test_source_status_date_validation_covers_deck_files_and_future_dates(
    studio: StudioStore,
) -> None:
    for digit, (title, value) in enumerate(
        (
            ("future.csv", "2026-12-31"),
            ("impossible.csv", "2026-02-30"),
            ("timestamp.csv", "2026-11-01T10:00:00Z"),
        )
    ):
        studio.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=title,
            sha256=str(digit) * 64,
            snapshot_date=value,
        )
    deck_source = studio.connection.execute("SELECT source_id FROM corpus_deck LIMIT 1").fetchone()
    studio.connection.execute(
        "UPDATE source SET snapshot_date = 'not-a-date' WHERE source_id = ?", (deck_source[0],)
    )
    studio.connection.commit()
    status = _section(data_report(studio, today=TODAY), "source_status")
    shown = {str(i["title"]): i["snapshot_date"] for i in status["details"]}  # type: ignore[attr-defined]
    assert shown["timestamp.csv"] == "2026-11-01T10:00:00Z"
    assert shown["future.csv"] == shown["impossible.csv"] == "unbekannt"
    decks = status["deck_file_sources"]
    assert decks["author_save_date_unknown"] >= 1  # type: ignore[index]
    assert (
        decks["author_save_date_known"] + decks["author_save_date_unknown"] == decks["total"]  # type: ignore[index,operator]
    )
    assert decks["retrieval_date"] == "unbekannt"  # type: ignore[index]


def test_importers_write_snapshot_date_only_for_a_stated_retrieval_date(tmp_path: Path) -> None:
    from commander_lab.studio.provenance import README_NAME
    from commander_lab.studio.rulings import import_rulings
    from commander_lab.studio.signals import _register
    from tests.unit.test_studio_rulings import _file as ruling_file
    from tests.unit.test_studio_rulings import _line

    store = StudioStore.open(tmp_path / "studio")
    data = tmp_path / "data"
    data.mkdir()
    (data / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n"
        "| `dated.jsonl` | x | Abruf 2026-11-12 |\n"
        "| `built.jsonl` | x | Build 2026-11-11 |\n"
        "| `part_{1..2}.csv` | x | Abruf 2026-11-11/12 |\n",
        encoding="utf-8",
    )
    line = _line("00000000-0000-0000-0000-000000000001", "2020-01-01", "A ruling.")
    for name in ("dated.jsonl", "built.jsonl", "unlisted.jsonl"):
        ruling_file(data / name, [line.replace("A ruling.", f"A ruling {name}.")])
    import_rulings(store, [data / "dated.jsonl", data / "built.jsonl", data / "unlisted.jsonl"])
    dates = dict(store.connection.execute("SELECT title, snapshot_date FROM source"))
    assert dates["dated.jsonl"] == "2026-11-12"
    assert dates["built.jsonl"] is None  # a build date is not a retrieval date
    assert dates["unlisted.jsonl"] is None  # no statement: unknown, not the import day
    # signal files: a tournament "date" column is not a retrieval date either
    (data / "tourney.csv").write_text("tournament,date,card_name\nT,2026-05-05,A\n", "utf-8")
    for name in ("part_1.csv", "part_2.csv", "part_3.csv"):
        (data / name).write_text(f"card_name\n{name}\n", encoding="utf-8")
    _register(store, [data / "tourney.csv"])
    _register(store, [data / "part_1.csv", data / "part_2.csv"])
    _register(store, [data / "part_3.csv", data / "part_1.csv"])
    dates = dict(store.connection.execute("SELECT title, snapshot_date FROM source"))
    assert dates["tourney.csv"] is None
    assert dates["part_1.csv"] == dates["part_2.csv"] == "2026-11-11"
    assert dates["part_3.csv"] is None
    # one date for a multi-part file only when every part states one (then the oldest)
    assert dates["part_1.csv (+1 parts)"] == "2026-11-11"
    assert dates["part_3.csv (+1 parts)"] is None


def test_gap_matrix_counts_a_filter_card_as_unknown_not_as_in_no_deck(
    studio: StudioStore,
) -> None:
    from commander_lab.studio import builder, universe_choice
    from commander_lab.studio.gap_matrix import _matrix
    from tests.unit.test_studio_strength import COMMANDER

    pool = builder.pool_cards(studio, [COMMANDER], with_signals=False)
    cards = pool["cards"]
    ids = [str(card["card_id"]) for card in cards]  # type: ignore[index]
    base = universe_choice.local_spec(studio, COMMANDER)
    plain = _matrix(studio, base, ids, COMMANDER, len(ids))
    required = next(str(card["name"]) for card in cards)  # type: ignore[index]
    narrowed = _matrix(studio, {**base, "must_contain": [required]}, ids, COMMANDER, len(ids))  # type: ignore[typeddict-item]
    assert narrowed["classes_sum"] == len(ids)
    assert narrowed["classes"]["unknown"] >= 1  # type: ignore[index]
    assert narrowed["classes"]["unknown"] > plain["classes"]["unknown"]  # type: ignore[index]


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


def test_gap_matrix_counts_pool_cards_the_spread_does_not_return_as_unknown(
    studio: StudioStore,
) -> None:
    from commander_lab.studio import builder, universe_choice
    from commander_lab.studio.gap_matrix import _matrix
    from tests.unit.test_studio_strength import COMMANDER

    cards = builder.pool_cards(studio, [COMMANDER], with_signals=False)["cards"]
    ids = [str(card["card_id"]) for card in cards]  # type: ignore[index]
    base = universe_choice.local_spec(studio, COMMANDER)
    full = _matrix(studio, base, ids, COMMANDER, len(ids))
    short = _matrix(studio, base, ids[:-2], COMMANDER, len(ids))  # two pool cards not returned
    assert short["classes_sum"] == len(ids) == short["pool"]
    assert short["classes"]["unknown"] == full["classes"]["unknown"] + 2  # type: ignore[index]


def test_mainboard_and_deck_card_count_metrics_use_real_main_and_commander_sections(
    tmp_path: Path,
) -> None:
    """#1624: corpus.mainboard_not_99_cards counts real 'main' rows (not only 'mainboard'),
    and deck_not_100_cards counts commander + main/mainboard with provenance."""
    store = StudioStore.open(tmp_path / "studio_1624")
    try:
        db = store.connection
        src = "src-1624"
        db.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
            "VALUES (?, 'OBSERVED_DECK', 'test', 'deadbeef', '2026-11-19')",
            (src,),
        )
        # 1) Standard 100-card deck: 1 commander + 99 main (+ 2 sideboard ignored)
        # 2) Partner 100-card deck: 2 commander + 98 main
        # 3) Short deck: 1 commander + 50 main
        for idx, (cmd_qty, main_qty, side_qty) in enumerate(
            [(1, 99, 2), (2, 98, 0), (1, 50, 0)], start=1
        ):
            did = f"deck-{idx}"
            db.execute(
                "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, tags, "
                "fingerprint, legality_audit, source_id) "
                "VALUES (?, 'bracket:3', '', 'edhrec', '', '[]', ?, 'ok', ?)",
                (did, f"fp-{idx}", src),
            )
            db.execute(
                "INSERT INTO corpus_deck_card(deck_id, card_name, quantity, section, "
                "normalization_status) VALUES (?, 'Cmd', ?, 'commander', 'matched')",
                (did, cmd_qty),
            )
            db.execute(
                "INSERT INTO corpus_deck_card(deck_id, card_name, quantity, section, "
                "normalization_status) VALUES (?, 'Forest', ?, 'main', 'matched')",
                (did, main_qty),
            )
            if side_qty:
                db.execute(
                    "INSERT INTO corpus_deck_card(deck_id, card_name, quantity, section, "
                    "normalization_status) VALUES (?, 'Side', ?, 'sideboard', 'matched')",
                    (did, side_qty),
                )
        db.commit()

        corpus = _section(data_report(store, today=TODAY), "corpus")
        # Only deck-2 (98 main) and deck-3 (50 main) have main != 99; deck-1 (99 main) is valid!
        # Mutation back to LOWER(section) = 'mainboard' would report 3/3 and fail here.
        assert corpus["mainboard_not_99_cards"] == {"count": 2, "of": 3}
        not_100 = corpus["deck_not_100_cards"]
        assert isinstance(not_100, dict)
        # deck-1 (1+99=100) and deck-2 (2+98=100) are 100 cards; only deck-3 (51) is not.
        assert not_100["count"] == 1
        assert not_100["of"] == 3
        assert not_100["counted_sections"] == ["commander", "main", "mainboard"]
        assert "corpus_deck_card" in str(not_100["provenance"])
    finally:
        store.close()


def test_readme_source_url_is_read_only_when_the_row_names_exactly_one_address(
    tmp_path: Path,
) -> None:
    from commander_lab.studio.provenance import README_NAME, readme_source_url

    (tmp_path / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n"
        "| `one.csv` | x (https://not-the-source.example/x) | API, Abruf 2026-11-12. Data by A (https://a.example). |\n"
        "| `two.csv` | x | https://a.example und https://b.example |\n"
        "| `same.csv` | x | https://a.example, https://a.example |\n"
        "| `none.csv` | x | Seite ohne Adresse, Abruf 2026-11-12 |\n",
        encoding="utf-8",
    )
    # only the last cell counts; a full stop after the address is not part of it
    assert readme_source_url(tmp_path / "one.csv") == "https://a.example"
    assert readme_source_url(tmp_path / "two.csv") is None  # two addresses: unknown
    assert readme_source_url(tmp_path / "same.csv") == "https://a.example"
    assert readme_source_url(tmp_path / "none.csv") is None
    assert readme_source_url(tmp_path / "unlisted.csv") is None
    assert readme_source_url(tmp_path / "sub" / "one.csv") is None  # no README there


def test_readme_source_url_is_a_http_or_https_address_with_a_host_and_no_markup(
    tmp_path: Path,
) -> None:
    from commander_lab.studio.provenance import README_NAME, readme_source_url

    rows = {
        # trailing punctuation, quotation and emphasis marks are not part of the address
        "bold.csv": ("**https://a.example**", "https://a.example"),
        "quoted.csv": ('"https://a.example", Abruf 2026-11-12', "https://a.example"),
        "stop.csv": ("https://a.example/x?q=1.", "https://a.example/x?q=1"),
        "port.csv": ("https://a.example:8080/x", "https://a.example:8080/x"),
        "plain_http.csv": ("http://a.example", "http://a.example"),
        # not an address: unknown, never a repaired guess
        "dot.csv": ("https://.", None),
        "empty_label.csv": ("https://a..example", None),
        "dash.csv": ("https://-a.example", None),
        "inner_star.csv": ("https://a*b.example", None),
        "inner_quote.csv": ('https://a"b.example', None),
        "inner_bracket.csv": ("https://a.example/x(y", None),
        "credentials.csv": ("https://user:secret@a.example", None),
        "bad_port.csv": ("https://a.example:99999", None),
        "ftp.csv": ("ftp://a.example", None),
        "no_host.csv": ("https:// ohne Host", None),
        # a malformed address next to a valid one: the cell is not a clear statement
        "mixed.csv": ("https://a.example und https://.", None),
    }
    (tmp_path / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n"
        + "".join(f"| `{name}` | x | {cell} |\n" for name, (cell, _) in rows.items()),
        encoding="utf-8",
    )
    assert {name: readme_source_url(tmp_path / name) for name in rows} == {
        name: expected for name, (_, expected) in rows.items()
    }


def test_committed_readme_names_an_address_only_for_the_tournament_files() -> None:
    from commander_lab.studio.provenance import readme_source_url

    folder = Path(__file__).resolve().parents[2] / "data" / "research" / "deckbuilder_1655"
    expected = {
        "topdeck_chulane_decks.csv": "https://topdeck.gg",
        "topdeck_commander_presence.csv": "https://topdeck.gg",
        "commander_card_signals_2.csv": None,  # names a site, not an address
        "card_rulings_1655.jsonl": None,
    }
    assert {name: readme_source_url(folder / name) for name in expected} == expected


def _source_rows(store: StudioStore) -> list[tuple[object, ...]]:
    return [
        tuple(row) for row in store.connection.execute("SELECT * FROM source ORDER BY source_id")
    ]


def _readme(folder: Path, rows: str) -> None:
    from commander_lab.studio.provenance import README_NAME

    (folder / README_NAME).write_text(
        "| Datei | Inhalt | Quelle |\n|---|---|---|\n" + rows, encoding="utf-8"
    )


def test_a_stated_date_and_address_replace_what_an_older_rule_stored(tmp_path: Path) -> None:
    from commander_lab.studio.signals import _register
    from commander_lab.studio.store import sha256_file

    store = StudioStore.open(tmp_path / "studio")
    data = tmp_path / "data"
    data.mkdir()
    _readme(
        data,
        "| `stated.csv` | x | API, Abruf 2026-11-12 (https://a.example) |\n"
        "| `date_only.csv` | x | API, Abruf 2026-11-12 |\n"
        "| `address_only.csv` | x | Seite https://c.example |\n"
        "| `silent.csv` | x | Seite ohne Datum |\n",
    )  # unlisted.csv has no row at all
    # a store imported before the rule: an id fragment or a tournament date, and an address (or
    # none); (old date, old address) per file
    old = {
        "stated.csv": ("20261115", None),
        "date_only.csv": ("20261115", "https://stored.example/date"),
        "address_only.csv": ("2026-09-18", "https://stored.example/address"),
        "silent.csv": ("2026-09-17", "https://stored.example/silent"),
        "unlisted.csv": ("2026-09-16", "https://stored.example/unlisted"),
    }
    for name, (old_date, old_url) in old.items():
        (data / name).write_text(f"card_name\n{name}\n", encoding="utf-8")
        digest = sha256_file(data / name)
        store.connection.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, snapshot_date, url, "
            "imported_at) VALUES (?, 'NORMALIZED_SOURCE', ?, ?, ?, ?, '2026-11-16')",
            (f"src:{digest[:16]}", name, digest, old_date, old_url),
        )

    def run() -> dict[str, tuple[object, object]]:
        for name in old:
            _register(store, [data / name])
        return {
            title: (date, url)
            for title, date, url in store.connection.execute(
                "SELECT title, snapshot_date, url FROM source"
            )
        }

    rows = run()
    # a stated value replaces the stored one, field by field ...
    assert rows["stated.csv"] == ("2026-11-12", "https://a.example")
    assert rows["date_only.csv"] == ("2026-11-12", "https://stored.example/date")
    assert rows["address_only.csv"] == ("2026-09-18", "https://c.example")
    # ... a file that states nothing keeps what is stored, address included: nothing is
    # estimated or erased (a README without a row for the file, or a row without an address)
    assert rows["silent.csv"] == ("2026-09-17", "https://stored.example/silent")
    assert rows["unlisted.csv"] == ("2026-09-16", "https://stored.example/unlisted")
    # a second run leaves every column of every row as it is, not only the number of rows
    before = _source_rows(store)
    assert len(before) == len(old)
    assert run() == rows
    assert _source_rows(store) == before


def test_a_multi_part_source_has_an_address_only_when_every_part_names_the_same_one(
    tmp_path: Path,
) -> None:
    from commander_lab.studio.signals import _register

    store = StudioStore.open(tmp_path / "studio")
    data = tmp_path / "data"
    data.mkdir()
    stems = ("same", "gap", "split")  # all parts name one address / one part names none / two
    parts = {
        stem: [data / f"{stem}_1.csv", data / f"{stem}_2.csv"] for stem in stems
    }  # own contents per case, so no case sees the address another one stored
    for files in parts.values():
        for file in files:
            file.write_text(f"card_name\n{file.name}\n", encoding="utf-8")

    _readme(
        data,
        "| `same_{1..2}.csv` | x | Abruf 2026-11-11, https://a.example |\n"
        "| `gap_1.csv` | x | Abruf 2026-11-11, https://a.example |\n"
        "| `gap_2.csv` | x | Abruf 2026-11-11 |\n"
        "| `split_1.csv` | x | Abruf 2026-11-11, https://a.example |\n"
        "| `split_2.csv` | x | Abruf 2026-11-11, https://b.example |\n",
    )

    def addresses() -> dict[str, object]:
        return dict(store.connection.execute("SELECT title, url FROM source"))

    combined = {stem: _register(store, files) for stem, files in parts.items()}
    shown = addresses()
    assert shown["same_1.csv"] == shown["same_2.csv"] == "https://a.example"
    assert shown["gap_1.csv"] == "https://a.example" and shown["gap_2.csv"] is None
    assert shown["split_1.csv"] == "https://a.example"
    assert shown["split_2.csv"] == "https://b.example"
    # the whole file carries an address only when every part names the same one: not the first
    # part's address when the parts differ, none when one part names none
    assert shown["same_1.csv (+1 parts)"] == "https://a.example"
    assert shown["gap_1.csv (+1 parts)"] is None
    assert shown["split_1.csv (+1 parts)"] is None

    # an address stored for the whole file stays when the parts do not state one clearly
    stored = "https://stored.example"
    store.connection.execute("UPDATE source SET url = ?", (stored,))
    for stem, files in parts.items():
        assert _register(store, files) == combined[stem]
    kept = addresses()
    assert kept["gap_1.csv (+1 parts)"] == kept["split_1.csv (+1 parts)"] == stored
    # parts that agree on one address replace the stored one
    assert kept["same_1.csv (+1 parts)"] == "https://a.example"
    # a part without a README row at all is no statement either: the address stays as it is
    _readme(data, "| `other.csv` | x | Abruf 2026-11-11, https://c.example |\n")
    assert _register(store, parts["same"]) == combined["same"]
    assert addresses()["same_1.csv (+1 parts)"] == "https://a.example"


def test_a_rulings_source_has_an_address_only_when_the_readme_names_one(tmp_path: Path) -> None:
    from commander_lab.studio.rulings import import_rulings
    from commander_lab.studio.store import sha256_file
    from tests.unit.test_studio_rulings import _file as ruling_file
    from tests.unit.test_studio_rulings import _line

    store = StudioStore.open(tmp_path / "studio")
    data = tmp_path / "data"
    data.mkdir()
    _readme(
        data,
        "| `named.jsonl` | x | Abruf 2026-11-12, https://a.example |\n"
        "| `silent.jsonl` | x | Abruf 2026-11-12 |\n"
        "| `kept.jsonl` | x | Abruf 2026-11-12 |\n",
    )  # unlisted.jsonl has no row
    names = ("named.jsonl", "silent.jsonl", "unlisted.jsonl", "kept.jsonl")
    for name in names:
        line = _line("00000000-0000-0000-0000-000000000001", "2020-01-01", f"Ruling {name}.")
        ruling_file(data / name, [line])
    # an older import stored one default address for every rulings file
    old = "https://default.example/rulings"
    for name in ("named.jsonl", "kept.jsonl"):
        digest = sha256_file(data / name)
        store.connection.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, snapshot_date, url, "
            "imported_at) VALUES (?, 'NORMALIZED_SOURCE', ?, ?, NULL, ?, '2026-11-16')",
            (f"src:{digest[:16]}", name, digest, old),
        )
    import_rulings(store, [data / name for name in names])
    urls = dict(store.connection.execute("SELECT title, url FROM source"))
    # the README statement wins over what was stored; without one the address is unknown, never
    # a default for rulings files; an older stored address stays (nothing is erased)
    assert urls == {
        "named.jsonl": "https://a.example",
        "silent.jsonl": None,
        "unlisted.jsonl": None,
        "kept.jsonl": old,
    }
    status = _section(data_report(store, today=TODAY), "source_status")
    shown = {str(item["title"]): item["address_stored"] for item in status["details"]}  # type: ignore[attr-defined]
    assert shown == {
        "named.jsonl": True,
        "silent.jsonl": False,
        "unlisted.jsonl": False,
        "kept.jsonl": True,
    }
    assert status["address_stored"] == {"count": 2, "of": 4}
