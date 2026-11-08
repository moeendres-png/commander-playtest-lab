"""Optional payments made before X share the cast's visible mana budget."""

from typing import Any

import pytest

from tests.unit.test_full_game_pilot_mana_and_may import _PASS, _policy, _request
from tests.unit.test_pilot_x_and_pay_amount import _announce, _kicker, _lands


def _offer(policy: Any, number: int, source: str = "Comet Storm") -> str:
    request = _kicker(number, source)
    request["pilot_state"] = _lands(8)
    request["prompt"] = f"Pay {number} {'time' if number == 1 else 'times'} Multikicker {{1}} ?"
    return str(policy.decide(request)["selected_option_ids"][0])


def _x(policy: Any, source: str = "Comet Storm", prompt: str = "Announce the value for {X}") -> int:
    request = _announce(prompt, _lands(8), source)
    request["context"].update(numeric_non_x_mana_value=2, numeric_x_symbols=prompt.count("{X}"))
    return int(policy.decide(request)["numeric_choice"])


def test_kicker_before_x_keeps_budget_for_both() -> None:
    policy = _policy()
    assert [_offer(policy, n) for n in range(1, 5)] == ["yes", "yes", "yes", "no"]
    assert _x(policy) == 3


def test_no_keeps_paid_counts_and_x_symbols_share_remainder() -> None:
    policy = _policy()
    for n in range(1, 5):
        _offer(policy, n)
    assert _x(policy, prompt="Announce the value for {X}{X}") == 1


def test_repeated_ordinal_after_no_does_not_double_count() -> None:
    policy = _policy()
    for n in range(1, 5):
        _offer(policy, n)
    _offer(policy, 3)
    assert _x(policy) == 3


@pytest.mark.parametrize("source", ["Savannah Lions", "Unknown imaginary spell"])
def test_non_x_or_unknown_spell_keeps_prior_cap(source: str) -> None:
    policy = _policy()
    assert [_offer(policy, n, source) for n in range(1, 4)] == ["yes", "yes", "yes"]


def test_commitment_is_source_scoped() -> None:
    policy = _policy()
    _offer(policy, 1)
    assert _x(policy, "Other spell") == 6


def test_commitment_is_seat_scoped() -> None:
    policy = _policy()
    _offer(policy, 1)
    request = _announce("Announce the value for {X}", _lands(8), "Comet Storm")
    request["pilot_state"]["seat"] = 1
    request["context"].update(numeric_non_x_mana_value=2, numeric_x_symbols=1)
    assert policy.decide(request)["numeric_choice"] == 6


def test_next_priority_clears_commitment() -> None:
    policy = _policy()
    _offer(policy, 1)
    policy.decide(_request("priority", [_PASS], state=_lands(8)))
    assert _x(policy) == 6


def test_first_offer_leaves_one_mana_for_x() -> None:
    policy = _policy()
    request = _kicker(1, "Comet Storm")
    request["pilot_state"] = _lands(3)
    request["prompt"] = "Pay 1 time Multikicker {1} ?"
    assert policy.decide(request)["selected_option_ids"] == ["no"]


def test_native_non_x_cost_takes_precedence_over_printed_cost() -> None:
    policy = _policy()
    policy._priority_cost_facts[1] = {"stack-Comet Storm": 4}
    assert [_offer(policy, n) for n in range(1, 4)] == ["yes", "yes", "no"]


def test_engine_numeric_domain_is_preserved(monkeypatch: Any) -> None:
    policy = _policy()
    _offer(policy, 1)
    pilot = policy._pilots[1].pilot
    domains: list[dict[str, Any]] = []

    def choose_number(state: Any, domain: dict[str, Any], rng: Any) -> int:
        domains.append(domain)
        return domain["max"]

    monkeypatch.setattr(type(pilot), "choose_number", choose_number_with_self(choose_number))
    assert _x(policy) == 2147483647
    assert (domains[0]["min"], domains[0]["max"], domains[0]["affordable_max"]) == (
        0,
        2147483647,
        5,
    )


def choose_number_with_self(callback: Any) -> Any:
    def wrapped(self: Any, state: Any, domain: Any, rng: Any) -> int:
        return int(callback(state, domain, rng))

    return wrapped
