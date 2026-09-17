from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from functools import lru_cache
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import _RawFullGameClient
from commander_lab.engine.rules.full_game_ws18 import FullGamePilotBindingV2, XmageFullGameRunnerV2
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)

XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SUPPORT_PATH = ROOT / "qualification/evidence/ws22-xmage/RUNTIME_SUPPORT_EVIDENCE.json"
HIDDEN_BASELINE_FIXTURES = {"HIDDEN_01", "HIDDEN_02"}
HIDDEN_AUDIT_FIXTURES = {"HIDDEN_18", "HIDDEN_19", "HIDDEN_HONEYCARD_SENTINEL"}
HIDDEN_SCENARIO_FIXTURES = {f"HIDDEN_{index:02d}" for index in range(3, 18)}
PILOT_RUNTIME_FIXTURES = {"PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_CHOOSE_OBJECT"}
PILOT_ALL_FIXTURES = {
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "PILOT_CHOOSE_OBJECT",
    "PILOT_TARGET_AMOUNT",
    "PILOT_MULLIGAN",
    "PILOT_CHOOSE_USE",
    "PILOT_CHOICE",
    "PILOT_PILE",
    "PILOT_MANA_PAYMENT",
    "PILOT_ANNOUNCE_X",
    "PILOT_MULTI_AMOUNT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_TRIGGER_ORDER",
    "PILOT_CHOOSE_MODE",
    "PILOT_CHOOSE_ABILITY",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
}
NEGATIVE_FIXTURES = {
    "NEGATIVE_FIRST_OPTION",
    "NEGATIVE_RANDOM_OPTION",
    "NEGATIVE_DEFAULT_YES_NO",
    "NEGATIVE_INTERNAL_AI",
    "NEGATIVE_GUI_DEFAULT",
    "NEGATIVE_SILENT_SKIP",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
}
REPLAY_FIXTURES = {
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
}
HONEY_SENTINEL = "Snow-Covered Plains"
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _bridge_command() -> tuple[str, ...]:
    raw = os.environ.get("COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD", "").strip()
    if not raw:
        raise RuntimeError("XMAGE_BRIDGE_NOT_CONFIGURED")
    return tuple(shlex.split(raw))


def _deck(seat: int, basic_land: str = "Plains", *, label: str = "hidden") -> RulesDeckInput:
    deck_id = f"ws22-{label}-seat-{seat}"
    commander_names = ("Isamaru, Hound of Konda",)
    mainboard = tuple(basic_land for _ in range(99))
    material = {
        "deck_id": deck_id,
        "commander_names": commander_names,
        "mainboard": mainboard,
    }
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"WS-22 {label} seat {seat}",
        commander_names=commander_names,
        mainboard=mainboard,
        deck_hash=_sha256(material),
        source_path=f"synthetic:ws22-{label}-runtime",
    )


def _deck_payload(deck: RulesDeckInput) -> dict[str, Any]:
    return {
        "deck_id": deck.deck_id,
        "name": deck.name,
        "commander_names": list(deck.commander_names),
        "mainboard": list(deck.mainboard),
        "deck_hash": deck.deck_hash,
        "source_path": deck.source_path,
    }


def _pass(reason: str, payload: Any) -> dict[str, Any]:
    return {
        "verdict": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": reason,
        "artifact_hashes": {"semantic_probe_sha256": _sha256(payload)},
    }


def _fail(reason: str, payload: Any) -> dict[str, Any]:
    return {
        "verdict": "FAIL",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": reason,
        "artifact_hashes": {"semantic_probe_sha256": _sha256(payload)},
    }


def _unsupported(reason: str, payload: Any) -> dict[str, Any]:
    return {
        "verdict": "UNSUPPORTED",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": reason,
        "artifact_hashes": {"runtime_support_sha256": _sha256(payload)},
    }


@lru_cache(maxsize=1)
def runtime_support_evidence() -> dict[str, Any]:
    if not RUNTIME_SUPPORT_PATH.is_file():
        raise RuntimeError("WS22_RUNTIME_SUPPORT_EVIDENCE_MISSING")
    data = json.loads(RUNTIME_SUPPORT_PATH.read_text(encoding="utf-8"))
    if data.get("xmage_commit") != XMAGE_COMMIT:
        raise RuntimeError("XMAGE_BUILD_IDENTITY_MISMATCH")
    capabilities = data.get("capabilities")
    lane = data.get("full_game_lane")
    if not isinstance(capabilities, dict) or not isinstance(lane, dict):
        raise RuntimeError("WS22_RUNTIME_SUPPORT_EVIDENCE_INVALID")
    return data


def _require_no_scenario_injection() -> dict[str, Any]:
    evidence = runtime_support_evidence()
    capabilities = evidence["capabilities"]
    if capabilities.get("starting_state_injection_supported") is not False:
        raise RuntimeError("starting-state injection runtime truth changed")
    if capabilities.get("scenario_injection_supported") is not False:
        raise RuntimeError("scenario injection runtime truth changed")
    return evidence


def _start_real_four_player_game(
    decks: tuple[RulesDeckInput, ...], *, game_id: str, seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _RawFullGameClient(_bridge_command(), cwd=ROOT, request_timeout_seconds=120.0) as client:
        started = client.request("start_engine")
        if started.get("lane") != "xmage_full_game_external_pilots":
            raise RuntimeError("bridge did not enter full-game lane")
        provider = client.request("get_provider_version")
        if provider.get("engine_commit") != XMAGE_COMMIT:
            raise RuntimeError("XMAGE_BUILD_IDENTITY_MISMATCH")
        handles: list[str] = []
        for deck in decks:
            imported = client.request("import_deck", {"deck": _deck_payload(deck)})
            handle = imported.get("deck_handle")
            if not isinstance(handle, dict) or not isinstance(handle.get("handle_id"), str):
                raise RuntimeError("IMPORT_DECK returned no stable handle")
            handles.append(handle["handle_id"])
        created = client.request(
            "create_full_game",
            {
                "game_id": game_id,
                "deck_handles": handles,
                "seed": seed,
                "starting_player_seat": 0,
                "starting_life": 40,
            },
        )
        if created.get("player_count") != 4:
            raise RuntimeError("semantic probe did not create a real 4P game")
        client.request("start_full_game")
        observed = client.request(
            "get_full_game_observation",
            {"viewer_seat": 0, "decision_subject_seat": 0},
        )
        observation = observed.get("observation")
        if not isinstance(observation, dict):
            raise RuntimeError("actor-scoped observation unavailable")
        result = client.request("get_full_game_result")
        if not isinstance(result, dict):
            raise RuntimeError("full-game audit result unavailable")
        return observation, result


@lru_cache(maxsize=1)
def hidden_baseline_results() -> dict[str, dict[str, Any]]:
    decks = tuple(_deck(seat) for seat in range(1, 5))
    observation, _ = _start_real_four_player_game(
        decks, game_id="ws22-hidden-baseline", seed=424242
    )
    players = observation.get("players")
    if not isinstance(players, list) or len(players) != 4:
        raise RuntimeError("actor-scoped observation does not contain four registered players")
    own = players[0]
    opponents = players[1:]
    hand_ok = (
        isinstance(own, dict)
        and isinstance(own.get("hand"), list)
        and all(
            isinstance(player, dict)
            and isinstance(player.get("hand_count"), int)
            and "hand" not in player
            for player in opponents
        )
    )
    library_ok = all(
        isinstance(player, dict)
        and isinstance(player.get("library_count"), int)
        and player.get("library_count", -1) >= 0
        and "library" not in player
        and isinstance(player.get("known_library"), list)
        and len(player["known_library"]) == 0
        for player in players
    )
    return {
        "HIDDEN_01": _pass(
            "Real 4P XMage KnowledgeLedger observation exposes the viewer hand, preserves opponent hand counts, and omits opponent hand identities.",
            observation,
        )
        if hand_ok
        else _fail(
            "Real 4P XMage KnowledgeLedger observation leaked opponent hand identities or omitted required hand counts.",
            observation,
        ),
        "HIDDEN_02": _pass(
            "Real 4P XMage KnowledgeLedger observation preserves library counts while omitting unknown library identities/order for the viewer.",
            observation,
        )
        if library_ok
        else _fail(
            "Real 4P XMage KnowledgeLedger observation exposed unknown library identity/order or omitted the public library count.",
            observation,
        ),
    }


@lru_cache(maxsize=1)
def hidden_audit_results() -> dict[str, dict[str, Any]]:
    decks = (
        _deck(1, "Plains", label="audit"),
        _deck(2, HONEY_SENTINEL, label="honey"),
        _deck(3, HONEY_SENTINEL, label="honey"),
        _deck(4, HONEY_SENTINEL, label="honey"),
    )
    observation, result = _start_real_four_player_game(
        decks, game_id="ws22-hidden-audit", seed=424242
    )
    transcript = result.get("transcript")
    if not isinstance(transcript, list) or not transcript:
        raise RuntimeError("full-game transcript unavailable for audit redaction probe")
    forbidden_transcript_keys = {
        "prompt",
        "legal_option_labels",
        "selected_option_labels",
        "private_actor_state_reference",
        "public_state_reference",
        "payload",
        "message",
        "detail",
    }
    transcript_keys = {key for event in transcript if isinstance(event, dict) for key in event}
    transcript_ok = forbidden_transcript_keys.isdisjoint(transcript_keys)
    hidden_18_payload = {
        "transcript": transcript,
        "forbidden_keys": sorted(forbidden_transcript_keys),
    }
    hidden_18 = (
        _pass(
            "Real XMage full-game durable transcript is a structural whitelist and omits prompts, labels, private state references, payloads and failure details.",
            hidden_18_payload,
        )
        if transcript_ok
        else _fail(
            "Durable XMage full-game transcript retained actor-private or free-text audit fields.",
            hidden_18_payload,
        )
    )
    api_payload = {"observation": observation, "result": result}
    api_text = json.dumps(api_payload, sort_keys=True, ensure_ascii=False)
    forbidden_api_keys = {
        "raw_game",
        "raw_engine",
        "engine_object",
        "omniscient_state",
        "native_game",
        "native_card",
    }
    api_keys = {key for root in (observation, result) for key in root if isinstance(root, dict)}
    hidden_19_ok = not _UUID_RE.search(api_text) and forbidden_api_keys.isdisjoint(api_keys)
    hidden_19 = (
        _pass(
            "Even the lower-level full-game JSON bridge exposes actor-scoped JSON projection only: no raw UUID identity or omniscient/raw engine object field reaches the pilot-facing lane.",
            api_payload,
        )
        if hidden_19_ok
        else _fail(
            "Pilot-facing full-game surface exposed a raw UUID or raw/omniscient engine-state field.",
            api_payload,
        )
    )
    honey_ok = HONEY_SENTINEL not in api_text
    honey = (
        _pass(
            "A real 4P run with opponent-only Snow-Covered Plains honeycard identities leaves the viewer observation and durable result/transcript free of the forbidden identity token.",
            api_payload,
        )
        if honey_ok
        else _fail(
            "Opponent-only honeycard identity leaked into actor-visible observation or durable full-game audit result.",
            api_payload,
        )
    )
    return {
        "HIDDEN_18": hidden_18,
        "HIDDEN_19": hidden_19,
        "HIDDEN_HONEYCARD_SENTINEL": honey,
    }


def _pilot_binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBindingV2:
    return FullGamePilotBindingV2(
        seat=seat,
        deck_id=deck.deck_id,
        strategy="generic",
        commander_names=deck.commander_names,
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-ws22-pilot-smoke-policy-1.0.0",
    )


@lru_cache(maxsize=1)
def pilot_smoke_results() -> dict[str, dict[str, Any]]:
    decks = tuple(_deck(seat, label="pilot-smoke") for seat in range(1, 5))
    pilots = tuple(_pilot_binding(seat, decks[seat - 1]) for seat in range(1, 5))
    own = decks[0]
    if own.deck_hash is None:
        raise RuntimeError("pilot-smoke deck hash unavailable")
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=4,
        seat=1,
        scenario_id="ws22-pilot-smoke",
        seed=424242,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-ws22-pilot-smoke-policy-1.0.0",
    )
    result = XmageFullGameRunnerV2(
        cwd=ROOT, request_timeout_seconds=120.0, max_decisions=50_000
    ).run(scenario=scenario, decks=decks, pilots=pilots)
    transcript = result.result_payload.get("transcript")
    if not result.terminal or not isinstance(transcript, list):
        raise RuntimeError("pilot-smoke external-pilot run did not reach terminal transcript")
    requested: dict[str, int] = {}
    accepted: dict[str, int] = {}
    for event in transcript:
        if not isinstance(event, dict):
            continue
        decision_class = event.get("decision_class")
        if not isinstance(decision_class, str):
            continue
        if event.get("kind") == "decision_requested":
            requested[decision_class] = requested.get(decision_class, 0) + 1
        elif event.get("kind") == "decision_accepted":
            accepted[decision_class] = accepted.get(decision_class, 0) + 1
    evidence = {
        "decision_count": result.decision_count,
        "requested": requested,
        "accepted": accepted,
        "semantic_transcript_sha256": result.semantic_transcript_sha256,
        "raw_result_sha256": result.raw_result_sha256,
        "fallback_used": result.fallback_used,
        "xmage_rules_authority": result.xmage_rules_authority,
        "commander_lab_pilot_decision_authority": result.commander_lab_pilot_decision_authority,
    }

    def verdict(decision_class: str, *, minimum: int = 1) -> dict[str, Any]:
        req = requested.get(decision_class, 0)
        acc = accepted.get(decision_class, 0)
        ok = (
            req >= minimum
            and acc == req
            and result.fallback_used is False
            and result.xmage_rules_authority is True
            and result.commander_lab_pilot_decision_authority is True
        )
        return (
            _pass(
                f"Real terminal 4P XMage run exercised {decision_class} through the primary external pilot policy with {req} requested/{acc} accepted decisions, exact XMage legal-option submission, no fallback, and XMage retained rules authority.",
                evidence,
            )
            if ok
            else _fail(
                f"Real terminal 4P XMage run did not complete the required external {decision_class} decision roundtrip without fallback.",
                evidence,
            )
        )

    return {
        "PILOT_MULLIGAN": verdict("mulligan", minimum=4),
        "PILOT_CHOOSE_OBJECT": verdict("choose_object"),
        "PILOT_PRIORITY": verdict("priority"),
    }


def _parent_fallback_result() -> dict[str, Any]:
    evidence = runtime_support_evidence()
    suite = evidence.get("bridge_test_suites", {}).get("XmageFullGamePlayerBoundaryTest")
    if not isinstance(suite, dict) or suite.get("passed") is not True:
        return _fail(
            "Exact-head player-boundary runtime suite did not pass; parent-class fallback remains unqualified.",
            evidence,
        )
    return _pass(
        "Exact-head compiled player-boundary suite executed the complete discretionary callback reflection gate and confirmed only the two explicitly audited safe parent delegations remain.",
        {"suite": suite, "evidence_sha256": evidence.get("evidence_sha256")},
    )


def _scenario_injection_unsupported(fixture_id: str) -> dict[str, Any]:
    evidence = _require_no_scenario_injection()
    return _unsupported(
        f"{fixture_id} requires a deterministic semantic starting state or scenario injection to execute its exact rules path. The exact-head full-game runtime reports both starting_state_injection_supported=false and scenario_injection_supported=false; WS-22 therefore closes this fixture as UNSUPPORTED rather than awarding source-derived credit.",
        {
            "fixture_id": fixture_id,
            "capabilities": evidence["capabilities"],
            "evidence_sha256": evidence.get("evidence_sha256"),
        },
    )


def _replay_unsupported(fixture_id: str) -> dict[str, Any]:
    evidence = runtime_support_evidence()
    capabilities = evidence["capabilities"]
    lane = evidence["full_game_lane"]
    if capabilities.get("replay_supported") is not False:
        raise RuntimeError("replay capability runtime truth changed")
    if lane.get("bit_exact_replay_validated") is not False:
        raise RuntimeError("bit-exact replay runtime truth changed")
    return _unsupported(
        f"{fixture_id} requires durable replay/RNG-tape evidence. The exact-head runtime reports replay_supported=false and bit_exact_replay_validated=false, so no replay obligation receives substitute PASS credit.",
        {
            "fixture_id": fixture_id,
            "replay_supported": capabilities.get("replay_supported"),
            "bit_exact_replay_validated": lane.get("bit_exact_replay_validated"),
            "evidence_sha256": evidence.get("evidence_sha256"),
        },
    )


def _negative_unsupported(fixture_id: str) -> dict[str, Any]:
    evidence = runtime_support_evidence()
    return _unsupported(
        f"{fixture_id} is a mandatory forbidden-fallback mechanism. The exact-head boundary suite is executed, but the production lane exposes no deterministic negative-mechanism injection hook that independently executes this specific forbidden fallback. WS-22 therefore records UNSUPPORTED instead of inferring PASS from source structure.",
        {
            "fixture_id": fixture_id,
            "boundary_suite": evidence.get("bridge_test_suites", {}).get(
                "XmageFullGamePlayerBoundaryTest"
            ),
            "evidence_sha256": evidence.get("evidence_sha256"),
        },
    )


def run_semantic_fixture(fixture_id: str) -> dict[str, Any] | None:
    if fixture_id in HIDDEN_BASELINE_FIXTURES:
        return hidden_baseline_results()[fixture_id]
    if fixture_id in HIDDEN_AUDIT_FIXTURES:
        return hidden_audit_results()[fixture_id]
    if fixture_id in PILOT_RUNTIME_FIXTURES:
        return pilot_smoke_results()[fixture_id]
    if fixture_id == "NEGATIVE_PARENT_CLASS_FALLBACK":
        return _parent_fallback_result()
    if fixture_id in NEGATIVE_FIXTURES:
        return _negative_unsupported(fixture_id)
    if fixture_id in REPLAY_FIXTURES:
        return _replay_unsupported(fixture_id)
    if fixture_id in HIDDEN_SCENARIO_FIXTURES:
        return _scenario_injection_unsupported(fixture_id)
    if fixture_id in PILOT_ALL_FIXTURES:
        return _scenario_injection_unsupported(fixture_id)
    if fixture_id.startswith("WS05-"):
        return _scenario_injection_unsupported(fixture_id)
    if fixture_id.startswith("MICRO_"):
        return _scenario_injection_unsupported(fixture_id)
    if fixture_id.startswith("CARD_"):
        return _scenario_injection_unsupported(fixture_id)
    return None
