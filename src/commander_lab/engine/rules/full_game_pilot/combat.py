"""Attack and block declarations."""

from __future__ import annotations

import random
from typing import Any

from commander_lab.models import (
    PilotActionView,
)

from ..full_game_pilot_views import (
    attack_score,
    block_score,
)
from .choices import _ChoiceDecisions
from .common import (
    FullGameProtocolError,
    _RuntimePilot,
)


class _CombatDecisions(_ChoiceDecisions):
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
        # #732: board-aware attack judgment. An attack into a blocker that
        # kills the attacker and survives, or with a zero-power creature, is
        # not put up; the pilot chooses among the remaining defenders (its
        # evaluator weighs life and threat) or holds.
        for option in attacks:
            score, _facts = attack_score(option, state)
            if score <= 0.0:
                continue
            label = str(option.get("label", "Attack"))
            base = f"attack:{label.casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            action = self._combat_action(option, state)
            action = action.model_copy(
                update={
                    "action_id": stable_id,
                    "floor_value": min(3.0, max(action.floor_value, score)),
                }
            )
            actions.append(action)
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        if not actions:
            return self._required_text(hold, "option_id")
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
        except KeyError:
            raise FullGameProtocolError("pilot returned unknown stable attack action") from None

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
        ranked: list[tuple[float, str]] = []
        raw_by_stable_id: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for option in options:
            label = str(option.get("label", "Block"))
            base = f"block:{label.casefold()}"
            occurrence = occurrences.get(base, 0)
            occurrences[base] = occurrence + 1
            stable_id = f"{base}:{occurrence}"
            # The board decides blocks: the generic evaluator has no P/T.
            score, _facts = block_score(option, state)
            ranked.append((score, stable_id))
            raw_by_stable_id[stable_id] = self._required_text(option, "option_id")
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        # #732: block only where it pays (the blocker survives, trades up, or
        # a chump block prevents lethal or near-lethal damage); the old rule
        # always blocked at least once, which threw creatures away.
        worthwhile = sum(1 for score, _stable_id in ranked if score > 0.0)
        judged = max(min_selections, min(max_selections, worthwhile))
        # #802: the engine re-asks the whole declaration whenever its own check
        # rejects the configuration as a whole - an unmet "blocks this turn if
        # able", a menace minimum, a restriction that discards the declared
        # blockers. It only leaves that retry loop for a computer-controlled
        # player, so the pilot must answer a re-ask with a *different* legal
        # declaration: repeating one (including the empty one, which cannot
        # satisfy a block requirement) spins until the decision cap and ends
        # the game in ENGINE_FAILURE. The frame counter gives a bounded ladder,
        # and a frame the engine still rejects after the pilot's last legal
        # declaration fails closed instead of looping. The count is per seat
        # and turn, and the seat's next decision of any other class (the
        # priority window after an accepted declaration) clears it, so each
        # later combat in the same turn starts the ladder over (review P1).
        asks = self._count_block_frame_ask(runtime.binding.seat, state, options)
        judged_pick = [raw_by_stable_id[stable_id] for _score, stable_id in ranked[:judged]]
        maximal = max(min_selections, min(max_selections, len(options)))
        maximal_pick = [raw_by_stable_id[stable_id] for _score, stable_id in ranked[:maximal]]
        # Ask 1 is the judgment. Ask 2 is a search heuristic inside the options
        # the engine offered: the maximal declaration is the best chance to
        # satisfy a requirement like "blocks this turn if able" (CR 509.1c). It
        # makes no legality claim - the engine still accepts or rejects what is
        # submitted.
        if asks == 1:
            return judged_pick
        if asks == 2:
            return maximal_pick
        # From ask 3 on: the empty declaration (it can violate no blocking
        # restriction, but it cannot satisfy a mandatory block either), then
        # each single block the earlier asks did not declare, best first. A
        # requirement that names one attacker ("must be blocked if able", a
        # Predatory Impetus on a lower-ranked attacker) is only met by the
        # declaration that blocks that attacker, and the maximal declaration
        # of a one-block frame names only the best-ranked one (Seed 21 pod 010:
        # the Reiver Demon was offered, the Kaalia the requirement named never).
        tried = [judged_pick, maximal_pick]
        ladder: list[list[str]] = [[]] if min_selections == 0 else []
        if min_selections <= 1 <= max_selections:
            for _score, stable_id in ranked:
                single = [raw_by_stable_id[stable_id]]
                if single not in tried and single not in ladder:
                    ladder.append(single)
        if asks - 3 >= len(ladder):
            raise FullGameProtocolError(
                "engine rejected every block declaration the pilot can make: "
                f"seat={runtime.binding.seat} turn={state.get('turn_number')} "
                f"frames={len(options)}",
                code="BLOCK_DECLARATION_REJECTED",
            )
        return ladder[asks - 3]

    @staticmethod
    def _block_frame_key(options: list[dict[str, object]]) -> tuple[str, ...]:
        """Identify the engine's ask: the blocker and the attackers it offered.

        The engine's own object ids come from the option metadata, so two
        same-named blockers stay distinct frames. An option missing either id
        cannot be attributed to any engine frame, so it fails closed instead
        of collapsing into one opaque ``None>None`` frame that merges
        unrelated engine asks (and hides a bridge that stopped emitting the
        ids). The engine emits both ids on every declare_blocker option.
        """
        parts: list[str] = []
        for option in options:
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            blocker_id = meta.get("blocker_id")
            attacker_id = meta.get("attacker_id")
            if not isinstance(blocker_id, str) or not blocker_id.strip():
                raise FullGameProtocolError(
                    "declare_blocker option is missing the engine's blocker_id"
                )
            if not isinstance(attacker_id, str) or not attacker_id.strip():
                raise FullGameProtocolError(
                    "declare_blocker option is missing the engine's attacker_id"
                )
            parts.append(f"{blocker_id}>{attacker_id}")
        return tuple(sorted(parts))

    def _count_block_frame_ask(
        self, seat: int, state: dict[str, object], options: list[dict[str, object]]
    ) -> int:
        """How often the engine has asked this block frame this turn (1 = first).

        Bounded by the frame count of one declaration round. The seat's whole
        count is dropped by its next decision of another class (see
        ``decide``), so an accepted declaration - after which the seat gets
        priority - starts the next combat's frames at 1 again, and the count
        cannot grow with the length of a game.
        """
        turn = state.get("turn_number")
        stored = self._block_frame_asks.get(seat)
        counts = dict(stored[1]) if stored is not None and stored[0] == turn else {}
        key = self._block_frame_key(options)
        asks = counts.get(key, 0) + 1
        counts[key] = asks
        self._block_frame_asks[seat] = (turn, counts)
        return asks
