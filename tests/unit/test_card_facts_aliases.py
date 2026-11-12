"""Identity-preserving public XMage facts export and catalog lookups."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.deck_readiness import CardReadinessStatus, _CardData
from commander_lab.engine.structural.card_facts import CARD_FACTS_SCHEMA_VERSION, CardFactsCatalog

ROOT = Path(__file__).resolve().parents[2]


def _exporter():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "facts_export_test", ROOT / "scripts/export_xmage_card_facts.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(name: str, **changes: str) -> dict[str, str]:
    return {
        "NAME": name,
        "P": "2",
        "T": "3",
        "L": "",
        "MV": "2",
        "TY": "CREATURE",
        "ST": "Cat",
        "SP": "",
        "MC": "{1}@@@{U}",
        "R": "Flying",
        "H": "FALSE",
        "F": "",
        "S": "",
        "O": "",
        "D": "",
        **changes,
    }


def test_coherent_rows_aliases_and_ambiguity_are_distinguished(tmp_path: Path) -> None:
    mod = _exporter()
    rows = [
        _row("Plain", S="Back"),
        _row("Plain", S="Back"),
        _row("Left // Right", P="4"),
        _row("Left", H="TRUE", P="1"),
        _row("Both", H="TRUE", P="1"),
        _row("Both", P="3"),
        _row("Conflicted", P="2", T="6"),
        _row("Conflicted", P="5", T="3"),
        _row("Different Faces", S="One"),
        _row("Different Faces", S="Two"),
    ]
    payload = mod.build_facts(rows, None)
    assert payload == mod.build_facts(reversed(rows), None)
    assert set(payload["cards"]) == {"Plain", "Left // Right"}
    assert payload["ambiguous"] == ["Both", "Conflicted", "Different Faces"]
    assert payload["excluded_split_halves"] == ["Left"]
    assert payload["aliases"] == {"Plain // Back": "Plain"}
    assert payload["missing"] == []
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(json.dumps(payload), encoding="utf-8")
    catalog = CardFactsCatalog.from_json(facts_path)
    assert catalog.get("Plain // Back").name == "Plain"
    assert catalog.get("Plain // Wrong") is None
    assert catalog.get("Left").name == "Left // Right"
    assert catalog.get("Both") is None
    subset = mod.build_facts(rows, {"Plain // Back", "Plain // Wrong", "Both", "Left"})
    assert set(subset["cards"]) == {"Plain // Back", "Left"}
    assert subset["missing"] == ["Plain // Wrong"]
    assert "Both" in subset["ambiguous"]


def test_invalid_mana_and_alias_target_fail_closed(tmp_path: Path) -> None:
    mod = _exporter()
    for mv in ("", "NaN", "-1"):
        with pytest.raises(ValueError, match="mana value"):
            mod.build_facts([_row("Invalid", MV=mv)], None)
    payload = mod.build_facts([_row("Present")], None)
    payload["aliases"] = {"Claim // Wrong": "Absent"}
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="alias"):
        CardFactsCatalog.from_json(path)


def test_each_engine_face_relation_supplies_only_its_known_pair() -> None:
    mod = _exporter()
    rows = [
        _row("Flip", F="Flipped"),
        _row("Transform", S="Transformed"),
        _row("Option", O="Spell"),
        _row("Double", D="Other"),
    ]
    result = mod.build_facts(rows, None)
    assert result["aliases"] == {
        "Flip // Flipped": "Flip",
        "Transform // Transformed": "Transform",
        "Option // Spell": "Option",
        "Double // Other": "Double",
    }


def test_conflicting_retained_lookup_does_not_override_standalone(tmp_path: Path) -> None:
    mod = _exporter()
    payload = mod.build_facts([_row("Part", P="2"), _row("Part // Side", P="5")], None)
    payload["retained_lookup"] = {"part": "Part // Side"}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicts"):
        CardFactsCatalog.from_json(path)


def test_retained_names_require_facts_and_verified_identity(tmp_path: Path) -> None:
    mod = _exporter()
    fresh = mod.build_facts([_row("Elan", S="Back")], None)
    fact = fresh["cards"]["Elan"]
    path = tmp_path / "old.json"
    prior = {
        "schema_version": CARD_FACTS_SCHEMA_VERSION,
        "cards": {"Élan": fact, "Elan // Back": fact},
    }
    path.write_text(json.dumps(prior), encoding="utf-8")
    mod.retain_catalog(fresh, path)
    assert fresh["cards"]["Élan"] == fact
    assert fresh["cards"]["Elan // Back"] == fact
    assert fresh["retained_catalog"]["card_count"] == 2
    for old in ({"Elan // Wrong": fact}, {"Élan": {**fact, "power": 999}}):
        path.write_text(json.dumps({**prior, "cards": old}), encoding="utf-8")
        with pytest.raises(ValueError, match="retained"):
            mod.retain_catalog(mod.build_facts([_row("Elan", S="Back")], None), path)


def test_retention_preserves_prior_index_and_implicit_front_identity(tmp_path: Path) -> None:
    mod = _exporter()
    rows = [
        _row("Elan"),
        _row("Front", S="Back"),
        _row("Split // Side", P="5"),
        _row("Split", H="TRUE", P="1"),
    ]
    fresh = mod.build_facts(rows, None)
    prior_cards = {
        "Élan": fresh["cards"]["Elan"],
        "Front // Back": fresh["cards"]["Front"],
        "Split // Side": fresh["cards"]["Split // Side"],
    }
    prior_path = tmp_path / "old.json"
    prior_path.write_text(
        json.dumps({"schema_version": CARD_FACTS_SCHEMA_VERSION, "cards": prior_cards}),
        encoding="utf-8",
    )
    previous = CardFactsCatalog.from_json(prior_path)
    mod.retain_catalog(fresh, prior_path)
    current_path = tmp_path / "current.json"
    current_path.write_text(json.dumps(fresh), encoding="utf-8")
    current = CardFactsCatalog.from_json(current_path)
    assert {key: current._by_key.get(key) for key in previous._by_key} == previous._by_key
    assert current.get("Front").name == "Front // Back"
    assert current.get("Split").name == "Split // Side"
    assert current.get("Élan").name == "Élan"
    assert current.get("Front // Wrong") is None


def test_retention_rejects_competing_standalone_front(tmp_path: Path) -> None:
    mod = _exporter()
    fresh = mod.build_facts([_row("Part // Side", P="5"), _row("Part", P="2")], None)
    prior_path = tmp_path / "old.json"
    prior_path.write_text(
        json.dumps(
            {
                "schema_version": CARD_FACTS_SCHEMA_VERSION,
                "cards": {"Part // Side": fresh["cards"]["Part // Side"]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="different fresh engine fact"):
        mod.retain_catalog(fresh, prior_path)


def test_retention_failure_never_replaces_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _exporter()
    row = _row("Real", S="Back")
    prior = tmp_path / "old.json"
    fake = mod.build_facts([row], None)["cards"]["Real"]
    prior.write_text(
        json.dumps({"schema_version": CARD_FACTS_SCHEMA_VERSION, "cards": {"Real // Wrong": fake}}),
        encoding="utf-8",
    )
    output = tmp_path / "out.json"
    output.write_text("unchanged", encoding="utf-8")

    def export(_db: Path, _jar: Path, dest: Path) -> str:
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return "a" * 64

    monkeypatch.setattr(mod, "export", export)
    monkeypatch.setattr(mod, "wanted_names", lambda *args: pytest.fail("owner selection read"))
    monkeypatch.setattr(
        sys, "argv", ["export", "--all-cards", "--retain-catalog", str(prior), "--out", str(output)]
    )
    with pytest.raises(ValueError, match="retained name"):
        mod.main()
    assert output.read_text(encoding="utf-8") == "unchanged"


def test_pilot_and_readiness_refuse_unattested_pairs(tmp_path: Path) -> None:
    mod = _exporter()
    payload = mod.build_facts(
        [
            _row("Plain", S="Back"),
            _row("Split // Other"),
            _row("Uncertain", P="1"),
            _row("Uncertain", P="2"),
        ],
        None,
    )
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(json.dumps(payload), encoding="utf-8")
    pilot_path = tmp_path / "pilot.json"
    pilot_path.write_text(
        json.dumps(
            {
                "cards": {
                    name: {"name": name}
                    for name in ("Plain", "Plain // Back", "Split // Other", "Uncertain")
                }
            }
        ),
        encoding="utf-8",
    )
    assert card_facts("Plain // Back", pilot_path) is not None
    assert card_facts("Plain // Wrong", pilot_path) is None
    assert card_facts("Split", pilot_path).name == "Split // Other"
    assert card_facts("Split // Wrong", pilot_path) is None
    data = _CardData(facts_path, pilot_path)
    assert data.status_of("Plain // Back") is CardReadinessStatus.OK
    assert data.status_of("Plain // Wrong") is CardReadinessStatus.NO_CARD_FACTS
    assert data.status_of("Uncertain") is CardReadinessStatus.NO_CARD_FACTS
    assert data.status_of("Split") is CardReadinessStatus.OK


def test_exact_standalone_name_takes_priority_over_split_alias(tmp_path: Path) -> None:
    mod = _exporter()
    payload = mod.build_facts([_row("Part // Side", P="5"), _row("Part", P="2")], None)
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    catalog = CardFactsCatalog.from_json(path)
    assert catalog.get("Part").power == 2
    assert catalog.get("Part // Side").power == 5
