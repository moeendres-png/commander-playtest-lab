"""Every record any arrival-using lane executes declares the choices the lane transports.

Errata 1.0.28-1.0.30 each enumerated some lane registries by hand and missed
others (the probe's causal rows, then the actual-card campaign and the replay
twin's payments). Each miss surfaced only at PB-03 runtime. This test derives
the registries from the lanes themselves and checks every record statically:

* one pregame keep per seat (CR 103.5) and an arrival ``priority_pass_through``
  ending at the record's checkpoint (CR 117.3d);
* the obligation ``priority_pass_through`` with the symbolic
  ``OBLIGATION_COMPLETE`` bound;
* a ``mana_payment`` step for every cost whose payment sources the record
  declares (CR 601.2g-h), except where the lane provably never pays or pays
  from the record's own cost declaration (named below, with the reason).

A new registry entry without these declarations fails here, before any engine
runs.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import actual_card_campaign as acc
from commander_lab.qualification.current_boundary import knowledge_projection as kp
from commander_lab.qualification.current_boundary import midgame_replay_twin as tw
from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OBLIGATION_END = {"event": "OBLIGATION_COMPLETE"}

# Rows whose obligation completes inside casting, before any cost is paid
# (contract 1.0.30 MANA_NOT_REACHED): the engine never asks them for mana.
MANA_NOT_REACHED = frozenset(
    {
        "NEGATIVE_FIRST_OPTION",
        "NEGATIVE_GUI_DEFAULT",
        "NEGATIVE_RANDOM_OPTION",
        "NEGATIVE_SILENT_SKIP",
        "PILOT_MULTI_AMOUNT",
        "PILOT_TARGET_AMOUNT",
    }
)


def _registries() -> dict[str, frozenset[str]]:
    probe = mr.probe_module()
    return {
        "midgame_rows.ROWS": frozenset(mr.ROWS),
        "knowledge_projection.ROWS": frozenset(kp.ROWS),
        "midgame_replay_twin.ROWS": frozenset(tw.ROWS),
        "probe.PROBE_ROWS": frozenset(getattr(probe, "PROBE_ROWS", {}) or {}),
        "probe.CAUSAL_ROWS": frozenset(getattr(probe, "CAUSAL_ROWS", {}) or {}),
        "actual_card_campaign": frozenset(
            row.fixture_id for row in acc.derive_corpus(REPO_ROOT).rows
        ),
    }


def _knowledge_only() -> frozenset[str]:
    """Records only the knowledge lane pays for: its transport takes the payment
    from the record's own ``action_cost_state`` sources (record-bound)."""
    registries = _registries()
    others = frozenset().union(
        *(rows for name, rows in registries.items() if name != "knowledge_projection.ROWS")
    )
    return registries["knowledge_projection.ROWS"] - others


def declaration_problems(record: dict[str, Any], *, mana_exempt: bool) -> list[str]:
    script = list(record.get("decision_script") or ())
    seats = [str(player["player_id"]) for player in record["players"]]
    problems = []
    keeps = {
        str(step.get("actor"))
        for step in script
        if step.get("decision_family") == "mulligan"
        and (step.get("selection") or {}).get("semantic_value") == "keep_opening_hand"
    }
    if missing := sorted(set(seats) - keeps):
        problems.append(f"no pregame keep for {missing}")
    passes = [step for step in script if step.get("decision_family") == "priority_pass_through"]
    temporal = record.get("temporal_state") or {}
    checkpoint = {
        "turn": temporal.get("turn_number"),
        "phase": str(temporal.get("phase") or "").lower(),
        "step": str(temporal.get("step") or "").lower(),
    }
    if not any((step.get("scope") or {}).get("until") == checkpoint for step in passes):
        problems.append("no arrival pass-through ending at the checkpoint")
    if not any((step.get("scope") or {}).get("until") == OBLIGATION_END for step in passes):
        problems.append("no obligation pass-through")
    if not mana_exempt:
        declared = [
            list(((step.get("selection") or {}).get("semantic_value") or {}).get("sources") or ())
            for step in script
            if step.get("decision_family") == "mana_payment"
        ]
        for cost in record.get("action_cost_state") or ():
            sources = list(cost.get("explicit_payment_sources") or ())
            if sources and sources not in declared:
                problems.append(f"undeclared payment for {cost.get('source_semantic_id')}")
    return problems


def test_the_registries_are_the_lanes_own_and_non_empty() -> None:
    registries = _registries()
    for name, rows in registries.items():
        assert rows, name
    assert len(frozenset().union(*registries.values())) >= 127


def test_every_lane_record_declares_its_history_obligation_and_payments() -> None:
    materialization = load_effective_materialization(REPO_ROOT)
    exempt = MANA_NOT_REACHED | _knowledge_only()
    failures = {}
    for fixture_id in sorted(frozenset().union(*_registries().values())):
        problems = declaration_problems(
            dict(materialization.record(fixture_id)), mana_exempt=fixture_id in exempt
        )
        if problems:
            failures[fixture_id] = problems
    assert not failures, failures


def test_the_mana_exemptions_are_exactly_the_named_rows() -> None:
    """An exemption is never a blanket: the knowledge-only rows are the HIDDEN
    knowledge records, and the not-reached rows are the six named ones."""
    assert all(fixture_id.startswith("HIDDEN_") for fixture_id in _knowledge_only())
    assert frozenset(mr.ROWS) >= MANA_NOT_REACHED
    for fixture_id in MANA_NOT_REACHED:
        assert mr.ROWS[fixture_id].mana_sources == (), fixture_id


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("drop_keep", "no pregame keep"),
        ("drop_arrival", "no arrival pass-through"),
        ("drop_obligation", "no obligation pass-through"),
        ("drop_payment", "undeclared payment"),
    ],
)
def test_red_control_each_missing_declaration_is_named(mutation: str, expected: str) -> None:
    record = copy.deepcopy(dict(load_effective_materialization(REPO_ROOT).record("CARD_01")))
    assert declaration_problems(record, mana_exempt=False) == []
    script = record["decision_script"]
    if mutation == "drop_keep":
        script.remove(next(s for s in script if s.get("decision_family") == "mulligan"))
    elif mutation == "drop_arrival":
        script.remove(
            next(
                s
                for s in script
                if s.get("decision_family") == "priority_pass_through"
                and (s.get("scope") or {}).get("until") != OBLIGATION_END
            )
        )
    elif mutation == "drop_obligation":
        script.remove(
            next(s for s in script if (s.get("scope") or {}).get("until") == OBLIGATION_END)
        )
    else:
        script.remove(next(s for s in script if s.get("decision_family") == "mana_payment"))
    assert any(expected in problem for problem in declaration_problems(record, mana_exempt=False))
