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
    return json.loads(path.read_text(encoding="utf-8"))


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
    return [path for path in paths if path.exists()]


def _collect_structural_profile_ids(
    opponent_dir: Path,
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    profile_ids: set[str] = set()
    duplicate_records: list[dict[str, Any]] = []
    specs: list[dict[str, Any]] = []
    first_source: dict[str, str] = {}

    for path in _structural_configs(opponent_dir):
        payload = _load_json(path)
        local_seen: set[str] = set()
        for raw_spec in payload.get("profiles", []):
            spec = dict(raw_spec)
            deck_id = str(spec["deck_id"])
            specs.append(spec)
            if deck_id in local_seen:
                duplicate_records.append(
                    {
                        "deck_id": deck_id,
                        "kind": "duplicate_within_file",
                        "source": str(path),
                    }
                )
            local_seen.add(deck_id)
            if deck_id in first_source and first_source[deck_id] != str(path):
                duplicate_records.append(
                    {
                        "deck_id": deck_id,
                        "kind": "duplicate_across_files",
                        "source": str(path),
                        "first_source": first_source[deck_id],
                    }
                )
            else:
                first_source[deck_id] = str(path)
            profile_ids.add(deck_id)
    return profile_ids, duplicate_records, specs


def _collect_exact_profile_ids(
    opponent_dir: Path,
) -> tuple[set[str], list[dict[str, Any]]]:
    profile_ids: set[str] = set()
    problems: list[dict[str, Any]] = []
    for path in sorted(opponent_dir.glob("*_precon.json")):
        payload = _load_json(path)
        profile_id = str(payload.get("profile_id", ""))
        if profile_id:
            if profile_id in profile_ids:
                problems.append(
                    {
                        "kind": "duplicate_exact_profile_id",
                        "profile_id": profile_id,
                        "source": str(path),
                    }
                )
            profile_ids.add(profile_id)
        if payload.get("list_status") != "official_precon":
            problems.append(
                {
                    "kind": "precon_status_mismatch",
                    "profile_id": profile_id,
                    "source": str(path),
                    "list_status": payload.get("list_status"),
                }
            )
        deck = payload.get("deck", {})
        cards = deck.get("cards", []) if isinstance(deck, dict) else []
        quantity = sum(int(card.get("quantity", 0)) for card in cards if isinstance(card, dict))
        if quantity != 100:
            problems.append(
                {
                    "kind": "precon_quantity_mismatch",
                    "profile_id": profile_id,
                    "source": str(path),
                    "quantity": quantity,
                }
            )
    return profile_ids, problems


def _evidence_boundary_problems(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for spec in specs:
        deck_id = str(spec.get("deck_id", "unknown"))
        kinds = {str(value) for value in spec.get("evidence_kinds", [])}
        forbidden_pairs = (
            ("synthetic_completion", "directly_observed"),
            ("inferred", "verified_full_deck"),
        )
        for lower, promoted in forbidden_pairs:
            if lower in kinds and promoted in kinds:
                problems.append(
                    {
                        "deck_id": deck_id,
                        "kind": "forbidden_evidence_promotion",
                        "from": lower,
                        "to": promoted,
                    }
                )
        for field in ("evidence_status", "source_status"):
            value = str(spec.get(field, "")).strip().casefold()
            if value == "external_rules_engine":
                problems.append(
                    {
                        "deck_id": deck_id,
                        "kind": "structural_profile_claims_external_rules_engine",
                        "field": field,
                    }
                )
    return problems


def audit_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    opponent_dir = root / "data/opponents"
    checks: list[dict[str, Any]] = []

    if not opponent_dir.exists():
        checks.append(
            _result(
                "opponent_data_present",
                FAIL,
                evidence={"path": str(opponent_dir)},
            )
        )
        return _finalize(checks)

    structural_ids, structural_duplicates, specs = _collect_structural_profile_ids(opponent_dir)
    checks.append(
        _result(
            "unique_structural_profile_ids",
            PASS if not structural_duplicates else FAIL,
            evidence={
                "profile_count": len(structural_ids),
                "duplicates": structural_duplicates,
            },
        )
    )

    exact_ids, exact_problems = _collect_exact_profile_ids(opponent_dir)
    checks.append(
        _result(
            "official_precon_integrity",
            PASS if not exact_problems else FAIL,
            evidence={"profile_count": len(exact_ids), "problems": exact_problems},
        )
    )

    evidence_problems = _evidence_boundary_problems(specs)
    checks.append(
        _result(
            "structural_evidence_boundaries",
            PASS if not evidence_problems else FAIL,
            evidence={"problems": evidence_problems},
        )
    )

    registry_path = opponent_dir / "opponent_registry.json"
    if registry_path.exists():
        registry = _load_json(registry_path)
        current = {str(key): str(value) for key, value in registry.get("current", {}).items()}
        known_targets = structural_ids | exact_ids
        missing_targets = sorted(set(current.values()) - known_targets)
        checks.append(
            _result(
                "opponent_registry_referential_integrity",
                PASS if not missing_targets else FAIL,
                evidence={"missing_targets": missing_targets},
            )
        )

        valid_redirects = set(current) | set(current.values())
        broken_aliases = sorted(
            alias
            for alias, payload in registry.get("aliases", {}).items()
            if str(payload.get("redirect", "")) not in valid_redirects
        )
        checks.append(
            _result(
                "opponent_alias_referential_integrity",
                PASS if not broken_aliases else FAIL,
                evidence={"broken_aliases": broken_aliases},
            )
        )

        kaervek_ok = (
            current.get("kaervek/current") == "kaervek/current"
            and bool(str(registry.get("kaervek_deck_hash", "")))
        )
        checks.append(
            _result(
                "kaervek_frozen_reference_present",
                PASS if kaervek_ok else FAIL,
                evidence={
                    "registry_target": current.get("kaervek/current"),
                    "deck_hash_present": bool(str(registry.get("kaervek_deck_hash", ""))),
                },
            )
        )
    else:
        checks.append(_result("opponent_registry_referential_integrity", FAIL))
        checks.append(_result("opponent_alias_referential_integrity", FAIL))
        checks.append(_result("kaervek_frozen_reference_present", FAIL))

    checks.append(
        _result(
            "drive_primary_pod_and_frequency_policy",
            LIMITATION,
            limitations=[
                "Primary-pod and opponent-frequency policy is canonical Drive state; this repo-local "
                "auditor intentionally does not infer or mutate it."
            ],
        )
    )
    checks.append(
        _result(
            "deck_inventory_allocation_mutation",
            NOT_APPLICABLE,
            limitations=["This auditor is read-only and does not execute simulation mutation paths."],
        )
    )
    return _finalize(checks)


def _finalize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "pass": sum(check["status"] == PASS for check in checks),
        "fail": sum(check["status"] == FAIL for check in checks),
        "limitations": sum(check["status"] == LIMITATION for check in checks),
        "not_applicable": sum(check["status"] == NOT_APPLICABLE for check in checks),
    }
    return {"schema_version": "1.0", "checks": checks, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit repo-local Commander project invariants.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = audit_project(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
