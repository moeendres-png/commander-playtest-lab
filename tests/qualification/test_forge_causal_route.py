"""#520: the Forge causal stack route casts a record's stack on engine frames.

The route never places a spell on the stack, never pays, resolves or decides
anything itself: every transition is an engine-offered option selected by the
shared fail-closed selector, and a frame it does not expect fails closed. The
lane judges the CR 903.9 commander zone choice from engine readback only.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_causal_route as fcr,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_scenario_lane as fsl,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    scripted_selection as ss,
)

ROGRAKH = "Rograkh, Son of Rohgahh"
FALLBACKS = sorted(ss.FORBIDDEN_FALLBACKS)
ENTRY = {
    "entry_mode": "causal_stack",
    "terminal": "commander_zone_choice",
    "fuel": [
        {"semantic_id": "obj:fuel-a", "card_identity": "Swamp", "owner": "P2"},
        {"semantic_id": "obj:fuel-b", "card_identity": "Swamp", "owner": "P2"},
    ],
}


def _record(answer: bool = True, choice: str = "command", zone: str = "graveyard") -> dict:
    return {
        "fixture_id": "WS05-CMD-ZONE-GY-YES",
        "players": [{"player_id": f"P{seat}"} for seat in range(1, 5)],
        "semantic_objects": [
            {
                "semantic_id": "obj:cmd",
                "card_identity": ROGRAKH,
                "commander_id": "cmd:P1-A",
                "controller": "P1",
                "owner": "P1",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:blade",
                "card_identity": "Doom Blade",
                "controller": "P2",
                "owner": "P2",
                "zone": "stack",
            },
        ],
        "stack_state": [
            {
                "cast_complete": True,
                "controller": "P2",
                "costs_paid": True,
                "modes": [],
                "source_semantic_id": "obj:blade",
                "targets": ["obj:cmd"],
            }
        ],
        "decision_script": [
            {
                "actor": "P1",
                "causal_step_id": "cause-0",
                "decision_family": "choice",
                "forbidden_fallbacks": FALLBACKS,
                "selection": {
                    "matches_only_provider_offered_legal_options": True,
                    "on_multiple_match": "FAIL_CLOSED",
                    "on_zero_match": "FAIL_CLOSED",
                    "selector_kind": "boolean",
                    "semantic_value": answer,
                },
            }
        ],
        "expected_events": {
            "required_events": [f"commander_zone_event:{zone}", f"commander_choice:{choice}"]
        },
        "temporal_state": {
            "turn_number": 1,
            "phase": "precombat_main",
            "step": "main",
            "active_player": "P1",
            "priority_player": "P1",
        },
    }


def _action(action_id: str, action_type: str, label: str, source=None, refs=()) -> dict:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "source_object_id": source,
        "metadata": {"label": label, "object_refs": list(refs)},
    }


def _priority(actor: str, *extra: dict) -> dict:
    return {
        "decision": {"kind": "PRIORITY", "actor": actor},
        "actions": [_action(f"pass-{actor}", "pass_priority", "Pass priority"), *extra],
    }


def _frames(answer_kind: str = "COMMANDER_MOVE") -> list[dict]:
    swamp = _action("tap", "tap_mana_source", "Tap Swamp for mana", "Swamp")
    return [
        _priority("p1"),
        _priority(
            "p2",
            _action("cast", "cast_spell", "Doom Blade [cast_spell] ({1}{B})", "Doom Blade"),
        ),
        {
            "decision": {"kind": "TARGET_SELECTION", "actor": "p2"},
            "actions": [
                _action(
                    "tgt",
                    "target",
                    f"Target [{ROGRAKH};]",
                    refs=[
                        {
                            "kind": "card",
                            "card_id": 100,
                            "name": ROGRAKH,
                            "controller": "p1",
                            "zone": "Battlefield",
                        }
                    ],
                )
            ],
        },
        {"decision": {"kind": "MANA_PAYMENT", "actor": "p2"}, "actions": [swamp, swamp]},
        {"decision": {"kind": "MANA_PAYMENT", "actor": "p2"}, "actions": [swamp]},
        _priority("p2"),
        _priority("p3"),
        _priority("p4"),
        _priority("p1"),
        {
            "decision": {"kind": answer_kind, "actor": "p1"},
            "actions": [
                _action("yes", "confirm", "Move to the command zone? [Yes]"),
                _action("no", "confirm", "Move to the command zone? [No]"),
            ],
        },
        _priority("p1"),
    ]


def _state(stack: list[str], **zones: list[str]) -> dict:
    return {
        "stack": stack,
        "players": [{"player_id": "p1", "zones": zones}],
        "turn_number": 1,
        "phase": "MAIN1",
        "step": "MAIN1",
        "active_player_id": "p1",
        "priority_player_id": "p1",
    }


class FakeBridge:
    """Hands the route scripted engine frames and records what it submitted."""

    def __init__(self, frames: list[dict], states: dict[int, dict]) -> None:
        self.frames = frames
        self.states = states
        self.index = -1
        self.requests: list[tuple[str, dict]] = []

    def poll(self, *_args: Any, **_kwargs: Any) -> dict:
        self.index += 1
        if self.index >= len(self.frames):
            raise AssertionError("the route polled past the scripted frames")
        return self.frames[self.index]

    def request(self, method: str, params: dict, **_kwargs: Any) -> dict:
        self.requests.append((method, params))
        return {"success": True}

    def observe(self, _game_id: str) -> dict:
        return self.states[max(key for key in self.states if key <= self.index)]


STATES = {
    0: _state([], battlefield=[ROGRAKH], command=["Commander Effect"]),
    5: _state(["Doom Blade (411) - Destroy Rograkh (100)."], battlefield=[ROGRAKH]),
    9: _state([], graveyard=[ROGRAKH], command=["Commander Effect"]),
    10: _state([], command=[ROGRAKH, "Commander Effect"]),
}


def _run(
    monkeypatch,
    frames: list[dict],
    states: dict[int, dict] = STATES,
    record=None,
    answer_kind: str = "COMMANDER_MOVE",
):
    bridge = FakeBridge(frames, states)
    monkeypatch.setattr(fcr, "poll_decision", bridge.poll)
    monkeypatch.setattr(fcr, "decision_identity_params", lambda _c, _f: {})
    record = record or _record()
    plan = fcr.causal_plan(record, ENTRY)
    assert plan is not None
    run = fcr.run_causal_route(
        bridge,  # type: ignore[arg-type]
        "g",
        record,
        plan,
        seat_count=4,
        observe=bridge.observe,
        answer_frame_kinds=frozenset({answer_kind}),
        checkpoint_priority="p1",
    )
    return bridge, run


def test_the_plan_binds_the_record_stack_and_the_declared_fuel() -> None:
    plan = fcr.causal_plan(_record(), ENTRY)
    assert plan is not None
    assert plan.spells == (fcr.StackSpell("obj:blade", "Doom Blade", "p2", ("obj:cmd",)),)
    assert [card.semantic_id for card in plan.fuel] == ["obj:fuel-a", "obj:fuel-b"]
    assert plan.to_document()["fuel_authority"].startswith("run_midgame_capability_probe")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["stack_state"][0].update(modes=["mode-1"]),
        lambda r: r["stack_state"][0].update(cast_complete=False),
        lambda r: r["stack_state"][0].update(costs_paid=False),
        lambda r: r["stack_state"][0].update(source_semantic_id="obj:unknown"),
        lambda r: r.update(stack_state=[]),
    ],
)
def test_an_incomplete_or_modal_stack_has_no_plan(mutate) -> None:
    record = _record()
    mutate(record)
    assert fcr.causal_plan(record, ENTRY) is None


def test_a_row_without_declared_fuel_has_no_plan() -> None:
    assert fcr.causal_plan(_record(), None) is None


def test_the_pre_causal_position_adds_the_spell_and_fuel_without_mutating() -> None:
    plan = fcr.causal_plan(_record(), ENTRY)
    assert plan is not None
    neutral = {"hands": {"p1": ["Mountain"]}, "battlefield": [{"card": ROGRAKH}]}
    original = copy.deepcopy(neutral)
    state = fcr.pre_causal_state(neutral, plan)
    assert neutral == original
    assert state["hands"] == {"p1": ["Mountain"], "p2": ["Doom Blade"]}
    assert state["battlefield"][1:] == [
        {"card": "Swamp", "controller": "p2", "owner": "p2"},
        {"card": "Swamp", "controller": "p2", "owner": "p2"},
    ]


def test_the_route_casts_targets_pays_and_answers_on_engine_frames(monkeypatch) -> None:
    bridge, run = _run(monkeypatch, _frames())
    assert run.failure is None
    submitted = [
        params["proposal"]["legal_action_id"]
        for method, params in bridge.requests
        if method == "submit_action"
    ]
    assert submitted == ["cast", "tgt", "tap", "tap", "yes"]
    assert sum(method == "pass_priority" for method, _ in bridge.requests) == 5
    assert run.stack_after_cast == ["Doom Blade (411) - Destroy Rograkh (100)."]
    assert run.scripted_answers == [
        {
            "step": "cause-0",
            "frame_kind": "COMMANDER_MOVE",
            "label": "Move to the command zone? [Yes]",
            "boolean": True,
        }
    ]
    assert [snapshot["at"] for snapshot in run.snapshots] == [
        "stack_caused",
        "requested_checkpoint",
        "before_scripted_0",
        "settled",
    ]


def test_an_unexpected_engine_frame_fails_closed(monkeypatch) -> None:
    frames = _frames()
    frames[9] = {"decision": {"kind": "DECLARE_ATTACKERS", "actor": "p1"}, "actions": []}
    _, run = _run(monkeypatch, frames)
    assert run.failure and "unexpected engine frame DECLARE_ATTACKERS" in run.failure


def test_a_stack_the_record_did_not_request_fails_closed(monkeypatch) -> None:
    states = {**STATES, 5: _state(["Doom Blade (411)", "Lightning Bolt (412)"])}
    _, run = _run(monkeypatch, _frames(), states)
    assert run.failure and "the engine stack holds 2 objects" in run.failure


def test_a_missing_target_option_fails_closed(monkeypatch) -> None:
    frames = _frames()
    frames[2]["actions"][0]["metadata"]["object_refs"][0]["controller"] = "p3"
    _, run = _run(monkeypatch, frames)
    assert run.failure and "zero_match" in run.failure


def test_declining_to_pay_is_never_chosen(monkeypatch) -> None:
    frames = _frames()
    frames[3]["actions"] = [
        _action("decline", "tap_mana_source", "Decline to tap (leave cost unpaid)")
    ]
    _, run = _run(monkeypatch, frames)
    assert run.failure and "zero_match" in run.failure


# ---------------------------------------------------------------------------
# Lane integration
# ---------------------------------------------------------------------------
def _model(record: dict, monkeypatch) -> fsl.RequestedStateModel:
    monkeypatch.setattr(fcr, "declared_causal_entry", lambda _fixture_id: ENTRY)
    return fsl.model_requested_state(record)


def test_a_routable_row_is_caused_not_unsupported(monkeypatch) -> None:
    model = _model(_record(), monkeypatch)
    assert model.causal_plan is not None
    statuses = {item.dimension: item.status for item in model.dimensions}
    assert statuses["stack_state"] == fsl.DIMENSION_CAUSED
    assert statuses["semantic_objects.zone:stack"] == fsl.DIMENSION_CAUSED
    assert statuses["decision_execution.choice.boolean"] == fsl.DIMENSION_CAUSED
    assert not model.hard_unsupported
    assert model.neutral_initial_state["hands"]["p2"] == ["Doom Blade"]
    assert not any(item.runtime_probe for item in model.dimensions)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["expected_events"].update(
            required_events=["commander_zone_event:library", "commander_choice:command"]
        ),
        lambda r: r["decision_script"][0]["selection"].update(selector_kind="semantic_choice_key"),
        lambda r: r["semantic_objects"][0].pop("commander_id"),
    ],
)
def test_a_row_the_lane_cannot_judge_stays_unsupported(mutate, monkeypatch) -> None:
    record = _record()
    mutate(record)
    model = _model(record, monkeypatch)
    assert model.causal_plan is None
    assert "stack_state" in {item.dimension for item in model.hard_unsupported}


def test_the_effective_rows_the_lane_routes(monkeypatch) -> None:
    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    records = load_effective_materialization(REPO).denominator_records()
    routed = sorted(r["fixture_id"] for r in records if fsl.lane_causal_plan(r) is not None)
    assert routed == sorted(
        f"WS05-CMD-ZONE-{zone}-{answer}"
        for zone in ("GY", "EXILE", "HAND")
        for answer in ("YES", "NO")
    )


def test_the_commander_zone_choice_is_judged_from_engine_facts(monkeypatch) -> None:
    model = _model(_record(), monkeypatch)
    _, run = _run(monkeypatch, _frames())
    verdict = fsl.evaluate_commander_zone_choice(model, run)
    assert verdict.observed and verdict.credit_eligible_observation, verdict.reason
    assert verdict.semantic_events == ["commander_zone_event:graveyard", "commander_choice:command"]


@pytest.mark.parametrize(
    ("frames", "states", "failed"),
    [
        (_frames("GENERIC_CONFIRM"), STATES, "causal route"),
        (_frames(), {**STATES, 10: _state([], graveyard=[ROGRAKH])}, "commander_choice"),
        (
            _frames(),
            {**STATES, 9: _state([], graveyard=[ROGRAKH], hand=[ROGRAKH])},
            "name_identifies_one_card",
        ),
        (_frames(), {**STATES, 9: _state([], exile=[ROGRAKH])}, "commander_zone_event"),
        (
            _frames(),
            {**STATES, 5: {**STATES[5], "priority_player_id": "p2"}},
            "requested_checkpoint",
        ),
        (
            _frames(),
            {
                **STATES,
                5: _state(["Doom Blade (411) - Destroy Grizzly Bears (7)."], battlefield=[ROGRAKH]),
            },
            "requested_checkpoint",
        ),
    ],
)
def test_the_commander_zone_choice_is_not_observed_on_other_facts(
    frames, states, failed, monkeypatch
) -> None:
    model = _model(_record(), monkeypatch)
    _, run = _run(monkeypatch, frames, states)
    verdict = fsl.evaluate_commander_zone_choice(model, run)
    assert not verdict.observed and not verdict.credit_eligible_observation
    assert failed in verdict.reason


def test_the_hand_replacement_is_asked_while_the_commander_is_on_the_battlefield(
    monkeypatch,
) -> None:
    record = _record(answer=False, choice="hand", zone="hand")
    model = _model(record, monkeypatch)
    states = {
        **STATES,
        9: _state(["Unsummon"], battlefield=[ROGRAKH]),
        10: _state([], hand=["Mountain", ROGRAKH]),
    }
    _, run = _run(
        monkeypatch,
        _frames("REPLACEMENT_CONFIRM"),
        states,
        record,
        answer_kind="REPLACEMENT_CONFIRM",
    )
    verdict = fsl.evaluate_commander_zone_choice(model, run)
    assert verdict.observed, verdict.reason
    assert verdict.semantic_events == ["commander_zone_event:hand", "commander_choice:hand"]


def test_a_failed_route_is_never_observed(monkeypatch) -> None:
    model = _model(_record(), monkeypatch)
    verdict = fsl.evaluate_commander_zone_choice(model, fcr.CausalRun(failure="boom"))
    assert not verdict.observed and "boom" in verdict.reason


def test_the_scripted_answer_is_refused_on_any_other_choice_frame(monkeypatch) -> None:
    """Review P2: a trigger the engine asks about first never gets the record's answer."""
    frames = _frames()
    frames.insert(
        8,
        {
            "decision": {"kind": "TRIGGER_PLAY", "actor": "p1"},
            "actions": [
                _action("ty", "confirm", "Play trigger? [Yes]"),
                _action("tn", "confirm", "Play trigger? [No]"),
            ],
        },
    )
    bridge, run = _run(monkeypatch, frames)
    assert run.failure and "answered only on ['COMMANDER_MOVE']" in run.failure
    submitted = [
        p["proposal"]["legal_action_id"] for m, p in bridge.requests if m == "submit_action"
    ]
    assert "ty" not in submitted and "tn" not in submitted


def test_a_choice_frame_before_the_cast_is_refused(monkeypatch) -> None:
    frames = _frames()
    frames.insert(
        0,
        {
            "decision": {"kind": "COMMANDER_MOVE", "actor": "p1"},
            "actions": [
                _action("gy", "confirm", "Move? [Yes]"),
                _action("gn", "confirm", "Move? [No]"),
            ],
        },
    )
    bridge, run = _run(monkeypatch, frames)
    assert run.failure and "after the requested stack is cast" in run.failure
    assert not [m for m, _ in bridge.requests if m == "submit_action"]


def test_the_requested_checkpoint_is_judged_from_the_engine_snapshot(monkeypatch) -> None:
    """Review P2: the record's checkpoint is the caused stack with P1 on priority."""
    model = _model(_record(), monkeypatch)
    _, run = _run(monkeypatch, _frames())
    verdict = fsl.evaluate_commander_zone_choice(model, run)
    checkpoint = verdict.terminal_facts["requested_checkpoint"]
    assert checkpoint["verdict"] == fsl.CHECKPOINT_EXACT, checkpoint
    assert checkpoint["fields"]["stack_target_card_id"]["observed"] is True
