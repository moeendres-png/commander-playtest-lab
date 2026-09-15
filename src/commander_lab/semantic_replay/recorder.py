"""WS218 recorder: fresh-process tape capture over the production lane.

Uses the production full-game JSONL lane (``_RawFullGameClient``) plus the
production ``ExternalPilotDecisionPolicy`` for discretionary choices. The
recorder never synthesizes legality: every recorded choice is a native
option id offered by XMage for the exact pending decision; fingerprints
are evidence projections only. Rules RNG is never injected: the recorder
only observes ``rules_random_calls`` from live ``rules_seed_binding``.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from commander_lab.agents import build_pilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RawFullGameClient,
    _RuntimePilot,
)
from commander_lab.models import ENGINE_PROTOCOL_VERSION, RulesDeckInput

from .canonicalization import CANONICALIZATION_VERSION, canonical_hash
from .divergence import DivergenceClass, ReplayDivergence
from .fingerprint import (
    SEMANTIC_OPTION_IDENTITY_VERSION,
    STATE_DIGEST_VERSION,
    internal_checkpoint_digest,
    legal_set_digest,
    principal_observation_digest,
    public_state_digest,
)
from .source_lock import collect_source_lock
from .tape import (
    TAPE_SCHEMA_VERSION,
    SemanticReplayTape,
    TapeCheckpoint,
    TapeDeckRef,
    TapeGameManifest,
    TapeReplayStep,
    TapeRngContract,
    TapeSeatPrincipal,
    TapeTerminal,
)
from .tape_helpers import (
    actor_principal_from_decision,
    deck_content_digest,
    event_digest_for_step,
    selected_fingerprints_for_response,
)

STARTING_LIFE = 40
MULLIGAN_CONTRACT = (
    "London mulligan, free first, deterministic harness discipline for "
    "qualification (neutral keep / develop extreme-opener take-one, max 3); "
    "paid London bottom arrives as hand-target choices natively"
)
STARTING_CONTRACT_TEMPLATE = (
    "seed_mod_N chooser (starting_player_seat = seed % N); native CR103.2 "
    "starting-player choice offered to the chooser"
)
PILOT_DERIVATION = (
    "deterministic pilot rng sha256(scenario_seed:seat:offset:class); "
    "no separate pilot seed; pilot identities/versions bound in manifest"
)
PROCESS_ISOLATION_CONTRACT = (
    "one_game_per_process fresh JVM per record and per replay; "
    "120s request timeout; no shared mutable engine state"
)


def _deck_ref(deck: RulesDeckInput) -> TapeDeckRef:
    if deck.deck_hash is None:
        raise ValueError(f"deck_hash required for {deck.deck_id}")
    expected = deck_content_digest(
        deck_id=deck.deck_id,
        commander_names=tuple(deck.commander_names),
        mainboard=tuple(deck.mainboard),
    )
    if deck.deck_hash != expected:
        raise ReplayDivergence(
            DivergenceClass.DOMAIN_LOCK_MISMATCH,
            f"deck {deck.deck_id} hash does not match content digest",
        )
    return TapeDeckRef(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash,
        commander_names=tuple(deck.commander_names),
        mainboard=tuple(deck.mainboard),
    )


def _seat_principals(
    pilots: tuple[FullGamePilotBinding, ...],
) -> tuple[TapeSeatPrincipal, ...]:
    return tuple(
        TapeSeatPrincipal(
            seat=binding.seat,
            deck_id=binding.deck_id,
            pilot_identity=binding.pilot_identity,
            pilot_version=binding.pilot_version,
            decision_policy_version=binding.decision_policy_version,
        )
        for binding in sorted(pilots, key=lambda b: b.seat)
    )


def _binding_calls(status: dict[str, Any]) -> int:
    binding = status.get("rules_seed_binding")
    if not isinstance(binding, dict) or "rules_random_calls" not in binding:
        raise ReplayDivergence(
            DivergenceClass.RULES_RNG_CALL_DRIFT,
            "status is missing live rules_seed_binding.rules_random_calls",
        )
    return int(binding["rules_random_calls"])


def _binding_seed(status: dict[str, Any]) -> int:
    binding = status.get("rules_seed_binding")
    if not isinstance(binding, dict):
        raise ReplayDivergence(
            DivergenceClass.INITIAL_STATE_MISMATCH, "status missing rules_seed_binding"
        )
    return int(binding.get("rules_seed", -1))


def _verify_binding(status: dict[str, Any], seed: int) -> None:
    binding = status.get("rules_seed_binding")
    if not isinstance(binding, dict):
        raise ReplayDivergence(
            DivergenceClass.INITIAL_STATE_MISMATCH, "missing rules_seed_binding"
        )
    if int(binding.get("rules_seed", -1)) != seed:
        raise ReplayDivergence(DivergenceClass.RULES_RNG_RESULT_DRIFT, "rules_seed mismatch")
    if binding.get("rules_seed_matches") is not True:
        raise ReplayDivergence(DivergenceClass.RULES_RNG_RESULT_DRIFT, "seed not matching")
    if binding.get("rules_seed_explicit") is not True:
        raise ReplayDivergence(DivergenceClass.RULES_RNG_RESULT_DRIFT, "seed not explicit")


def _pilot_state_of(decision: dict[str, Any]) -> dict[str, Any]:
    state = decision.get("pilot_state")
    if not isinstance(state, dict):
        raise ReplayDivergence(DivergenceClass.OBSERVATION_MISMATCH, "decision lacks pilot_state")
    return state


def _legal_options_of(decision: dict[str, Any]) -> list[dict[str, Any]]:
    raw = decision.get("legal_options")
    if not isinstance(raw, list) or not all(isinstance(o, dict) for o in raw):
        raise ReplayDivergence(DivergenceClass.LEGAL_SET_MISMATCH, "legal_options malformed")
    return list(raw)


def _seat_uuid_map(status: dict[str, Any], decision: dict[str, Any]) -> dict[int, str]:
    """1-based seat -> native player UUID from current observation."""
    mapping: dict[int, str] = {}
    state = decision.get("pilot_state")
    if isinstance(state, dict) and isinstance(state.get("players"), list):
        for entry in state["players"]:
            if isinstance(entry, dict) and isinstance(entry.get("seat"), int):
                pid = entry.get("player_id")
                if isinstance(pid, str):
                    mapping[int(entry["seat"]) + 1] = pid
    outcomes = status.get("outcomes")
    if isinstance(outcomes, list):
        for item in outcomes:
            if isinstance(item, dict) and isinstance(item.get("seat"), int):
                pid = item.get("player_id")
                if isinstance(pid, str):
                    mapping[int(item["seat"]) + 1] = pid
    return mapping


def record_tape(
    *,
    scenario: FutureXmageScenario,
    decks: tuple[RulesDeckInput, ...],
    pilots: tuple[FullGamePilotBinding, ...],
    command: tuple[str, ...],
    output_path: str | Path,
    max_decisions: int = 120,
    concede_to_finish: bool = True,
    winner_seat: int = 1,
    cwd: str | Path | None = None,
) -> SemanticReplayTape:
    """Record one complete tape in a fresh process; atomic write; fail closed."""
    output = Path(output_path)
    tmp_incomplete = output.with_suffix(output.suffix + ".incomplete")
    tmp_write = output.with_suffix(output.suffix + ".tmp")
    runtime_pilots = tuple(
        _RuntimePilot(binding=b, pilot=build_pilot(b.config, strategy=b.strategy))
        for b in sorted(pilots, key=lambda b: b.seat)
    )
    policy = ExternalPilotDecisionPolicy(runtime_pilots, scenario.seed)
    player_count = scenario.player_count
    starting_seat = scenario.seed % player_count

    with _RawFullGameClient(command, cwd=cwd) as client:
        client.request("start_engine")
        provider = client.request("get_provider_version")
        client.request("get_capabilities")
        engine_commit = str(provider.get("engine_commit", ""))
        engine_version = str(provider.get("engine_version", "unknown"))
        if provider.get("engine") != "xmage":
            raise ReplayDivergence(DivergenceClass.SOURCE_LOCK_MISMATCH, "provider is not xmage")
        source_lock = collect_source_lock(
            engine_commit=engine_commit,
            engine_version=engine_version,
            engine_tree=None,
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            protocol_version=ENGINE_PROTOCOL_VERSION,
            oracle_snapshot_identity=f"xmage-{engine_commit}:card-db-live",
            rulings_snapshot_identity=None,
            commander_authority_identity="xmage-commander-ffa",
        )
        manifest = TapeGameManifest(
            player_count=player_count,
            seat_principals=_seat_principals(pilots),
            decks=tuple(_deck_ref(d) for d in decks),
            commander_identities=tuple(sorted({c for d in decks for c in d.commander_names})),
            starting_life=STARTING_LIFE,
            starting_player_selection_contract=(
                STARTING_CONTRACT_TEMPLATE + f" (chooser seat_index={starting_seat})"
            ),
            mulligan_contract=MULLIGAN_CONTRACT,
            rules_seed=scenario.seed,
            pilot_seed_derivation=PILOT_DERIVATION,
            process_isolation_contract=PROCESS_ISOLATION_CONTRACT,
        )
        rng_contract = TapeRngContract(
            root_rules_seed=scenario.seed,
            rules_seed_explicit=True,
            require_explicit_seed=True,
        )
        handles: list[str] = []
        for deck in decks:
            imported = client.request(
                "import_deck",
                {
                    "deck": {
                        "commander_names": list(deck.commander_names),
                        "deck_hash": deck.deck_hash,
                        "deck_id": deck.deck_id,
                        "mainboard": list(deck.mainboard),
                        "sideboard": list(deck.sideboard),
                    }
                },
            )
            handle = imported.get("deck_handle", {})
            handle_id = str(handle.get("handle_id", "")).strip()
            if not handle_id:
                raise ReplayDivergence(DivergenceClass.MALFORMED_TAPE, "deck import gave no handle")
            handles.append(handle_id)
        game_id = f"ws218-record:{scenario.scenario_id}:{scenario.seed}"
        created = client.request(
            "create_full_game",
            {
                "deck_handles": handles,
                "game_id": game_id,
                "seed": scenario.seed,
                "starting_life": STARTING_LIFE,
                "starting_player_seat": starting_seat,
            },
        )
        if created.get("player_count") != player_count or created.get("seed") != scenario.seed:
            raise ReplayDivergence(DivergenceClass.DOMAIN_LOCK_MISMATCH, "creation mismatch")
        status = client.request("start_full_game")
        if isinstance(status.get("failure"), dict):
            raise ReplayDivergence(
                DivergenceClass.EARLY_TERMINATION,
                "engine failed at start: " + json.dumps(status["failure"], sort_keys=True),
            )
        _verify_binding(status, scenario.seed)
        # The engine thread needs a beat to publish the first decision;
        # poll exactly like the production runner (never synthesize).
        if not isinstance(status.get("decision"), dict):
            if bool(status.get("terminal")):
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION, "game terminal before first decision"
                )
            status = client.request("get_full_game_decision")
            if isinstance(status.get("failure"), dict):
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION,
                    "engine failed before first decision: "
                    + json.dumps(status["failure"], sort_keys=True),
                )
        _verify_binding(status, scenario.seed)
        if not isinstance(status.get("decision"), dict):
            raise ReplayDivergence(DivergenceClass.EARLY_TERMINATION, "no initial decision")
        first_decision: dict[str, Any] = status["decision"]
        first_state = _pilot_state_of(first_decision)
        first_legal = _legal_options_of(first_decision)
        first_calls = _binding_calls(status)
        first_turn = int(status.get("turn_number", 1))
        initial_checkpoint = TapeCheckpoint(
            rules_seed=scenario.seed,
            rules_random_calls=first_calls,
            turn_number=first_turn,
            phase=str(first_state.get("phase")) if first_state.get("phase") else None,
            step=str(first_state.get("step")) if first_state.get("step") else None,
            decision_sequence=0,
            event_offset=0,
            semantic_state_digest=internal_checkpoint_digest(
                pilot_state=first_state,
                legal_options=first_legal,
                rules_seed=scenario.seed,
                rules_random_calls=first_calls,
                turn_number=first_turn,
                decision_offset=int(first_decision.get("decision_offset", 1)),
            ),
            public_state_digest=public_state_digest(first_state),
            principal_digests={
                f"seat-{actor_principal_from_decision(first_decision)}": principal_observation_digest(
                    first_state
                )
            },
        )
        steps: list[TapeReplayStep] = []
        sequence = 0
        try:
            while True:
                failure = status.get("failure")
                if isinstance(failure, dict):
                    raise ReplayDivergence(
                        DivergenceClass.EARLY_TERMINATION,
                        "engine failure mid-game: " + json.dumps(failure, sort_keys=True),
                    )
                decision = status.get("decision")
                if not isinstance(decision, dict):
                    if bool(status.get("terminal")):
                        break
                    status = client.request("get_full_game_decision")
                    continue
                if len(steps) >= max_decisions:
                    break
                sequence += 1
                decision_class = str(decision.get("decision_class", ""))
                actor_principal = actor_principal_from_decision(decision)
                revision = int(decision.get("decision_offset", -1))
                state = _pilot_state_of(decision)
                legal = _legal_options_of(decision)
                calls_before = _binding_calls(status)
                turn_before = int(status.get("turn_number", 1))
                obs_digest = principal_observation_digest(state)
                legal_digest = legal_set_digest(legal, state)
                legal_size = len(legal)
                context = decision.get("context") if isinstance(decision.get("context"), dict) else {}
                numeric_min = context.get("numeric_min")
                numeric_max = context.get("numeric_max")
                response = policy.decide(decision)
                selected_ids = [str(v) for v in response.get("selected_option_ids", [])]
                numeric_choice = response.get("numeric_choice")
                selected_prints, selected_labels = (
                    selected_fingerprints_for_response(decision, selected_ids)
                    if selected_ids
                    else ((), ())
                )
                status_next = client.request(
                    "submit_full_game_decision", {"response": response}
                )
                if isinstance(status_next.get("failure"), dict):
                    raise ReplayDivergence(
                        DivergenceClass.EARLY_TERMINATION,
                        "engine failure after submit: "
                        + json.dumps(status_next["failure"], sort_keys=True),
                    )
                calls_after = _binding_calls(status_next)
                next_decision = status_next.get("decision")
                if isinstance(next_decision, dict):
                    offset_after = int(next_decision.get("decision_offset", revision))
                    turn_after: int | None = int(status_next.get("turn_number", turn_before))
                    next_state = _pilot_state_of(next_decision)
                    next_legal = _legal_options_of(next_decision)
                    post_digest: str | None = internal_checkpoint_digest(
                        pilot_state=next_state,
                        legal_options=next_legal,
                        rules_seed=scenario.seed,
                        rules_random_calls=calls_after,
                        turn_number=turn_after,
                        decision_offset=offset_after,
                    )
                else:
                    offset_after = revision
                    turn_after = int(status_next.get("turn_number", turn_before))
                    post_digest = None
                event_digest = event_digest_for_step(
                    sequence=sequence,
                    decision_class=decision_class,
                    actor_principal=actor_principal,
                    selected_fingerprints=selected_prints,
                    numeric_choice=int(numeric_choice) if numeric_choice is not None else None,
                    rng_calls_before=calls_before,
                    rng_calls_after=calls_after,
                    turn_before=turn_before,
                    turn_after=turn_after,
                    observation_digest=obs_digest,
                    post_digest=post_digest,
                )
                steps.append(
                    TapeReplayStep(
                        sequence=sequence,
                        step_kind="decision",
                        decision_class=decision_class,
                        actor_principal=actor_principal,
                        decision_revision=revision,
                        principal_observation_digest=obs_digest,
                        legal_set_digest=legal_digest,
                        legal_set_size=legal_size,
                        selected_fingerprints=tuple(selected_prints),
                        selected_labels=tuple(selected_labels),
                        numeric_choice=int(numeric_choice) if numeric_choice is not None else None,
                        numeric_min=int(numeric_min) if isinstance(numeric_min, int) else None,
                        numeric_max=int(numeric_max) if isinstance(numeric_max, int) else None,
                        rng_calls_before=calls_before,
                        rng_calls_after=calls_after,
                        event_offset_before=revision,
                        event_offset_after=offset_after,
                        event_digest=event_digest,
                        post_checkpoint_digest=post_digest,
                    )
                )
                status = status_next
                if bool(status.get("terminal")) and not isinstance(status.get("decision"), dict):
                    break

            if not bool(status.get("terminal")) and concede_to_finish:
                # Force a bounded complete terminal via native concessions.
                # After each concession the engine may still hold a pending
                # discretionary decision for a survivor (e.g. London bottom);
                # drain those natively with the production policy so the game
                # actually reaches terminal. Drained decisions are recorded
                # as ordinary decision steps (beyond the prefix budget).
                conceded: set[int] = set()
                drain_budget = 60

                def _record_one_decision(
                    current_status: dict[str, Any], seq: int
                ) -> tuple[dict[str, Any], TapeReplayStep]:
                    dec = current_status.get("decision")
                    if not isinstance(dec, dict):
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            "drain expected a pending decision",
                        )
                    dclass = str(dec.get("decision_class", ""))
                    principal = actor_principal_from_decision(dec)
                    revision = int(dec.get("decision_offset", -1))
                    st = _pilot_state_of(dec)
                    legal = _legal_options_of(dec)
                    calls_b = _binding_calls(current_status)
                    turn_b = int(current_status.get("turn_number", 1))
                    obs_d = principal_observation_digest(st)
                    legal_d = legal_set_digest(legal, st)
                    ctx = dec.get("context") if isinstance(dec.get("context"), dict) else {}
                    nmin = ctx.get("numeric_min")
                    nmax = ctx.get("numeric_max")
                    resp = policy.decide(dec)
                    sel_ids = [str(v) for v in resp.get("selected_option_ids", [])]
                    nchoice = resp.get("numeric_choice")
                    sel_prints, sel_labels = (
                        selected_fingerprints_for_response(dec, sel_ids) if sel_ids else ((), ())
                    )
                    nxt = client.request("submit_full_game_decision", {"response": resp})
                    calls_a = _binding_calls(nxt)
                    nxt_dec = nxt.get("decision")
                    if isinstance(nxt_dec, dict):
                        off_a = int(nxt_dec.get("decision_offset", revision))
                        turn_a: int | None = int(nxt.get("turn_number", turn_b))
                        nst = _pilot_state_of(nxt_dec)
                        nlegal = _legal_options_of(nxt_dec)
                        post_d: str | None = internal_checkpoint_digest(
                            pilot_state=nst,
                            legal_options=nlegal,
                            rules_seed=scenario.seed,
                            rules_random_calls=calls_a,
                            turn_number=turn_a,
                            decision_offset=off_a,
                        )
                    else:
                        off_a = revision
                        turn_a = int(nxt.get("turn_number", turn_b))
                        post_d = None
                    ev_d = event_digest_for_step(
                        sequence=seq,
                        decision_class=dclass,
                        actor_principal=principal,
                        selected_fingerprints=sel_prints,
                        numeric_choice=int(nchoice) if nchoice is not None else None,
                        rng_calls_before=calls_b,
                        rng_calls_after=calls_a,
                        turn_before=turn_b,
                        turn_after=turn_a,
                        observation_digest=obs_d,
                        post_digest=post_d,
                    )
                    step_rec = TapeReplayStep(
                        sequence=seq,
                        step_kind="decision",
                        decision_class=dclass,
                        actor_principal=principal,
                        decision_revision=revision,
                        principal_observation_digest=obs_d,
                        legal_set_digest=legal_d,
                        legal_set_size=len(legal),
                        selected_fingerprints=tuple(sel_prints),
                        selected_labels=tuple(sel_labels),
                        numeric_choice=int(nchoice) if nchoice is not None else None,
                        numeric_min=int(nmin) if isinstance(nmin, int) else None,
                        numeric_max=int(nmax) if isinstance(nmax, int) else None,
                        rng_calls_before=calls_b,
                        rng_calls_after=calls_a,
                        event_offset_before=revision,
                        event_offset_after=off_a,
                        event_digest=ev_d,
                        post_checkpoint_digest=post_d,
                    )
                    return nxt, step_rec

                losers = [s for s in range(1, player_count + 1) if s != winner_seat]
                guard = 0
                while any(s not in conceded for s in losers):
                    guard += 1
                    if guard > player_count + drain_budget + 10:
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            "concede interleave guard tripped",
                        )
                    if bool(status.get("terminal")):
                        break
                    pending_now = status.get("decision")
                    if not isinstance(pending_now, dict):
                        status = client.request("get_full_game_decision")
                        pending_now = status.get("decision")
                        if not isinstance(pending_now, dict):
                            break
                    try:
                        pending_actor = actor_principal_from_decision(pending_now)
                    except ValueError:
                        pending_actor = -1
                    remaining = [s for s in losers if s not in conceded]
                    if pending_actor in remaining:
                        # Pending belongs to a future conceder: answer it
                        # first (never concede the pending actor).
                        sequence += 1
                        try:
                            status, drained_step = _record_one_decision(status, sequence)
                        except (ReplayDivergence, Exception) as exc:
                            failure = status.get("failure")
                            raise ReplayDivergence(
                                DivergenceClass.EARLY_TERMINATION,
                                "engine failure while draining to terminal: "
                                + json.dumps(failure, sort_keys=True)[:2000]
                                + f" exc={type(exc).__name__}:{exc}",
                            ) from exc
                        steps.append(drained_step)
                        if isinstance(status.get("failure"), dict):
                            raise ReplayDivergence(
                                DivergenceClass.EARLY_TERMINATION,
                                "engine failure while draining to terminal: "
                                + json.dumps(status["failure"], sort_keys=True)[:2000],
                            )
                        continue
                    seat = next(s for s in remaining if s != pending_actor)
                    seat_uuids = _seat_uuid_map(status, pending_now)
                    principal_uuid = seat_uuids.get(seat)
                    if not principal_uuid:
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            f"cannot map seat {seat} to a native principal",
                        )
                    sequence += 1
                    calls_before_c = _binding_calls(status)
                    turn_before_c = int(status.get("turn_number", 1))
                    offer = client.request(
                        "get_concede_offer", {"player_id": principal_uuid}
                    )
                    if offer.get("concede_available") is not True:
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            f"concede unavailable for seat {seat}",
                        )
                    status = client.request(
                        "submit_concede",
                        {
                            "proposal": {
                                "actor_id": principal_uuid,
                                "player_id": principal_uuid,
                            }
                        },
                    )
                    calls_after_c = _binding_calls(status)
                    next_dec = status.get("decision")
                    offset_after_c = (
                        int(next_dec.get("decision_offset", 0))
                        if isinstance(next_dec, dict)
                        else 0
                    )
                    turn_after_c: int | None = int(status.get("turn_number", turn_before_c))
                    event_digest_c = event_digest_for_step(
                        sequence=sequence,
                        decision_class="concede",
                        actor_principal=seat,
                        selected_fingerprints=(),
                        numeric_choice=None,
                        rng_calls_before=calls_before_c,
                        rng_calls_after=calls_after_c,
                        turn_before=turn_before_c,
                        turn_after=turn_after_c,
                        observation_digest=canonical_hash(
                            {"concede_actor": seat, "available": True}
                        ),
                        post_digest=None,
                    )
                    steps.append(
                        TapeReplayStep(
                            sequence=sequence,
                            step_kind="lifecycle_concede",
                            decision_class="concede",
                            actor_principal=seat,
                            decision_revision=max(1, offset_after_c or 1),
                            principal_observation_digest=canonical_hash(
                                {"concede_actor": seat}
                            ),
                            legal_set_digest=canonical_hash({"concede_available": True}),
                            legal_set_size=1,
                            selected_fingerprints=(),
                            selected_labels=(f"concede seat {seat}",),
                            rng_calls_before=calls_before_c,
                            rng_calls_after=calls_after_c,
                            event_offset_before=calls_before_c,
                            event_offset_after=calls_after_c,
                            event_digest=event_digest_c,
                        )
                    )
                    conceded.add(seat)
                    # Loop re-evaluates pending before the next concede;
                    # no eager drain here (avoids answering for left seats).

                # All losers conceded: drain survivor decisions to terminal.
                drained = 0
                while not bool(status.get("terminal")) and drained < drain_budget:
                    pending = status.get("decision")
                    if not isinstance(pending, dict):
                        status = client.request("get_full_game_decision")
                        pending = status.get("decision")
                        if not isinstance(pending, dict):
                            break
                    sequence += 1
                    try:
                        status, drained_step = _record_one_decision(status, sequence)
                    except (ReplayDivergence, Exception) as exc:
                        failure = status.get("failure")
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            "engine failure while draining to terminal: "
                            + json.dumps(failure, sort_keys=True)[:2000]
                            + f" exc={type(exc).__name__}:{exc}",
                        ) from exc
                    steps.append(drained_step)
                    drained += 1
                    if isinstance(status.get("failure"), dict):
                        raise ReplayDivergence(
                            DivergenceClass.EARLY_TERMINATION,
                            "engine failure while draining to terminal: "
                            + json.dumps(status["failure"], sort_keys=True)[:2000],
                        )

            if not bool(status.get("terminal")):
                # Bounded prefix without terminal: mark incomplete, never seal.
                incomplete = {
                    "complete": False,
                    "reason": "budget_exhausted_without_terminal",
                    "steps": len(steps),
                }
                tmp_incomplete.write_text(json.dumps(incomplete, indent=2) + "\n", encoding="utf-8")
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION,
                    "record budget exhausted without terminal; no complete tape sealed",
                )
            result = client.request("get_full_game_result")
            outcomes_raw = result.get("outcomes")
            if not isinstance(outcomes_raw, list) or len(outcomes_raw) != player_count:
                raise ReplayDivergence(
                    DivergenceClass.TERMINAL_OUTCOME_MISMATCH, "terminal outcomes malformed"
                )
            outcomes: list[dict[str, Any]] = []
            for item in outcomes_raw:
                if not isinstance(item, dict):
                    raise ReplayDivergence(
                        DivergenceClass.TERMINAL_OUTCOME_MISMATCH, "outcome not an object"
                    )
                outcomes.append(
                    {
                        "left": bool(item.get("left")),
                        "life": int(item.get("life", 0)),
                        "lost": bool(item.get("lost")),
                        "seat": int(item.get("seat", -1)) + 1,
                        "won": bool(item.get("won")),
                    }
                )
            outcomes.sort(key=lambda o: int(o["seat"]))
            final_turn = int(result.get("turn_number", status.get("turn_number", 1)))
            final_calls = _binding_calls(result if "rules_seed_binding" in result else status)
            terminal = TapeTerminal(
                turn_number=final_turn,
                rules_random_calls=final_calls,
                outcomes=tuple(outcomes),
                semantic_state_digest=canonical_hash(
                    {"outcomes": outcomes, "turn": final_turn, "calls": final_calls}
                ),
                public_state_digest=canonical_hash(
                    {"outcomes": outcomes, "turn": final_turn}
                ),
            )
            tape_id = hashlib.sha256(
                (
                    json.dumps(manifest.model_dump(mode="json"), sort_keys=True)
                    + json.dumps(initial_checkpoint.model_dump(mode="json"), sort_keys=True)
                    + json.dumps(
                        [s.model_dump(mode="json") for s in steps], sort_keys=True
                    )
                ).encode("utf-8")
            ).hexdigest()
            tape = SemanticReplayTape(
                tape_id=tape_id,
                source_lock=source_lock,
                game_manifest=manifest,
                rng_contract=rng_contract,
                initial_checkpoint=initial_checkpoint,
                steps=tuple(steps),
                terminal_checkpoint=terminal,
                seal={
                    "canonicalization": CANONICALIZATION_VERSION,
                    "identity": SEMANTIC_OPTION_IDENTITY_VERSION,
                    "state_digest": STATE_DIGEST_VERSION,
                    "tape_schema": TAPE_SCHEMA_VERSION,
                    "terminal_digest": terminal.semantic_state_digest,
                },
            )
        except Exception:
            # Interruption leaves original complete artifacts intact and marks
            # the new incomplete artifact identifiably; never a false seal.
            if output.exists():
                pass
            raise
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_write.write_text(
        json.dumps(tape.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_write.replace(output)
    if tmp_incomplete.exists():
        tmp_incomplete.unlink()
    _ = time.monotonic()
    return tape


__all__ = ["record_tape"]
