from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from commander_lab.agents import (
    GenericCommanderPilot,
    KaervekOpponentPilot,
    KorvoldAggressivePilot,
    KorvoldConservativePilot,
    KorvoldLandRebuildPilot,
    KorvoldPilot,
    KorvoldSacrificePilot,
    KorvoldValuePilot,
    RogShaiPilot,
    auto_pilot_name,
    build_pilot,
)
from commander_lab.agents.ensemble import PilotRegistry
from commander_lab.engine.structural.project import live_commander_strategy
from commander_lab.models import PilotConfig
from commander_lab.models.mulligan import MulliganPolicyName
from commander_lab.mulligan import MulliganLab, MulliganLabError

ROOT = Path(__file__).resolve().parents[2]
RETIRED_KORVOLD_CLASSES = (
    KorvoldPilot,
    KorvoldValuePilot,
    KorvoldSacrificePilot,
    KorvoldLandRebuildPilot,
    KorvoldAggressivePilot,
    KorvoldConservativePilot,
)
ALLOWED_LEGACY_BUILD_PILOT_CALLERS = frozenset(
    {
        "src/commander_lab/agents/live_routing.py",
        "src/commander_lab/agents/ensemble.py",
        "src/commander_lab/tools/service_knowledge.py",
        "src/commander_lab/tools/service_pilots.py",
    }
)


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
    assert type(pilot) is GenericCommanderPilot  # exactly, not a subclass of it
    korvold_auto = build_pilot(PilotConfig(pilot_name="auto"), strategy="korvold")
    assert type(korvold_auto) is GenericCommanderPilot


def test_live_builder_rejects_cross_family_and_retired_korvold_pilots() -> None:
    with pytest.raises(ValueError, match="family mismatch"):
        build_pilot(PilotConfig(pilot_name="RogShaiPilot"), strategy="generic")
    with pytest.raises(ValueError, match="family mismatch"):
        build_pilot(PilotConfig(pilot_name="GenericCommanderPilot"), strategy="rogshai")
    for cls in RETIRED_KORVOLD_CLASSES:
        for strategy in ("generic", "korvold", "rogshai"):
            with pytest.raises(ValueError, match="retired former-own-deck pilot"):
                build_pilot(PilotConfig(pilot_name=cls.pilot_name), strategy=strategy)


def test_all_six_korvold_pilot_classes_carry_explicit_retirement_docstring() -> None:
    assert len(RETIRED_KORVOLD_CLASSES) == 6
    for cls in RETIRED_KORVOLD_CLASSES:
        doc = (cls.__doc__ or "").casefold()
        assert "retired" in doc, f"{cls.__name__} is missing retirement docstring"
        assert "live_routing" in doc or "live routing" in doc


def test_no_unapproved_production_module_imports_legacy_pilots_build_pilot() -> None:
    src_root = ROOT / "src" / "commander_lab"
    offenders: list[str] = []
    seen_allowed: set[str] = set()
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        imports_legacy = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_pilots_mod = module == "commander_lab.agents.pilots" or (
                    node.level >= 1 and module == "pilots" and path.parent.name == "agents"
                )
                if is_pilots_mod and any(alias.name == "build_pilot" for alias in node.names):
                    imports_legacy = True
            elif isinstance(node, ast.Attribute) and node.attr == "build_pilot":
                if isinstance(node.value, ast.Name) and node.value.id == "pilots":
                    imports_legacy = True
        if imports_legacy:
            if rel in ALLOWED_LEGACY_BUILD_PILOT_CALLERS:
                seen_allowed.add(rel)
            else:
                offenders.append(rel)
    assert offenders == [], f"unapproved legacy pilots.build_pilot imports: {offenders}"
    assert seen_allowed == ALLOWED_LEGACY_BUILD_PILOT_CALLERS


def test_live_builder_preserves_rogshai_and_kaervek_families() -> None:
    assert type(build_pilot(PilotConfig(), strategy="rogshai")) is RogShaiPilot
    assert (
        type(build_pilot(PilotConfig(), strategy="punisher_control_reanimation"))
        is KaervekOpponentPilot
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
    assert all(
        value == 1.0
        for key, value in generic.weights.as_dict().items()
        if key != "political_visibility"
    )
    assert generic.weights.political_visibility == -0.65


def test_canonical_mulligan_routes_non_rogshai_fixture_to_generic() -> None:
    lab = MulliganLab(ROOT)
    generic_deck = next(
        deck
        for deck in lab.decks.values()
        if deck.commander_strategy in {"aggro", "control", "engine"}
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
