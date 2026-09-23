from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import queue
import random
import re
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

# WS229 forced-move audit channel. Forced moves (no pilot discretion) are
# auto-submitted only with a structured log record; discretionary actions
# are never hidden from the pilot.
_LOG = logging.getLogger(__name__)


class FullGameProtocolError(RuntimeError):
    """Fail-closed full-game bridge or external-pilot protocol error."""


class FullGameConformanceError(RuntimeError):
    """A run violated a full-game conformance invariant."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FullGamePilotBinding(_StrictModel):
    seat: int = Field(ge=1, le=6)
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


class FullGameSmokeResult(_StrictModel):
    """Bounded cardinality smoke outcome (WS223).

    Proves live production startup and authoritative decision progression up
    to a calibrated decision target (or earlier terminal) with clean bounded
    shutdown. This is a lifecycle smoke, not a game-over conformance claim:
    terminal/outcome-shape evidence stays with :class:`FullGameConformanceResult`
    (live 4P gate) and the per-count unit outcome guards.
    """

    schema_version: Literal["xmage-full-game-smoke-result-1.0.0"] = (
        "xmage-full-game-smoke-result-1.0.0"
    )
    scenario_id: str
    player_count: int = Field(ge=2, le=6)
    seed: int = Field(ge=0)
    engine_version: str
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_protocol_version: str
    decision_count: int = Field(ge=1)
    smoke_decision_target: int = Field(ge=1)
    bounded_criterion_met: Literal[True]
    terminal_reached: bool
    seed_preserved: Literal[True]
    player_count_preserved: Literal[True]
    observed_decision_classes: tuple[str, ...]
    unsupported_callback_seen: Literal[False] = False
    clean_shutdown: Literal[True] = True
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    fallback_used: Literal[False] = False


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
        if len(runtime_pilots) < 2 or len(runtime_pilots) > 6:
            raise ValueError("full-game policy requires two to six pilot bindings")
        seats = {item.binding.seat for item in runtime_pilots}
        if seats != set(range(1, len(runtime_pilots) + 1)):
            raise ValueError("full-game pilot bindings must cover seats 1..N exactly")
        self._pilots = {item.binding.seat: item for item in runtime_pilots}
        self._player_count = len(runtime_pilots)
        self.scenario_seed = scenario_seed
        self._mulligan_count: dict[int, int] = {
            seat: 0 for seat in range(1, len(runtime_pilots) + 1)
        }
        # No-progress guard memory for mana payments (per seat): last
        # decision fingerprint plus consecutive-repeat count. A mana
        # payment whose full offer (unpaid requirement, options, pool
        # amounts) repeats identically means no selection advanced it;
        # the guard then takes the engine-offered cancel (graceful abort).
        self._mana_last_fingerprint: dict[int, tuple] = {}
        self._mana_repeat_count: dict[int, int] = {}

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
        min_selections = int(request.get("minimum_selections", request.get("min_selections", 0)))
        max_selections = int(request.get("maximum_selections", request.get("max_selections", 0)))
        decision_offset = int(request.get("decision_offset", -1))
        if decision_offset < 1:
            raise FullGameProtocolError("decision_offset must be a positive integer")
        rng = self._rng(decision_offset, decision_class, seat)

        selected: list[str] = []
        numeric_choice: int | None = None
        numeric_choices: list[int] | None = None
        prompt = str(request.get("prompt", ""))

        if decision_class == "mulligan":
            selected = [self._decide_mulligan(runtime, pilot_state, options, rng)]
        elif decision_class in {"announce_x", "amount"}:
            numeric_choice = self._decide_numeric(
                runtime,
                pilot_state,
                context,
                rng,
                decision_class=decision_class,
                prompt=prompt,
            )
        elif decision_class == "multi_amount":
            numeric_choices = self._decide_multi_amount(
                runtime, pilot_state, context, rng, prompt=prompt
            )
        elif decision_class == "mana_payment":
            selected = [self._decide_mana(runtime, pilot_state, options, context, rng)]
        elif decision_class == "choose_use":
            selected = [self._decide_boolean(runtime, pilot_state, options, context, rng)]
        elif decision_class == "pile":
            selected = [self._decide_pile(runtime, pilot_state, options, context, rng)]
        elif decision_class in {"choice", "replacement_effect", "trigger_order"}:
            selected = [self._decide_semantic_option(runtime, pilot_state, options, rng)]
        elif decision_class == "mode":
            selected = [self._decide_mode(runtime, pilot_state, options, rng)]
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
                numeric_choice = self._decide_numeric(
                    runtime,
                    pilot_state,
                    context,
                    rng,
                    decision_class=decision_class,
                    prompt=prompt,
                )
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
        if numeric_choices is not None:
            response["numeric_choices"] = list(numeric_choices)
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
        if self._mulligan_count[seat] >= 3:
            # WS229 F-RULES-03 disposition: the cap overrides pilot discretion,
            # so the forced keep is a logged forced-move record, never silent.
            if not keep:
                _LOG.info(
                    "forced mulligan keep: seat=%s mulligans=%s pilot_wanted_mulligan=true",
                    seat,
                    self._mulligan_count[seat],
                )
            keep = True
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
        pass_id = self._required_text(pass_option, "option_id")
        non_mana = [
            option
            for option in options
            if self._required_text(option, "option_type") not in {"pass_priority", "mana_ability"}
        ]
        # Affordability-aware pilot judgment: an activated ability whose
        # engine-reported costs provably exceed the actor's free resources
        # (pool mana plus, for tap costs, an untapped source) is withheld
        # from the pilot's selection set so the pilot passes or acts
        # elsewhere instead of spending a shared resource mid-payment and
        # failing activation. Withheld options stay engine-offered; the
        # pilot simply does not select them. Unknown/absent cost facts mean
        # no gating: the engine remains the authority.
        affordable = [
            option for option in non_mana if self._priority_action_affordable(option, state)
        ]
        if len(affordable) != len(non_mana):
            _LOG.info(
                "withheld %d unaffordable priority action(s) from pilot selection",
                len(non_mana) - len(affordable),
            )
            non_mana = affordable
        # WS229 F-RULES-03 disposition: Core-authorized mana abilities were
        # withheld from the pilot. Mana abilities are discretionary actions,
        # so they are offered to the pilot with explicit mana metadata
        # instead of being hidden. Only a lone pass (no discretion) is
        # auto-submitted, with a forced-move record.
        #
        # Affordability applies to mana abilities with activation mana costs
        # too (e.g. signets): selecting one the pool cannot fund spends a
        # shared resource mid-payment and fails activation. Pure mana
        # abilities (no mana cost, untapped source) always pass the gate.
        mana_options = [
            option
            for option in options
            if self._required_text(option, "option_type") == "mana_ability"
        ]
        affordable_mana = [
            option for option in mana_options if self._priority_action_affordable(option, state)
        ]
        if len(affordable_mana) != len(mana_options):
            _LOG.info(
                "withheld %d unaffordable mana abilit(ies) from pilot selection",
                len(mana_options) - len(affordable_mana),
            )
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable view identities (WS92-D5 pattern): raw engine option
        # ids embed per-process UUIDs, so pilot tiebreaks on them would make
        # same-seed fresh-process twins diverge. Views carry content-derived
        # stable ids (type + label + content occurrence, all Rules-visible);
        # the pilot's pick maps back to the raw engine id here. Occurrence
        # counting is keyed by content, never by bridge order, so input
        # permutation cannot change the outcome.
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        action_views: list[PilotActionView] = []
        for option in non_mana:
            base = (
                "priority:"
                f"{self._required_text(option, 'option_type')}:"
                f"{str(option.get('label', 'action')).casefold()}"
            )
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action_views.append(
                self._priority_action(option, state).model_copy(update={"action_id": stable_id})
            )
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        for option in affordable_mana:
            base = f"priority:mana:{str(option.get('label', 'mana')).casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action_views.append(
                self._priority_mana_action(option, state).model_copy(update={"action_id": stable_id})
            )
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        action_views.append(
            PilotActionView(
                action_id=pass_id,
                action_kind="pass",
                card_name="Pass priority",
                floor_value=0.15,
                immediate_impact=0.0,
                metadata={"flexible_interaction": bool(state.get("stack"))},
            )
        )
        if len(action_views) == 1:
            _LOG.info("forced priority pass: no discretionary action offered")
            return pass_id
        decision = runtime.pilot.choose_action(pilot_state, action_views, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no priority action")
        if decision.selected_action_id == pass_id:
            return pass_id
        try:
            return raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable priority action") from exc

    def _priority_action_affordable(
        self, option: dict[str, Any], state: dict[str, Any]
    ) -> bool:
        """Pilot-side discretionary ranking among engine-authorized options.

        Returns False only when engine-native cost facts prove the action
        cannot be funded from free resources: a tap cost on an already
        tapped source, an untap cost on an untapped source, or mana costs
        the current pool cannot cover (``pool_covers_mana_cost`` is the
        engine's own ``Mana.enough`` verdict, projected losslessly by the
        bridge). Anything unknown means affordable.

        This is pilot choice, not a legality verdict: withheld options stay
        engine-offered, the pilot simply selects pass/another legal action
        instead, and the engine re-validates whatever is selected (a
        mid-payment cancel aborts to pass natively). No card names, no
        label parsing, no invented actions.
        """
        del state
        metadata = option.get("metadata")
        if not isinstance(metadata, dict):
            return True
        if metadata.get("requires_tap_source") is True:
            if metadata.get("source_tapped") is True:
                return False
        if metadata.get("requires_untap_source") is True:
            if metadata.get("source_tapped") is False:
                return False
        if metadata.get("pool_covers_mana_cost") is False:
            return False
        return True

    def _priority_mana_action(
        self, option: dict[str, Any], state: dict[str, Any]
    ) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        source_name = str(meta.get("source_name") or option.get("label") or "Mana ability")
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="card",
            card_name=source_name,
            mana_cost=0.0,
            floor_value=0.5,
            immediate_impact=0.35,
            remaining_mana=self._actor_mana(self._actor(state)),
            metadata={
                "xmage_option_type": "mana_ability",
                "is_mana_ability": True,
            },
        )

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
        context = request.get("context")
        structured_context = context if isinstance(context, dict) else {}
        # WS229 F-RULES-03 disposition: London-bottom routing is driven by
        # the bridge-supplied structured flag
        # (context.bottom_of_library_selection), never by prompt-text
        # heuristics. The flag is set only inside the native
        # putCardsOnBottomOfLibrary selection path.
        if structured_context.get("bottom_of_library_selection") is True:
            actor = self._actor(state)
            hand = actor.get("hand")
            if not isinstance(hand, list):
                raise FullGameProtocolError("London bottom decision requires actor hand visibility")
            legal_ids = {self._required_text(option, "option_id") for option in options}
            hand_ids = {
                self._required_text(card, "object_id")
                for card in hand
                if isinstance(card, dict)
            }
            # Two engine-native shapes share the bottom-selection path:
            # London mulligan bottoms cards FROM HAND (options are hand
            # cards), while library effects (e.g. Dig Through Time) order
            # looked-at LIBRARY cards (options are not hand cards). Only
            # the London shape uses opening-hand bottom valuation; library
            # bottom-ordering falls through to generic offered-option
            # ranking below (highest utility first: last chosen ends
            # bottommost, so the best card stays most accessible).
            if legal_ids and legal_ids <= hand_ids:
                count = min_selections
                card_actions = tuple(
                    self._hand_action(card) for card in hand if isinstance(card, dict)
                )
                selected = runtime.pilot.choose_bottom_cards(
                    card_actions,
                    count,
                    commander_names=runtime.binding.commander_names,
                )
                if not set(selected).issubset(legal_ids):
                    raise FullGameProtocolError("pilot bottom-card selection is not XMage-legal")
                return list(selected)

        if not options:
            return []
        outcome = str((request.get("context") or {}).get("outcome", "neutral")).casefold()
        pilot_state = self._pilot_state(runtime, state)
        # Twin-stable target identities: rank key is (score, Rules-visible
        # label, content-derived stable id); raw engine ids never order or
        # identify pilot inputs.
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        ranked: list[tuple[float, str, str]] = []
        for option in options:
            base = (
                "target:"
                f"{self._required_text(option, 'option_type')}:"
                f"{str(option.get('label', 'target')).casefold()}"
            )
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            action = self._target_action(option, state, outcome).model_copy(
                update={"action_id": stable_id}
            )
            breakdown = runtime.pilot.evaluate_action(pilot_state, action)
            score = breakdown.total_utility + self._target_alignment(action, state, outcome)
            ranked.append((score, action.card_name, stable_id))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

        if max_selections <= 0:
            return []
        if outcome in {"benefit", "benefit_to_controller"}:
            take = max_selections
        elif min_selections == 0:
            take = 0 if all(score < 0.0 for score, _label, _oid in ranked) else 1
        else:
            take = min_selections
        take = max(min_selections, min(max_selections, take))
        try:
            return [raw_by_stable_id[stable_id] for _score, _label, stable_id in ranked[:take]]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable target action") from exc

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
        # Twin-stable identities (same pattern as priority/targets).
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        actions: list[PilotActionView] = []
        for option in options:
            base = f"semantic:{str(option.get('label', 'option')).casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                self._semantic_action(option).model_copy(update={"action_id": stable_id})
            )
        decision = runtime.pilot.choose_action(pilot_state, actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no semantic option")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable semantic option") from exc
        return self._require_offered(raw_id, options, "semantic option")

    def _decide_mode(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        rng: random.Random,
    ) -> str:
        """Modal choice with native target-availability ranking.

        The bridge projects per-mode ``mode_targets_available`` from the
        engine's own ``Target.canChoose`` verdict. Modes explicitly lacking
        targets are depreferred (selecting one fails the cast: paper 601.2
        rewind shape); unknown/absent flags mean no filtering and the
        engine stays the authority. When every mode lacks targets the
        pilot still chooses (transcript agency) and the bridge maps the
        doomed cast to pass via its no-viable-mode flag.
        """
        if not options:
            raise FullGameProtocolError("mode decision has no legal options")
        viable = [
            option
            for option in options
            if not isinstance(option.get("metadata"), dict)
            or option["metadata"].get("mode_targets_available") is not False
        ]
        return self._decide_semantic_option(runtime, state, viable or options, rng)

    def _decide_boolean(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("boolean decision has no legal options")
        outcome = str(context.get("outcome", "neutral")).casefold()
        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        for option in options:
            metadata = option.get("metadata")
            value = metadata.get("value") if isinstance(metadata, dict) else None
            if not isinstance(value, bool):
                raise FullGameProtocolError("boolean option is missing explicit boolean value")
            aligned = (value and outcome in {"benefit", "benefit_to_controller"}) or (
                not value and outcome in {"detriment", "detriment_to_controller"}
            )
            # Twin-stable: boolean value words are Rules-visible content.
            stable_id = f"boolean:{value}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="card",
                    card_name=str(option.get("label", value)),
                    floor_value=0.8 if aligned else 0.35,
                    immediate_impact=0.45 if aligned else 0.15,
                    metadata={"boolean_value": value, "decision_outcome": outcome},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no boolean decision")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable boolean option") from exc
        return self._require_offered(raw_id, options, "boolean decision")

    def _decide_pile(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("pile decision has no legal options")
        outcome = str(context.get("outcome", "benefit")).casefold()
        benefit = outcome not in {"detriment", "detriment_to_controller"}
        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for option in options:
            metadata = option.get("metadata")
            cards = metadata.get("cards", []) if isinstance(metadata, dict) else []
            size = len(cards) if isinstance(cards, list) else 0
            scaled = min(2.0, size / 4.0)
            # Twin-stable: pile identity is its Rules-visible content
            # (sorted member names), never engine UUIDs.
            names: list[str] = []
            if isinstance(cards, list):
                for card in cards:
                    if isinstance(card, dict):
                        names.append(str(card.get("name", "")).casefold())
                    else:
                        names.append(str(card).casefold())
            base = f"pile:{size}:{'+'.join(sorted(names))}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="card",
                    card_name=str(option.get("label", "Pile")),
                    floor_value=(0.4 + scaled * 0.25) if benefit else max(0.0, 0.9 - scaled * 0.25),
                    immediate_impact=(0.3 + scaled * 0.2)
                    if benefit
                    else max(0.0, 0.7 - scaled * 0.2),
                    metadata={"pile_size": size, "decision_outcome": outcome},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no pile decision")
        try:
            raw_id = raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable pile option") from exc
        return self._require_offered(raw_id, options, "pile decision")

    def _decide_mana(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        options: list[dict[str, Any]],
        context: dict[str, Any],
        rng: random.Random,
    ) -> str:
        if not options:
            raise FullGameProtocolError("mana decision has no legal options")

        # No-progress guard: an identical mana-payment offer repeating
        # consecutively means no selection advanced the payment (e.g. pool
        # spends the engine cannot apply, re-prompted unchanged). Take the
        # engine-offered cancel so the activation aborts gracefully instead
        # of looping forever. Any progress (pool drain, tapped source,
        # changed requirement) alters the fingerprint and resets the count.
        # This is liveness bookkeeping, not payment semantics: the engine
        # alone decides what each selection does.
        seat = runtime.binding.seat
        fingerprint = (
            seat,
            str(context.get("unpaid_mana", "")),
            tuple(
                sorted(
                    (
                        self._required_text(option, "option_id"),
                        str(option.get("label", "")),
                        str((option.get("metadata") or {}).get("mana_available")),
                    )
                    for option in options
                )
            ),
        )
        if self._mana_last_fingerprint.get(seat) == fingerprint:
            repeats = self._mana_repeat_count.get(seat, 1) + 1
        else:
            repeats = 1
        self._mana_last_fingerprint[seat] = fingerprint
        self._mana_repeat_count[seat] = repeats
        if repeats >= 3:
            self._mana_repeat_count[seat] = 0
            for option in options:
                if self._required_text(option, "option_type") == "cancel_mana_payment":
                    _LOG.info(
                        "mana-payment no-progress guard: identical offer %d times, cancelling",
                        repeats,
                    )
                    return self._required_text(option, "option_id")
            raise FullGameProtocolError(
                "mana-payment no-progress guard tripped with no cancel offered"
            )

        pool_options = [
            option
            for option in options
            if self._required_text(option, "option_type") == "mana_pool"
        ]
        if pool_options:
            unpaid = str(context.get("unpaid_mana", "")).casefold()

            def pool_symbol(option: dict[str, Any]) -> str:
                metadata = option.get("metadata")
                meta = metadata if isinstance(metadata, dict) else {}
                mana_type = str(meta.get("mana_type", "")).casefold()
                return {
                    "white": "w",
                    "blue": "u",
                    "black": "b",
                    "red": "r",
                    "green": "g",
                    "colorless": "c",
                }.get(mana_type, "")

            def pool_advances(option: dict[str, Any]) -> bool:
                # Engine-native affordance (ManaCost.testPay projected by
                # the bridge): one mana of this pool type advances the
                # unpaid cost. Unknown/absent means usable; the engine
                # stays the authority and re-prompts (guarded above) if a
                # spend cannot apply.
                metadata = option.get("metadata")
                if not isinstance(metadata, dict):
                    return True
                return metadata.get("advances_payment") is not False

            def pool_key(option: dict[str, Any]) -> tuple[int, str, str]:
                metadata = option.get("metadata")
                meta = metadata if isinstance(metadata, dict) else {}
                mana_type = str(meta.get("mana_type", "")).casefold()
                symbol = pool_symbol(option)
                exact_required = 1 if symbol and f"{{{symbol}}}" in unpaid else 0
                return exact_required, mana_type, str(option.get("label", "")).casefold()

            # WS229 F-RULES-03 disposition: pool-first routing is kept, but
            # auto-submit is gated to the no-discretion case. A lone pool
            # candidate is a forced move (logged); several candidates hide
            # real discretion (which color to spend), so the pilot chooses.
            # Productive candidates are those the engine reports as
            # payment-advancing; the prompt-text heuristic below only orders
            # them and never excludes: exclusion is native-flag-only.
            candidates = [option for option in pool_options if pool_advances(option)]
            if len(candidates) == 1:
                chosen_pool = self._required_text(candidates[0], "option_id")
                _LOG.info(
                    "forced mana-pool spend: single productive pool candidate %s",
                    chosen_pool,
                )
                return chosen_pool
            if candidates:
                ordered = sorted(candidates, key=pool_key, reverse=True)
                pool_views: list[PilotActionView] = []
                raw_by_pool_view: dict[str, str] = {}
                for rank, option in enumerate(ordered):
                    view_id = f"mana:pool:{rank}"
                    raw_by_pool_view[view_id] = self._required_text(option, "option_id")
                    pool_views.append(
                        PilotActionView(
                            action_id=view_id,
                            action_kind="card",
                            card_name=str(option.get("label", "Spend pool mana")),
                            floor_value=max(0.05, 0.75 - 0.01 * rank),
                            immediate_impact=0.55,
                            metadata={"xmage_option_type": "mana_pool"},
                        )
                    )
                pool_decision = runtime.pilot.choose_action(
                    self._pilot_state(runtime, state), pool_views, rng
                )
                if pool_decision.selected_action_id is None:
                    raise FullGameProtocolError("Commander Lab pilot returned no mana decision")
                try:
                    return raw_by_pool_view[pool_decision.selected_action_id]
                except KeyError as exc:
                    raise FullGameProtocolError(
                        "pilot returned unknown stable pool-mana action"
                    ) from exc

        non_pool = [
            option
            for option in options
            if self._required_text(option, "option_type") != "mana_pool"
        ]
        if not non_pool:
            raise FullGameProtocolError(
                "mana decision has no productive option: pool cannot satisfy "
                "the colored requirement and no ability or cancel is offered"
            )
        options = non_pool

        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[tuple[str, str], int] = {}
        for option in options:
            option_type = self._required_text(option, "option_type")
            label = str(option.get("label", option_type))
            key = (option_type, label.casefold())
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            stable_id = f"mana:{option_type}:{label.casefold()}:{occurrence}"
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
            actions.append(
                PilotActionView(
                    action_id=stable_id,
                    action_kind="pass" if option_type == "cancel_mana_payment" else "card",
                    card_name=label,
                    floor_value=0.1 if option_type == "cancel_mana_payment" else 0.75,
                    immediate_impact=0.0 if option_type == "cancel_mana_payment" else 0.55,
                    metadata={"xmage_option_type": option_type},
                )
            )
        decision = runtime.pilot.choose_action(self._pilot_state(runtime, state), actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no mana decision")
        try:
            return raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable mana action") from exc

    @staticmethod
    def _required_bound(mapping: dict[str, Any], key: str) -> int:
        """Authoritative integer bound from Core-supplied context (fail closed).

        Strict: missing, boolean, or non-integer bounds raise. No coercion,
        no default, no clamp — the Lab never invents domain content.
        """
        if not isinstance(mapping, dict) or key not in mapping:
            raise FullGameProtocolError(f"numeric decision missing explicit bound: {key}")
        raw = mapping[key]
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise FullGameProtocolError(f"numeric decision bound is not an integer: {key}")
        return cast(int, raw)

    def _decide_numeric(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        context: dict[str, Any],
        rng: random.Random,
        *,
        decision_class: str,
        prompt: str = "",
    ) -> int:
        """Range-native scalar decision (WS229 Design B).

        The Core-supplied [min, max] is projected losslessly into a domain
        descriptor; the pilot chooses strategy inside it; the Lab validates
        exact membership before submission. No enumeration, no sampling, no
        {min,mid,max} collapse, no clamp, no nearest-value mapping, no
        default, no fallback. Malformed, non-integer, and out-of-domain
        pilot returns fail closed.
        """
        minimum = self._required_bound(context, "numeric_min")
        maximum = self._required_bound(context, "numeric_max")
        if maximum < minimum:
            raise FullGameProtocolError("numeric decision has reversed bounds")
        outcome = str(context.get("outcome", "benefit")).casefold()
        domain: dict[str, Any] = {
            "kind": "contiguous_inclusive_int",
            "min": minimum,
            "max": maximum,
            "outcome": outcome,
            "prompt": prompt,
        }
        chosen = runtime.pilot.choose_number(self._pilot_state(runtime, state), domain, rng)
        if isinstance(chosen, bool) or not isinstance(chosen, int):
            raise FullGameProtocolError(
                f"pilot returned non-integer numeric decision for {decision_class}"
            )
        if not minimum <= chosen <= maximum:
            raise FullGameProtocolError(
                f"pilot numeric decision {chosen} outside authoritative domain "
                f"{minimum}..{maximum} for {decision_class}"
            )
        return chosen

    def _decide_multi_amount(
        self,
        runtime: _RuntimePilot,
        state: dict[str, Any],
        context: dict[str, Any],
        rng: random.Random,
        *,
        prompt: str = "",
    ) -> list[int]:
        """Joint bounded integer-vector decision (WS229 Design B).

        One pilot-facing decision with per-leg [min, max] plus the total
        band — the exact isGoodValues predicate projected, not invented.
        Per-leg frames are never separate pilot strategic choices.
        """
        raw_legs = context.get("numeric_legs")
        if not isinstance(raw_legs, list) or not raw_legs:
            raise FullGameProtocolError(
                "multi_amount requires a joint vector context (numeric_legs)"
            )
        legs: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_legs):
            if not isinstance(raw, dict):
                raise FullGameProtocolError(f"multi_amount leg {index} is not a bounds object")
            leg_min = self._required_bound(raw, "min")
            leg_max = self._required_bound(raw, "max")
            if leg_max < leg_min:
                raise FullGameProtocolError(f"multi_amount leg {index} has reversed bounds")
            legs.append({"min": leg_min, "max": leg_max, "prompt": str(raw.get("prompt", ""))})
        total_min = self._required_bound(context, "numeric_total_min")
        total_max = self._required_bound(context, "numeric_total_max")
        if total_max < total_min:
            raise FullGameProtocolError("multi_amount has a reversed total band")
        if (
            sum(leg["min"] for leg in legs) > total_max
            or sum(leg["max"] for leg in legs) < total_min
        ):
            raise FullGameProtocolError("multi_amount joint domain is empty")
        outcome = str(context.get("outcome", "benefit")).casefold()
        domain: dict[str, Any] = {
            "kind": "joint_bounded_int_vector",
            "legs": legs,
            "total_min": total_min,
            "total_max": total_max,
            "outcome": outcome,
            "prompt": prompt,
        }
        chosen = runtime.pilot.choose_numbers(self._pilot_state(runtime, state), domain, rng)
        if not isinstance(chosen, (list, tuple)) or len(chosen) != len(legs):
            raise FullGameProtocolError("pilot joint numeric decision has the wrong vector length")
        values: list[int] = []
        for element in chosen:
            if isinstance(element, bool) or not isinstance(element, int):
                raise FullGameProtocolError(
                    "pilot joint numeric decision has a non-integer element"
                )
            values.append(element)
        for index, (value, leg) in enumerate(zip(values, legs, strict=True)):
            if not leg["min"] <= value <= leg["max"]:
                raise FullGameProtocolError(
                    f"pilot joint numeric leg {index} value {value} outside "
                    f"authoritative domain {leg['min']}..{leg['max']}"
                )
        if not total_min <= sum(values) <= total_max:
            raise FullGameProtocolError(
                f"pilot joint numeric total {sum(values)} outside authoritative band "
                f"{total_min}..{total_max}"
            )
        return values

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
        actions: list[PilotActionView] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for option in attacks:
            label = str(option.get("label", "Attack"))
            base = f"attack:{label.casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action = self._combat_action(option, state).model_copy(update={"action_id": stable_id})
            actions.append(action)
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        actions.append(
            PilotActionView(
                action_id="attack:hold",
                action_kind="pass",
                card_name="Hold attacker",
                floor_value=0.1,
            )
        )
        raw_by_stable_id["attack:hold"] = self._required_text(hold, "option_id")
        decision = runtime.pilot.choose_combat_target(pilot_state, actions, rng)
        if decision.selected_action_id is None:
            raise FullGameProtocolError("Commander Lab pilot returned no attack decision")
        try:
            return raw_by_stable_id[decision.selected_action_id]
        except KeyError as exc:
            raise FullGameProtocolError("pilot returned unknown stable attack action") from exc

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
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for option in options:
            label = str(option.get("label", "Block"))
            base = f"block:{label.casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action = self._combat_action(option, state).model_copy(update={"action_id": stable_id})
            score = runtime.pilot.evaluate_action(pilot_state, action).total_utility
            ranked.append((score, stable_id))
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        actor = self._actor(state)
        life = float(actor.get("life", 40))
        take = max_selections if life <= 15 else min(max_selections, max(min_selections, 1))
        return [raw_by_stable_id[stable_id] for _score, stable_id in ranked[:take]]

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
            pod_size=self._player_count,
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
            opponents_to_act_before_next_turn=self._player_count - 1,
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

    def _rng(self, decision_offset: int, decision_class: str, seat: int) -> random.Random:
        material = f"{self.scenario_seed}:{seat}:{decision_offset}:{decision_class}"
        digest = hashlib.sha256(material.encode()).digest()
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
    def _require_offered(selected_id: str, options: list[dict[str, Any]], kind: str) -> str:
        """Fail closed when the pilot returns an unoffered option id."""
        offered = {str(option.get("option_id")) for option in options if isinstance(option, dict)}
        if selected_id not in offered:
            raise FullGameProtocolError(f"pilot returned unknown {kind}")
        return selected_id

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
    """Run one isolated 2..6-player XMage Commander game with Commander Lab pilot policy."""

    MIN_PLAYERS = 2
    MAX_PLAYERS = 6

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
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameConformanceResult:
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        policy = self._validated_policy(scenario, decks, pilots)

        with _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
        ) as client:
            provider = self._open_game(client, scenario, decks)
            _decision_count, _, terminal = self._drive(client, policy, stop_after=None)
            assert terminal is True
            result = client.request("get_full_game_result")

        return self._build_result(scenario, provider, result)

    def run_smoke(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
        smoke_decision_target: int = 25,
    ) -> FullGameSmokeResult:
        """Drive a bounded live lifecycle smoke for one supported cardinality.

        Reuses the exact fail-closed validation, handshake, seed/count binding,
        and authoritative pilot policy of :meth:`run`, but stops after
        ``smoke_decision_target`` answered decisions (or earlier terminal) and
        shuts the engine down cleanly instead of requiring game over. Any
        unsupported engine callback surfaces as ``FullGameProtocolError`` /
        ``FullGameConformanceError`` from the shared drive loop, failing the
        smoke closed.
        """
        if smoke_decision_target < 1:
            raise ValueError("smoke_decision_target must be positive")
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        policy = self._validated_policy(scenario, decks, pilots)

        with _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
        ) as client:
            provider = self._open_game(client, scenario, decks)
            decision_count, observed, terminal = self._drive(
                client, policy, stop_after=smoke_decision_target
            )
        if decision_count == 0:
            raise FullGameConformanceError(
                "bounded smoke observed no authoritative decisions before terminal"
            )

        return FullGameSmokeResult(
            scenario_id=scenario.scenario_id,
            player_count=scenario.player_count,
            seed=scenario.seed,
            engine_version=str(provider.get("engine_version", "unknown")),
            xmage_commit=scenario.xmage_commit,
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=decision_count,
            smoke_decision_target=smoke_decision_target,
            bounded_criterion_met=True,
            terminal_reached=terminal,
            seed_preserved=True,
            player_count_preserved=True,
            observed_decision_classes=tuple(observed),
        )

    def _validated_policy(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> ExternalPilotDecisionPolicy:
        self._validate_inputs(scenario, decks, pilots)
        runtime_pilots = tuple(
            _RuntimePilot(
                binding=binding,
                pilot=build_pilot(binding.config, strategy=binding.strategy),
            )
            for binding in sorted(pilots, key=lambda item: item.seat)
        )
        return ExternalPilotDecisionPolicy(runtime_pilots, scenario.seed)

    def _open_game(
        self,
        client: _RawFullGameClient,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
    ) -> dict[str, Any]:
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
        player_count = scenario.player_count
        created = client.request(
            "create_full_game",
            {
                "game_id": game_id,
                "deck_handles": handles,
                "seed": scenario.seed,
                "starting_player_seat": scenario.seed % player_count,
                "starting_life": 40,
            },
        )
        if created.get("player_count") != player_count or created.get("seed") != scenario.seed:
            raise FullGameConformanceError(
                "full-game creation did not preserve player-count/seed contract"
            )
        if created.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("full-game creation returned unsafe evidence class")
        if created.get("holdout_consumed") is not False:
            raise FullGameConformanceError("technical conformance must not consume holdout")
        return provider

    def _drive(
        self,
        client: _RawFullGameClient,
        policy: ExternalPilotDecisionPolicy,
        *,
        stop_after: int | None,
    ) -> tuple[int, list[str], bool]:
        """Drive authoritative decisions until terminal (or ``stop_after`` answers).

        Returns ``(decision_count, observed_decision_classes, terminal)``.
        Shared verbatim by :meth:`run` (``stop_after=None``) and
        :meth:`run_smoke` so smoke progression and full-game progression
        cannot diverge.
        """
        status = client.request("start_full_game")
        decision_count = 0
        observed: list[str] = []
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
                decision_class = decision.get("decision_class")
                if isinstance(decision_class, str) and decision_class not in observed:
                    observed.append(decision_class)
                response = policy.decide(decision)
                status = client.request(
                    "submit_full_game_decision",
                    {"response": response},
                )
                if stop_after is not None and decision_count >= stop_after:
                    return decision_count, observed, False
                continue
            if bool(status.get("terminal")):
                return decision_count, observed, True
            status = client.request("get_full_game_decision")

    def run_replay_gate(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
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
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> None:
        player_count = scenario.player_count
        if (
            player_count < XmageFullGameRunner.MIN_PLAYERS
            or player_count > XmageFullGameRunner.MAX_PLAYERS
        ):
            raise FullGameConformanceError("operational full-game scope is two to six players")
        if len(decks) != player_count or len(pilots) != player_count:
            raise FullGameConformanceError(
                "deck/pilot cardinality must equal the scenario player count"
            )
        if len({deck.deck_id for deck in decks}) != player_count:
            raise FullGameConformanceError("full-game requires distinct deck identities per seat")
        if {pilot.seat for pilot in pilots} != set(range(1, player_count + 1)):
            raise FullGameConformanceError("pilot bindings must cover seats 1..N exactly")
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
        lane_min = lane.get("min_players")
        lane_max = lane.get("max_players")
        if (
            not isinstance(lane_min, int)
            or not isinstance(lane_max, int)
            or lane_min != XmageFullGameRunner.MIN_PLAYERS
            or lane_max != XmageFullGameRunner.MAX_PLAYERS
            or not lane_min <= scenario.player_count <= lane_max
        ):
            raise FullGameConformanceError(
                "full-game capability player-count range does not cover the scenario"
            )
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
        if not isinstance(outcomes, list) or len(outcomes) != scenario.player_count:
            raise FullGameConformanceError(
                "full-game result must contain one seat outcome per player"
            )
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
                        "prompt": XmageFullGameRunner._semantic_text(raw.get("prompt")),
                        "selected_option_types": raw.get("selected_option_types"),
                        "selected_option_labels": XmageFullGameRunner._semantic_text_list(
                            raw.get("selected_option_labels")
                        ),
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
    def _semantic_text(value: object) -> object:
        if not isinstance(value, str):
            return value
        text = re.sub(
            r"\s+object_id=(['\"])[^'\"]+\1",
            "",
            value,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            "<engine-object>",
            text,
        )
        text = re.sub(r"(</font>)\s*\[[0-9a-fA-F]{3,8}\]", r"\1", text)
        text = re.sub(r"\s*\[[0-9a-fA-F]{3,8}\](?=</div>|$)", "", text)
        return text

    @staticmethod
    def _semantic_text_list(value: object) -> object:
        if not isinstance(value, list):
            return value
        return [XmageFullGameRunner._semantic_text(item) for item in value]

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
