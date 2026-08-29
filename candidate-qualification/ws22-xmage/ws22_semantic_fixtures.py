from __future__ import annotations

import hashlib
import json
import os
import shlex
from functools import lru_cache
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import _RawFullGameClient
from commander_lab.models import RulesDeckInput

XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
ROOT = Path(__file__).resolve().parents[2]
HIDDEN_BASELINE_FIXTURES = {"HIDDEN_01", "HIDDEN_02"}


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


def _deck(seat: int) -> RulesDeckInput:
    deck_id = f"ws22-hidden-seat-{seat}"
    commander_names = ("Isamaru, Hound of Konda",)
    mainboard = tuple("Plains" for _ in range(99))
    material = {
        "deck_id": deck_id,
        "commander_names": commander_names,
        "mainboard": mainboard,
    }
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"WS-22 hidden-information seat {seat}",
        commander_names=commander_names,
        mainboard=mainboard,
        deck_hash=_sha256(material),
        source_path="synthetic:ws22-hidden-information-runtime",
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


@lru_cache(maxsize=1)
def hidden_baseline_results() -> dict[str, dict[str, Any]]:
    decks = tuple(_deck(seat) for seat in range(1, 5))
    with _RawFullGameClient(
        _bridge_command(),
        cwd=ROOT,
        request_timeout_seconds=120.0,
    ) as client:
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
                "game_id": "ws22-hidden-baseline",
                "deck_handles": handles,
                "seed": 424242,
                "starting_player_seat": 0,
                "starting_life": 40,
            },
        )
        if created.get("player_count") != 4:
            raise RuntimeError("hidden-information probe did not create a real 4P game")
        client.request("start_full_game")
        observed = client.request(
            "get_full_game_observation",
            {"viewer_seat": 0, "decision_subject_seat": 0},
        )
        observation = observed.get("observation")
        if not isinstance(observation, dict):
            raise RuntimeError("actor-scoped observation unavailable")

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
    hidden_01 = (
        _pass(
            "Real 4P XMage KnowledgeLedger observation exposes the viewer hand, preserves opponent hand counts, and omits opponent hand identities.",
            observation,
        )
        if hand_ok
        else _fail(
            "Real 4P XMage KnowledgeLedger observation leaked opponent hand identities or omitted required hand counts.",
            observation,
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
    hidden_02 = (
        _pass(
            "Real 4P XMage KnowledgeLedger observation preserves library counts while omitting unknown library identities/order for the viewer.",
            observation,
        )
        if library_ok
        else _fail(
            "Real 4P XMage KnowledgeLedger observation exposed unknown library identity/order or omitted the public library count.",
            observation,
        )
    )

    return {"HIDDEN_01": hidden_01, "HIDDEN_02": hidden_02}


def run_semantic_fixture(fixture_id: str) -> dict[str, Any] | None:
    if fixture_id in HIDDEN_BASELINE_FIXTURES:
        return hidden_baseline_results()[fixture_id]
    return None
