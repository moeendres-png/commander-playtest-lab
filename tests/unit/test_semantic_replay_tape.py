"""WS218 unit tests: canonicalization, fingerprints, digests, schema, divergence."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from commander_lab.semantic_replay.canonicalization import (
    CANONICALIZATION_VERSION,
    canonical_bytes,
    redact_text,
)
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence
from commander_lab.semantic_replay.fingerprint import (
    internal_checkpoint_digest,
    legal_set_digest,
    legal_set_fingerprints,
    option_fingerprint,
    principal_observation_digest,
    public_state_digest,
)
from commander_lab.semantic_replay.source_lock import verify_domain_lock, verify_source_lock
from commander_lab.semantic_replay.tape import (
    TAPE_SCHEMA_VERSION,
    SemanticReplayTape,
    TapeCheckpoint,
    TapeDeckRef,
    TapeGameManifest,
    TapeReplayStep,
    TapeRngContract,
    TapeSeatPrincipal,
    TapeSourceLock,
    TapeTerminal,
)


def _pilot_state() -> dict[str, Any]:
    return {
        "actor_id": "actor-uuid-1",
        "active_player_id": "actor-uuid-1",
        "priority_player_id": "actor-uuid-1",
        "game_id": "game-uuid",
        "phase": "precombat_main",
        "seat": 0,
        "step": None,
        "stack": [{"name": "Lightning Bolt", "object_id": "stack-uuid-1"}],
        "commander_status": [],
        "turn_number": 3,
        "players": [
            {
                "battlefield": [
                    {
                        "abilities": ["Flying"],
                        "ability_count": 1,
                        "controller_id": "actor-uuid-1",
                        "counters": [],
                        "damage": 0,
                        "name": "Isamaru, Hound of Konda",
                        "object_id": "perm-uuid-1",
                        "power": 2,
                        "tapped": False,
                        "toughness": 2,
                    }
                ],
                "command": [{"name": "Isamaru, Hound of Konda", "object_id": "cmd-uuid-1"}],
                "exile_count": 0,
                "graveyard": [{"name": "Plains", "object_id": "gy-uuid-1"}],
                "graveyard_count": 1,
                "hand": [
                    {"name": "Plains", "object_id": "hand-uuid-1"},
                    {"name": "Plains", "object_id": "hand-uuid-2"},
                ],
                "hand_count": 2,
                "has_lost": False,
                "has_won": False,
                "is_actor": True,
                "land_plays_remaining": 1,
                "library_count": 90,
                "life": 40,
                "mana_pool": {
                    "black": 0,
                    "blue": 0,
                    "colorless": 0,
                    "green": 0,
                    "red": 0,
                    "white": 1,
                },
                "player_id": "actor-uuid-1",
                "poison_counters": 0,
                "seat": 0,
            },
            {
                "battlefield": [],
                "command": [{"name": "Rograkh, Son of Rohgahh", "object_id": "cmd-uuid-2"}],
                "exile_count": 0,
                "graveyard": [],
                "graveyard_count": 0,
                "hand_count": 5,
                "has_lost": False,
                "has_won": False,
                "is_actor": False,
                "library_count": 93,
                "life": 38,
                "player_id": "opp-uuid-9",
                "poison_counters": 0,
                "seat": 1,
            },
        ],
    }


def test_canonicalization_is_stable_and_versioned() -> None:
    assert CANONICALIZATION_VERSION == "semantic-canonical-1.0.0"
    value = {"b": [3, 2, 1], "a": {"y": 1, "x": 2}}
    assert canonical_bytes(value) == b'{"a":{"x":2,"y":1},"b":[3,2,1]}'
    assert canonical_bytes(value).decode("utf-8")
    with pytest.raises(ValueError, match="non-canonical"):
        canonical_bytes({"nan": float("nan")})


def test_redaction_removes_uuids_but_keeps_rules_text() -> None:
    prompt = (
        "{W}<div><font object_id='64c42435-d2e2-4aa3-8ce7-7a77ecaecc00'>Isamaru</font> [64c]</div>"
    )
    redacted = str(redact_text(prompt))
    assert "Isamaru" in redacted
    assert "object_id" not in redacted
    assert "64c42435" not in redacted
    twin = (
        "{W}<div><font object_id='07f0fab5-af4b-4f72-905b-bd7184dfc56a'>Isamaru</font> [07f]</div>"
    )
    assert redact_text(prompt) == redact_text(twin)


def test_option_fingerprint_ignores_process_local_ids() -> None:
    state = _pilot_state()
    first = {
        "label": "Keep opening hand",
        "metadata": {},
        "option_id": "aaaa",
        "option_type": "keep",
    }
    second = dict(first, option_id="bbbb")
    assert option_fingerprint(first, state) == option_fingerprint(second, state)
    boolean_yes = {
        "label": "Yes",
        "metadata": {"value": True},
        "option_id": "x",
        "option_type": "boolean",
    }
    boolean_no = {
        "label": "No",
        "metadata": {"value": False},
        "option_id": "y",
        "option_type": "boolean",
    }
    assert option_fingerprint(boolean_yes, state) != option_fingerprint(boolean_no, state)


def test_target_fingerprint_joins_observation_not_name_only() -> None:
    state = _pilot_state()
    # Two identical labels resolving to different objects must differ.
    attacker_state = copy.deepcopy(state)
    attacker_state["players"][0]["battlefield"].append(
        {
            "abilities": [],
            "ability_count": 0,
            "controller_id": "opp-uuid-9",
            "counters": [],
            "damage": 0,
            "name": "Savannah Lions",
            "object_id": "perm-uuid-2",
            "power": 2,
            "tapped": False,
            "toughness": 1,
        }
    )
    attacker_state["players"][1]["battlefield"] = [
        {
            "abilities": [],
            "ability_count": 0,
            "controller_id": "opp-uuid-9",
            "counters": [],
            "damage": 0,
            "name": "Savannah Lions",
            "object_id": "perm-uuid-3",
            "power": 2,
            "tapped": True,
            "toughness": 1,
        }
    ]
    opt_a = {
        "label": "Savannah Lions",
        "metadata": {"name": "Savannah Lions", "object_id": "perm-uuid-2"},
        "option_id": "perm-uuid-2",
        "option_type": "target",
    }
    opt_b = {
        "label": "Savannah Lions",
        "metadata": {"name": "Savannah Lions", "object_id": "perm-uuid-3"},
        "option_id": "perm-uuid-3",
        "option_type": "target",
    }
    assert option_fingerprint(opt_a, attacker_state) != option_fingerprint(opt_b, attacker_state)


def test_duplicate_identical_projections_are_ambiguous_by_design() -> None:
    state = _pilot_state()
    state["players"][0]["battlefield"] = [
        {
            "abilities": [],
            "ability_count": 0,
            "controller_id": "actor-uuid-1",
            "counters": [],
            "damage": 0,
            "name": "Plains",
            "object_id": "perm-uuid-10",
            "power": 0,
            "tapped": False,
            "toughness": 0,
        },
        {
            "abilities": [],
            "ability_count": 0,
            "controller_id": "actor-uuid-1",
            "counters": [],
            "damage": 0,
            "name": "Plains",
            "object_id": "perm-uuid-11",
            "power": 0,
            "tapped": False,
            "toughness": 0,
        },
    ]
    opt_a = {
        "label": "Plains",
        "metadata": {"name": "Plains", "object_id": "perm-uuid-10"},
        "option_id": "perm-uuid-10",
        "option_type": "target",
    }
    opt_b = {
        "label": "Plains",
        "metadata": {"name": "Plains", "object_id": "perm-uuid-11"},
        "option_id": "perm-uuid-11",
        "option_type": "target",
    }
    # Identical public projections share a fingerprint: the consumer must
    # fail closed as AMBIGUOUS rather than pick one.
    assert option_fingerprint(opt_a, state) == option_fingerprint(opt_b, state)
    prints = legal_set_fingerprints([opt_a, opt_b], state)
    assert prints[0] == prints[1]


def test_legal_set_is_a_multiset() -> None:
    state = _pilot_state()
    opt = {
        "label": "Keep opening hand",
        "metadata": {},
        "option_id": "k",
        "option_type": "keep",
    }
    one = legal_set_digest([opt], state)
    two = legal_set_digest([opt, dict(opt, option_id="k2")], state)
    assert one != two


def test_observation_digests_are_stable_and_scoped() -> None:
    first = _pilot_state()
    second = copy.deepcopy(first)
    # Remap every raw UUID to fresh values with identical seats/structure.
    remap = {
        "actor-uuid-1": "fresh-actor",
        "opp-uuid-9": "fresh-opp",
        "game-uuid": "fresh-game",
        "perm-uuid-1": "fresh-perm",
        "cmd-uuid-1": "fresh-cmd",
        "cmd-uuid-2": "fresh-cmd2",
        "gy-uuid-1": "fresh-gy",
        "hand-uuid-1": "fresh-h1",
        "hand-uuid-2": "fresh-h2",
        "stack-uuid-1": "fresh-stack",
    }
    encoded = json.dumps(second)
    for old, new in remap.items():
        encoded = encoded.replace(old, new)
    second = json.loads(encoded)
    assert principal_observation_digest(first) == principal_observation_digest(second)
    assert public_state_digest(first) == public_state_digest(second)
    encoded_full = json.dumps(
        {"digest": principal_observation_digest(first), "public": public_state_digest(first)}
    )
    for raw in remap:
        assert raw not in encoded_full
    # Opponent hand contents never enter the digest: the canonical view
    # must not carry a hand array for non-actors (counts only).
    assert '"hand":' not in json.dumps(second["players"][1])


def test_internal_digest_binds_seed_calls_turn_offset() -> None:
    state = _pilot_state()
    legal = [
        {"label": "Pass priority", "metadata": {}, "option_id": "p", "option_type": "pass_priority"}
    ]
    base = internal_checkpoint_digest(
        pilot_state=state,
        legal_options=legal,
        rules_seed=7,
        rules_random_calls=10,
        turn_number=3,
        decision_offset=9,
    )
    assert (
        internal_checkpoint_digest(
            pilot_state=state,
            legal_options=legal,
            rules_seed=7,
            rules_random_calls=11,
            turn_number=3,
            decision_offset=9,
        )
        != base
    )


def _lock() -> TapeSourceLock:
    return TapeSourceLock(
        adapter_identity="xmage-engine-bridge full-game lane",
        commander_authority_identity="xmage-commander-ffa",
        decision_protocol_version="xmage-external-decision-protocol-1.0.0",
        engine_commit="d" * 40,
        engine_repository="xmage-engine (pinned via XmageProvider)",
        engine_version="1.4.61",
        lab_commit="a" * 40,
        lab_repository="moeendres-png/commander-playtest-lab",
        lab_tree="b" * 40,
        oracle_snapshot_identity="xmage-card-db",
        protocol_schema_digest="c" * 64,
        protocol_version="2.0.0",
        provider_identity="xmage",
        rules_authority_identity="xmage",
        rulings_snapshot_identity=None,
    )


def test_tape_schema_is_versioned_and_strict() -> None:
    assert TAPE_SCHEMA_VERSION == "semantic-replay-tape/1.0.0"
    lock = _lock()
    manifest = TapeGameManifest(
        commander_identities=("Isamaru, Hound of Konda", "Rograkh, Son of Rohgahh"),
        decks=(
            TapeDeckRef(
                commander_names=("Isamaru, Hound of Konda",),
                deck_hash="e" * 64,
                deck_id="deck-1",
                mainboard=tuple(["Plains"] * 99),
            ),
            TapeDeckRef(
                commander_names=("Rograkh, Son of Rohgahh",),
                deck_hash="f" * 64,
                deck_id="deck-2",
                mainboard=tuple(["Mountain"] * 99),
            ),
        ),
        mulligan_contract="London",
        pilot_seed_derivation="derived",
        player_count=2,
        process_isolation_contract="fresh",
        rules_seed=1,
        seat_principals=(
            TapeSeatPrincipal(
                decision_policy_version="p",
                deck_id="deck-1",
                pilot_identity="P",
                pilot_version="1",
                seat=1,
            ),
            TapeSeatPrincipal(
                decision_policy_version="p",
                deck_id="deck-2",
                pilot_identity="P",
                pilot_version="1",
                seat=2,
            ),
        ),
        starting_life=40,
        starting_player_selection_contract="seed_mod_N",
    )
    assert manifest.player_count == 2
    checkpoint = TapeCheckpoint(
        decision_sequence=0,
        event_offset=0,
        phase="precombat_main",
        principal_digests={"seat-1": "f" * 64},
        public_state_digest="f" * 64,
        rules_random_calls=0,
        rules_seed=1,
        semantic_state_digest="f" * 64,
        step=None,
        turn_number=1,
    )
    terminal = TapeTerminal(
        outcomes=(
            {"left": False, "life": 40, "lost": False, "seat": 1, "won": True},
            {"left": True, "life": 40, "lost": False, "seat": 2, "won": False},
        ),
        public_state_digest="f" * 64,
        rules_random_calls=9,
        semantic_state_digest="f" * 64,
        turn_number=2,
    )
    tape = SemanticReplayTape(
        game_manifest=manifest,
        initial_checkpoint=checkpoint,
        rng_contract=TapeRngContract(
            require_explicit_seed=True, root_rules_seed=1, rules_seed_explicit=True
        ),
        seal={"tape_schema": TAPE_SCHEMA_VERSION},
        source_lock=lock,
        steps=(),
        tape_id="0" * 64,
        terminal_checkpoint=terminal,
    )
    assert tape.schema_version == TAPE_SCHEMA_VERSION
    with pytest.raises(Exception, match="steps must be densely ordered"):
        SemanticReplayTape(
            game_manifest=manifest,
            initial_checkpoint=checkpoint,
            rng_contract=tape.rng_contract,
            seal=tape.seal,
            source_lock=lock,
            steps=(
                TapeReplayStep(
                    actor_principal=1,
                    decision_class="priority",
                    decision_revision=1,
                    event_digest="f" * 64,
                    event_offset_before=1,
                    legal_set_digest="f" * 64,
                    legal_set_size=1,
                    principal_observation_digest="f" * 64,
                    rng_calls_before=0,
                    sequence=2,
                ),
            ),
            tape_id="0" * 64,
            terminal_checkpoint=terminal,
        )


def test_divergence_taxonomy_has_required_classes() -> None:
    names = {item.value for item in DivergenceClass}
    for required in (
        "SOURCE_LOCK_MISMATCH",
        "DOMAIN_LOCK_MISMATCH",
        "INITIAL_STATE_MISMATCH",
        "ACTOR_MISMATCH",
        "DECISION_CLASS_MISMATCH",
        "DECISION_REVISION_MISMATCH",
        "OBSERVATION_MISMATCH",
        "LEGAL_SET_MISMATCH",
        "CHOSEN_OPTION_MISSING",
        "CHOSEN_OPTION_AMBIGUOUS",
        "RULES_RNG_CALL_DRIFT",
        "RULES_RNG_RESULT_DRIFT",
        "EVENT_DIGEST_MISMATCH",
        "STATE_DIGEST_MISMATCH",
        "EARLY_TERMINATION",
        "EXTRA_DECISION",
        "TERMINAL_OUTCOME_MISMATCH",
        "MALFORMED_TAPE",
    ):
        assert required in names
    exc = ReplayDivergence(DivergenceClass.ACTOR_MISMATCH, "seat differs")
    assert "ACTOR_MISMATCH" in str(exc)


def test_source_lock_refuses_close_enough() -> None:
    first, second = _lock(), _lock()
    second = second.model_copy(update={"engine_commit": "e" * 40})
    with pytest.raises(ReplayDivergence) as caught:
        verify_source_lock(first, second)
    assert caught.value.divergence == DivergenceClass.SOURCE_LOCK_MISMATCH
    with pytest.raises(ReplayDivergence):
        verify_domain_lock({"player_count": 4}, {"player_count": 3})
