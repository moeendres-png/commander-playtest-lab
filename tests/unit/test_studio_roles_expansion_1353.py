"""Tests for #1353 part B (EDHREC cardlist completeness & thresholds) and part C (role expansion)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from commander_lab.studio import importers, repo_import, roles, signals
from commander_lab.studio.store import DataClass, StudioStore

_RESEARCH = Path(__file__).resolve().parents[2] / "data" / "research"
_ROLES_DIR = _RESEARCH / "roles_1655"
_EDHREC_DIR = _RESEARCH / "edhrec_observations_chulane"


@pytest.mark.parametrize(
    ("type_line", "oracle_text", "expected_roles"),
    [
        ("Creature — Human", "", ()),
        ("Basic Land — Forest", "({T}: Add {G}.)", ()),
        (
            "Creature — Elf Druid",
            "{T}: Add {G}.",
            ("mana_dork", "ramp"),
        ),
        (
            "Artifact",
            "{T}: Add {G} or {W}.",
            ("mana_rock", "ramp"),
        ),
        (
            "Sorcery",
            "Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
            ("land_ramp", "ramp"),
        ),
        (
            "Instant",
            "Counter target creature spell. Scry 1.",
            ("card_selection", "counterspell"),
        ),
        (
            "Instant",
            "Target creature gets +3/+3 and gains flying until end of turn.",
            ("combat_trick", "evasion"),
        ),
        (
            "Enchantment",
            "Other creatures you control get +1/+1.\nCreatures you control have vigilance.",
            ("anthem",),
        ),
        (
            "Sorcery",
            "Creatures you control get +3/+3 and gain trample until end of turn.",
            ("combat_trick",),
        ),
        (
            "Creature — Elf Warrior",
            "When this creature enters, put a +1/+1 counter on target creature and create a 1/1 green Elf Warrior creature token.",
            ("counters", "token_production"),
        ),
        (
            "Instant",
            "Target player mills four cards. Draw a card.",
            ("card_draw", "mill"),
        ),
        (
            "Artifact",
            "Spells you cast cost {1} less to cast.",
            ("cost_reduction",),
        ),
        (
            "Creature — Human Scout",
            "Landfall — Whenever a land you control enters, you gain 2 life.",
            ("landfall", "lifegain"),
        ),
        (
            "Instant",
            "Exile target artifact or enchantment.",
            ("removal",),
        ),
        (
            "Sorcery",
            "Destroy all creatures.",
            ("board_wipe",),
        ),
        (
            "Instant",
            "Return target nonland permanent to its owner's hand.",
            ("bounce",),
        ),
        (
            "Creature — Faerie Rogue",
            "Flying, hexproof\nWhenever this creature enters, untap target land.",
            ("evasion", "protection", "untapper"),
        ),
        (
            "Creature — Human Soldier",
            "{T}: Tap target creature.",
            ("tapper",),
        ),
        (
            "Instant",
            "Copy target instant or sorcery spell. You may choose new targets for the copy.",
            ("copy",),
        ),
    ],
)
def test_classify_oracle_roles_deterministic_rules(
    type_line: str, oracle_text: str, expected_roles: tuple[str, ...]
) -> None:
    assert roles.classify_oracle_roles(type_line, oracle_text) == expected_roles


def test_expanded_role_vocabulary_and_repo_files_import_idempotently(tmp_path: Path) -> None:
    assert len(roles.ROLES) == 34
    assert len(set(roles.ROLES.values())) == 34

    discovered = repo_import.RepoFiles.discover(_RESEARCH)
    names = [path.name for path in discovered.roles]
    assert "roles_s4_tagger_expansion_wug.json" in names
    assert "roles_s5_oracle_expansion.json" in names

    store = StudioStore.open(tmp_path / "studio")
    try:
        for path in discovered.roles:
            first = roles.import_roles(store, path)
            second = roles.import_roles(store, path)
            assert first["claims_removed"] == 0
            assert second["claims_added"] == 0
            assert second["claims_removed"] == 0

        claims_total = int(
            store.connection.execute("SELECT COUNT(*) FROM card_role_claim").fetchone()[0]
        )
        assert claims_total == 21272
    finally:
        store.close()


def test_edhrec_chulane_threshold_audit_and_cardlist_import(tmp_path: Path) -> None:
    audit_path = _EDHREC_DIR / "edhrec_chulane_threshold_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["cardlists_present"] == 12
    assert audit["distinct_cards_snapshot"] == 241
    assert audit["pool_cards_with_commander_signal_before"] == 68
    assert audit["pool_cards_with_commander_signal_after"] == 68
    assert audit["sections"]["newcards"]["min_numerator"] == 29
    assert audit["sections"]["manaartifacts"]["min_numerator"] == 505

    # Verify synthetic EDHREC commander + table import retains both low-share newcards
    # and all regular sections without silent truncation.
    signals_dir = tmp_path / "signals"
    signals_dir.mkdir()
    sig_csv = signals_dir / "commander_card_signals.csv"
    with sig_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "commander_name",
                "commander_slug",
                "list_header",
                "list_tag",
                "card_name",
                "card_slug",
                "source_card_id",
                "synergy",
                "lift",
                "num_decks",
                "potential_decks",
                "trend_zscore",
                "source_file",
            ]
        )
        writer.writerow(
            [
                "Chulane, Teller of Tales",
                "chulane-teller-of-tales",
                "New Cards",
                "newcards",
                "Low Newcard",
                "low-newcard",
                "c1",
                "0.05",
                "0.05",
                "29",
                "1221",
                "0.0",
                "synthetic.json",
            ]
        )
        writer.writerow(
            [
                "Chulane, Teller of Tales",
                "chulane-teller-of-tales",
                "Mana Artifacts",
                "manaartifacts",
                "Talisman of Unity",
                "talisman-of-unity",
                "c2",
                "0.10",
                "0.10",
                "505",
                "9824",
                "0.0",
                "synthetic.json",
            ]
        )

    obs_csv = tmp_path / "edhrec_table_test.csv"
    with obs_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "card_id",
                "card_name",
                "theme",
                "url",
                "snapshot_utc",
                "num_decks",
                "potential_decks",
                "inclusion_pct",
                "lift",
            ]
        )
        writer.writerow(
            [
                "card:test:1",
                "Low Newcard",
                "chulane-teller-of-tales",
                "https://edhrec.com/commanders/chulane-teller-of-tales",
                "2026-11-12T00:00:00Z",
                "29",
                "1221",
                "2.3751",
                "0.05",
            ]
        )

    store = StudioStore.open(tmp_path / "studio")
    try:
        with store.connection as db:
            sid = store.register_source(
                data_class=DataClass.ORIGINAL_SOURCE,
                title="synthetic",
                sha256="0" * 64,
            )
            db.execute(
                "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, source_id) "
                "VALUES ('card:test:1', 'oid-1', 'Low Newcard', 'G', '{G}', 1.0, 'Creature', '', 0, ?)",
                (sid,),
            )
            db.execute(
                "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, source_id) "
                "VALUES ('card:test:2', 'oid-2', 'Talisman of Unity', 'GW', '{2}', 2.0, 'Artifact', '', 0, ?)",
                (sid,),
            )
        report = signals.import_signals(store, signals_dir, commander="Chulane, Teller of Tales")
        assert int(report["rows_written"]) > 0
        obs_report = importers.import_edhrec_table(store, obs_csv)
        assert obs_report["rows"] == 1
        assert int(store.connection.execute("SELECT COUNT(*) FROM observation").fetchone()[0]) == 2
        rows = store.connection.execute(
            "SELECT card_name, numerator, denominator FROM card_signal "
            "WHERE commander_name = 'Chulane, Teller of Tales' "
            "AND signal = 'edhrec_commander_inclusion' ORDER BY numerator"
        ).fetchall()
        assert [(str(r[0]), int(r[1]), int(r[2])) for r in rows] == [
            ("Low Newcard", 29, 1221),
            ("Talisman of Unity", 505, 9824),
        ]
    finally:
        store.close()
