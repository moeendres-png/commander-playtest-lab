#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ws22_semantic_fixtures import run_semantic_fixture

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import FullGameProtocolError, _RawFullGameClient
from commander_lab.engine.rules.full_game_ws18 import FullGamePilotBindingV2, XmageFullGameRunnerV2
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

PROTOCOL = "commander-lab.rules-service/1.1.0"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"
WS18_PARENT = "b48c5ff3e54b492f172760d66a669156b85bc037"
CANDIDATE = "XMAGE_WS22"
ROOT = Path(__file__).resolve().parents[2]
PLAYER_COUNT_FIXTURES = {
    "PLAYER_COUNT_2P": 2,
    "PLAYER_COUNT_3P": 3,
    "PLAYER_COUNT_4P": 4,
    "PLAYER_COUNT_5P": 5,
}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
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


def _base_response(
    request: dict[str, Any],
    message_type: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
    actor_id: str | None = None,
    state_revision: int | None = None,
) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "message_type": message_type,
        "request_id": str(request.get("request_id", "missing-request-id")),
        "session_id": session_id if session_id is not None else request.get("session_id"),
        "actor_id": actor_id if actor_id is not None else request.get("actor_id"),
        "state_revision": state_revision,
        "payload": payload,
    }


def _error(
    request: dict[str, Any],
    code: str,
    message: str,
    *,
    terminal: bool = False,
    session_id: str | None = None,
    state_revision: int | None = None,
) -> dict[str, Any]:
    return _base_response(
        request,
        "ERROR",
        {"error_code": code, "message": message, "retryable": False, "terminal": terminal},
        session_id=session_id,
        state_revision=state_revision,
    )


def _metadata() -> dict[str, Any]:
    return {
        "provider_id": CANDIDATE,
        "engine_id": "xmage",
        "engine_version": "1.4.61",
        "engine_source_commit": XMAGE_COMMIT,
        "engine_source_tree": XMAGE_TREE,
        "candidate_parent_commit": WS18_PARENT,
        "adapter_source_commit": os.environ.get("GITHUB_SHA", "UNRESOLVED_OUTSIDE_CI"),
        "protocol_version": PROTOCOL,
        "supported_player_counts": [2, 3, 4, 5],
        "one_game_per_rules_process": True,
        "rules_authority": "xmage",
        "decision_authority": "external_rsp_client",
        "observation_authority": "xmage_knowledge_ledger",
        "typed_fail_closed": True,
        "bit_exact_replay_claimed": False,
    }


def _deck_for_player_count(seat: int, player_count: int) -> RulesDeckInput:
    deck_id = f"ws22-technical-isamaru-{player_count}p-seat-{seat}"
    commander = ("Isamaru, Hound of Konda",)
    mainboard = tuple("Plains" for _ in range(99))
    material = {"deck_id": deck_id, "commander_names": commander, "mainboard": mainboard}
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"WS-22 technical Isamaru {player_count}P seat {seat}",
        commander_names=commander,
        mainboard=mainboard,
        deck_hash=_sha256(material),
        source_path="synthetic:ws22-player-count-runtime-only",
    )


def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBindingV2:
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
        decision_policy_version="xmage-ws22-player-count-policy-1.0.0",
    )


def _run_player_count_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(fixture.get("fixture_id", ""))
    expected_count = PLAYER_COUNT_FIXTURES[fixture_id]
    requested_count = int(fixture.get("player_count", -1))
    if requested_count != expected_count:
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": f"Fixture cardinality mismatch: {fixture_id} expects {expected_count}, got {requested_count}.",
            "artifact_hashes": {},
        }
    decks = tuple(
        _deck_for_player_count(seat, expected_count) for seat in range(1, expected_count + 1)
    )
    pilots = tuple(_binding(seat, decks[seat - 1]) for seat in range(1, expected_count + 1))
    own = decks[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=expected_count,
        seat=1,
        scenario_id=f"ws22-rsp-{fixture_id.lower()}",
        seed=int(fixture.get("seed", 424242)),
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-ws22-player-count-policy-1.0.0",
    )
    result = XmageFullGameRunnerV2(
        cwd=ROOT, request_timeout_seconds=120.0, max_decisions=50_000
    ).run(scenario=scenario, decks=decks, pilots=pilots)
    outcomes = result.result_payload.get("outcomes")
    if (
        not result.terminal
        or result.decision_count <= 0
        or not isinstance(outcomes, list)
        or len(outcomes) != expected_count
    ):
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": f"XMage {expected_count}P lifecycle did not satisfy terminal/decision/outcome invariants.",
            "artifact_hashes": {},
        }
    return {
        "verdict": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": f"Real isolated XMage {expected_count}P Commander lifecycle reached terminal state with {result.decision_count} external decisions.",
        "artifact_hashes": {
            "semantic_transcript_sha256": result.semantic_transcript_sha256,
            "raw_result_sha256": result.raw_result_sha256,
        },
    }


@dataclass
class DecisionBinding:
    external_decision_id: str
    native_decision_id: str
    native_actor_id: str
    actor_id: str
    state_revision: int
    options_digest: str
    external_to_native: dict[str, str]


@dataclass
class Session:
    session_id: str
    players: list[dict[str, Any]]
    seed: int
    client: _RawFullGameClient
    state_revision: int = 0
    decision_index: int = 0
    semantic_id_index: int = 0
    native_to_semantic_id: dict[str, str] = field(default_factory=dict)
    pending: DecisionBinding | None = None
    last_status: dict[str, Any] = field(default_factory=dict)
    terminal: bool = False

    def player_id_for_zero_seat(self, seat: int) -> str:
        if seat < 0 or seat >= len(self.players):
            raise FullGameProtocolError(
                f"COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: invalid native seat {seat}"
            )
        return str(self.players[seat]["player_id"])

    def zero_seat_for_player_id(self, player_id: str) -> int:
        for index, player in enumerate(self.players):
            if str(player["player_id"]) == player_id:
                return index
        raise FullGameProtocolError(f"UNKNOWN_ACTOR: {player_id}")

    def semantic_id(self, native: str) -> str:
        existing = self.native_to_semantic_id.get(native)
        if existing is not None:
            return existing
        self.semantic_id_index += 1
        semantic = f"object-{self.semantic_id_index:06d}"
        self.native_to_semantic_id[native] = semantic
        return semantic

    def sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, child in value.items():
                if (
                    key == "seat" or key in {"viewer_seat", "decision_subject_seat"}
                ) and isinstance(child, int):
                    result[key] = child + 1
                elif key.endswith("player_id") and isinstance(child, str) and _UUID_RE.match(child):
                    result[key] = self.semantic_id(child)
                else:
                    result[key] = self.sanitize(child)
            return result
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, str) and _UUID_RE.match(value):
            return self.semantic_id(value)
        return value

    def refresh_status(self) -> dict[str, Any]:
        if self.terminal:
            return self.last_status
        status = self.client.request("get_full_game_decision")
        self.last_status = status
        self.terminal = bool(status.get("terminal"))
        return status

    def decision_frame(self) -> dict[str, Any] | None:
        status = self.last_status or self.refresh_status()
        failure = status.get("failure")
        if isinstance(failure, dict):
            raise FullGameProtocolError(
                "XMAGE_PROVIDER_FAILURE: " + json.dumps(failure, sort_keys=True)
            )
        native = status.get("decision")
        if not isinstance(native, dict):
            if bool(status.get("terminal")):
                self.terminal = True
                return None
            status = self.refresh_status()
            native = status.get("decision")
            if not isinstance(native, dict):
                return None

        native_decision_id = str(native.get("decision_id", ""))
        native_actor_id = str(native.get("actor_id", ""))
        seat_zero = int(native.get("seat", -1))
        actor_id = self.player_id_for_zero_seat(seat_zero)
        if self.pending is not None and self.pending.native_decision_id == native_decision_id:
            return self._frame(native, self.pending)

        native_options = native.get("legal_options")
        if not isinstance(native_options, list):
            raise FullGameProtocolError(
                "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: legal_options is not an array"
            )
        self.decision_index += 1
        external_decision_id = f"decision-{self.decision_index:08d}"
        external_options: list[dict[str, Any]] = []
        external_to_native: dict[str, str] = {}
        for index, option in enumerate(native_options, start=1):
            if not isinstance(option, dict) or not isinstance(option.get("option_id"), str):
                raise FullGameProtocolError(
                    "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: option lacks provider identity"
                )
            external_id = f"option-{index:04d}"
            external_to_native[external_id] = option["option_id"]
            external_options.append(
                {
                    "option_id": external_id,
                    "option_type": option.get("option_type", "generic"),
                    "label": option.get("label", external_id),
                    "metadata": self.sanitize(option.get("metadata") or {}),
                }
            )
        digest = _sha256(
            {
                "decision_id": external_decision_id,
                "state_revision": self.state_revision,
                "minimum_selections": int(native.get("minimum_selections", 0)),
                "maximum_selections": int(native.get("maximum_selections", 0)),
                "options": external_options,
            }
        )
        binding = DecisionBinding(
            external_decision_id=external_decision_id,
            native_decision_id=native_decision_id,
            native_actor_id=native_actor_id,
            actor_id=actor_id,
            state_revision=self.state_revision,
            options_digest=digest,
            external_to_native=external_to_native,
        )
        self.pending = binding
        return self._frame(native, binding, external_options)

    def _frame(
        self,
        native: dict[str, Any],
        binding: DecisionBinding,
        external_options: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if external_options is None:
            reverse = {
                native_id: external_id
                for external_id, native_id in binding.external_to_native.items()
            }
            external_options = []
            for option in native.get("legal_options") or []:
                if not isinstance(option, dict):
                    continue
                native_id = str(option.get("option_id", ""))
                external_id = reverse.get(native_id)
                if external_id is None:
                    raise FullGameProtocolError(
                        "STALE_DECISION: native option set changed while pending"
                    )
                external_options.append(
                    {
                        "option_id": external_id,
                        "option_type": option.get("option_type", "generic"),
                        "label": option.get("label", external_id),
                        "metadata": self.sanitize(option.get("metadata") or {}),
                    }
                )
        subject_seat_zero = int(native.get("decision_subject_seat", native.get("seat", -1)))
        subject_id = self.player_id_for_zero_seat(subject_seat_zero)
        return {
            "decision_id": binding.external_decision_id,
            "state_revision": binding.state_revision,
            "options_digest": binding.options_digest,
            "decision_class": native.get("decision_class"),
            "decision_subject_player_id": subject_id,
            "decision_authority_player_id": binding.actor_id,
            "viewer_player_id": binding.actor_id,
            "minimum_selections": int(native.get("minimum_selections", 0)),
            "maximum_selections": int(native.get("maximum_selections", 0)),
            "prompt": native.get("prompt", ""),
            "context": self.sanitize(native.get("context") or {}),
            "legal_options": external_options,
            "source_object": self.sanitize(native.get("source_object")),
            "observation": self.sanitize(native.get("pilot_state") or {}),
        }


class Provider:
    def __init__(self) -> None:
        self.session: Session | None = None

    def close(self) -> None:
        if self.session is not None:
            self.session.client.close()
            self.session = None

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("protocol") != PROTOCOL:
            return _error(
                request, "PROTOCOL_VERSION_MISMATCH", f"expected {PROTOCOL}", terminal=True
            )
        message_type = str(request.get("message_type", ""))
        try:
            if message_type == "HELLO_REQUEST":
                return _base_response(
                    request, "HELLO_RESPONSE", {"metadata": _metadata()}, state_revision=0
                )
            if message_type == "OPEN_SESSION":
                return self._open(request)
            if message_type == "OBSERVE":
                return self._observe(request)
            if message_type == "NEXT_DECISION":
                return self._next_decision(request)
            if message_type == "SUBMIT_DECISION":
                return self._submit(request)
            if message_type == "CLOSE_SESSION":
                return self._close(request)
            if message_type == "RUN_FIXTURE":
                return self._run_fixture(request)
            return _error(
                request,
                "UNSUPPORTED_MESSAGE_TYPE",
                f"unsupported RSP message type {message_type!r}",
            )
        except FullGameProtocolError as exc:
            text = str(exc)
            code = (
                "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"
                if "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER" in text
                else "PROVIDER_FAILURE"
            )
            return _error(
                request,
                code,
                text,
                terminal=True,
                session_id=None if self.session is None else self.session.session_id,
                state_revision=None if self.session is None else self.session.state_revision,
            )
        except Exception as exc:
            return _error(
                request,
                "PROVIDER_FAILURE",
                f"{type(exc).__name__}: {exc}",
                terminal=True,
                session_id=None if self.session is None else self.session.session_id,
                state_revision=None if self.session is None else self.session.state_revision,
            )

    def _require_session(self, request: dict[str, Any]) -> Session:
        if self.session is None:
            raise FullGameProtocolError("SESSION_NOT_OPEN")
        if request.get("session_id") != self.session.session_id:
            raise FullGameProtocolError(
                f"SESSION_ID_MISMATCH: expected {self.session.session_id!r}"
            )
        return self.session

    def _open(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.session is not None:
            return _error(
                request, "SESSION_ALREADY_OPEN", "one XMage game per rules process", terminal=True
            )
        payload = request.get("payload")
        if not isinstance(payload, dict):
            return _error(request, "INVALID_REQUEST", "OPEN_SESSION payload must be an object")
        session_id = str(request.get("session_id") or payload.get("session_id") or "").strip()
        players = payload.get("players")
        if not session_id or not isinstance(players, list) or len(players) not in {2, 3, 4, 5}:
            return _error(
                request,
                "INVALID_REQUEST",
                "OPEN_SESSION requires session_id and exactly 2 through 5 players",
            )
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, player in enumerate(players, start=1):
            if not isinstance(player, dict):
                return _error(request, "INVALID_REQUEST", f"players[{index - 1}] must be an object")
            player_id = str(player.get("player_id", "")).strip()
            seat = int(player.get("seat", index))
            deck = player.get("deck")
            if not player_id or player_id in seen or seat != index or not isinstance(deck, dict):
                return _error(
                    request,
                    "INVALID_REQUEST",
                    "players require unique player_id, contiguous 1-based seat, and deck",
                )
            seen.add(player_id)
            normalized.append({"player_id": player_id, "seat": seat, "deck": deck})
        seed = int(payload.get("seed", 0))
        starting_seat_one = int(payload.get("starting_player_seat", 1))
        if starting_seat_one < 1 or starting_seat_one > len(normalized):
            return _error(request, "INVALID_REQUEST", "starting_player_seat outside session")

        client = _RawFullGameClient(_bridge_command(), cwd=ROOT, request_timeout_seconds=120.0)
        try:
            started = client.request("start_engine")
            if started.get("lane") != "xmage_full_game_external_pilots":
                raise FullGameProtocolError("bridge did not enter full-game lane")
            provider = client.request("get_provider_version")
            if provider.get("engine_commit") != XMAGE_COMMIT:
                raise FullGameProtocolError("XMAGE_BUILD_IDENTITY_MISMATCH")
            handles: list[str] = []
            for player in normalized:
                imported = client.request("import_deck", {"deck": player["deck"]})
                handle = imported.get("deck_handle")
                if not isinstance(handle, dict) or not isinstance(handle.get("handle_id"), str):
                    raise FullGameProtocolError("IMPORT_DECK returned no stable handle")
                handles.append(handle["handle_id"])
            created = client.request(
                "create_full_game",
                {
                    "game_id": session_id,
                    "deck_handles": handles,
                    "seed": seed,
                    "starting_player_seat": starting_seat_one - 1,
                    "starting_life": int(payload.get("starting_life", 40)),
                },
            )
            if created.get("player_count") != len(normalized):
                raise FullGameProtocolError("SESSION_CARDINALITY_MISMATCH")
            status = client.request("start_full_game")
            self.session = Session(
                session_id=session_id,
                players=normalized,
                seed=seed,
                client=client,
                last_status=status,
            )
            self.session.terminal = bool(status.get("terminal"))
        except Exception:
            client.close()
            raise
        return _base_response(
            request,
            "SESSION_OPENED",
            {
                "metadata": _metadata(),
                "player_count": len(normalized),
                "players": [{"player_id": p["player_id"], "seat": p["seat"]} for p in normalized],
                "seed": seed,
                "starting_player_seat": starting_seat_one,
            },
            session_id=session_id,
            state_revision=0,
        )

    def _observe(self, request: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(request)
        viewer_id = str(request.get("actor_id") or "").strip()
        if not viewer_id:
            return _error(
                request,
                "INVALID_REQUEST",
                "OBSERVE requires actor_id",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        payload = request.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        subject_id = str(payload.get("decision_subject_player_id") or viewer_id)
        viewer_zero = session.zero_seat_for_player_id(viewer_id)
        subject_zero = session.zero_seat_for_player_id(subject_id)
        native = session.client.request(
            "get_full_game_observation",
            {"viewer_seat": viewer_zero, "decision_subject_seat": subject_zero},
        )
        observation = session.sanitize(native.get("observation") or {})
        return _base_response(
            request,
            "OBSERVATION",
            {
                "viewer_player_id": viewer_id,
                "decision_subject_player_id": subject_id,
                "observation": observation,
                "terminal": bool(native.get("terminal")),
            },
            session_id=session.session_id,
            actor_id=viewer_id,
            state_revision=session.state_revision,
        )

    def _next_decision(self, request: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(request)
        frame = session.decision_frame()
        if frame is None:
            if session.terminal:
                result = session.client.request("get_full_game_result")
                return _base_response(
                    request,
                    "DECISION_FRAME",
                    {
                        "terminal": True,
                        "terminal_result": session.sanitize(result),
                        "decision": None,
                    },
                    session_id=session.session_id,
                    state_revision=session.state_revision,
                )
            return _error(
                request,
                "NO_DECISION_AVAILABLE",
                "XMage has no pending decision and is not terminal",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        return _base_response(
            request,
            "DECISION_FRAME",
            {"terminal": False, "decision": frame},
            session_id=session.session_id,
            actor_id=str(frame["decision_authority_player_id"]),
            state_revision=session.state_revision,
        )

    def _submit(self, request: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(request)
        payload = request.get("payload")
        if not isinstance(payload, dict) or session.pending is None:
            return _error(
                request,
                "STALE_DECISION",
                "no pending decision",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        binding = session.pending
        if payload.get("decision_id") != binding.external_decision_id:
            return _error(
                request,
                "STALE_DECISION",
                "decision_id does not match pending frame",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        if (
            int(payload.get("state_revision", -1)) != binding.state_revision
            or payload.get("options_digest") != binding.options_digest
        ):
            return _error(
                request,
                "STALE_DECISION",
                "revision/options digest does not match pending frame",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        selected_external = payload.get("selected_option_ids") or []
        ordering_external = payload.get("ordering") or []
        if not isinstance(selected_external, list) or not isinstance(ordering_external, list):
            return _error(
                request,
                "INVALID_DECISION",
                "selected_option_ids and ordering must be arrays",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        try:
            selected_native = [binding.external_to_native[str(item)] for item in selected_external]
            ordering_native = [binding.external_to_native[str(item)] for item in ordering_external]
        except KeyError as exc:
            return _error(
                request,
                "ILLEGAL_ACTION",
                f"option was not offered: {exc.args[0]}",
                session_id=session.session_id,
                state_revision=session.state_revision,
            )
        native_response: dict[str, Any] = {
            "decision_id": binding.native_decision_id,
            "actor_id": binding.native_actor_id,
            "selected_option_ids": selected_native,
            "ordering": ordering_native,
        }
        if payload.get("numeric_choice") is not None:
            native_response["numeric_choice"] = int(payload["numeric_choice"])
        status = session.client.request("submit_full_game_decision", {"response": native_response})
        session.state_revision += 1
        session.pending = None
        session.last_status = status
        session.terminal = bool(status.get("terminal"))
        return _base_response(
            request,
            "DECISION_ACCEPTED",
            {"decision_id": binding.external_decision_id, "terminal": session.terminal},
            session_id=session.session_id,
            actor_id=binding.actor_id,
            state_revision=session.state_revision,
        )

    def _close(self, request: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(request)
        session_id = session.session_id
        revision = session.state_revision
        session.client.close()
        self.session = None
        return _base_response(
            request,
            "SESSION_CLOSED",
            {"closed": True},
            session_id=session_id,
            state_revision=revision,
        )

    def _run_fixture(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = request.get("payload")
        fixture = payload.get("fixture") if isinstance(payload, dict) else None
        if not isinstance(fixture, dict):
            return _base_response(
                request,
                "FIXTURE_RESULT",
                {
                    "verdict": "FAIL",
                    "evidence_class": "RUNTIME_VERIFIED",
                    "reason": "RUN_FIXTURE payload.fixture is required",
                    "artifact_hashes": {},
                },
            )
        fixture_id = str(fixture.get("fixture_id", ""))
        if fixture_id in PLAYER_COUNT_FIXTURES:
            try:
                result = _run_player_count_fixture(fixture)
            except Exception as exc:
                result = {
                    "verdict": "FAIL",
                    "evidence_class": "RUNTIME_VERIFIED",
                    "reason": f"XMage runtime fixture raised {type(exc).__name__}: {exc}",
                    "artifact_hashes": {},
                }
            return _base_response(request, "FIXTURE_RESULT", result)

        try:
            semantic_result = run_semantic_fixture(fixture_id)
        except Exception as exc:
            semantic_result = {
                "verdict": "FAIL",
                "evidence_class": "RUNTIME_VERIFIED",
                "reason": f"XMage semantic runtime fixture raised {type(exc).__name__}: {exc}",
                "artifact_hashes": {},
            }
        if semantic_result is not None:
            return _base_response(request, "FIXTURE_RESULT", semantic_result)

        return _base_response(
            request,
            "FIXTURE_RESULT",
            {
                "verdict": "NOT_RUN",
                "evidence_class": "NOT_RUN",
                "reason": f"WS-22 fixture {fixture_id} has not yet been runtime-materialized; no source-derived PASS is allowed.",
                "artifact_hashes": {},
            },
        )


def main() -> int:
    provider = Provider()
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise TypeError("request must be an object")
                response = provider.handle(request)
            except Exception as exc:
                response = {
                    "protocol": PROTOCOL,
                    "message_type": "ERROR",
                    "request_id": "unparsed-request",
                    "session_id": None,
                    "actor_id": None,
                    "state_revision": None,
                    "payload": {
                        "error_code": "INVALID_JSON",
                        "message": f"{type(exc).__name__}: {exc}",
                        "retryable": False,
                        "terminal": False,
                    },
                }
            print(json.dumps(response, sort_keys=True), flush=True)
    finally:
        provider.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
