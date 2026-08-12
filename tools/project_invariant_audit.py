from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
LIMITATION = "LIMITATION"
NOT_APPLICABLE = "NOT_APPLICABLE"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _result(
    check_id: str,
    status: str,
    *,
    evidence: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "evidence": evidence or {},
        "limitations": limitations or [],
    }


def _structural_configs(opponent_dir: Path) -> list[Path]:
    paths = [opponent_dir / "current_structural_profiles.json"]
    paths.extend(sorted(opponent_dir.glob("*_structural_profile.json")))
    return [path for path in paths if path.is_file()]


def _collect_structural_profile_ids(
    opponent_dir: Path,
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    profile_ids: set[str] = set()
    duplicate_records: list[dict[str, Any]] = []
    specs: list[dict[str, Any]] = []
    first_source: dict[str, str] = {}
    for path in _structural_configs(opponent_dir):
        payload = _load_json(path)
        rows = payload.get("profiles")
        if not isinstance(rows, list):
            duplicate_records.append({"kind": "missing_profiles_list", "source": path.name})
            continue
        local_seen: set[str] = set()
        for raw_spec in rows:
            if not isinstance(raw_spec, dict) or not str(raw_spec.get("deck_id", "")):
                duplicate_records.append({"kind": "invalid_profile_record", "source": path.name})
                continue
            spec = dict(raw_spec)
            deck_id = str(spec["deck_id"])
            specs.append(spec)
            if deck_id in local_seen:
                duplicate_records.append(
                    {"deck_id": deck_id, "kind": "duplicate_within_file", "source": path.name}
                )
            local_seen.add(deck_id)
            if deck_id in first_source and first_source[deck_id] != path.name:
                duplicate_records.append(
                    {
                        "deck_id": deck_id,
                        "kind": "duplicate_across_files",
                        "source": path.name,
                        "first_source": first_source[deck_id],
                    }
                )
            else:
                first_source[deck_id] = path.name
            profile_ids.add(deck_id)
    return profile_ids, duplicate_records, specs


def _collect_exact_profile_ids(opponent_dir: Path) -> tuple[set[str], list[dict[str, Any]]]:
    profile_ids: set[str] = set()
    problems: list[dict[str, Any]] = []
    for path in sorted(opponent_dir.glob("*_precon.json")):
        payload = _load_json(path)
        profile_id = str(payload.get("profile_id", ""))
        if not profile_id:
            problems.append({"kind": "missing_exact_profile_id", "source": path.name})
        elif profile_id in profile_ids:
            problems.append(
                {
                    "kind": "duplicate_exact_profile_id",
                    "profile_id": profile_id,
                    "source": path.name,
                }
            )
        profile_ids.add(profile_id)
        if payload.get("list_status") != "official_precon":
            problems.append(
                {
                    "kind": "precon_status_mismatch",
                    "profile_id": profile_id,
                    "source": path.name,
                    "list_status": payload.get("list_status"),
                }
            )
        deck = payload.get("deck")
        cards = deck.get("cards", []) if isinstance(deck, dict) else []
        quantity = sum(int(card.get("quantity", 0)) for card in cards if isinstance(card, dict))
        if quantity != 100:
            problems.append(
                {
                    "kind": "precon_quantity_mismatch",
                    "profile_id": profile_id,
                    "source": path.name,
                    "quantity": quantity,
                }
            )
    profile_ids.discard("")
    return profile_ids, problems


def _evidence_boundary_problems(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for spec in specs:
        deck_id = str(spec.get("deck_id", "unknown"))
        kinds = {str(value).casefold() for value in spec.get("evidence_kinds", [])}
        for lower, promoted in (
            ("synthetic_completion", "directly_observed"),
            ("synthetic", "observed"),
            ("inferred", "verified_full_deck"),
        ):
            if lower in kinds and promoted in kinds:
                problems.append(
                    {
                        "deck_id": deck_id,
                        "kind": "forbidden_evidence_promotion",
                        "from": lower,
                        "to": promoted,
                    }
                )
        for field in ("evidence_status", "source_status", "validation_level"):
            value = str(spec.get(field, "")).strip().casefold()
            if value in {"external_rules_engine", "external_engine_verified"}:
                problems.append(
                    {
                        "deck_id": deck_id,
                        "kind": "structural_profile_claims_external_rules_engine",
                        "field": field,
                    }
                )
    return problems


def _broken_aliases(registry: dict[str, Any], known_targets: set[str]) -> list[str]:
    current = registry.get("current")
    aliases = registry.get("aliases")
    if not isinstance(current, dict) or not isinstance(aliases, dict):
        return ["<invalid_registry_shape>"]
    broken: list[str] = []
    for alias in sorted(str(key) for key in aliases):
        seen = {alias}
        reference = alias
        for _ in range(len(aliases) + 2):
            raw_alias = aliases.get(reference)
            if isinstance(raw_alias, dict):
                reference = str(raw_alias.get("redirect", ""))
            elif reference in current:
                target = str(current[reference])
                if target in known_targets:
                    break
                reference = target
            elif reference in known_targets:
                break
            else:
                broken.append(alias)
                break
            if not reference or reference in seen:
                broken.append(alias)
                break
            seen.add(reference)
        else:
            broken.append(alias)
    return broken


def _kaervek_problems(
    root: Path, registry: dict[str, Any], specs: list[dict[str, Any]]
) -> list[str]:
    problems: list[str] = []
    current = registry.get("current")
    registry_hash = str(registry.get("kaervek_deck_hash", ""))
    if not isinstance(current, dict) or current.get("kaervek/current") != "kaervek/current":
        problems.append("registry_target")
    if len(registry_hash) != 64:
        problems.append("registry_hash")
    kaervek_specs = [spec for spec in specs if spec.get("deck_id") == "kaervek/current"]
    if len(kaervek_specs) != 1 or str(kaervek_specs[0].get("deck_hash", "")) != registry_hash:
        problems.append("structural_profile_hash")
    deck_path = root / "data/decks/opponents/kaervek/current/deck.json"
    if not deck_path.is_file():
        problems.append("exact_deck_missing")
        return problems
    deck = _load_json(deck_path)
    if deck.get("verified_full_list") is not True or deck.get("deck_hash") != registry_hash:
        problems.append("exact_deck_identity")
    cards = deck.get("cards")
    quantity = (
        sum(int(card.get("quantity", 0)) for card in cards if isinstance(card, dict))
        if isinstance(cards, list)
        else 0
    )
    if quantity != 100:
        problems.append("exact_deck_quantity")
    return problems


def audit_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    opponent_dir = root / "data/opponents"
    if not opponent_dir.is_dir():
        return _finalize([_result("opponent_data_present", FAIL, evidence={"missing": True})])

    structural_ids, structural_duplicates, specs = _collect_structural_profile_ids(opponent_dir)
    exact_ids, exact_problems = _collect_exact_profile_ids(opponent_dir)
    evidence_problems = _evidence_boundary_problems(specs)
    checks = [
        _result(
            "unique_structural_profile_ids",
            PASS if not structural_duplicates else FAIL,
            evidence={"profile_count": len(structural_ids), "duplicates": structural_duplicates},
        ),
        _result(
            "official_precon_integrity",
            PASS if not exact_problems else FAIL,
            evidence={"profile_count": len(exact_ids), "problems": exact_problems},
        ),
        _result(
            "structural_evidence_boundaries",
            PASS if not evidence_problems else FAIL,
            evidence={"problems": evidence_problems},
        ),
    ]

    registry_path = opponent_dir / "opponent_registry.json"
    if registry_path.is_file():
        registry = _load_json(registry_path)
        current = registry.get("current")
        known_targets = structural_ids | exact_ids
        current_targets = (
            set(str(value) for value in current.values()) if isinstance(current, dict) else set()
        )
        missing_targets = sorted(current_targets - known_targets)
        broken_aliases = _broken_aliases(registry, known_targets)
        kaervek_problems = _kaervek_problems(root, registry, specs)
        checks.extend(
            [
                _result(
                    "opponent_registry_referential_integrity",
                    PASS if isinstance(current, dict) and not missing_targets else FAIL,
                    evidence={"missing_targets": missing_targets},
                ),
                _result(
                    "opponent_alias_referential_integrity",
                    PASS if not broken_aliases else FAIL,
                    evidence={"broken_aliases": broken_aliases},
                ),
                _result(
                    "kaervek_frozen_semantics",
                    PASS if not kaervek_problems else FAIL,
                    evidence={"problems": kaervek_problems},
                ),
            ]
        )
    else:
        checks.extend(
            _result(check_id, FAIL)
            for check_id in (
                "opponent_registry_referential_integrity",
                "opponent_alias_referential_integrity",
                "kaervek_frozen_semantics",
            )
        )

    checks.extend(
        [
            _result(
                "drive_primary_pod_and_frequency_policy",
                LIMITATION,
                limitations=[
                    "Live Drive freshness is outside this repo-local read-only audit and must be verified separately."
                ],
            ),
            _result(
                "deck_inventory_allocation_mutation",
                NOT_APPLICABLE,
                limitations=["The auditor is read-only and executes no mutation path."],
            ),
        ]
    )
    return _finalize(checks)


def _finalize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "pass": sum(check["status"] == PASS for check in checks),
        "fail": sum(check["status"] == FAIL for check in checks),
        "limitations": sum(check["status"] == LIMITATION for check in checks),
        "not_applicable": sum(check["status"] == NOT_APPLICABLE for check in checks),
    }
    return {
        "schema_version": "1.1",
        "error_code": "PROJECT_INVARIANT_VIOLATION" if summary["fail"] else None,
        "checks": checks,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit repo-local Commander project invariants.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        report = audit_project(args.root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        report = _finalize(
            [_result("auditor_input_integrity", FAIL, evidence={"error": type(exc).__name__})]
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
