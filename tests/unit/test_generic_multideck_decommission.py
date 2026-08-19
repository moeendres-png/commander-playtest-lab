from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from commander_lab.agents import GenericCommanderPilot, KaervekOpponentPilot, RogShaiPilot
from commander_lab.agents import auto_pilot_name, build_pilot
from commander_lab.agents.ensemble import PilotRegistry
from commander_lab.engine.structural.project import live_commander_strategy
from commander_lab.models import PilotConfig
from commander_lab.models.mulligan import MulliganPolicyName
from commander_lab.mulligan import MulliganLab, MulliganLabError

ROOT = Path(__file__).resolve().parents[2]


def _deck_with_commanders(*commanders: str) -> SimpleNamespace:
    return SimpleNamespace(commander=SimpleNamespace(commanders=commanders))


def test_live_commander_strategy_is_explicit_rogshai_or_generic() -> None:
    assert (
        live_commander_strategy(
            _deck_with_commanders("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh")
        )
        == "rogshai"
    )
    assert (
        live_commander_strategy(
            _deck_with_commanders("Rograkh, Son of Rohgahh", "Ishai, Ojutai Dragonspeaker")
        )
        == "rogshai"
    )
    assert live_commander_strategy(_deck_with_commanders("Unknown Commander")) == "generic"
    assert live_commander_strategy(_deck_with_commanders("Korvold, Fae-Cursed King")) == "generic"


def test_live_auto_pilot_does_not_treat_unknown_or_korvold_as_rogshai() -> None:
    assert auto_pilot_name("rogshai") == "RogShaiPilot"
    assert auto_pilot_name("unknown-family") == "GenericCommanderPilot"
    assert auto_pilot_name("korvold") == "GenericCommanderPilot"


def test_live_builder_uses_generic_pilot_for_unknown_family() -> None:
    pilot = build_pilot(PilotConfig(), strategy="unknown-family")
    assert isinstance(pilot, GenericCommanderPilot)


def test_live_builder_rejects_cross_family_and_retired_korvold_pilots() -> None:
    with pytest.raises(ValueError, match="family mismatch"):
        build_pilot(PilotConfig(pilot_name="RogShaiPilot"), strategy="generic")
    with pytest.raises(ValueError, match="family mismatch"):
        build_pilot(PilotConfig(pilot_name="GenericCommanderPilot"), strategy="rogshai")
    with pytest.raises(ValueError, match="retired former-own-deck pilot"):
        build_pilot(PilotConfig(pilot_name="KorvoldPilot"), strategy="generic")


def test_live_builder_preserves_rogshai_and_kaervek_families() -> None:
    assert isinstance(build_pilot(PilotConfig(), strategy="rogshai"), RogShaiPilot)
    assert isinstance(
        build_pilot(PilotConfig(), strategy="punisher_control_reanimation"),
        KaervekOpponentPilot,
    )


def test_canonical_pilot_registry_contains_generic_and_rogshai_but_no_korvold() -> None:
    profiles = PilotRegistry(ROOT).profiles()
    families = {profile.commander_family for profile in profiles}
    names = {profile.pilot_name for profile in profiles}
    assert families == {"generic", "rogshai"}
    assert "GenericCommanderPilot" in names
    assert not any(name.casefold().startswith("korvold") for name in names)
    generic = next(profile for profile in profiles if profile.pilot_name == "GenericCommanderPilot")
    assert generic.supported_deck_hashes == ()
    assert all(value == 1.0 for key, value in generic.weights.as_dict().items() if key != "political_visibility")
    assert generic.weights.political_visibility == -0.65


def test_canonical_mulligan_routes_non_rogshai_fixture_to_generic() -> None:
    lab = MulliganLab(ROOT)
    generic_deck = next(
        deck for deck in lab.decks.values() if deck.commander_strategy in {"aggro", "control", "engine"}
    )
    assert (
        lab._pilot_name_for_policy(
            generic_deck.deck_id,
            MulliganPolicyName.CURRENT_PILOT,
            "baseline",
        )
        == "GenericCommanderPilot"
    )
    with pytest.raises(MulliganLabError, match="family mismatch"):
        lab._pilot_name_for_policy(
            generic_deck.deck_id,
            MulliganPolicyName.CURRENT_PILOT,
            "RogShaiPilot",
        )


def test_canonical_mulligan_keeps_rogshai_specialization() -> None:
    lab = MulliganLab(ROOT)
    assert (
        lab._pilot_name_for_policy(
            "rogshai/current",
            MulliganPolicyName.CURRENT_PILOT,
            "baseline",
        )
        == "RogShaiPilot"
    )
