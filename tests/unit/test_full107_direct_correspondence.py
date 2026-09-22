"""FULL107 DIRECT correspondence guard (fixture-identity adjudication 2026-09-22).

Mechanical regression preventing unsupported DIRECT promotions: every DIRECT
mapping entry must hold an EXACT verdict in the fixture-identity register,
no NATIVE_STATE_LOAD entry may be DIRECT (injection does not exist yet), and
the PLAYER_COUNT gate-equivalence must never be credited as fixture identity
while the gate runner uses technical Isamaru decks. Promoting a new DIRECT
requires updating the register with exact deck/seed/procedure evidence first.
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

NATURAL_FIXTURES = {
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
}


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
    assert set(verdicts) == NATURAL_FIXTURES
    direct = [entry["fixture_id"] for entry in mapping["entries"] if entry["status"] == "DIRECT"]
    assert direct, "mapping must retain at least one DIRECT entry"
    for fixture_id in direct:
        assert verdicts.get(fixture_id) == "EXACT", (
            f"{fixture_id} is DIRECT without an EXACT identity verdict"
        )
    exact = sorted(fid for fid, verdict in verdicts.items() if verdict == "EXACT")
    assert exact == ["WS05-CMD-MULL-2", "WS05-CMD-MULL-4"]
    assert sorted(direct) == exact


def test_no_native_state_load_entry_is_direct(repo_root: Path) -> None:
    mapping = _load_mapping(repo_root)
    records = _load_materialization(repo_root)
    for entry in mapping["entries"]:
        if entry["status"] == "DIRECT":
            mode = records[entry["fixture_id"]].get("execution_entry_mode")
            assert mode == "NATURAL_GAME_START", (
                f"{entry['fixture_id']} is DIRECT with entry mode {mode}; "
                "native injection does not exist yet"
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
    assert map_fixture("PILOT_MULLIGAN", {})["status"] in ("SUPPORTING", "UNKNOWN")
    assert (
        map_fixture("MICRO_COSTS", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "UNKNOWN"
    )
    assert (
        map_fixture("WS05-CMD-TAX-2", {"execution_entry_mode": "NATIVE_STATE_LOAD"})["status"]
        == "NOT_RUN_BLOCKED"
    )
