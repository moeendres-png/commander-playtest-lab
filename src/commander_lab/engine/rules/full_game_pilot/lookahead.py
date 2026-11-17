"""Bounded XMage-backed look-ahead rollouts for priority decisions (#1265 S5).

XMage remains the sole Rules authority (§2): look-ahead branches run inside the
bridge's isolated ``Game.copy()`` probe via ``start_lookahead_probe``,
``step_lookahead_probe``, and ``end_lookahead_probe``, with per-owner §5
hidden-zone redetermination and an explicit ``probe_seed``. Both probe
``actor_view`` payloads and intermediate probe ``decision`` frames pass the
fail-closed §5 actor-scoped audit before evaluation.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ..full_game_pilot_views import (
    board_summary,
    creature_power,
    entry_value,
    is_creature_entry,
    is_land_entry,
)
from .common import FullGameConformanceError, FullGameProtocolError

_TERMINAL_WIN_SCORE = 10_000.0
_TERMINAL_LOSS_SCORE = -10_000.0
_PROBE_FAILURE_PENALTY = -10_000.0


class LookaheadClient(Protocol):
    """Minimal request boundary satisfied by ``_RawFullGameClient`` and fakes."""

    def request(
        self, message_type: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]: ...


class RolloutPolicy(Protocol):
    """Minimal policy boundary for stepping an isolated look-ahead branch."""

    def decide(self, request: dict[str, object]) -> dict[str, object]: ...


FrameAuditor = Callable[[dict[str, object]], tuple[int, int, list[str]]]
LookaheadChooser = Callable[[Mapping[str, object], int, str, tuple[str, ...]], str]


@dataclass(frozen=True, slots=True)
class LookaheadConfig:
    """Configuration for bounded priority look-ahead (default disabled)."""

    enabled: bool = False
    max_candidates: int = 4
    max_searches_per_game: int = 12
    rollout_steps: int = 16
    min_margin: float = 0.5
    min_turn: int = 2
    redetermine: bool = True

    def __post_init__(self) -> None:
        if self.max_candidates < 2:
            raise ValueError("max_candidates must be at least 2")
        if self.max_searches_per_game < 0:
            raise ValueError("max_searches_per_game must be non-negative")
        if self.rollout_steps < 1:
            raise ValueError("rollout_steps must be at least 1")
        if self.min_turn < 1:
            raise ValueError("min_turn must be at least 1")
        if not math.isfinite(self.min_margin):
            raise ValueError("min_margin must be finite")


def derive_probe_seed(game_seed: int, decision_offset: int, candidate_index: int) -> int:
    """Derive a deterministic positive 63-bit probe seed per branching decision."""
    payload = f"{game_seed}:{decision_offset}:{candidate_index}".encode()
    digest = hashlib.sha256(payload).digest()
    return (int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF) or 1


def _num(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _player_rows(actor_view: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = actor_view.get("players")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def _commander_names_lower(actor_view: Mapping[str, object]) -> set[str]:
    raw = actor_view.get("commander_status")
    if not isinstance(raw, list):
        return set()
    names: set[str] = set()
    for item in raw:
        if isinstance(item, Mapping):
            name = item.get("name")
            if isinstance(name, str) and name:
                names.add(name.casefold())
    return names


def _hand_count(row: Mapping[str, object]) -> int:
    count = row.get("hand_count")
    if not isinstance(count, bool) and isinstance(count, int):
        return max(0, count)
    hand = row.get("hand")
    if isinstance(hand, list):
        return len(hand)
    return 0


def _untapped_lands_and_nonlands(row: Mapping[str, object]) -> tuple[int, int, int]:
    battlefield = row.get("battlefield")
    if not isinstance(battlefield, list):
        return 0, 0, 0
    untapped_lands = 0
    creatures = 0
    untapped_creatures = 0
    for perm in battlefield:
        if not isinstance(perm, Mapping):
            continue
        tapped = perm.get("tapped") is True
        if is_land_entry(perm):
            if not tapped:
                untapped_lands += 1
        elif is_creature_entry(perm):
            creatures += 1
            if not tapped:
                untapped_creatures += 1
    return untapped_lands, creatures, untapped_creatures


def board_score(actor_view: Mapping[str, object], actor_seat: int | None = None) -> float:
    """Evaluate a viewer-scoped ``actor_view`` snapshot using only legal viewer info."""
    rows = _player_rows(actor_view)
    if not rows:
        return 0.0
    own_row: Mapping[str, object] | None = None
    opponents: list[Mapping[str, object]] = []
    for row in rows:
        if own_row is None and (
            row.get("is_actor") is True
            or (actor_seat is not None and row.get("seat") == actor_seat)
        ):
            own_row = row
            continue
        opponents.append(row)
    if own_row is None:
        return 0.0
    if own_row.get("has_won") is True:
        return _TERMINAL_WIN_SCORE
    if own_row.get("has_lost") is True:
        return _TERMINAL_LOSS_SCORE
    alive_opponents = [opp for opp in opponents if opp.get("has_lost") is not True]
    if opponents and not alive_opponents:
        return _TERMINAL_WIN_SCORE

    own_life = _num(own_row.get("life"), 40.0)
    own_poison = _int(own_row.get("poison_counters"), 0)
    own_summary = board_summary(own_row)
    untapped_lands, own_creatures, untapped_creatures = _untapped_lands_and_nonlands(own_row)
    own_hand = _hand_count(own_row)
    cmd_names = _commander_names_lower(actor_view)

    score = 0.25 * min(max(own_life, 0.0), 60.0)
    if own_life <= 5.0:
        score -= 6.0
    score -= 1.5 * own_poison
    score += 1.2 * own_summary["lands"] + 0.35 * untapped_lands
    score += 1.5 * own_creatures + 0.2 * untapped_creatures
    score += 0.4 * min(own_summary["creature_power"], 40.0)
    non_creature_nonlands = max(0.0, own_summary["nonland_permanents"] - own_creatures)
    score += 1.4 * non_creature_nonlands
    score += 0.75 * min(own_hand, 10)

    own_battlefield = own_row.get("battlefield")
    if isinstance(own_battlefield, list):
        commander_on_board = any(
            isinstance(perm, Mapping) and str(perm.get("name") or "").casefold() in cmd_names
            for perm in own_battlefield
        )
        if commander_on_board:
            score += 1.8
        permanent_sum = 0.0
        for perm in own_battlefield:
            if isinstance(perm, Mapping) and not is_land_entry(perm):
                permanent_sum += min(8.0, entry_value(perm, actor_view))
        score += 0.15 * permanent_sum

    eliminated_count = len(opponents) - len(alive_opponents)
    score += 12.0 * eliminated_count

    if alive_opponents:
        opp_pressure = 0.0
        for opp in alive_opponents:
            opp_life = _num(opp.get("life"), 40.0)
            opp_summary = board_summary(opp)
            opp_hand = _hand_count(opp)
            opp_bf = opp.get("battlefield")
            opp_untapped_power = (
                sum(
                    creature_power(perm)
                    for perm in opp_bf
                    if isinstance(perm, Mapping) and perm.get("tapped") is not True
                )
                if isinstance(opp_bf, list)
                else 0
            )
            opp_pressure += (
                0.12 * min(max(opp_life, 0.0), 60.0)
                + 0.45 * min(opp_hand, 10)
                + 0.7 * opp_summary["lands"]
                + 0.9 * opp_summary["nonland_permanents"]
                + 0.35 * min(opp_summary["creature_power"], 40.0)
                + 0.2 * opp_untapped_power
            )
        score -= 0.5 * (opp_pressure / len(alive_opponents))
    return score


@dataclass(slots=True)
class LookaheadEvaluator:
    """Stateful per-game bounded look-ahead coordinator over an active bridge client."""

    client: LookaheadClient
    clone_policy: Callable[[int], RolloutPolicy]
    game_seed: int
    config: LookaheadConfig
    frame_auditor: FrameAuditor
    searches_used: int = 0
    decisions_evaluated: int = 0
    decisions_altered: int = 0
    last_rollout_scores: dict[str, float] = field(default_factory=dict)

    def _audit_probe_payload(
        self, payload: Mapping[str, object], expected_actor_id: str
    ) -> Mapping[str, object]:
        actor_view = payload.get("actor_view")
        if not isinstance(actor_view, Mapping):
            raise FullGameConformanceError("look-ahead probe returned no actor_view")
        if actor_view.get("actor_id") != expected_actor_id:
            raise FullGameConformanceError(
                "look-ahead probe actor_view mismatched expected viewer identity"
            )
        view_frame: dict[str, object] = {
            "actor_id": expected_actor_id,
            "pilot_state": dict(actor_view),
        }
        _rows, _vis, view_violations = self.frame_auditor(view_frame)
        if view_violations:
            raise FullGameConformanceError(
                "look-ahead probe actor_view failed §5 scoping audit: " + "; ".join(view_violations)
            )
        return actor_view

    def _audit_probe_decision(self, decision: Mapping[str, object]) -> None:
        _rows, _vis, violations = self.frame_auditor(dict(decision))
        if violations:
            raise FullGameConformanceError(
                "look-ahead probe decision failed §5 scoping audit: " + "; ".join(violations)
            )

    def _evaluate_candidate(
        self,
        *,
        actor_id: str,
        actor_seat: int | None,
        decision_offset: int,
        candidate_index: int,
        candidate_option_id: str,
    ) -> float:
        probe_seed = derive_probe_seed(self.game_seed, decision_offset, candidate_index)
        rollout_policy = self.clone_policy(probe_seed)
        probe_id: str | None = None
        try:
            status = self.client.request(
                "start_lookahead_probe",
                {
                    "actor_id": actor_id,
                    "candidate_option_id": candidate_option_id,
                    "probe_seed": probe_seed,
                    "redetermine": True,
                },
            )
            raw_probe_id = status.get("probe_id")
            probe_id = raw_probe_id if isinstance(raw_probe_id, str) and raw_probe_id else None
            actor_view = self._audit_probe_payload(status, actor_id)

            for _ in range(self.config.rollout_steps):
                if (
                    status.get("terminal") is True
                    or isinstance(status.get("failure"), Mapping)
                    or _int(status.get("engine_error_count"), 0) > 0
                ):
                    break
                next_decision = status.get("decision")
                if not isinstance(next_decision, dict):
                    break
                self._audit_probe_decision(next_decision)
                response = rollout_policy.decide(next_decision)
                step_payload: dict[str, object] = {"response": response}
                if probe_id is not None:
                    step_payload["probe_id"] = probe_id
                status = self.client.request("step_lookahead_probe", step_payload)
                actor_view = self._audit_probe_payload(status, actor_id)

            if (
                isinstance(status.get("failure"), Mapping)
                or _int(status.get("engine_error_count"), 0) > 0
            ):
                return _PROBE_FAILURE_PENALTY
            return board_score(actor_view, actor_seat)
        finally:
            if probe_id is not None:
                self.client.request("end_lookahead_probe", {"probe_id": probe_id})

    def choose_priority_option(
        self,
        pilot_state: Mapping[str, object],
        decision_offset: int,
        default_option_id: str,
        candidate_option_ids: tuple[str, ...],
    ) -> str:
        """Rank ``candidate_option_ids`` via bounded probe rollouts; keep heuristic unless gain >= min_margin."""
        if not self.config.enabled:
            return default_option_id
        if not self.config.redetermine:
            raise FullGameProtocolError(
                "LOOKAHEAD_REDETERMINATION_REQUIRED: look-ahead probes require redetermine=True"
            )
        if len(candidate_option_ids) < 2:
            return default_option_id
        if self.searches_used >= self.config.max_searches_per_game:
            return default_option_id
        turn = pilot_state.get("turn_number")
        if isinstance(turn, bool) or not isinstance(turn, int) or turn < self.config.min_turn:
            return default_option_id
        actor_id = pilot_state.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id:
            return default_option_id
        raw_seat = pilot_state.get("seat")
        actor_seat = (
            raw_seat if not isinstance(raw_seat, bool) and isinstance(raw_seat, int) else None
        )

        self.searches_used += 1
        self.decisions_evaluated += 1

        limited = candidate_option_ids[: self.config.max_candidates]
        scores: dict[str, float] = {}
        for idx, option_id in enumerate(limited):
            scores[option_id] = self._evaluate_candidate(
                actor_id=actor_id,
                actor_seat=actor_seat,
                decision_offset=decision_offset,
                candidate_index=idx,
                candidate_option_id=option_id,
            )
        self.last_rollout_scores = dict(scores)

        baseline_id = limited[0]
        baseline_score = scores[baseline_id]
        best_other_id: str | None = None
        best_other_score = baseline_score
        for option_id in limited[1:]:
            candidate_score = scores[option_id]
            if candidate_score - baseline_score >= self.config.min_margin and (
                best_other_id is None or candidate_score > best_other_score
            ):
                best_other_id = option_id
                best_other_score = candidate_score
        if best_other_id is not None:
            self.decisions_altered += 1
            return best_other_id
        return default_option_id
