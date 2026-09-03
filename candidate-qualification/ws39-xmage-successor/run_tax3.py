#!/usr/bin/env python3
"""Execute the mandatory WS-39 Commander-tax three-record runtime gate.

Every decision is selected by an explicit semantic contract selector from the
current XMage-offered legal option set. There is no first/random/default/AI/GUI
fallback. Commander tax is never calculated by this harness: it records base
and adjusted costs emitted by the read-only native XMage probe and verifies the
contract against those values. Tax-2/Tax-4 additionally perform the real cast
and pay from the exact four contract-declared Mountain objects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FC = HERE.parents[0] / "finalist-convergence-xmage"
WS26 = HERE.parents[0] / "ws26-xmage"
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path[:0] = [str(ROOT / "src"), str(HERE), str(WS34), str(FC), str(WS26)]

import canonical_v102  # noqa: E402
import run_ws26_gate as gate  # noqa: E402
from successor_contract import (  # noqa: E402
    canonical_sha,
    load_contract,
    requested_state_digest,
    requested_state_projection,
    ws34_records,
)

MANDATORY = ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4", "WS05-CMD-PARTNER-TAX")
ROGRAKH = "Rograkh, Son of Rohgahh"
KEDISS = "Kediss, Emberclaw Familiar"


def unique(items: list[dict[str, Any]], predicate, label: str) -> dict[str, Any]:
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise RuntimeError(f"SEMANTIC_MATCH_NOT_UNIQUE:{label}:matches={len(matches)}")
    return matches[0]


def probe_row(probe: dict[str, Any], section: str, commander_id: str) -> dict[str, Any]:
    rows = probe.get(section)
    if not isinstance(rows, list):
        raise RuntimeError(f"WS39_PROBE_SECTION_MISSING:{section}")
    return unique(
        rows, lambda row: row.get("commander_id") == commander_id, f"{section}:{commander_id}"
    )


def assert_construction(record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    requested = requested_state_projection(record)
    digest = requested_state_digest(record)
    if digest != record["requested_state_digest"]:
        raise RuntimeError("CONTRACT_REQUESTED_STATE_DIGEST_MISMATCH")
    constructed = state.get("normalized_constructed_state")
    if not isinstance(constructed, dict):
        raise RuntimeError("PROVIDER_NORMALIZED_CONSTRUCTED_STATE_MISSING")
    constructed_digest = canonical_sha(constructed)
    if constructed != requested or constructed_digest != digest:
        raise RuntimeError("REQUESTED_VS_PROVIDER_CONSTRUCTED_STATE_MISMATCH")
    if state.get("normalized_constructed_state_declared_digest") != digest:
        raise RuntimeError("PROVIDER_DECLARED_CONSTRUCTED_DIGEST_MISMATCH")
    if state.get("normalized_constructed_state_proof") != "PROVIDER_NATIVE_SETUP_VALIDATION_BOUND":
        raise RuntimeError("PROVIDER_NATIVE_SETUP_PROOF_MISSING")
    validation = state.get("normalized_constructed_state_native_validation")
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise RuntimeError("PROVIDER_NATIVE_SETUP_VALIDATION_NOT_PASS")
    history_validation = validation.get("commander_history")
    if not isinstance(history_validation, dict) or history_validation.get("valid") is not True:
        raise RuntimeError("COMMANDER_HISTORY_NATIVE_VALIDATION_NOT_PASS")
    return {
        "requested_state_digest": digest,
        "constructed_state_digest": constructed_digest,
        "requested_native_state_equal": True,
        "native_validation": validation,
    }


def assert_initial_probe(record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    probe = state.get("ws39_commander_probe")
    if not isinstance(probe, dict):
        raise RuntimeError("WS39_COMMANDER_PROBE_MISSING")
    if (
        probe.get("rules_core_authoritative") is not True
        or probe.get("read_only_game_state") is not True
    ):
        raise RuntimeError("WS39_COMMANDER_PROBE_AUTHORITY_INVALID")
    if probe.get("synthetic_historical_events") is not False:
        raise RuntimeError("WS39_SYNTHETIC_HISTORY_NOT_FALSE")

    expected = {
        item["commander_id"]: int(item["prior_command_zone_cast_count"])
        for item in record["commander_state"]["commanders"]
    }
    for commander_id, count in expected.items():
        history = probe_row(probe, "commander_history", commander_id)
        if int(history["live_command_zone_cast_count"]) != count:
            raise RuntimeError(f"COMMANDER_HISTORY_INITIAL_MISMATCH:{commander_id}")

    rograkh = probe_row(probe, "commander_costs", "cmd:P1-A")
    if rograkh.get("card_name") != ROGRAKH:
        raise RuntimeError("P1_A_NOT_ROGRAKH")
    if int(rograkh["native_base_mana_count"]) != 0:
        raise RuntimeError("ROGRAKH_NATIVE_BASE_COST_NOT_ZERO")
    if int(rograkh["native_commander_adjusted_mana_count"]) != 4:
        raise RuntimeError("ROGRAKH_NATIVE_ADJUSTED_COST_NOT_FOUR")
    if rograkh.get("rules_core_method") != "Card.commanderCost":
        raise RuntimeError("ROGRAKH_COST_NOT_RULES_CORE_DERIVED")

    result: dict[str, Any] = {
        "probe_schema": probe.get("schema_version"),
        "p1_rograkh": rograkh,
        "history": probe.get("commander_history"),
        "player_totals": probe.get("player_totals"),
    }
    if record["fixture_id"] == "WS05-CMD-PARTNER-TAX":
        kediss = probe_row(probe, "commander_costs", "cmd:P1-B")
        if kediss.get("card_name") != KEDISS:
            raise RuntimeError("P1_B_NOT_KEDISS")
        if int(kediss["native_commander_adjusted_mana_count"]) != int(
            kediss["native_base_mana_count"]
        ):
            raise RuntimeError("KEDISS_ZERO_TAX_NOT_NATIVE_EQUAL")
        result["p1_kediss"] = kediss
    return result


def start_fixture(record: dict[str, Any]):
    decks, scenario = canonical_v102.deck_and_scenario(record)
    client = gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0)
    client.__enter__()
    try:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request(
            "create_full_game",
            {
                "game_id": f"WS39-TAX3-{record['fixture_id']}",
                "deck_handles": handles,
                "starting_player_seat": int(scenario["starting_player_seat"]) - 1,
                "starting_life": 40,
                "seed": int(scenario["seed"]),
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        if configured.get("execution_entry_mode") != record["execution_entry_mode"]:
            raise RuntimeError("CONFIGURED_ENTRY_MODE_MISMATCH")
        client.request("start_full_game")
        state = client.request("get_qualification_state")
        return client, scenario, state
    except Exception:
        client.__exit__(*sys.exc_info())
        raise


def unique_cast_option(decision: dict[str, Any]) -> dict[str, Any]:
    if decision.get("decision_class") != "priority" or int(decision.get("seat", -1)) != 0:
        raise RuntimeError("TAX_EXPECTED_P1_PRIORITY")
    return unique(
        decision.get("legal_options") or [],
        lambda option: (
            option.get("option_type") == "activated_ability"
            and (option.get("metadata") or {}).get("source_name") == ROGRAKH
        ),
        "P1_ROGRAKH_CAST",
    )


def pay_exact_sources(
    client: gate._RawFullGameClient,
    first_payload: dict[str, Any],
    payment_sources: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = first_payload
    evidence: list[dict[str, Any]] = []
    for semantic_source in payment_sources:
        decision = payload.get("decision")
        if not isinstance(decision, dict):
            payload = client.request("get_full_game_decision")
            decision = payload.get("decision")
        if not isinstance(decision, dict) or decision.get("decision_class") != "mana_payment":
            raise RuntimeError(f"EXPECTED_MANA_PAYMENT_FOR:{semantic_source}")
        option = unique(
            decision.get("legal_options") or [],
            lambda item, semantic_source=semantic_source: (
                item.get("option_type") == "mana_ability"
                and (item.get("metadata") or {}).get("semantic_source_object_id")
                == semantic_source
            ),
            f"MANA_SOURCE:{semantic_source}",
        )
        metadata = option.get("metadata") or {}
        evidence.append(
            {
                "semantic_source_object_id": semantic_source,
                "offered_option_id": option.get("option_id"),
                "source_name": metadata.get("source_name"),
                "unpaid_mana_before": (decision.get("context") or {}).get("unpaid_mana"),
            }
        )
        payload = gate.submit_one(client, decision, [str(option["option_id"])])
    return evidence, payload


def execute_tax_cast(record: dict[str, Any], client: gate._RawFullGameClient) -> dict[str, Any]:
    cost_state = record.get("action_cost_state") or []
    if len(cost_state) != 1:
        raise RuntimeError("TAX_ACTION_COST_STATE_NOT_SINGLE")
    payment_sources = list(cost_state[0].get("explicit_payment_sources") or [])
    if len(payment_sources) != 4 or len(set(payment_sources)) != 4:
        raise RuntimeError("TAX_EXPLICIT_PAYMENT_SOURCES_NOT_EXACT_FOUR")

    payload = client.request("get_full_game_decision")
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        raise RuntimeError("TAX_PRIORITY_DECISION_MISSING")
    cast_option = unique_cast_option(decision)
    after_cast_selection = gate.submit_one(client, decision, [str(cast_option["option_id"])])
    mana_evidence, _ = pay_exact_sources(client, after_cast_selection, payment_sources)

    after = client.request("get_qualification_state")
    probe = after.get("ws39_commander_probe")
    if not isinstance(probe, dict):
        raise RuntimeError("WS39_POST_CAST_PROBE_MISSING")
    history = probe_row(probe, "commander_history", "cmd:P1-A")
    if int(history["live_command_zone_cast_count"]) != 3:
        raise RuntimeError("ROGRAKH_POST_CAST_HISTORY_NOT_THREE")

    objects = (after.get("semantic_state") or {}).get("scenario_objects") or []
    by_id = {item.get("semantic_id"): item for item in objects if isinstance(item, dict)}
    for semantic_source in payment_sources:
        obj = by_id.get(semantic_source)
        if (
            not isinstance(obj, dict)
            or obj.get("card_name") != "Mountain"
            or obj.get("tapped") is not True
        ):
            raise RuntimeError(f"PAYMENT_SOURCE_NOT_NATIVE_TAPPED:{semantic_source}")

    return {
        "cast_selector": {
            "decision_class": decision.get("decision_class"),
            "option_type": cast_option.get("option_type"),
            "source_name": (cast_option.get("metadata") or {}).get("source_name"),
            "unique_match": True,
        },
        "payment_sources_contract": payment_sources,
        "mana_payment_decisions": mana_evidence,
        "post_cast_history": history,
        "all_contract_payment_sources_native_tapped": True,
        "native_cast_event_inferred_from_watcher_increment": True,
    }


def execute_one(record: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "fixture_id": record["fixture_id"],
        "record_digest": record["materialization_digest"],
        "status": "FAIL_CLOSED",
        "runtime_credit": "WITHHELD",
    }
    client = None
    try:
        client, _scenario, state = start_fixture(record)
        row["construction"] = assert_construction(record, state)
        row["initial_native_probe"] = assert_initial_probe(record, state)
        if record["fixture_id"] == "WS05-CMD-PARTNER-TAX":
            row["transaction"] = {
                "native_cost_enumeration": "PASS",
                "p1_rograkh_tax_observed_as_native_base_0_adjusted_4": True,
                "p1_kediss_tax_observed_as_native_adjusted_equals_base": True,
            }
        else:
            row["transaction"] = execute_tax_cast(record, client)
        row["status"] = "PASS"
        row["runtime_credit"] = "FRESH_WS39_RUNTIME_PASS"
        return row
    except Exception as exc:
        row["error_type"] = type(exc).__name__
        row["error"] = str(exc)
        return row
    finally:
        if client is not None:
            client.__exit__(None, None, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    selected = {row["fixture_id"]: row for row in ws34_records(contract)}
    if any(fixture_id not in selected for fixture_id in MANDATORY):
        raise SystemExit("WS39_TAX3_CONTRACT_ID_MISSING")

    rows = [execute_one(selected[fixture_id]) for fixture_id in MANDATORY]
    passed = sum(row["status"] == "PASS" for row in rows)
    output = {
        "schema_version": "commander-lab.ws39-tax3-runtime/1.0.0",
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "engine_commit": os.environ.get("XMAGE_WS39_COMMIT", "UNKNOWN"),
        "denominator": 3,
        "pass_count": passed,
        "fail_count": 3 - passed,
        "historical_pass_imported": False,
        "records": rows,
        "gate": "PASS" if passed == 3 else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"tax3_pass": passed, "tax3_denominator": 3, "gate": output["gate"]}, sort_keys=True
        )
    )
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
