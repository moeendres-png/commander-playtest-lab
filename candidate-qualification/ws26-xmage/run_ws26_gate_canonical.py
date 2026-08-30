#!/usr/bin/env python3
"""WS-26 qualification entrypoint with deterministic replay comparison.

This wrapper changes only qualification presentation/setup details:
- legal-option sets used for replay comparison are canonically ordered;
- each clean-process replay capture is persisted as diagnostic evidence; and
- PILOT_CHOICE uses City of Brass's native AnyColorManaAbility/ChoiceColor path,
  avoiding the non-reachable Unclaimed Territory play-land path observed in run #34.

XMage remains the sole rules/legal-action authority. Selected option order and
explicit decision `ordering` values are never sorted or otherwise rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path

import run_ws26_gate as gate


_original_offer_map = gate.replay_semantic_offer_map
_original_capture_replay_run = gate.capture_replay_run
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


gate.replay_semantic_offer_map = canonical_offer_map
gate.capture_replay_run = diagnostic_capture_replay_run
gate.choice_scenario = city_of_brass_choice_scenario


if __name__ == "__main__":
    raise SystemExit(gate.main())
