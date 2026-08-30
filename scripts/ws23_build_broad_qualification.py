#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PLAYER_COUNT_IDS = tuple(f"PLAYER_COUNT_{count}P" for count in (2, 3, 4, 5))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--actual-card-domain", type=Path, required=True)
    ap.add_argument("--player-count-proof", type=Path, required=True)
    ap.add_argument("--bounded-matrix", type=Path, required=True)
    ap.add_argument("--runtime-proof", type=Path, required=True)
    ap.add_argument("--common-output", type=Path, required=True)
    ap.add_argument("--cards-output", type=Path, required=True)
    ap.add_argument("--summary-output", type=Path, required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    actual_domain = load(args.actual_card_domain)
    player_counts = load(args.player_count_proof)
    bounded = load(args.bounded_matrix)
    runtime = load(args.runtime_proof)

    fixtures = manifest["fixtures"]
    if len(fixtures) != 135:
        raise AssertionError(f"common denominator drift: {len(fixtures)}")
    if bounded.get("denominator") != 14 or bounded.get("pass_count") != 14:
        raise AssertionError("broad qualification requires Gate-D 14/14 CONTINUE")
    if player_counts.get("denominator") != 4 or player_counts.get("pass_count") != 4:
        raise AssertionError("broad qualification requires 2P-5P lifecycle 4/4")

    bounded_pass = {
        row["fixture_id"] for row in bounded["rows"] if row.get("status") == "PASS"
    }
    count_pass = {
        row["fixture_id"]
        for row in player_counts["rows"]
        if row.get("status") == "PASS"
    }
    if count_pass != set(PLAYER_COUNT_IDS):
        raise AssertionError(f"player-count proof drift: {sorted(count_pass)}")

    common_rows = []
    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        if fixture_id in bounded_pass or fixture_id in count_pass:
            common_rows.append(
                {
                    "fixture_id": fixture_id,
                    "category": fixture["category"],
                    "player_count": fixture.get("player_count"),
                    "verdict": "PASS",
                    "behavioral_evidence_class": "RUNTIME_VERIFIED",
                    "classification": "RUNTIME_PASS",
                    "reason": (
                        "WS-23 bounded Gate-D runtime proof"
                        if fixture_id in bounded_pass
                        else "WS-23 full Forge lifecycle runtime proof"
                    ),
                }
            )
        else:
            common_rows.append(
                {
                    "fixture_id": fixture_id,
                    "category": fixture["category"],
                    "player_count": fixture.get("player_count"),
                    "verdict": "NOT_RUN",
                    "behavioral_evidence_class": "NOT_RUN",
                    "classification": "FAIL_CLOSED_UNSUPPORTED",
                    "reason": (
                        "WS23_FAIL_CLOSED_UNSUPPORTED: no behavioral runtime implementation "
                        "for this canonical common fixture; reachability/parsing receives no credit"
                    ),
                }
            )

    cards = list(actual_domain["regression_corpus_29"])
    if len(cards) != 29:
        raise AssertionError(f"actual-card denominator drift: {len(cards)}")
    manifest_cards = {
        fixture["fixture_id"]: fixture
        for fixture in fixtures
        if fixture["fixture_id"].startswith("CARD_")
    }
    expected_card_ids = [f"CARD_{index:02d}" for index in range(1, 30)]
    if sorted(manifest_cards) != expected_card_ids:
        raise AssertionError("canonical CARD_01..CARD_29 fixture set drift")
    commander = runtime.get("commander_proof") or {}
    card02_runtime_pass = (
        commander.get("actual_card_fixture_id") == "CARD_02"
        and commander.get("card_identity") == "Rograkh, Son of Rohgahh"
        and commander.get("cast_from_command_runtime_verified") is True
        and commander.get("commander_cast_count") == 1
        and commander.get("actual_card_behavior_verified") is True
    )
    if not card02_runtime_pass:
        raise AssertionError("CARD_02 behavioral runtime proof missing")

    card_rows = []
    for index, identity in enumerate(cards, start=1):
        fixture_id = f"CARD_{index:02d}"
        manifest_identity = manifest_cards[fixture_id].get("card_identity")
        if manifest_identity != identity:
            raise AssertionError(
                f"{fixture_id} identity drift: manifest={manifest_identity!r} domain={identity!r}"
            )
        if fixture_id == "CARD_02":
            card_rows.append(
                {
                    "fixture_id": fixture_id,
                    "card_identity": identity,
                    "verdict": "PASS",
                    "behavioral_evidence_class": "RUNTIME_VERIFIED",
                    "classification": "RUNTIME_PASS",
                    "reason": (
                        "Rograkh was Forge-legally cast from the command zone, counted as a "
                        "commander cast, and resolved to the battlefield"
                    ),
                }
            )
        else:
            card_rows.append(
                {
                    "fixture_id": fixture_id,
                    "card_identity": identity,
                    "verdict": "NOT_RUN",
                    "behavioral_evidence_class": "NOT_RUN",
                    "classification": "FAIL_CLOSED_UNSUPPORTED",
                    "reason": (
                        "WS23_FAIL_CLOSED_UNSUPPORTED: no card-specific behavioral runtime "
                        "scenario executed; source presence/load/parsing is explicitly not function"
                    ),
                }
            )

    common_output = {
        "schema_version": "ws23-broad-common-qualification/1.0.0",
        "denominator": len(common_rows),
        "pass_count": sum(row["verdict"] == "PASS" for row in common_rows),
        "not_run_count": sum(row["verdict"] == "NOT_RUN" for row in common_rows),
        "rows": common_rows,
    }
    cards_output = {
        "schema_version": "ws23-actual-card-behavioral-qualification/1.0.0",
        "denominator": len(card_rows),
        "pass_count": sum(row["verdict"] == "PASS" for row in card_rows),
        "not_run_count": sum(row["verdict"] == "NOT_RUN" for row in card_rows),
        "rows": card_rows,
    }
    summary = {
        "schema_version": "ws23-broad-qualification-summary/1.0.0",
        "gate_d_continue": bounded.get("continue_gate"),
        "player_count_pass_count": player_counts["pass_count"],
        "player_count_denominator": player_counts["denominator"],
        "common_pass_count": common_output["pass_count"],
        "common_denominator": common_output["denominator"],
        "actual_card_pass_count": cards_output["pass_count"],
        "actual_card_denominator": cards_output["denominator"],
        "production_ready": (
            common_output["pass_count"] == common_output["denominator"]
            and cards_output["pass_count"] == cards_output["denominator"]
        ),
    }

    for path, payload in (
        (args.common_output, common_output),
        (args.cards_output, cards_output),
        (args.summary_output, summary),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
