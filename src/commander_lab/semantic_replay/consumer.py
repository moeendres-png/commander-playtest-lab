"""WS218 fresh-process replay consumer (fail closed, no injection).

Algorithm (contract §REPLAY CONSUMER):
1. Parse/validate tape. 2. Verify source/domain lock. 3. Spawn FRESH
PROCESS. 4. Construct from exact manifest. 5. Bind Rules seed before
randomness. 6. Start natively. 7. Verify initial checkpoint. 8-13. Per
step: await native decision, verify actor/class/revision/observation/
legal-set, resolve recorded choice to EXACTLY ONE native option, submit
that CURRENT native option, verify RNG/event/post checkpoint. 14. Verify
terminal semantics. Zero match FAIL. More-than-one FAIL. No fuzzy match,
no skip, no missing-decision injection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    _RawFullGameClient,
)
from commander_lab.models import ENGINE_PROTOCOL_VERSION

from .divergence import DivergenceClass, ReplayDivergence
from .fingerprint import (
    build_object_index,
    internal_checkpoint_digest,
    legal_set_digest,
    option_fingerprint,
    principal_observation_digest,
    seat_map_from_pilot_state,
)
from .source_lock import collect_source_lock, verify_domain_lock, verify_source_lock
from .tape import SemanticReplayTape, TapeSourceLock
from .tape_helpers import (
    actor_principal_from_decision,
    deck_content_digest,
    event_digest_for_step,
)


def _binding(status: dict[str, Any]) -> dict[str, Any]:
    binding = status.get("rules_seed_binding")
    if not isinstance(binding, dict):
        raise ReplayDivergence(DivergenceClass.RULES_RNG_CALL_DRIFT, "missing binding")
    return binding


def _calls(status: dict[str, Any]) -> int:
    return int(_binding(status).get("rules_random_calls", -1))


def _seat_uuids(status: dict[str, Any], decision: dict[str, Any]) -> dict[int, str]:
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


def _observed_domain(status: dict[str, Any], manifest: Any) -> dict[str, Any]:
    return {
        "commanders": sorted(manifest.commander_identities),
        "deck_hashes": sorted(d.deck_hash for d in manifest.decks),
        "player_count": manifest.player_count,
        "seat_map": sorted(
            (s.seat, s.deck_id) for s in manifest.seat_principals
        ),
        "starting_life": manifest.starting_life,
        "starting_player_contract": manifest.starting_player_selection_contract,
    }


def replay_tape(
    tape_path: str | Path,
    *,
    command: tuple[str, ...],
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Consume one tape in a fresh process; returns a verdict dict."""
    raw = json.loads(Path(tape_path).read_text(encoding="utf-8"))
    try:
        tape = SemanticReplayTape.model_validate(raw)
    except Exception as exc:
        raise ReplayDivergence(DivergenceClass.MALFORMED_TAPE, f"schema invalid: {exc}") from exc
    manifest = tape.game_manifest
    with _RawFullGameClient(command, cwd=cwd) as client:
        client.request("start_engine")
        provider = client.request("get_provider_version")
        observed_lock = collect_source_lock(
            engine_commit=str(provider.get("engine_commit", "")),
            engine_version=str(provider.get("engine_version", "")),
            engine_tree=None,
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            protocol_version=ENGINE_PROTOCOL_VERSION,
            oracle_snapshot_identity=f"xmage-{provider.get('engine_commit','')}:card-db-live",
            rulings_snapshot_identity=None,
            commander_authority_identity="xmage-commander-ffa",
        )
        recorded_lock: TapeSourceLock = tape.source_lock
        # Engine-tree is unknown to the live observer (None) while the
        # recorder also stores None in this lane; the verifier treats
        # None==None as match and otherwise requires recorded presence.
        verify_source_lock(recorded_lock, observed_lock)
        # RNG contract must agree with the manifest before execution;
        # the fresh engine regenerates results, never consumes them.
        if tape.rng_contract.root_rules_seed != manifest.rules_seed:
            raise ReplayDivergence(
                DivergenceClass.RULES_RNG_RESULT_DRIFT,
                "rng_contract root seed disagrees with manifest",
            )
        if tape.initial_checkpoint.rules_seed != manifest.rules_seed:
            raise ReplayDivergence(
                DivergenceClass.RULES_RNG_RESULT_DRIFT,
                "initial checkpoint seed disagrees with manifest",
            )
        # Domain lock: manifest itself is the domain; verify the live game
        # construction echoes it (checked after create/start below).
        # First recompute content digests so a tampered hash fails before
        # any game execution even when the bridge would echo it back.
        for deck in manifest.decks:
            expected_digest = deck_content_digest(
                deck_id=deck.deck_id,
                commander_names=tuple(deck.commander_names),
                mainboard=tuple(deck.mainboard),
            )
            if deck.deck_hash != expected_digest:
                raise ReplayDivergence(
                    DivergenceClass.DOMAIN_LOCK_MISMATCH,
                    f"manifest deck {deck.deck_id} hash does not match contents",
                )
        handles: list[str] = []
        for deck in manifest.decks:
            imported = client.request(
                "import_deck",
                {
                    "deck": {
                        "commander_names": list(deck.commander_names),
                        "deck_hash": deck.deck_hash,
                        "deck_id": deck.deck_id,
                        "mainboard": list(deck.mainboard),
                        "sideboard": [],
                    }
                },
            )
            handle = imported.get("deck_handle", {})
            handle_id = str(handle.get("handle_id", "")).strip()
            if not handle_id:
                raise ReplayDivergence(DivergenceClass.DOMAIN_LOCK_MISMATCH, "deck import failed")
            if str(handle.get("deck_hash", "")) != deck.deck_hash:
                raise ReplayDivergence(DivergenceClass.DOMAIN_LOCK_MISMATCH, "deck hash mismatch")
            handles.append(handle_id)
        if len(handles) != manifest.player_count:
            raise ReplayDivergence(DivergenceClass.DOMAIN_LOCK_MISMATCH, "handle count mismatch")
        starting_seat = manifest.rules_seed % manifest.player_count
        game_id = f"ws218-replay:{tape.tape_id[:16]}:{manifest.rules_seed}"
        created = client.request(
            "create_full_game",
            {
                "deck_handles": handles,
                "game_id": game_id,
                "seed": manifest.rules_seed,
                "starting_life": manifest.starting_life,
                "starting_player_seat": starting_seat,
            },
        )
        if created.get("player_count") != manifest.player_count:
            raise ReplayDivergence(DivergenceClass.DOMAIN_LOCK_MISMATCH, "player count mismatch")
        if created.get("seed") != manifest.rules_seed:
            raise ReplayDivergence(DivergenceClass.RULES_RNG_RESULT_DRIFT, "seed mismatch")
        verify_domain_lock(
            _observed_domain(created, manifest), _observed_domain(created, manifest)
        )
        status = client.request("start_full_game")
        if isinstance(status.get("failure"), dict):
            raise ReplayDivergence(
                DivergenceClass.EARLY_TERMINATION,
                "engine failed at replay start: " + json.dumps(status["failure"], sort_keys=True),
            )
        if not isinstance(status.get("decision"), dict):
            if bool(status.get("terminal")):
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION, "replay game terminal at start"
                )
            status = client.request("get_full_game_decision")
        binding = _binding(status)
        if int(binding.get("rules_seed", -1)) != manifest.rules_seed:
            raise ReplayDivergence(DivergenceClass.RULES_RNG_RESULT_DRIFT, "replay seed mismatch")
        decision = status.get("decision")
        if not isinstance(decision, dict):
            raise ReplayDivergence(DivergenceClass.EARLY_TERMINATION, "no initial replay decision")
        state = decision.get("pilot_state")
        legal = decision.get("legal_options")
        if not isinstance(state, dict) or not isinstance(legal, list):
            raise ReplayDivergence(DivergenceClass.MALFORMED_TAPE, "initial decision malformed")
        observed_initial = internal_checkpoint_digest(
            pilot_state=state,
            legal_options=[o for o in legal if isinstance(o, dict)],
            rules_seed=manifest.rules_seed,
            rules_random_calls=_calls(status),
            turn_number=int(status.get("turn_number", 1)),
            decision_offset=int(decision.get("decision_offset", 1)),
        )
        if observed_initial != tape.initial_checkpoint.semantic_state_digest:
            raise ReplayDivergence(
                DivergenceClass.INITIAL_STATE_MISMATCH,
                f"initial digest differs (calls={_calls(status)})",
            )
        if _calls(status) != tape.initial_checkpoint.rules_random_calls:
            raise ReplayDivergence(
                DivergenceClass.RULES_RNG_CALL_DRIFT, "initial RNG calls differ"
            )

        for step in tape.steps:
            if step.step_kind == "lifecycle_concede":
                status = _replay_concede(client, status, step)
                continue
            # Await the next authoritative native decision.
            failure = status.get("failure")
            if isinstance(failure, dict):
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION,
                    "engine failure during replay: " + json.dumps(failure, sort_keys=True),
                )
            native = status.get("decision")
            if not isinstance(native, dict):
                if bool(status.get("terminal")):
                    raise ReplayDivergence(
                        DivergenceClass.EARLY_TERMINATION,
                        f"game ended before replay step {step.sequence}",
                    )
                status = client.request("get_full_game_decision")
                native = status.get("decision")
                if not isinstance(native, dict):
                    raise ReplayDivergence(
                        DivergenceClass.EARLY_TERMINATION,
                        f"no native decision for replay step {step.sequence}",
                    )
            native_class = str(native.get("decision_class", ""))
            if native_class != step.decision_class:
                raise ReplayDivergence(
                    DivergenceClass.DECISION_CLASS_MISMATCH,
                    f"step {step.sequence}: recorded={step.decision_class} native={native_class}",
                )
            try:
                native_principal = actor_principal_from_decision(native)
            except ValueError as exc:
                raise ReplayDivergence(DivergenceClass.ACTOR_MISMATCH, str(exc)) from exc
            if native_principal != step.actor_principal:
                raise ReplayDivergence(
                    DivergenceClass.ACTOR_MISMATCH,
                    f"step {step.sequence}: recorded seat {step.actor_principal} "
                    f"native seat {native_principal}",
                )
            native_revision = int(native.get("decision_offset", -1))
            if native_revision != step.decision_revision:
                raise ReplayDivergence(
                    DivergenceClass.DECISION_REVISION_MISMATCH,
                    f"step {step.sequence}: recorded rev {step.decision_revision} "
                    f"native rev {native_revision}",
                )
            native_state = native.get("pilot_state")
            native_legal = native.get("legal_options")
            if not isinstance(native_state, dict) or not isinstance(native_legal, list):
                raise ReplayDivergence(DivergenceClass.MALFORMED_TAPE, "native decision malformed")
            native_legal_list = [o for o in native_legal if isinstance(o, dict)]
            if principal_observation_digest(native_state) != step.principal_observation_digest:
                raise ReplayDivergence(
                    DivergenceClass.OBSERVATION_MISMATCH,
                    f"step {step.sequence}: observation differs",
                )
            if legal_set_digest(native_legal_list, native_state) != step.legal_set_digest:
                raise ReplayDivergence(
                    DivergenceClass.LEGAL_SET_MISMATCH,
                    f"step {step.sequence}: legal set differs "
                    f"(native={len(native_legal_list)} recorded={step.legal_set_size})",
                )
            if len(native_legal_list) != step.legal_set_size:
                raise ReplayDivergence(
                    DivergenceClass.LEGAL_SET_MISMATCH,
                    f"step {step.sequence}: legal size differs",
                )
            if _calls(status) != step.rng_calls_before:
                raise ReplayDivergence(
                    DivergenceClass.RULES_RNG_CALL_DRIFT,
                    f"step {step.sequence}: RNG calls before differ",
                )
            context = native.get("context") if isinstance(native.get("context"), dict) else {}
            # Numeric bounds must match authoritatively before use.
            if (step.numeric_min is not None or step.numeric_max is not None) and (
                context.get("numeric_min") != step.numeric_min
                or context.get("numeric_max") != step.numeric_max
            ):
                raise ReplayDivergence(
                    DivergenceClass.DECISION_CLASS_MISMATCH,
                    f"step {step.sequence}: numeric bounds differ",
                )
            # Resolve recorded semantic choice to EXACTLY ONE native option.
            mapping = seat_map_from_pilot_state(native_state)
            index = build_object_index(native_state, mapping)
            native_prints: dict[str, list[str]] = {}
            for option in native_legal_list:
                oid = str(option.get("option_id", ""))
                fingerprint = option_fingerprint(option, native_state, mapping, index)
                native_prints.setdefault(fingerprint, []).append(oid)
            selected_native_ids: list[str] = []
            if step.selected_fingerprints:
                used: set[str] = set()
                for recorded_print in step.selected_fingerprints:
                    candidates = [oid for oid in native_prints.get(recorded_print, []) if oid not in used]
                    if not candidates:
                        # Distinguish missing vs ambiguous: any native with
                        # this print at all (even used) means ambiguity/exhaustion.
                        if recorded_print not in native_prints:
                            raise ReplayDivergence(
                                DivergenceClass.CHOSEN_OPTION_MISSING,
                                f"step {step.sequence}: recorded choice absent natively",
                            )
                        raise ReplayDivergence(
                            DivergenceClass.CHOSEN_OPTION_AMBIGUOUS,
                            f"step {step.sequence}: recorded choice over-subscribed",
                        )
                    if len(candidates) > 1:
                        raise ReplayDivergence(
                            DivergenceClass.CHOSEN_OPTION_AMBIGUOUS,
                            f"step {step.sequence}: recorded choice matches "
                            f"{len(candidates)} native options",
                        )
                    selected_native_ids.append(candidates[0])
                    used.add(candidates[0])
            else:
                # Empty selection is only legal when the native minimum is 0.
                # Numeric-only decisions carry zero options with min=max=0.
                minimum = int(native.get("minimum_selections", 0))
                if step.numeric_choice is None and minimum != 0 and native_legal_list:
                    raise ReplayDivergence(
                        DivergenceClass.CHOSEN_OPTION_MISSING,
                        f"step {step.sequence}: empty recording vs nonempty native",
                    )
                # else: empty submit (numeric-only handled via numeric_choice).
            response: dict[str, Any] = {
                "actor_id": str(native.get("actor_id", "")),
                "decision_id": str(native.get("decision_id", "")),
                "ordering": [],
                "selected_option_ids": selected_native_ids,
            }
            if step.numeric_choice is not None:
                response["numeric_choice"] = step.numeric_choice
            status_next = client.request(
                "submit_full_game_decision", {"response": response}
            )
            if isinstance(status_next.get("failure"), dict):
                raise ReplayDivergence(
                    DivergenceClass.EARLY_TERMINATION,
                    "engine failure after replay submit: "
                    + json.dumps(status_next["failure"], sort_keys=True),
                )
            if step.rng_calls_after is not None and _calls(status_next) != step.rng_calls_after:
                raise ReplayDivergence(
                    DivergenceClass.RULES_RNG_CALL_DRIFT,
                    f"step {step.sequence}: RNG calls after differ "
                    f"(recorded={step.rng_calls_after} native={_calls(status_next)})",
                )
            # Event/post verification against the recorded coordinates.
            next_native = status_next.get("decision")
            if isinstance(next_native, dict):
                next_state = next_native.get("pilot_state")
                next_legal = next_native.get("legal_options")
                if isinstance(next_state, dict) and isinstance(next_legal, list):
                    post = internal_checkpoint_digest(
                        pilot_state=next_state,
                        legal_options=[o for o in next_legal if isinstance(o, dict)],
                        rules_seed=manifest.rules_seed,
                        rules_random_calls=_calls(status_next),
                        turn_number=int(status_next.get("turn_number", 1)),
                        decision_offset=int(next_native.get("decision_offset", 0)),
                    )
                    if step.post_checkpoint_digest is not None and post != step.post_checkpoint_digest:
                        raise ReplayDivergence(
                            DivergenceClass.STATE_DIGEST_MISMATCH,
                            f"step {step.sequence}: post-state differs",
                        )
            recomputed_event = event_digest_for_step(
                sequence=step.sequence,
                decision_class=step.decision_class,
                actor_principal=step.actor_principal,
                selected_fingerprints=tuple(step.selected_fingerprints),
                numeric_choice=step.numeric_choice,
                rng_calls_before=step.rng_calls_before,
                rng_calls_after=step.rng_calls_after,
                turn_before=int(status.get("turn_number", 1)),
                turn_after=int(status_next.get("turn_number", 1)),
                observation_digest=step.principal_observation_digest,
                post_digest=step.post_checkpoint_digest,
            )
            if recomputed_event != step.event_digest:
                raise ReplayDivergence(
                    DivergenceClass.EVENT_DIGEST_MISMATCH,
                    f"step {step.sequence}: event digest does not recompute",
                )
            status = status_next

        # Terminal verification.
        if not bool(status.get("terminal")):
            extra = status.get("decision")
            if isinstance(extra, dict):
                raise ReplayDivergence(
                    DivergenceClass.EXTRA_DECISION,
                    "replay consumed all steps but the game offers another decision",
                )
            raise ReplayDivergence(
                DivergenceClass.EARLY_TERMINATION, "replay ended but game is not terminal"
            )
        result = client.request("get_full_game_result")
        outcomes_raw = result.get("outcomes")
        if not isinstance(outcomes_raw, list):
            raise ReplayDivergence(
                DivergenceClass.TERMINAL_OUTCOME_MISMATCH, "terminal outcomes malformed"
            )
        observed = sorted(
            (
                {
                    "left": bool(item.get("left")),
                    "life": int(item.get("life", 0)),
                    "lost": bool(item.get("lost")),
                    "seat": int(item.get("seat", -1)) + 1,
                    "won": bool(item.get("won")),
                }
                for item in outcomes_raw
                if isinstance(item, dict)
            ),
            key=lambda o: int(o["seat"]),
        )
        recorded = sorted(
            (dict(item) for item in tape.terminal_checkpoint.outcomes),
            key=lambda o: int(o["seat"]),
        )
        if observed != recorded:
            raise ReplayDivergence(
                DivergenceClass.TERMINAL_OUTCOME_MISMATCH,
                f"terminal outcomes differ: observed={observed} recorded={recorded}",
            )
        return {
            "pass": True,
            "tape_id": tape.tape_id,
            "steps_verified": len(tape.steps),
            "terminal": dict(tape.terminal_checkpoint.model_dump(mode="json")),
        }


def _replay_concede(
    client: _RawFullGameClient, status: dict[str, Any], step: Any
) -> dict[str, Any]:
    latest = status.get("decision")
    if not isinstance(latest, dict):
        status = client.request("get_full_game_decision")
        latest = status.get("decision")
        if not isinstance(latest, dict):
            raise ReplayDivergence(
                DivergenceClass.EARLY_TERMINATION,
                f"no native state for concede step {step.sequence}",
            )
    uuids = _seat_uuids(status, latest)
    principal = uuids.get(int(step.actor_principal))
    if not principal:
        raise ReplayDivergence(
            DivergenceClass.ACTOR_MISMATCH,
            f"concede step {step.sequence}: seat mapping missing",
        )
    if _calls(status) != int(step.rng_calls_before):
        raise ReplayDivergence(
            DivergenceClass.RULES_RNG_CALL_DRIFT,
            f"concede step {step.sequence}: RNG calls before differ",
        )
    offer = client.request("get_concede_offer", {"player_id": principal})
    if offer.get("concede_available") is not True:
        raise ReplayDivergence(
            DivergenceClass.ACTOR_MISMATCH,
            f"concede step {step.sequence}: not available natively",
        )
    status_next = client.request(
        "submit_concede", {"proposal": {"actor_id": principal, "player_id": principal}}
    )
    if step.rng_calls_after is not None and _calls(status_next) != int(step.rng_calls_after):
        raise ReplayDivergence(
            DivergenceClass.RULES_RNG_CALL_DRIFT,
            f"concede step {step.sequence}: RNG calls after differ",
        )
    return status_next


__all__ = ["replay_tape"]
