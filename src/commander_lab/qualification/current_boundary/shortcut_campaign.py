"""Negative campaign against the production action-validation seam.

The seven ``NEGATIVE_*`` obligations ask the same question in seven ways: can a
prohibited fallback satisfy a production-reachable decision? AGENTS.md section 2
enumerates the forbidden set -- first-option, random-option, default yes/no,
engine-internal AI substituting for external decision control, GUI/default
selections, silent skip, parent-class fallback -- and the answer to each is a
property of the code that validates a proposal, not of the engine.

This module answers that question behaviourally rather than by keyword search.
A static scan cannot distinguish ``candidates[0]`` as a forbidden first-option
pick from the same subscript reached only after an exact-uniqueness check, and
it produces nothing at all for a forbidden behaviour that is simply absent. So
each obligation is tested by feeding the production validator a proposal that
*would* succeed if the forbidden fallback existed, and recording that it fails
closed instead.

The properties exercised are the ones that make the forbidden set unreachable
here:

* exactly one engine-offered candidate must remain after filtering, so no
  "take the first" path exists;
* targets, modes and choices must be subsets of what the engine offered, so the
  validator cannot add anything and therefore cannot reconstruct legality;
* required choices must be present, so no default can be substituted;
* every rejection raises, so nothing is silently skipped;
* the returned value is the engine's own ``LegalAction``, so the validator never
  substitutes an object of its own.

Scope is stated precisely and is deliberately narrow. This establishes the
behaviour of *this* seam, which is the seam a proposal must pass to reach the
engine. It does **not** audit every other production-reachable surface, and it
does not claim the seven obligations are globally discharged. Saying otherwise
would be the very over-claim these obligations exist to catch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from commander_lab.engine.action_validation import IllegalActionProposal, validate_action_proposal
from commander_lab.models import ActionProposal, ActionType, GameState, LegalAction, PlayerState

SEAM = "commander_lab.engine.action_validation.validate_action_proposal"

_ACTOR = "p1"
_OTHER = "p2"


def _state(
    *,
    offered: int = 1,
    priority: str | None = _ACTOR,
    lost: bool = False,
    distinct_sources: bool = True,
) -> GameState:
    """A state whose actor is offered ``offered`` legal actions.

    ``distinct_sources=False`` offers several actions that are identical in every
    field a proposal can name except ``action_id``. That is the input a
    first-option shortcut would resolve: nothing in the proposal can single one
    out, so taking the first would be an unrequested pick.
    """
    actions = tuple(
        LegalAction(
            action_id=f"act-{index}",
            actor_id=_ACTOR,
            action_type=ActionType.CAST_SPELL,
            source_object_id=f"src-{index}" if distinct_sources else None,
            allowed_target_ids=(f"tgt-{index}",),
            modes=("mode-a",),
            choices_schema={
                "required": ["amount"],
                "properties": {"amount": {"type": "integer"}},
            },
        )
        for index in range(offered)
    )
    return GameState(
        game_id="g",
        players=(
            PlayerState(player_id=_ACTOR, seat=0, has_lost=lost),
            PlayerState(player_id=_OTHER, seat=1),
        ),
        priority_player_id=priority,
        legal_actions=actions,
    )


def _proposal(
    *,
    legal_action_id: str | None = "act-0",
    action_type: ActionType = ActionType.CAST_SPELL,
    source_object_id: str | None = "src-0",
    target_ids: tuple[str, ...] = (),
    selected_modes: tuple[str, ...] = (),
    choices: dict[str, Any] | None = None,
    actor_id: str = _ACTOR,
) -> ActionProposal:
    return ActionProposal(
        proposal_id="prop",
        actor_id=actor_id,
        legal_action_id=legal_action_id,
        action_type=action_type,
        source_object_id=source_object_id,
        target_ids=target_ids,
        selected_modes=selected_modes,
        choices={"amount": 1} if choices is None else choices,
    )


def _rejects(state: GameState, proposal: ActionProposal) -> tuple[bool, str]:
    try:
        validate_action_proposal(state, proposal)
    except IllegalActionProposal as exc:
        return True, str(exc)
    return False, ""


# ---------------------------------------------------------------------------
# One adversarial case per forbidden shortcut. Each would succeed if that
# shortcut were reachable through this seam.
# ---------------------------------------------------------------------------

_CASES: tuple[tuple[str, str, Callable[[], tuple[bool, str]]], ...] = (
    (
        "NEGATIVE_FIRST_OPTION",
        "three offered actions with no disambiguator, which a first-option pick would resolve",
        lambda: _rejects(
            _state(offered=3, distinct_sources=False), _proposal(legal_action_id=None)
        ),
    ),
    (
        "NEGATIVE_SILENT_SKIP",
        "a proposal naming no offered action, which a silent skip would absorb",
        lambda: _rejects(_state(offered=2), _proposal(legal_action_id="act-nonexistent")),
    ),
    (
        "NEGATIVE_DEFAULT_YES_NO",
        "a required choice omitted, which a default would silently supply",
        lambda: _rejects(_state(), _proposal(choices={})),
    ),
    (
        "NEGATIVE_RANDOM_OPTION",
        "a choice outside the offered schema, which an arbitrary pick would produce",
        lambda: _rejects(_state(), _proposal(choices={"amount": 1, "unlisted": "x"})),
    ),
    (
        "NEGATIVE_INTERNAL_AI",
        "an actor that does not hold priority, which substituting an engine-internal decision would bypass",
        lambda: _rejects(_state(priority=_OTHER), _proposal()),
    ),
    (
        "NEGATIVE_GUI_DEFAULT",
        "a target the engine did not offer, which a default or UI-chosen target would introduce",
        lambda: _rejects(_state(), _proposal(target_ids=("tgt-not-offered",))),
    ),
    (
        "NEGATIVE_PARENT_CLASS_FALLBACK",
        "a mode the engine did not offer, which an inherited or synthesised action would permit",
        lambda: _rejects(_state(), _proposal(selected_modes=("mode-not-offered",))),
    ),
)


def run_negative_campaign() -> dict[str, Any]:
    """Run every adversarial case and report which failed closed."""
    results: dict[str, Any] = {}
    for obligation_id, description, case in _CASES:
        rejected, detail = case()
        results[obligation_id] = {
            "adversarial_input": description,
            "rejected": rejected,
            "validator_message": detail,
            "outcome": "FAILS_CLOSED" if rejected else "SHORTCUT_REACHABLE",
        }

    # The positive case proves the seam still works, so the campaign is not
    # passing because everything is rejected for an unrelated reason.
    legal = validate_action_proposal(
        _state(), _proposal(target_ids=("tgt-0",), selected_modes=("mode-a",))
    )
    results["_positive_control"] = {
        "adversarial_input": "a proposal matching exactly one offered action",
        "rejected": False,
        "returned_is_engine_object": isinstance(legal, LegalAction),
        "returned_action_id": legal.action_id,
        "outcome": "ACCEPTED_AS_OFFERED",
    }

    unreachable = [k for k, v in results.items() if v["outcome"] == "SHORTCUT_REACHABLE"]
    return {
        "schema_version": "commander-lab.forbidden-shortcut-campaign/1.0.0",
        "seam_under_test": SEAM,
        "obligations": {k: v for k, v in results.items() if not k.startswith("_")},
        "positive_control": results["_positive_control"],
        "shortcuts_reachable": unreachable,
        "counts": {
            "obligations_tested": len([k for k in results if not k.startswith("_")]),
            "failed_closed": len([k for k, v in results.items() if v["outcome"] == "FAILS_CLOSED"]),
            "shortcut_reachable": len(unreachable),
        },
        "scope": (
            f"behaviour of {SEAM}, the seam a proposal must pass to reach the engine. This is a "
            "behavioural negative campaign against one production seam, not an audit of every "
            "production-reachable surface, and it does not claim the seven obligations are "
            "globally discharged"
        ),
        "evidence_class": "DIRECTLY_VERIFIED",
        "what_it_does_not_establish": [
            "that no other production-reachable surface can satisfy a decision by a forbidden "
            "fallback; that requires a separate, broader audit",
            "anything about engine behaviour, which is not involved",
            "that the obligations may be promoted to PASS: promotion is a separate, evidence-bound "
            "step and the row outcomes belong to the current-boundary runner under an active owner",
        ],
    }
