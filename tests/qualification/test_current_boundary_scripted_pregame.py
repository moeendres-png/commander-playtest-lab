"""#441 PILOT_MULLIGAN: a record's scripted pregame on the candidate-neutral lane.

The driver answers every engine mulligan frame from the record's plan, for the
seat the engine names as the frame's actor (never the seat that happened to
poll), in the plan's order; an unscripted, extra or missing frame fails closed.
The row is credited only from the engine's own decisions and each seat's
engine-reported hand at the first priority after the pregame.
"""

from __future__ import annotations

import copy
import types
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import full107, game_driver
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = (("p1", False), ("p2", True), ("p3", True), ("p4", True), ("p1", True))
ENGINE_IDS = {"p1": "uuid-a", "p2": "uuid-b", "p3": "uuid-c", "p4": "uuid-d"}


def _record() -> dict[str, Any]:
    records = load_effective_materialization(REPO_ROOT).denominator_records()
    return copy.deepcopy(next(r for r in records if r["fixture_id"] == "PILOT_MULLIGAN"))


class _FakeProcess:
    """A bridge that reports seats either at creation or through state envelopes."""

    def __init__(
        self,
        *,
        roster_at_create: bool,
        hands: dict[str, int] | None = None,
        seed_echo: int | None = None,
        shuffles_on_mulligan: bool | None = True,
    ) -> None:
        self.roster_at_create = roster_at_create
        self.hands = hands or {seat: 7 for seat in ENGINE_IDS}
        self.seed_echo = seed_echo
        # None: a launch without the orchestration channel. True: every
        # mulligan shuffles the hand back (CR 103.5), as the engines do. False:
        # the engine accepts the answers but never performs a mulligan.
        self.shuffles_on_mulligan = shuffles_on_mulligan
        if shuffles_on_mulligan is not None:
            self.plan = types.SimpleNamespace(
                env_overrides={game_driver.ORCHESTRATION_KEY_VARIABLE: "11" * 32}
            )
        self.imports = 0
        self.decks: list[dict[str, Any]] = []
        self.mulligans: list[tuple[str, bool]] = []

    def actor(self, seat: str) -> str:
        return seat if self.roster_at_create else ENGINE_IDS[seat]

    def request(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        game_id: str | None = None,
        timeout_s: float = 0,
    ) -> dict[str, Any]:
        del game_id, timeout_s
        if message_type == "get_capabilities":
            supported = self.seed_echo is not None
            capabilities = {
                "seed_supported": supported,
                "constructed_state_supported": self.shuffles_on_mulligan is not None,
            }
            return {"success": True, "payload": {"capabilities": capabilities}}
        if message_type == "get_constructed_state":
            seats = {self.actor(seat): seat for seat in ENGINE_IDS}
            taken = {seat: 0 for seat in ENGINE_IDS}
            for actor, keep in self.mulligans:
                if not keep and self.shuffles_on_mulligan:
                    taken[seats.get(actor, actor)] += 1
            players = [
                {"player_id": seat.upper(), "library_shuffles": 1 + taken[seat]}
                for seat in ENGINE_IDS
            ]
            return {"success": True, "payload": {"constructed_state": {"players": players}}}
        if message_type in {"start_engine", "get_provider_version"}:
            return {"success": True, "payload": {}}
        if message_type == "import_deck":
            self.imports += 1
            self.decks.append(payload["deck"])
            return {"success": True, "payload": {"deck_handle": {"handle_id": f"d{self.imports}"}}}
        if message_type == "create_commander_game":
            created: dict[str, Any] = {"player_count": 4}
            request = payload.get("request") or {}
            if "starting_player_seat" in request:
                # An honest bridge echoes the starter it applied, and that it
                # was the requested one.
                created["starting_player_seat"] = request["starting_player_seat"]
                created["starting_player_seat_source"] = "REQUEST"
            if self.seed_echo is not None:
                created["rules_seed"] = self.seed_echo
            if self.roster_at_create:
                created["seats"] = [
                    {"seat": index, "player_id": seat} for index, seat in enumerate(ENGINE_IDS)
                ]
            return {"success": True, "payload": created}
        if message_type == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message_type == "resolve_mulligan":
            self.mulligans.append((str(payload["player_id"]), bool(payload["keep"])))
            return {"success": True, "payload": {"keep": payload["keep"]}}
        if message_type == "pass_priority":
            return {"success": True, "payload": {}}
        if message_type == "get_game_state":
            seat = str(payload["observer_player_id"])
            index = list(ENGINE_IDS).index(seat)
            rows = [
                {
                    "player_id": self.actor(other),
                    "seat": position,
                    "zones": {"hand": [None] * self.hands[other], "library_size": 92},
                    **({"is_actor": other == seat} if self.roster_at_create else {}),
                }
                for position, other in enumerate(ENGINE_IDS)
            ]
            state = {"players": rows, "turn_number": 1, "phase": "beginning", "step": "upkeep"}
            envelope = (
                {}
                if self.roster_at_create
                else {
                    "observer_player_id": seat,
                    "observer_seat": index,
                    "observer_engine_player_id": ENGINE_IDS[seat],
                }
            )
            return {"success": True, "payload": {"state": state, **envelope}}
        raise AssertionError(f"unexpected request {message_type}")


def _frame(kind: str, actor: str) -> dict[str, Any]:
    # Every frame is reported to the first seat that polls: the polled seat is
    # never the actor's identity.
    return {
        "seat": "p1",
        "decision": {
            "kind": kind,
            "actor": actor,
            "revision": 1,
            "decision_id": None,
            "status": "SUPPORTED",
        },
        "actions": (
            [{"action_id": "pass", "action_type": "pass_priority", "metadata": {}}]
            if kind == "PRIORITY"
            else [{"action_id": "keep"}, {"action_id": "mull"}]
        ),
        "raw": {},
    }


def _drive(
    monkeypatch: pytest.MonkeyPatch,
    proc: _FakeProcess,
    asked: list[str],
    plan: tuple[tuple[str, bool], ...] = PLAN,
) -> game_driver.CommandedGameResult:
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in asked]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    return game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        player_count=4,
        seed=424242,
        drive_to="priority",
        mulligan_plan=plan,
    )


ASKED_IN_PLAN_ORDER = ["p1", "p2", "p3", "p4", "p1"]


@pytest.mark.parametrize("roster_at_create", [False, True])
def test_every_mulligan_frame_is_answered_from_the_plan_for_its_actor(
    monkeypatch: pytest.MonkeyPatch, roster_at_create: bool
) -> None:
    proc = _FakeProcess(roster_at_create=roster_at_create)
    result = _drive(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert result.failure is None
    assert [keep for _, keep in proc.mulligans] == [keep for _, keep in PLAN]
    tape = [(e.seat, e.keep) for e in result.decision_tape if e.step == "mulligan"]
    assert tape == list(PLAN)
    # PB-03 AF04: each frame is taped as the engine offered and executed it, the
    # engine's own actor and no fabricated option id (a mulligan is a boolean
    # answer, not an offered option), exactly as on the generic keep path.
    for entry, (seat, _) in zip(
        [e for e in result.decision_tape if e.step == "mulligan"], PLAN, strict=True
    ):
        assert entry.actor == proc.actor(seat)
        assert entry.chosen_option_id is None
    assert all(
        e.policy == game_driver.SCRIPTED_MULLIGAN_POLICY
        for e in result.decision_tape
        if e.step == "mulligan"
    )
    hands = result.terminal_facts["post_pregame_zone_counts"]
    assert {seat: hands[seat]["hand_count"] for seat in ENGINE_IDS} == dict.fromkeys(ENGINE_IDS, 7)


@pytest.mark.parametrize(
    "asked",
    [
        # Another seat than the plan's next entry.
        ["p2", "p1", "p3", "p4", "p1"],
        # A frame after the plan is exhausted.
        [*ASKED_IN_PLAN_ORDER, "p2"],
        # A plan entry the engine never asked.
        ["p1", "p2", "p3", "p4"],
    ],
)
def test_an_unscripted_extra_or_missing_mulligan_fails_closed(
    monkeypatch: pytest.MonkeyPatch, asked: list[str]
) -> None:
    result = _drive(monkeypatch, _FakeProcess(roster_at_create=False), asked)
    assert result.failure is not None and "DecisionUnsatisfied" in result.failure
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"


def test_an_actor_outside_the_engines_roster_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False)
    frames = iter([_frame("MULLIGAN", "uuid-unknown")])
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    result = game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        player_count=4,
        seed=1,
        mulligan_plan=PLAN,
    )
    assert result.failure is not None and "not a seat" in result.failure
    assert proc.mulligans == []


def test_the_records_plan_and_script_must_agree() -> None:
    record = _record()
    assert full107.scripted_pregame_plan(record) == PLAN
    disagreeing = copy.deepcopy(record)
    disagreeing["decision_script"][0]["selection"]["semantic_value"] = "keep_opening_hand"
    with pytest.raises(ValueError):
        full107.scripted_pregame_plan(disagreeing)
    other_actor = copy.deepcopy(record)
    other_actor["decision_script"][1]["actor"] = "P3"
    with pytest.raises(ValueError):
        full107.scripted_pregame_plan(other_actor)


def _row(
    monkeypatch: pytest.MonkeyPatch, proc: _FakeProcess, asked: list[str]
) -> full107.RowResult:
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in asked]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    return full107.scripted_pregame_row(
        _record(),
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )


def test_the_records_own_decks_are_imported() -> None:
    decks = full107.record_decks(_record())
    assert [deck["commander_names"] for deck in decks] == [["Rograkh, Son of Rohgahh"]] * 4
    assert all(deck["mainboard"] == ["Mountain"] * 99 for deck in decks)
    broken = _record()
    broken["deck_state"][0]["library_template"]["count"] = 98
    with pytest.raises(ValueError):
        full107.record_decks(broken)


def test_the_observed_pregame_is_not_credited_without_construction_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242)
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    # The obligation is observed on the record's decks under the acknowledged
    # seed; the record's construction_validation still withholds credit.
    assert proc.decks == full107.record_decks(_record())
    assert row.evidence["unmet_required_events"] == []
    assert row.outcome == "UNKNOWN"
    assert "construction equality is unestablished" in row.reason


def test_an_unacknowledged_seed_is_never_credited(monkeypatch: pytest.MonkeyPatch) -> None:
    for proc in (
        _FakeProcess(roster_at_create=False),
        _FakeProcess(roster_at_create=False, seed_echo=7),
    ):
        row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
        assert row.outcome == "UNKNOWN"
        assert "did not acknowledge the record's Rules seed" in row.reason


def test_without_a_required_construction_check_the_observed_pregame_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The PASS path exists only for a record that does not require construction
    # equality; no current record is such a record.
    record = _record()
    record["construction_validation"] = {"required": False}
    frames = iter(
        [_frame("MULLIGAN", ENGINE_IDS[seat]) for seat in ASKED_IN_PLAN_ORDER]
        + [_frame("PRIORITY", ENGINE_IDS["p1"])]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    row = full107.scripted_pregame_row(
        record,
        _FakeProcess(roster_at_create=False, seed_echo=424242),  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )
    assert row.outcome == "PASS", row.reason


def test_a_bottomed_card_is_not_the_free_mulligan(monkeypatch: pytest.MonkeyPatch) -> None:
    # P1 kept six cards: one was bottomed, so "bottom_count:P1:0" is not shown.
    proc = _FakeProcess(
        roster_at_create=False, hands={"p1": 6, "p2": 7, "p3": 7, "p4": 7}, seed_echo=424242
    )
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["unmet_required_events"] == ["bottom_count:P1:0"]


def test_a_pregame_that_did_not_complete_is_never_credited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _row(monkeypatch, _FakeProcess(roster_at_create=False), ["p2", *ASKED_IN_PLAN_ORDER])
    assert row.outcome == "UNKNOWN"
    assert "did not complete" in row.reason


def test_only_the_declared_scripted_pregame_rows_take_this_route() -> None:
    assert full107.SCRIPTED_PREGAME_ROWS == ("PILOT_MULLIGAN", "WS05-CMD-MULL-2", "WS05-CMD-MULL-4")


def _mull_record(fixture_id: str) -> dict[str, Any]:
    records = load_effective_materialization(REPO_ROOT).denominator_records()
    return copy.deepcopy(next(r for r in records if r["fixture_id"] == fixture_id))


def _mull_row(
    monkeypatch: pytest.MonkeyPatch, proc: _FakeProcess, record: dict[str, Any]
) -> full107.RowResult:
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in ASKED_IN_PLAN_ORDER]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    return full107.scripted_pregame_row(
        record,
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )


def test_mull_4_states_the_same_plan_and_its_tokens_are_engine_measured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1.0.21: MULL-4's script states its own pregame plan (P1 mulligans, all
    # keep, P1 keeps again). mulligan_once:P1 is P1's one mulligan and keep;
    # free_mulligan:true is P1's seven-card hand at turn 1 (CR 103.5c).
    record = _mull_record("WS05-CMD-MULL-4")
    assert full107.scripted_pregame_plan(record) == PLAN
    assert record["expected_events"]["required_events"] == [
        "mulligan_once:P1",
        "free_mulligan:true",
    ]
    record["construction_validation"] = {"required": False}
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242)
    row = _mull_row(monkeypatch, proc, record)
    assert row.evidence["unmet_required_events"] == []
    assert row.outcome == "PASS", row.reason


def test_a_bottomed_card_is_no_free_mulligan_for_mull_4(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _mull_record("WS05-CMD-MULL-4")
    record["construction_validation"] = {"required": False}
    proc = _FakeProcess(
        roster_at_create=False, hands={"p1": 6, "p2": 7, "p3": 7, "p4": 7}, seed_echo=424242
    )
    row = _mull_row(monkeypatch, proc, record)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["unmet_required_events"] == ["free_mulligan:true"]


def test_mull_4_is_not_credited_without_construction_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242)
    row = _mull_row(monkeypatch, proc, _mull_record("WS05-CMD-MULL-4"))
    assert row.evidence["unmet_required_events"] == []
    assert row.outcome == "UNKNOWN"
    assert "construction equality is unestablished" in row.reason


def test_a_scripted_london_bottom_is_never_chosen_by_the_lab() -> None:
    # MULL-2 owes one card after a non-free two-player mulligan. No lane offers
    # an external bottom-card decision, so nothing is executed: the row is
    # UNKNOWN before any request, never a Lab-chosen card.
    record = _mull_record("WS05-CMD-MULL-2")
    assert full107.scripted_london_bottoms(record) == [("p1", {"Mountain": 1})]
    assert full107.scripted_pregame_plan(record) == (("p1", False), ("p2", True), ("p1", True))

    class _Untouched:
        def request(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("nothing may be sent for an unanswerable bottom selection")

    row = full107.scripted_pregame_row(
        record,
        _Untouched(),  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )
    assert row.outcome == "UNKNOWN"
    assert "London bottom selection" in row.reason
    assert row.evidence["scripted_london_bottoms"] == [["p1", {"Mountain": 1}]]


def test_an_answered_mulligan_the_engine_never_performed_is_not_observed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex P1 (#534): accepted answers and the final hand are not a mulligan."""
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242, shuffles_on_mulligan=False)
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["engine_performed_mulligans"] == dict.fromkeys(ENGINE_IDS, 0)
    # Every mulligan token needs the engine's own shuffle; keeps do not. The
    # plan's mulligan itself is unbacked too (#553 Audit 1 B4).
    assert row.evidence["unmet_required_events"] == [
        "mulligan:P1:round1",
        "cr103.5:engine_performed_mulligans",
    ]


def test_without_the_orchestration_channel_no_mulligan_is_observed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242, shuffles_on_mulligan=None)
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["engine_performed_mulligans"] is None
    assert row.evidence["unmet_required_events"] == [
        "mulligan:P1:round1",
        "cr103.5:engine_performed_mulligans",
    ]


def test_a_plan_mulligan_needs_engine_evidence_whatever_the_tokens_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#553 Audit 1 B4: the CR 103.5 gate follows the plan, not the token wording."""
    record = _record()
    record["expected_events"]["required_events"] = [
        token
        for token in record["expected_events"]["required_events"]
        if not token.startswith(("mulligan:", "mulligan_once:", "free_mulligan:"))
    ]
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242, shuffles_on_mulligan=False)
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in ASKED_IN_PLAN_ORDER]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    row = full107.scripted_pregame_row(
        record,
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )
    assert row.outcome == "UNKNOWN"
    assert "cr103.5:engine_performed_mulligans" in row.evidence["unmet_required_events"]
    assert not any(
        token.startswith("mulligan") for token in record["expected_events"]["required_events"]
    )


def test_the_engine_performed_exactly_the_planned_mulligans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242)
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert row.evidence["engine_performed_mulligans"] == {"p1": 1, "p2": 0, "p3": 0, "p4": 0}
    assert row.evidence["unmet_required_events"] == []


def test_mull_4_needs_the_engine_to_have_performed_the_mulligan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex P1 (#534): the fake that records resolve_mulligan without redrawing.

    With the independent construction gate disabled, the accepted answers and
    an unchanged seven-card hand used to clear mulligan_once and free_mulligan.
    """
    record = _mull_record("WS05-CMD-MULL-4")
    record["construction_validation"] = {"required": False}
    proc = _FakeProcess(roster_at_create=False, seed_echo=424242, shuffles_on_mulligan=False)
    row = _mull_row(monkeypatch, proc, record)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["unmet_required_events"] == [
        "mulligan_once:P1",
        "free_mulligan:true",
        "cr103.5:engine_performed_mulligans",
    ]
