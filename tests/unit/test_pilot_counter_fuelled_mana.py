"""Full-game pilot: a mana ability fuelled by counters is not tapped once the counters are gone.

Everflowing Chalice ("{T}: Add {C} for each charge counter on {this}.") and the storage lands
(Mage-Ring Network: "{T}, Remove any number of storage counters from {this}: Add {C} for each
storage counter removed this way.") are offered by the engine in a payment whatever their
counters. A payment that took one with no counters spent the permanent's tap for no mana and
ended in a cancelled cast (167 cancels in 60 round-robin games, 44 of them storage-land taps and
45 Chalice-related). The counters are board-public, so the pilot reads them.

Controls: a Chalice with a counter, a storage land with a counter, the plain ability of a storage
land, a mana rule that is not counter-fuelled and a permanent whose counters are not reported
are all left as they were.
"""

from __future__ import annotations

from typing import Any

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_pilot.common import (
    counter_fuelled_mana_supply,
    mana_ability_yields_nothing,
    permanent_mana_is_counter_starved,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength

_CHALICE_RULE = "{T}: Add {C} for each charge counter on {this}."
_CHALICE_LABEL = f"Everflowing Chalice — {_CHALICE_RULE}"
_PLAIN_RULE = "{T}: Add {C}."
_STORAGE_RULE = (
    "{T}, Remove any number of storage counters from {this}: "
    "Add {C} for each storage counter removed this way."
)
_STORAGE_LABEL = f"Mage-Ring Network — {_STORAGE_RULE}"
_PLAIN_LABEL = f"Mage-Ring Network — {_PLAIN_RULE}"
_CORNUCOPIA_RULE = (
    "{T}: Add X mana of any one color, where X is the number of charge counters on {this}."
)


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Isamaru, Hound of Konda",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261110)  # type: ignore[arg-type]


def _permanent(
    object_id: str,
    name: str,
    rules: list[str],
    counters: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "object_id": object_id,
        "name": name,
        "abilities": rules,
        "tapped": False,
    }
    if counters is not None:
        item["counters"] = counters
    return item


def _state(extra: list[dict[str, Any]]) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 2,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [
            {"object_id": "waste", "name": "Wastes", "tapped": False},
            *extra,
        ],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [{"object_id": "hand-0", "name": "Savannah Lions"}],
        "mana_pool": {
            "white": 0,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        },
    }
    opponents = [
        {
            "player_id": f"opponent-{seat}",
            "seat": seat,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [],
        }
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 5,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": "precombat_main",
        "players": [actor, *opponents],
        "stack": [],
    }


def _tap(option_id: str, label: str, source_id: str) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": "mana_ability",
        "label": label,
        "metadata": {
            "source_name": label.partition(" — ")[0],
            "source_object_id": source_id,
            "ability_type": "activated_mana",
            "mana_ability": True,
            "pool_covers_mana_cost": True,
            "requires_tap_source": True,
            "requires_untap_source": False,
            "requires_sacrifice_source": False,
            "source_tapped": False,
        },
    }


def _payment(options: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    cancel = {
        "option_id": "cancel",
        "option_type": "cancel_mana_payment",
        "label": "Cancel mana payment",
        "metadata": {},
    }
    return {
        "decision_id": "opaque-mana_payment-1",
        "decision_offset": 1,
        "actor_id": "actor",
        "decision_class": "mana_payment",
        "pilot_state": state,
        "context": {"unpaid_mana": "{1}"},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [cancel, *options],
        "prompt": "{1}",
        "source_object": {"source_name": "Sol Ring", "ability_type": "spell"},
    }


# -- reading the rule ---------------------------------------------------------------------


def test_chalice_supply_is_its_charge_counters() -> None:
    chalice = _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [])
    assert counter_fuelled_mana_supply(_CHALICE_RULE, chalice) == 0
    chalice["counters"] = [{"type": "charge", "count": 2}]
    assert counter_fuelled_mana_supply(_CHALICE_RULE, chalice) == 2


def test_only_counters_of_the_named_kind_count() -> None:
    chalice = _permanent(
        "c",
        "Everflowing Chalice",
        [_CHALICE_RULE],
        [{"type": "+1/+1", "count": 3}, {"type": "storage", "count": 4}],
    )
    assert counter_fuelled_mana_supply(_CHALICE_RULE, chalice) == 0


def test_storage_and_where_x_rules_are_read() -> None:
    land = _permanent("m", "Mage-Ring Network", [], [{"type": "storage", "count": 3}])
    assert counter_fuelled_mana_supply(_STORAGE_RULE, land) == 3
    land["counters"] = []
    assert counter_fuelled_mana_supply(_STORAGE_RULE, land) == 0
    cornucopia = _permanent("a", "Astral Cornucopia", [], [])
    assert counter_fuelled_mana_supply(_CORNUCOPIA_RULE, cornucopia) == 0


def test_a_rule_that_is_not_counter_fuelled_has_no_supply() -> None:
    land = _permanent("m", "Mage-Ring Network", [_PLAIN_RULE], [])
    assert counter_fuelled_mana_supply(_PLAIN_RULE, land) is None
    assert counter_fuelled_mana_supply("{T}: Add {G}.", land) is None
    assert counter_fuelled_mana_supply("", land) is None


def test_unreported_counters_are_never_read_as_zero() -> None:
    chalice = _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], None)
    assert counter_fuelled_mana_supply(_CHALICE_RULE, chalice) is None
    chalice["counters"] = [{"type": "charge", "count": "two"}]
    assert counter_fuelled_mana_supply(_CHALICE_RULE, chalice) is None


# -- the option -------------------------------------------------------------------------------


def test_an_option_of_a_starved_source_yields_nothing() -> None:
    battlefield = [_permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [])]
    assert mana_ability_yields_nothing(_tap("chalice", _CHALICE_LABEL, "c"), battlefield)


def test_options_with_counters_or_plain_text_are_not_withheld() -> None:
    fed = [
        _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [{"type": "charge", "count": 1}])
    ]
    assert not mana_ability_yields_nothing(_tap("chalice", _CHALICE_LABEL, "c"), fed)
    land = [_permanent("m", "Mage-Ring Network", [_PLAIN_RULE, _STORAGE_RULE], [])]
    assert not mana_ability_yields_nothing(_tap("plain", _PLAIN_LABEL, "m"), land)
    assert mana_ability_yields_nothing(_tap("storage", _STORAGE_LABEL, "m"), land)


def test_an_option_whose_source_is_not_on_the_board_is_not_withheld() -> None:
    assert not mana_ability_yields_nothing(_tap("chalice", _CHALICE_LABEL, "gone"), [])
    assert not mana_ability_yields_nothing(_tap("chalice", _CHALICE_LABEL, "gone"), None)


def test_a_permanent_is_starved_only_when_all_its_mana_is_counter_fuelled() -> None:
    assert permanent_mana_is_counter_starved(
        _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [])
    )
    assert not permanent_mana_is_counter_starved(
        _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [{"type": "charge", "count": 1}])
    )
    assert not permanent_mana_is_counter_starved(
        _permanent("m", "Mage-Ring Network", [_PLAIN_RULE, _STORAGE_RULE], [])
    )
    assert not permanent_mana_is_counter_starved(
        _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], None)
    )
    assert not permanent_mana_is_counter_starved(_permanent("p", "Plains", [], []))


# -- the payment ------------------------------------------------------------------------------


def test_payment_does_not_tap_a_chalice_without_counters() -> None:
    state = _state([_permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [])])
    wastes = _tap("wastes", "Wastes — {T}: Add {C}.", "waste")
    chalice = _tap("chalice", _CHALICE_LABEL, "c")
    # Listed first, so an alphabetical or positional tie-break would pick the Chalice.
    response = _policy().decide(_payment([chalice, wastes], state))
    assert response["selected_option_ids"] == ["wastes"]


def test_payment_does_not_use_the_storage_ability_without_counters() -> None:
    state = _state([_permanent("m", "Mage-Ring Network", [_PLAIN_RULE, _STORAGE_RULE], [])])
    storage = _tap("storage", _STORAGE_LABEL, "m")
    plain = _tap("plain", _PLAIN_LABEL, "m")
    response = _policy().decide(_payment([storage, plain], state))
    assert response["selected_option_ids"] == ["plain"]


def test_payment_still_taps_a_chalice_that_has_a_counter() -> None:
    # Control: the Chalice is the only source on offer and holds a counter, so it is selectable.
    state = _state(
        [_permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [{"type": "charge", "count": 1}])]
    )
    chalice = _tap("chalice", _CHALICE_LABEL, "c")
    response = _policy().decide(_payment([chalice], state))
    assert response["selected_option_ids"] == ["chalice"]


def test_payment_still_uses_the_storage_ability_with_counters() -> None:
    # Control: with a storage counter on the land the ability yields mana and stays on offer.
    state = _state(
        [
            _permanent(
                "m",
                "Mage-Ring Network",
                [_PLAIN_RULE, _STORAGE_RULE],
                [{"type": "storage", "count": 2}],
            )
        ]
    )
    storage = _tap("storage", _STORAGE_LABEL, "m")
    response = _policy().decide(_payment([storage], state))
    assert response["selected_option_ids"] == ["storage"]


# -- what the pilot counts as spendable --------------------------------------------------------


def _wastes_and(extra: dict[str, Any]) -> dict[str, Any]:
    state = _state([extra])
    state["players"][0]["battlefield"][0]["abilities"] = ["{T}: Add {C}."]
    return state


def test_a_starved_chalice_is_not_counted_as_a_mana_source() -> None:
    # Wastes plus a Chalice with no counters is one mana, not two.
    state = _wastes_and(_permanent("c", "Everflowing Chalice", [_CHALICE_RULE], []))
    policy = _policy()
    assert policy._mana_budget(state) == 1
    assert policy._available_mana(state["players"][0], state=state) == 1


def test_a_chalice_with_a_counter_is_still_counted() -> None:
    # Control: one charge counter makes it a source.
    state = _wastes_and(
        _permanent("c", "Everflowing Chalice", [_CHALICE_RULE], [{"type": "charge", "count": 1}])
    )
    policy = _policy()
    assert policy._mana_budget(state) == 2
    assert policy._available_mana(state["players"][0], state=state) == 2


def test_a_storage_land_keeps_counting_through_its_plain_ability() -> None:
    # Control: Mage-Ring Network without storage counters still taps for {C}.
    state = _wastes_and(_permanent("m", "Mage-Ring Network", [_PLAIN_RULE, _STORAGE_RULE], []))
    policy = _policy()
    assert policy._mana_budget(state) == 2
    assert policy._available_mana(state["players"][0], state=state) == 2
