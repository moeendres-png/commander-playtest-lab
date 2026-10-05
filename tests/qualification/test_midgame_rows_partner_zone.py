"""WS05-CMD-PARTNER-ZONE: the game-start command-zone obligation on XMage.

The row's oracle is the native partner execution test's own facts: each partner
the record names is a separate engine commander identity that begins in its
owner's command zone. On the production mid-game lane that evidence is the
engine's constructed-state readback, so these tests read the effective FULL107
record and pin the row spec to it, then exercise the six wrong-reason controls
that must each keep the row non-PASS:

1. two partners merged into one identity;
2. a partner on the battlefield instead of in the command zone;
3. partners split across seats;
4. two commander rows byte-identical apart from the list index;
5. a refused constructed-state read stays UNKNOWN, never PASS;
6. the verdict never asserts the record's declared commander relation.

No test fabricates a legal option or a game fact: the positive readback is the
record's own requested command zone, and every mutation is a wrong-reason
input the verifier must reject.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ID = "WS05-CMD-PARTNER-ZONE"
TOKEN_A = "game_start_command_zone:cmd:P1-A"
TOKEN_B = "game_start_command_zone:cmd:P1-B"


# --------------------------------------------------------------------------- #
# The effective record and the row spec
# --------------------------------------------------------------------------- #


def _effective_record() -> dict[str, Any]:
    records = load_effective_materialization(REPO_ROOT).denominator_records()
    return next(record for record in records if record["fixture_id"] == FIXTURE_ID)


def _required_events(record: dict[str, Any]) -> list[str]:
    events = (record.get("expected_events") or {}).get("required_events") or []
    return [str(event) for event in events]


def _declared_commanders(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry["commander_id"]): entry
        for entry in (record.get("commander_state") or {}).get("commanders") or ()
    }


def _bindings() -> dict[str, mr.TerminalCheck]:
    bindings: dict[str, mr.TerminalCheck] = {}
    for token, binding in mr.ROWS[FIXTURE_ID].token_bindings:
        assert isinstance(binding, mr.TerminalCheck), token
        bindings[token] = binding
    return bindings


def _requested_command_zone(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The record's own command-zone entries, one per requested commander."""
    declared = _declared_commanders(record)
    entries: list[dict[str, Any]] = []
    for obj in record.get("semantic_objects") or ():
        if obj.get("zone") != "command" or not obj.get("commander_id"):
            continue
        state = declared[str(obj["commander_id"])]
        entries.append(
            {
                "commander_id": str(obj["commander_id"]),
                "owner": str(state.get("owner") or obj.get("owner")),
                "card_identity": str(state.get("card_identity") or obj.get("card_identity")),
            }
        )
    return entries


def _observation(entries: list[dict[str, Any]], *, relation: Any = None) -> dict[str, Any]:
    """An engine-readback-shaped observation from the given command-zone rows."""
    seats: dict[str, dict[str, Any]] = {
        f"P{index}": {"player_id": f"P{index}", "commanders": []} for index in range(1, 5)
    }
    for entry in entries:
        seats[entry["owner"]]["commanders"].append(
            {"card_identity": entry["card_identity"], "zone": entry.get("zone", "COMMAND")}
        )
    observation: dict[str, Any] = {"seats": [seats[f"P{index}"] for index in range(1, 5)]}
    if relation is not None:
        observation["multiple_commander_relations"] = relation
    return observation


def _all_checks_hold(observation: dict[str, Any]) -> bool:
    return all(mr.check_terminal(check, observation, [], []) for check in _bindings().values())


# --------------------------------------------------------------------------- #
# Positives: the record and the engine readback agree
# --------------------------------------------------------------------------- #


def test_the_row_spec_binds_exactly_the_records_required_events() -> None:
    record = _effective_record()
    required = _required_events(record)
    assert required == [TOKEN_A, TOKEN_B]
    bindings = _bindings()
    assert set(bindings) == set(required)
    declared = _declared_commanders(record)
    for token in required:
        commander_id = token.split(":", 1)[1]
        check = bindings[token]
        assert check.kind == "game_start_command_zone"
        assert check.principal == declared[commander_id]["owner"]
        assert check.card_identity == declared[commander_id]["card_identity"]
    # The two partners are different identities in the record itself, so a
    # collapsed binding (both tokens to one identity) cannot be the spec.
    assert declared["cmd:P1-A"]["card_identity"] != declared["cmd:P1-B"]["card_identity"]


def test_the_positive_readback_observes_both_partners_in_the_command_zone() -> None:
    record = _effective_record()
    observation = _observation(_requested_command_zone(record))
    for token, check in _bindings().items():
        assert mr.needs_observation(check), token
        assert mr.check_terminal(check, observation, [], []), token
    # The same readback carries every other requested commander (P2-A..P4-A),
    # which the construction verdict this executor requires compares exactly.
    seats = {seat["player_id"]: seat for seat in observation["seats"]}
    for seat in ("P2", "P3", "P4"):
        assert seats[seat]["commanders"] == [
            {"card_identity": "Rograkh, Son of Rohgahh", "zone": "COMMAND"}
        ]


def test_the_obligation_kind_is_the_shared_forge_lane_kind() -> None:
    from commander_lab.qualification.current_boundary import forge_scenario_lane as fsl

    record = _effective_record()
    assert fsl._obligation_kind(fsl.model_requested_state(record)) == "game_start_command_zone"


# --------------------------------------------------------------------------- #
# Wrong-reason red controls
# --------------------------------------------------------------------------- #


def test_identity_collapse_keeps_the_row_non_pass() -> None:
    """Control 1: the two partners merged into one engine identity."""
    record = _effective_record()
    bindings = _bindings()
    merged = [
        entry for entry in _requested_command_zone(record) if entry["commander_id"] != "cmd:P1-B"
    ]
    observation = _observation(merged)
    assert mr.check_terminal(bindings[TOKEN_A], observation, [], [])
    assert not mr.check_terminal(bindings[TOKEN_B], observation, [], [])
    assert not _all_checks_hold(observation)


def test_a_partner_on_the_battlefield_keeps_the_row_non_pass() -> None:
    """Control 2: Kediss is a genuine commander, but not in the command zone."""
    record = _effective_record()
    bindings = _bindings()
    entries = [
        {**entry, "zone": "BATTLEFIELD"} if entry["commander_id"] == "cmd:P1-B" else entry
        for entry in _requested_command_zone(record)
    ]
    observation = _observation(entries)
    assert mr.check_terminal(bindings[TOKEN_A], observation, [], [])
    assert not mr.check_terminal(bindings[TOKEN_B], observation, [], [])
    assert not _all_checks_hold(observation)


def test_partners_split_across_seats_keep_the_row_non_pass() -> None:
    """Control 3: both partners belong to one seat; the engine moved one away."""
    record = _effective_record()
    bindings = _bindings()
    entries = [
        {**entry, "owner": "P2"} if entry["commander_id"] == "cmd:P1-B" else entry
        for entry in _requested_command_zone(record)
    ]
    observation = _observation(entries)
    assert mr.check_terminal(bindings[TOKEN_A], observation, [], [])
    assert not mr.check_terminal(bindings[TOKEN_B], observation, [], [])
    assert not _all_checks_hold(observation)


def test_byte_identical_commander_rows_are_not_two_identities() -> None:
    """Control 4: two rows identical apart from the list index are one identity.

    A membership test (``any``) would accept this readback; the obligation needs
    exactly one command-zone row per requested identity, so a duplicated row is
    not evidence of a second partner.
    """
    record = _effective_record()
    bindings = _bindings()
    rograkh = next(
        entry for entry in _requested_command_zone(record) if entry["commander_id"] == "cmd:P1-A"
    )
    entries = [entry for entry in _requested_command_zone(record) if entry["owner"] != "P1"] + [
        rograkh,
        dict(rograkh),
    ]
    observation = _observation(entries)
    p1 = next(seat for seat in observation["seats"] if seat["player_id"] == "P1")
    assert len(p1["commanders"]) == 2
    assert p1["commanders"][0] == p1["commanders"][1]
    assert any(entry["card_identity"] == rograkh["card_identity"] for entry in p1["commanders"])
    assert not mr.check_terminal(bindings[TOKEN_A], observation, [], [])
    assert not mr.check_terminal(bindings[TOKEN_B], observation, [], [])
    assert not _all_checks_hold(observation)


# --------------------------------------------------------------------------- #
# Control 5: a refused constructed-state read is UNKNOWN, never PASS
# --------------------------------------------------------------------------- #


class _Arrival:
    construction_verdict = "EXACT"


class _RefusingClient:
    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {"events": [], "latest_offset": 0}

    def pending_decision(self, *, attempts: int = 60) -> None:
        return None

    def complete_arrival(self) -> dict[str, Any]:
        raise ml.MidgameLaneArrivalRejected("the engine refused the constructed-state read")


def _stub_arrival(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mr,
        "probe_module",
        lambda: types.SimpleNamespace(
            CAUSAL_STACK_ELIMINATION="causal_stack_elimination",
            drive_arrival=lambda *args, **kwargs: _Arrival(),
        ),
    )


def test_a_refused_constructed_state_read_is_unknown_never_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _effective_record()
    _stub_arrival(monkeypatch)
    execution = mr.execute_row(  # type: ignore[arg-type]
        _RefusingClient(), record, {}, mr.ROWS[FIXTURE_ID]
    )
    # The arrival itself was accepted; only the state read refused. The row is
    # therefore unestablished (UNKNOWN), not a PASS and not a construction FAIL.
    assert execution.construction_verdict == "EXACT"
    assert execution.verified is False
    assert "readback failed closed" in execution.detail
    assert execution.document()["verified"] is False


# --------------------------------------------------------------------------- #
# Control 6: the verdict comes from the engine rows, not the declared relation
# --------------------------------------------------------------------------- #


class _GoodClient:
    def __init__(self, observation: dict[str, Any]) -> None:
        self._observation = observation

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {"events": [], "latest_offset": 0}

    def pending_decision(self, *, attempts: int = 60) -> None:
        return None

    def complete_arrival(self) -> dict[str, Any]:
        return {"observation": self._observation}


RELATION = [{"relation": "Partner", "commander_ids": ["cmd:P1-A", "cmd:P1-B"]}]


def test_the_verdict_comes_from_the_engine_rows_not_the_declared_relation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _effective_record()
    _stub_arrival(monkeypatch)
    observation = _observation(_requested_command_zone(record), relation=RELATION)
    execution = mr.execute_row(  # type: ignore[arg-type]
        _GoodClient(observation), record, {}, mr.ROWS[FIXTURE_ID]
    )
    assert execution.verified is True
    document = execution.document()
    assert "multiple_commander_relations" not in json.dumps(document)
    assert "Partner" not in json.dumps(document)
    # A relation claim is never a substitute for the rows: the collapsed state
    # still fails even though the fabricated relation is present.
    collapsed = _observation(
        [entry for entry in _requested_command_zone(record) if entry["commander_id"] != "cmd:P1-B"],
        relation=RELATION,
    )
    refused = mr.execute_row(  # type: ignore[arg-type]
        _GoodClient(collapsed), record, {}, mr.ROWS[FIXTURE_ID]
    )
    assert refused.verified is False


# --------------------------------------------------------------------------- #
# The runner declares the row receivable
# --------------------------------------------------------------------------- #


def _runner(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    path = REPO_ROOT / "scripts" / "run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("partner_zone_runner_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_the_runner_declares_the_partner_zone_row_receivable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner(monkeypatch)
    materialization = runner.load_effective_materialization(REPO_ROOT)
    rows = runner.classify_remaining(
        materialization,
        set(),
        candidate="xmage",
        identity={"starting_state_injection_supported": False},
    )
    row = next(item for item in rows if item.fixture_id == FIXTURE_ID)
    assert row.outcome == "UNKNOWN"
    assert "MIDGAME_ROW_EXECUTIONS.json" in row.reason
    assert "no current-boundary execution path" not in row.reason
    # The XMage mid-game lane is not a Forge route: the Forge column keeps its
    # own residual classification and outcome.
    forge_rows = runner.classify_remaining(
        materialization,
        set(),
        candidate="forge",
        identity={"starting_state_injection_supported": True},
    )
    forge_row = next(item for item in forge_rows if item.fixture_id == FIXTURE_ID)
    assert forge_row.outcome == "UNKNOWN"
    assert "Forge" in forge_row.reason
