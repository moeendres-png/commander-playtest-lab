from __future__ import annotations

import contextlib
import hashlib
import json
import os
import queue
import random
import shlex
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.agents import BasePilot, build_pilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    CardRole,
    EngineProtocolResponse,
    PilotActionView,
    PilotCommanderView,
    PilotConfig,
    PilotOpponentView,
    PilotStateView,
    RulesDeckInput,
)

FULL_GAME_DECISION_PROTOCOL_VERSION = "xmage-external-decision-protocol-1.0.0"
FULL_GAME_LANE = "xmage_full_game_external_pilots"
FULL_GAME_EVIDENCE_CLASS: Literal["technical_conformance_only"] = "technical_conformance_only"
XMAGE_FULL_GAME_COMMAND_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"


class FullGameProtocolError(RuntimeError):
    """Fail-closed full-game bridge or external-pilot protocol error."""


class FullGameConformanceError(RuntimeError):
    """A run violated a full-game conformance invariant."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FullGamePilotBinding(_StrictModel):
    seat: int = Field(ge=1, le=4)
    deck_id: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    commander_names: tuple[str, ...]
    config: PilotConfig
    pilot_identity: str = Field(min_length=1)
    pilot_version: str = Field(min_length=1)
    decision_policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def identity_matches_config(self) -> FullGamePilotBinding:
        requested = self.config.pilot_name.casefold().strip()
        if requested != "auto" and requested != self.pilot_identity.casefold().strip():
            raise ValueError("pilot_identity must match explicit PilotConfig.pilot_name")
        if not self.commander_names:
            raise ValueError("commander_names must not be empty")
        return self


class FullGameConformanceResult(_StrictModel):
    schema_version: Literal["xmage-full-game-conformance-result-1.0.0"] = (
        "xmage-full-game-conformance-result-1.0.0"
    )
    scenario: FutureXmageScenario
    engine_version: str
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_protocol_version: str
    decision_count: int = Field(ge=0)
    terminal: bool
    winner_seats: tuple[int, ...]
    result_payload: dict[str, Any]
    semantic_transcript_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    structural_decision_authority: Literal[False] = False
    tactical_decision_authority: Literal[False] = False
    xmage_rules_authority: Literal[True] = True
    commander_lab_pilot_decision_authority: Literal[True] = True
    hidden_information_actor_scoped: Literal[True] = True
    fallback_used: Literal[False] = False
    bit_exact_replay_validated: Literal[False] = False


class FullGameReplayGate(_StrictModel):
    schema_version: Literal["xmage-full-game-replay-gate-1.0.0"] = (
        "xmage-full-game-replay-gate-1.0.0"
    )
    scenario_id: str
    seed: int = Field(ge=0)
    semantic_replay_match: bool
    raw_result_match: bool
    first_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    second_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    second_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bit_exact_replay_validated: Literal[False] = False
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class _RuntimePilot:
    binding: FullGamePilotBinding
    pilot: BasePilot


class _RawFullGameClient:
    """One-process client for the dedicated XMage full-game lane."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
    ) -> None:
        if not command:
            raise ValueError("full-game bridge command must not be empty")
        if "full-game" not in command:
            raise ValueError(
                "full-game bridge command must explicitly include the full-game subcommand"
            )
        self.command = command
        self.cwd = None if cwd is None else str(cwd)
        self.request_timeout_seconds = request_timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_lines[-80:])

    def start(self) -> None:
        if self._process is not None:
            if self._process.poll() is None:
                return
            raise FullGameProtocolError(
                f"full-game bridge already exited with code {self._process.returncode}"
            )
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise FullGameProtocolError(f"unable to start full-game bridge: {exc}") from exc
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._stdout_thread = threading.Thread(
            target=self._pump_stdout,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._pump_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.start()
        process = self._process
        assert process is not None
        if process.poll() is not None or process.stdin is None:
            raise FullGameProtocolError(
                "full-game bridge is not writable: " + " | ".join(self.stderr_tail)
            )
        request_id = str(uuid.uuid4())
        body = payload or {}
        request = {
            "protocol_version": ENGINE_PROTOCOL_VERSION,
            "request_id": request_id,
            "engine": "xmage",
            "message_type": message_type,
            "method": message_type,
            "payload": body,
            "params": body,
        }
        process.stdin.write(json.dumps(request, sort_keys=True) + "\n")
        process.stdin.flush()
        try:
            line = self._stdout_queue.get(timeout=self.request_timeout_seconds)
        except queue.Empty as exc:
            raise FullGameProtocolError(
                f"full-game bridge timeout for {message_type!r}; stderr="
                + " | ".join(self.stderr_tail)
            ) from exc
        if line is None:
            raise FullGameProtocolError(
                f"full-game bridge closed before replying to {message_type!r}: "
                + " | ".join(self.stderr_tail)
            )
        try:
            response = EngineProtocolResponse.from_wire(json.loads(line))
        except Exception as exc:
            raise FullGameProtocolError(
                f"invalid full-game bridge response for {message_type!r}: {line!r}"
            ) from exc
        if response.protocol_version != ENGINE_PROTOCOL_VERSION:
            raise FullGameProtocolError(
                f"protocol mismatch: expected {ENGINE_PROTOCOL_VERSION}, "
                f"received {response.protocol_version}"
            )
        if response.request_id != request_id:
            raise FullGameProtocolError("full-game bridge response request_id mismatch")
        if not response.success:
            error = response.errors[0] if response.errors else None
            detail = "unknown bridge error" if error is None else f"{error.code}: {error.message}"
            raise FullGameProtocolError(f"{message_type} failed: {detail}")
        return response.payload

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            with contextlib.suppress(Exception):
                self.request("shutdown_engine")
        if process.poll() is None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                with contextlib.suppress(OSError):
                    stream.close()
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None:
                thread.join(timeout=2)
        self._process = None

    def _pump_stdout(self, stream: Any) -> None:
        try:
            for line in iter(stream.readline, ""):
                self._stdout_queue.put(line)
        finally:
            self._stdout_queue.put(None)

    def _pump_stderr(self, stream: Any) -> None:
        for line in iter(stream.readline, ""):
            self._stderr_lines.append(line.rstrip("\n"))

    def __enter__(self) -> _RawFullGameClient:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class ExternalPilotDecisionPolicy:
    """Decision-complete adapter from XMage typed choices to Commander Lab pilots.

    This is the primary policy, not a fallback. Every supported decision class
    has an explicit deterministic/stochastic rule. Unknown classes fail closed.
    """

    _SUPPORTED_CLASSES = frozenset(
        {
            "priority",
            "target",
            "choose_object",
            "target_amount",
            "mulligan",
            "choose_use",
            "choice",
            "pile",
            "mana_payment",
            "announce_x",
            "amount",
            "multi_amount",
            "replacement_effect",
            "trigger_order",
            "mode",
            "declare_attacker",
            "declare_blocker",
        }
    )

    def __init__(self, runtime_pilots: tuple[_RuntimePilot, ...], scenario_seed: int) -> None:
        if len(runtime_pilots) != 4:
            raise ValueError("full-game policy requires exactly four pilot bindings")
        seats = {item.binding.seat for item in runtime_pilots}
        if seats != {1, 2, 3, 4}:
            raise ValueError("full-game pilot bindings must cover seats 1..4 exactly")
        self._pilots = {item.binding.seat: item for item in runtime_pilots}
        self.scenario_seed = scenario_seed
        self._mulligan_count: dict[int, int] = {seat: 0 for seat in range(1, 5)}

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        decision_id = self._required_text(request, "decision_id")
        actor_id = self._required_text(request, "actor_id")
        decision_class = self._required_text(request, "decision_class")
        if decision_class not in self._SUPPORTED_CLASSES:
            raise FullGameProtocolError(
                f"unsupported discretionary decision class: {decision_class}"
            )
        pilot_state = self._required_object(request, "pilot_state")
        seat = int(pilot_state.get("seat", -1)) + 1
        runtime = self._pilots.get(seat)
        if runtime is None:
            raise FullGameProtocolError(f"decision actor has unmapped seat: {seat}")
        options = self._legal_options(request)
        context = dict(request.get("context") or {})
        min_selections = int(request.get("min_selections", 0))
        max_selections = int(request.get("max_selections", 0))
        rng = self._rng(decision_id, seat)

        selected: list[str] = []
        numeric_choice: int | None = None

        if decision_class == "mulligan":
            selected = [self._decide_mulligan(runtime, pilot_state, options, rng)]
        elif decision_class in {"announce_x", "amount", "multi_amount"}:
            numeric_choice = self._decide_numeric(context)
        elif decision_class == "mana_payment":
            selected = [self._decide_mana(options)]
        elif decision_class == "choose_use":
            selected = [self._decide_boolean(options, context)]
        elif decision_class == "pile":
            selected = [self._decide_pile(options, context)]
        elif decision_class in {"choice", "replacement_effect", "trigger_order", "mode"}:
            selected = [self._decide_semantic_option(runtime, pilot_state, options, rng)]
        elif decision_class == "priority":
            selected = [self._decide_priority(runtime, pilot_state, options, rng)]
        elif decision_class in {"target", "choose_object", "target_amount"}:
            selected = self._decide_targets(
                runtime,
                pilot_state,
                request,
                options,
                min_selections,
                max_selections,
                rng,
            )
            if decision_class == "target_amount":
                numeric_choice = self._decide_numeric(context)
        elif decision_class == "declare_attacker":
            selected = [self._decide_attack(runtime, pilot_state, options, rng)]
        elif decision_class == "declare_blocker":
            selected = self._decide_blocks(
                runtime,
                pilot_state,
                options,
                min_selections,
                max_selections,
                rng,
            )
        else:  # pragma: no cover - guarded by exhaustive supported class set
            raise FullGameProtocolError(f"unhandled decision class: {decision_class}")

        if len(selected) < min_selections or len(selected) > max_selections:
            raise FullGameProtocolError(
                f"policy produced {len(selected)} selections outside "
                f"{min_selections}..{max_selections} for {decision_class}"
            )

        response: dict[str, Any] = {
            "decision_id": decision_id,
            "actor_id": actor_id,
            "selected_option_ids": selected,
            "ordering": [],
        }
        if numeric_choice is not None:
            response["numeric_choice"] = numeric_choice
        return response

    def _decide_mulligan(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        seat = runtime.binding.seat
        actor = self._actor(state)
        hand = actor.get("hand")
        if not isinstance(hand, list):
            raise FullGameProtocolError("mulligan requires actor hand visibility")
        cards = tuple(self._hand_action(card) for card in hand if isinstance(card, dict))
        keep, _score = runtime.pilot.should_keep_opening_hand(
            cards,
            mulligans=self._mulligan_count[seat],
            free_first=True,
            commander_names=runtime.binding.commander_names,
            rng=rng,
        )
        desired = "keep" if keep else "mulligan"
        chosen = self._option_by_type(options, desired)
        if desired == "mulligan":
            self._mulligan_count[seat] += 1
        return self._required_text(chosen, "option_id")

    def _decide_priority(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        pass_option = self._option_by_type(options, "pass_priority")
        non_mana = [
            option
            for option in options
            if self._required_text(option, "option_type") not in {"pass_priority", "mana_ability"}
        ]
        if not non_mana:
            return self._required_text(pass_option, "option_id")

        pilot_state = self._pilot_state(runtime, state)
        action_views = [self._priority_action(option, state) for option in non_mana]
        action_views.append(
            PilotActionView(
                action_id=self._required_text(pass_option, "option_id"),
                action_kind="pass",
                card_name="Pass priority",
                floor_value=0.15,
                immediate_impact=0.0,
                metadata={"flexible_interaction": bool(state.get("stack"))},
            )
        )
        decision = runtime.pilot.choose_action(pilot_state, action_views, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no priority action")
        return decision.selected_action_id

    def _decide_targets(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        request: dict[str, Any],
        options: list[dict[str, Any]],
        min_selections: int,
        max_selections: int,
        rng: random.Random,
    ) -> list[str]:
        prompt = str(request.get("prompt", "")).casefold()
        if "bottom" in prompt and "library" in prompt:
            actor = self._actor(state)
            hand = actor.get("hand")
            if not isinstance(hand, list):
                raise FullGameProtocolError("London bottom decision requires actor hand visibility")
            count = min_selections
            card_actions = tuple(self._hand_action(card) for card in hand if isinstance(card, dict))
            selected = runtime.pilot.choose_bottom_cards(
                card_actions,
                count,
                commander_names=runtime.binding.commander_names,
            )
            legal_ids = {self._required_text(option, "option_id") for option in options}
            if not set(selected).issubset(legal_ids):
                raise FullGameProtocolError("pilot bottom-card selection is not XMage-legal")
            return list(selected)

        if not options:
            return []
        outcome = str((request.get("context") or {}).get("outcome", "neutral")).casefold()
        pilot_state = self._pilot_state(runtime, state)
        ranked: list[tuple[float, str]] = []
        for option in options:
            action = self._target_action(option, state, outcome)
            breakdown = runtime.pilot.evaluate_action(pilot_state, action)
            score = breakdown.total_utility + self._target_alignment(action, state, outcome)
            ranked.append((score, action.action_id))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

        if max_selections <= 0:
            return []
        if outcome in {"benefit", "benefit_to_controller"}:
            take = max_selections
        elif min_selections == 0:
            take = 0 if all(score < 0.0 for score, _ in ranked) else 1
        else:
            take = min_selections
        take = max(min_selections, min(max_selections, take))
        return [option_id for _score, option_id in ranked[:take]]

    def _decide_semantic_option(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("semantic decision has no legal options")
        pilot_state = self._pilot_state(runtime, state)
        actions = [self._semantic_action(option) for option in options]
        decision = runtime.pilot.choose_action(pilot_state, actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no semantic option")
        return decision.selected_action_id

    def _decide_boolean(self, options: list[dict[str, Any]], context: dict[str, Any]) -> str:
        outcome = str(context.get("outcome", "neutral")).casefold()
        desired = outcome not in {"detriment", "detriment_to_controller"}
        for option in options:
            metadata = option.get("metadata")
            if isinstance(metadata, dict) and metadata.get("value") is desired:
                return self._required_text(option, "option_id")
        raise FullGameProtocolError("boolean decision lacks matching explicit value option")

    def _decide_pile(self, options: list[dict[str, Any]], context: dict[str, Any]) -> str:
        if not options:
            raise FullGameProtocolError("pile decision has no legal options")
        outcome = str(context.get("outcome", "benefit")).casefold()
        scored: list[tuple[int, str]] = []
        for option in options:
            metadata = option.get("metadata")
            cards = metadata.get("cards", []) if isinstance(metadata, dict) else []
            size = len(cards) if isinstance(cards, list) else 0
            scored.append((size, self._required_text(option, "option_id")))
        reverse = outcome not in {"detriment", "detriment_to_controller"}
        scored.sort(key=lambda item: (item[0], item[1]), reverse=reverse)
        return scored[0][1]

    def _decide_mana(self, options: list[dict[str, Any]]) -> str:
        mana = [
            option
            for option in options
            if self._required_text(option, "option_type") == "mana_ability"
        ]
        if mana:
            mana.sort(key=lambda item: self._required_text(item, "option_id"))
            return self._required_text(mana[0], "option_id")
        cancel = self._option_by_type(options, "cancel_mana_payment")
        return self._required_text(cancel, "option_id")

    def _decide_numeric(self, context: dict[str, Any]) -> int:
        if "numeric_min" not in context or "numeric_max" not in context:
            raise FullGameProtocolError("numeric decision missing explicit bounds")
        minimum = int(context["numeric_min"])
        maximum = int(context["numeric_max"])
        if maximum < minimum:
            raise FullGameProtocolError("numeric decision has reversed bounds")
        outcome = str(context.get("outcome", "benefit")).casefold()
        return minimum if outcome in {"detriment", "detriment_to_controller"} else maximum

    def _decide_attack(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        hold = self._option_by_type(options, "hold_attacker")
        attacks = [
            option
            for option in options
            if self._required_text(option, "option_type") == "declare_attacker"
        ]
        if not attacks:
            return self._required_text(hold, "option_id")
        pilot_state = self._pilot_state(runtime, state)
        actions = [self._combat_action(option, state) for option in attacks]
        actions.append(
            PilotActionView(
                action_id=self._required_text(hold, "option_id"),
                action_kind="pass",
                card_name="Hold attacker",
                floor_value=0.1,
            )
        )
        decision = runtime.pilot.choose_combat_target(pilot_state, actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no attack decision")
        return decision.selected_action_id

    def _decide_blocks(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        min_selections: int,
        max_selections: int,
        rng: random.Random,
    ) -> list[str]:
        if not options or max_selections == 0:
            return []
        pilot_state = self._pilot_state(runtime, state)
        ranked: list[tuple[float, str]] = []
        for option in options:
            action = self._combat_action(option, state)
            score = runtime.pilot.evaluate_action(pilot_state, action).total_utility
            ranked.append((score, action.action_id))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        actor = self._actor(state)
        life = float(actor.get("life", 40))
        take = max_selections if life <= 15 else min(max_selections, max(min_selections, 1))
        return [option_id for _score, option_id in ranked[:take]]

    def _pilot_state(self, runtime: _RuntimePilot, state: dict[str, Any]) -> PilotStateView:
        actor = self._actor(state)
        actor_id = self._required_text(state, "actor_id")
        opponents: list[PilotOpponentView] = []
        players = state.get("players")
        if not isinstance(players, list):
            raise FullGameProtocolError("pilot_state.players must be an array")
        for raw in players:
            if not isinstance(raw, dict) or raw.get("player_id") == actor_id:
                continue
            battlefield = raw.get("battlefield")
            board_size = len(battlefield) if isinstance(battlefield, list) else 0
            graveyard_count = int(raw.get("graveyard_count", 0))
            life = float(raw.get("life", 40))
            threat = board_size * 0.75 + graveyard_count * 0.08 + max(0.0, 40.0 - life) * 0.04
            opponents.append(
                PilotOpponentView(
                    player_id=self._required_text(raw, "player_id"),
                    life=life,
                    threat=max(0.0, threat),
                    board_power=float(board_size),
                    engine_value=float(board_size) * 0.35,
                    graveyard_size=graveyard_count,
                    hand_size=int(raw.get("hand_count", 0)),
                )
            )
        battlefield = actor.get("battlefield")
        battlefield_items = battlefield if isinstance(battlefield, list) else []
        hand = actor.get("hand")
        hand_items = hand if isinstance(hand, list) else []
        mana_pool = actor.get("mana_pool")
        mana = (
            sum(float(value) for value in mana_pool.values() if isinstance(value, (int, float)))
            if isinstance(mana_pool, dict)
            else 0.0
        )
        command = actor.get("command")
        command_items = command if isinstance(command, list) else []
        commanders = tuple(
            PilotCommanderView(
                name=str(item.get("name", "Unknown commander")),
                base_cost=0.0,
                next_cost=0.0,
                casts=0,
                on_battlefield=False,
            )
            for item in command_items
            if isinstance(item, dict)
        )
        return PilotStateView(
            player_id=actor_id,
            deck_id=runtime.binding.deck_id,
            strategy=runtime.binding.strategy,
            turn=max(1, int(state.get("turn_number", 1))),
            pod_size=4,
            seat_position=runtime.binding.seat,
            life=float(actor.get("life", 40)),
            hand_size=int(actor.get("hand_count", len(hand_items))),
            mana_available=max(0.0, mana),
            lands=sum(
                1
                for item in battlefield_items
                if isinstance(item, dict) and "land" in str(item.get("name", "")).casefold()
            ),
            ramp_mana=0.0,
            resources=float(len(battlefield_items)),
            tokens=0.0,
            board_power=float(len(battlefield_items)),
            engine_value=float(len(battlefield_items)) * 0.35,
            graveyard_size=int(actor.get("graveyard_count", 0)),
            battlefield_names=tuple(
                str(item.get("name", ""))
                for item in battlefield_items
                if isinstance(item, dict) and item.get("name")
            ),
            hand_names=tuple(
                str(item.get("name", ""))
                for item in hand_items
                if isinstance(item, dict) and item.get("name")
            ),
            role_counts={},
            commanders=commanders,
            opponents=tuple(opponents),
            hidden_information_uncertainty=1.0,
            opponent_intent_uncertainty=1.0,
            unknown_opponent_fraction=1.0,
            opponents_to_act_before_next_turn=3,
        )

    def _priority_action(self, option: dict[str, Any], state: dict[str, Any]) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        source_name = str(meta.get("source_name") or option.get("label") or "XMage action")
        source_id = str(meta.get("source_object_id") or "")
        actor = self._actor(state)
        command = actor.get("command")
        command_items = command if isinstance(command, list) else []
        command_ids = {
            str(item.get("object_id")) for item in command_items if isinstance(item, dict)
        }
        action_kind: Literal["card", "commander"] = (
            "commander" if source_id in command_ids else "card"
        )
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind=action_kind,
            card_name=source_name,
            mana_cost=0.0,
            floor_value=0.65,
            immediate_impact=0.45,
            commander_synergy=0.6 if action_kind == "commander" else 0.15,
            remaining_mana=self._actor_mana(actor),
            metadata={"xmage_option_type": self._required_text(option, "option_type")},
        )

    def _target_action(
        self,
        option: dict[str, Any],
        state: dict[str, Any],
        outcome: str,
    ) -> PilotActionView:
        option_id = self._required_text(option, "option_id")
        owner_id = self._object_owner(option_id, state)
        actor_id = self._required_text(state, "actor_id")
        target_threat = self._player_threat(owner_id, state)
        beneficial = outcome in {"benefit", "benefit_to_controller"}
        roles = frozenset({CardRole.PROTECTION}) if beneficial else frozenset({CardRole.REMOVAL})
        return PilotActionView(
            action_id=option_id,
            action_kind="protection" if beneficial else "removal_target",
            card_name=str(option.get("label", option_id)),
            roles=roles,
            role_strengths={role: 1.0 for role in roles},
            floor_value=0.3,
            immediate_impact=0.6,
            target_player_id=owner_id,
            target_threat=target_threat,
            threat_score=target_threat,
            metadata={"target_is_actor_controlled": owner_id == actor_id},
        )

    def _combat_action(self, option: dict[str, Any], state: dict[str, Any]) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        target_id = str(meta.get("defender_id") or meta.get("attacker_id") or "") or None
        target_threat = self._player_threat(target_id, state)
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="combat_target",
            card_name=str(option.get("label", "Combat")),
            floor_value=0.35,
            immediate_impact=0.8,
            target_player_id=target_id,
            target_threat=target_threat,
            threat_score=target_threat,
            metadata={"target_life": self._player_life(target_id, state)},
        )

    def _semantic_action(self, option: dict[str, Any]) -> PilotActionView:
        label = str(option.get("label", "XMage option"))
        normalized = label.casefold()
        roles: set[CardRole] = set()
        if any(word in normalized for word in ("draw", "card advantage")):
            roles.add(CardRole.DRAW)
        if any(word in normalized for word in ("destroy", "exile", "damage", "counter target")):
            roles.add(CardRole.REMOVAL)
        if any(word in normalized for word in ("create", "token")):
            roles.add(CardRole.TOKEN_SOURCE)
        if any(word in normalized for word in ("return", "graveyard")):
            roles.add(CardRole.RECURSION)
        role_set = frozenset(roles)
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="card",
            card_name=label,
            roles=role_set,
            role_strengths={role: 1.0 for role in role_set},
            floor_value=0.4,
            immediate_impact=0.4 + min(0.5, len(role_set) * 0.15),
        )

    def _hand_action(self, card: dict[str, Any]) -> PilotActionView:
        name = self._required_text(card, "name")
        return PilotActionView(
            action_id=self._required_text(card, "object_id"),
            action_kind="card",
            card_name=name,
            floor_value=0.5,
            immediate_impact=0.3,
            metadata={"is_land": self._looks_like_basic_land(name)},
        )

    def _target_alignment(
        self,
        action: PilotActionView,
        state: dict[str, Any],
        outcome: str,
    ) -> float:
        actor_id = self._required_text(state, "actor_id")
        same = action.target_player_id == actor_id
        if outcome in {"benefit", "benefit_to_controller"}:
            return 8.0 if same else -8.0
        if outcome in {"detriment", "detriment_to_controller"}:
            return -8.0 if same else 8.0
        return 0.0

    def _object_owner(self, object_id: str, state: dict[str, Any]) -> str | None:
        players = state.get("players")
        if not isinstance(players, list):
            return None
        for raw in players:
            if not isinstance(raw, dict):
                continue
            player_id = str(raw.get("player_id", ""))
            if player_id == object_id:
                return player_id
            for zone in ("battlefield", "graveyard", "command", "hand"):
                items = raw.get(zone)
                if not isinstance(items, list):
                    continue
                if any(
                    isinstance(item, dict) and str(item.get("object_id", "")) == object_id
                    for item in items
                ):
                    return player_id
        return None

    def _player_threat(self, player_id: str | None, state: dict[str, Any]) -> float:
        if player_id is None:
            return 0.0
        player = self._player(player_id, state)
        if player is None:
            return 0.0
        battlefield = player.get("battlefield")
        board_size = len(battlefield) if isinstance(battlefield, list) else 0
        return max(
            0.0,
            board_size * 0.8
            + int(player.get("graveyard_count", 0)) * 0.08
            + max(0.0, 40.0 - float(player.get("life", 40))) * 0.04,
        )

    def _player_life(self, player_id: str | None, state: dict[str, Any]) -> float:
        if player_id is None:
            return 40.0
        player = self._player(player_id, state)
        return 40.0 if player is None else float(player.get("life", 40))

    def _player(self, player_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
        players = state.get("players")
        if not isinstance(players, list):
            return None
        return next(
            (
                raw
                for raw in players
                if isinstance(raw, dict) and str(raw.get("player_id")) == player_id
            ),
            None,
        )

    def _actor(self, state: dict[str, Any]) -> dict[str, Any]:
        actor_id = self._required_text(state, "actor_id")
        actor = self._player(actor_id, state)
        if actor is None:
            raise FullGameProtocolError("actor is absent from actor-scoped state")
        return actor

    @staticmethod
    def _actor_mana(actor: dict[str, Any]) -> float:
        mana = actor.get("mana_pool")
        if not isinstance(mana, dict):
            return 0.0
        return max(
            0.0,
            sum(float(value) for value in mana.values() if isinstance(value, (int, float))),
        )

    def _rng(self, decision_id: str, seat: int) -> random.Random:
        digest = hashlib.sha256(f"{self.scenario_seed}:{seat}:{decision_id}".encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    @staticmethod
    def _looks_like_basic_land(name: str) -> bool:
        return name.casefold() in {
            "plains",
            "island",
            "swamp",
            "mountain",
            "forest",
            "wastes",
        }

    @staticmethod
    def _legal_options(request: dict[str, Any]) -> list[dict[str, Any]]:
        raw = request.get("legal_options")
        if not isinstance(raw, list):
            raise FullGameProtocolError("decision legal_options must be an array")
        if not all(isinstance(item, dict) for item in raw):
            raise FullGameProtocolError("decision legal_options contains non-object entries")
        return cast(list[dict[str, Any]], raw)

    @staticmethod
    def _option_by_type(options: list[dict[str, Any]], option_type: str) -> dict[str, Any]:
        matches = [option for option in options if option.get("option_type") == option_type]
        if len(matches) != 1:
            raise FullGameProtocolError(
                f"expected exactly one {option_type!r} option; observed {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _required_text(value: dict[str, Any], key: str) -> str:
        raw = value.get(key)
        text = "" if raw is None else str(raw).strip()
        if not text:
            raise FullGameProtocolError(f"required text field is blank: {key}")
        return text

    @staticmethod
    def _required_object(value: dict[str, Any], key: str) -> dict[str, Any]:
        raw = value.get(key)
        if not isinstance(raw, dict):
            raise FullGameProtocolError(f"required object field missing: {key}")
        return raw


class XmageFullGameRunner:
    """Run one isolated four-player XMage game with Commander Lab pilot policy."""

    def __init__(
        self,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
        max_decisions: int = 50_000,
    ) -> None:
        self.command = command or self.command_from_environment()
        self.cwd = cwd
        self.request_timeout_seconds = request_timeout_seconds
        self.max_decisions = max_decisions
        if self.max_decisions < 1:
            raise ValueError("max_decisions must be positive")

    @staticmethod
    def command_from_environment() -> tuple[str, ...] | None:
        raw = os.getenv(XMAGE_FULL_GAME_COMMAND_ENV)
        return tuple(shlex.split(raw)) if raw else None

    def run(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput],
        pilots: tuple[
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
        ],
    ) -> FullGameConformanceResult:
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        self._validate_inputs(scenario, decks, pilots)
        runtime_pilots = tuple(
            _RuntimePilot(
                binding=binding,
                pilot=build_pilot(binding.config, strategy=binding.strategy),
            )
            for binding in sorted(pilots, key=lambda item: item.seat)
        )
        policy = ExternalPilotDecisionPolicy(runtime_pilots, scenario.seed)

        with _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
        ) as client:
            started = client.request("start_engine")
            if started.get("lane") != FULL_GAME_LANE:
                raise FullGameConformanceError("bridge did not enter explicit full-game lane")
            provider = client.request("get_provider_version")
            capabilities = client.request("get_capabilities")
            self._validate_handshake(scenario, provider, capabilities)

            handles: list[str] = []
            for deck in decks:
                imported = client.request("import_deck", {"deck": self._deck_payload(deck)})
                handle = imported.get("deck_handle")
                if not isinstance(handle, dict):
                    raise FullGameConformanceError("IMPORT_DECK returned no deck_handle")
                handle_id = str(handle.get("handle_id", "")).strip()
                if not handle_id:
                    raise FullGameConformanceError("IMPORT_DECK returned blank handle_id")
                handles.append(handle_id)

            game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
            created = client.request(
                "create_full_game",
                {
                    "game_id": game_id,
                    "deck_handles": handles,
                    "seed": scenario.seed,
                    "starting_player_seat": scenario.seed % 4,
                    "starting_life": 40,
                },
            )
            if created.get("player_count") != 4 or created.get("seed") != scenario.seed:
                raise FullGameConformanceError(
                    "full-game creation did not preserve 4p/seed contract"
                )
            if created.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
                raise FullGameConformanceError("full-game creation returned unsafe evidence class")
            if created.get("holdout_consumed") is not False:
                raise FullGameConformanceError("technical conformance must not consume holdout")

            status = client.request("start_full_game")
            decision_count = 0
            while True:
                failure = status.get("failure")
                if isinstance(failure, dict):
                    raise FullGameConformanceError(
                        "XMage full-game engine failed: " + json.dumps(failure, sort_keys=True)
                    )
                decision = status.get("decision")
                if isinstance(decision, dict):
                    decision_count += 1
                    if decision_count > self.max_decisions:
                        raise FullGameConformanceError(
                            f"full-game exceeded max_decisions={self.max_decisions}"
                        )
                    response = policy.decide(decision)
                    status = client.request(
                        "submit_full_game_decision",
                        {"response": response},
                    )
                    continue
                if bool(status.get("terminal")):
                    break
                status = client.request("get_full_game_decision")

            result = client.request("get_full_game_result")

        return self._build_result(scenario, provider, result)

    def run_replay_gate(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput],
        pilots: tuple[
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
        ],
    ) -> FullGameReplayGate:
        first = self.run(scenario=scenario, decks=decks, pilots=pilots)
        second = self.run(scenario=scenario, decks=decks, pilots=pilots)
        return FullGameReplayGate(
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            semantic_replay_match=(
                first.semantic_transcript_sha256 == second.semantic_transcript_sha256
            ),
            raw_result_match=first.raw_result_sha256 == second.raw_result_sha256,
            first_semantic_sha256=first.semantic_transcript_sha256,
            second_semantic_sha256=second.semantic_transcript_sha256,
            first_raw_sha256=first.raw_result_sha256,
            second_raw_sha256=second.raw_result_sha256,
            bit_exact_replay_validated=False,
        )

    @staticmethod
    def _validate_inputs(
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput],
        pilots: tuple[
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
            FullGamePilotBinding,
        ],
    ) -> None:
        if scenario.player_count != 4 or len(decks) != 4 or len(pilots) != 4:
            raise FullGameConformanceError("operational full-game scope is exactly four players")
        if len({deck.deck_id for deck in decks}) != 4:
            raise FullGameConformanceError("full-game requires four distinct deck identities")
        if {pilot.seat for pilot in pilots} != {1, 2, 3, 4}:
            raise FullGameConformanceError("pilot bindings must cover seats 1..4 exactly")
        for index, (deck, pilot) in enumerate(
            zip(decks, sorted(pilots, key=lambda item: item.seat), strict=True),
            start=1,
        ):
            if deck.deck_id != pilot.deck_id:
                raise FullGameConformanceError(
                    f"seat {index} deck/pilot mismatch: {deck.deck_id} != {pilot.deck_id}"
                )
            if tuple(deck.commander_names) != tuple(pilot.commander_names):
                raise FullGameConformanceError(f"seat {index} commander/pilot mismatch")
            if deck.deck_hash is None:
                raise FullGameConformanceError(f"seat {index} deck_hash is required")
        own = decks[scenario.seat - 1]
        if own.deck_id != scenario.candidate_id:
            raise FullGameConformanceError(
                "FutureXmageScenario candidate_id must occupy the declared scenario seat"
            )
        if own.deck_hash != scenario.deck_hash:
            raise FullGameConformanceError("FutureXmageScenario deck_hash does not match own deck")
        opponent_ids = tuple(
            deck.deck_id for index, deck in enumerate(decks, start=1) if index != scenario.seat
        )
        if opponent_ids != scenario.opponent_deck_ids:
            raise FullGameConformanceError(
                "FutureXmageScenario opponent_deck_ids do not match seat-ordered opponents"
            )
        own_pilot = sorted(pilots, key=lambda item: item.seat)[scenario.seat - 1]
        if own_pilot.pilot_identity != scenario.pilot_identity:
            raise FullGameConformanceError("scenario pilot_identity mismatch")
        if own_pilot.pilot_version != scenario.pilot_version:
            raise FullGameConformanceError("scenario pilot_version mismatch")
        if own_pilot.decision_policy_version != scenario.decision_policy_version:
            raise FullGameConformanceError("scenario decision_policy_version mismatch")

    @staticmethod
    def _validate_handshake(
        scenario: FutureXmageScenario,
        provider: dict[str, Any],
        capabilities_payload: dict[str, Any],
    ) -> None:
        if provider.get("engine") != "xmage":
            raise FullGameConformanceError("full-game provider is not XMage")
        if provider.get("engine_commit") != scenario.xmage_commit:
            raise FullGameConformanceError(
                f"XMage commit mismatch: scenario={scenario.xmage_commit} "
                f"provider={provider.get('engine_commit')}"
            )
        lane = capabilities_payload.get("full_game_lane")
        caps = capabilities_payload.get("capabilities")
        if not isinstance(lane, dict) or not isinstance(caps, dict):
            raise FullGameConformanceError("full-game capability handshake is incomplete")
        if lane.get("lane") != FULL_GAME_LANE:
            raise FullGameConformanceError("full-game lane identity mismatch")
        if lane.get("decision_protocol_version") != FULL_GAME_DECISION_PROTOCOL_VERSION:
            raise FullGameConformanceError("full-game decision protocol mismatch")
        if lane.get("operational_pod_size") != 4:
            raise FullGameConformanceError("full-game capability pod size is not 4")
        if lane.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("full-game capability evidence class is unsafe")
        if lane.get("generic_capability_promotion") is not False:
            raise FullGameConformanceError("full-game lane must not promote generic capabilities")
        if lane.get("one_game_per_process") is not True:
            raise FullGameConformanceError("full-game lane must isolate one game per JVM")
        if lane.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay may not be preclaimed")
        required_true = {
            "commander_supported",
            "partner_supported",
            "multiplayer_supported",
            "headless_supported",
            "seed_supported",
            "deck_import_supported",
            "target_selection_supported",
            "mode_selection_supported",
            "trigger_order_supported",
            "mulligan_supported",
        }
        missing = sorted(name for name in required_true if caps.get(name) is not True)
        if missing:
            raise FullGameConformanceError(
                "full-game lane missing required capabilities: " + ", ".join(missing)
            )

    @staticmethod
    def _deck_payload(deck: RulesDeckInput) -> dict[str, Any]:
        if deck.deck_hash is None:
            raise FullGameConformanceError(f"deck_hash required for {deck.deck_id}")
        return {
            "deck_id": deck.deck_id,
            "deck_hash": deck.deck_hash,
            "mainboard": list(deck.mainboard),
            "commander_names": list(deck.commander_names),
            "sideboard": list(deck.sideboard),
        }

    @classmethod
    def _build_result(
        cls,
        scenario: FutureXmageScenario,
        provider: dict[str, Any],
        result: dict[str, Any],
    ) -> FullGameConformanceResult:
        if result.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("result evidence class is not technical conformance")
        for field in (
            "consumed_gameplay_evidence",
            "holdout_consumed",
            "official_campaign_eligible",
        ):
            if result.get(field) is not False:
                raise FullGameConformanceError(f"unsafe full-game result flag: {field}")
        if result.get("rules_authority") != "xmage":
            raise FullGameConformanceError("result rules authority is not XMage")
        if result.get("decision_policy_authority") != "commander_lab_external_pilot":
            raise FullGameConformanceError("result decision authority is not Commander Lab pilot")
        if result.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay was promoted without gate")
        if result.get("seed") != scenario.seed:
            raise FullGameConformanceError("result seed mismatch")
        if result.get("terminal") is not True:
            raise FullGameConformanceError("XMage full-game did not terminate")

        outcomes = result.get("outcomes")
        if not isinstance(outcomes, list) or len(outcomes) != 4:
            raise FullGameConformanceError("full-game result must contain four seat outcomes")
        winner_seats = tuple(
            int(item.get("seat", -1)) + 1
            for item in outcomes
            if isinstance(item, dict) and item.get("won") is True
        )
        semantic = cls.semantic_transcript(result)
        return FullGameConformanceResult(
            scenario=scenario,
            engine_version=str(provider.get("engine_version", "unknown")),
            xmage_commit=str(provider.get("engine_commit", "")),
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=int(result.get("decision_count", 0)),
            terminal=True,
            winner_seats=winner_seats,
            result_payload=result,
            semantic_transcript_sha256=cls._sha256(semantic),
            raw_result_sha256=cls._sha256(result),
        )

    @staticmethod
    def semantic_transcript(result: dict[str, Any]) -> dict[str, Any]:
        transcript = result.get("transcript")
        semantic_events: list[dict[str, Any]] = []
        if isinstance(transcript, list):
            for raw in transcript:
                if not isinstance(raw, dict):
                    continue
                semantic_events.append(
                    {
                        "sequence": raw.get("sequence"),
                        "kind": raw.get("kind"),
                        "decision_class": raw.get("decision_class"),
                        "actor_seat": raw.get("actor_seat"),
                        "prompt": raw.get("prompt"),
                        "selected_option_types": raw.get("selected_option_types"),
                        "selected_option_labels": raw.get("selected_option_labels"),
                        "numeric_choice": raw.get("numeric_choice"),
                    }
                )
        outcomes = result.get("outcomes")
        semantic_outcomes = []
        if isinstance(outcomes, list):
            semantic_outcomes = [
                {
                    "seat": item.get("seat"),
                    "life": item.get("life"),
                    "won": item.get("won"),
                    "lost": item.get("lost"),
                    "left": item.get("left"),
                }
                for item in outcomes
                if isinstance(item, dict)
            ]
        return {
            "seed": result.get("seed"),
            "turn_number": result.get("turn_number"),
            "decision_count": result.get("decision_count"),
            "events": semantic_events,
            "outcomes": semantic_outcomes,
        }

    @staticmethod
    def _sha256(value: dict[str, Any]) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = [
    "FULL_GAME_DECISION_PROTOCOL_VERSION",
    "FULL_GAME_EVIDENCE_CLASS",
    "FULL_GAME_LANE",
    "XMAGE_FULL_GAME_COMMAND_ENV",
    "ExternalPilotDecisionPolicy",
    "FullGameConformanceError",
    "FullGameConformanceResult",
    "FullGamePilotBinding",
    "FullGameProtocolError",
    "FullGameReplayGate",
    "XmageFullGameRunner",
]
