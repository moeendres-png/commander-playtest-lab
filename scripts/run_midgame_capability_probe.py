#!/usr/bin/env python3
"""End-to-end runtime probe for the production-reachable mid-game lane.

Launches the pinned engine's real ``midgame`` Protocol-2 process, submits only
decisions the engine itself offered, and writes a receipt containing the
engine's own capability manifest, the engine's own construction verdict and the
engine's own rejection codes.

The probe never computes legality, never invents an option and never converts a
rejection into a pass. A row is reported as reachable only when the engine
accepted the explicit frozen starting state and its field-level readback compare
reported no mismatch outside the documented declaration-step priority
allowance.

Usage:
    python scripts/run_midgame_capability_probe.py --out <receipt.json>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import midgame_lane as ml  # noqa: E402

MATERIALIZATION = (
    REPO_ROOT / "qualification" / "ws47" / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
)

# Rows chosen to span the mechanism classes the current-boundary XMage column
# fails closed on one coarse capability bit. Each is a real frozen record with
# real card identities.
PROBE_ROWS: tuple[str, ...] = (
    "WS05-MP-COMBAT-4",
    "WS05-MP-COMBAT-5",
    "WS05-MP-BLOCK-4",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-TURN-5",
    "WS05-CMD-ELIM-4",
    "WS05-CMD-DMG-SPLIT",
    "WS05-CMD-PARTNER-ZONE",
    "WS05-CMD-TAX-2",
    "MICRO_REPLACEMENT",
    "MICRO_COMBAT",
    "CARD_02",
    "WS05-MP-PRIO-3",
    "WS05-CMD-DMG-CONTROL",
    "WS05-CMD-ZONE-GY-YES",
    "MICRO_ZONE_CHANGES",
)

SEED = 424242


# Causal-entry rows. Each names the frozen record, the entry mode, the
# declared fuel or instruments, and the terminal obligation the row requires
# after the causal route has executed. Fuel and instruments are declared here,
# placed through the engine seam, and published in the receipt; nothing is
# inferred by the lane.
CAUSAL_ROWS: dict[str, dict[str, object]] = {
    "WS05-MP-PRIO-3": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p1",
                "card_identity": "Mountain",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "priority_ring_with_live_response",
    },
    "WS05-MP-PRIO-5": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p1",
                "card_identity": "Mountain",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "priority_ring_with_live_response",
    },
    "WS05-CMD-ZONE-GY-YES": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-swamp-a",
                "card_identity": "Swamp",
                "owner": "P2",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-swamp-b",
                "card_identity": "Swamp",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "MICRO_ZONE_CHANGES": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p1",
                "card_identity": "Mountain",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "spell_resolves_to_graveyard",
    },
    "WS05-MP-ELIM-PRIO-3": {
        "entry_mode": "causal_elimination",
        "elimination_actor": "P1",
        "elimination_victim": "P2",
        "bolt_count": 14,
        "terminal": "victim_eliminated_by_engine",
    },
}


def launch_argv(workspace: Path, classpath: str) -> tuple[str, ...]:
    return (
        "java",
        "-Djava.awt.headless=true",
        f"-Dcommanderlab.repoRoot={REPO_ROOT}",
        "-cp",
        f"{workspace / 'target' / 'classes'}:{classpath}",
        "org.commanderlab.xmage.Main",
        "midgame",
    )


def option_of_type(decision: dict[str, Any], option_type: str) -> str | None:
    for option in decision.get("legal_options") or ():
        if option.get("option_type") == option_type:
            return str(option.get("option_id"))
    return None


def option_by_label_suffix(decision: dict[str, Any], suffix: str) -> str | None:
    for option in decision.get("legal_options") or ():
        label = str(option.get("label") or "")
        if label.endswith(suffix):
            return str(option.get("option_id"))
    return None


def seat_label(principal_id: str) -> str:
    return "Full Game Seat " + principal_id.removeprefix("P")


# The frozen record addresses a checkpoint by (phase, step) pair; the engine's
# readback names the same point by a single step token. The mapping is the
# engine seam's own, reproduced here so the probe compares the engine's live
# reading against the record's own request rather than against a guess.
_ENGINE_STEP_BY_POINT: dict[tuple[str, str], str] = {
    ("beginning", "upkeep"): "UPKEEP",
    ("beginning", "draw"): "DRAW",
    ("precombat_main", "main"): "PRECOMBAT_MAIN",
    ("combat", "declare_attackers"): "DECLARE_ATTACKERS",
    ("combat", "declare_blockers"): "DECLARE_BLOCKERS",
    ("combat", "combat_damage"): "COMBAT_DAMAGE",
    ("postcombat_main", "main"): "POSTCOMBAT_MAIN",
}


def engine_temporal_point(phase: str, step: str, fixture_id: str) -> tuple[str, str]:
    try:
        return phase.upper(), _ENGINE_STEP_BY_POINT[(phase, step)]
    except KeyError as exc:
        raise ml.MidgameLaneError(
            f"{fixture_id}: the probe does not know the engine step for {phase}/{step}"
        ) from exc


def drive_arrival(client: ml.MidgameLaneClient, record: dict[str, Any]) -> ml.RowVerdict | None:
    """Drive the engine to the record's own temporal checkpoint.

    Every step is an external pilot answer selected from the engine's own
    offered options. The function answers nothing on the pilot's behalf and
    fails closed on a decision class it does not recognise.
    """
    temporal = record["temporal_state"]
    target_phase, target_step = engine_temporal_point(
        str(temporal["phase"]), str(temporal["step"]), str(record["fixture_id"])
    )
    active_label = seat_label(str(temporal["active_player"]))

    for _ in range(120):
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class == "mulligan":
            keep = option_of_type(decision, "keep")
            if keep is None:
                raise ml.MidgameLaneError("the engine offered no keep option for the mulligan")
            client.submit_options(decision, [keep])
        elif decision_class in {"choice", "choose_object"}:
            chosen = option_by_label_suffix(decision, active_label)
            if chosen is None:
                raise ml.MidgameLaneError(
                    f"the engine offered no option for the record's active principal {active_label}"
                )
            client.submit_options(decision, [chosen])
        elif decision_class == "priority":
            probe = client.complete_arrival().get("readback") or {}
            if str(probe.get("phase")) == target_phase and str(probe.get("step")) == target_step:
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError("the engine offered no pass-priority option")
            client.submit_options(decision, [passed])
        elif decision_class in {"declare_attacker", "declare_blocker"}:
            # A declaration checkpoint: the engine has reached the record's
            # temporal point. Stop and let the caller decide whether to
            # execute the obligation.
            probe = client.complete_arrival().get("readback") or {}
            if str(probe.get("phase")) == target_phase and str(probe.get("step")) == target_step:
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            raise ml.MidgameLaneError(
                f"the engine reached {probe.get('phase')}/{probe.get('step')} before the "
                f"record's requested {target_phase}/{target_step} checkpoint"
            )
        else:
            raise ml.MidgameLaneError(
                f"the probe refuses to answer an unrecognised decision class: {decision_class}"
            )
    raise ml.MidgameLaneError("the engine did not reach the record's temporal checkpoint")


def probe_row(workspace: Path, classpath: str, fixture_id: str) -> dict[str, Any]:
    record = ml.frozen_record(MATERIALIZATION, fixture_id)
    game_id = f"probe-{fixture_id}"
    request = {
        "game_id": game_id,
        "plan_id": game_id,
        "seed": SEED,
        "requested_starting_state": record,
    }
    started = time.time()
    with ml.MidgameLaneClient(launch_argv(workspace, classpath), workspace) as client:
        client.request("get_provider_version", None)
        client.read_dimension_manifest()
        created = client.request("create_midgame_game", request)
        if not created.get("success"):
            errors = created.get("errors") or []
            code = errors[0].get("code") if errors else None
            detail = errors[0].get("message") if errors else None
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=code,
                detail=detail,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        start = client.request("start_midgame_game", None)
        if not start.get("success"):
            errors = start.get("errors") or []
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=errors[0].get("code") if errors else None,
                detail=errors[0].get("message") if errors else None,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        try:
            row_verdict = drive_arrival(client, record)
        except ml.MidgameLaneError as exc:
            # The engine accepted the explicit starting state; the probe only
            # failed to execute the row's own scripted obligation. Recorded
            # distinctly so an accepted starting state is never reported as an
            # engine rejection, and never as a row-level pass either.
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code="OBLIGATION_NOT_EXECUTED",
                detail=str(exc),
                engine_commit=client.engine_commit,
                state_accepted=True,
            )
            return verdict.as_dict() | {
                "outcome": "ENGINE_STATE_ACCEPTED",
                "elapsed_s": round(time.time() - started, 3),
            }
        if row_verdict is None:
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code="OBLIGATION_NOT_EXECUTED",
                detail="the engine went terminal before the record's temporal checkpoint",
                engine_commit=client.engine_commit,
                state_accepted=True,
            )
            return verdict.as_dict() | {
                "outcome": "ENGINE_STATE_ACCEPTED",
                "elapsed_s": round(time.time() - started, 3),
            }
        return row_verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}


# ----------------------------------------------------------------------
# Causal-entry drivers. Every answer below is an external pilot selection
# from the engine's own offered options. The lane places the pre-causal
# position and verifies the causal outcome; it never casts, pays, resolves
# or eliminates anything itself.
# ----------------------------------------------------------------------


def submit_proposal(
    client: ml.MidgameLaneClient,
    legal: dict[str, Any],
    action: dict[str, Any],
    proposal_id: str,
) -> dict[str, Any]:
    proposal = {
        "proposal_id": proposal_id,
        "actor_id": legal["actor_id"],
        "legal_action_id": action["action_id"],
        "action_type": action["action_type"],
        "target_ids": [],
        "selected_modes": [],
        "choices": {"ordering": []},
        "decision_tier": 1,
        "policy_name": "midgame-causal-external-pilot",
    }
    response = client.request("submit_action", {"proposal": proposal})
    if not response.get("success"):
        errors = response.get("errors") or []
        raise ml.MidgameLaneError(f"the engine rejected the proposal: {errors}")
    return response.get("payload") or {}


def legal_actions(client: ml.MidgameLaneClient) -> dict[str, Any]:
    response = client.request("get_legal_actions", None)
    if not response.get("success"):
        raise ml.MidgameLaneError("get_legal_actions failed closed")
    return response.get("payload") or {}


def find_source_cast(legal: dict[str, Any], native_source_id: str) -> dict[str, Any] | None:
    for action in legal.get("actions") or ():
        metadata = action.get("metadata") or {}
        engine = metadata.get("xmage_option_metadata") or {}
        if (
            engine.get("source_object_id") == native_source_id
            and engine.get("ability_type") == "spell"
        ):
            return action
    return None


def find_native_offer(legal: dict[str, Any], native_id: str) -> dict[str, Any] | None:
    for action in legal.get("actions") or ():
        metadata = action.get("metadata") or {}
        engine = metadata.get("xmage_option_metadata") or {}
        for value in engine.values():
            if value == native_id:
                return action
    return None


def find_pool_spend(legal: dict[str, Any]) -> dict[str, Any] | None:
    spends = [
        action
        for action in legal.get("actions") or ()
        if (action.get("metadata") or {}).get("option_type") == "mana_pool"
    ]
    return spends[0] if len(spends) == 1 else None


def drain_combat_to_priority(client: ml.MidgameLaneClient, tag: str) -> None:
    """Answer combat declarations with holds/empties until priority is pending."""
    for _ in range(60):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal while draining combat")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            return
        legal = legal_actions(client)
        if decision_class == "declare_attacker":
            # The hold lives in the action projection, not the decision frame.
            for action in legal.get("actions") or ():
                metadata = action.get("metadata") or {}
                if metadata.get("option_type") == "hold_attacker":
                    submit_proposal(client, legal, action, f"{tag}-hold")
                    break
            else:
                raise ml.MidgameLaneError(f"{tag}: the engine offered no hold")
            continue
        if decision_class == "declare_blocker":
            proposal = {
                "proposal_id": f"{tag}-noblock",
                "actor_id": legal["actor_id"],
                "legal_action_id": "empty-block",
                "action_type": "declare_blockers",
                "target_ids": [],
                "selected_modes": [],
                "choices": {"ordering": []},
                "decision_tier": 1,
                "policy_name": "midgame-causal-external-pilot",
            }
            response = client.request("submit_action", {"proposal": proposal})
            if not response.get("success"):
                raise ml.MidgameLaneError(f"{tag}: empty block rejected")
            continue
        raise ml.MidgameLaneError(
            f"{tag}: expected combat or priority while draining, observed {decision_class}"
        )
    raise ml.MidgameLaneError(f"{tag}: the engine never returned to priority")


def cast_frame_source(
    client: ml.MidgameLaneClient,
    tag: str,
    native_source_id: str,
) -> None:
    drain_combat_to_priority(client, tag)
    for _ in range(40):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal seeking the cast")
        if str(decision.get("decision_class")) != "priority":
            raise ml.MidgameLaneError(
                f"{tag}: expected priority to cast, observed {decision.get('decision_class')}"
            )
        legal = legal_actions(client)
        cast = find_source_cast(legal, native_source_id)
        if cast is not None:
            submit_proposal(client, legal, cast, tag)
            return
        passed = option_of_type(decision, "pass_priority")
        if passed is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
        client.submit_options(decision, [passed])
    raise ml.MidgameLaneError(f"{tag}: the engine never offered the requested source cast")


def answer_object_target(
    client: ml.MidgameLaneClient,
    tag: str,
    native_target_id: str,
) -> None:
    for _ in range(20):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal seeking the target")
        if str(decision.get("decision_class")) != "target":
            raise ml.MidgameLaneError(
                f"{tag}: expected a target decision, observed {decision.get('decision_class')}"
            )
        offer = find_native_offer(legal_actions(client), native_target_id)
        if offer is not None:
            submit_proposal(client, legal_actions(client), offer, tag)
            return
        raise ml.MidgameLaneError(f"{tag}: the engine never offered the requested target")
    raise ml.MidgameLaneError(f"{tag}: the target was never offered")


def answer_player_target(
    client: ml.MidgameLaneClient,
    tag: str,
    seat_name: str,
) -> None:
    for _ in range(20):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal seeking the target")
        if str(decision.get("decision_class")) != "target":
            raise ml.MidgameLaneError(
                f"{tag}: expected a target decision, observed {decision.get('decision_class')}"
            )
        legal = legal_actions(client)
        for action in legal.get("actions") or ():
            metadata = action.get("metadata") or {}
            if metadata.get("label") == seat_name:
                submit_proposal(client, legal, action, tag)
                return
        raise ml.MidgameLaneError(f"{tag}: the engine never offered {seat_name} as a target")
    raise ml.MidgameLaneError(f"{tag}: the target was never offered")


def answer_fuel_mana(
    client: ml.MidgameLaneClient,
    tag: str,
    fuel_native_ids: list[str],
) -> None:
    """Pay from declared fuel abilities, then from the resulting pool.

    Any offered ability whose source is a declared fuel card may be used; the
    engine offers its untapped fuel in its own order and never re-offers a
    tapped land, so matching the set (not a position) consumes fuel exactly
    once each. A fuel card the engine never offers is never touched.
    """
    fuel_set = set(fuel_native_ids)
    for _ in range(40):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal seeking mana")
        if str(decision.get("decision_class")) != "mana_payment":
            return
        legal = legal_actions(client)
        tapped = False
        for action in legal.get("actions") or ():
            metadata = action.get("metadata") or {}
            engine = metadata.get("xmage_option_metadata") or {}
            if (
                metadata.get("option_type") == "mana_ability"
                and engine.get("source_object_id") in fuel_set
            ):
                submit_proposal(client, legal, action, f"{tag}-tap")
                tapped = True
                break
        if tapped:
            continue
        spend = find_pool_spend(legal)
        if spend is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no single pool spend")
        submit_proposal(client, legal, spend, f"{tag}-spend")


def complete_causal(
    client: ml.MidgameLaneClient,
    mode: str,
) -> dict[str, Any]:
    response = client.request("complete_causal_reconstruction", {"mode": mode})
    if not response.get("success"):
        errors = response.get("errors") or []
        raise ml.MidgameLaneError(f"complete_causal_reconstruction failed: {errors}")
    return response.get("payload") or {}


def causal_stack_frames(
    client: ml.MidgameLaneClient,
    tag: str,
    causal_plan: dict[str, Any],
    placed: dict[str, str],
    fuel_native_ids: list[str],
) -> None:
    """Cast every causal frame bottom-to-top through the engine."""
    for frame in causal_plan.get("frames_bottom_to_top") or ():
        frame_tag = f"{tag}-{frame.get('semantic_id')}"
        cast_frame_source(client, frame_tag, str(frame.get("native_source_id")))
        for target in frame.get("targets") or ():
            if target in placed:
                answer_object_target(client, f"{frame_tag}-target", placed[target])
            else:
                answer_player_target(client, f"{frame_tag}-target", seat_label(str(target)))
        if fuel_native_ids:
            answer_fuel_mana(client, f"{frame_tag}-mana", fuel_native_ids)


def observe_priority_ring(
    client: ml.MidgameLaneClient,
    tag: str,
    passes: int = 3,
) -> dict[str, Any]:
    """Pass priority and record the ring order. Every pass is engine-offered."""
    actors: list[str] = []
    for _ in range(12):
        decision = client.pending_decision()
        if decision is None:
            break
        if str(decision.get("decision_class")) != "priority":
            break
        actors.append(str(decision.get("actor_id")))
        passed = option_of_type(decision, "pass_priority")
        if passed is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
        client.submit_options(decision, [passed])
        if len(actors) >= passes:
            break
    distinct = sorted(set(actors))
    return {
        "kind": "priority_ring_with_live_response",
        "observed": len(actors) >= passes and len(distinct) >= passes,
        "detail": f"ring actors observed in order: {len(actors)} passes across {len(distinct)} principals",
        "actors_sample": distinct[:passes],
    }


def resolve_and_record_classes(
    client: ml.MidgameLaneClient,
    tag: str,
    bound: int = 120,
) -> dict[str, Any]:
    """Resolve fully, recording every decision class the engine offers."""
    trace: list[str] = []
    reached_cleanup_discard = False
    for _ in range(bound):
        decision = client.pending_decision(attempts=5)
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        trace.append(decision_class)
        if decision_class == "choose_object":
            prompt = str(decision.get("prompt") or "")
            if "discard" in prompt:
                reached_cleanup_discard = True
                break
            raise ml.MidgameLaneError(f"{tag}: unexpected non-discard choose_object")
        if decision_class == "declare_attacker":
            drain_combat_to_priority(client, f"{tag}-hold")
            continue
        if decision_class == "declare_blocker":
            legal = legal_actions(client)
            proposal = {
                "proposal_id": f"{tag}-noblock",
                "actor_id": legal["actor_id"],
                "legal_action_id": "empty-block",
                "action_type": "declare_blockers",
                "target_ids": [],
                "selected_modes": [],
                "choices": {"ordering": []},
                "decision_tier": 1,
                "policy_name": "midgame-causal-external-pilot",
            }
            response = client.request("submit_action", {"proposal": proposal})
            if not response.get("success"):
                raise ml.MidgameLaneError(f"{tag}: empty block rejected")
            continue
        if decision_class != "priority":
            # Any other class (choice, choose_use, replacement_effect, ...) is
            # an obligation, not resolution transport: stop and report.
            break
        passed = option_of_type(decision, "pass_priority")
        if passed is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
        client.submit_options(decision, [passed])
    return {
        "trace": trace,
        "reached_cleanup_discard": reached_cleanup_discard,
    }


def probe_causal_row(
    workspace: Path,
    classpath: str,
    fixture_id: str,
    spec: dict[str, object],
) -> dict[str, Any]:
    record = ml.frozen_record(MATERIALIZATION, fixture_id)
    game_id = f"probe-causal-{fixture_id}"
    entry_mode = str(spec["entry_mode"])
    started = time.time()
    with ml.MidgameLaneClient(launch_argv(workspace, classpath), workspace) as client:
        client.request("get_provider_version", None)
        client.read_dimension_manifest()
        request: dict[str, Any] = {
            "game_id": game_id,
            "plan_id": game_id,
            "seed": SEED,
            "entry_mode": entry_mode,
            "requested_starting_state": record,
        }
        if entry_mode == "causal_stack":
            request["fuel"] = list(spec.get("fuel") or [])
        elif entry_mode == "causal_elimination":
            instruments: list[dict[str, str]] = []
            bolt_count = int(spec.get("bolt_count") or 0)
            actor = str(spec["elimination_actor"])
            for index in range(bolt_count):
                instruments.append(
                    {
                        "semantic_id": f"obj:elim-bolt-{index}",
                        "card_identity": "Lightning Bolt",
                        "owner": actor,
                        "zone": "hand",
                    }
                )
                instruments.append(
                    {
                        "semantic_id": f"obj:elim-mountain-{index}",
                        "card_identity": "Mountain",
                        "owner": actor,
                        "zone": "battlefield",
                    }
                )
            request["elimination"] = {
                "actor": actor,
                "victim": str(spec["elimination_victim"]),
                "instruments": instruments,
            }
        created = client.request("create_midgame_game", request)
        if not created.get("success"):
            errors = created.get("errors") or []
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=errors[0].get("code") if errors else None,
                detail=errors[0].get("message") if errors else None,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        payload = created.get("payload") or {}
        start = client.request("start_midgame_game", None)
        if not start.get("success"):
            errors = start.get("errors") or []
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=errors[0].get("code") if errors else None,
                detail=errors[0].get("message") if errors else None,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        try:
            if entry_mode == "causal_stack":
                row = drive_causal_stack(client, fixture_id, record, payload, spec)
            else:
                row = drive_causal_elimination(client, fixture_id, record, payload, spec)
        except ml.MidgameLaneError as exc:
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code="CAUSAL_TRANSPORT_FAILURE",
                detail=str(exc),
                engine_commit=client.engine_commit,
                state_accepted=True,
            )
            return verdict.as_dict() | {
                "outcome": "ENGINE_STATE_ACCEPTED",
                "entry_mode": entry_mode,
                "elapsed_s": round(time.time() - started, 3),
            }
        row["elapsed_s"] = round(time.time() - started, 3)
        row["entry_mode"] = entry_mode
        return row


def drive_causal_stack(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    causal_plan = created.get("causal_plan") or {}
    placed = {str(k): str(v) for k, v in (causal_plan.get("placed_objects") or {}).items()}
    fuel_native_ids = [
        placed[card["semantic_id"]]
        for card in (spec.get("fuel") or [])
        if isinstance(card, dict) and card.get("semantic_id") in placed
    ]
    drive_arrival(client, record)
    causal_stack_frames(client, f"probe-{fixture_id}", causal_plan, placed, fuel_native_ids)
    stack_verdict = complete_causal(client, "stack").get("verdict") or {}
    terminal_kind = str(spec.get("terminal"))
    terminal: dict[str, Any] | None = None
    if terminal_kind == "priority_ring_with_live_response":
        terminal = observe_priority_ring(client, f"probe-{fixture_id}")
    elif terminal_kind == "commander_zone_choice":
        resolution = resolve_and_record_classes(client, f"probe-{fixture_id}")
        trace = resolution["trace"]
        choice_seen = any(c in {"choice", "choose_use", "replacement_effect"} for c in trace)
        if choice_seen:
            terminal = {
                "kind": terminal_kind,
                "observed": True,
                "detail": f"the engine offered a zone-choice decision; trace={trace}",
            }
        else:
            terminal = {
                "kind": terminal_kind,
                "observed": False,
                "detail": "the engine resolved to "
                + ("cleanup" if resolution["reached_cleanup_discard"] else "terminal")
                + f" with no zone-choice decision; trace={trace}",
            }
    elif terminal_kind == "spell_resolves_to_graveyard":
        before = graveyard_count(client, record)
        resolve_and_record_classes(client, f"probe-{fixture_id}")
        after = graveyard_count(client, record)
        terminal = {
            "kind": terminal_kind,
            "observed": after > before,
            "detail": f"graveyard count moved {before} -> {after}",
        }
    else:
        raise ml.MidgameLaneError(f"unknown causal terminal: {terminal_kind}")
    row_verdict = ml.classification_from_causal_verdict(
        fixture_id,
        ml.MIDGAME_LANE,
        "causal_stack",
        stack_verdict,
        terminal,
        engine_commit=client.engine_commit,
    )
    return row_verdict.as_dict()


def graveyard_count(client: ml.MidgameLaneClient, record: dict[str, Any]) -> int:
    decision = client.pending_decision()
    if decision is None:
        raise ml.MidgameLaneError("the engine went terminal reading zone counts")
    state = client.zone_counts(str(decision.get("actor_id")))
    seats = (state.get("zone_counts") or {}).get("seats") or []
    return sum(int(seat.get("graveyard_count") or 0) for seat in seats)


def drive_causal_elimination(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    plan = created.get("elimination_plan") or {}
    placed = {str(k): str(v) for k, v in (plan.get("placed_objects") or {}).items()}
    bolt_ids = sorted(v for k, v in placed.items() if "bolt" in k)
    mountain_ids = sorted(v for k, v in placed.items() if "mountain" in k)
    victim_seat = seat_label(str(spec["elimination_victim"]))
    bolt_count = int(spec.get("bolt_count") or 0)
    assert len(bolt_ids) == bolt_count and len(mountain_ids) == bolt_count
    drive_arrival(client, record)
    expected_life: int | None = None
    for index in range(bolt_count):
        cast_frame_source(client, f"probe-{fixture_id}-cast-{index}", bolt_ids[index])
        answer_player_target(client, f"probe-{fixture_id}-target-{index}", victim_seat)
        answer_fuel_mana(client, f"probe-{fixture_id}-mana-{index}", mountain_ids)
        expected_life = resolve_until_life_drops(
            client,
            f"probe-{fixture_id}-resolve-{index}",
            str(spec["elimination_victim"]),
            expected_life,
        )
    verdict = complete_causal(client, "elimination").get("verdict") or {}
    row_verdict = ml.classification_from_causal_verdict(
        fixture_id,
        ml.MIDGAME_LANE,
        "causal_elimination",
        verdict,
        None,
        engine_commit=client.engine_commit,
    )
    return row_verdict.as_dict()


def resolve_until_life_drops(
    client: ml.MidgameLaneClient,
    tag: str,
    victim_pid: str,
    previous_life: int | None,
) -> int:
    """Pass priority until the victim's life drops, then stop immediately.

    The elimination verify is a pure query while parked. Stopping at the first
    observed drop means the pilot never passes with an empty stack, so combat
    never starts and cleanup never discards the remaining ammunition.
    """
    for _ in range(30):
        verdict = complete_causal(client, "elimination").get("verdict") or {}
        life = (verdict.get("life_totals") or {}).get(victim_pid)
        if previous_life is None and isinstance(life, int):
            # First observation establishes the baseline; the just-cast spell
            # is still resolving, so keep passing instead of returning.
            previous_life = life
        if isinstance(life, int) and life < previous_life:
            if life != previous_life - 3:
                raise ml.MidgameLaneError(
                    f"{tag}: expected exactly 3 damage, observed {previous_life} -> {life}"
                )
            return life
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal while resolving")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
            client.submit_options(decision, [passed])
            continue
        if decision_class in {"declare_attacker", "declare_blocker"}:
            drain_combat_to_priority(client, tag)
            continue
        raise ml.MidgameLaneError(f"{tag}: unexpected {decision_class} while resolving")
    raise ml.MidgameLaneError(f"{tag}: the victim's life never dropped")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=REPO_ROOT / "engine-bridge",
        help="the Lab engine-bridge module that carries target/classes",
    )
    parser.add_argument(
        "--rows",
        nargs="*",
        default=list(PROBE_ROWS) + [row for row in CAUSAL_ROWS if row not in PROBE_ROWS],
    )
    args = parser.parse_args()

    classpath_file = args.workspace / "target" / "cp-wsr22.txt"
    if not classpath_file.is_file():
        print(
            f"missing {classpath_file}; build the bridge module and regenerate the classpath "
            f"manifest first",
            file=sys.stderr,
        )
        return 2
    classpath = classpath_file.read_text(encoding="utf-8").strip()

    manifest_payload: dict[str, Any] | None = None
    engine_commit: str | None = None
    with ml.MidgameLaneClient(launch_argv(args.workspace, classpath), args.workspace) as client:
        client.request("get_provider_version", None)
        manifest = client.read_dimension_manifest()
        manifest_payload = manifest.as_dict()
        engine_commit = client.engine_commit

    rows: list[dict[str, Any]] = []
    for fixture_id in args.rows:
        if fixture_id in CAUSAL_ROWS:
            rows.append(
                probe_causal_row(args.workspace, classpath, fixture_id, CAUSAL_ROWS[fixture_id])
            )
        else:
            rows.append(probe_row(args.workspace, classpath, fixture_id))

    reachable = [row["fixture_id"] for row in rows if row["outcome"] == "ENGINE_NATIVE_REACHABLE"]
    accepted_only = [row["fixture_id"] for row in rows if row["outcome"] == "ENGINE_STATE_ACCEPTED"]
    causal_reachable = [
        row["fixture_id"] for row in rows if row["outcome"] == "CAUSAL_ROUTE_REACHABLE"
    ]
    causal_measured = [
        {"fixture_id": row["fixture_id"], "detail": row.get("detail")}
        for row in rows
        if row["outcome"] == "CAUSAL_ROUTE_MEASURED_BLOCKED"
    ]
    mismatched = [row["fixture_id"] for row in rows if row["outcome"] == "CONSTRUCTION_MISMATCH"]
    rejected = [
        {"fixture_id": row["fixture_id"], "code": row["code"]}
        for row in rows
        if row["outcome"] == "ENGINE_REJECTED"
    ]

    receipt = {
        "schema_version": "commander-lab.midgame-capability-probe/1.0.0",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe_run_id": str(uuid.uuid4()),
        "evidence_class": "FRESH_RUNTIME_PROTOCOL2_PROCESS",
        "rules_core": "xmage",
        "engine_commit": engine_commit,
        "lane": ml.MIDGAME_LANE,
        "protocol_version": ml.PROTOCOL_VERSION,
        "seed": SEED,
        "materialization": {
            "path": str(MATERIALIZATION.relative_to(REPO_ROOT)),
            "version": "commander-lab.semantic-fixture-materialization/1.0.5",
        },
        "starting_state_dimensions_manifest": manifest_payload,
        "counts": {
            "probed": len(rows),
            "engine_native_reachable": len(reachable),
            "engine_state_accepted_obligation_not_executed": len(accepted_only),
            "causal_route_reachable": len(causal_reachable),
            "causal_route_measured_blocked": len(causal_measured),
            "construction_mismatch": len(mismatched),
            "engine_rejected": len(rejected),
        },
        "engine_native_reachable": reachable,
        "engine_state_accepted_obligation_not_executed": accepted_only,
        "causal_route_reachable": causal_reachable,
        "causal_route_measured_blocked": causal_measured,
        "construction_mismatch": mismatched,
        "engine_rejected": rejected,
        "rows": rows,
        "notes": [
            "Every decision was submitted from the engine's own offered option set.",
            "Reachability requires the engine's own field-level readback compare to report no "
            "mismatch outside the documented declaration-step priority allowance. The engine's own "
            "raw construction_match bit is reported alongside the classification.",
            "CAUSAL_ROUTE_REACHABLE requires the engine's own causal_match with no mismatches "
            "plus the row's terminal obligation observed. CAUSAL_ROUTE_MEASURED_BLOCKED means "
            "the causal route executed but the terminal obligation did not appear; nothing is "
            "promoted.",
            "ENGINE_STATE_ACCEPTED means the engine accepted the explicit starting state and this "
            "probe did not execute the row's own scripted obligation. It is not a row-level pass.",
            "Engine-rejected rows are reported with the engine's own code and stay fail closed.",
            "This probe is technical capability evidence. It is not provider selection and does "
            "not establish Architecture Freeze.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "engine_commit": engine_commit,
                "counts": receipt["counts"],
                "engine_native_reachable": reachable,
                "engine_state_accepted_obligation_not_executed": accepted_only,
                "causal_route_reachable": causal_reachable,
                "causal_route_measured_blocked": causal_measured,
                "engine_rejected": rejected,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
