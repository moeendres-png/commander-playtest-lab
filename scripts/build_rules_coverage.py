#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED_COVERAGE = {
    "external_engine_verified",
    "external_engine_partial",
    "tactical_only",
    "structural_only",
    "unsupported",
    "provider_disagreement",
}
CURRENT_SOURCE_FILES = (
    "data/decks/rogshai_current.json",
    "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
    "data/cards/structural_role_profiles.json",
    "data/rules/validation_registry.json",
    "data/rules/project_critical_interactions.json",
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _name(row: object) -> str | None:
    if isinstance(row, str):
        return row.strip() or None
    if not isinstance(row, dict):
        return None
    for key in ("oracle_name", "name", "Oracle-Name"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _record(records: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return records.setdefault(
        name,
        {
            "oracle_name": name,
            "deck_versions": [],
            "source_status": [],
            "evidence_files": [],
        },
    )


def _load_current_candidate_registry(root: Path, records: dict[str, dict[str, Any]]) -> None:
    path = root / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    payload = load(path)
    eligible = payload.get("eligible_by_deck", {}) if isinstance(payload, dict) else {}
    if not isinstance(eligible, dict):
        raise RuntimeError("current candidate eligibility registry has invalid eligible_by_deck")
    for deck_id, rows in eligible.items():
        if not isinstance(rows, dict):
            continue
        for name, facts in rows.items():
            if not isinstance(name, str) or not isinstance(facts, dict):
                continue
            rec = _record(records, name)
            rec["inventory_candidate"] = True
            quantity = facts.get("physical_available_quantity")
            if isinstance(quantity, int) and not isinstance(quantity, bool):
                rec["inventory_quantity"] = max(int(rec.get("inventory_quantity", 0)), quantity)
            rec["inventory_metadata"] = {
                "color_identity": facts.get("color_identity"),
                "commander_legal": facts.get("commander_legal"),
                "last_verified_at": facts.get("last_verified_at"),
            }
            rec["deck_versions"].append(f"candidate-pool/{deck_id}")
            rec["source_status"].append("current_candidate_eligibility")
            rec["evidence_files"].append(str(path.relative_to(root)))


def _load_current_rogshai(root: Path, records: dict[str, dict[str, Any]]) -> None:
    path = root / "data/decks/rogshai_current.json"
    payload = load(path)
    if not isinstance(payload, dict) or payload.get("deck_id") != "rogshai/current":
        raise RuntimeError("current RogShai deck registry is missing or invalid")
    cards = payload.get("cards", [])
    if not isinstance(cards, list):
        raise RuntimeError("current RogShai deck cards must be a list")
    quantity_total = 0
    for row in cards:
        if not isinstance(row, dict):
            continue
        name = _name(row)
        if name is None:
            continue
        quantity = row.get("quantity", 1)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise RuntimeError(f"invalid current RogShai quantity for {name}")
        quantity_total += quantity
        rec = _record(records, name)
        rec["deck_versions"].append("rogshai/current")
        rec["source_status"].append("current_control")
        rec["evidence_files"].append(str(path.relative_to(root)))
    if quantity_total != 100:
        raise RuntimeError(f"current RogShai registry expected 100 cards, got {quantity_total}")


def _load_current_opponents(root: Path, records: dict[str, dict[str, Any]]) -> None:
    opponents_root = root / "data/decks/opponents"
    if opponents_root.is_dir():
        for path in sorted(opponents_root.glob("*.json")):
            payload = load(path)
            if not isinstance(payload, dict):
                continue
            deck_id = str(payload.get("deck_id") or f"opponent/{path.stem}")
            raw_rows = payload.get("cards", payload.get("mainboard", []))
            if isinstance(raw_rows, dict):
                raw_rows = list(raw_rows)
            if not isinstance(raw_rows, list):
                continue
            for row in raw_rows:
                name = _name(row)
                if name is None:
                    continue
                rec = _record(records, name)
                rec["deck_versions"].append(deck_id)
                rec["source_status"].append(
                    str(
                        payload.get("evidence_status")
                        or payload.get("data_status")
                        or "current_opponent"
                    )
                )
                rec["evidence_files"].append(str(path.relative_to(root)))

    ensembles_root = root / "data/opponent_ensembles"
    if ensembles_root.is_dir():
        for path in sorted(ensembles_root.glob("*.json")):
            payload = load(path)
            if not isinstance(payload, dict):
                continue
            ensemble_id = str(payload.get("ensemble_id") or path.stem)
            for variant in payload.get("variants", []):
                if not isinstance(variant, dict):
                    continue
                variant_id = str(variant.get("variant_id") or "variant")
                for key, status in (
                    ("known_cards", "known"),
                    ("assumed_cards", "synthetic_assumption"),
                ):
                    rows = variant.get(key, [])
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        name = _name(row)
                        if name is None:
                            continue
                        rec = _record(records, name)
                        rec["deck_versions"].append(f"{ensemble_id}/{variant_id}")
                        rec["source_status"].append(status)
                        rec["evidence_files"].append(str(path.relative_to(root)))


def _scenario_scope(scenario_id: str) -> str:
    if scenario_id.startswith("rogshai_"):
        return "current_rogshai_regression"
    if scenario_id.startswith("opponent_"):
        return "current_opponent_or_generic_regression"
    if scenario_id.startswith("korvold_"):
        return "historical_generic_regression_only"
    return "generic_rules_regression"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/rules_coverage_current")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = (root / args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    for relative in CURRENT_SOURCE_FILES:
        if not (root / relative).is_file():
            raise RuntimeError(f"required current rules-coverage source is missing: {relative}")

    role_data = load(root / "data/cards/structural_role_profiles.json")
    validation = load(root / "data/rules/validation_registry.json")
    package_path = root / "data/packages/package_registry.json"
    package_data = load(package_path) if package_path.is_file() else {"packages": []}
    oracle_path = root / "data/cards/oracle_subset.json"
    oracle_data = load(oracle_path) if oracle_path.is_file() else {"cards": []}

    roles = {
        row["oracle_name"]: row.get("roles", [])
        for row in role_data.get("profiles", [])
        if isinstance(row, dict) and isinstance(row.get("oracle_name"), str)
    }
    tactical_cards = validation.get("cards", {}) if isinstance(validation, dict) else {}
    oracle = {
        row["oracle_name"]: row
        for row in oracle_data.get("cards", [])
        if isinstance(row, dict) and isinstance(row.get("oracle_name"), str)
    }
    packages: dict[str, set[str]] = defaultdict(set)
    for package in package_data.get("packages", []):
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("package_id") or "unknown")
        for key in (
            "core_cards",
            "support_cards",
            "optional_cards",
            "enablers",
            "payoffs",
            "finishers",
        ):
            for row in package.get(key, []):
                name = _name(row)
                if name:
                    packages[name].add(package_id)

    records: dict[str, dict[str, Any]] = {}
    _load_current_candidate_registry(root, records)
    _load_current_rogshai(root, records)
    _load_current_opponents(root, records)

    coverage: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for name in sorted(records):
        rec = records[name]
        tactical_row = tactical_cards.get(name, {}) if isinstance(tactical_cards, dict) else {}
        tactical = (
            isinstance(tactical_row, dict) and int(tactical_row.get("tactical_passed", 0)) > 0
        )
        structural = bool(roles.get(name))
        status = "tactical_only" if tactical else "structural_only" if structural else "unsupported"
        assert status in ALLOWED_COVERAGE
        counts[status] += 1
        oracle_row = oracle.get(name, {})
        coverage.append(
            {
                "oracle_name": name,
                "oracle_id": oracle_row.get("oracle_id") if isinstance(oracle_row, dict) else None,
                "deck_versions": sorted(set(rec["deck_versions"])),
                "roles": roles.get(name, []),
                "packages": sorted(packages.get(name, set())),
                "structural_support": structural,
                "tactical_oracle_support": tactical,
                "xmage_recognized": False,
                "xmage_rules_verified": False,
                "forge_recognized": False,
                "forge_rules_verified": False,
                "external_rules_engine_evidence": False,
                "coverage_status": status,
                "fallback_policy": (
                    "tactical_oracle"
                    if tactical
                    else "structural_only"
                    if structural
                    else "unsupported"
                ),
                "inventory_candidate": bool(rec.get("inventory_candidate")),
                "inventory_quantity": rec.get("inventory_quantity"),
                "inventory_metadata": rec.get("inventory_metadata"),
                "source_status": sorted(set(str(value) for value in rec["source_status"] if value)),
                "evidence_files": sorted(set(rec["evidence_files"])),
            }
        )

    scenario_path = root / "data/rules/rules_scenario_registry.json"
    existing_scenarios = load(scenario_path) if scenario_path.is_file() else {"scenarios": []}
    scenarios: list[dict[str, Any]] = []
    for raw in existing_scenarios.get("scenarios", []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        scenario_id = str(row.get("scenario_id") or "")
        row["coverage_scope"] = _scenario_scope(scenario_id)
        row["current_source_registry"] = scenario_id.startswith(("rogshai_", "opponent_"))
        scenarios.append(row)

    deck_stats: dict[str, Any] = {}
    for deck_id in sorted({deck for row in coverage for deck in row["deck_versions"]}):
        rows = [row for row in coverage if deck_id in row["deck_versions"]]
        deck_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            deck_counts[row["coverage_status"]] += 1
        deck_stats[deck_id] = {
            "unique_oracle_names": len(rows),
            "coverage": dict(deck_counts),
        }

    card_registry = {
        "schema_version": 3,
        "source_scope": "current_registries_only",
        "dated_canonical_import_used": False,
        "current_source_files": list(CURRENT_SOURCE_FILES),
        "external_engine_execution_status": "not_run_by_builder",
        "cards": coverage,
        "coverage_counts": dict(counts),
        "inventory_candidate_count": sum(1 for row in coverage if row["inventory_candidate"]),
        "deck_statistics": deck_stats,
        "truth_boundary": (
            "Coverage labels describe registered Structural/Tactical support only. They do not imply "
            "real external-rules-engine validation. Dated canonical_import snapshots are excluded."
        ),
    }
    scenario_registry = {
        "schema_version": 3,
        "source_scope": "current_plus_explicit_generic_regressions",
        "external_engine_execution_status": "not_run_by_builder",
        "scenarios": scenarios,
    }
    unsupported = [row for row in coverage if row["coverage_status"] == "unsupported"]
    differences = {
        "schema_version": 3,
        "status": "not_run",
        "provider_comparisons": [],
        "reason": "Rules coverage construction does not execute XMage or Forge.",
    }

    outputs = {
        "CARD_RULES_COVERAGE.json": card_registry,
        "RULES_SCENARIO_REGISTRY.json": scenario_registry,
        "GOLDEN_RULES_SCENARIOS.json": scenario_registry,
        "GOLDEN_RULES_CORPUS.json": scenario_registry,
        "UNSUPPORTED_CARD_REGISTER.json": {"schema_version": 3, "cards": unsupported},
        "PROVIDER_DIFFERENCE_REGISTER.json": differences,
    }
    for name, payload in outputs.items():
        (out / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "source_scope": "current_registries_only",
                "dated_canonical_import_used": False,
                "cards": len(coverage),
                "inventory_candidates": card_registry["inventory_candidate_count"],
                "coverage_counts": dict(counts),
                "scenarios": len(scenarios),
                "deck_statistics": deck_stats,
                "output_directory": str(out),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())