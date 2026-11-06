"""Engine-provided resolution costs inform ranking without narrowing choices."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_full_game_pilot_mana_and_may import _policy
from tests.unit.test_pilot_optional_costs import _ask, _board

_PROMPT = "Create a token that's a copy of that creature?"
_RIKU = {"ability_type": "triggered_nonmana", "source_name": "Riku of Two Reflections"}
_GREEN = "{T}: Add {G}."
_BLUE = "{T}: Add {U}."
_RED = "{T}: Add {R}."


def _decide(
    monkeypatch: pytest.MonkeyPatch,
    board: Any,
    hint: Any = "{G}{U}",
    scope: Any = "effect_resolution",
    *,
    prompt: str = _PROMPT,
    source: Any = _RIKU,
    only_yes: bool = False,
) -> tuple[str, list[bool]]:
    request = _ask(prompt, board, source, outcome="benefit", offset=1)
    if hint is not None:
        request["context"]["optional_mana_cost"] = hint
    if scope is not None:
        request["context"]["optional_mana_cost_scope"] = scope
    if only_yes:
        request["legal_options"] = request["legal_options"][:1]
    policy = _policy()
    pilot = policy._pilots[1].pilot
    original = pilot.choose_action
    seen: list[bool] = []

    def capture(state: Any, actions: Any, rng: Any) -> Any:
        seen.extend(a.metadata["boolean_value"] for a in actions)
        return original(state, actions, rng)

    monkeypatch.setattr(pilot, "choose_action", capture)
    result = policy.decide(request)["selected_option_ids"][0]
    return str(result), seen


@pytest.mark.parametrize("lands", [(), (_RED, _BLUE)])
def test_shortfall_ranks_no_preserving_both(
    monkeypatch: pytest.MonkeyPatch, lands: tuple[str, ...]
) -> None:
    answer, seen = _decide(monkeypatch, _board(*lands))
    assert answer == "no"
    assert sorted(seen) == [False, True]


def test_sufficient_mana_keeps_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _decide(monkeypatch, _board(_GREEN, _BLUE))[0] == "yes"


@pytest.mark.parametrize(
    ("hint", "scope"),
    [
        (None, "effect_resolution"),
        ("{G}{U}", None),
        ("{G}{U}", "other"),
        (5, "effect_resolution"),
        ("{G}{U}", 4),
        ("{X}{U}", "effect_resolution"),
    ],
)
def test_invalid_or_unknown_hint_keeps_normal_choice(
    monkeypatch: pytest.MonkeyPatch, hint: Any, scope: Any
) -> None:
    assert _decide(monkeypatch, _board(), hint, scope)[0] == "yes"


def test_unknown_mana_source_keeps_normal_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _decide(monkeypatch, _board(unreadable=True))[0] == "yes"


@pytest.mark.parametrize("prompt", [_PROMPT, "Pay {G}{U}?"])
def test_resolution_does_not_add_original_spell_cost(
    monkeypatch: pytest.MonkeyPatch, prompt: str
) -> None:
    spell = {"ability_type": "spell", "source_name": "Magma Opus"}
    answer, seen = _decide(monkeypatch, _board(_GREEN, _BLUE), prompt=prompt, source=spell)
    assert answer == "yes"
    assert sorted(seen) == [False, True]


def test_yes_remains_reachable_when_only_offered_option(monkeypatch: pytest.MonkeyPatch) -> None:
    answer, seen = _decide(monkeypatch, _board(), only_yes=True)
    assert answer == "yes"
    assert seen == [True]


def test_native_resolution_hint_suppresses_legacy_spell_base_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spell = {"ability_type": "spell", "source_name": "Nullpriest of Oblivion"}
    board = _board(_GREEN, _BLUE, "{T}: Add {B}.")
    answer, seen = _decide(monkeypatch, board, prompt="Pay {G}{U}?", source=spell)
    assert answer == "yes"
    assert sorted(seen) == [False, True]


def test_invalid_hint_preserves_legacy_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    spell = {"ability_type": "spell", "source_name": "Nullpriest of Oblivion"}
    board = _board(_GREEN, _BLUE, "{T}: Add {B}.")
    answer, seen = _decide(monkeypatch, board, scope="other", prompt="Pay {G}{U}?", source=spell)
    assert answer == "no"
    assert seen == [False]
