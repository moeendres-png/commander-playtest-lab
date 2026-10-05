"""#561 B1: the Forge causal route's widened selectors, terminal and cast predicate.

A scripted cast on the caused stack (``scripted_decision_offered``) is answered
only with engine-offered options that match the record's own declared steps;
every cast is complete only when the engine returns priority to its caster with
the source on top of the stack. The controls here are the wrong-reason reds of
the B.4 evidence plan: a non-first target is never replaced by the first option,
an injected stack is refused, a legal-but-undeclared mana source is rejected by
the Lab, and a payment the declaration cannot cover never passes.
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
    forge_residuals as fr,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_scenario_lane as fsl,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    scripted_selection as ss,
)

FALLBACKS = sorted(ss.FORBIDDEN_FALLBACKS)
ENTRY = {
    "entry_mode": "causal_stack",
    "terminal": "scripted_decision_offered",
    "fuel": [
        {"semantic_id": "obj:fuel-mountain-p2", "card_identity": "Mountain", "owner": "P2"},
    ],
}


def _selection(kind: str, value: Any) -> dict[str, Any]:
    return {
        "matches_only_provider_offered_legal_options": True,
        "on_multiple_match": "FAIL_CLOSED",
        "on_zero_match": "FAIL_CLOSED",
        "selector_kind": kind,
        "semantic_value": value,
    }


def _step(family: str, kind: str, value: Any) -> dict[str, Any]:
    return {
        "actor": "P1",
        "causal_step_id": "cast-counter",
        "decision_family": family,
        "forbidden_fallbacks": FALLBACKS,
        "selection": _selection(kind, value),
    }


def _object(sid: str, card: str, controller: str, zone: str) -> dict[str, Any]:
    return {
        "semantic_id": sid,
        "card_identity": card,
        "controller": controller,
        "owner": controller,
        "zone": zone,
        "tapped": False,
        "counters": {},
        "face_down": False,
    }


def _record(sources: tuple[str, ...] = ("obj:island-a", "obj:island-b")) -> dict[str, Any]:
    """MICRO_MANA_PAYMENT's shape: P2's Bolt caused, P1 counters it from two Islands."""
    return {
        "fixture_id": "MICRO_MANA_PAYMENT",
        "players": [{"player_id": f"P{seat}"} for seat in range(1, 5)],
        "semantic_objects": [
            _object("obj:island-a", "Island", "P1", "battlefield"),
            _object("obj:island-b", "Island", "P1", "battlefield"),
            _object("obj:counterspell", "Counterspell", "P1", "hand"),
            _object("obj:bolt", "Lightning Bolt", "P2", "stack"),
        ],
        "stack_state": [
            {
                "cast_complete": True,
                "controller": "P2",
                "costs_paid": True,
                "modes": [],
                "source_semantic_id": "obj:bolt",
                "targets": ["P2"],
            }
        ],
        "action_cost_state": [
            {
                "actor": "P1",
                "explicit_payment_sources": list(sources),
                "payable": True,
                "source_semantic_id": "obj:counterspell",
            }
        ],
        "decision_script": [
            _step("priority", "semantic_action", {"action": "cast", "object": "obj:counterspell"}),
            _step("target", "semantic_stack_object", "stack:1"),
            _step("mana_payment", "mana_payment", {"mana": ["U", "U"]}),
        ],
        "expected_events": {
            "required_events": ["mana_abilities_activated:2", "mana_paid:UU", "Counterspell_cast"]
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


def _frame(kind: str, actor: str, *actions: dict) -> dict:
    return {"decision": {"kind": kind, "actor": actor}, "actions": list(actions)}


ISLAND = "Tap Island for mana"
DECLINE = _action("decline", "tap_mana_source", "Decline to tap (leave cost unpaid)")
BOLT = "Lightning Bolt (411) - Lightning Bolt (411) deals 3 damage to forge-p2."
COUNTER = "Counterspell (410) - Counter Lightning Bolt (411)."


def _players(tapped_islands: int = 0) -> list[dict]:
    details = [
        {"name": "Island", "tapped": index < tapped_islands, "counters": {}} for index in range(2)
    ]
    return [
        {
            "player_id": "p1",
            "mana_pool": {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0},
            "zones": {"battlefield": ["Island", "Island"], "battlefield_details": details},
        },
        {"player_id": "p2", "zones": {}},
    ]


def _state(stack: list[str], priority: str, tapped_islands: int = 0) -> dict:
    return {
        "stack": stack,
        "players": _players(tapped_islands),
        "turn_number": 1,
        "phase": "precombat_main",
        "step": "MAIN1",
        "active_player_id": "p1",
        "priority_player_id": priority,
    }


def _frames() -> list[dict]:
    """The engine frames of the pinned bridge for this scenario (shape observed live)."""
    players = [
        _action(
            f"t-{seat}",
            "target",
            f"Target [player {seat};]",
            refs=[{"kind": "player", "player_id": seat}],
        )
        for seat in ("p1", "p2", "p3", "p4")
    ]
    return [
        _priority(
            "p1",
            _action("cs-early", "cast_spell", "Counterspell [cast_spell] ({U}{U})", "Counterspell"),
        ),
        _priority(
            "p2",
            _action("bolt", "cast_spell", "Lightning Bolt [cast_spell] ({R})", "Lightning Bolt"),
        ),
        _frame("TARGET_SELECTION", "p2", *players),
        _frame(
            "MANA_PAYMENT",
            "p2",
            _action("tap-mountain", "tap_mana_source", "Tap Mountain for mana", "Mountain"),
            DECLINE,
        ),
        _priority("p2"),  # 4: the Bolt's cast is complete
        _priority("p3"),
        _priority("p4"),
        _priority(
            "p1", _action("cs", "cast_spell", "Counterspell [cast_spell] ({U}{U})", "Counterspell")
        ),
        _frame(
            "MANA_PAYMENT",
            "p1",
            _action("i1", "tap_mana_source", ISLAND, "Island"),
            _action("i2", "tap_mana_source", ISLAND, "Island"),
            DECLINE,
        ),
        _frame("MANA_PAYMENT", "p1", _action("i3", "tap_mana_source", ISLAND, "Island"), DECLINE),
        _priority("p1"),  # 10: Counterspell's cast is complete
        _priority("p2"),
        _priority("p3"),
        _priority("p4"),
        _priority("p1"),  # 14: settled
    ]


STATES = {
    0: _state([], "p1"),
    4: _state([BOLT], "p2"),
    7: _state([BOLT], "p1"),
    10: _state([COUNTER, BOLT], "p1", tapped_islands=2),
    14: _state([], "p1", tapped_islands=2),
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

    def submitted(self) -> list[str]:
        return [p["proposal"]["legal_action_id"] for m, p in self.requests if m == "submit_action"]


def _plan(record: dict, entry: dict = ENTRY) -> fcr.CausalPlan:
    plan = fcr.causal_plan(record, entry)
    assert plan is not None
    return plan


def _run(monkeypatch, frames=None, states=STATES, record=None, entry=ENTRY):
    bridge = FakeBridge(frames if frames is not None else _frames(), states)
    monkeypatch.setattr(fcr, "poll_decision", bridge.poll)
    monkeypatch.setattr(fcr, "decision_identity_params", lambda _c, _f: {})
    record = record or _record()
    run = fcr.run_causal_route(
        bridge,  # type: ignore[arg-type]
        "g",
        record,
        _plan(record, entry),
        seat_count=4,
        observe=bridge.observe,
        answer_frame_kinds=frozenset(),
        checkpoint_priority="p1",
    )
    return bridge, run


def _model(record: dict, monkeypatch, entry: dict = ENTRY) -> fsl.RequestedStateModel:
    monkeypatch.setattr(fcr, "declared_causal_entry", lambda _fixture_id: entry)
    return fsl.model_requested_state(record)


# ---------------------------------------------------------------------------
# Decision classes: named, never answered without a selector
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kind", "decision_class"),
    [
        ("MODE_SELECTION", "mode"),
        ("COST_SELECTION", "cost"),
        ("ORDER_CHOICE", "cost_order"),
        ("AMOUNT_DISTRIBUTION", "amount"),
        ("X_ANNOUNCE", "amount"),
        ("TRIGGER_ORDER", "order"),
    ],
)
def test_new_frame_kinds_are_mapped_but_have_no_scripted_selector(kind, decision_class) -> None:
    frame = _frame(kind, "p1", _action("a", "structural_decision", "Option A"))
    assert ss.forge_options(frame)[0] == decision_class
    assert decision_class not in ss.FAMILIES_WITH_SELECTORS
    step = {**_step(decision_class, "anything", "a")}
    with pytest.raises(ss.SelectionFailure, match="selector_not_supported"):
        ss.select(step, decision_class, ss.forge_options(frame)[1], {})


def test_an_unmapped_frame_kind_still_raises() -> None:
    with pytest.raises(ss.SelectionFailure, match="frame_kind_not_mapped"):
        ss.forge_options(_frame("COPY_CHOICE", "p1"))


@pytest.mark.parametrize(
    "value", [{"mana": []}, {"mana": ["U", "X"]}, {"mana": [["U"]]}, {"mana": "UU"}, None]
)
def test_a_payment_step_must_declare_its_mana(value) -> None:
    with pytest.raises(ss.SelectionFailure, match="payment_mana_missing"):
        ss.payment_step_mana(_step("mana_payment", "mana_payment", value))


def test_a_payment_step_must_carry_the_fail_closed_contract() -> None:
    step = _step("mana_payment", "mana_payment", {"mana": ["U"]})
    step["selection"]["on_multiple_match"] = "FIRST"
    with pytest.raises(ss.SelectionFailure, match="selection_contract_not_fail_closed"):
        ss.payment_step_mana(step)
    assert ss.payment_step_mana(_step("mana_payment", "mana_payment", {"mana": ["U", "U"]})) == (
        "U",
        "U",
    )


# ---------------------------------------------------------------------------
# Positive control: the scripted cast on the caused stack
# ---------------------------------------------------------------------------
def test_the_scripted_cast_is_answered_only_with_declared_engine_options(monkeypatch) -> None:
    bridge, run = _run(monkeypatch)
    assert run.failure is None, run.failure
    # The caster's own PRIORITY frame offered the declared source; the cast is
    # the engine's option, the stack is exactly the record's.
    cast = next(frame for frame in run.frames if frame.reason == "causal cast obj:bolt")
    assert cast.kind == "PRIORITY" and cast.actor == "p2"
    assert "Lightning Bolt [cast_spell] ({R})" in cast.offered
    assert [fcr.stack_card(entry) for entry in run.stack_after_cast or ()] == ["Lightning Bolt"]
    # p2 is not the first target option: the declared one is chosen, never options[0].
    assert bridge.submitted() == ["bolt", "t-p2", "tap-mountain", "cs", "i1", "i3"]
    assert "cs-early" not in bridge.submitted()
    payments = [frame for frame in run.frames if frame.reason.startswith("declared payment ")]
    assert [frame.payment_source for frame in payments] == ["obj:island-a", "obj:island-b"]
    assert run.engine_assigned_targets == [
        {
            "source_semantic_id": "obj:counterspell",
            "targets": [
                {
                    "semantic_id": "obj:bolt",
                    "stack_entry": BOLT,
                    "card_id": "411",
                    "cast_text": COUNTER,
                    "basis": "sole valid target set: the bridge parks no frame; verified in readback",
                }
            ],
        }
    ]
    assert [snapshot["at"] for snapshot in run.snapshots] == [
        "cast_complete:obj:bolt",
        "stack_caused",
        "requested_checkpoint",
        "before_scripted_0",
        "cast_complete:obj:counterspell",
        "settled",
    ]


def test_the_mana_payment_obligation_is_observed_from_tape_and_readback(monkeypatch) -> None:
    model = _model(_record(), monkeypatch)
    assert fsl.causal_terminal(model) == "scripted_decision_offered"
    _, run = _run(monkeypatch)
    verdict = fsl.evaluate_scripted_decision_offered(model, run)
    assert verdict.observed and verdict.credit_eligible_observation, verdict.reason
    assert verdict.semantic_events == [
        "mana_abilities_activated:2",
        "mana_paid:UU",
        "Counterspell_cast",
    ]
    assert verdict.terminal_facts["requested_checkpoint"]["verdict"] == fsl.CHECKPOINT_EXACT


# ---------------------------------------------------------------------------
# Red A: a target that is not the first option, or not offered at all
# ---------------------------------------------------------------------------
def test_an_undeclared_causal_target_raises_and_never_takes_the_first_option(monkeypatch) -> None:
    record = _record()
    record["stack_state"][0]["targets"] = ["obj:counterspell"]  # in hand: never offered
    bridge, run = _run(monkeypatch, record=record)
    assert run.failure and "SelectionFailure: zero_match" in run.failure
    assert bridge.submitted() == ["bolt"]
    assert "t-p1" not in bridge.submitted()


def test_two_indistinguishable_targets_fail_closed(monkeypatch) -> None:
    """MICRO_PRIORITY's live shape: two P2 Grizzly Bears, one of them the target."""
    record = _record()
    record["semantic_objects"] += [
        _object("obj:p2-bears", "Grizzly Bears", "P2", "battlefield"),
        _object("obj:micro-target", "Grizzly Bears", "P2", "battlefield"),
    ]
    record["stack_state"][0]["targets"] = ["obj:micro-target"]
    bears = [
        _action(
            f"b{n}",
            "target",
            "Target [Grizzly Bears;]",
            refs=[
                {
                    "kind": "card",
                    "card_id": n,
                    "name": "Grizzly Bears",
                    "controller": "p2",
                    "zone": "Battlefield",
                }
            ],
        )
        for n in (405, 406)
    ]
    frames = _frames()
    frames[2] = _frame("TARGET_SELECTION", "p2", *bears)
    bridge, run = _run(monkeypatch, frames=frames, record=record)
    assert run.failure and "multiple_match" in run.failure
    assert bridge.submitted() == ["bolt"]


def test_the_scripted_cast_needs_its_declared_source_offered(monkeypatch) -> None:
    frames = _frames()
    frames[7] = _priority("p1", _action("other", "cast_spell", "Opt [cast_spell] ({U})", "Opt"))
    bridge, run = _run(monkeypatch, frames=frames)
    assert run.failure and "zero_match" in run.failure
    assert "other" not in bridge.submitted()


# ---------------------------------------------------------------------------
# Red B: the stack is caused, never injected
# ---------------------------------------------------------------------------
def test_an_injected_stack_is_refused_before_the_engine(monkeypatch) -> None:
    plan = _plan(_record())
    with pytest.raises(fcr.CausalRouteError, match="never injects a stack"):
        fcr.pre_causal_state({"stack": [{"card": "Lightning Bolt"}]}, plan)
    model = _model(_record(), monkeypatch)
    assert "stack" not in model.neutral_initial_state
    assert model.neutral_initial_state["hands"]["p2"] == ["Lightning Bolt"]


# ---------------------------------------------------------------------------
# Red C: a legal-but-undeclared source is rejected by the Lab
# ---------------------------------------------------------------------------
def test_an_undeclared_mountain_is_never_tapped(monkeypatch) -> None:
    frames = _frames()
    mountain = _action("m1", "tap_mana_source", "Tap Mountain for mana", "Mountain")
    frames[9] = _frame("MANA_PAYMENT", "p1", mountain, DECLINE)
    bridge, run = _run(monkeypatch, frames=frames)
    assert run.failure and "zero_match" in run.failure
    assert "m1" not in bridge.submitted() and "decline" not in bridge.submitted()


def test_a_third_undeclared_island_makes_the_payment_ambiguous(monkeypatch) -> None:
    frames = _frames()
    frames[8]["actions"].insert(2, _action("i9", "tap_mana_source", ISLAND, "Island"))
    bridge, run = _run(monkeypatch, frames=frames)
    assert run.failure and "mana_source_ambiguous" in run.failure
    assert not {"i1", "i2", "i9"} & set(bridge.submitted())


def test_a_tampered_payment_choice_is_rejected_by_the_contract(monkeypatch) -> None:
    """The engine would accept the Mountain; the Lab's tape check must not."""
    model = _model(_record(), monkeypatch)
    frames = _frames()
    frames[8]["actions"].insert(
        0, _action("m1", "tap_mana_source", "Tap Mountain for mana", "Mountain")
    )
    _, run = _run(monkeypatch, frames=frames)
    assert run.failure is None
    assert fsl.evaluate_scripted_decision_offered(model, run).observed
    tampered = copy.deepcopy(run)
    payment = next(f for f in tampered.frames if f.reason.startswith("declared payment "))
    payment.chosen_option_id = "m1"
    verdict = fsl.evaluate_scripted_decision_offered(model, tampered)
    assert not verdict.observed and not verdict.credit_eligible_observation
    assert "tape_choices_offered" in verdict.reason
    assert "mana_paid:UU" in verdict.reason
    relabelled = copy.deepcopy(tampered)
    payment = next(f for f in relabelled.frames if f.reason.startswith("declared payment "))
    payment.chosen, payment.chosen_source = "Tap Mountain for mana", "Mountain"
    verdict = fsl.evaluate_scripted_decision_offered(model, relabelled)
    assert not verdict.observed
    assert "not a tap of a declared payment source" in verdict.reason


# ---------------------------------------------------------------------------
# Red D: a declaration that cannot pay never passes
# ---------------------------------------------------------------------------
def test_a_payment_cut_to_one_source_declines_nothing_and_fails(monkeypatch) -> None:
    """One Island declared, two on the battlefield: the Lab cannot tell them apart."""
    record = _record(sources=("obj:island-a",))
    bridge, run = _run(monkeypatch, record=record)
    assert run.failure and "mana_source_ambiguous" in run.failure
    assert not {"i1", "i2", "i3", "decline"} & set(bridge.submitted())
    model = _model(record, monkeypatch)
    assert not fsl.evaluate_scripted_decision_offered(model, run).observed


def test_a_payment_the_declaration_cannot_cover_never_declines(monkeypatch) -> None:
    """One Island declared and on the battlefield: after it, only "decline" is left."""
    record = _record(sources=("obj:island-a",))
    record["semantic_objects"] = [
        o for o in record["semantic_objects"] if o["semantic_id"] != "obj:island-b"
    ]
    frames = _frames()
    frames[8]["actions"] = [_action("i1", "tap_mana_source", ISLAND, "Island"), DECLINE]
    frames[9]["actions"] = [DECLINE]
    bridge, run = _run(monkeypatch, frames=frames, record=record)
    assert run.failure and "zero_match" in run.failure
    assert bridge.submitted()[-1] == "i1" and "decline" not in bridge.submitted()


def test_fuel_cut_to_nothing_cannot_cause_the_stack(monkeypatch) -> None:
    entry = {**ENTRY, "fuel": []}
    bridge, run = _run(monkeypatch, entry=entry)
    assert run.failure and "zero_match" in run.failure
    assert bridge.submitted() == ["bolt", "t-p2"]


def test_an_unused_declared_source_fails_the_cast(monkeypatch) -> None:
    frames = _frames()
    del frames[9]  # the engine charged only one Island
    states = {key - (key > 9): value for key, value in STATES.items()}
    _, run = _run(monkeypatch, frames=frames, states=states)
    assert run.failure and "left declared payment sources unused" in run.failure


# ---------------------------------------------------------------------------
# The cast-complete predicate and the frames a cast may ask
# ---------------------------------------------------------------------------
def test_priority_without_the_source_on_the_stack_fails_closed(monkeypatch) -> None:
    states = {**STATES, 10: _state([BOLT], "p1", tapped_islands=2)}
    _, run = _run(monkeypatch, states=states)
    assert run.failure and "the engine stack holds 1 objects after the cast" in run.failure


def test_an_unasked_target_must_be_proven_from_the_readback(monkeypatch) -> None:
    states = {**STATES, 10: _state(["Counterspell (410) - Counter target spell.", BOLT], "p1", 2)}
    _, run = _run(monkeypatch, states=states)
    assert run.failure and "does not show it as the declared obj:bolt" in run.failure


def test_leaving_the_pre_causal_step_before_the_cast_fails_closed(monkeypatch) -> None:
    """The live MICRO_PRIORITY shape: an all-pass ring ends the main phase."""
    states = {**STATES, 1: {**_state([], "p2"), "phase": "combat", "step": "COMBAT_BEGIN"}}
    bridge, run = _run(monkeypatch, states=states)
    assert run.failure and "left the pre-causal position" in run.failure
    assert bridge.submitted() == []


def test_a_mode_frame_during_a_cast_has_no_declared_answer(monkeypatch) -> None:
    frames = _frames()
    frames.insert(8, _frame("MODE_SELECTION", "p1", _action("m", "mode", "Mode A")))
    bridge, run = _run(monkeypatch, frames=frames)
    assert run.failure and "no declared answer for the engine's MODE_SELECTION" in run.failure
    assert "m" not in bridge.submitted()


def test_a_cost_order_during_a_cast_uses_the_shared_native_order_policy(monkeypatch) -> None:
    frames = _frames()
    order = [
        {
            "action_id": f"o{n}",
            "action_type": "structural_decision",
            "metadata": {
                "label": f"order {n}",
                "decision_subtype": "cost_order",
                "cost_order_indices": indices,
            },
        }
        for n, indices in ((1, [1, 0]), (2, [0, 1]))
    ]
    frames.insert(8, _frame("ORDER_CHOICE", "p1", *order))
    states = {key + (key >= 8): value for key, value in STATES.items()}
    bridge, run = _run(monkeypatch, frames=frames, states=states)
    assert run.failure is None, run.failure
    assert "o2" in bridge.submitted() and "o1" not in bridge.submitted()
    assert any(frame.reason == "native cost-order policy" for frame in run.frames)


def test_a_cost_order_outside_a_cast_fails_closed(monkeypatch) -> None:
    frames = _frames()
    frames.insert(5, _frame("ORDER_CHOICE", "p3", _action("o", "structural_decision", "x")))
    bridge, run = _run(monkeypatch, frames=frames)
    assert run.failure and "no declared answer for the engine's ORDER_CHOICE" in run.failure
    assert "o" not in bridge.submitted()


def test_n_spells_are_cast_in_order_and_checked_top_first(monkeypatch) -> None:
    record = _record()
    record["semantic_objects"].append(_object("obj:shock", "Shock", "P2", "stack"))
    record["stack_state"].append(
        {
            "cast_complete": True,
            "controller": "P2",
            "costs_paid": True,
            "modes": [],
            "source_semantic_id": "obj:shock",
            "targets": ["P3"],
        }
    )
    entry = {
        **ENTRY,
        "fuel": [
            {"semantic_id": "obj:fuel-a", "card_identity": "Mountain", "owner": "P2"},
            {"semantic_id": "obj:fuel-b", "card_identity": "Mountain", "owner": "P2"},
        ],
    }
    plan = _plan(record, entry)
    assert [spell.semantic_id for spell in plan.spells] == ["obj:bolt", "obj:shock"]
    targets = [
        _action(
            f"t-{seat}",
            "target",
            f"Target [player {seat};]",
            refs=[{"kind": "player", "player_id": seat}],
        )
        for seat in ("p2", "p3")
    ]
    tap = _action("tap", "tap_mana_source", "Tap Mountain for mana", "Mountain")
    shock = "Shock (412) - Shock (412) deals 2 damage to forge-p3."
    frames = [
        _priority("p1"),
        _priority(
            "p2",
            _action("bolt", "cast_spell", "Lightning Bolt [cast_spell] ({R})", "Lightning Bolt"),
        ),
        _frame("TARGET_SELECTION", "p2", *targets),
        _frame("MANA_PAYMENT", "p2", tap),
        _priority("p2", _action("shock", "cast_spell", "Shock [cast_spell] ({R})", "Shock")),
        _frame("TARGET_SELECTION", "p2", *targets),
        _frame("MANA_PAYMENT", "p2", tap),
        _priority("p2"),
    ]
    good = {0: _state([], "p1"), 4: _state([BOLT], "p2"), 7: _state([shock, BOLT], "p2")}
    record["decision_script"] = []
    record["expected_events"] = {"required_events": []}
    bridge = FakeBridge([*frames, _priority("p3")], good)
    monkeypatch.setattr(fcr, "poll_decision", bridge.poll)
    monkeypatch.setattr(fcr, "decision_identity_params", lambda _c, _f: {})
    run = fcr.run_causal_route(
        bridge,  # type: ignore[arg-type]
        "g",
        record,
        plan,
        seat_count=4,
        observe=bridge.observe,
        answer_frame_kinds=frozenset(),
        checkpoint_priority=None,
        max_frames=len(frames),
    )
    assert run.stack_after_cast == [shock, BOLT]
    assert bridge.submitted() == ["bolt", "t-p2", "tap", "shock", "t-p3", "tap"]
    wrong = {**good, 7: _state([BOLT, shock], "p2")}
    bridge = FakeBridge(frames, wrong)
    monkeypatch.setattr(fcr, "poll_decision", bridge.poll)
    run = fcr.run_causal_route(
        bridge,  # type: ignore[arg-type]
        "g",
        record,
        plan,
        seat_count=4,
        observe=bridge.observe,
        answer_frame_kinds=frozenset(),
        checkpoint_priority=None,
    )
    assert run.failure and "did not complete" in run.failure


# ---------------------------------------------------------------------------
# Lane: routed is not credited; unobservable tokens are named
# ---------------------------------------------------------------------------
def test_resolution_tokens_have_no_observer_and_stay_unknown(monkeypatch) -> None:
    record = _record()
    record["expected_events"]["required_events"] += ["resolve:Counterspell"]
    model = _model(record, monkeypatch)
    _, run = _run(monkeypatch, record=record)
    verdict = fsl.evaluate_scripted_decision_offered(model, run)
    assert not verdict.observed and not verdict.credit_eligible_observation
    assert "resolve:Counterspell" in verdict.reason and "CR 608.2b" in verdict.reason
    assert not fsl.scripted_token_observable("resolve:Lightning_Bolt")
    assert fsl.scripted_token_observable("Counterspell_cast")


def test_the_effective_target_rows_stay_blocked_with_exact_reasons() -> None:
    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    records = {
        r["fixture_id"]: r for r in load_effective_materialization(REPO).denominator_records()
    }
    for fixture in ("MICRO_PRIORITY", "MICRO_STACK", "MICRO_MANA_PAYMENT"):
        model = fsl.model_requested_state(records[fixture])
        assert fsl.causal_terminal(model) == "scripted_decision_offered"
        statuses = {item.dimension: item.status for item in model.dimensions}
        assert statuses["stack_state"] == fsl.DIMENSION_CAUSED
        # Open gates, never credit: D2 owns the cost state, and exact hand
        # equality after the natural draw is an authority gate.
        assert statuses["action_cost_state"] == fsl.DIMENSION_UNSUPPORTED
        assert statuses["temporal_checkpoint.exact_hand_after_draw"] == fsl.DIMENSION_UNSUPPORTED
        assert not model.credit_eligible
        row = fr.classify_row(records[fixture])
        assert row.classification != fr.SCENARIO_LANE_EXECUTABLE
        if fixture != "MICRO_MANA_PAYMENT":
            assert {
                "scripted_token:resolve:Giant_Growth",
                "scripted_token:resolve:Lightning_Bolt",
            } <= {item["dimension"] for item in row.mechanisms}
