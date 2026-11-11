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
    for forbidden in ("Forest", "Swarm Rat", "Test Commander", "private note text", "http"):
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
