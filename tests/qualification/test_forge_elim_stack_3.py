"""WS05-MP-ELIM-STACK-3 on the Forge lane: the victim's own stack, then its elimination.

P2's Lightning Bolt (aimed at P1) must be on the stack when P2 loses, and leave
with P2 without resolving (CR 800.4a). The Forge route casts the record's stack
on the engine's frames from a pre-causal position (P2 at its starting life,
openly substituted for the recorded 0), verifies it at the requested
checkpoint, and only then casts the declared instruments (the XMage lane's own
declaration: 14 Lightning Bolts and 14 Mountains of P1's) at P2. The engine
deals the damage and applies the loss; the observer judges the obligation from
the decision tape and the readback only.

``FakeForge`` replays the pinned bridge's frame and readback shapes (as a real
run of this row showed them) and models only what those frames need: casting,
targeting, paying, passing, resolution of the top object and the loss check.
The wrong-reason controls each name the mutation that turns them red.
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
    midgame_rows as mr,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    scripted_selection as ss,
)
from commander_lab.qualification.current_boundary.materialization import (  # noqa: E402
    load_effective_materialization,
)

ROW = "WS05-MP-ELIM-STACK-3"
BOLT = "Lightning Bolt"
SEATS = ("p1", "p2", "p3")


@pytest.fixture(scope="module")
def records() -> dict[str, dict[str, Any]]:
    return {r["fixture_id"]: r for r in load_effective_materialization(REPO).denominator_records()}


@pytest.fixture
def record(records) -> dict[str, Any]:
    return copy.deepcopy(records[ROW])


def _action(action_id: str, action_type: str, label: str, source=None, refs=()) -> dict:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "source_object_id": source,
        "metadata": {"label": label, "object_refs": list(refs)},
    }


class FakeForge:
    """The pinned bridge's frames for this row, driven by what the route submits."""

    def __init__(
        self,
        *,
        p1_bolts: int = 14,
        p1_lands: int = 14,
        p2_life: int = 40,
        lose_on_victim_cast: bool = False,
        loss_reason: str = "LifeReachedZero",
    ) -> None:
        self.life = {"p1": 40, "p2": p2_life, "p3": 40}
        self.lost = dict.fromkeys(SEATS, False)
        self.loss_reason: dict[str, str | None] = dict.fromkeys(SEATS)
        self.hand = {"p1": [BOLT] * p1_bolts + ["Mountain"], "p2": [BOLT], "p3": ["Mountain"] * 7}
        self.lands = {"p1": [False] * p1_lands, "p2": [False], "p3": []}
        self.battlefield_extra = {seat: ["Grizzly Bears"] for seat in SEATS}
        self.graveyard: dict[str, list[str]] = {seat: [] for seat in SEATS}
        self.stack: list[dict[str, Any]] = []  # top first
        self.priority = "p1"
        self.passes = 0
        self.pending: tuple[str, ...] | None = None
        self.next_id = 300
        self.frame: dict | None = None
        self.requests: list[tuple[str, dict]] = []
        self.lose_on_victim_cast = lose_on_victim_cast
        self.reason = loss_reason

    # -- frames ---------------------------------------------------------------
    def _live(self) -> list[str]:
        return [seat for seat in SEATS if not self.lost[seat]]

    def poll(self, *_args: Any, **_kwargs: Any) -> dict:
        if self.pending and self.pending[0] == "target":
            caster = self.pending[1]
            actions = [
                _action(
                    f"t-{seat}",
                    "target",
                    f"Target [player {seat};]",
                    refs=[{"kind": "player", "player_id": seat}],
                )
                for seat in self._live()
            ] + [
                _action(f"t-bears-{seat}", "target", "Target [Grizzly Bears;]")
                for seat in self._live()
            ]
            self.frame = {
                "decision": {"kind": "TARGET_SELECTION", "actor": caster},
                "actions": actions,
            }
        elif self.pending and self.pending[0] == "pay":
            caster = self.pending[1]
            untapped = [i for i, tapped in enumerate(self.lands[caster]) if not tapped]
            actions = [
                _action(f"tap-{caster}-{i}", "tap_mana_source", "Tap Mountain for mana", "Mountain")
                for i in untapped
            ] + [_action("decline", "tap_mana_source", "Decline to tap (leave cost unpaid)")]
            self.frame = {"decision": {"kind": "MANA_PAYMENT", "actor": caster}, "actions": actions}
        else:
            seat = self.priority
            actions = [
                _action(f"pass-{seat}", "pass_priority", "Pass priority"),
                _action(f"concede-{seat}", "concede", "Concede the game"),
            ]
            untapped = sum(1 for tapped in self.lands[seat] if not tapped)
            if untapped:
                actions += [
                    _action(f"cast-{seat}-{i}", "cast_spell", f"{BOLT} [cast_spell] ({{R}})", BOLT)
                    for i, card in enumerate(self.hand[seat])
                    if card == BOLT
                ]
            self.frame = {"decision": {"kind": "PRIORITY", "actor": seat}, "actions": actions}
        return self.frame

    # -- submissions ----------------------------------------------------------
    def request(self, method: str, params: dict, **_kwargs: Any) -> dict:
        self.requests.append((method, params))
        assert self.frame is not None
        actor = self.frame["decision"]["actor"]
        if method == "pass_priority":
            self.passes += 1
            if self.passes >= len(self._live()):
                self._resolve()
            else:
                after = SEATS[SEATS.index(actor) + 1 :] + SEATS[: SEATS.index(actor) + 1]
                self.priority = next(seat for seat in after if not self.lost[seat])
                if self.lose_on_victim_cast and self.priority == "p1" and self.stack:
                    # The engine shows the victim lost before P1 could verify
                    # the stack and cast a single instrument.
                    self.lost["p2"] = True
                    self.loss_reason["p2"] = self.reason
            return {"success": True}
        chosen = params["proposal"]["legal_action_id"]
        offered = {action["action_id"]: action for action in self.frame["actions"]}
        if chosen not in offered:
            return {"success": False, "errors": [f"{chosen} not offered"]}
        if chosen.startswith("cast-"):
            self.hand[actor].remove(BOLT)
            self.pending = ("target", actor)
        elif chosen.startswith("t-"):
            target = chosen.split("-")[-1]
            self.pending = ("pay", actor, target)
        elif chosen.startswith("tap-"):
            index = int(chosen.split("-")[-1])
            self.lands[actor][index] = True
            target = self.pending[2] if self.pending else "?"
            card_id = self.next_id
            self.next_id += 1
            self.stack.insert(
                0,
                {
                    "id": card_id,
                    "controller": actor,
                    "target": target,
                    "text": f"{BOLT} ({card_id}) - {BOLT} ({card_id}) deals 3 damage to forge-{target}.",
                },
            )
            self.pending = None
            self.priority = actor
            self.passes = 0
        else:
            return {"success": False, "errors": [f"unmodelled {chosen}"]}
        return {"success": True}

    def _resolve(self) -> None:
        self.passes = 0
        if not self.stack:
            raise AssertionError("an all-pass ring on an empty stack would end the step")
        top = self.stack.pop(0)
        self.life[top["target"]] -= 3
        self.graveyard[top["controller"]].append(BOLT)
        for seat in SEATS:
            if not self.lost[seat] and self.life[seat] <= 0:
                # CR 704.5a, then CR 800.4a: the leaver's objects leave with it.
                self.lost[seat] = True
                self.loss_reason[seat] = self.reason
                self.stack = [item for item in self.stack if item["controller"] != seat]
                self.lands[seat] = []
                self.battlefield_extra[seat] = []
                self.hand[seat] = []
        self.priority = "p1"

    # -- readback -------------------------------------------------------------
    def observe(self, _game_id: str) -> dict:
        players = []
        for seat in SEATS:
            details = [
                {"name": "Grizzly Bears", "tapped": False, "counters": {}}
                for _ in self.battlefield_extra[seat]
            ] + [
                {"name": "Mountain", "tapped": tapped, "counters": {}}
                for tapped in self.lands[seat]
            ]
            players.append(
                {
                    "player_id": seat,
                    "life": self.life[seat],
                    "has_lost": self.lost[seat],
                    "loss_reason": self.loss_reason[seat],
                    "zones": {
                        "hand": list(self.hand[seat]) if seat == "p1" else ["<hidden>"],
                        "battlefield": [d["name"] for d in details],
                        "battlefield_details": details,
                        "graveyard": list(self.graveyard[seat]),
                        "command": ["Rograkh, Son of Rohgahh", "Commander Effect"],
                    },
                }
            )
        return {
            "stack": [item["text"] for item in self.stack],
            "players": players,
            "turn_number": 1,
            "phase": "precombat_main",
            "step": "MAIN1",
            "active_player_id": "p1",
            "priority_player_id": self.priority,
        }


def _model(record: dict) -> fsl.RequestedStateModel:
    model = fsl.model_requested_state(record)
    assert model.causal_plan is not None and model.causal_plan.elimination is not None
    return model


def _run(record: dict, monkeypatch, engine: FakeForge | None = None):
    engine = engine or FakeForge()
    monkeypatch.setattr(fcr, "poll_decision", engine.poll)
    monkeypatch.setattr(fcr, "decision_identity_params", lambda _c, _f: {})
    model = _model(record)
    run = fcr.run_causal_route(
        engine,  # type: ignore[arg-type]
        "g",
        record,
        model.causal_plan,  # type: ignore[arg-type]
        seat_count=3,
        observe=engine.observe,
        answer_frame_kinds=fsl._route_answer_frames(model),
        checkpoint_priority=model.temporal_state.get("priority_player"),
    )
    return engine, model, run


def _verdict(model, run) -> fsl.ObligationVerdict:
    return fsl.evaluate_stack_controller_eliminated(model, run)


def _snapshot(run: fcr.CausalRun, at: str) -> dict:
    return next(snap["state"] for snap in run.snapshots if snap["at"] == at)


def _row(state: dict, seat: str) -> dict:
    return next(row for row in state["players"] if row["player_id"] == seat)


# ---------------------------------------------------------------------------
# The route and the observer on the engine's facts
# ---------------------------------------------------------------------------
def test_the_row_is_routed_from_the_shared_declaration(record) -> None:
    model = _model(record)
    plan = model.causal_plan
    assert plan is not None and plan.elimination is not None
    elimination = plan.elimination
    assert (elimination.actor, elimination.victim, elimination.bolt_count) == ("p1", "p2", 14)
    assert [spell.card for spell in plan.spells] == [BOLT]
    assert plan.spells[0].controller == "p2" and plan.spells[0].targets == ("P1",)
    # The stack is cast, never injected; the instruments are placed, the
    # victim's recorded 0 life is substituted openly with its starting life.
    neutral = model.neutral_initial_state
    assert "stack" not in neutral and "decision_script" not in neutral
    assert neutral["hands"]["p2"] == [BOLT]
    assert neutral["hands"]["p1"] == [BOLT] * 14
    assert neutral["life"] == {"p1": 40, "p2": 40, "p3": 40}
    assert model.life_by_player["p2"] == 0
    document = plan.to_document()["elimination"]
    assert document["life_substitution"]["recorded_life"] == 0
    assert document["life_substitution"]["placed_life"] == 40
    assert not model.hard_unsupported and model.credit_eligible
    assert fsl.causal_terminal(model) == "stack_controller_eliminated"
    assert fsl._route_observer(model) == "p1"
    assert fr.classify_row(record).classification == fr.SCENARIO_LANE_EXECUTABLE


def test_the_obligation_is_observed_from_engine_facts(record, monkeypatch) -> None:
    engine, model, run = _run(record, monkeypatch)
    assert run.failure is None, run.failure
    verdict = _verdict(model, run)
    assert verdict.observed and verdict.credit_eligible_observation, verdict.reason
    assert verdict.semantic_events == ["player_leaves:P2", "multiplayer_cleanup:CR800.4"]
    assert verdict.terminal_facts["victim_life_progression"] == [40 - 3 * k for k in range(15)]
    assert len(run.elimination_casts) == 14
    # Every submission is an engine-offered id; nothing is chosen for P2 or P3.
    submitted = [
        p["proposal"]["legal_action_id"] for m, p in engine.requests if m == "submit_action"
    ]
    assert submitted[:3] == ["cast-p2-0", "t-p1", "tap-p2-0"]
    assert all(not item.startswith(("cast-p3", "t-p3")) for item in submitted)
    assert engine.life == {"p1": 40, "p2": -2, "p3": 40}


def test_the_pre_causal_checkpoint_names_the_life_substitution(record) -> None:
    model = _model(record)
    engine = FakeForge()
    state = {"payload": {"state": engine.observe("g")}}
    equivalence = fsl.compare_checkpoint(model, {"p1": state})
    assert equivalence.verdict == fsl.CHECKPOINT_ALLOWED_VARIANCE
    assert "declared causal elimination" in str(equivalence.variance_source)
    life = {item.field: item.verdict for item in equivalence.fields if item.field.endswith("life")}
    assert life["players.p2.life"] == fsl.CHECKPOINT_CAUSAL_SUBSTITUTION
    # The recorded 0 placed as is (no substitution): a mismatch, never a variance.
    unsubstituted = {"payload": {"state": FakeForge(p2_life=0).observe("g")}}
    assert fsl.compare_checkpoint(model, {"p1": unsubstituted}).verdict == fsl.CHECKPOINT_MISMATCH


# ---------------------------------------------------------------------------
# 1. The loss lands before the stack is verified
# ---------------------------------------------------------------------------
def test_a_loss_before_the_instruments_fails_the_route(record, monkeypatch) -> None:
    """Mutation: drop the route's ``lost after N of M`` check -> the route settles green."""
    _, model, run = _run(record, monkeypatch, FakeForge(lose_on_victim_cast=True))
    assert run.failure is not None and "p2 lost after 0 of 14 declared instruments" in run.failure
    assert not _verdict(model, run).observed


def test_a_loss_shown_before_the_verified_stack_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop ``has_lost(...) is False`` from ``stack_verified_before_loss``."""
    _, model, run = _run(record, monkeypatch)
    _row(_snapshot(run, "elimination_start"), "p2")["has_lost"] = True
    verdict = _verdict(model, run)
    assert not verdict.observed and "stack_verified_before_loss" in verdict.reason


def test_an_instrument_before_the_stack_verification_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop ``positions == sorted(positions)`` from ``stack_verified_before_loss``."""
    _, model, run = _run(record, monkeypatch)
    start = next(snap for snap in run.snapshots if snap["at"] == "elimination_start")
    run.snapshots.remove(start)
    first_cast = next(
        i for i, snap in enumerate(run.snapshots) if snap["at"] == "cast_complete:obj:elim-bolt-0"
    )
    run.snapshots.insert(first_cast + 1, start)
    verdict = _verdict(model, run)
    assert not verdict.observed and "stack_verified_before_loss" in verdict.reason


def test_an_instrument_cast_that_moved_the_verified_stack_fails_the_route(
    record, monkeypatch
) -> None:
    """Mutation: drop the route's ``stack[1:] != stack_after_cast`` instrument check."""
    engine = FakeForge()
    original = engine.observe

    def observe(game_id: str) -> dict:
        state = original(game_id)
        if len(state["stack"]) == 2:
            state["stack"][1] = (
                "Lightning Bolt (999) - Lightning Bolt (999) deals 3 damage to forge-p1."
            )
        return state

    engine.observe = observe  # type: ignore[method-assign]
    _, _, run = _run(record, monkeypatch, engine)
    assert run.failure is not None and "did not keep the verified stack" in run.failure


# ---------------------------------------------------------------------------
# 2. An injected loss flag or an undeclared loss
# ---------------------------------------------------------------------------
def test_a_loss_for_an_undeclared_reason_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop the ``loss_reason`` clause of ``victim_lost_for_declared_reason``."""
    _, model, run = _run(record, monkeypatch, FakeForge(loss_reason="SpellEffect"))
    assert run.failure is None
    verdict = _verdict(model, run)
    assert not verdict.observed and "victim_lost_for_declared_reason" in verdict.reason


def test_an_injected_loss_flag_above_the_recorded_life_is_never_observed(
    record, monkeypatch
) -> None:
    """Mutation: drop the ``life <= recorded`` clause of ``victim_lost_for_declared_reason``."""
    _, model, run = _run(record, monkeypatch)
    after = _snapshot(run, "after_loss")
    _row(after, "p2")["life"] = 5  # the flag says lost; the engine's life says otherwise
    verdict = _verdict(model, run)
    assert not verdict.observed
    assert "victim_lost_for_declared_reason" in verdict.reason


def test_an_undeclared_loss_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop the ``no_undeclared_loss`` check."""
    _, model, run = _run(record, monkeypatch)
    _row(_snapshot(run, "elimination_resolved:3"), "p3")["has_lost"] = True
    verdict = _verdict(model, run)
    assert not verdict.observed and "no_undeclared_loss" in verdict.reason


def test_a_victim_that_never_lost_is_not_routed_as_eliminated(record) -> None:
    """Mutation: drop the elimination-trigger clause of ``_elimination_plan``."""
    record["elimination_trigger"] = {"player": "P3", "reason": "life_total_0"}
    assert fsl.lane_causal_plan(record) is None
    record["elimination_trigger"] = {"player": "P2", "reason": "poison_10"}
    assert fsl.lane_causal_plan(record) is None


# ---------------------------------------------------------------------------
# 3. No surviving players
# ---------------------------------------------------------------------------
def test_no_surviving_player_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop the ``survivors_remain`` check."""
    _, model, run = _run(record, monkeypatch)
    after = _snapshot(run, "after_loss")
    for seat in ("p1", "p3"):
        _row(after, seat)["has_lost"] = True
    verdict = _verdict(model, run)
    assert not verdict.observed and "survivors_remain" in verdict.reason


def test_a_survivor_hit_by_the_victims_spell_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop the ``survivors_at_requested_life`` check."""
    _, model, run = _run(record, monkeypatch)
    _row(_snapshot(run, "after_loss"), "p1")["life"] = 37
    verdict = _verdict(model, run)
    assert not verdict.observed and "survivors_at_requested_life" in verdict.reason


# ---------------------------------------------------------------------------
# 4. Thirteen instruments for the declared fourteen
# ---------------------------------------------------------------------------
def test_thirteen_declared_instruments_for_fourteen_bolts_is_not_planned(
    record, monkeypatch
) -> None:
    """Mutation: drop ``len(bolts) != count`` in ``_elimination_plan``."""
    probe = mr.probe_module()
    original = probe.elimination_request

    def thirteen(spec: dict) -> dict:
        request = original(spec)
        request["instruments"] = request["instruments"][:-2]
        return request

    monkeypatch.setattr(probe, "elimination_request", thirteen)
    assert fsl.lane_causal_plan(record) is None
    model = fsl.model_requested_state(record)
    assert "stack_state" in {item.dimension for item in model.hard_unsupported}


def test_thirteen_instruments_in_the_engine_fail_the_route(record, monkeypatch) -> None:
    """Mutation: drop the route's instrument-count check at ``elimination_start``."""
    _, _, run = _run(record, monkeypatch, FakeForge(p1_bolts=13))
    assert run.failure is not None and "the engine shows p1's instruments" in run.failure


def test_a_loss_after_thirteen_instruments_fails_the_route(record, monkeypatch) -> None:
    """The engine eliminated the victim one instrument early: not the declared cause."""
    _, _, run = _run(record, monkeypatch, FakeForge(p2_life=39))
    assert run.failure is not None and "p2 lost after 13 of 14" in run.failure


def test_a_tape_with_thirteen_instrument_casts_is_never_observed(record, monkeypatch) -> None:
    """Mutation: drop the ``declared_instrument_count`` check."""
    _, model, run = _run(record, monkeypatch)
    run.elimination_casts.pop()
    verdict = _verdict(model, run)
    assert not verdict.observed and "declared_instrument_count" in verdict.reason


# ---------------------------------------------------------------------------
# 5. A tampered, engine-legal but undeclared option id
# ---------------------------------------------------------------------------
def test_a_tampered_target_id_is_rejected(record, monkeypatch) -> None:
    """Mutation: drop ``_frame_choice_offered(target)`` from the instrument tape check."""
    _, model, run = _run(record, monkeypatch)
    target = next(frame for frame in run.frames if frame.reason == "elimination target")
    target.chosen_option_id = "t-p3"  # offered by the engine, legal, not declared
    assert "t-p3" in target.offered_option_ids
    verdict = _verdict(model, run)
    assert not verdict.observed and "instrument_tape_bound" in verdict.reason


def test_a_tampered_cast_id_is_rejected(record, monkeypatch) -> None:
    """Mutation: drop ``_frame_choice_offered`` from the instrument cast check."""
    _, model, run = _run(record, monkeypatch)
    cast = run.frames[run.elimination_casts[5]["frame_index"]]
    cast.chosen_option_id = "concede-p1"
    verdict = _verdict(model, run)
    assert not verdict.observed and "instrument_tape_bound" in verdict.reason


def test_an_undeclared_payment_source_is_rejected(record, monkeypatch) -> None:
    """Mutation: drop ``payment_source in declared_lands`` from the instrument tape check."""
    _, model, run = _run(record, monkeypatch)
    payment = next(f for f in run.frames if f.reason.startswith("declared instrument "))
    payment.payment_source = "obj:fuel-mountain-p2"
    verdict = _verdict(model, run)
    assert not verdict.observed and "instrument_tape_bound" in verdict.reason


def test_an_undeclared_instance_of_the_instrument_is_never_cast() -> None:
    """Mutation: drop the count check in ``select_instrument_cast``."""
    frame = {
        "decision": {"kind": "PRIORITY", "actor": "p1"},
        "actions": [
            _action(f"c{i}", "cast_spell", f"{BOLT} [cast_spell] ({{R}})", BOLT) for i in range(15)
        ],
    }
    _, options = ss.forge_options(frame)
    with pytest.raises(ss.SelectionFailure, match="instrument_count_mismatch"):
        fcr.select_instrument_cast(options, BOLT, 14)
    assert fcr.select_instrument_cast(options[:14], BOLT, 14).option_id == "c0"


def test_a_distinguishable_instrument_offer_is_never_cast() -> None:
    """Mutation: drop the identical-offer check in ``select_instrument_cast``."""
    actions = [
        _action(f"c{i}", "cast_spell", f"{BOLT} [cast_spell] ({{R}})", BOLT) for i in range(2)
    ]
    actions[1]["metadata"]["label"] = f"{BOLT} [cast_spell] (flashback {{R}})"
    _, options = ss.forge_options(
        {"decision": {"kind": "PRIORITY", "actor": "p1"}, "actions": actions}
    )
    with pytest.raises(ss.SelectionFailure, match="instrument_ambiguous"):
        fcr.select_instrument_cast(options, BOLT, 2)


# ---------------------------------------------------------------------------
# 6. The stack refusal still holds where it should
# ---------------------------------------------------------------------------
def test_a_modal_victim_spell_stays_a_refused_stack(record) -> None:
    """Mutation: drop the modes clause of ``causal_plan``."""
    record["stack_state"][0]["modes"] = ["mode-1"]
    model = fsl.model_requested_state(record)
    assert model.causal_plan is None
    refused = {item.dimension: item for item in model.hard_unsupported}
    assert refused["stack_state"].runtime_probe == "stack"
    assert fr.classify_row(record).first_missing["dimension"] == "stack_state"


def test_a_scripted_decision_keeps_the_elimination_unrouted(record) -> None:
    """Mutation: let a terminal without selectors accept a non-empty script."""
    record["decision_script"] = [
        {
            "actor": "P1",
            "causal_step_id": "extra",
            "decision_family": "priority",
            "forbidden_fallbacks": sorted(ss.FORBIDDEN_FALLBACKS),
            "selection": {
                "matches_only_provider_offered_legal_options": True,
                "on_multiple_match": "FAIL_CLOSED",
                "on_zero_match": "FAIL_CLOSED",
                "selector_kind": "semantic_action",
                "semantic_value": {"action": "cast", "object": "obj:leave-bolt"},
            },
        }
    ]
    assert fsl.lane_causal_plan(record) is None


def test_a_caused_permanent_elimination_stays_refused(records) -> None:
    """Mutation: drop the ``caused_permanents`` clause of ``_elimination_plan``."""
    control = copy.deepcopy(records["WS05-MP-ELIM-CONTROL-3"])
    entry = mr.causal_stack_elimination_entry("WS05-MP-ELIM-CONTROL-3")
    assert entry is not None and entry.get("caused_permanents")
    assert fcr._elimination_plan(control, entry) is None
    # Without its caused permanents the same entry would be planned: the
    # refusal is the caused permanent's, not an incidental one.
    assert fcr._elimination_plan(control, {**entry, "caused_permanents": []}) is not None
    assert fcr.causal_plan(control, entry) is None
    assert fsl.lane_causal_plan(control) is None
    # Its own blocker (the owner and attachment readback) is unchanged.
    assert fr.classify_row(control).classification == fr.PROVIDER_ADAPTER_GAP


def test_the_route_still_refuses_an_injected_stack(record) -> None:
    model = _model(record)
    assert model.causal_plan is not None
    with pytest.raises(fcr.CausalRouteError, match="never injects a stack"):
        fcr.pre_causal_state({"stack": [{"card": BOLT}]}, model.causal_plan)


# ---------------------------------------------------------------------------
# 7. Missing observer evidence stays UNKNOWN
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "drop",
    ["after_loss", "elimination_start", "elimination_resolved:7", "requested_checkpoint"],
)
def test_a_missing_snapshot_leaves_the_obligation_unobserved(drop, record, monkeypatch) -> None:
    _, model, run = _run(record, monkeypatch)
    run.snapshots = [snap for snap in run.snapshots if snap["at"] != drop]
    verdict = _verdict(model, run)
    assert not verdict.observed and not verdict.credit_eligible_observation
    assert verdict.semantic_events == []


def test_a_missing_life_readback_leaves_the_obligation_unobserved(record, monkeypatch) -> None:
    """Mutation: drop the ``isinstance(life, int)`` clause of ``victim_life_reached_by_engine``."""
    _, model, run = _run(record, monkeypatch)
    del _row(_snapshot(run, "elimination_resolved:7"), "p2")["life"]
    verdict = _verdict(model, run)
    assert not verdict.observed and "victim_life_reached_by_engine" in verdict.reason


def test_a_missing_permanent_readback_leaves_the_obligation_unobserved(record, monkeypatch) -> None:
    """Mutation: let ``victim_permanents_left`` accept a missing battlefield readback."""
    _, model, run = _run(record, monkeypatch)
    del _row(_snapshot(run, "after_loss"), "p2")["zones"]["battlefield"]
    verdict = _verdict(model, run)
    assert not verdict.observed and "victim_permanents_left" in verdict.reason


def test_an_empty_run_is_unobserved_not_passed(record) -> None:
    model = _model(record)
    verdict = _verdict(model, fcr.CausalRun())
    assert not verdict.observed and not verdict.credit_eligible_observation
    failed = _verdict(model, fcr.CausalRun(failure="boom"))
    assert not failed.observed and "boom" in failed.reason
