"""#634 step B2: the causal probe helpers answer for a player only as declared.

Red controls, one per site:

* an undeclared multi-option priority frame stops the row (resolve_stack,
  resolve_until_life_drops, cast_frame_source) and nothing is submitted;
* a declared pass-through scope authorizes the pass and names its step;
* a positional fuel-mana pick is refused: the declared fuel order decides, and an
  ambiguous ability or pool spend stops the row;
* an attack hold or an empty block is given only under the record's own empty
  declaration, as the engine's own empty selection; no ``"empty-block"`` id is
  ever submitted;
* trace completeness: every Lab answer is in the authority's trace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr

PROBE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_midgame_capability_probe.py"
FAIL_CLOSED = {
    "matches_only_provider_offered_legal_options": True,
    "on_zero_match": "FAIL_CLOSED",
    "on_multiple_match": "FAIL_CLOSED",
}
DECLARED = {
    "decision_script": [
        {"decision_family": "mulligan", "actor": "P1"},
        {
            "decision_family": "priority_pass_through",
            "actor": "ALL",
            "selection": {
                **FAIL_CLOSED,
                "selector_kind": "semantic_action",
                "semantic_value": "pass_priority",
            },
            "scope": {
                "from": {"turn": 1, "phase": "beginning"},
                "until": {"event": "OBLIGATION_COMPLETE"},
            },
        },
    ]
}
EMPTY_COMBAT = {
    "decision_script": [
        {
            "decision_family": "declare_attackers",
            "actor": "P1",
            "turn": 1,
            "selection": {
                **FAIL_CLOSED,
                "selector_kind": "attacker_assignment",
                "semantic_value": {},
            },
        },
        {
            "decision_family": "declare_blockers",
            "actor": "P2",
            "turn": 1,
            "selection": {
                **FAIL_CLOSED,
                "selector_kind": "blocker_assignment",
                "semantic_value": {},
            },
        },
    ]
}


class _Client:
    """A lane client whose engine offers the given decisions and legal frames in turn."""

    def __init__(
        self,
        decisions: list[dict[str, Any] | None],
        legal: list[dict[str, Any]] | None = None,
    ) -> None:
        self.decisions = list(decisions)
        self.legal = list(legal or [])
        self.submitted: list[list[str]] = []
        self.proposals: list[dict[str, Any]] = []

    def pending_decision(self, attempts: int = 0) -> dict[str, Any] | None:
        return self.decisions[0] if self.decisions else None

    def submit_options(self, decision: dict[str, Any], options: list[str]) -> None:
        self.submitted.append(list(options))
        self.decisions.pop(0)

    def request(self, message: str, payload: Any) -> dict[str, Any]:
        if message == "get_midgame_projection":
            view = {"turn_number": 1, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"}
            return {"success": True, "payload": {"view": view}}
        if message == "get_legal_actions":
            return {"success": True, "payload": self.legal[0]}
        if message == "submit_action":
            self.proposals.append(payload["proposal"])
            self.legal.pop(0)
            self.decisions.pop(0)
            return {"success": True, "payload": {}}
        raise AssertionError(message)


def _priority(stack: list[str], *, cast: bool, seat: int = 0, ident: str = "d") -> dict[str, Any]:
    options = [{"option_type": "pass_priority", "option_id": "pass"}]
    if cast:
        options.append({"option_type": "activate_ability", "option_id": "cast-bolt"})
    return {
        "decision_class": "priority",
        "decision_id": ident,
        "seat": seat,
        "legal_options": options,
        "pilot_state": {"stack": stack},
    }


def test_undeclared_multi_option_priority_frame_stops_the_row() -> None:
    probe = mr.probe_module()
    client = _Client([_priority(["bolt"], cast=True)])
    with pytest.raises(probe.ml.MidgameLaneError, match="undeclared priority pass"):
        probe.resolve_stack(client, "t", probe.PassAuthority({"decision_script": []}))
    assert client.submitted == []


def test_declared_scope_authorizes_the_pass_and_names_its_step() -> None:
    probe = mr.probe_module()
    client = _Client([_priority(["bolt"], cast=True, ident="d1"), _priority([], cast=True)])
    authority = probe.PassAuthority(DECLARED)
    probe.resolve_stack(client, "t", authority)
    assert client.submitted == [["pass"]]
    assert authority.trace == [
        {
            "kind": "priority_pass",
            "actor": "P1",
            "decision_id": "d1",
            "scope": "decision_script[1]",
            "tag": "t",
        }
    ]


def test_seeking_a_cast_never_passes_another_players_undeclared_priority() -> None:
    probe = mr.probe_module()
    legal = {"actor_id": "p2", "actions": []}
    client = _Client([_priority([], cast=True, seat=1)], legal=[legal])
    with pytest.raises(probe.ml.MidgameLaneError, match="undeclared priority pass for P2"):
        probe.cast_frame_source(
            client, "t", "bolt-id", probe.PassAuthority({"decision_script": []})
        )
    assert client.submitted == []


def test_resolving_until_life_drops_never_passes_undeclared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = mr.probe_module()
    monkeypatch.setattr(
        probe, "complete_causal", lambda client, mode: {"verdict": {"life_totals": {"P2": 20}}}
    )
    client = _Client([_priority(["bolt"], cast=True)])
    with pytest.raises(probe.ml.MidgameLaneError, match="undeclared priority pass"):
        probe.resolve_until_life_drops(
            client, "t", "P2", None, probe.PassAuthority({"decision_script": []})
        )
    assert client.submitted == []


def _mana_frame() -> dict[str, Any]:
    return {"decision_class": "mana_payment", "decision_id": "m", "seat": 0, "legal_options": []}


def _ability(action_id: str, source: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action_type": "activate_ability",
        "metadata": {
            "option_type": "mana_ability",
            "xmage_option_metadata": {"source_object_id": source},
        },
    }


def _spend(action_id: str) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action_type": "structural_decision",
        "metadata": {
            "option_type": "mana_pool",
            "xmage_option_metadata": {"advances_payment": True},
        },
    }


def test_fuel_is_tapped_in_declared_order_and_each_mana_spent_as_it_comes() -> None:
    probe = mr.probe_module()
    tap_frame = {
        "actor_id": "p1",
        "actions": [_ability("tap-a", "fuel-a"), _ability("tap-b", "fuel-b")],
    }
    spend_frame = {"actor_id": "p1", "actions": [_spend("blue"), _ability("tap-a", "fuel-a")]}
    authority = probe.PassAuthority({"decision_script": []})
    client = _Client(
        [_mana_frame(), _mana_frame(), {"decision_class": "priority"}],
        legal=[tap_frame, spend_frame],
    )
    probe.answer_fuel_mana(client, "t", ["fuel-b", "fuel-a"], authority)
    # Declared order (b before a), not the engine's list order; the produced mana
    # is spent before any further fuel is tapped.
    assert [proposal["legal_action_id"] for proposal in client.proposals] == ["tap-b", "blue"]
    assert [(entry["kind"], entry["scope"]) for entry in authority.trace] == [
        ("mana_tap", "declared_fuel[0]"),
        ("pool_spend", "single_advancing_spend"),
    ]


def test_ambiguous_fuel_ability_or_pool_spend_is_refused() -> None:
    probe = mr.probe_module()
    authority = probe.PassAuthority({"decision_script": []})
    two_abilities = {
        "actor_id": "p1",
        "actions": [_ability("tap-a1", "fuel-a"), _ability("tap-a2", "fuel-a")],
    }
    with pytest.raises(probe.ml.MidgameLaneError, match="2 mana abilities"):
        probe.answer_fuel_mana(
            _Client([_mana_frame()], legal=[two_abilities]), "t", ["fuel-a"], authority
        )
    two_spends = {"actor_id": "p1", "actions": [_spend("red"), _spend("black")]}
    client = _Client([_mana_frame()], legal=[two_spends])
    with pytest.raises(probe.ml.MidgameLaneError, match="2 advancing pool spends"):
        probe.answer_fuel_mana(client, "t", ["fuel-a"], authority)
    assert client.proposals == [] and authority.trace == []


def _combat(decision_class: str, seat: int, option_type: str) -> dict[str, Any]:
    return {
        "decision_class": decision_class,
        "decision_id": f"{decision_class}-{seat}",
        "seat": seat,
        "minimum_selections": 0,
        "legal_options": [{"option_type": option_type, "option_id": f"{option_type}-id"}],
    }


def test_combat_is_drained_only_under_declared_empty_sets() -> None:
    probe = mr.probe_module()
    frames = [
        _combat("declare_attacker", 0, "hold_attacker"),
        _combat("declare_blocker", 1, "declare_blocker"),
        _priority([], cast=False),
    ]
    authority = probe.PassAuthority(EMPTY_COMBAT)
    client = _Client(frames)
    probe.drain_combat_to_priority(client, "t", authority)
    # The hold is the engine's own option; the empty block is the engine's empty selection.
    assert client.submitted == [["hold_attacker-id"], []]
    assert [entry["kind"] for entry in authority.trace] == ["hold_attacker", "empty_block"]
    assert [entry["scope"] for entry in authority.trace] == [
        "decision_script[0]",
        "decision_script[1]",
    ]
    for frame in (
        _combat("declare_attacker", 0, "hold_attacker"),
        _combat("declare_blocker", 1, "declare_blocker"),
    ):
        undeclared = _Client([frame])
        with pytest.raises(probe.ml.MidgameLaneError, match="undeclared"):
            probe.drain_combat_to_priority(
                undeclared, "t", probe.PassAuthority({"decision_script": []})
            )
        assert undeclared.submitted == [] and undeclared.proposals == []


def test_empty_block_needs_the_engines_zero_minimum() -> None:
    probe = mr.probe_module()
    frame = _combat("declare_blocker", 1, "declare_blocker")
    frame["minimum_selections"] = 1
    client = _Client([frame])
    with pytest.raises(probe.ml.MidgameLaneError, match="does not offer an empty block"):
        probe.drain_combat_to_priority(client, "t", probe.PassAuthority(EMPTY_COMBAT))
    assert client.submitted == []


def test_no_synthetic_empty_block_id_remains_in_the_probe() -> None:
    assert '"empty-block"' not in PROBE_PATH.read_text(encoding="utf-8")


def test_trace_names_every_lab_answer() -> None:
    probe = mr.probe_module()
    frames = [
        _combat("declare_attacker", 0, "hold_attacker"),
        _priority(["bolt"], cast=True, ident="p1"),
        _priority(["bolt"], cast=False, ident="p2"),
        _priority([], cast=True),
    ]
    authority = probe.PassAuthority(
        {"decision_script": EMPTY_COMBAT["decision_script"] + DECLARED["decision_script"]}
    )
    client = _Client(frames)
    probe.drain_combat_to_priority(client, "t", authority)
    probe.resolve_stack(client, "t", authority)
    assert len(authority.trace) == len(client.submitted) == 3
    assert [entry["decision_id"] for entry in authority.trace] == [
        "declare_attacker-0",
        "p1",
        "p2",
    ]
