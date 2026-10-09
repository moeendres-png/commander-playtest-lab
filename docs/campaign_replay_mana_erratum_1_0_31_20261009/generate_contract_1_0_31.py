"""Generate FULL107 successor contract 1.0.31 from 1.0.30: the actual-card
campaign arrival histories and the remaining record-bound mana declarations
(#634 step B data, Owner-accepted engine strategy, ADR #647).

Two lane registries were not enumerated by errata 1.0.28-1.0.30:

* the actual-card campaign (``actual_card_campaign.derive_corpus``): 22 of its 29
  CARD records declared no game-start history, so the strict arrival refused
  them since #625 (AF07 UNKNOWN on PB-03 runs 37888112605 and 37914716200);
* the replay twin's and the campaign's mana payments: their executors pay from
  the record's ``action_cost_state`` sources, which step B (#645) only accepts
  through a scripted ``mana_payment`` step (PB-03 run 37920050254).

Rulings applied (Coordinator, #634):

1. Arrival history (1.0.28 shape) for the 22 CARD records without it: one keep
   per seat and one arrival ``priority_pass_through`` (actor ALL) from turn 1's
   beginning to the record's checkpoint, until exclusive (CR 103.5, 117.3d).
2. Obligation pass-through (1.0.30 shape, symbolic OBLIGATION_COMPLETE bound,
   SCRIPTED_STEPS_FIRST) where a record has none.
3. Mana declarations for every cost whose payment the executor makes, bound to
   the record's own ``explicit_payment_sources``, placed where the pinned engine
   asks for the payment (CR 601.2g-h). The 1.0.30 default (after the cast's
   whole target/mode/amount sub-sequence) holds unless the record's later steps
   are answered after payment; those rows carry their measured position in
   ``TAIL_BEFORE_PAYMENT`` (resolution-time choices such as Dig Through Time's
   look-and-choose, or a fused/split cast that is paid before its targets).
   ``mana`` lists the colours actually spent: the basic-land colour of each
   tapped source in order, a source's own declared ``activate_mana`` colour, or
   the explicit ``MANA_SPENT`` entry where the cost is smaller than the declared
   source list (CARD_23: {3}{B} from four Mountains and a Swamp).

Measured locally on the pinned XMage engine with the #645 step-B lane before
generation (LOCAL_OBSERVED, not credit): all 29 campaign rows DIRECT_PASS.

The 1.0.31 diff against 1.0.30 is exactly the per-record ``decision_script``
additions above plus the version/accounting fields, the authority pointer and
the errata ledger. Obligation keys and requested states are unchanged; the
107-row denominator is untouched and no runtime credit is claimed.

Idempotent: always regenerated from the 1.0.30 bytes.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO / "scripts"))
import resolve_pre_freeze_contract as resolver  # noqa: E402

PRE = REPO / "qualification/pre-freeze-successor"
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_30.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_31.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.30-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_31.json"
NEW_VERSION = "1.0.31"
NEW_MINOR = "31"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_DECLARED_PASSES_AND_MANA"

# The union of every arrival-using lane registry, the denominator of ruling 1:
# midgame_rows.ROWS (74) + knowledge_projection.ROWS (20) +
# midgame_replay_twin.ROWS (5) + the six causal-only records of
# run_midgame_capability_probe.CAUSAL_ROWS (CARD_07/10/13/16/20/22) =
# 105 distinct records. The coverage test enumerates the registries themselves
# and asserts this set is exactly the records they execute.
# Every record this erratum changes: the 22 campaign records without history
# and every record whose executor pays mana without a declaration.
OBLIGATION_FIXTURES = (
    "CARD_01",
    "CARD_03",
    "CARD_04",
    "CARD_05",
    "CARD_06",
    "CARD_08",
    "CARD_09",
    "CARD_10",
    "CARD_11",
    "CARD_12",
    "CARD_14",
    "CARD_15",
    "CARD_17",
    "CARD_18",
    "CARD_19",
    "CARD_21",
    "CARD_22",
    "CARD_23",
    "CARD_24",
    "CARD_25",
    "CARD_26",
    "CARD_27",
    "CARD_28",
    "CARD_29",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
)

# The 22 actual-card campaign records the 1.0.28-1.0.30 coverage omitted: the
# campaign registry (actual_card_campaign.derive_corpus) was never enumerated,
# so they declared no game-start history and the strict arrival refused them.
ARRIVAL_FIXTURES = (
    "CARD_01",
    "CARD_03",
    "CARD_04",
    "CARD_05",
    "CARD_06",
    "CARD_08",
    "CARD_09",
    "CARD_11",
    "CARD_12",
    "CARD_14",
    "CARD_15",
    "CARD_17",
    "CARD_18",
    "CARD_19",
    "CARD_21",
    "CARD_23",
    "CARD_24",
    "CARD_25",
    "CARD_26",
    "CARD_27",
    "CARD_28",
    "CARD_29",
)

# The causal-stack and elimination rows (ruling 3): scope.from is the causal
# preparation start, turn 1's beginning, so the declaration also covers the
# construction/causal passes of the probe helpers. The three ``placement``
# causal entries (WS05-MP-TURN-5, WS05-MP-BLOCK-4, MICRO_REPLACEMENT) are not
# causal preparation and keep the checkpoint as their scope start.
CAUSAL_FIXTURES: tuple[str, ...] = ()

# The RowSpec records whose executor pays mana from the Lab's mana_sources list
# (midgame_rows.py's mana-payment branch) and whose record therefore needs the
# mana declaration: every row of ROWS with a non-empty RowSpec.mana_sources
# except the seven that already declare their payment sources in a
# mana_payment step (PILOT_CHOOSE_USE, PILOT_PILE, NEGATIVE_DEFAULT_YES_NO,
# WS05-MP-TURN-3, WS05-MP-TURN-5) or that are covered below by completing the
# existing step (MICRO_MANA_PAYMENT, PILOT_MANA_PAYMENT).
MANA_FIXTURES = (
    "CARD_01",
    "CARD_03",
    "CARD_05",
    "CARD_06",
    "CARD_08",
    "CARD_09",
    "CARD_10",
    "CARD_11",
    "CARD_12",
    "CARD_14",
    "CARD_15",
    "CARD_17",
    "CARD_18",
    "CARD_22",
    "CARD_23",
    "CARD_24",
    "CARD_25",
    "CARD_26",
    "CARD_27",
    "CARD_28",
    "CARD_29",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
)
# The six obligation records whose obligation is observed before the engine
# asks for payment: a typed refusal of a casting choice (the four
# NEGATIVE_* records) or the divided-amount announcement (CR 601.2d, the two
# PILOT_*_AMOUNT records) completes the row inside casting, before costs are
# paid (CR 601.2g-h). The engine never asks these rows for mana, so a payment
# declaration would be a step no engine frame answers and would keep the row
# from its natural stop (PB-03 run 37888112605: zero mana frames on each, the
# ff688b58 epoch identically). They declare no payment; a later frame asking
# for mana stays undeclared and fails closed.
MANA_NOT_REACHED: tuple[str, ...] = ()
# The records whose scripted steps after the cast belong to a later object,
# not to the cast: MICRO_TRIGGERS's target step answers the creature's
# enters-the-battlefield trigger (CR 603.3d), which the engine asks after the
# spell was paid for (CR 601.2g-h) and resolved. The payment declaration sits
# directly after the cast step, in the engine's own order.
# The number of the cast's own target/mode/amount steps that the pinned engine
# asks before the payment, where it differs from "all of them" (measured on
# the pinned engine with the step-B lane; the remaining steps are answered after
# payment: resolution-time choices, or targets of a fused split card).
TAIL_BEFORE_PAYMENT = {
    "CARD_11": 0,
    "CARD_12": 0,
    "CARD_15": 1,
    "CARD_22": 1,
    "CARD_24": 0,
    "CARD_25": 1,
    "CARD_27": 0,
    "CARD_28": 0,
    "CARD_29": 0,
}
# The colours actually spent, per payment in script order, where the cost is
# smaller than the declared source list or a source is not a basic land.
MANA_SPENT = {
    "CARD_23": (("R", "R", "R", "B"), ("R",)),
    "CARD_27": (("R", "R"),),
}

# The two records with a pre-existing mana_payment step that declares no
# sources: the record's own action_cost_state already binds them, so the step
# gains the missing ``sources`` key and no new step is inserted.
MANA_SOURCE_COMPLETIONS: tuple[str, ...] = ()

# Ruling 5 (2026-10-09, step A2): the knowledge-projection records whose
# obligation window reaches the active player's declare-attackers step. The
# knowledge lane's transport runs the record's script past its own steps (the
# obligation pass-through keeps passing priority through the checkpoint turn),
# so the active player's attack declaration is a decision the record must make:
# an explicit empty attack set (CR 508.1: the active player declares; 508.8:
# a creature that did not attack is not declared). The set is bound to the
# checkpoint turn's active player and the engine's DECLARE_ATTACKERS step.
KNOWLEDGE_ATTACK_FIXTURES: tuple[str, ...] = ()

DECISIONS = (
    "#634 Coordinator ruling 2026-10-09 (contract 1.0.31): the actual-card "
    "campaign's records declare their game-start history and obligation "
    "pass-through like every other arrival-using lane, and every record whose "
    "executor pays mana (campaign and replay twin) declares the payment as "
    "mana_payment step(s) bound to its own action_cost_state sources, at the "
    "point the engine asks for it (CR 103.5, 117.3d, 601.2g-h). No Lab default, "
    "first-option or positional choice answers an engine frame in step B"
)
FORBIDDEN = [
    "first_option",
    "random_option",
    "default_yes_no",
    "internal_ai",
    "gui_default",
    "silent_skip",
    "parent_class_fallback",
]
KNOWN_RUNTIME_BLOCKER = (
    "NO_RUNTIME_CREDIT_CLAIMED_BY_THIS_MATERIALIZATION: every Lab-answered pass "
    "and mana pick is now declared in decision_script (obligation pass-through "
    "scopes, causal preparation scopes, record-bound mana sources), so step B can "
    "refuse anything undeclared. The row still requires exact-head runtime "
    "requalification after the Lab transport follows these declarations; this "
    "erratum only adds the declarations and claims no runtime behavior"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #634 declared obligation pass-throughs "
        "and record-bound mana payment declarations for every arrival-using lane"
    ),
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_OBLIGATION_KEYS_UNTOUCHED",
    "predecessor_non_requested_digests": "HISTORICAL_PROVENANCE_ONLY",
    "successor_non_requested_digest_policy": (
        "REMOVE_STALE_VALUES_AND_PRESERVE_UNDER_historical_digests"
    ),
}
# The arrival transport's own checkpoint vocabulary, reproduced so a record
# whose temporal point the transport cannot address is refused here instead of
# silently mis-scoped.
ENGINE_STEP_BY_POINT = {
    ("beginning", "upkeep"): "UPKEEP",
    ("beginning", "draw"): "DRAW",
    ("precombat_main", "main"): "PRECOMBAT_MAIN",
    ("combat", "declare_attackers"): "DECLARE_ATTACKERS",
    ("combat", "declare_blockers"): "DECLARE_BLOCKERS",
    ("combat", "combat_damage"): "COMBAT_DAMAGE",
    ("postcombat_main", "main"): "POSTCOMBAT_MAIN",
}
# The engine's own turn order, so a checkpoint's position relative to the
# declare-attackers step is decided here rather than guessed: a knowledge
# record's obligation window includes that step exactly when its checkpoint
# starts at or before it in the same turn (ruling 5).
_ENGINE_POINT_ORDER = (
    ("beginning", "upkeep"),
    ("beginning", "draw"),
    ("precombat_main", "main"),
    ("combat", "declare_attackers"),
    ("combat", "declare_blockers"),
    ("combat", "combat_damage"),
    ("postcombat_main", "main"),
)
_DECLARE_ATTACKERS_POINT = ("combat", "declare_attackers")
# The record's own pre-checkpoint transport steps; every other family is the
# caller's obligation and must not appear before the checkpoint.
_ARRIVAL_PREFIX_FAMILIES = ("mulligan", "priority_pass_through")
# The decision families that immediately follow a cast step and are part of
# that cast's own decision sub-sequence: the mana declaration is inserted after
# them, exactly where the existing payment steps sit.
_CAST_TAIL_FAMILIES = (
    "target",
    "choose_mode",
    "announce_x",
    "multi_amount",
    "target_amount",
    "choose_object",
    "choice",
)
_BASIC_LAND_COLORS = {
    "Island": "U",
    "Mountain": "R",
    "Swamp": "B",
    "Forest": "G",
    "Plains": "W",
}

raw = src.read_bytes()
contract = json.loads(raw)
authority = json.loads((REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text())
base = {
    r["fixture_id"]: r
    for r in json.loads(
        (REPO / authority["full107"]["historical_base_materialization"]).read_text()
    )["records"]
}
existing = {p["fixture_id"]: p for p in contract["record_successors"]}
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert contract["contract_id"] == PRIOR_CONTRACT
assert len(denominator) == 107
assert len(OBLIGATION_FIXTURES) == len(set(OBLIGATION_FIXTURES)) == 29
assert set(ARRIVAL_FIXTURES) <= set(OBLIGATION_FIXTURES)
assert set(CAUSAL_FIXTURES) <= set(OBLIGATION_FIXTURES)
assert set(MANA_FIXTURES) <= set(OBLIGATION_FIXTURES)
assert set(MANA_SOURCE_COMPLETIONS) <= set(MANA_FIXTURES)
assert not set(MANA_NOT_REACHED) & set(MANA_FIXTURES)
assert set(MANA_NOT_REACHED) <= set(OBLIGATION_FIXTURES)
assert set(TAIL_BEFORE_PAYMENT) <= set(MANA_FIXTURES)
assert set(MANA_SPENT) <= set(MANA_FIXTURES)
for fixture_id in OBLIGATION_FIXTURES:
    # The six causal-only CARD records are executed by the probe lane but live
    # outside the 107-row provider denominator; their declaration still needs
    # the historical base to overlay.
    assert fixture_id in base, fixture_id


def mulligan_step(seat: str) -> dict:
    return {
        "actor": seat,
        "causal_step_id": f"mull-r1-{seat}",
        "decision_family": "mulligan",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            f"CR 103.5: {seat} keeps its opening hand; which hand is kept is the "
            "player's own choice, declared here so the Lab only transports it and never "
            "defaults to a keep"
        ),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "keep_opening_hand",
        },
    }


def arrival_priority_step(fixture_id: str, temporal: dict) -> dict:
    until = {
        "turn": temporal["turn_number"],
        "phase": str(temporal["phase"]).strip().lower(),
        "step": str(temporal["step"]).strip().lower(),
    }
    return {
        "actor": "ALL",
        "causal_step_id": f"priority-pass-r1-to-{fixture_id.lower()}-checkpoint",
        "decision_family": "priority_pass_through",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            f"CR 117.3d, 305.1: from game start to {fixture_id}'s declared checkpoint "
            "no player plays a land, casts or activates anything, so every priority "
            "decision in that scope is the record's declared pass-through and the Lab "
            "answers it PASS. A non-priority decision in scope that is not separately "
            "scripted fails closed; the record never lets the Lab answer for a player. "
            "The selector is the arrival transport's own semantic pass-priority shape "
            "(midgame_rows/probe) and the scope key carries the ruled temporal window"
        ),
        "scope": {
            "from": {"turn": 1, "phase": "beginning"},
            "until": until,
        },
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "pass_priority",
        },
    }


def obligation_priority_step(fixture_id: str, temporal: dict, causal: bool, until: dict) -> dict:
    start = (
        {"turn": 1, "phase": "beginning"}
        if causal
        else {
            "turn": temporal["turn_number"],
            "phase": str(temporal["phase"]).strip().lower(),
            "step": str(temporal["step"]).strip().lower(),
        }
    )
    origins = (
        "the causal preparation start (turn 1's beginning) so the construction and "
        "causal passes of the probe helpers are covered"
        if causal
        else "the record's own checkpoint, inclusive"
    )
    return {
        "actor": "ALL",
        "causal_step_id": f"priority-pass-obligation-{fixture_id.lower()}",
        "decision_family": "priority_pass_through",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            f"CR 117.3d: from {origins} to the lane's own obligation completion "
            "point (declared symbolically as the event OBLIGATION_COMPLETE), any "
            "priority frame that no explicitly scripted step of this record answers is "
            "passed by the player holding priority (the midgame lane's obligation loop "
            "and the probe's causal helpers). Scripted steps take precedence: this "
            "declaration only authorizes the pass, it never consumes an obligation, "
            "never drives execution forward and never extends a row past its natural "
            "stop (the #643 regression repair ruling)"
        ),
        "precedence": "SCRIPTED_STEPS_FIRST",
        "scope": {"from": start, "until": until},
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "pass_priority",
        },
    }


def declare_attackers_step(fixture_id: str, temporal: dict) -> dict:
    """Ruling 5: the active player's explicit empty attack set for the
    checkpoint turn (CR 508.1, 508.8).

    The knowledge lane's transport runs the record's script through the
    obligation pass-through window, which reaches the declare-attackers step.
    The record declares that no creature attacks: the set is bound to the
    checkpoint turn's active player and the engine's own DECLARE_ATTACKERS
    step, so the transport answers each of the engine's attack frames with its
    hold offer (the arrival pilot's own declaration shape).
    """
    turn = temporal["turn_number"]
    return {
        "actor": str(temporal["active_player"]),
        "causal_step_id": f"declare-attackers-r{turn}-{str(temporal['active_player']).lower()}",
        "decision_family": "declare_attackers",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            "CR 508.1, 508.8: the active player declares its attackers; this "
            "record declares that no creature attacks during its obligation "
            "window, so the Lab answers each engine declare-attacker frame "
            "with the engine's own hold offer and never chooses an attacker "
            "for the player. The step is bound to the declared turn and the "
            f"{fixture_id} checkpoint's active player"
        ),
        "phase": "DECLARE_ATTACKERS",
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "attacker_assignment",
            "semantic_value": {},
        },
        "turn": turn,
    }


def mana_step(
    fixture_id: str, index: int, actor: str, sources: list[str], mana: list[str] | None
) -> dict:
    value: dict = {"sources": list(sources)}
    if mana is not None:
        value["mana"] = list(mana)
    return {
        "actor": actor,
        "causal_step_id": f"mana-payment-{fixture_id.lower()}-{index}",
        "decision_family": "mana_payment",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            "CR 601.2g-h: the record declares the exact permanents it pays with, in "
            "order, bound to its own semantic object identities (the record's "
            "action_cost_state declaration); the Lab takes mana only from this step "
            "and never from an executor-side registry or offer order"
        ),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "mana_payment",
            "semantic_value": value,
        },
    }


def effective_like(fixture_id: str) -> dict:
    """The 1.0.30 effective record, rebuilt from the base and the 1.0.30 patch."""
    record = copy.deepcopy(base[fixture_id])
    prior = existing.get(fixture_id)
    if prior is not None:
        for key, value in prior["replace"].items():
            record[key] = copy.deepcopy(value)
        record["knowledge_state"]["channel_policy"] = prior["knowledge_state_channel_policy"]
    return record


def is_keep_step(step: object, seat: str) -> bool:
    return (
        isinstance(step, dict)
        and step.get("decision_family") == "mulligan"
        and step.get("actor") == seat
        and (step.get("selection") or {}).get("selector_kind") == "semantic_action"
        and (step.get("selection") or {}).get("semantic_value") == "keep_opening_hand"
    )


def object_colors(record: dict) -> dict[str, str]:
    colors: dict[str, str] = {}
    for obj in record.get("semantic_objects") or ():
        if not isinstance(obj, dict):
            continue
        identity = obj.get("card_identity")
        if identity in _BASIC_LAND_COLORS:
            colors[str(obj.get("semantic_id"))] = _BASIC_LAND_COLORS[identity]
    return colors


patches: dict[str, dict] = {}
arrival_added: dict[str, bool] = {}
obligation_added: dict[str, bool] = {}
attack_added: dict[str, bool] = {}
mana_added: dict[str, list[str]] = {}
obligation_digests: dict[str, str] = {}

for fixture_id in OBLIGATION_FIXTURES:
    prior = existing.get(fixture_id)
    prior_replace = copy.deepcopy(prior["replace"]) if prior is not None else {}
    record = effective_like(fixture_id)
    assert isinstance(record.get("decision_script") or [], list), fixture_id
    script = copy.deepcopy(record.get("decision_script") or [])
    temporal = dict(record.get("temporal_state") or {})
    assert isinstance(temporal.get("turn_number"), int), fixture_id
    point = (
        str(temporal["phase"]).strip().lower(),
        str(temporal["step"]).strip().lower(),
    )
    if point not in ENGINE_STEP_BY_POINT:
        raise SystemExit(f"unpatchable: {fixture_id}: checkpoint {point} cannot be derived")
    seats = [str(p["player_id"]) for p in record["players"]]
    assert seats == [f"P{index + 1}" for index in range(len(seats))], (fixture_id, seats)
    causal = fixture_id in CAUSAL_FIXTURES

    # --- the record's own leading arrival-history prefix ----------------------- #
    prefix_end = 0
    while prefix_end < len(script) and (
        str(script[prefix_end].get("decision_family")) in _ARRIVAL_PREFIX_FAMILIES
    ):
        prefix_end += 1
    prefix = script[:prefix_end]
    tail = script[prefix_end:]

    # --- ruling 4: the 1.0.28-shape arrival history where it is missing -------- #
    new_prefix: list[dict] = []
    added_arrival = False
    if fixture_id in ARRIVAL_FIXTURES:
        for seat in seats:
            declared = next((step for step in prefix if is_keep_step(step, seat)), None)
            if declared is None:
                new_prefix.append(mulligan_step(seat))
                added_arrival = True
            else:
                new_prefix.append(copy.deepcopy(declared))
        declared_pass = next(
            (
                step
                for step in prefix
                if isinstance(step, dict) and step.get("decision_family") == "priority_pass_through"
            ),
            None,
        )
        if declared_pass is None:
            new_prefix.append(arrival_priority_step(fixture_id, temporal))
            added_arrival = True
        else:
            new_prefix.append(copy.deepcopy(declared_pass))
        seats_present = seats
    else:
        new_prefix = [copy.deepcopy(step) for step in prefix]
        seats_present = seats
    arrival_added[fixture_id] = added_arrival

    # --- ruling 2: the mana-payment declarations ------------------------------- #
    added_sources: list[str] = []
    if fixture_id in MANA_FIXTURES:
        costs = [
            cost
            for cost in record.get("action_cost_state") or ()
            if isinstance(cost, dict) and cost.get("explicit_payment_sources")
        ]
        assert costs, fixture_id
        colors = object_colors(record)
        # A source the record itself activates for mana declares its colour.
        for step in script:
            value = (
                (step.get("selection") or {}).get("semantic_value")
                if isinstance(step, dict)
                else None
            )
            if (
                isinstance(value, dict)
                and value.get("action") == "activate_mana"
                and value.get("color")
            ):
                colors[str(value.get("source"))] = str(value["color"])
        if fixture_id in MANA_SOURCE_COMPLETIONS:
            # The record's pre-existing mana_payment step gains the sources its
            # own action_cost_state already binds; no new step is inserted.
            mana_steps = [
                step
                for step in tail
                if isinstance(step, dict) and step.get("decision_family") == "mana_payment"
            ]
            assert len(mana_steps) == len(costs), (fixture_id, len(mana_steps), len(costs))
            for step, cost in zip(mana_steps, costs, strict=True):
                sources = [str(source) for source in cost["explicit_payment_sources"]]
                assert str(step.get("actor")) == str(cost.get("actor")), fixture_id
                assert all(source in colors for source in sources), (fixture_id, sources)
                assert (step.get("selection") or {}).get("selector_kind") == "mana_payment"
                step["selection"]["semantic_value"]["sources"] = sources
                added_sources.extend(sources)
        else:
            inserted: list[tuple[int, dict]] = []
            used: set[int] = set()
            for cost in costs:
                actor = str(cost.get("actor"))
                sources = [str(source) for source in cost["explicit_payment_sources"]]
                for source in sources:
                    if source not in colors:
                        raise SystemExit(
                            f"unpatchable: {fixture_id}: mana source {source} has no "
                            "record object with a declared basic-land color"
                        )
                if any(
                    isinstance(step, dict)
                    and step.get("decision_family") == "mana_payment"
                    and ((step.get("selection") or {}).get("semantic_value") or {}).get("sources")
                    == sources
                    for step in tail
                ):
                    # This payment is already declared (RNG_RULES_TAPE's Chaos Warp).
                    continue
                wanted = cost.get("source_semantic_id")
                if wanted:
                    # The cast of the named object pays the cost; an activated
                    # ability of it (Basilisk Collar's equip) only when the
                    # record casts nothing by that name.
                    for key in ("object", "source"):
                        candidates = [
                            index
                            for index, step in enumerate(tail)
                            if isinstance(step, dict)
                            and step.get("decision_family") == "priority"
                            and str(step.get("actor")) == actor
                            and (step.get("selection") or {}).get("semantic_value", {}).get(key)
                            == wanted
                            and index not in used
                        ]
                        if candidates:
                            break
                else:
                    # A commander cast declares no object id; the record's own
                    # action_cost_state order pairs each entry with the next
                    # unconsumed cast step of that actor (WS05-CMD-PARTNER-TAX
                    # casts both partners in script order).
                    candidates = [
                        index
                        for index, step in enumerate(tail)
                        if isinstance(step, dict)
                        and step.get("decision_family") == "priority"
                        and str(step.get("actor")) == actor
                        and str(
                            (step.get("selection") or {})
                            .get("semantic_value", {})
                            .get("action", "")
                        ).startswith("cast")
                        and index not in used
                    ]
                if len(candidates) > 1 and wanted:
                    raise SystemExit(
                        f"unpatchable: {fixture_id}: cast step for {wanted} is "
                        f"not unique ({candidates})"
                    )
                if not candidates:
                    raise SystemExit(
                        f"unpatchable: {fixture_id}: no cast step for {wanted or actor}"
                    )
                cast = candidates[0]
                insert_at = cast
                limit = TAIL_BEFORE_PAYMENT.get(fixture_id)
                taken = 0
                while (
                    (limit is None or taken < limit)
                    and insert_at + 1 < len(tail)
                    and isinstance(tail[insert_at + 1], dict)
                    and str(tail[insert_at + 1].get("decision_family")) in _CAST_TAIL_FAMILIES
                    and str(tail[insert_at + 1].get("actor")) == actor
                ):
                    insert_at += 1
                    taken += 1
                used.add(cast)
                inserted.append(
                    (
                        insert_at + 1,
                        mana_step(
                            fixture_id,
                            len(inserted),
                            actor,
                            sources,
                            list(MANA_SPENT[fixture_id][len(inserted)])
                            if fixture_id in MANA_SPENT
                            else [colors[source] for source in sources],
                        ),
                    )
                )
                added_sources.extend(sources)
            for offset, (insert_at, step) in enumerate(sorted(inserted, key=lambda item: item[0])):
                tail.insert(insert_at + offset, step)
    mana_added[fixture_id] = added_sources

    # --- ruling 1: the obligation-phase pass-through declaration --------------- #
    required = list((record.get("expected_events") or {}).get("required_events") or ())
    extra_turns = sum(1 for event in required if str(event).startswith("next_turn:"))
    # The scope's ``until`` is the lane's own obligation completion point,
    # declared symbolically: the pass-through authorizes passes on frames no
    # scripted step answers, and it never drives execution forward or extends
    # a row past its natural stop (#643 regression repair ruling).
    obligation_step = obligation_priority_step(
        fixture_id, temporal, causal, {"event": "OBLIGATION_COMPLETE"}
    )
    # --- ruling 5: the knowledge lane's declared empty attack set ------------ #
    attack_step: dict | None = None
    if fixture_id in KNOWLEDGE_ATTACK_FIXTURES:
        # The knowledge lane's transport runs the obligation window through the
        # checkpoint turn's combat, so the checkpoint turn is the only turn the
        # declaration has to cover (no knowledge record declares an extra turn).
        assert extra_turns == 0, fixture_id
        assert point in _ENGINE_POINT_ORDER, (fixture_id, point)
        if _ENGINE_POINT_ORDER.index(point) <= _ENGINE_POINT_ORDER.index(_DECLARE_ATTACKERS_POINT):
            attack_step = declare_attackers_step(fixture_id, temporal)
    attack_added[fixture_id] = attack_step is not None
    if attack_step is not None:
        tail.append(attack_step)
    already = any(
        isinstance(step, dict)
        and step.get("decision_family") == "priority_pass_through"
        and (step.get("scope") or {}).get("until") == {"event": "OBLIGATION_COMPLETE"}
        for step in tail
    )
    if not already:
        tail.append(obligation_step)
    obligation_added[fixture_id] = not already

    new_script = [*new_prefix, *tail]
    merged_replace = {**prior_replace, "decision_script": new_script}
    corrected = copy.deepcopy(base[fixture_id])
    if prior is not None:
        for key, value in prior["replace"].items():
            corrected[key] = copy.deepcopy(value)
    for key, value in merged_replace.items():
        corrected[key] = copy.deepcopy(value)
    corrected["knowledge_state"]["channel_policy"] = (
        prior["knowledge_state_channel_policy"]
        if prior is not None
        else base[fixture_id]["knowledge_state"]["channel_policy"]
    )

    # The obligation is the 1.0.30 one, key for key: nothing it projects is touched.
    assert resolver.obligation_digest(corrected) == resolver.obligation_digest(record)
    obligation_digests[fixture_id] = resolver.obligation_digest(corrected)
    for untouched in ("expected_events", "terminal_postconditions", "negative_fallback_probe"):
        assert corrected.get(untouched) == record.get(untouched), untouched
    for untouched in ("temporal_state", "stack_state", "deck_state"):
        assert corrected.get(untouched) == record.get(untouched), untouched
    prior_digest = (
        prior["successor_requested_state_digest"]
        if prior is not None
        else base[fixture_id]["requested_state_digest"]
    )
    successor_digest = resolver.requested_state_digest(corrected)
    assert prior_digest == successor_digest, fixture_id

    field_changes = []
    if added_arrival:
        field_changes.append(
            {
                "change": (
                    "decision_script + pregame mulligan keeps and the arrival "
                    "priority_pass_through scope (1.0.28 shape)"
                ),
                "comprehensive_rules": "103.5, 117.3d",
                "reason": (
                    "the record is executed by run_midgame_capability_probe.CAUSAL_ROWS, "
                    "which the 1.0.28-1.0.30 coverage did not enumerate, so its "
                    "game-start arrival history was undeclared and the strict arrival "
                    "answered the keeps and priority with Lab defaults (#642 review "
                    "P2-2). The record now declares one pregame keep per seat present "
                    "in it and the arrival pass-through to its own checkpoint, until "
                    "exclusive"
                ),
            }
        )
    if not already:
        field_changes.append(
            {
                "change": (
                    "decision_script +1 obligation priority_pass_through scope (actor ALL, "
                    "precedence SCRIPTED_STEPS_FIRST) from "
                    + (
                        "the causal preparation start to the lane's own obligation "
                        "completion point (symbolic event OBLIGATION_COMPLETE)"
                        if causal
                        else "the record's checkpoint (inclusive) to the lane's own "
                        "obligation completion point (symbolic event OBLIGATION_COMPLETE)"
                    )
                ),
                "comprehensive_rules": "117.3d",
                "reason": (
                    "the midgame obligation loop passes any priority frame that no scripted "
                    "step answers (midgame_rows.py:5188-5201), and the probe's causal "
                    "helpers pass through construction; both were Lab choices made for the "
                    "player holding priority (#634 audit). The record now declares that "
                    "scope: scripted steps take precedence and every priority frame they do "
                    "not consume inside this window is passed (CR 117.3d), so step B can "
                    "refuse an undeclared pass"
                ),
            }
        )
    if added_sources:
        field_changes.append(
            {
                "change": (
                    "decision_script + mana_payment declaration(s) with "
                    f"{len(added_sources)} record-bound source identity/identities"
                ),
                "comprehensive_rules": "601.2g-h",
                "reason": (
                    "the executor's mana-payment branch taps the next source in the "
                    "Lab's RowSpec mana_sources order (midgame_rows.py:5255-5264), a "
                    "Lab choice (#634 audit). The record now declares the same sources, "
                    "bound to its own semantic object identities and in declared order "
                    "(its action_cost_state explicit_payment_sources), so step B can "
                    "take the payment from the record only"
                ),
            }
        )
    if attack_added[fixture_id]:
        field_changes.append(
            {
                "change": (
                    "decision_script +1 declare_attackers empty attack set (actor = "
                    "the checkpoint turn's active player, turn/phase bound)"
                ),
                "comprehensive_rules": "508.1, 508.8",
                "reason": (
                    "the knowledge lane's transport runs the record's script through "
                    "its obligation pass-through window, which reaches the active "
                    "player's declare-attackers step; the record now declares that no "
                    "creature attacks during the window (an explicit empty "
                    "attacker_assignment), so the engine's own hold offer answers each "
                    "declare-attacker frame and the lane never chooses attackers for "
                    "the player (CR 508.1, 508.8; #634 step A2)"
                ),
            }
        )
    erratum = {
        "actor": None,
        "details": {
            "authority": DECISIONS,
            "comprehensive_rules": "103.5, 117.3d, 508.1, 508.8, 601.2g-h",
            "erratum_class": CORRECTION_CLASS,
            "field_changes": copy.deepcopy(field_changes),
            "obligation_changed": False,
            "provider_semantics_used": False,
            "reason": (
                "#634 audit: the credited midgame path answered undeclared priority "
                "passes and RowSpec mana picks for players. This record now declares "
                "its obligation pass-through scope"
                + (", its game-start arrival history" if added_arrival else "")
                + (", its record-bound mana payment sources" if added_sources else "")
                + (
                    ", and its empty attack set for the obligation window's declare-attackers step"
                    if attack_added[fixture_id]
                    else ""
                )
                + " in decision_script, so the Lab transports exactly what the record "
                "declares and step B refuses anything undeclared. Obligation keys are "
                "untouched, the denominator is untouched and no runtime credit is claimed"
            ),
        },
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-declared-passes-mana-{fixture_id.lower()}",
    }
    if prior is not None:
        patch = {
            **copy.deepcopy(prior),
            "append_native_procedure": [
                *copy.deepcopy(prior["append_native_procedure"]),
                erratum,
            ],
            "authority_overlay": dict(OVERLAY),
            "correction_class": CORRECTION_CLASS,
            "digest_migration": {
                **DIGEST_MIGRATION,
                "reason": (
                    "the declared decision script gains the obligation pass-through "
                    "scope and, where applicable, the mana declarations; the requested "
                    "state and the obligation keys are byte for byte the predecessor's, "
                    "so both digests are unchanged and the historical materialization "
                    "digest is preserved under historical_digests"
                ),
            },
            "predecessor_invalidity": {
                "predecessor_values": {
                    "decision_script": copy.deepcopy(script),
                },
                "reason": (
                    "the 1.0.30 predecessor declared neither the obligation-phase "
                    "priority pass-through nor this record's mana sources, so the lane "
                    "answered those frames with Lab choices (#634 audit)"
                ),
            },
            "replace": merged_replace,
            "successor_requested_state_digest": successor_digest,
            "superseded_successor_patch": {
                # The predecessor's own superseded chain is carried nested under
                # its own key, so every class behind this record's lineage stays
                # reachable (the successor test walks the whole chain).
                **(
                    {
                        "superseded_successor_patch": copy.deepcopy(
                            prior["superseded_successor_patch"]
                        )
                    }
                    if prior.get("superseded_successor_patch") is not None
                    else {}
                ),
                "contract": PRIOR_CONTRACT,
                "correction_class": prior["correction_class"],
                "patch_sha256": hashlib.sha256(
                    resolver.canonical_json(prior).encode("utf-8")
                ).hexdigest(),
                "successor_requested_state_digest": prior["successor_requested_state_digest"],
                "append_native_procedure": copy.deepcopy(prior["append_native_procedure"]),
                "lineage": (
                    "its replace is kept and extended with the 1.0.31 decision-script "
                    "additions; its erratum steps are preserved here as history and are "
                    "not active procedure"
                ),
            },
        }
    else:
        patch = {
            "append_native_procedure": [erratum],
            "authority_overlay": dict(OVERLAY),
            "correction_class": CORRECTION_CLASS,
            "digest_migration": {
                **DIGEST_MIGRATION,
                "reason": (
                    "the record's declared decision script gains the arrival history, "
                    "the obligation pass-through scope and the mana declarations; the "
                    "requested state and the obligation keys are byte for byte the base "
                    "record's, so both digests are unchanged and the historical "
                    "materialization digest is preserved under historical_digests"
                ),
            },
            "evidence_survival": "REQUALIFICATION_REQUIRED",
            "fixture_id": fixture_id,
            "knowledge_state_channel_policy": base[fixture_id]["knowledge_state"]["channel_policy"],
            "predecessor_invalidity": {
                "predecessor_values": {"decision_script": copy.deepcopy(script)},
                "reason": (
                    "the base record declared no game-start arrival history and no "
                    "obligation pass-through or mana sources, so the lane answered "
                    "those frames with Lab choices (#634 audit / #642 review P2-2)"
                ),
            },
            "predecessor_requested_state_digest": base[fixture_id]["requested_state_digest"],
            "replace": merged_replace,
            "successor_requested_state_digest": successor_digest,
        }
    assert resolver.requested_state_digest(corrected) == patch["successor_requested_state_digest"]
    assert prior_digest == patch["successor_requested_state_digest"], fixture_id
    patches[fixture_id] = patch

# --- assemble the 1.0.31 contract --------------------------------------------- #

replaced = [patches.get(p["fixture_id"], p) for p in contract["record_successors"]]
assert [p["fixture_id"] for p in replaced] == [
    p["fixture_id"] for p in contract["record_successors"]
]
new_patches = [
    patches[fixture_id] for fixture_id in OBLIGATION_FIXTURES if fixture_id not in existing
]
assert len(new_patches) == sum(
    1 for fixture_id in OBLIGATION_FIXTURES if fixture_id not in existing
)
contract["record_successors"] = [*replaced, *new_patches]

accounting = contract["change_accounting"]
for fixture_id in OBLIGATION_FIXTURES:
    if fixture_id not in accounting["changed_fixture_ids"]:
        accounting["changed_fixture_ids"].append(fixture_id)
    accounting["per_fixture_correction_class"][fixture_id] = CORRECTION_CLASS
accounting["change_class"] = "MIXED_FIXTURE_CONTRACT_ERRATA_AND_RULES_AUTHORITY_CORRECTION"
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.31 carries "
    "every 1.0.30 record successor and the bounded-secondary PLAYER_COUNT_6P section "
    "byte for byte, and adds the 1.0.28-shape arrival history and the obligation "
    "pass-through to the 22 actual-card campaign records that lacked them, and the "
    "record-bound mana_payment declarations for every campaign and replay-twin "
    "payment (CR 103.5, 117.3d, 601.2g-h). The obligation keys and the 107-row "
    "denominator are untouched and no runtime credit is claimed. Per #634 "
    "Coordinator ruling 2026-10-09."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_30.json",
    "record_count": len(contract["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.30 overlay to the same 1.0.5 historical base and adds the 22 campaign "
        "arrival histories and obligation pass-throughs and the campaign and "
        "replay-twin mana declarations, with the obligation keys unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.31 ------------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_30_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.30", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.30", NEW_VERSION)
# The 1.0.31 declarations reuse the 1.0.30 declared shapes exactly (the mulligan
# keep step, the ALL-actor priority pass-through with its scope, the
# mana_payment step with its declared sources and the fail-closed selections);
# the one addition is the step-level precedence token the obligation
# pass-through carries.
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
new_materialization = f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
if new_materialization not in enum:
    enum.append(new_materialization)
schema["properties"]["contract_id"]["const"] = f"commander-lab.full107/{NEW_VERSION}-successor"
schema["properties"]["schema_version"]["const"] = new_materialization
schema["$defs"]["decision"]["properties"]["precedence"] = {"enum": ["SCRIPTED_STEPS_FIRST"]}
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / f"SEMANTIC_FIXTURE_SCHEMA_v1_0_{NEW_MINOR}_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

# --- authority pointer --------------------------------------------------------- #

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = SUCCESSOR_PATH
full["effective_materialization_schema"] = (
    f"qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_{NEW_MINOR}_SUCCESSOR.json"
)
for fixture_id in OBLIGATION_FIXTURES:
    if fixture_id not in full["changed_fixture_ids"]:
        full["changed_fixture_ids"].append(fixture_id)
    full["evidence_survival"][fixture_id] = "REQUALIFICATION_REQUIRED_" + CORRECTION_CLASS
full["unchanged_fixture_count"] = sum(
    1 for fixture_id in denominator if fixture_id not in full["changed_fixture_ids"]
)
assert len(full["changed_fixture_ids"]) == len(set(full["changed_fixture_ids"]))
assert full["denominator_count"] == 107
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- errata ledger entries ----------------------------------------------------- #

lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
ledger["records"] = [r for r in ledger["records"] if r["fixture_id"] not in OBLIGATION_FIXTURES]
new_entries = []
for fixture_id in OBLIGATION_FIXTURES:
    patch = patches[fixture_id]
    prior = existing.get(fixture_id)
    new_entries.append(
        dict(
            sorted(
                {
                    "correction_class": CORRECTION_CLASS,
                    "denominator_effect": "NONE",
                    "effective_obligation_digest": obligation_digests[fixture_id],
                    "effective_requested_state_digest": patch["successor_requested_state_digest"],
                    "evidence_survival": "REQUALIFICATION_REQUIRED",
                    "field_changes": copy.deepcopy(
                        patch["append_native_procedure"][-1]["details"]["field_changes"]
                    ),
                    "fixture_id": fixture_id,
                    "known_runtime_blocker": KNOWN_RUNTIME_BLOCKER,
                    "notes": (
                        "#634 Coordinator ruling 2026-10-09: every Lab default the "
                        "credited midgame/knowledge/replay/probe path answered for a "
                        "player is now a record declaration -- the obligation "
                        "pass-through scope"
                        + (", the missing arrival history" if arrival_added[fixture_id] else "")
                        + (
                            f", {len(mana_added[fixture_id])} record-bound mana source(s)"
                            if mana_added[fixture_id]
                            else ""
                        )
                        + (
                            ", and the knowledge window's explicit empty attack set "
                            "(CR 508.1, 508.8)"
                            if attack_added[fixture_id]
                            else ""
                        )
                        + ". The Lab transports each declared frame; unscripted frames "
                        "fail closed in step B. The obligation digest is unchanged, the "
                        "107-row denominator is untouched and no runtime credit is claimed"
                    ),
                    "predecessor_requested_state_digest": (
                        prior["successor_requested_state_digest"]
                        if prior is not None
                        else base[fixture_id]["requested_state_digest"]
                    ),
                    "successor_contract": SUCCESSOR_PATH,
                }.items()
            )
        )
    )
ledger["records"] = [*ledger["records"], *new_entries]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

print("wrote", dst.name, "predecessor sha256", contract["predecessor"]["sha256"])
print("patched", len(OBLIGATION_FIXTURES), "records;", len(new_patches), "new patch entries")
for fixture_id in OBLIGATION_FIXTURES:
    print(
        fixture_id,
        "arrival" if arrival_added[fixture_id] else "",
        "obligation" if obligation_added[fixture_id] else "",
        "mana+" + str(len(mana_added[fixture_id])) if mana_added[fixture_id] else "",
    )
