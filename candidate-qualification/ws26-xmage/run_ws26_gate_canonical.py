#!/usr/bin/env python3
"""WS-26 qualification entrypoint with deterministic replay comparison.

This wrapper changes only qualification presentation/setup details:
- legal-option sets used for replay comparison are canonically ordered;
- each clean-process replay capture is persisted as diagnostic evidence; and
- PILOT_CHOICE uses City of Brass's native AnyColorManaAbility/ChoiceColor path,
  selecting City of Brass from XMage's priority legal actions and White from
  the subsequently engine-offered ChoiceColor options.

XMage remains the sole rules/legal-action authority. Selected option order and
explicit decision `ordering` values are never sorted or otherwise rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path

import run_ws26_gate as gate


_original_offer_map = gate.replay_semantic_offer_map
_original_capture_replay_run = gate.capture_replay_run
_original_run_single_decision_family = gate.run_single_decision_family
_capture_index = 0


def canonical_offer_map(decision):
    semantic_ids, raw_by_semantic = _original_offer_map(decision)
    return sorted(semantic_ids), raw_by_semantic


def diagnostic_capture_replay_run(expected_tape=None):
    global _capture_index
    result = _original_capture_replay_run(expected_tape)
    _capture_index += 1
    out = Path("qualification/evidence/ws26-xmage")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"REPLAY_CAPTURE_{_capture_index}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def city_of_brass_choice_scenario():
    def configure(players):
        players[0]["zones"]["battlefield"].append(
            {
                "semantic_id": "p1-city-of-brass",
                "card_name": "City of Brass",
                "tapped": False,
                "controller_seat": 1,
                "face": "main",
            }
        )

    return gate.scenario_payload(
        "WS26-PILOT-CHOICE",
        [["City of Brass"], [], [], []],
        configure,
    )


def qualification_decision_family(
    *,
    fixture_id,
    scenario_builder,
    priority_label,
    expected_class,
    expected_label=None,
    boolean_value=None,
):
    if fixture_id == "PILOT_CHOICE":
        return _original_run_single_decision_family(
            fixture_id=fixture_id,
            scenario_builder=scenario_builder,
            priority_label="City of Brass",
            expected_class="choice",
            expected_label="White",
            boolean_value=None,
        )
    return _original_run_single_decision_family(
        fixture_id=fixture_id,
        scenario_builder=scenario_builder,
        priority_label=priority_label,
        expected_class=expected_class,
        expected_label=expected_label,
        boolean_value=boolean_value,
    )


gate.replay_semantic_offer_map = canonical_offer_map
gate.capture_replay_run = diagnostic_capture_replay_run
gate.choice_scenario = city_of_brass_choice_scenario
gate.run_single_decision_family = qualification_decision_family


if __name__ == "__main__":
    raise SystemExit(gate.main())
