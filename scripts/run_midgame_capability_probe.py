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
import re
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import bridge_launcher  # noqa: E402
from commander_lab.qualification.current_boundary import midgame_lane as ml  # noqa: E402
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary.starting_player import (  # noqa: E402
    SEATS,
    midgame_starting_seat,
)

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

# A causal stack whose controller is then eliminated causally in the same game.
CAUSAL_STACK_ELIMINATION = "causal_stack_elimination"


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
    # MICRO_COPY: P2's Lightning Bolt, then P1's Flare of Duplication on it.
    # The engine decides whether the Flare may target that Bolt.
    "MICRO_COPY": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
            *(
                {
                    "semantic_id": f"obj:fuel-mountain-p1-{index}",
                    "card_identity": "Mountain",
                    "owner": "P1",
                    "zone": "battlefield",
                }
                for index in range(3)
            ),
        ],
        "terminal": "spell_copied_on_stack",
    },
    # MICRO_RULES_RANDOMNESS: P1's Stitch in Time ({1}{U}{R}) on the stack.
    "MICRO_RULES_RANDOMNESS": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": f"obj:fuel-{identity.lower()}-p1",
                "card_identity": identity,
                "owner": "P1",
                "zone": "battlefield",
            }
            for identity in ("Island", "Mountain", "Plains")
        ],
        "terminal": "rules_rng_coin_flip",
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
    "WS05-CMD-ZONE-GY-NO": {
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
    "WS05-CMD-ZONE-EXILE-YES": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-plains-a",
                "card_identity": "Plains",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-CMD-ZONE-EXILE-NO": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-plains-a",
                "card_identity": "Plains",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-CMD-ZONE-HAND-YES": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-island-a",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-CMD-ZONE-HAND-NO": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-island-a",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-CMD-ZONE-LIB-YES": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-forest-a",
                "card_identity": "Forest",
                "owner": "P2",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-plains-a",
                "card_identity": "Plains",
                "owner": "P2",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-island-a",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-CMD-ZONE-LIB-NO": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-forest-a",
                "card_identity": "Forest",
                "owner": "P2",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-plains-a",
                "card_identity": "Plains",
                "owner": "P2",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-island-a",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "commander_zone_choice",
    },
    "WS05-MP-ELIM-OWNED-3": {
        "entry_mode": "causal_elimination",
        "elimination_actor": "P1",
        "elimination_victim": "P2",
        "bolt_count": 14,
        "terminal": "victim_eliminated_by_engine",
    },
    # P2's Control Magic must control P1's Bears while P2 is eliminated. An
    # attachment and a control change are caused, never placed: P2 casts the
    # Aura at the Bears on P1's turn under a declared flash enabler (Leyline of
    # Anticipation, CR 702.8a), the engine resolves it and the caused-permanent
    # verifier confirms attachment and control; only then does P1 cause P2's loss.
    "WS05-MP-ELIM-CONTROL-3": {
        "entry_mode": CAUSAL_STACK_ELIMINATION,
        "fuel": [
            {
                "semantic_id": "obj:enabler-leyline-p2",
                "card_identity": "Leyline of Anticipation",
                "owner": "P2",
                "zone": "battlefield",
            },
            *(
                {
                    "semantic_id": f"obj:fuel-island-p2-{index}",
                    "card_identity": "Island",
                    "owner": "P2",
                    "zone": "battlefield",
                }
                for index in range(4)
            ),
        ],
        "caused_permanents": ["obj:leave-controlmagic"],
        "elimination_actor": "P1",
        "elimination_victim": "P2",
        "bolt_count": 14,
        "terminal": "caused_permanent_controller_eliminated",
    },
    "WS05-MP-ELIM-TURN-3": {
        "entry_mode": "causal_elimination",
        "elimination_actor": "P1",
        "elimination_victim": "P2",
        "bolt_count": 14,
        "terminal": "victim_eliminated_by_engine",
    },
    "WS05-MP-ELIM-5": {
        "entry_mode": "causal_elimination",
        "elimination_actor": "P1",
        "elimination_victim": "P3",
        "bolt_count": 14,
        "terminal": "victim_eliminated_by_engine",
    },
    # The victim's own spell must be on the stack while the victim is
    # eliminated (CR 800.4a). P2 casts it on the engine's frames, the stack
    # verifier confirms it, and only then does P1 cause P2's loss.
    "WS05-MP-ELIM-STACK-3": {
        "entry_mode": CAUSAL_STACK_ELIMINATION,
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "elimination_actor": "P1",
        "elimination_victim": "P2",
        "bolt_count": 14,
        "terminal": "stack_controller_eliminated",
    },
    "WS05-MP-TURN-5": {
        "entry_mode": "placement",
        "terminal": "extra_turns_in_order",
    },
    "WS05-MP-BLOCK-4": {
        "entry_mode": "placement",
        "terminal": "blocker_partition",
    },
    "MICRO_REPLACEMENT": {
        "entry_mode": "placement",
        "terminal": "damage_doubled_to_six",
    },
    # The stack is built causally; the row's first scripted decision must then be
    # offered to its scripted actor with the scripted option among the offers.
    "PILOT_CHOOSE_OBJECT": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-swamp-p2",
                "card_identity": "Swamp",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "PILOT_CHOICE": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-forest-p1",
                "card_identity": "Forest",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "PILOT_MANA_PAYMENT": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "PILOT_REPLACEMENT_EFFECT": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-island-p2",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "MICRO_MANA_PAYMENT": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "MICRO_PRIORITY": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p1",
                "card_identity": "Mountain",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "MICRO_STACK": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p1",
                "card_identity": "Mountain",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "CARD_13": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "CARD_07": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": f"obj:fuel-island-p2-{index}",
                "card_identity": "Island",
                "owner": "P2",
                "zone": "battlefield",
            }
            for index in range(3)
        ],
        "terminal": "scripted_decision_offered",
    },
    "CARD_16": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": f"obj:fuel-island-p1-{index}",
                "card_identity": "Island",
                "owner": "P1",
                "zone": "battlefield",
            }
            for index in range(3)
        ],
        "terminal": "scripted_decision_offered",
    },
    "CARD_10": {
        "entry_mode": "causal_stack",
        # Rograkh costs {0}: the commander spell needs no fuel.
        "fuel": [],
        "terminal": "scripted_decision_offered",
    },
    "CARD_22": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-mountain-p2",
                "card_identity": "Mountain",
                "owner": "P2",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
    "CARD_20": {
        "entry_mode": "causal_stack",
        "fuel": [
            {
                "semantic_id": "obj:fuel-swamp-p1-a",
                "card_identity": "Swamp",
                "owner": "P1",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-swamp-p1-b",
                "card_identity": "Swamp",
                "owner": "P1",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-swamp-p1-c",
                "card_identity": "Swamp",
                "owner": "P1",
                "zone": "battlefield",
            },
            {
                "semantic_id": "obj:fuel-swamp-p1-d",
                "card_identity": "Swamp",
                "owner": "P1",
                "zone": "battlefield",
            },
        ],
        "terminal": "scripted_decision_offered",
    },
}


def open_client(workspace: Path) -> ml.MidgameLaneClient:
    """Open one isolated mid-game session under the canonical launch plan.

    The plan supplies the exact classpath manifest, the engine identity and the
    shared runtime directory outside every candidate worktree; the client adds
    no launch model of its own.
    """
    plan = bridge_launcher.build_launch_plan("xmage", lane="midgame", xmage_workspace=workspace)
    return ml.MidgameLaneClient(plan.argv, plan.cwd, env_overrides=dict(plan.env_overrides))


def live_engine_pin() -> str:
    """The canonical XMage candidate identity from ``config/rules_engines.json``."""
    return bridge_launcher.canonical_xmage_engine_pin()


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
    """The engine's own seat label for a record seat id.

    The record's declarations use the lowercase ``p1``..``p6`` seat ids
    (``starting_player``), while the engine labels its seat offers
    ``Full Game Seat 1``..; the ``P``/``p`` prefix case is the only
    normalization, applied alike to both sides.
    """
    token = str(principal_id).strip()
    if token[:1].lower() == "p" and token[1:].isdigit():
        token = token[1:]
    return "Full Game Seat " + token


def record_starting_seat_index(record: dict[str, Any]) -> int | None:
    """The create-time starting seat from the record's own declaration, or None.

    The record's ``starting_player`` step/field wins; a turn-1 checkpoint's
    active player is the starter by CR 103.1 (the engine still performs that
    turn). A later checkpoint's active player is never converted into a starter
    by seat arithmetic: without a declaration the caller gets None and the
    bridge refuses creation rather than the Lab inventing a start.
    """
    seat, _source = midgame_starting_seat(record)
    return SEATS.index(seat) if seat is not None else None


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


def _arrival_at_checkpoint(
    probe: dict[str, Any], target_turn: int, target_phase: str, target_step: str
) -> bool:
    """Whether the arrival readback stands exactly at the record's temporal point.

    The declared turn is part of the point: turn 1's precombat main is not the
    turn-2 checkpoint, and an arrival that stopped there would report the wrong
    state. A readback without a readable turn never matches.
    """
    turn = probe.get("turn_number")
    if not isinstance(turn, int) or isinstance(turn, bool):
        return False
    return (
        turn == target_turn
        and str(probe.get("phase")) == target_phase
        and str(probe.get("step")) == target_step
    )


def drive_arrival(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    declare: Callable[[dict[str, Any], str], bool] | None = None,
    answer_scripted: Callable[[dict[str, Any], str, str, dict[str, Any]], bool] | None = None,
) -> ml.RowVerdict | None:
    """Drive the engine to the record's own temporal checkpoint.

    Every step is an external pilot answer selected from the engine's own
    offered options. The function answers nothing on the pilot's behalf and
    fails closed on a decision class it does not recognise.

    ``declare`` answers a combat declaration from the record's own requested
    combat and reports whether the request determined it. A declaration before
    the checkpoint that it does not determine fails closed; at the checkpoint
    step, a determined declaration is answered (the checkpoint is the priority
    after it) and an undetermined one is the checkpoint itself (the record's
    script declares). At the checkpoint step, priority is
    passed until the record's requested priority player holds it (the record's
    policy scripts exactly the passes needed to reach its declared checkpoint);
    the step never ends on the way.

    ``answer_scripted`` answers a record-scripted decision that the engine asks
    during the arrival (a turn-1 cleanup discard, CR 514.1), from the record's
    own selection. It is tried only when no setup option matches, and it fails
    closed itself on a wrong actor, a missing name, a count mismatch or an
    unscripted extra frame; the probe never picks a card for a player.
    """
    temporal = record["temporal_state"]
    target_phase, target_step = engine_temporal_point(
        str(temporal["phase"]), str(temporal["step"]), str(record["fixture_id"])
    )
    target_turn = temporal.get("turn_number")
    if not isinstance(target_turn, int) or isinstance(target_turn, bool):
        raise ml.MidgameLaneError("the record declares no readable turn for its checkpoint")
    # The setup frame (the starting-player choice) is answered for the seat the
    # record declares as the starter, never for a later checkpoint's active
    # player: at turn 2 those are different seats.
    starter_seat, _starter_source = midgame_starting_seat(record)
    active_label = seat_label(starter_seat or str(temporal["active_player"]))
    wanted_priority = str(temporal.get("priority_player") or "")
    reached_checkpoint_step = False

    script = list(record.get("decision_script") or ())
    first_family = str(script[0].get("decision_family")) if script else None

    for _ in range(120):
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class not in {"priority", "declare_attacker", "declare_blocker"} and (
            decision_class == first_family
        ):
            # The record's own first scripted decision (e.g. ordering the
            # simultaneous upkeep triggers) is asked before any priority in the
            # checkpoint step. It is the checkpoint only if the engine is at the
            # record's temporal point; otherwise it is an unrecognised decision.
            probe = client.complete_arrival().get("observation") or {}
            if _arrival_at_checkpoint(probe, target_turn, target_phase, target_step):
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            if str(probe.get("phase")) != "UNINITIALIZED":
                raise ml.MidgameLaneError(
                    f"the engine asked {decision_class} at {probe.get('phase')}/"
                    f"{probe.get('step')}, not at the record's {target_phase}/{target_step} "
                    "checkpoint"
                )
            # Before the game starts the same class is a setup frame (the
            # starting player), answered below like any other setup frame.
        if decision_class == "mulligan":
            keep = option_of_type(decision, "keep")
            if keep is None:
                raise ml.MidgameLaneError("the engine offered no keep option for the mulligan")
            client.submit_options(decision, [keep])
        elif decision_class in {"choice", "choose_object"}:
            chosen = option_by_label_suffix(decision, active_label)
            if chosen is None and answer_scripted is not None:
                legal = legal_actions(client)
                principal = decision_principal(decision, legal)
                if answer_scripted(decision, decision_class, principal, legal):
                    continue
            if chosen is None:
                raise ml.MidgameLaneError(
                    f"the engine offered no option for the record's starting principal {active_label}"
                )
            client.submit_options(decision, [chosen])
        elif decision_class == "priority":
            probe = client.complete_arrival().get("observation") or {}
            at_checkpoint = _arrival_at_checkpoint(probe, target_turn, target_phase, target_step)
            if reached_checkpoint_step and not at_checkpoint:
                raise ml.MidgameLaneError(
                    f"the checkpoint step {target_phase}/{target_step} ended before "
                    f"{wanted_priority} held priority"
                )
            if at_checkpoint and (
                declare is None
                or not wanted_priority
                or str(probe.get("priority_player")) == wanted_priority
            ):
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            reached_checkpoint_step = reached_checkpoint_step or at_checkpoint
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError("the engine offered no pass-priority option")
            client.submit_options(decision, [passed])
        elif decision_class in {"declare_attacker", "declare_blocker"}:
            # A declaration checkpoint: the engine has reached the record's
            # temporal point. Stop and let the caller decide whether to
            # execute the obligation.
            probe = client.complete_arrival().get("observation") or {}
            at_checkpoint = _arrival_at_checkpoint(probe, target_turn, target_phase, target_step)
            if (
                declare is not None
                and (
                    at_checkpoint
                    or (
                        int(probe.get("turn_number") or 0) == target_turn
                        and _checkpoint_follows(str(probe.get("step")), target_step)
                    )
                )
                and declare(decision, decision_class)
            ):
                reached_checkpoint_step = reached_checkpoint_step or at_checkpoint
                continue
            if at_checkpoint:
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


# The turn's steps in order (CR 500.1), by the engine's own step names.
_TURN_STEP_ORDER = (
    "UNTAP",
    "UPKEEP",
    "DRAW",
    "PRECOMBAT_MAIN",
    "BEGIN_COMBAT",
    "DECLARE_ATTACKERS",
    "DECLARE_BLOCKERS",
    "FIRST_COMBAT_DAMAGE",
    "COMBAT_DAMAGE",
    "END_COMBAT",
    "POSTCOMBAT_MAIN",
    "END_TURN",
    "CLEANUP",
)


def _checkpoint_follows(current_step: str, target_step: str) -> bool:
    """Whether the checkpoint step comes after the engine's current step this turn."""
    if current_step not in _TURN_STEP_ORDER or target_step not in _TURN_STEP_ORDER:
        return False
    return _TURN_STEP_ORDER.index(target_step) > _TURN_STEP_ORDER.index(current_step)


def probe_row(workspace: Path, fixture_id: str) -> dict[str, Any]:
    record = ml.frozen_record(MATERIALIZATION, fixture_id)
    game_id = f"probe-{fixture_id}"
    request = {
        "game_id": game_id,
        "plan_id": game_id,
        "seed": SEED,
        "requested_starting_state": record,
    }
    # The record's own starting-seat declaration is the create-time choosing
    # seat; without one the bridge refuses the creation instead of defaulting
    # to seat 0 (#572). A later checkpoint's active player is never turned
    # into a starter by seat arithmetic.
    starting_seat_index = record_starting_seat_index(record)
    if starting_seat_index is not None:
        request["starting_player_seat"] = starting_seat_index
    started = time.time()
    with open_client(workspace) as client:
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
            # One mapping decides what this failure means. A timeout, protocol
            # violation or transport failure becomes TRANSPORT_FAILURE with no
            # reachability credit; only an explicitly recognized obligation case
            # becomes ENGINE_STATE_ACCEPTED, which is still not a pass. Any
            # non-lane exception propagates rather than being converted.
            verdict, outcome = ml.failure_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                exc,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {
                "outcome": outcome,
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
    numeric_choice: int | None = None,
    selected_option_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Submit one engine-offered action; a numeric answer only where the frame asks one.

    ``selected_option_ids`` is set only for a multi-select frame the engine
    authored with more than one required selection: every id in it is an engine
    offer of the same pending decision, and ``legal_action_id`` stays one of
    them. The bridge validates membership and the frame's own cardinality, so a
    selection can never smuggle an option the engine did not offer.
    """
    choices: dict[str, Any] = {"ordering": []}
    if numeric_choice is not None:
        choices["numeric_choice"] = numeric_choice
    if selected_option_ids is not None:
        choices["selected_option_ids"] = list(selected_option_ids)
    proposal = {
        "proposal_id": proposal_id,
        "actor_id": legal["actor_id"],
        "legal_action_id": action["action_id"],
        "action_type": action["action_type"],
        "target_ids": [],
        "selected_modes": [],
        "choices": choices,
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


def normalize_words(text: str) -> list[str]:
    import re

    return [w for w in re.sub(r"[^a-z ]", "", text.lower()).split() if w]


def is_subsequence(needles: list[str], haystack: list[str]) -> bool:
    cursor = 0
    for needle in needles:
        while cursor < len(haystack) and haystack[cursor] != needle:
            cursor += 1
        if cursor >= len(haystack):
            return False
        cursor += 1
    return True


def answer_mode(
    client: ml.MidgameLaneClient,
    tag: str,
    mode_token: str,
) -> None:
    """Select the engine-offered mode matching the frame's mode token.

    The frame names a mode by its rules token (e.g.
    put_creature_on_bottom_of_owners_library); the engine offers labels
    (e.g. "put target creature on the bottom of its owner's library.").
    The token's words must appear in order in exactly one offered label.
    Zero or multiple matches fail closed rather than guessing.
    """
    wanted = normalize_words(mode_token.replace("_", " "))
    for _ in range(10):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal seeking the mode")
        if str(decision.get("decision_class")) != "mode":
            raise ml.MidgameLaneError(
                f"{tag}: expected a mode decision, observed {decision.get('decision_class')}"
            )
        matches: list[str] = []
        for option in decision.get("legal_options") or ():
            if is_subsequence(wanted, normalize_words(str(option.get("label") or ""))):
                matches.append(str(option.get("option_id")))
        if len(matches) != 1:
            raise ml.MidgameLaneError(
                f"{tag}: expected exactly one mode matching {mode_token}, observed {len(matches)}"
            )
        client.submit_options(decision, matches)
        return
    raise ml.MidgameLaneError(f"{tag}: the mode was never offered")


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
    for _ in range(60):
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
        # Spend pool mana the engine marks as advancing the payment. The
        # engine withdraws spent mana from later offers, so a repeated color
        # across polls is fresh mana, not a repeat.
        spend = None
        for action in legal.get("actions") or ():
            metadata = action.get("metadata") or {}
            if metadata.get("option_type") != "mana_pool":
                continue
            engine = metadata.get("xmage_option_metadata") or {}
            advances = (
                "advances_payment" not in engine
                or engine.get("advances_payment") is None
                or bool(engine.get("advances_payment"))
            )
            if advances:
                spend = action
                break
        if spend is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no advancing pool spend")
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
        for mode in frame.get("modes") or ():
            answer_mode(client, f"{frame_tag}-mode", str(mode))
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
        # The persisted evidence carries the public count only. The engine's
        # raw principal ids are opaque handles to private seats and must never
        # enter a principal-facing artifact.
        "principals_observed": len(distinct),
        "passes_observed": len(actors),
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


def drive_placement_obligation(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    """Execute a placement row's scripted obligation through the lane.

    The starting state is placed (not causally reconstructed); the pilot then
    drives the engine through the record's own decision script — declarations,
    blocks, damage steps, turn progressions — selecting only engine-offered
    options. Used for rows whose requested state needs no stack but whose
    obligation needs gameplay.
    """
    terminal_kind = str(spec.get("terminal"))
    drive_to_precombat_main(client, record)
    if terminal_kind == "blocker_partition":
        terminal = execute_block_partition(client, fixture_id, record)
    elif terminal_kind == "damage_doubled_to_six":
        terminal = execute_damage_observation(client, fixture_id, record)
    elif terminal_kind == "extra_turns_in_order":
        terminal = execute_turn_sequence(client, fixture_id, record)
    else:
        raise ml.MidgameLaneError(f"unknown placement terminal: {terminal_kind}")
    # A placement row is placed, not causally reconstructed, so no engine
    # causal_match exists for it. The engine verdict this path actually has is
    # the measured terminal obligation, and the row says exactly that instead of
    # asserting a causal match the engine never reported.
    row_verdict = ml.classification_from_placement_obligation(
        fixture_id,
        ml.MIDGAME_LANE,
        terminal,
        engine_commit=client.engine_commit,
    )
    return row_verdict.as_dict()


def execute_block_partition(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    """Declare a2->P2 and a3->P3, then have P2 block a2 with the Bear.

    Routes attackers by engine-offered defender labels and records native
    attacker identities for the partition proof. Holds all other attackers.
    """
    script = record.get("decision_script") or []
    block_step = next((s for s in script if s.get("decision_family") == "declare_blocker"), None)
    if block_step is None:
        raise ml.MidgameLaneError(f"{fixture_id}: the record names no block step")
    # The record's combat_state names the obligated attacks.
    combat = record.get("combat_state") or {}
    obligated = dict(combat.get("attackers") or {})
    defender_by_attacker: dict[str, str] = {}
    remaining = set(obligated.values())
    for _ in range(60):
        if not remaining:
            break
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{fixture_id}: terminal while declaring")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError(f"{fixture_id}: no pass offered")
            client.submit_options(decision, [passed])
            continue
        if decision_class != "declare_attacker":
            break
        answered = False
        for option in decision.get("legal_options") or ():
            if option.get("option_type") != "declare_attacker":
                continue
            label = str(option.get("label") or "")
            for defender_principal in obligated.values():
                seat = seat_label(str(defender_principal))
                if label.endswith("attacks " + seat) and defender_principal in remaining:
                    client.submit_options(decision, [str(option.get("option_id"))])
                    # Record the native attacker behind this declaration from
                    # the option metadata for the partition proof.
                    metadata = option.get("metadata") or {}
                    native_id = str(metadata.get("object_id") or "")
                    if native_id:
                        defender_by_attacker[native_id] = seat
                    remaining.remove(defender_principal)
                    answered = True
                    break
            if answered:
                break
        if not answered:
            held = option_of_type(decision, "hold_attacker")
            if held is None:
                raise ml.MidgameLaneError(f"{fixture_id}: no hold offered")
            client.submit_options(decision, [held])
    if remaining:
        raise ml.MidgameLaneError(
            f"{fixture_id}: obligated attacks never declared: {sorted(remaining)}"
        )
    # Hold the rest so the engine reaches blockers.
    for _ in range(20):
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                break
            client.submit_options(decision, [passed])
            continue
        if decision_class != "declare_attacker":
            break
        held = option_of_type(decision, "hold_attacker")
        if held is None:
            break
        client.submit_options(decision, [held])
    # P2 blocks. Route by seat; identify the Bear by the engine prompt.
    p2_attackers = {nid for nid, seat in defender_by_attacker.items() if "Seat 2" in seat}
    other_attackers = set(defender_by_attacker) - p2_attackers
    for _ in range(60):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{fixture_id}: terminal seeking the block")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError(f"{fixture_id}: no pass offered")
            client.submit_options(decision, [passed])
            continue
        if decision_class != "declare_blocker":
            break
        if int(decision.get("seat") or -1) != 1:
            submit_empty_block(client, f"probe-{fixture_id}")
            continue
        prompt = str(decision.get("prompt") or "")
        if "Runeclaw Bear" not in prompt:
            submit_empty_block(client, f"probe-{fixture_id}")
            continue
        legal = legal_actions(client)
        offered: set[str] = set()
        bear_offer: dict[str, Any] | None = None
        for action in legal.get("actions") or ():
            metadata = action.get("metadata") or {}
            if metadata.get("option_type") != "declare_blocker":
                continue
            engine = metadata.get("xmage_option_metadata") or {}
            attacker_id = str(engine.get("attacker_id") or "")
            if attacker_id:
                offered.add(attacker_id)
                bear_offer = action
        if not (p2_attackers & offered):
            raise ml.MidgameLaneError(f"{fixture_id}: P2 was never offered its obligated attacker")
        if other_attackers & offered:
            raise ml.MidgameLaneError(
                f"{fixture_id}: P2 was offered an attacker it does not defend "
                f"(CR 802.4a partition violated)"
            )
        if bear_offer is None:
            raise ml.MidgameLaneError(f"{fixture_id}: no block action offered")
        submit_proposal(client, legal, bear_offer, f"probe-{fixture_id}-block")
        return {
            "kind": "blocker_partition",
            "observed": True,
            "detail": f"P2 blocked exactly its obligated attacker; "
            f"{len(other_attackers)} non-defended attacker(s) correctly absent",
        }
    raise ml.MidgameLaneError(f"{fixture_id}: P2 never executed the block")


def submit_empty_block(client: ml.MidgameLaneClient, tag: str) -> None:
    legal = legal_actions(client)
    proposal = {
        "proposal_id": f"{tag}-noblock",
        "actor_id": legal["actor_id"],
        "legal_action_id": None,
        "action_type": "structural_decision",
        "target_ids": [],
        "selected_modes": [],
        "choices": {"ordering": []},
        "decision_tier": 1,
        "policy_name": "midgame-causal-external-pilot",
    }
    response = client.request("submit_action", {"proposal": proposal})
    if not response.get("success"):
        raise ml.MidgameLaneError(f"{tag}: empty block rejected")


def execute_damage_observation(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    """Declare the Giant at P2, walk to combat damage, read P2's life."""
    before = arrival_life(client, "P2")
    giant_declared = False
    for _ in range(60):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{fixture_id}: terminal while declaring")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError(f"{fixture_id}: no pass offered")
            client.submit_options(decision, [passed])
            continue
        if decision_class != "declare_attacker":
            break
        answered = False
        for option in decision.get("legal_options") or ():
            if option.get("option_type") != "declare_attacker":
                continue
            label = str(option.get("label") or "")
            if label.startswith("Hill Giant") and label.endswith("attacks Full Game Seat 2"):
                client.submit_options(decision, [str(option.get("option_id"))])
                giant_declared = True
                answered = True
                break
        if not answered:
            held = option_of_type(decision, "hold_attacker")
            if held is None:
                raise ml.MidgameLaneError(f"{fixture_id}: no hold offered")
            client.submit_options(decision, [held])
        if giant_declared:
            break
    if not giant_declared:
        raise ml.MidgameLaneError(f"{fixture_id}: the Hill Giant never attacked P2")
    for _ in range(20):
        decision = client.pending_decision()
        if decision is None:
            break
        if str(decision.get("decision_class")) != "declare_attacker":
            break
        held = option_of_type(decision, "hold_attacker")
        if held is None:
            break
        client.submit_options(decision, [held])
    for _ in range(80):
        observation = client.complete_arrival().get("observation") or {}
        if observation.get("step") == "COMBAT_DAMAGE":
            after = arrival_life(client, "P2")
            return {
                "kind": "damage_doubled_to_six",
                "observed": after == before - 6,
                "detail": f"P2 life moved {before} -> {after} (doubled 3 to 6)"
                if after == before - 6
                else f"P2 life moved {before} -> {after}, expected {before - 6}",
            }
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                break
            client.submit_options(decision, [passed])
            continue
        if decision_class == "declare_blocker":
            submit_empty_block(client, f"probe-{fixture_id}")
            continue
        if decision_class == "declare_attacker":
            held = option_of_type(decision, "hold_attacker")
            if held is None:
                break
            client.submit_options(decision, [held])
            continue
        break
    raise ml.MidgameLaneError(f"{fixture_id}: combat damage never arrived")


def arrival_life(client: ml.MidgameLaneClient, principal_id: str) -> int:
    observation = client.complete_arrival().get("observation") or {}
    for seat in observation.get("seats") or ():
        if seat.get("player_id") == principal_id:
            return int(seat.get("life"))
    raise ml.MidgameLaneError(f"the engine names no seat {principal_id}")


def execute_turn_sequence(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    """Drive forward recording active players; extra turns would repeat one."""
    active_sequence: list[str] = []
    last_active = ""
    for _step in range(400):
        observation = client.complete_arrival().get("observation") or {}
        active = str(observation.get("active_player") or "")
        if active and active != last_active:
            active_sequence.append(active)
            last_active = active
        if len(active_sequence) >= 7:
            break
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class == "priority":
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                break
            client.submit_options(decision, [passed])
            continue
        if decision_class == "declare_attacker":
            held = option_of_type(decision, "hold_attacker")
            if held is None:
                break
            client.submit_options(decision, [held])
            continue
        if decision_class == "declare_blocker":
            submit_empty_block(client, f"probe-{fixture_id}")
            continue
        if decision_class == "mulligan":
            kept = option_of_type(decision, "keep")
            if kept is None:
                break
            client.submit_options(decision, [kept])
            continue
        if decision_class == "choose_object":
            # Cleanup discard: discard a declared scaffolding filler (a basic
            # land) by identity. This is an external discretionary choice among
            # the engine's own offered options, and it cannot create an extra
            # turn. When no declared filler is offered the probe fails the row
            # closed instead of silently taking the engine's first option: a
            # first-option fallback would be an internal policy substitute for
            # the external decision, which this lane forbids.
            options = decision.get("legal_options") or []
            choice = None
            for option in options:
                label = str(option.get("label") or "")
                if any(
                    land in label
                    for land in ("Mountain", "Plains", "Island", "Swamp", "Forest", "Wastes")
                ):
                    choice = str(option.get("option_id"))
                    break
            if choice is None:
                break
            client.submit_options(decision, [choice])
            continue
        break
    for index in range(1, len(active_sequence)):
        if active_sequence[index] == active_sequence[index - 1]:
            return {
                "kind": "extra_turns_in_order",
                "observed": False,
                "detail": f"unexpected consecutive repeat without a causal extra turn; "
                f"sequence={active_sequence}",
            }
    return {
        "kind": "extra_turns_in_order",
        "observed": False,
        "detail": f"normal rotation with no extra turn; sequence={active_sequence}. "
        f"Reaching the obligated P3-then-P2 extra turns needs the placed "
        f"graveyard spells cast from hand for real (a causal-cast entry the "
        f"lane does not have).",
    }


def drive_to_precombat_main(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
) -> None:
    """Drive the engine to the record's declared precombat-main priority.

    Placement rows with later checkpoints (declare_blockers, combat_damage)
    must be arrived at their own precombat main; their own obligation execution
    advances from there through the engine's combat steps. The declared turn is
    part of the stop: turn 1's precombat main is not a turn-2 checkpoint.
    Answering only arrival transport (mulligan, choosing-pick, priority passes)
    and failing closed on anything else.
    """
    temporal = record.get("temporal_state") or {}
    target_turn = temporal.get("turn_number")
    if not isinstance(target_turn, int) or isinstance(target_turn, bool):
        raise ml.MidgameLaneError("the record declares no readable turn for its checkpoint")
    starter_seat, _starter_source = midgame_starting_seat(record)
    active_label = seat_label(starter_seat or str(temporal.get("active_player") or "P1"))
    for _ in range(120):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError("the engine went terminal before precombat main")
        decision_class = str(decision.get("decision_class"))
        if decision_class == "mulligan":
            kept = option_of_type(decision, "keep")
            if kept is None:
                raise ml.MidgameLaneError("the engine offered no keep option")
            client.submit_options(decision, [kept])
        elif decision_class in {"choice", "choose_object"}:
            chosen = option_by_label_suffix(decision, active_label)
            if chosen is None:
                raise ml.MidgameLaneError(f"the engine offered no option for {active_label}")
            client.submit_options(decision, [chosen])
        elif decision_class == "priority":
            observation = client.complete_arrival().get("observation") or {}
            if (
                observation.get("turn_number") == target_turn
                and observation.get("phase") == "PRECOMBAT_MAIN"
                and observation.get("step") == "PRECOMBAT_MAIN"
            ):
                return
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError("the engine offered no pass")
            client.submit_options(decision, [passed])
        else:
            raise ml.MidgameLaneError(f"unexpected {decision_class} during arrival transport")
    raise ml.MidgameLaneError("the engine never reached precombat main")


def probe_causal_row(
    workspace: Path,
    fixture_id: str,
    spec: dict[str, object],
) -> dict[str, Any]:
    record = ml.frozen_record(MATERIALIZATION, fixture_id)
    game_id = f"probe-causal-{fixture_id}"
    entry_mode = str(spec["entry_mode"])
    started = time.time()
    with open_client(workspace) as client:
        client.request("get_provider_version", None)
        client.read_dimension_manifest()
        request: dict[str, Any] = {
            "game_id": game_id,
            "plan_id": game_id,
            "seed": SEED,
            "entry_mode": entry_mode,
            "requested_starting_state": record,
        }
        # The record's own starting-seat declaration is the create-time
        # choosing seat; a record without one omits the field and the bridge
        # refuses creation instead of defaulting to seat 0 (#572). A later
        # checkpoint's active player is never turned into a starter.
        starting_seat_index = record_starting_seat_index(record)
        if starting_seat_index is not None:
            request["starting_player_seat"] = starting_seat_index
        if entry_mode in ("causal_stack", CAUSAL_STACK_ELIMINATION):
            request["fuel"] = list(spec.get("fuel") or [])
        if entry_mode in ("causal_elimination", CAUSAL_STACK_ELIMINATION):
            request["elimination"] = elimination_request(spec)
        if spec.get("caused_permanents"):
            request["caused_permanents"] = list(spec["caused_permanents"])  # type: ignore[call-overload]
        created = client.request("create_midgame_game", request)
        if not created.get("success"):
            errors = created.get("errors") or []
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=errors[0].get("code") if errors else None,
                detail=errors[0].get("message") if errors else None,
                engine_commit=client.engine_commit,
                entry_mode=entry_mode,
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
                entry_mode=entry_mode,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        try:
            if entry_mode == "causal_stack":
                row = drive_causal_stack(client, fixture_id, record, payload, spec)
            elif entry_mode == "causal_elimination":
                row = drive_causal_elimination(client, fixture_id, record, payload, spec)
            elif entry_mode == CAUSAL_STACK_ELIMINATION:
                row = drive_causal_stack_elimination(client, fixture_id, record, payload, spec)
            else:
                row = drive_placement_obligation(client, fixture_id, record, payload, spec)
        except ml.MidgameLaneError as exc:
            verdict, outcome = ml.failure_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                exc,
                engine_commit=client.engine_commit,
                entry_mode=entry_mode,
                obligation_code="CAUSAL_OBLIGATION_NOT_EXECUTED",
                transport_code="CAUSAL_LANE_TRANSPORT_FAILURE",
                protocol_code="CAUSAL_LANE_PROTOCOL_VIOLATION",
                timeout_code="CAUSAL_LANE_TIMEOUT",
            )
            return verdict.as_dict() | {
                "outcome": outcome,
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
    withheld = ml.causal_credit_gate(
        fixture_id,
        "causal_stack",
        drive_arrival(client, record),
        engine_commit=client.engine_commit,
    )
    if withheld is not None:
        return withheld
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
    elif terminal_kind == "scripted_decision_offered":
        terminal = observe_scripted_decision(client, f"probe-{fixture_id}", record, placed)
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


def decision_principal(decision: dict[str, Any], legal: dict[str, Any]) -> str:
    """The requested-state principal (P1..PN) the engine asks, from its seat index."""
    seat = decision.get("seat")
    if not isinstance(seat, int):
        actions = legal.get("actions") or ()
        metadata = (actions[0].get("metadata") or {}) if actions else {}
        seat = metadata.get("seat")
    if not isinstance(seat, int) or isinstance(seat, bool):
        raise ml.MidgameLaneError("the pending decision names no seat")
    return f"P{seat + 1}"


def scripted_value_offered(
    legal: dict[str, Any],
    family: str,
    value: Any,
    placed: dict[str, str],
) -> tuple[bool, str]:
    """Whether the scripted selection is among the engine's own offers.

    Exactly one offer must match; zero or several are not a match, as the
    decision script's FAIL_CLOSED selection contract requires.
    """
    actions = list(legal.get("actions") or ())
    if family == "choose_object" and isinstance(value, str):
        native = placed.get(value)
        if native is None:
            return False, f"{value} has no placed native id"
        found = find_native_offer(legal, native) is not None
        return found, f"{value} offered={found}"
    if family == "choice" and isinstance(value, str):
        labels = [str((a.get("metadata") or {}).get("label") or "") for a in actions]
        matches = [label for label in labels if label.strip().lower() == value.lower()]
        return len(matches) == 1, f"{value} matched {len(matches)} of {labels}"
    if isinstance(value, bool):
        matches = [
            a
            for a in actions
            if ((a.get("metadata") or {}).get("xmage_option_metadata") or {}).get("value") is value
        ]
        return len(matches) == 1, f"boolean {value} matched {len(matches)}"
    return False, f"selector for {family} not evaluated by this probe"


def observe_scripted_decision(
    client: ml.MidgameLaneClient,
    tag: str,
    record: dict[str, Any],
    placed: dict[str, str],
) -> dict[str, Any]:
    """After the causal stack, the row's first scripted decision must be offered.

    Priority is passed only through engine-offered passes, never by the
    scripted actor when the scripted decision is itself a priority action.
    The family must equal the engine's decision class exactly; a different
    class is reported, not aliased.
    """
    script = record.get("decision_script") or []
    if not script:
        raise ml.MidgameLaneError(f"{tag}: the record scripts no decision")
    step = script[0]
    actor = str(step.get("actor"))
    family = str(step.get("decision_family"))
    value = (step.get("selection") or {}).get("semantic_value")
    trace: list[str] = []
    for _ in range(40):
        decision = client.pending_decision(attempts=5)
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        legal = legal_actions(client)
        principal = decision_principal(decision, legal)
        trace.append(f"{decision_class}:{principal}")
        if decision_class == "priority" and family == "priority" and principal == actor:
            wanted = str((value or {}).get("object")) if isinstance(value, dict) else ""
            native = placed.get(wanted)
            offered = native is not None and find_source_cast(legal, native) is not None
            return {
                "kind": "scripted_decision_offered",
                "observed": offered,
                "detail": f"{actor} holds priority; cast of {wanted} offered={offered}; "
                f"trace={trace}",
            }
        if decision_class != "priority":
            matched, why = scripted_value_offered(legal, family, value, placed)
            observed = decision_class == family and principal == actor and matched
            return {
                "kind": "scripted_decision_offered",
                "observed": observed,
                "detail": f"scripted {family}:{actor}, engine asked {decision_class}:"
                f"{principal}; {why}; trace={trace}",
            }
        passed = option_of_type(decision, "pass_priority")
        if passed is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
        client.submit_options(decision, [passed])
    return {
        "kind": "scripted_decision_offered",
        "observed": False,
        "detail": f"the scripted {family} for {actor} was never asked; trace={trace}",
    }


def graveyard_count(client: ml.MidgameLaneClient, record: dict[str, Any]) -> int:
    decision = client.pending_decision()
    if decision is None:
        raise ml.MidgameLaneError("the engine went terminal reading zone counts")
    state = client.zone_counts(str(decision.get("actor_id")))
    seats = (state.get("zone_counts") or {}).get("seats") or []
    return sum(int(seat.get("graveyard_count") or 0) for seat in seats)


def elimination_request(spec: dict[str, object]) -> dict[str, Any]:
    """The declared instruments of a causal elimination: one Lightning Bolt in
    the actor's hand and one Mountain on the actor's battlefield per bolt. They
    are placed through the engine seam and published in the plan payload."""
    instruments: list[dict[str, str]] = []
    actor = str(spec["elimination_actor"])
    for index in range(int(spec.get("bolt_count") or 0)):
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
    return {
        "actor": actor,
        "victim": str(spec["elimination_victim"]),
        "instruments": instruments,
    }


def elimination_instrument_ids(plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The engine's native ids of the plan's declared bolts and mountains.

    Only the declared instruments count, bound by the engine's own native ids:
    the record's other objects (a Bolt or a Mountain of the victim's) are never
    instruments, whatever they are called.
    """
    instruments = [entry for entry in plan.get("instruments") or () if isinstance(entry, dict)]
    bolts = sorted(
        str(entry["native_id"])
        for entry in instruments
        if entry.get("card_identity") == "Lightning Bolt" and entry.get("zone") == "hand"
    )
    mountains = sorted(
        str(entry["native_id"])
        for entry in instruments
        if entry.get("card_identity") == "Mountain" and entry.get("zone") == "battlefield"
    )
    return bolts, mountains


def eliminate_causally(
    client: ml.MidgameLaneClient,
    tag: str,
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    """Cast every declared bolt at the victim through the engine; the engine's
    own elimination verdict afterwards. Every answer is an engine offer; the
    engine alone deals the damage and applies the state-based loss."""
    bolt_ids, mountain_ids = elimination_instrument_ids(created.get("elimination_plan") or {})
    victim_seat = seat_label(str(spec["elimination_victim"]))
    bolt_count = int(spec.get("bolt_count") or 0)
    if len(bolt_ids) != bolt_count or len(mountain_ids) != bolt_count:
        raise ml.MidgameLaneError(
            f"{tag}: the plan placed {len(bolt_ids)} bolts and {len(mountain_ids)} "
            f"mountains for {bolt_count} declared"
        )
    expected_life: int | None = None
    for index in range(bolt_count):
        cast_frame_source(client, f"{tag}-cast-{index}", bolt_ids[index])
        answer_player_target(client, f"{tag}-target-{index}", victim_seat)
        answer_fuel_mana(client, f"{tag}-mana-{index}", mountain_ids)
        expected_life = resolve_until_life_drops(
            client,
            f"{tag}-resolve-{index}",
            str(spec["elimination_victim"]),
            expected_life,
        )
    return complete_causal(client, "elimination").get("verdict") or {}


def build_and_eliminate(
    client: ml.MidgameLaneClient,
    tag: str,
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    """The composed route: cast the victim's stack, verify it, then eliminate.

    Returns both engine verdicts. The elimination starts only after the stack
    verifier confirmed the requested stack, so the victim's spell is provably on
    the stack when the engine applies the loss.
    """
    causal_plan = created.get("causal_plan") or {}
    placed = {str(k): str(v) for k, v in (causal_plan.get("placed_objects") or {}).items()}
    declared_fuel = [str(card["semantic_id"]) for card in spec.get("fuel") or ()]  # type: ignore[union-attr,index]
    fuel = [placed[semantic] for semantic in declared_fuel if semantic in placed]
    if len(fuel) != len(declared_fuel):
        raise ml.MidgameLaneError(f"{tag}: a declared fuel card was not placed")
    causal_stack_frames(client, f"{tag}-stack", causal_plan, placed, fuel)
    stack_verdict = complete_causal(client, "stack").get("verdict") or {}
    if not stack_verdict.get("causal_match") or stack_verdict.get("mismatches"):
        return {"stack": stack_verdict, "permanents": None, "elimination": None}
    permanents: dict[str, Any] | None = None
    if spec.get("caused_permanents"):
        # The caused permanents exist only once their casts resolve: the engine
        # resolves the stack, and the verifier compares attachment and control
        # with the record before anything else happens.
        resolve_stack(client, f"{tag}-resolve")
        permanents = complete_causal(client, "permanents").get("verdict") or {}
        if not permanents.get("causal_match") or permanents.get("mismatches"):
            return {"stack": stack_verdict, "permanents": permanents, "elimination": None}
    elimination = eliminate_causally(client, f"{tag}-elimination", created, spec)
    return {"stack": stack_verdict, "permanents": permanents, "elimination": elimination}


def resolve_stack(client: ml.MidgameLaneClient, tag: str, limit: int = 30) -> None:
    """Pass priority until the engine's own stack is empty at a priority frame.

    Only priority passes are submitted; any other decision while resolving is
    not something this route answers, so it fails closed.
    """
    for _ in range(limit):
        decision = client.pending_decision()
        if decision is None:
            raise ml.MidgameLaneError(f"{tag}: the engine went terminal while resolving")
        if str(decision.get("decision_class")) != "priority":
            raise ml.MidgameLaneError(
                f"{tag}: unexpected {decision.get('decision_class')} while resolving"
            )
        stack = (decision.get("pilot_state") or {}).get("stack")
        if not isinstance(stack, list):
            raise ml.MidgameLaneError(f"{tag}: the engine's priority frame exposes no stack")
        if not stack:
            return
        passed = option_of_type(decision, "pass_priority")
        if passed is None:
            raise ml.MidgameLaneError(f"{tag}: the engine offered no pass")
        client.submit_options(decision, [passed])
    raise ml.MidgameLaneError(f"{tag}: the stack never emptied")


def drive_causal_stack_elimination(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    withheld = ml.causal_credit_gate(
        fixture_id,
        CAUSAL_STACK_ELIMINATION,
        drive_arrival(client, record),
        engine_commit=client.engine_commit,
    )
    if withheld is not None:
        return withheld
    verdicts = build_and_eliminate(client, f"probe-{fixture_id}", created, spec)
    stack = verdicts["stack"]
    elimination = verdicts["elimination"] or {}
    # The obligation, not only the elimination: the victim left (lost and
    # left), the engine's own stack is empty at the next decision, and no
    # survivor's life moved from the record's request (the victim's spells
    # never resolved).
    eliminated = elimination.get("victim_lost") is True and elimination.get("victim_left") is True
    # The next decision is read only after an elimination ran: a stack mismatch
    # keeps its exact diagnosis instead of waiting on a decision.
    decision = client.pending_decision() if verdicts["elimination"] is not None else None
    pilot_stack = ((decision or {}).get("pilot_state") or {}).get("stack")
    stack_empty = isinstance(pilot_stack, list) and not pilot_stack
    requested_life = {
        str(player.get("player_id")): player.get("life")
        for player in record.get("players") or ()
        if player.get("player_id") != spec.get("elimination_victim")
    }
    life_totals = elimination.get("life_totals") or {}
    survivors_untouched = bool(requested_life) and all(
        life_totals.get(pid) == life for pid, life in requested_life.items()
    )
    permanents = verdicts.get("permanents")
    permanents_ok = permanents is None or (
        bool(permanents.get("causal_match")) and not permanents.get("mismatches")
    )
    observed = (
        verdicts["elimination"] is not None
        and eliminated
        and stack_empty
        and survivors_untouched
        and permanents_ok
    )
    terminal = {
        "kind": str(spec.get("terminal")),
        "observed": observed,
        "stack_match": bool(stack.get("causal_match")) and not stack.get("mismatches"),
        "victim_lost": elimination.get("victim_lost") is True,
        "victim_left": elimination.get("victim_left") is True,
        "stack_empty_after_loss": stack_empty,
        "survivors_at_requested_life": survivors_untouched,
        "detail": (
            (
                "the engine caused the record's permanents at its checkpoint, then "
                "eliminated their controller"
                if permanents is not None
                else "the engine built the victim's stack, eliminated the victim, and "
                "the victim's spells left without resolving"
            )
            if observed
            else f"stack={stack} elimination={verdicts['elimination']} "
            f"stack_after={pilot_stack} life={life_totals} requested={requested_life}"
        ),
    }
    if verdicts["elimination"] is not None:
        combined = dict(elimination)
    elif permanents is not None:
        # The caused permanents did not match: that verdict is the row's.
        combined = dict(permanents)
    else:
        combined = dict(stack)
    combined["stack_verdict"] = stack
    if permanents is not None:
        combined["permanents_verdict"] = permanents
    if permanents is not None:
        terminal["caused_permanents"] = permanents
    row_verdict = ml.classification_from_causal_verdict(
        fixture_id,
        ml.MIDGAME_LANE,
        CAUSAL_STACK_ELIMINATION,
        combined,
        terminal,
        engine_commit=client.engine_commit,
    )
    return row_verdict.as_dict()


def drive_causal_elimination(
    client: ml.MidgameLaneClient,
    fixture_id: str,
    record: dict[str, Any],
    created: dict[str, Any],
    spec: dict[str, object],
) -> dict[str, Any]:
    withheld = ml.causal_credit_gate(
        fixture_id,
        "causal_elimination",
        drive_arrival(client, record),
        engine_commit=client.engine_commit,
    )
    if withheld is not None:
        return withheld
    verdict = eliminate_causally(client, f"probe-{fixture_id}", created, spec)
    victim_lost = verdict.get("victim_lost") is True
    victim_left = verdict.get("victim_left") is True
    eliminated = victim_lost or victim_left
    # The terminal obligation is the engine's own elimination verdict, recorded
    # explicitly. It is never inferred from the row's requested terminal.
    terminal = {
        "kind": "victim_eliminated_by_engine",
        "observed": eliminated,
        "victim_lost": victim_lost,
        "victim_left": victim_left,
        "detail": (
            "the engine reported the victim lost/left the game"
            if eliminated
            else "the engine did not report the victim as lost or left"
        ),
    }
    row_verdict = ml.classification_from_causal_verdict(
        fixture_id,
        ml.MIDGAME_LANE,
        "causal_elimination",
        verdict,
        terminal,
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

    # Bind the executing Lab runner before any engine process starts. A dirty
    # tree cannot issue runtime evidence: an artifact that names one commit
    # while other bytes executed is a false provenance claim.
    runner = receipt_mod.capture_runner_identity(REPO_ROOT)
    receipt_mod.require_clean_runner(runner)

    classpath_file = args.workspace / "target" / "cp-wsr22.txt"
    if not classpath_file.is_file():
        print(
            f"missing {classpath_file}; build the bridge module and regenerate the classpath "
            f"manifest first",
            file=sys.stderr,
        )
        return 2

    manifest_payload: dict[str, Any] | None = None
    engine_commit: str | None = None
    engine_artifact: dict[str, Any] | None = None
    try:
        with open_client(args.workspace) as client:
            client.request("get_provider_version", None)
            manifest = client.read_dimension_manifest()
            manifest_payload = manifest.as_dict()
            engine_commit = client.engine_commit
            engine_artifact = client.engine_artifact
    except bridge_launcher.BridgeLaunchError as exc:
        print(f"the mid-game lane could not be launched: {exc}", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    for fixture_id in args.rows:
        if fixture_id in CAUSAL_ROWS:
            rows.append(probe_causal_row(args.workspace, fixture_id, CAUSAL_ROWS[fixture_id]))
        else:
            rows.append(probe_row(args.workspace, fixture_id))

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
    unrecognized = [
        row["fixture_id"] for row in rows if row["outcome"] == "UNRECOGNIZED_CONSTRUCTION_VERDICT"
    ]
    transport_failed = [
        {"fixture_id": row["fixture_id"], "code": row["code"]}
        for row in rows
        if row["outcome"] == "TRANSPORT_FAILURE"
    ]
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
        "engine_artifact_kind": (engine_artifact or {}).get("kind"),
        "engine_artifact_path": (engine_artifact or {}).get("path"),
        "engine_artifact_sha256": (engine_artifact or {}).get("sha256"),
        "engine_artifact_size": (engine_artifact or {}).get("size"),
        "candidate_commit": live_engine_pin(),
        "lane": ml.MIDGAME_LANE,
        "protocol_version": ml.PROTOCOL_VERSION,
        "seed": SEED,
        "runner_commit": runner.commit,
        "runner_tree": runner.tree,
        "runner_digest": runner.digest(),
        "runner": runner.to_document(),
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
            "unrecognized_construction_verdict": len(unrecognized),
            "transport_failure": len(transport_failed),
            "engine_rejected": len(rejected),
        },
        "engine_native_reachable": reachable,
        "engine_state_accepted_obligation_not_executed": accepted_only,
        "causal_route_reachable": causal_reachable,
        "causal_route_measured_blocked": causal_measured,
        "construction_mismatch": mismatched,
        "unrecognized_construction_verdict": unrecognized,
        "transport_failure": transport_failed,
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
            "UNRECOGNIZED_CONSTRUCTION_VERDICT means the engine's construction verdict could not "
            "be interpreted (a negative verdict with a missing, empty or unrecognized mismatch "
            "list, a self-contradictory positive verdict, or a non-boolean flag). It earns no "
            "reachability credit.",
            "TRANSPORT_FAILURE means the lane's transport, child process or protocol failed, so no "
            "engine verdict exists at all. It is never reported as an accepted engine state. "
            "A stalled child is terminated and reaped and classified as a timeout here.",
            "This probe is technical capability evidence. It is not provider selection and does "
            "not establish Architecture Freeze.",
            "The receipt binds the executing Lab runner (commit, tree, digest of every executed "
            "runner/adapter input) and the engine commit the provider reported. A receipt whose "
            "runner or engine identity does not match the assembling head is stale and earns "
            "zero runtime credit; it is never grandfathered.",
        ],
    }
    if receipt["engine_commit"] != receipt["candidate_commit"]:
        # The provider must report the engine candidate the manifest pins. A
        # different engine executed, so the rows describe an identity this
        # evidence cannot claim; the run refuses to seal a mismatched receipt.
        print(
            f"engine identity mismatch: provider reported {receipt['engine_commit']!r}, "
            f"canonical candidate is {receipt['candidate_commit']!r}",
            file=sys.stderr,
        )
        return 3
    if (
        receipt["engine_artifact_kind"] != "file"
        or not isinstance(receipt["engine_artifact_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["engine_artifact_sha256"])
    ):
        # The declared commit is a constant; without the loaded artifact's
        # digest this receipt cannot claim which engine bytes produced it.
        print(
            "engine artifact identity unavailable: "
            f"kind={receipt['engine_artifact_kind']!r} "
            f"sha256={receipt['engine_artifact_sha256']!r}",
            file=sys.stderr,
        )
        return 3
    receipt["receipt_digest"] = receipt_mod.document_digest(receipt)
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
                "unrecognized_construction_verdict": unrecognized,
                "transport_failure": transport_failed,
                "engine_rejected": rejected,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
