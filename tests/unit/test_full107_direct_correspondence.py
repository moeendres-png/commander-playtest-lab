"""FULL107 DIRECT correspondence guard (adjudications 2026-09-22).

Mechanical regression preventing unsupported DIRECT promotions: every DIRECT
mapping entry must hold an EXACT verdict in the fixture-identity register;
NATIVE_STATE_LOAD entries may be DIRECT only for executed fixtures in the
register's EXACT set (injection + execution qualified per fixture, never by
mode alone); and the PLAYER_COUNT gate-equivalence must never be credited as
fixture identity while the gate runner uses technical Isamaru decks.
Promoting a new DIRECT requires updating the register with exact
deck/seed/procedure evidence first.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MAPPING_PATH = Path("docs/workstream_full107_definition_20260921/FULL107_MAPPING.json")
REGISTER_PATH = Path(
    "docs/workstream_full107_fixture_identity_20260922/FIXTURE_IDENTITY_REGISTER.json"
)
MATERIALIZATION_PATH = Path("qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")
GATE_RUNNER_PATH = Path("scripts/run_external_full_game_conformance.py")
GENERATOR_PATH = Path("scripts/generate_full107_mapping.py")

ADJUDICATED_FIXTURES = {
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
    "WS05-CMD-TAX-2",
    "WS05-CMD-TAX-4",
    "WS05-CMD-PARTNER-ZONE",
    "WS05-CMD-PARTNER-TAX",
    "CARD_02",
}

EXACT_FIXTURES = [
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
    "WS05-CMD-TAX-2",
    "WS05-CMD-TAX-4",
    "WS05-CMD-PARTNER-ZONE",
    "WS05-CMD-PARTNER-TAX",
    "CARD_02",
]


def _load_mapping(repo_root: Path) -> dict:
    return json.loads((repo_root / MAPPING_PATH).read_text(encoding="utf-8"))


def _load_register(repo_root: Path) -> dict:
    return json.loads((repo_root / REGISTER_PATH).read_text(encoding="utf-8"))


def _load_materialization(repo_root: Path) -> dict:
    payload = json.loads((repo_root / MATERIALIZATION_PATH).read_text(encoding="utf-8"))
    return {record["fixture_id"]: record for record in payload["records"]}


def _load_map_fixture(repo_root: Path):
    spec = importlib.util.spec_from_file_location(
        "generate_full107_mapping", repo_root / GENERATOR_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.map_fixture


def test_direct_entries_require_exact_register_verdict(repo_root: Path) -> None:
    mapping = _load_mapping(repo_root)
    register = _load_register(repo_root)
    verdicts = {item["fixture_id"]: item["verdict"] for item in register["verdicts"]}
    assert set(verdicts) == ADJUDICATED_FIXTURES
    direct = [entry["fixture_id"] for entry in mapping["entries"] if entry["status"] == "DIRECT"]
    assert direct, "mapping must retain at least one DIRECT entry"
    for fixture_id in direct:
        assert verdicts.get(fixture_id) == "EXACT", (
            f"{fixture_id} is DIRECT without an EXACT identity verdict"
        )
    exact = sorted(fid for fid, verdict in verdicts.items() if verdict == "EXACT")
    assert exact == sorted(EXACT_FIXTURES)
    assert sorted(direct) == exact


def test_native_direct_requires_executed_subset(repo_root: Path) -> None:
    mapping = _load_mapping(repo_root)
    records = _load_materialization(repo_root)
    for entry in mapping["entries"]:
        if entry["status"] == "DIRECT":
            mode = records[entry["fixture_id"]].get("execution_entry_mode")
            if mode == "NATIVE_STATE_LOAD":
                assert entry["fixture_id"] in (
                    "WS05-CMD-TAX-2",
                    "WS05-CMD-TAX-4",
                    "WS05-CMD-PARTNER-ZONE",
                    "WS05-CMD-PARTNER-TAX",
                    "CARD_02",
                ), (
                    f"{entry['fixture_id']} is a NATIVE DIRECT outside the executed subset; "
                    "injection alone never earns DIRECT"
                )


def test_exact_fixtures_bind_real_cards_in_deck_state(repo_root: Path) -> None:
    records = _load_materialization(repo_root)
    for fixture_id in ("WS05-CMD-MULL-2", "WS05-CMD-MULL-4"):
        deck_state = records[fixture_id]["deck_state"]
        assert len(deck_state) == (2 if fixture_id.endswith("-2") else 4)
        for seat in deck_state:
            commanders = seat["commander"]
            assert commanders == [{"card_identity": "Rograkh, Son of Rohgahh", "count": 1}]
            assert seat["main_deck"] == [{"card_identity": "Mountain", "count": 99}]
            assert seat["exact_card_count"] == 100


def test_tax_fixtures_match_executed_subset_shape(repo_root: Path) -> None:
    records = _load_materialization(repo_root)
    for fixture_id in ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4"):
        record = records[fixture_id]
        assert record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
        assert record.get("deck_state") is None
        zones = {obj["zone"] for obj in record["semantic_objects"]}
        assert zones <= {"command", "battlefield"}, (fixture_id, zones)
        assert record["commander_state"]["commander_damage_matrix"] == []
        temporal = record["temporal_state"]
        assert (temporal["turn_number"], temporal["phase"], temporal["step"]) == (
            1,
            "precombat_main",
            "main",
        )
        assert [event for event in record["expected_events"]["required_events"]] == [
            "commander_cast_from_command",
            "commander_tax:+4_generic",
            "mana_paid:4",
        ]


def test_partner_fixtures_match_executed_subset_shape(repo_root: Path) -> None:
    records = _load_materialization(repo_root)
    expected_events = {
        "WS05-CMD-PARTNER-ZONE": [
            "game_start_command_zone:cmd:P1-A",
            "game_start_command_zone:cmd:P1-B",
        ],
        "WS05-CMD-PARTNER-TAX": ["tax:cmd:P1-A:+4", "tax:cmd:P1-B:+0"],
    }
    for fixture_id, required in expected_events.items():
        record = records[fixture_id]
        assert record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
        assert record.get("deck_state") is None
        assert record["decision_script"] == [], fixture_id
        zones = {obj["zone"] for obj in record["semantic_objects"]}
        assert zones <= {"command", "battlefield"}, (fixture_id, zones)
        assert record["commander_state"]["commander_damage_matrix"] == []
        relations = record["commander_state"]["multiple_commander_relations"]
        assert len(relations) == 1
        assert relations[0]["relation"] == "Partner"
        commander_ids = {
            commander["commander_id"] for commander in record["commander_state"]["commanders"]
        }
        assert set(relations[0]["commander_ids"]) <= commander_ids
        temporal = record["temporal_state"]
        assert (temporal["turn_number"], temporal["phase"], temporal["step"]) == (
            1,
            "precombat_main",
            "main",
        )
        assert [event for event in record["expected_events"]["required_events"]] == required


def test_player_count_gates_cannot_be_direct_while_technical(repo_root: Path) -> None:
    runner = (repo_root / GATE_RUNNER_PATH).read_text(encoding="utf-8")
    assert "Isamaru, Hound of Konda" in runner, (
        "gate-runner deck assumption changed; re-adjudicate PLAYER_COUNT identity"
    )
    mapping = _load_mapping(repo_root)
    statuses = {entry["fixture_id"]: entry["status"] for entry in mapping["entries"]}
    for count in (2, 3, 4, 5):
        assert statuses[f"PLAYER_COUNT_{count}P"] != "DIRECT", (
            f"PLAYER_COUNT_{count}P credited as fixture identity while gates run "
            "technical Isamaru decks at other seeds"
        )


def test_generator_mapping_rules(repo_root: Path) -> None:
    map_fixture = _load_map_fixture(repo_root)
    assert map_fixture("PLAYER_COUNT_2P", {})["status"] == "SUPPORTING"
    assert map_fixture("PLAYER_COUNT_5P", {})["status"] == "SUPPORTING"
    assert map_fixture("WS05-CMD-MULL-2", {})["status"] == "DIRECT"
    assert map_fixture("WS05-CMD-MULL-4", {})["status"] == "DIRECT"
    assert (
        map_fixture("WS05-CMD-TAX-2", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "DIRECT"
    )
    assert (
        map_fixture("WS05-CMD-TAX-4", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "DIRECT"
    )
    assert (
        map_fixture("WS05-CMD-PARTNER-ZONE", {"execution_entry_mode": "NATIVE_STATE_LOAD"})[
            "status"
        ]
        == "DIRECT"
    )
    assert (
        map_fixture("WS05-CMD-PARTNER-TAX", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "DIRECT"
    )
    assert (
        map_fixture("CARD_02", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"] == "DIRECT"
    )
    assert map_fixture("PILOT_MULLIGAN", {})["status"] in ("SUPPORTING", "UNKNOWN")
    assert (
        map_fixture("MICRO_COSTS", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "UNKNOWN"
    )
    assert (
        map_fixture("WS05-CMD-START-2", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "NOT_RUN_BLOCKED"
    )


def test_direct_reasons_claim_digest_equality(repo_root: Path) -> None:
    mapping = _load_mapping(repo_root)
    assert any(entry["status"] == "DIRECT" for entry in mapping["entries"])
    for entry in mapping["entries"]:
        if entry["status"] == "DIRECT":
            assert "requested_state_digest" in entry.get("reason", ""), (
                f"{entry['fixture_id']} is DIRECT without a digest-equality claim; "
                "mandatory construction credit must never be silently replaced"
            )


def test_card02_fixture_matches_executed_shape(repo_root: Path) -> None:
    records = _load_materialization(repo_root)
    record = records["CARD_02"]
    assert record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
    assert record.get("deck_state") is None
    zones = {obj["zone"] for obj in record["semantic_objects"]}
    assert zones <= {"command"}, zones
    assert record["commander_state"]["commander_damage_matrix"] == []
    assert record["commander_state"].get("multiple_commander_relations", []) == []
    temporal = record["temporal_state"]
    assert (temporal["turn_number"], temporal["phase"], temporal["step"]) == (
        1,
        "precombat_main",
        "main",
    )
    assert len(record["decision_script"]) == 1
    script = record["decision_script"][0]
    assert script["actor"] == "P1"
    assert script["decision_family"] == "priority"
    assert script["selection"]["semantic_value"]["action"] == "cast_commander"
    assert script["selection"]["semantic_value"]["commander_id"] == "cmd:P1-A"
    assert [event for event in record["expected_events"]["required_events"]] == [
        "commander_cast",
        "spell_resolved",
        "creature_entered",
    ]
