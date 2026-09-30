"""The PB-03 chain's last links: verified placement obligation -> positive receipt -> credit.

``midgame_rows`` executes exactly constructed placement rows on the production
midgame lane and verifies each required event against the engine's public
event tape. These tests pin the verification rules and the receipt chain
without a live engine: a receipt exists only for a verified row, it loads only
intact, and it is credited only for the bound candidate, runner and
denominator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary import receipts as R

COMMIT = "9" * 40
RUNNER = "r" * 64


def _record(required: list[str]) -> dict[str, Any]:
    return {
        "fixture_id": "MICRO_TRIGGERS",
        "expected_events": {"required_events": required},
        "terminal_postconditions": ["P2 is at 38 life."],
        "requested_state_digest": "a" * 64,
        "obligation_digest": "b" * 64,
    }


TAPE: list[dict[str, Any]] = [
    {
        "sequence": 7,
        "type": "ZONE_CHANGE",
        "from": "HAND",
        "to": "STACK",
        "target_object": "obj:bears",
    },
    {"sequence": 8, "type": "SPELL_CAST", "source_object": "obj:bears", "player_player": "P1"},
    {
        "sequence": 9,
        "type": "ZONE_CHANGE",
        "from": "STACK",
        "to": "BATTLEFIELD",
        "target_object": "obj:bears",
    },
    {
        "sequence": 10,
        "type": "TRIGGERED_ABILITY",
        "source_name": "Warstorm Surge",
        "source_object": "obj:surge",
    },
    {"sequence": 11, "type": "DAMAGED_PLAYER", "target_player": "P2", "amount": 2, "combat": False},
    {
        "sequence": 12,
        "type": "ATTACKER_DECLARED",
        "source_object": "obj:mp-attacker-0",
        "target_player": "P2",
    },
    {
        "sequence": 13,
        "type": "ZONE_CHANGE",
        "from": "COMMAND",
        "to": "STACK",
        "public_identity": True,
    },
]

TRACE = [
    mr.Frame("priority", "P1", ["Cast Grizzly Bears"], "Cast Grizzly Bears", scripted=True),
    mr.Frame("mana_payment", "P1", ["Forest"], "Forest", selected_option_type="mana_ability"),
    mr.Frame("mana_payment", "P1", ["Spend"], "Spend", selected_option_type="mana_pool"),
    mr.Frame(
        "target", "P1", ["Full Game Seat 2", "Full Game Seat 3"], "Full Game Seat 2", scripted=True
    ),
]


@pytest.mark.parametrize(
    "token",
    [
        "creature_enters",
        "creature_enters:obj:bears",
        "creature_entered",
        "trigger:Warstorm_Surge",
        "Warstorm_trigger",
        "damage:P2:2",
        "entering_creature_damage:P2:2",
        "noncombat_damage:P2:2",
        "spell_cast:obj:bears",
        "attacker_declared:obj:mp-attacker-0->P2",
        "commander_cast_from_command",
        "spell_resolved",
        "priority_decision_frame:P1",
        "target_decision_frame:P1",
        "target_selected:P2",
        "legal_targets_exposed",
        "mana_paid:1",
    ],
)
def test_an_observed_token_has_positive_evidence(token: str) -> None:
    assert mr.verify_token(token, TAPE, TRACE, set()) is not None


@pytest.mark.parametrize(
    "token",
    [
        "creature_enters:obj:other",
        "trigger:Soul_Warden",
        "damage:P2:3",
        "damage:P3:2",
        "spell_cast:obj:other",
        "attacker_declared:obj:mp-attacker-0->P3",
        "target_selected:P3",
        "declare_attacker_frame:P1",
        "mana_paid:2",
        "commander_tax:+4_generic",
        "state_based_actions",
        "layer7b_set_pt:1/1",
    ],
)
def test_an_unobserved_or_unknown_token_is_never_assumed(token: str) -> None:
    assert mr.verify_token(token, TAPE, TRACE, set()) is None


def _payment(taps: int, spends: int) -> list[mr.Frame]:
    return [
        mr.Frame("mana_payment", "P1", [], "Mountain", selected_option_type="mana_ability")
        for _ in range(taps)
    ] + [
        mr.Frame("mana_payment", "P1", [], "Spend", selected_option_type="mana_pool")
        for _ in range(spends)
    ]


def test_commander_tax_is_charged_mana_minus_the_declared_printed_value() -> None:
    trace = _payment(4, 4)
    assert mr.verify_token("commander_tax:+4_generic", [], trace, set(), 0) is not None
    assert mr.verify_token("commander_tax:+4_generic", [], trace, set(), 1) is None


def test_charged_mana_is_the_engine_charge_not_the_number_of_tapped_sources() -> None:
    """Tapping every declared source first made the tap count describe the
    declaration: a 4-mana charge paid from 5 tapped Islands still read as 5."""
    assert mr.verify_token("mana_paid:5", [], _payment(5, 4), set()) is None
    assert mr.verify_token("mana_paid:4", [], _payment(5, 4), set()) is None
    assert mr.verify_token("commander_tax:+4_generic", [], _payment(4, 2), set(), 0) is None
    charged = mr.TerminalCheck("mana_charged", value=5)
    assert mr.check_terminal(charged, {}, [], _payment(5, 5))
    assert not mr.check_terminal(charged, {}, [], _payment(5, 4))


def test_mana_is_spent_from_the_pool_before_another_source_is_tapped() -> None:
    def action(option_type: str, source: str | None = None) -> dict[str, Any]:
        engine = {"source_object_id": source} if source else {}
        return {"metadata": {"option_type": option_type, "xmage_option_metadata": engine}}

    tap = action("mana_ability", "native-island-1")
    spend = action("mana_pool")
    assert mr._mana_offer({"actions": [tap, spend]}, ["native-island-1"]) is spend
    assert mr._mana_offer({"actions": [tap]}, ["native-island-1"]) is tap
    # Two advancing spends would be a colour choice: never made for the pilot.
    assert mr._mana_offer({"actions": [spend, action("mana_pool")]}, []) is None


def test_terminal_checks_read_the_engine_observation() -> None:
    observation = {
        "seats": [
            {
                "player_id": "P1",
                "life": 40,
                "commanders": [{"prior_casts": 3}],
                "battlefield": [{"card_identity": "Grizzly Bears", "tapped": True}],
            },
            {"player_id": "P2", "life": 38, "commanders": [], "battlefield": []},
        ]
    }
    assert mr.check_terminal(
        mr.TerminalCheck("life", principal="P2", value=38), observation, TAPE, TRACE
    )
    assert not mr.check_terminal(
        mr.TerminalCheck("life", principal="P2", value=18), observation, TAPE, TRACE
    )
    assert mr.check_terminal(
        mr.TerminalCheck("trigger_count", source_name="Warstorm Surge", value=1),
        observation,
        TAPE,
        TRACE,
    )
    assert mr.check_terminal(
        mr.TerminalCheck("commander_prior_casts", principal="P1", value=3), observation, TAPE, TRACE
    )
    assert mr.check_terminal(
        mr.TerminalCheck("tapped", principal="P1", card_identity="Grizzly Bears", value=True),
        observation,
        TAPE,
        TRACE,
    )
    assert not mr.check_terminal(mr.TerminalCheck("no_mana_payment"), observation, TAPE, TRACE)


def _verified() -> mr.RowExecution:
    return mr.RowExecution(
        "MICRO_TRIGGERS",
        True,
        "EXACT",
        "obligation observed",
        token_evidence={"damage:P2:2": {"events": [11]}},
        terminal_facts={"P2 is at 38 life": True},
        tape=TAPE,
    )


def test_an_unverified_row_gets_no_receipt() -> None:
    execution = _verified()
    execution.verified = False
    with pytest.raises(ValueError):
        mr.positive_receipt(
            execution, _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
        )


def _persist(tmp_path: Path, receipt: dict[str, Any]) -> Path:
    directory = tmp_path / R.POSITIVE_RECEIPT_SUBDIR
    R.persist(directory / "MICRO_TRIGGERS.json", receipt)
    return directory


def test_a_verified_receipt_loads_and_is_credited(tmp_path: Path) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    directory = _persist(tmp_path, receipt)
    loaded, rejected = R.collect_positive_fixture_receipts(directory)
    assert rejected == []
    credit = R.positive_fixture_credit(
        loaded,
        candidate="xmage",
        expected_commit=COMMIT,
        denominator={"MICRO_TRIGGERS"},
        expected_runner_digest=RUNNER,
    )
    assert credit == {"MICRO_TRIGGERS": [mr.TEST_IDENTITY_PREFIX + "MICRO_TRIGGERS"]}
    # The native-suite loader reads only the top level and never sees it.
    assert R.collect_receipts(tmp_path) == ([], [])


@pytest.mark.parametrize(
    ("commit", "runner", "denominator"),
    [
        ("8" * 40, RUNNER, {"MICRO_TRIGGERS"}),
        (COMMIT, "s" * 64, {"MICRO_TRIGGERS"}),
        (COMMIT, RUNNER, {"CARD_02"}),
    ],
)
def test_a_receipt_is_credited_only_for_its_candidate_runner_and_denominator(
    tmp_path: Path, commit: str, runner: str, denominator: set[str]
) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    loaded, _ = R.collect_positive_fixture_receipts(_persist(tmp_path, receipt))
    assert (
        R.positive_fixture_credit(
            loaded,
            candidate="xmage",
            expected_commit=commit,
            denominator=denominator,
            expected_runner_digest=runner,
        )
        == {}
    )


@pytest.mark.parametrize("defect", ["tampered", "missing_field", "wrong_schema"])
def test_a_defective_receipt_is_rejected(tmp_path: Path, defect: str) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    if defect == "tampered":
        receipt["fixture_id"] = "CARD_02"
    elif defect == "missing_field":
        del receipt["observed_assertion"]
        receipt["receipt_digest"] = R._digest(
            {k: v for k, v in receipt.items() if k != "receipt_digest"}
        )
    else:
        receipt["schema_version"] = R.NATIVE_SUITE_RECEIPT_SCHEMA
    loaded, rejected = R.collect_positive_fixture_receipts(_persist(tmp_path, receipt))
    assert loaded == []
    assert len(rejected) == 1


class _RefusingLane:
    """A lane that refuses every row at creation; no engine process is started."""

    engine_commit = COMMIT

    def __enter__(self) -> _RefusingLane:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def request(self, message_type: str, payload: object) -> dict[str, Any]:
        return {"success": False, "errors": [{"code": "refused"}]}

    def read_dimension_manifest(self) -> None:
        return None


def test_execute_and_persist_clears_its_own_stale_receipts_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row that no longer verifies loses its earlier receipt; receipts written by
    other direct producers into the same directory (R-4) are not this producer's
    to delete."""

    class _Probe:
        SEED = 424242

        @staticmethod
        def open_client(workspace: Path) -> _RefusingLane:
            return _RefusingLane()

    monkeypatch.setattr(mr, "_PROBE", _Probe())
    directory = tmp_path / R.POSITIVE_RECEIPT_SUBDIR
    directory.mkdir()
    own = directory / "PILOT_PRIORITY.json"
    own.write_text(json.dumps({"schema_version": "stale"}), encoding="utf-8")
    foreign = directory / "direct-lifecycle-PLAYER_COUNT_4P.json"
    foreign.write_text(json.dumps({"schema_version": "other producer"}), encoding="utf-8")
    summary = mr.execute_and_persist(
        workspace=tmp_path,
        records={"PILOT_PRIORITY": {"fixture_id": "PILOT_PRIORITY"}},
        candidate_commit=COMMIT,
        runner_digest=RUNNER,
        out_dir=directory,
        fixtures=("PILOT_PRIORITY",),
    )
    assert not own.exists()
    assert foreign.exists()
    assert summary["rows_verified"] == 0
    assert summary["rows"]["PILOT_PRIORITY"]["verified"] is False


def test_decision_families_map_to_the_engine_decision_class() -> None:
    trace = [mr.Frame("mode", "P1", ["a", "b"], "b", scripted=True, selected_key="create_devils")]
    assert mr.verify_token("choose_mode_frame:P1", [], trace, set()) is not None
    assert mr.verify_token("choose_mode_frame:P2", [], trace, set()) is None
    assert mr.verify_token("mode_selected:create_devils", [], trace, set()) is not None
    assert mr.verify_token("mode_selected:deal_damage", [], trace, set()) is None
    unscripted = [mr.Frame("mode", "P1", ["a", "b"], "b", selected_key="create_devils")]
    assert mr.verify_token("mode_selected:create_devils", [], unscripted, set()) is None


def test_x_is_the_number_the_engine_accepted_on_the_announce_frame() -> None:
    trace = [mr.Frame("announce_x", "P1", ["Provide numeric choice"], scripted=True, numeric=3)]
    assert mr.verify_token("x_announced:3", [], trace, set()) is not None
    assert mr.verify_token("x_announced:2", [], trace, set()) is None
    assert mr.verify_token("announce_x_frame:P1", [], trace, set()) is not None


def _mode_legal() -> dict[str, Any]:
    def mode(label: str) -> dict[str, Any]:
        return {"metadata": {"option_type": "mode", "label": label}}

    return {
        "actions": [
            mode("{this} deals 5 damage to each creature and each planeswalker."),
            mode('Create three 1/1 red Devil creature tokens with "When this creature dies..."'),
        ]
    }


def _step(kind: str, value: Any) -> dict[str, Any]:
    return {
        "decision_family": "choose_mode",
        "selection": {"selector_kind": kind, "semantic_value": value},
    }


def test_a_mode_key_selects_exactly_the_engine_mode_its_binding_names() -> None:
    spec = mr.RowSpec(mode_bindings=(("create_devils", "Devil creature tokens"),))
    answer = mr._scripted_answer(
        _mode_legal(), _step("semantic_mode_key", "create_devils"), {}, spec
    )
    assert "Devil" in mr._label_of(answer.action) and answer.key == "create_devils"


@pytest.mark.parametrize(
    "bindings",
    [(), (("create_devils", "Angel"),), (("create_devils", "creature"),)],
    ids=["unbound", "no-match", "ambiguous"],
)
def test_a_mode_key_without_exactly_one_matching_offer_fails_closed(
    bindings: tuple[tuple[str, str], ...],
) -> None:
    spec = mr.RowSpec(mode_bindings=bindings)
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_answer(_mode_legal(), _step("semantic_mode_key", "create_devils"), {}, spec)


def test_an_integer_answer_goes_only_to_the_engine_numeric_offer() -> None:
    numeric = {"metadata": {"option_type": "numeric_choice", "label": "Provide numeric choice"}}
    answer = mr._scripted_answer({"actions": [numeric]}, _step("integer", 3), {}, mr.RowSpec())
    assert answer.action is numeric and answer.numeric == 3
    for bad in (True, "3", None):
        with pytest.raises(mr.ml.MidgameLaneError):
            mr._scripted_answer({"actions": [numeric]}, _step("integer", bad), {}, mr.RowSpec())
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_answer({"actions": []}, _step("integer", 3), {}, mr.RowSpec())


def test_engine_side_terminal_checks() -> None:
    tape: list[dict[str, Any]] = [
        {"type": "ZONE_CHANGE", "from": "LIBRARY", "to": "HAND", "player_player": "P1"},
        {"type": "ZONE_CHANGE", "from": "LIBRARY", "to": "HAND", "player_player": "P1"},
        {"type": "ZONE_CHANGE", "from": "LIBRARY", "to": "HAND", "player_player": "P2"},
        {"type": "ZONE_CHANGE", "from": "GRAVEYARD", "to": "HAND", "player_player": "P1"},
        {"type": "CREATED_TOKEN", "target_name": "Devil Token"},
        {"type": "CREATED_TOKEN", "target_name": "Devil Token"},
    ]
    draws = mr.TerminalCheck("draws", principal="P1", value=2)
    assert mr.check_terminal(draws, {}, tape, [])
    assert not mr.check_terminal(mr.TerminalCheck("draws", principal="P1", value=3), {}, tape, [])
    devils = mr.TerminalCheck("tokens_created", card_identity="Devil", value=2)
    assert mr.check_terminal(devils, {}, tape, [])
    assert not mr.check_terminal(
        mr.TerminalCheck("tokens_created", card_identity="Devil", value=3), {}, tape, []
    )
    quiet = mr.TerminalCheck("no_permanent_damage")
    assert mr.check_terminal(quiet, {}, tape, [])
    assert not mr.check_terminal(quiet, {}, [*tape, {"type": "DAMAGED_PERMANENT"}], [])


def test_an_obligation_that_observes_nothing_is_never_verified() -> None:
    """A row with no required event and no terminal check would verify for any
    behaviour; it must stop before the lane is even driven."""
    record = {"fixture_id": "WS05-CMD-PARTNER-DMG", "expected_events": {"required_events": []}}
    execution = mr.execute_row(object(), record, {}, mr.RowSpec())  # type: ignore[arg-type]
    assert not execution.verified
    assert "no required event and no terminal check" in execution.detail


def test_every_registered_row_observes_something() -> None:
    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    records = {
        r["fixture_id"]: r
        for r in load_effective_materialization(
            Path(__file__).resolve().parents[2]
        ).denominator_records()
    }
    for fixture_id, spec in mr.ROWS.items():
        required = records[fixture_id]["expected_events"]["required_events"]
        assert required or spec.terminal_checks, fixture_id


def _ordering_legal() -> dict[str, Any]:
    def ability(source: str) -> dict[str, Any]:
        return {
            "metadata": {
                "option_type": "triggered_ability",
                "label": f"{source} - ability",
                "xmage_option_metadata": {"source_name": source},
            }
        }

    return {"actions": [ability("Mystic Remora"), ability("Phyrexian Arena")]}


def _order_step(value: Any) -> dict[str, Any]:
    return {
        "decision_family": "trigger_order",
        "selection": {"selector_kind": "order", "semantic_value": value},
    }


def test_the_order_selector_names_the_ability_to_put_on_the_stack_next() -> None:
    order = ["trigger:Phyrexian_Arena", "trigger:Mystic_Remora"]
    first = mr._scripted_answer(_ordering_legal(), _order_step(order), {}, mr.RowSpec())
    assert first.key == "trigger:Phyrexian_Arena"
    second = mr._scripted_answer(_ordering_legal(), _order_step(order), {}, mr.RowSpec(), 1)
    assert second.key == "trigger:Mystic_Remora"
    for bad in (["trigger:Soul_Warden"], ["Phyrexian Arena"], "trigger:Phyrexian_Arena", []):
        with pytest.raises(mr.ml.MidgameLaneError):
            mr._scripted_answer(_ordering_legal(), _order_step(bad), {}, mr.RowSpec())


def test_simultaneous_triggers_need_the_ordering_frame_and_the_abilities_put() -> None:
    frame = mr.Frame("trigger_order", "P1", ["Remora", "Arena"], "Arena", scripted=True)
    put = [
        {"sequence": 6, "type": "TRIGGERED_ABILITY", "player_player": "P1"},
        {"sequence": 7, "type": "TRIGGERED_ABILITY", "player_player": "P1"},
    ]
    assert mr.verify_token("simultaneous_triggers:P1:2", put, [frame], set()) is not None
    assert mr.verify_token("simultaneous_triggers:P1:2", put[:1], [frame], set()) is None
    assert mr.verify_token("simultaneous_triggers:P1:2", put, [], set()) is None
    assert mr.verify_token("simultaneous_triggers:P2:2", put, [frame], set()) is None


def test_the_stack_order_is_the_order_the_engine_put_the_abilities() -> None:
    check = mr.TerminalCheck(
        "stack_order", principal="P1", value=("Phyrexian Arena", "Mystic Remora")
    )
    arena_first = [
        {"type": "TRIGGERED_ABILITY", "player_player": "P1", "source_name": "Phyrexian Arena"},
        {"type": "TRIGGERED_ABILITY", "player_player": "P1", "source_name": "Mystic Remora"},
    ]
    assert mr.check_terminal(check, {}, arena_first, [])
    assert not mr.check_terminal(check, {}, list(reversed(arena_first)), [])
    assert not mr.check_terminal(check, {}, arena_first[:1], [])


def _game_start(draw_player: str | None) -> list[dict[str, Any]]:
    tape: list[dict[str, Any]] = [
        {"sequence": 1, "type": "LIBRARY_SHUFFLED", "turn": 1, "player_player": "P1"},
        {"sequence": 2, "type": "BEGIN_TURN", "turn": 1, "player_player": "P1"},
    ]
    if draw_player is not None:
        tape.append(
            {
                "sequence": 3,
                "type": "ZONE_CHANGE",
                "turn": 1,
                "step": "DRAW",
                "from": "LIBRARY",
                "to": "HAND",
                "player_player": draw_player,
            }
        )
    return tape


def test_the_starting_player_is_the_engines_first_turn() -> None:
    assert mr.verify_token("starting_player:P1", _game_start("P1"), [], set()) is not None
    assert mr.verify_token("starting_player:P2", _game_start("P1"), [], set()) is None
    # A tape that does not start at the game start has no first turn to read.
    later = [{"sequence": 9, "type": "BEGIN_TURN", "turn": 2, "player_player": "P1"}]
    assert mr.verify_token("starting_player:P1", later, [], set()) is None


def test_the_first_turn_draw_is_the_starting_players_draw_step_draw() -> None:
    assert mr.verify_token("first_turn_draw:true", _game_start("P1"), [], set()) is not None
    # CR 103.8a: in a two-player game the starting player skips it.
    assert mr.verify_token("first_turn_draw:true", _game_start(None), [], set()) is None
    assert mr.verify_token("first_turn_draw:true", _game_start("P2"), [], set()) is None
    main_phase_draw = _game_start("P1")
    main_phase_draw[-1]["step"] = "PRECOMBAT_MAIN"
    assert mr.verify_token("first_turn_draw:true", main_phase_draw, [], set()) is None
